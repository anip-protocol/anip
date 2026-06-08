package registryapi

import (
	"os"
	"testing"
)

func getRegistryPostgresDSN(t *testing.T) string {
	dsn := os.Getenv("ANIP_TEST_POSTGRES_DSN")
	if dsn == "" {
		t.Skip("ANIP_TEST_POSTGRES_DSN not set, skipping registry Postgres tests")
	}
	return dsn
}

func newRegistryPostgresStore(t *testing.T) *PostgresStore {
	t.Helper()
	store, err := NewPostgresStore(getRegistryPostgresDSN(t))
	if err != nil {
		t.Fatalf("NewPostgresStore: %v", err)
	}
	t.Cleanup(func() { _ = store.Close() })

	if _, err := store.pool.Exec(t.Context(), `
		TRUNCATE registry_receipts, registry_packages, published_lineages, registry_templates
	`); err != nil {
		t.Fatalf("truncate registry tables: %v", err)
	}

	return store
}

func TestPostgresStorePublishesTemplate(t *testing.T) {
	store := newRegistryPostgresStore(t)
	status, err := store.MigrationStatus(t.Context())
	if err != nil {
		t.Fatalf("MigrationStatus: %v", err)
	}
	if !status.Applied || status.ExpectedCount == 0 {
		t.Fatalf("expected applied migrations, got %+v", status)
	}

	result, err := store.PublishTemplate(validTestTemplateRequest(t))
	if err != nil {
		t.Fatalf("PublishTemplate: %v", err)
	}
	if result.Template.TemplateDigest == "" || result.Template.PackageDigest == "" {
		t.Fatalf("expected template digests, got %+v", result.Template)
	}

	record, ok := store.GetTemplate("notion-fronting-starter", "0.1.0")
	if !ok {
		t.Fatal("expected stored template record")
	}
	if record.Domain != "notion" || record.ProjectType != "governed_service_project" {
		t.Fatalf("unexpected template record %+v", record)
	}

	downloaded, ok := store.RecordTemplateDownload("notion-fronting-starter", "0.1.0")
	if !ok {
		t.Fatal("expected template download")
	}
	if downloaded.DownloadCount != 1 {
		t.Fatalf("expected download count 1, got %d", downloaded.DownloadCount)
	}
}

func TestPostgresStoreSeedsAndReadsDemoPublication(t *testing.T) {
	store := newRegistryPostgresStore(t)

	if err := store.SeedDemoData(); err != nil {
		t.Fatalf("SeedDemoData: %v", err)
	}

	count, err := store.CountPublishedLineages()
	if err != nil {
		t.Fatalf("CountPublishedLineages: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected 1 published lineage, got %d", count)
	}

	publications := store.ListPublications()
	if len(publications) != 1 {
		t.Fatalf("expected 1 publication, got %d", len(publications))
	}

	record, ok := store.GetPackage("issue-tracker-native-and-mcp-fronting", "0.1.0")
	if !ok {
		t.Fatal("expected package record")
	}
	if record.ProjectRef != "issue-tracker-native-and-mcp-fronting" {
		t.Fatalf("unexpected project ref %q", record.ProjectRef)
	}

	receipt, ok := store.GetReceipt("issue-tracker-native-and-mcp-fronting", "0.1.0")
	if !ok {
		t.Fatal("expected receipt record")
	}
	if receipt.ReceiptID == "" {
		t.Fatal("expected non-empty receipt id")
	}
	if receipt.SignatureAlgorithm != SignatureAlgorithmEd25519 || receipt.KeyID == "" {
		t.Fatalf("expected signed receipt metadata, got %+v", receipt)
	}
}

func TestPostgresStorePublishesPackage(t *testing.T) {
	store := newRegistryPostgresStore(t)

	request := validTestPublishPackageRequest()
	request.PackageID = "registry-db-test"
	request.PackageVersion = "0.0.1"
	request.ProjectRef = "registry-db-test"
	result, err := store.PublishPackage(request)
	if err != nil {
		t.Fatalf("PublishPackage: %v", err)
	}
	if result.Package.ManifestDigest == "" || result.Package.DefinitionDigest == "" {
		t.Fatal("expected digests to be populated")
	}

	record, ok := store.GetPackage("registry-db-test", "0.0.1")
	if !ok {
		t.Fatal("expected stored package record")
	}
	if record.PackageID != "registry-db-test" {
		t.Fatalf("unexpected package id %q", record.PackageID)
	}

	receipt, ok := store.GetReceipt("registry-db-test", "0.0.1")
	if !ok {
		t.Fatal("expected stored receipt")
	}
	if receipt.RegistrySignature == "" {
		t.Fatal("expected non-empty registry signature")
	}
	keys := store.ListPublicKeys()
	if len(keys) != 1 || keys[0].Algorithm != SignatureAlgorithmEd25519 {
		t.Fatalf("expected Ed25519 public key, got %+v", keys)
	}
}
