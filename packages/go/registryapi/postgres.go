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
		       p.published_at, p.download_count
		FROM published_lineages l
		JOIN registry_packages p USING (package_id, package_version)
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
		); err != nil {
			return []PublicationSummary{}
		}
		item.PublishedAt = publishedAt.UTC().Format(time.RFC3339)
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

	err := s.pool.QueryRow(context.Background(), `
		SELECT package_id, package_version, project_ref, product_revision_ref,
		       developer_revision_ref, contract_signature, publisher_id, publisher_type, schema_version,
		       manifest_digest, definition_digest, lock_digest, published_at, download_count,
		       manifest, service_definition, recommended_lock
		FROM registry_packages
		WHERE package_id = $1 AND package_version = $2
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
		       domain, industry, systems, publisher_id, publisher_type, published_at, download_count, manifest
		FROM registry_templates
		ORDER BY download_count DESC, published_at DESC, template_id ASC, template_version DESC
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
		); err != nil {
			return []TemplateSummary{}
		}
		item.PublishedAt = publishedAt.UTC().Format(time.RFC3339)
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
	err := s.pool.QueryRow(context.Background(), `
		SELECT template_id, template_version, template_kind, project_type, anip_spec_version,
		       domain, industry, systems, publisher_id, publisher_type, manifest_digest, template_digest,
		       package_digest, published_at, download_count, manifest, template, package
		FROM registry_templates
		WHERE template_id = $1 AND template_version = $2
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

type registryPublishTokenScopes struct {
	Operations  []string `json:"operations"`
	Namespaces  []string `json:"namespaces"`
	PackageIDs  []string `json:"package_ids"`
	TemplateIDs []string `json:"template_ids"`
}

func (s *PostgresStore) AuthorizePublish(ctx context.Context, token string, operation string, artifactID string) (PublishAuthContext, error) {
	tokenID, tokenSecret, ok := parseRegistryPublishToken(token)
	if !ok {
		return PublishAuthContext{}, ErrUnauthorizedPublish
	}
	operation = strings.TrimSpace(operation)
	artifactID = strings.TrimSpace(artifactID)
	if operation == "" || artifactID == "" {
		return PublishAuthContext{}, ErrUnauthorizedPublish
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
		return PublishAuthContext{}, ErrUnauthorizedPublish
	}
	if err != nil {
		return PublishAuthContext{}, err
	}
	if publisherStatus != "active" || revokedAt.Valid || (expiresAt.Valid && !expiresAt.Time.After(time.Now().UTC())) {
		return PublishAuthContext{}, ErrUnauthorizedPublish
	}

	var scopes registryPublishTokenScopes
	if err := json.Unmarshal(scopesBytes, &scopes); err != nil {
		return PublishAuthContext{}, fmt.Errorf("decode publish token scopes: %w", err)
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

	if _, err := s.pool.Exec(ctx, `
		UPDATE registry_publish_tokens
		SET last_used_at = now(), updated_at = now()
		WHERE token_id = $1::uuid
	`, tokenID); err != nil {
		return PublishAuthContext{}, err
	}
	auth.TokenID = tokenID
	_, _ = s.AppendAuditEvent(ctx, RegistryAuditEvent{
		ActorPublisherID: auth.PublisherID,
		TokenID:          tokenID,
		EventType:        "token.used",
		TargetType:       artifactKind,
		TargetID:         artifactID,
		Metadata: map[string]any{
			"operation": operation,
		},
	})
	return auth, nil
}

func (s *PostgresStore) ensureArtifactPublishAllowed(ctx context.Context, publisherID string, artifactKind string, artifactID string, scopes registryPublishTokenScopes) error {
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
