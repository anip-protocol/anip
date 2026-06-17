package registryapi

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	"embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

//go:embed migrations/*.sql
var migrationFiles embed.FS

type PostgresStore struct {
	pool       *pgxpool.Pool
	signer     *RegistrySigner
	publicKeys []RegistryPublicKey
}

type PostgresStoreOptions struct {
	Signer          *RegistrySigner
	ExtraPublicKeys []RegistryPublicKey
	RunMigrations   bool
}

const registryMigrationAdvisoryLockID int64 = 2402402401

const RegistryPublishTokenPrefix = "anip_pat_"

type publisherSummaryScan struct {
	PublisherID   sql.NullString
	PublisherType sql.NullString
	DisplayName   sql.NullString
	WebsiteURL    sql.NullString
	Status        sql.NullString
	TrustLevel    sql.NullString
}

func (scan publisherSummaryScan) summary() *PublisherSummary {
	if !scan.PublisherID.Valid || strings.TrimSpace(scan.PublisherID.String) == "" {
		return nil
	}
	return &PublisherSummary{
		PublisherID:   scan.PublisherID.String,
		PublisherType: scan.PublisherType.String,
		DisplayName:   scan.DisplayName.String,
		WebsiteURL:    scan.WebsiteURL.String,
		Status:        scan.Status.String,
		TrustLevel:    scan.TrustLevel.String,
	}
}

func NewPostgresStore(dsn string) (*PostgresStore, error) {
	return NewPostgresStoreWithSigner(dsn, NewDevRegistrySigner())
}

func NewPostgresStoreWithSigner(dsn string, signer *RegistrySigner) (*PostgresStore, error) {
	return NewPostgresStoreWithSignerAndPublicKeys(dsn, signer, nil)
}

func NewPostgresStoreWithSignerAndPublicKeys(dsn string, signer *RegistrySigner, extraPublicKeys []RegistryPublicKey) (*PostgresStore, error) {
	return NewPostgresStoreWithOptions(dsn, PostgresStoreOptions{
		Signer:          signer,
		ExtraPublicKeys: extraPublicKeys,
		RunMigrations:   true,
	})
}

func NewPostgresStoreWithOptions(dsn string, options PostgresStoreOptions) (*PostgresStore, error) {
	signer := options.Signer
	if signer == nil {
		signer = NewDevRegistrySigner()
	}
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		return nil, fmt.Errorf("connect to postgres: %w", err)
	}
	if err := pool.Ping(context.Background()); err != nil {
		pool.Close()
		return nil, fmt.Errorf("ping postgres: %w", err)
	}

	store := &PostgresStore{
		pool:       pool,
		signer:     signer,
		publicKeys: MergeRegistryPublicKeys(signer.PublicKeyRecord(), options.ExtraPublicKeys),
	}
	if options.RunMigrations {
		if err := store.runMigrations(context.Background()); err != nil {
			pool.Close()
			return nil, fmt.Errorf("run migrations: %w", err)
		}
	}

	return store, nil
}

func (s *PostgresStore) RunMigrations(ctx context.Context) error {
	return s.runMigrations(ctx)
}

func (s *PostgresStore) CheckReady(ctx context.Context) error {
	if err := s.pool.Ping(ctx); err != nil {
		return fmt.Errorf("postgres ping failed: %w", err)
	}
	status, err := s.MigrationStatus(ctx)
	if err != nil {
		return fmt.Errorf("migration status failed: %w", err)
	}
	if !status.Applied {
		return fmt.Errorf("registry migrations pending: %s", strings.Join(status.Pending, ", "))
	}
	return nil
}

func (s *PostgresStore) MigrationStatus(ctx context.Context) (MigrationStatus, error) {
	expected, err := migrationNames()
	if err != nil {
		return MigrationStatus{}, err
	}
	var migrationsTableExists bool
	if err := s.pool.QueryRow(ctx, `SELECT to_regclass('public.registry_schema_migrations') IS NOT NULL`).Scan(&migrationsTableExists); err != nil {
		return MigrationStatus{}, err
	}
	if !migrationsTableExists {
		return MigrationStatus{Applied: false, ExpectedCount: len(expected), Pending: expected}, nil
	}

	rows, err := s.pool.Query(ctx, `SELECT filename FROM registry_schema_migrations`)
	if err != nil {
		return MigrationStatus{}, err
	}
	defer rows.Close()

	applied := map[string]bool{}
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			return MigrationStatus{}, err
		}
		applied[name] = true
	}
	if err := rows.Err(); err != nil {
		return MigrationStatus{}, err
	}

	pending := make([]string, 0)
	for _, name := range expected {
		if !applied[name] {
			pending = append(pending, name)
		}
	}
	return MigrationStatus{
		Applied:       len(pending) == 0,
		AppliedCount:  len(expected) - len(pending),
		ExpectedCount: len(expected),
		Pending:       pending,
	}, nil
}

func migrationNames() ([]string, error) {
	entries, err := migrationFiles.ReadDir("migrations")
	if err != nil {
		return nil, err
	}

	names := make([]string, 0, len(entries))
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".sql") {
			continue
		}
		names = append(names, entry.Name())
	}
	sort.Strings(names)
	return names, nil
}

func (s *PostgresStore) Close() error {
	s.pool.Close()
	return nil
}

func (s *PostgresStore) runMigrations(ctx context.Context) error {
	lockConn, err := s.pool.Acquire(ctx)
	if err != nil {
		return fmt.Errorf("acquire migration lock connection: %w", err)
	}
	defer lockConn.Release()
	if _, err := lockConn.Exec(ctx, `SELECT pg_advisory_lock($1)`, registryMigrationAdvisoryLockID); err != nil {
		return fmt.Errorf("acquire migration advisory lock: %w", err)
	}
	defer lockConn.Exec(context.Background(), `SELECT pg_advisory_unlock($1)`, registryMigrationAdvisoryLockID)

	if _, err := s.pool.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS registry_schema_migrations (
			filename TEXT PRIMARY KEY,
			applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
		)
	`); err != nil {
		return err
	}

	names, err := migrationNames()
	if err != nil {
		return err
	}

	for _, name := range names {
		var alreadyApplied bool
		if err := s.pool.QueryRow(ctx,
			`SELECT EXISTS (SELECT 1 FROM registry_schema_migrations WHERE filename = $1)`,
			name,
		).Scan(&alreadyApplied); err != nil {
			return err
		}
		if alreadyApplied {
			continue
		}

		contents, err := migrationFiles.ReadFile(filepath.Join("migrations", name))
		if err != nil {
			return err
		}

		tx, err := s.pool.Begin(ctx)
		if err != nil {
			return err
		}

		if _, err := tx.Exec(ctx, string(contents)); err != nil {
			_ = tx.Rollback(ctx)
			return fmt.Errorf("apply %s: %w", name, err)
		}
		if _, err := tx.Exec(ctx,
			`INSERT INTO registry_schema_migrations (filename) VALUES ($1)`,
			name,
		); err != nil {
			_ = tx.Rollback(ctx)
			return fmt.Errorf("record %s: %w", name, err)
		}
		if err := tx.Commit(ctx); err != nil {
			return fmt.Errorf("commit %s: %w", name, err)
		}
	}

	return nil
}

func (s *PostgresStore) ListPublications() []PublicationSummary {
	rows, err := s.pool.Query(context.Background(), `
		SELECT p.package_id, p.package_version, p.project_ref, p.product_revision_ref,
		       p.developer_revision_ref, p.contract_signature, p.publisher_id, p.publisher_type,
		       p.published_at, p.download_count,
		       pub.publisher_id, pub.publisher_type, pub.display_name, pub.website_url, pub.status, pub.trust_level
		FROM published_lineages l
		JOIN registry_packages p USING (package_id, package_version)
		LEFT JOIN registry_artifact_ownership ownership
		       ON ownership.artifact_kind = 'package'
		      AND ownership.artifact_id = p.package_id
		      AND ownership.status = 'active'
		LEFT JOIN registry_publishers pub
		       ON pub.publisher_id = ownership.publisher_id
		WHERE l.status = 'published'
		ORDER BY p.download_count DESC, p.published_at DESC, p.package_id ASC, p.package_version DESC
	`)
	if err != nil {
		return []PublicationSummary{}
	}
	defer rows.Close()

	items := make([]PublicationSummary, 0)
	for rows.Next() {
		var item PublicationSummary
		var publishedAt time.Time
		var publisher publisherSummaryScan
		if err := rows.Scan(
			&item.PackageID,
			&item.PackageVersion,
			&item.ProjectRef,
			&item.ProductRevisionRef,
			&item.DeveloperRevisionRef,
			&item.ContractSignature,
			&item.PublisherID,
			&item.PublisherType,
			&publishedAt,
			&item.DownloadCount,
			&publisher.PublisherID,
			&publisher.PublisherType,
			&publisher.DisplayName,
			&publisher.WebsiteURL,
			&publisher.Status,
			&publisher.TrustLevel,
		); err != nil {
			return []PublicationSummary{}
		}
		item.PublishedAt = publishedAt.UTC().Format(time.RFC3339)
		item.Publisher = publisher.summary()
		if pkg, ok := s.GetPackage(item.PackageID, item.PackageVersion); ok {
			item.Lineage = pkg.Lineage
		}
		items = append(items, item)
	}
	return items
}

func (s *PostgresStore) GetPackage(packageID, version string) (RegistryPackageRecord, bool) {
	var record RegistryPackageRecord
	var publishedAt time.Time
	var manifestBytes []byte
	var definitionBytes []byte
	var lockBytes []byte
	var publisher publisherSummaryScan

	err := s.pool.QueryRow(context.Background(), `
		SELECT p.package_id, p.package_version, p.project_ref, p.product_revision_ref,
		       p.developer_revision_ref, p.contract_signature, p.publisher_id, p.publisher_type, p.schema_version,
		       p.manifest_digest, p.definition_digest, p.lock_digest, p.published_at, p.download_count,
		       p.manifest, p.service_definition, p.recommended_lock,
		       pub.publisher_id, pub.publisher_type, pub.display_name, pub.website_url, pub.status, pub.trust_level
		FROM registry_packages p
		LEFT JOIN registry_artifact_ownership ownership
		       ON ownership.artifact_kind = 'package'
		      AND ownership.artifact_id = p.package_id
		      AND ownership.status = 'active'
		LEFT JOIN registry_publishers pub
		       ON pub.publisher_id = ownership.publisher_id
		WHERE p.package_id = $1 AND p.package_version = $2
	`, packageID, version).Scan(
		&record.PackageID,
		&record.PackageVersion,
		&record.ProjectRef,
		&record.ProductRevisionRef,
		&record.DeveloperRevisionRef,
		&record.ContractSignature,
		&record.PublisherID,
		&record.PublisherType,
		&record.SchemaVersion,
		&record.ManifestDigest,
		&record.DefinitionDigest,
		&record.LockDigest,
		&publishedAt,
		&record.DownloadCount,
		&manifestBytes,
		&definitionBytes,
		&lockBytes,
		&publisher.PublisherID,
		&publisher.PublisherType,
		&publisher.DisplayName,
		&publisher.WebsiteURL,
		&publisher.Status,
		&publisher.TrustLevel,
	)
	if err == pgx.ErrNoRows {
		return RegistryPackageRecord{}, false
	}
	if err != nil {
		return RegistryPackageRecord{}, false
	}

	record.PublishedAt = publishedAt.UTC().Format(time.RFC3339)
	if err := json.Unmarshal(manifestBytes, &record.Manifest); err != nil {
		return RegistryPackageRecord{}, false
	}
	if err := json.Unmarshal(definitionBytes, &record.ServiceDefinition); err != nil {
		return RegistryPackageRecord{}, false
	}
	if err := json.Unmarshal(lockBytes, &record.RecommendedLock); err != nil {
		return RegistryPackageRecord{}, false
	}
	record.Lineage = normalizeLineage(record.Manifest, record.RecommendedLock)
	record.Readme = stringFromAny(record.Manifest["readme"])
	record.SourceLinks = normalizeSourceLinks(sourceLinksFromAny(record.Manifest["source_links"]))
	record.ImplementationMaterials = normalizeImplementationMaterials(implementationMaterialsFromAny(record.Manifest["implementation_material"]))
	record.Publisher = publisher.summary()

	return record, true
}

func (s *PostgresStore) RecordPackageDownload(packageID, version string) (RegistryPackageRecord, bool) {
	commandTag, err := s.pool.Exec(context.Background(), `
		UPDATE registry_packages
		SET download_count = download_count + 1,
		    updated_at = now()
		WHERE package_id = $1 AND package_version = $2
	`, packageID, version)
	if err != nil || commandTag.RowsAffected() != 1 {
		return RegistryPackageRecord{}, false
	}
	return s.GetPackage(packageID, version)
}

func (s *PostgresStore) GetReceipt(packageID, version string) (RegistryReceipt, bool) {
	var receipt RegistryReceipt
	var issuedAt time.Time
	err := s.pool.QueryRow(context.Background(), `
		SELECT receipt_id, package_id, package_version, registry_signature, publisher_id, publisher_type, issued_at
		FROM registry_receipts
		WHERE package_id = $1 AND package_version = $2
	`, packageID, version).Scan(
		&receipt.ReceiptID,
		&receipt.PackageID,
		&receipt.PackageVersion,
		&receipt.RegistrySignature,
		&receipt.PublisherID,
		&receipt.PublisherType,
		&issuedAt,
	)
	if err == pgx.ErrNoRows {
		return RegistryReceipt{}, false
	}
	if err != nil {
		return RegistryReceipt{}, false
	}
	receipt.IssuedAt = issuedAt.UTC().Format(time.RFC3339)
	return registryReceiptWithSignatureMetadata(receipt), true
}

func (s *PostgresStore) ListPublicKeys() []RegistryPublicKey {
	if len(s.publicKeys) == 0 {
		return []RegistryPublicKey{s.signer.PublicKeyRecord()}
	}
	keys := make([]RegistryPublicKey, 0, len(s.publicKeys))
	keys = append(keys, s.publicKeys...)
	return keys
}

func (s *PostgresStore) PublishPackage(request PublishPackageRequest) (PublishPackageResult, error) {
	request = normalizePublishRequest(request)

	if request.PackageID == "" || request.PackageVersion == "" || request.ProjectRef == "" {
		return PublishPackageResult{}, errors.New("missing required publication fields")
	}

	tx, err := s.pool.Begin(context.Background())
	if err != nil {
		return PublishPackageResult{}, err
	}
	defer tx.Rollback(context.Background())

	var exists bool
	if err := tx.QueryRow(context.Background(), `
		SELECT EXISTS (
			SELECT 1 FROM registry_packages WHERE package_id = $1 AND package_version = $2
		)
	`, request.PackageID, request.PackageVersion).Scan(&exists); err != nil {
		return PublishPackageResult{}, err
	}
	if exists {
		return PublishPackageResult{}, ErrPackageVersionExists
	}

	publishedAt := time.Now().UTC()
	publication, pkg, receipt, err := buildPublishedArtifacts(request, publishedAt, s.signer)
	if err != nil {
		return PublishPackageResult{}, err
	}

	manifestBytes, err := json.Marshal(pkg.Manifest)
	if err != nil {
		return PublishPackageResult{}, err
	}
	definitionBytes, err := json.Marshal(pkg.ServiceDefinition)
	if err != nil {
		return PublishPackageResult{}, err
	}
	lockBytes, err := json.Marshal(pkg.RecommendedLock)
	if err != nil {
		return PublishPackageResult{}, err
	}

	publishedLineageID := storeKey(publication.PackageID, publication.PackageVersion)
	if _, err := tx.Exec(context.Background(), `
		INSERT INTO published_lineages (
			id, package_id, package_version, project_ref, product_revision_ref,
			developer_revision_ref, contract_signature, publisher_id, publisher_type, published_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
	`, publishedLineageID, publication.PackageID, publication.PackageVersion, publication.ProjectRef,
		publication.ProductRevisionRef, publication.DeveloperRevisionRef, publication.ContractSignature,
		publication.PublisherID, publication.PublisherType, publishedAt); err != nil {
		return PublishPackageResult{}, err
	}

	if _, err := tx.Exec(context.Background(), `
		INSERT INTO registry_packages (
			package_id, package_version, published_lineage_id, project_ref,
			product_revision_ref, developer_revision_ref, contract_signature,
			publisher_id, publisher_type, schema_version, manifest_digest, definition_digest, lock_digest, published_at,
			manifest, service_definition, recommended_lock
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17
		)
	`, pkg.PackageID, pkg.PackageVersion, publishedLineageID, pkg.ProjectRef,
		pkg.ProductRevisionRef, pkg.DeveloperRevisionRef, pkg.ContractSignature,
		pkg.PublisherID, pkg.PublisherType, pkg.SchemaVersion,
		pkg.ManifestDigest, pkg.DefinitionDigest, pkg.LockDigest, publishedAt,
		manifestBytes, definitionBytes, lockBytes); err != nil {
		return PublishPackageResult{}, err
	}

	issuedAt, err := time.Parse(time.RFC3339, receipt.IssuedAt)
	if err != nil {
		return PublishPackageResult{}, err
	}
	if _, err := tx.Exec(context.Background(), `
		INSERT INTO registry_receipts (
			receipt_id, package_id, package_version, registry_signature, publisher_id, publisher_type, issued_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7)
	`, receipt.ReceiptID, receipt.PackageID, receipt.PackageVersion, receipt.RegistrySignature,
		receipt.PublisherID, receipt.PublisherType, issuedAt); err != nil {
		return PublishPackageResult{}, err
	}
	if err := s.recordArtifactOwnership(context.Background(), tx, "package", pkg.PackageID, pkg.PublisherID); err != nil {
		return PublishPackageResult{}, err
	}

	if err := tx.Commit(context.Background()); err != nil {
		return PublishPackageResult{}, err
	}

	return PublishPackageResult{
		Publication: publication,
		Package:     pkg,
		Receipt:     receipt,
	}, nil
}

func (s *PostgresStore) ListTemplates() []TemplateSummary {
	rows, err := s.pool.Query(context.Background(), `
		SELECT template_id, template_version, template_kind, project_type, anip_spec_version,
		       domain, industry, systems, t.publisher_id, t.publisher_type, published_at, download_count, manifest,
		       pub.publisher_id, pub.publisher_type, pub.display_name, pub.website_url, pub.status, pub.trust_level
		FROM registry_templates t
		LEFT JOIN registry_artifact_ownership ownership
		       ON ownership.artifact_kind = 'template'
		      AND ownership.artifact_id = t.template_id
		      AND ownership.status = 'active'
		LEFT JOIN registry_publishers pub
		       ON pub.publisher_id = ownership.publisher_id
		ORDER BY t.download_count DESC, t.published_at DESC, t.template_id ASC, t.template_version DESC
	`)
	if err != nil {
		return []TemplateSummary{}
	}
	defer rows.Close()

	items := make([]TemplateSummary, 0)
	for rows.Next() {
		var item TemplateSummary
		var publishedAt time.Time
		var systemsBytes []byte
		var manifestBytes []byte
		var publisher publisherSummaryScan
		if err := rows.Scan(
			&item.TemplateID,
			&item.TemplateVersion,
			&item.TemplateKind,
			&item.ProjectType,
			&item.ANIPSpecVersion,
			&item.Domain,
			&item.Industry,
			&systemsBytes,
			&item.PublisherID,
			&item.PublisherType,
			&publishedAt,
			&item.DownloadCount,
			&manifestBytes,
			&publisher.PublisherID,
			&publisher.PublisherType,
			&publisher.DisplayName,
			&publisher.WebsiteURL,
			&publisher.Status,
			&publisher.TrustLevel,
		); err != nil {
			return []TemplateSummary{}
		}
		item.PublishedAt = publishedAt.UTC().Format(time.RFC3339)
		item.Publisher = publisher.summary()
		_ = json.Unmarshal(systemsBytes, &item.Systems)
		_ = json.Unmarshal(manifestBytes, &item.Manifest)
		items = append(items, item)
	}
	return items
}

func (s *PostgresStore) GetTemplate(templateID, version string) (RegistryTemplateRecord, bool) {
	var record RegistryTemplateRecord
	var publishedAt time.Time
	var systemsBytes []byte
	var manifestBytes []byte
	var templateBytes []byte
	var packageBytes []byte
	var publisher publisherSummaryScan
	err := s.pool.QueryRow(context.Background(), `
		SELECT template_id, template_version, template_kind, project_type, anip_spec_version,
		       domain, industry, systems, t.publisher_id, t.publisher_type, manifest_digest, template_digest,
		       package_digest, published_at, download_count, manifest, template, package,
		       pub.publisher_id, pub.publisher_type, pub.display_name, pub.website_url, pub.status, pub.trust_level
		FROM registry_templates t
		LEFT JOIN registry_artifact_ownership ownership
		       ON ownership.artifact_kind = 'template'
		      AND ownership.artifact_id = t.template_id
		      AND ownership.status = 'active'
		LEFT JOIN registry_publishers pub
		       ON pub.publisher_id = ownership.publisher_id
		WHERE t.template_id = $1 AND t.template_version = $2
	`, templateID, version).Scan(
		&record.TemplateID,
		&record.TemplateVersion,
		&record.TemplateKind,
		&record.ProjectType,
		&record.ANIPSpecVersion,
		&record.Domain,
		&record.Industry,
		&systemsBytes,
		&record.PublisherID,
		&record.PublisherType,
		&record.ManifestDigest,
		&record.TemplateDigest,
		&record.PackageDigest,
		&publishedAt,
		&record.DownloadCount,
		&manifestBytes,
		&templateBytes,
		&packageBytes,
		&publisher.PublisherID,
		&publisher.PublisherType,
		&publisher.DisplayName,
		&publisher.WebsiteURL,
		&publisher.Status,
		&publisher.TrustLevel,
	)
	if err == pgx.ErrNoRows {
		return RegistryTemplateRecord{}, false
	}
	if err != nil {
		return RegistryTemplateRecord{}, false
	}
	record.PublishedAt = publishedAt.UTC().Format(time.RFC3339)
	if err := json.Unmarshal(systemsBytes, &record.Systems); err != nil {
		return RegistryTemplateRecord{}, false
	}
	if err := json.Unmarshal(manifestBytes, &record.Manifest); err != nil {
		return RegistryTemplateRecord{}, false
	}
	if err := json.Unmarshal(templateBytes, &record.Template); err != nil {
		return RegistryTemplateRecord{}, false
	}
	if err := json.Unmarshal(packageBytes, &record.Package); err != nil {
		return RegistryTemplateRecord{}, false
	}
	record.Publisher = publisher.summary()
	return record, true
}

func (s *PostgresStore) RecordTemplateDownload(templateID, version string) (RegistryTemplateRecord, bool) {
	commandTag, err := s.pool.Exec(context.Background(), `
		UPDATE registry_templates
		SET download_count = download_count + 1,
		    updated_at = now()
		WHERE template_id = $1 AND template_version = $2
	`, templateID, version)
	if err != nil || commandTag.RowsAffected() != 1 {
		return RegistryTemplateRecord{}, false
	}
	return s.GetTemplate(templateID, version)
}

func (s *PostgresStore) PublishTemplate(request PublishTemplateRequest) (PublishTemplateResult, error) {
	request = normalizeTemplatePublishRequest(request)
	if request.TemplateID == "" || request.TemplateVersion == "" {
		return PublishTemplateResult{}, errors.New("missing required template publication fields")
	}
	var exists bool
	if err := s.pool.QueryRow(context.Background(), `
		SELECT EXISTS (
			SELECT 1 FROM registry_templates WHERE template_id = $1 AND template_version = $2
		)
	`, request.TemplateID, request.TemplateVersion).Scan(&exists); err != nil {
		return PublishTemplateResult{}, err
	}
	if exists {
		return PublishTemplateResult{}, ErrPackageVersionExists
	}
	record, err := buildPublishedTemplate(request, time.Now().UTC())
	if err != nil {
		return PublishTemplateResult{}, err
	}
	manifestBytes, err := json.Marshal(record.Manifest)
	if err != nil {
		return PublishTemplateResult{}, err
	}
	templateBytes, err := json.Marshal(record.Template)
	if err != nil {
		return PublishTemplateResult{}, err
	}
	packageBytes, err := json.Marshal(record.Package)
	if err != nil {
		return PublishTemplateResult{}, err
	}
	systemsBytes, err := json.Marshal(record.Systems)
	if err != nil {
		return PublishTemplateResult{}, err
	}
	publishedAt, err := time.Parse(time.RFC3339, record.PublishedAt)
	if err != nil {
		return PublishTemplateResult{}, err
	}
	tx, err := s.pool.Begin(context.Background())
	if err != nil {
		return PublishTemplateResult{}, err
	}
	defer tx.Rollback(context.Background())

	if _, err := tx.Exec(context.Background(), `
		INSERT INTO registry_templates (
			template_id, template_version, template_kind, project_type, anip_spec_version,
			domain, industry, systems, publisher_id, publisher_type, manifest_digest, template_digest,
			package_digest, published_at, manifest, template, package
		) VALUES (
			$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17
		)
	`, record.TemplateID, record.TemplateVersion, record.TemplateKind, record.ProjectType,
		record.ANIPSpecVersion, record.Domain, record.Industry, systemsBytes, record.PublisherID,
		record.PublisherType, record.ManifestDigest, record.TemplateDigest, record.PackageDigest,
		publishedAt, manifestBytes, templateBytes, packageBytes); err != nil {
		return PublishTemplateResult{}, err
	}
	if err := s.recordArtifactOwnership(context.Background(), tx, "template", record.TemplateID, record.PublisherID); err != nil {
		return PublishTemplateResult{}, err
	}
	if err := tx.Commit(context.Background()); err != nil {
		return PublishTemplateResult{}, err
	}
	return PublishTemplateResult{Template: record}, nil
}

func (s *PostgresStore) SeedDemoData() error {
	var count int
	if err := s.pool.QueryRow(context.Background(), `SELECT count(*) FROM published_lineages`).Scan(&count); err != nil {
		return err
	}
	if count > 0 {
		return nil
	}

	_, pkg, _ := DemoPublicationFixture()
	_, err := s.PublishPackage(PublishPackageRequest{
		PackageID:            pkg.PackageID,
		PackageVersion:       pkg.PackageVersion,
		ProjectRef:           pkg.ProjectRef,
		ProductRevisionRef:   pkg.ProductRevisionRef,
		DeveloperRevisionRef: pkg.DeveloperRevisionRef,
		ContractSignature:    pkg.ContractSignature,
		Lineage:              pkg.Lineage,
		SchemaVersion:        pkg.SchemaVersion,
		Manifest:             pkg.Manifest,
		ServiceDefinition:    pkg.ServiceDefinition,
		RecommendedLock:      pkg.RecommendedLock,
	})
	return err
}

func (s *PostgresStore) CountPublishedLineages() (int, error) {
	var count int
	if err := s.pool.QueryRow(context.Background(), `SELECT count(*) FROM published_lineages`).Scan(&count); err != nil {
		return 0, err
	}
	return count, nil
}

func (s *PostgresStore) BootstrapOfficialANIPPublisher(ctx context.Context, legacyPublisherIDs []string) error {
	publisherID := "anip"
	legacyPublisherIDs = normalizePublisherIDList(append(legacyPublisherIDs, publisherID))

	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)

	if _, err := tx.Exec(ctx, `
		INSERT INTO registry_publishers (
			publisher_id, publisher_type, display_name, description, website_url, status, trust_level
		) VALUES (
			'anip', 'official', 'ANIP.dev',
			'Official ANIP publisher for canonical protocol, tooling, showcase package, and starter template artifacts.',
			'https://anip.dev', 'active', 'official'
		)
		ON CONFLICT (publisher_id) DO UPDATE SET
			publisher_type = EXCLUDED.publisher_type,
			display_name = EXCLUDED.display_name,
			description = EXCLUDED.description,
			website_url = EXCLUDED.website_url,
			status = EXCLUDED.status,
			trust_level = EXCLUDED.trust_level,
			updated_at = now()
	`); err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO registry_namespaces (
			namespace, publisher_id, artifact_kinds, status
		) VALUES (
			'anip', 'anip', '["package", "template"]'::jsonb, 'active'
		)
		ON CONFLICT (namespace) DO UPDATE SET
			publisher_id = EXCLUDED.publisher_id,
			artifact_kinds = EXCLUDED.artifact_kinds,
			status = EXCLUDED.status,
			updated_at = now()
	`); err != nil {
		return err
	}

	packageCount, err := bootstrapOfficialOwnership(ctx, tx, "package", legacyPublisherIDs)
	if err != nil {
		return err
	}
	templateCount, err := bootstrapOfficialOwnership(ctx, tx, "template", legacyPublisherIDs)
	if err != nil {
		return err
	}

	if err := tx.Commit(ctx); err != nil {
		return err
	}
	_, _ = s.AppendAuditEvent(ctx, RegistryAuditEvent{
		ActorPublisherID: publisherID,
		EventType:        "publisher.bootstrap",
		TargetType:       "publisher",
		TargetID:         publisherID,
		Metadata: map[string]any{
			"legacy_publisher_ids": legacyPublisherIDs,
			"package_ownership":    packageCount,
			"template_ownership":   templateCount,
		},
	})
	return nil
}

func bootstrapOfficialOwnership(ctx context.Context, tx pgx.Tx, artifactKind string, legacyPublisherIDs []string) (int64, error) {
	var commandTag pgconn.CommandTag
	var err error
	switch artifactKind {
	case "package":
		commandTag, err = tx.Exec(ctx, `
			INSERT INTO registry_artifact_ownership (
				artifact_kind, artifact_id, publisher_id, namespace, status
			)
			SELECT 'package', p.package_id, 'anip', 'anip', 'active'
			FROM registry_packages p
			WHERE p.publisher_id = ANY($1)
			ON CONFLICT (artifact_kind, artifact_id) DO NOTHING
		`, legacyPublisherIDs)
	case "template":
		commandTag, err = tx.Exec(ctx, `
			INSERT INTO registry_artifact_ownership (
				artifact_kind, artifact_id, publisher_id, namespace, status
			)
			SELECT 'template', t.template_id, 'anip', 'anip', 'active'
			FROM registry_templates t
			WHERE t.publisher_id = ANY($1)
			ON CONFLICT (artifact_kind, artifact_id) DO NOTHING
		`, legacyPublisherIDs)
	default:
		return 0, fmt.Errorf("unsupported artifact kind %q", artifactKind)
	}
	if err != nil {
		return 0, err
	}
	return commandTag.RowsAffected(), nil
}

func normalizePublisherIDList(values []string) []string {
	seen := map[string]bool{}
	normalized := make([]string, 0, len(values))
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" || seen[value] {
			continue
		}
		seen[value] = true
		normalized = append(normalized, value)
	}
	return normalized
}

func (s *PostgresStore) recordArtifactOwnership(ctx context.Context, tx pgx.Tx, artifactKind string, artifactID string, publisherID string) error {
	artifactKind = strings.TrimSpace(artifactKind)
	artifactID = strings.TrimSpace(artifactID)
	publisherID = strings.TrimSpace(publisherID)
	if artifactKind == "" || artifactID == "" || publisherID == "" {
		return nil
	}

	var existingPublisher string
	var existingStatus string
	err := tx.QueryRow(ctx, `
		SELECT publisher_id, status
		FROM registry_artifact_ownership
		WHERE artifact_kind = $1 AND artifact_id = $2
	`, artifactKind, artifactID).Scan(&existingPublisher, &existingStatus)
	if err == nil {
		if existingPublisher != publisherID || existingStatus != "active" {
			return ErrUnauthorizedPublish
		}
		return nil
	}
	if err != pgx.ErrNoRows {
		return err
	}

	var namespace string
	err = tx.QueryRow(ctx, `
		SELECT namespace
		FROM registry_namespaces
		WHERE publisher_id = $1 AND status = 'active'
		  AND artifact_kinds ? $2
		  AND ($3 = namespace OR starts_with($3, namespace || '/'))
		ORDER BY length(namespace) DESC
		LIMIT 1
	`, publisherID, artifactKind, artifactID).Scan(&namespace)
	if err == pgx.ErrNoRows {
		return nil
	}
	if err != nil {
		return err
	}
	_, err = tx.Exec(ctx, `
		INSERT INTO registry_artifact_ownership (
			artifact_kind, artifact_id, publisher_id, namespace, status
		) VALUES (
			$1, $2, $3, $4, 'active'
		)
	`, artifactKind, artifactID, publisherID, namespace)
	return err
}

func (s *PostgresStore) GetPublisher(ctx context.Context, publisherID string) (RegistryPublisher, bool, error) {
	var publisher RegistryPublisher
	var createdBy sql.NullString
	var createdAt time.Time
	var updatedAt time.Time
	err := s.pool.QueryRow(ctx, `
		SELECT publisher_id, publisher_type, display_name, description, website_url,
		       status, trust_level, created_by_user_id::text, created_at, updated_at
		FROM registry_publishers
		WHERE publisher_id = $1
	`, strings.TrimSpace(publisherID)).Scan(
		&publisher.PublisherID,
		&publisher.PublisherType,
		&publisher.DisplayName,
		&publisher.Description,
		&publisher.WebsiteURL,
		&publisher.Status,
		&publisher.TrustLevel,
		&createdBy,
		&createdAt,
		&updatedAt,
	)
	if err == pgx.ErrNoRows {
		return RegistryPublisher{}, false, nil
	}
	if err != nil {
		return RegistryPublisher{}, false, err
	}
	if createdBy.Valid {
		publisher.CreatedByUserID = createdBy.String
	}
	publisher.CreatedAt = createdAt.UTC().Format(time.RFC3339)
	publisher.UpdatedAt = updatedAt.UTC().Format(time.RFC3339)
	return publisher, true, nil
}

func (s *PostgresStore) UpdatePublisher(ctx context.Context, publisherID string, request UpdatePublisherRequest) (RegistryPublisher, error) {
	publisherID = strings.TrimSpace(publisherID)
	displayName := strings.TrimSpace(request.DisplayName)
	description := strings.TrimSpace(request.Description)
	websiteURL := strings.TrimSpace(request.WebsiteURL)
	if publisherID == "" || displayName == "" {
		return RegistryPublisher{}, ErrInvalidPackage
	}
	var publisher RegistryPublisher
	var createdBy sql.NullString
	var createdAt time.Time
	var updatedAt time.Time
	err := s.pool.QueryRow(ctx, `
		UPDATE registry_publishers
		SET display_name = $2,
		    description = $3,
		    website_url = $4,
		    updated_at = now()
		WHERE publisher_id = $1 AND status = 'active'
		RETURNING publisher_id, publisher_type, display_name, description, website_url,
		          status, trust_level, created_by_user_id::text, created_at, updated_at
	`, publisherID, displayName, description, websiteURL).Scan(
		&publisher.PublisherID,
		&publisher.PublisherType,
		&publisher.DisplayName,
		&publisher.Description,
		&publisher.WebsiteURL,
		&publisher.Status,
		&publisher.TrustLevel,
		&createdBy,
		&createdAt,
		&updatedAt,
	)
	if err != nil {
		return RegistryPublisher{}, err
	}
	if createdBy.Valid {
		publisher.CreatedByUserID = createdBy.String
	}
	publisher.CreatedAt = createdAt.UTC().Format(time.RFC3339)
	publisher.UpdatedAt = updatedAt.UTC().Format(time.RFC3339)
	_, _ = s.AppendAuditEvent(ctx, RegistryAuditEvent{
		ActorPublisherID: publisherID,
		EventType:        "publisher.updated",
		TargetType:       "publisher",
		TargetID:         publisherID,
		Metadata: map[string]any{
			"display_name": displayName,
			"website_url":  websiteURL,
		},
	})
	return publisher, nil
}

func (s *PostgresStore) ListPublisherNamespaces(ctx context.Context, publisherID string) ([]RegistryNamespaceSummary, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT namespace, publisher_id, artifact_kinds, status, created_at, updated_at
		FROM registry_namespaces
		WHERE publisher_id = $1
		ORDER BY namespace ASC
	`, strings.TrimSpace(publisherID))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := []RegistryNamespaceSummary{}
	for rows.Next() {
		item, err := scanRegistryNamespaceSummary(rows)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, rows.Err()
}

func (s *PostgresStore) CreatePublisherNamespace(ctx context.Context, publisherID string, request CreateNamespaceRequest) (RegistryNamespaceSummary, error) {
	publisherID = strings.TrimSpace(publisherID)
	namespace := strings.ToLower(strings.TrimSpace(request.Namespace))
	artifactKinds := normalizeArtifactKinds(request.ArtifactKinds)
	if publisherID == "" || !validRegistryNamespace(namespace) || len(artifactKinds) == 0 {
		return RegistryNamespaceSummary{}, ErrInvalidPackage
	}
	artifactKindsBytes, err := json.Marshal(artifactKinds)
	if err != nil {
		return RegistryNamespaceSummary{}, err
	}
	item, err := scanRegistryNamespaceSummary(s.pool.QueryRow(ctx, `
		INSERT INTO registry_namespaces (
			namespace, publisher_id, artifact_kinds, status
		) VALUES (
			$1, $2, $3, 'pending_verification'
		)
		RETURNING namespace, publisher_id, artifact_kinds, status, created_at, updated_at
	`, namespace, publisherID, artifactKindsBytes))
	if err != nil {
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23505" {
			return RegistryNamespaceSummary{}, ErrNamespaceExists
		}
		return RegistryNamespaceSummary{}, err
	}
	_, _ = s.AppendAuditEvent(ctx, RegistryAuditEvent{
		ActorPublisherID: publisherID,
		EventType:        "namespace.created",
		TargetType:       "namespace",
		TargetID:         namespace,
		Metadata: map[string]any{
			"artifact_kinds": artifactKinds,
		},
	})
	return item, nil
}

func (s *PostgresStore) UpdateNamespaceStatus(ctx context.Context, namespace string, request UpdateNamespaceStatusRequest) (RegistryNamespaceSummary, bool, error) {
	namespace = strings.ToLower(strings.TrimSpace(namespace))
	status := strings.ToLower(strings.TrimSpace(request.Status))
	reason := strings.TrimSpace(request.Reason)
	if !validRegistryNamespace(namespace) || !validRegistryNamespaceStatus(status) {
		return RegistryNamespaceSummary{}, false, ErrInvalidPackage
	}
	item, err := scanRegistryNamespaceSummary(s.pool.QueryRow(ctx, `
		UPDATE registry_namespaces
		SET status = $2, updated_at = now()
		WHERE namespace = $1
		RETURNING namespace, publisher_id, artifact_kinds, status, created_at, updated_at
	`, namespace, status))
	if err == pgx.ErrNoRows {
		return RegistryNamespaceSummary{}, false, nil
	}
	if err != nil {
		return RegistryNamespaceSummary{}, false, err
	}
	_, _ = s.AppendAuditEvent(ctx, RegistryAuditEvent{
		EventType:  "namespace.status.updated",
		TargetType: "namespace",
		TargetID:   namespace,
		Metadata: map[string]any{
			"status": status,
			"reason": reason,
		},
	})
	return item, true, nil
}

func (s *PostgresStore) AppendAuditEvent(ctx context.Context, event RegistryAuditEvent) (RegistryAuditEvent, error) {
	event.EventID = strings.TrimSpace(event.EventID)
	if event.EventID == "" {
		id, err := randomUUIDString()
		if err != nil {
			return RegistryAuditEvent{}, fmt.Errorf("generate audit event id: %w", err)
		}
		event.EventID = id
	}
	event.EventType = strings.TrimSpace(event.EventType)
	event.TargetType = strings.TrimSpace(event.TargetType)
	event.TargetID = strings.TrimSpace(event.TargetID)
	if event.EventType == "" || event.TargetType == "" || event.TargetID == "" {
		return RegistryAuditEvent{}, errors.New("event_type, target_type, and target_id are required")
	}
	if event.Metadata == nil {
		event.Metadata = map[string]any{}
	}
	metadataBytes, err := json.Marshal(event.Metadata)
	if err != nil {
		return RegistryAuditEvent{}, fmt.Errorf("marshal audit metadata: %w", err)
	}

	var inserted RegistryAuditEvent
	var actorUser sql.NullString
	var actorPublisher sql.NullString
	var tokenID sql.NullString
	var ipHash sql.NullString
	var userAgentHash sql.NullString
	var returnedMetadata []byte
	var createdAt time.Time
	err = s.pool.QueryRow(ctx, `
		INSERT INTO registry_audit_events (
			event_id, actor_user_id, actor_publisher_id, token_id, event_type,
			target_type, target_id, metadata, ip_hash, user_agent_hash
		) VALUES (
			$1::uuid, NULLIF($2, '')::uuid, NULLIF($3, ''), NULLIF($4, '')::uuid, $5,
			$6, $7, $8, NULLIF($9, ''), NULLIF($10, '')
		)
		RETURNING event_id::text, actor_user_id::text, actor_publisher_id, token_id::text,
		          event_type, target_type, target_id, metadata, ip_hash, user_agent_hash, created_at
	`, event.EventID, strings.TrimSpace(event.ActorUserID), strings.TrimSpace(event.ActorPublisherID),
		strings.TrimSpace(event.TokenID), event.EventType, event.TargetType, event.TargetID,
		metadataBytes, strings.TrimSpace(event.IPHash), strings.TrimSpace(event.UserAgentHash)).Scan(
		&inserted.EventID,
		&actorUser,
		&actorPublisher,
		&tokenID,
		&inserted.EventType,
		&inserted.TargetType,
		&inserted.TargetID,
		&returnedMetadata,
		&ipHash,
		&userAgentHash,
		&createdAt,
	)
	if err != nil {
		return RegistryAuditEvent{}, err
	}
	if actorUser.Valid {
		inserted.ActorUserID = actorUser.String
	}
	if actorPublisher.Valid {
		inserted.ActorPublisherID = actorPublisher.String
	}
	if tokenID.Valid {
		inserted.TokenID = tokenID.String
	}
	if ipHash.Valid {
		inserted.IPHash = ipHash.String
	}
	if userAgentHash.Valid {
		inserted.UserAgentHash = userAgentHash.String
	}
	if err := json.Unmarshal(returnedMetadata, &inserted.Metadata); err != nil {
		return RegistryAuditEvent{}, fmt.Errorf("decode audit metadata: %w", err)
	}
	inserted.CreatedAt = createdAt.UTC().Format(time.RFC3339)
	return inserted, nil
}

func (s *PostgresStore) AuthorizePublish(ctx context.Context, token string, operation string, artifactID string) (PublishAuthContext, error) {
	operation = strings.TrimSpace(operation)
	artifactID = strings.TrimSpace(artifactID)
	if operation == "" || artifactID == "" {
		return PublishAuthContext{}, ErrUnauthorizedPublish
	}
	auth, scopes, err := s.AuthenticatePublisherToken(ctx, token)
	if err != nil {
		return PublishAuthContext{}, err
	}
	if !stringInSet(operation, scopes.Operations) {
		return PublishAuthContext{}, ErrUnauthorizedPublish
	}
	artifactKind := strings.TrimPrefix(operation, "publish:")
	if artifactKind != "package" && artifactKind != "template" {
		return PublishAuthContext{}, ErrUnauthorizedPublish
	}
	if err := s.ensureArtifactPublishAllowed(ctx, auth.PublisherID, artifactKind, artifactID, scopes); err != nil {
		return PublishAuthContext{}, err
	}
	_, _ = s.AppendAuditEvent(ctx, RegistryAuditEvent{
		ActorPublisherID: auth.PublisherID,
		TokenID:          auth.TokenID,
		EventType:        "token.used",
		TargetType:       artifactKind,
		TargetID:         artifactID,
		Metadata: map[string]any{
			"operation": operation,
		},
	})
	return auth, nil
}

func (s *PostgresStore) AuthenticatePublisherToken(ctx context.Context, token string) (PublishAuthContext, RegistryPublishTokenScopes, error) {
	tokenID, tokenSecret, ok := parseRegistryPublishToken(token)
	if !ok {
		return PublishAuthContext{}, RegistryPublishTokenScopes{}, ErrUnauthorizedPublish
	}

	var auth PublishAuthContext
	var publisherStatus string
	var scopesBytes []byte
	var expiresAt sql.NullTime
	var revokedAt sql.NullTime
	err := s.pool.QueryRow(ctx, `
		SELECT t.publisher_id, p.publisher_type, p.status, t.scopes, t.expires_at, t.revoked_at
		FROM registry_publish_tokens t
		JOIN registry_publishers p ON p.publisher_id = t.publisher_id
		WHERE t.token_id = $1::uuid AND t.token_hash = $2
	`, tokenID, RegistryPublishTokenSecretHash(tokenSecret)).Scan(
		&auth.PublisherID,
		&auth.PublisherType,
		&publisherStatus,
		&scopesBytes,
		&expiresAt,
		&revokedAt,
	)
	if err == pgx.ErrNoRows {
		return PublishAuthContext{}, RegistryPublishTokenScopes{}, ErrUnauthorizedPublish
	}
	if err != nil {
		return PublishAuthContext{}, RegistryPublishTokenScopes{}, err
	}
	if publisherStatus != "active" || revokedAt.Valid || (expiresAt.Valid && !expiresAt.Time.After(time.Now().UTC())) {
		return PublishAuthContext{}, RegistryPublishTokenScopes{}, ErrUnauthorizedPublish
	}

	var scopes RegistryPublishTokenScopes
	if err := json.Unmarshal(scopesBytes, &scopes); err != nil {
		return PublishAuthContext{}, RegistryPublishTokenScopes{}, fmt.Errorf("decode publish token scopes: %w", err)
	}
	if _, err := s.pool.Exec(ctx, `
		UPDATE registry_publish_tokens
		SET last_used_at = now(), updated_at = now()
		WHERE token_id = $1::uuid
	`, tokenID); err != nil {
		return PublishAuthContext{}, RegistryPublishTokenScopes{}, err
	}
	auth.TokenID = tokenID
	return auth, scopes, nil
}

func (s *PostgresStore) ListPublisherArtifacts(ctx context.Context, publisherID string) ([]PublisherArtifactSummary, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT artifact_kind, artifact_id, namespace, status, created_at, updated_at
		FROM registry_artifact_ownership
		WHERE publisher_id = $1
		ORDER BY artifact_kind ASC, artifact_id ASC
	`, strings.TrimSpace(publisherID))
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := []PublisherArtifactSummary{}
	for rows.Next() {
		var item PublisherArtifactSummary
		var createdAt time.Time
		var updatedAt time.Time
		if err := rows.Scan(&item.ArtifactKind, &item.ArtifactID, &item.Namespace, &item.Status, &createdAt, &updatedAt); err != nil {
			return nil, err
		}
		item.CreatedAt = createdAt.UTC().Format(time.RFC3339)
		item.UpdatedAt = updatedAt.UTC().Format(time.RFC3339)
		items = append(items, item)
	}
	return items, rows.Err()
}

func (s *PostgresStore) ListPublisherTokens(ctx context.Context, publisherID string) ([]RegistryPublishTokenSummary, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT token_id::text, publisher_id, label, scopes, expires_at, last_used_at, revoked_at, created_at, updated_at
		FROM registry_publish_tokens
		WHERE publisher_id = $1
		ORDER BY revoked_at NULLS FIRST, created_at DESC, label ASC
	`, strings.TrimSpace(publisherID))
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := []RegistryPublishTokenSummary{}
	for rows.Next() {
		item, err := scanRegistryPublishTokenSummary(rows)
		if err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, rows.Err()
}

func (s *PostgresStore) CreatePublisherToken(ctx context.Context, publisherID string, request CreatePublishTokenRequest) (CreatePublishTokenResult, error) {
	publisherID = strings.TrimSpace(publisherID)
	label := strings.TrimSpace(request.Label)
	if publisherID == "" || label == "" {
		return CreatePublishTokenResult{}, ErrInvalidPackage
	}
	scopes := normalizeRegistryPublishTokenScopes(request.Scopes)
	if len(scopes.Operations) == 0 {
		return CreatePublishTokenResult{}, ErrUnauthorizedPublish
	}
	if err := s.ensurePublisherScopesAllowed(ctx, publisherID, scopes); err != nil {
		return CreatePublishTokenResult{}, err
	}
	tokenID, err := randomUUIDString()
	if err != nil {
		return CreatePublishTokenResult{}, err
	}
	secret, err := randomTokenSecret()
	if err != nil {
		return CreatePublishTokenResult{}, err
	}
	scopesBytes, err := json.Marshal(scopes)
	if err != nil {
		return CreatePublishTokenResult{}, err
	}
	var expiresAt sql.NullTime
	if strings.TrimSpace(request.ExpiresAt) != "" {
		parsed, err := time.Parse(time.RFC3339, strings.TrimSpace(request.ExpiresAt))
		if err != nil {
			return CreatePublishTokenResult{}, ErrInvalidPackage
		}
		expiresAt = sql.NullTime{Time: parsed.UTC(), Valid: true}
	}

	var result RegistryPublishTokenSummary
	result, err = scanRegistryPublishTokenSummary(s.pool.QueryRow(ctx, `
		INSERT INTO registry_publish_tokens (
			token_id, publisher_id, token_hash, label, scopes, expires_at
		) VALUES (
			$1::uuid, $2, $3, $4, $5, $6
		)
		RETURNING token_id::text, publisher_id, label, scopes, expires_at, last_used_at, revoked_at, created_at, updated_at
	`, tokenID, publisherID, RegistryPublishTokenSecretHash(secret), label, scopesBytes, expiresAt))
	if err != nil {
		return CreatePublishTokenResult{}, err
	}
	_, _ = s.AppendAuditEvent(ctx, RegistryAuditEvent{
		ActorPublisherID: publisherID,
		TokenID:          tokenID,
		EventType:        "token.created",
		TargetType:       "token",
		TargetID:         tokenID,
		Metadata: map[string]any{
			"label": label,
		},
	})
	return CreatePublishTokenResult{
		Token:       result,
		BearerToken: RegistryPublishTokenPrefix + tokenID + "_" + secret,
	}, nil
}

func (s *PostgresStore) RevokePublisherToken(ctx context.Context, publisherID string, tokenID string) (RegistryPublishTokenSummary, bool, error) {
	var result RegistryPublishTokenSummary
	result, err := scanRegistryPublishTokenSummary(s.pool.QueryRow(ctx, `
		UPDATE registry_publish_tokens
		SET revoked_at = COALESCE(revoked_at, now()), updated_at = now()
		WHERE publisher_id = $1 AND token_id = $2::uuid
		RETURNING token_id::text, publisher_id, label, scopes, expires_at, last_used_at, revoked_at, created_at, updated_at
	`, strings.TrimSpace(publisherID), strings.TrimSpace(tokenID)))
	if err == pgx.ErrNoRows {
		return RegistryPublishTokenSummary{}, false, nil
	}
	if err != nil {
		return RegistryPublishTokenSummary{}, false, err
	}
	_, _ = s.AppendAuditEvent(ctx, RegistryAuditEvent{
		ActorPublisherID: strings.TrimSpace(publisherID),
		TokenID:          tokenID,
		EventType:        "token.revoked",
		TargetType:       "token",
		TargetID:         tokenID,
		Metadata:         map[string]any{},
	})
	return result, true, nil
}

func (s *PostgresStore) ensurePublisherScopesAllowed(ctx context.Context, publisherID string, scopes RegistryPublishTokenScopes) error {
	for _, namespace := range scopes.Namespaces {
		var exists bool
		if err := s.pool.QueryRow(ctx, `
			SELECT EXISTS (
				SELECT 1
				FROM registry_namespaces
				WHERE publisher_id = $1 AND namespace = $2 AND status = 'active'
			)
		`, publisherID, namespace).Scan(&exists); err != nil {
			return err
		}
		if !exists {
			return ErrUnauthorizedPublish
		}
	}
	for _, packageID := range scopes.PackageIDs {
		if err := s.ensureArtifactPublishAllowed(ctx, publisherID, "package", packageID, scopes); err != nil {
			return err
		}
	}
	for _, templateID := range scopes.TemplateIDs {
		if err := s.ensureArtifactPublishAllowed(ctx, publisherID, "template", templateID, scopes); err != nil {
			return err
		}
	}
	return nil
}

func (s *PostgresStore) ensureArtifactPublishAllowed(ctx context.Context, publisherID string, artifactKind string, artifactID string, scopes RegistryPublishTokenScopes) error {
	var ownedPublisher sql.NullString
	var ownershipStatus sql.NullString
	err := s.pool.QueryRow(ctx, `
		SELECT publisher_id, status
		FROM registry_artifact_ownership
		WHERE artifact_kind = $1 AND artifact_id = $2
	`, artifactKind, artifactID).Scan(&ownedPublisher, &ownershipStatus)
	if err != nil && err != pgx.ErrNoRows {
		return err
	}
	if ownedPublisher.Valid {
		if ownedPublisher.String != publisherID || ownershipStatus.String != "active" {
			return ErrUnauthorizedPublish
		}
		return nil
	}

	if artifactKind == "package" && stringInSet(artifactID, scopes.PackageIDs) {
		return nil
	}
	if artifactKind == "template" && stringInSet(artifactID, scopes.TemplateIDs) {
		return nil
	}
	for _, namespace := range scopes.Namespaces {
		namespace = strings.TrimSpace(namespace)
		if namespace == "" {
			continue
		}
		if artifactID != namespace && !strings.HasPrefix(artifactID, namespace+"/") {
			continue
		}
		var exists bool
		if err := s.pool.QueryRow(ctx, `
			SELECT EXISTS (
				SELECT 1
				FROM registry_namespaces
				WHERE namespace = $1 AND publisher_id = $2 AND status = 'active'
				  AND artifact_kinds ? $3
			)
		`, namespace, publisherID, artifactKind).Scan(&exists); err != nil {
			return err
		}
		if exists {
			return nil
		}
	}
	return ErrUnauthorizedPublish
}

type registryPublishTokenRowScanner interface {
	Scan(dest ...any) error
}

func scanRegistryPublishTokenSummary(row registryPublishTokenRowScanner) (RegistryPublishTokenSummary, error) {
	var item RegistryPublishTokenSummary
	var scopesBytes []byte
	var expiresAt sql.NullTime
	var lastUsedAt sql.NullTime
	var revokedAt sql.NullTime
	var createdAt time.Time
	var updatedAt time.Time
	err := row.Scan(
		&item.TokenID,
		&item.PublisherID,
		&item.Label,
		&scopesBytes,
		&expiresAt,
		&lastUsedAt,
		&revokedAt,
		&createdAt,
		&updatedAt,
	)
	if err != nil {
		return RegistryPublishTokenSummary{}, err
	}
	if len(scopesBytes) > 0 {
		if err := json.Unmarshal(scopesBytes, &item.Scopes); err != nil {
			return RegistryPublishTokenSummary{}, err
		}
	}
	if expiresAt.Valid {
		item.ExpiresAt = expiresAt.Time.UTC().Format(time.RFC3339)
	}
	if lastUsedAt.Valid {
		item.LastUsedAt = lastUsedAt.Time.UTC().Format(time.RFC3339)
	}
	if revokedAt.Valid {
		item.RevokedAt = revokedAt.Time.UTC().Format(time.RFC3339)
	}
	item.CreatedAt = createdAt.UTC().Format(time.RFC3339)
	item.UpdatedAt = updatedAt.UTC().Format(time.RFC3339)
	return item, nil
}

func normalizeRegistryPublishTokenScopes(scopes RegistryPublishTokenScopes) RegistryPublishTokenScopes {
	return RegistryPublishTokenScopes{
		Operations:  normalizeStringSet(scopes.Operations),
		Namespaces:  normalizeStringSet(scopes.Namespaces),
		PackageIDs:  normalizeStringSet(scopes.PackageIDs),
		TemplateIDs: normalizeStringSet(scopes.TemplateIDs),
	}
}

func normalizeStringSet(values []string) []string {
	seen := map[string]bool{}
	normalized := make([]string, 0, len(values))
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" || seen[value] {
			continue
		}
		seen[value] = true
		normalized = append(normalized, value)
	}
	return normalized
}

func randomTokenSecret() (string, error) {
	var bytes [32]byte
	if _, err := rand.Read(bytes[:]); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes[:]), nil
}

func scanRegistryNamespaceSummary(row registryPublishTokenRowScanner) (RegistryNamespaceSummary, error) {
	var item RegistryNamespaceSummary
	var artifactKindsBytes []byte
	var createdAt time.Time
	var updatedAt time.Time
	if err := row.Scan(
		&item.Namespace,
		&item.PublisherID,
		&artifactKindsBytes,
		&item.Status,
		&createdAt,
		&updatedAt,
	); err != nil {
		return RegistryNamespaceSummary{}, err
	}
	if len(artifactKindsBytes) > 0 {
		if err := json.Unmarshal(artifactKindsBytes, &item.ArtifactKinds); err != nil {
			return RegistryNamespaceSummary{}, err
		}
	}
	item.CreatedAt = createdAt.UTC().Format(time.RFC3339)
	item.UpdatedAt = updatedAt.UTC().Format(time.RFC3339)
	return item, nil
}

func normalizeArtifactKinds(values []string) []string {
	allowed := map[string]bool{"package": true, "template": true}
	normalized := make([]string, 0, len(values))
	seen := map[string]bool{}
	for _, value := range values {
		value = strings.ToLower(strings.TrimSpace(value))
		if !allowed[value] || seen[value] {
			continue
		}
		seen[value] = true
		normalized = append(normalized, value)
	}
	return normalized
}

func validRegistryNamespace(namespace string) bool {
	if namespace == "" || len(namespace) > 80 {
		return false
	}
	for _, r := range namespace {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '-' || r == '_' || r == '/' {
			continue
		}
		return false
	}
	return !strings.HasPrefix(namespace, "/") && !strings.HasSuffix(namespace, "/") && !strings.Contains(namespace, "//")
}

func validRegistryNamespaceStatus(status string) bool {
	switch status {
	case "pending_verification", "active", "reserved", "suspended", "rejected":
		return true
	default:
		return false
	}
}

func RegistryPublishTokenSecretHash(secret string) string {
	sum := sha256.Sum256([]byte(secret))
	return hex.EncodeToString(sum[:])
}

func parseRegistryPublishToken(token string) (string, string, bool) {
	token = strings.TrimSpace(token)
	if !strings.HasPrefix(token, RegistryPublishTokenPrefix) {
		return "", "", false
	}
	remainder := strings.TrimPrefix(token, RegistryPublishTokenPrefix)
	tokenID, secret, ok := strings.Cut(remainder, "_")
	if !ok || strings.TrimSpace(tokenID) == "" || strings.TrimSpace(secret) == "" {
		return "", "", false
	}
	return tokenID, secret, true
}

func stringInSet(value string, candidates []string) bool {
	value = strings.TrimSpace(value)
	for _, candidate := range candidates {
		if value == strings.TrimSpace(candidate) {
			return true
		}
	}
	return false
}

func randomUUIDString() (string, error) {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x",
		b[0:4],
		b[4:6],
		b[6:8],
		b[8:10],
		b[10:16],
	), nil
}
