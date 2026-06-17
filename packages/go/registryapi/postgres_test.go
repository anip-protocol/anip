package registryapi

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"slices"
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
		TRUNCATE registry_audit_events, registry_artifact_ownership, registry_publish_tokens,
		         registry_namespaces, registry_publisher_memberships, registry_publishers,
		         registry_users, registry_receipts, registry_packages, published_lineages,
		         registry_templates
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

func TestPostgresStorePublisherLookupAndAuditAppend(t *testing.T) {
	store := newRegistryPostgresStore(t)
	status, err := store.MigrationStatus(t.Context())
	if err != nil {
		t.Fatalf("MigrationStatus: %v", err)
	}
	if !status.Applied || status.ExpectedCount < 6 {
		t.Fatalf("expected public publisher migration to be applied, got %+v", status)
	}

	if _, err := store.pool.Exec(t.Context(), `
		INSERT INTO registry_publishers (
			publisher_id, publisher_type, display_name, description, website_url, status, trust_level
		) VALUES (
			'anip', 'official', 'ANIP', 'Official ANIP publisher', 'https://anip.dev', 'active', 'official'
		)
	`); err != nil {
		t.Fatalf("insert publisher: %v", err)
	}

	publisher, ok, err := store.GetPublisher(t.Context(), "anip")
	if err != nil {
		t.Fatalf("GetPublisher: %v", err)
	}
	if !ok {
		t.Fatal("expected publisher")
	}
	if publisher.PublisherID != "anip" || publisher.TrustLevel != "official" {
		t.Fatalf("unexpected publisher %+v", publisher)
	}
	if publisher.CreatedAt == "" || publisher.UpdatedAt == "" {
		t.Fatalf("expected timestamps, got %+v", publisher)
	}

	event, err := store.AppendAuditEvent(t.Context(), RegistryAuditEvent{
		ActorPublisherID: "anip",
		EventType:        "publisher.created",
		TargetType:       "publisher",
		TargetID:         "anip",
		Metadata: map[string]any{
			"source": "test",
		},
	})
	if err != nil {
		t.Fatalf("AppendAuditEvent: %v", err)
	}
	if event.EventID == "" || event.CreatedAt == "" {
		t.Fatalf("expected audit id and timestamp, got %+v", event)
	}
	if event.ActorPublisherID != "anip" || event.Metadata["source"] != "test" {
		t.Fatalf("unexpected audit event %+v", event)
	}
}

func TestPostgresBootstrapOfficialANIPPublisherBackfillsOwnershipWithoutDigestChanges(t *testing.T) {
	store := newRegistryPostgresStore(t)

	packageRequest := validTestPublishPackageRequest()
	packageRequest.PackageID = "gtm-pipeline-q2-review"
	packageRequest.PackageVersion = "0.4.3"
	packageRequest.ProjectRef = "studio:gtm-pipeline-q2-review"
	packageRequest.PublisherID = "studio-local"
	packageRequest.PublisherType = "studio"
	packageResult, err := store.PublishPackage(packageRequest)
	if err != nil {
		t.Fatalf("PublishPackage: %v", err)
	}
	templateRequest := validTestTemplateRequest(t)
	templateRequest.TemplateID = "jira-fronting-starter"
	templateRequest.TemplateVersion = "0.2.3"
	templateRequest.PublisherID = "studio-local"
	templateRequest.PublisherType = "studio"
	templateResult, err := store.PublishTemplate(templateRequest)
	if err != nil {
		t.Fatalf("PublishTemplate: %v", err)
	}

	beforePackage, ok := store.GetPackage("gtm-pipeline-q2-review", "0.4.3")
	if !ok {
		t.Fatal("expected package before bootstrap")
	}
	beforeTemplate, ok := store.GetTemplate("jira-fronting-starter", "0.2.3")
	if !ok {
		t.Fatal("expected template before bootstrap")
	}
	if beforePackage.Publisher != nil || beforeTemplate.Publisher != nil {
		t.Fatalf("expected no ownership publisher before bootstrap, got package=%+v template=%+v", beforePackage.Publisher, beforeTemplate.Publisher)
	}

	if err := store.BootstrapOfficialANIPPublisher(t.Context(), []string{"studio-local"}); err != nil {
		t.Fatalf("BootstrapOfficialANIPPublisher: %v", err)
	}
	if err := store.BootstrapOfficialANIPPublisher(t.Context(), []string{"studio-local"}); err != nil {
		t.Fatalf("BootstrapOfficialANIPPublisher idempotent rerun: %v", err)
	}

	afterPackage, ok := store.GetPackage("gtm-pipeline-q2-review", "0.4.3")
	if !ok {
		t.Fatal("expected package after bootstrap")
	}
	afterTemplate, ok := store.GetTemplate("jira-fronting-starter", "0.2.3")
	if !ok {
		t.Fatal("expected template after bootstrap")
	}
	if afterPackage.ManifestDigest != packageResult.Package.ManifestDigest ||
		afterPackage.DefinitionDigest != packageResult.Package.DefinitionDigest ||
		afterPackage.LockDigest != packageResult.Package.LockDigest {
		t.Fatalf("package digests changed: before=%+v after=%+v", packageResult.Package, afterPackage)
	}
	if afterTemplate.ManifestDigest != templateResult.Template.ManifestDigest ||
		afterTemplate.TemplateDigest != templateResult.Template.TemplateDigest ||
		afterTemplate.PackageDigest != templateResult.Template.PackageDigest {
		t.Fatalf("template digests changed: before=%+v after=%+v", templateResult.Template, afterTemplate)
	}
	if afterPackage.Publisher == nil || afterPackage.Publisher.PublisherID != "anip" || afterPackage.Publisher.TrustLevel != "official" {
		t.Fatalf("expected official package publisher summary, got %+v", afterPackage.Publisher)
	}
	if afterTemplate.Publisher == nil || afterTemplate.Publisher.PublisherID != "anip" || afterTemplate.Publisher.TrustLevel != "official" {
		t.Fatalf("expected official template publisher summary, got %+v", afterTemplate.Publisher)
	}
	if afterPackage.PublisherID != "studio-local" || afterPackage.PublisherType != "studio" {
		t.Fatalf("bootstrap should not rewrite package publisher fields, got %+v", afterPackage)
	}
	if afterTemplate.PublisherID != "studio-local" || afterTemplate.PublisherType != "studio" {
		t.Fatalf("bootstrap should not rewrite template publisher fields, got %+v", afterTemplate)
	}

	publications := store.ListPublications()
	if len(publications) != 1 || publications[0].Publisher == nil || publications[0].Publisher.PublisherID != "anip" {
		t.Fatalf("expected publication publisher summary, got %+v", publications)
	}
	templates := store.ListTemplates()
	if len(templates) != 1 || templates[0].Publisher == nil || templates[0].Publisher.PublisherID != "anip" {
		t.Fatalf("expected template publisher summary, got %+v", templates)
	}
}

func TestPostgresScopedPublishTokenPublishesPackage(t *testing.T) {
	store := newRegistryPostgresStore(t)
	insertScopedPublisherFixture(t, store, "anip", "anip-token-secret", []string{"publish:package"}, []string{"anip"}, nil, nil)

	body := validTestPublishPackageRequest()
	body.PackageID = "anip/work-item-fronting"
	body.PackageVersion = "0.2.0"
	body.ProjectRef = "anip/work-item-fronting"
	payload, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal request: %v", err)
	}

	handler := NewHandlerWithOptions(store, HandlerOptions{})
	req := httptest.NewRequest(http.MethodPost, "/registry-api/v1/publications", bytes.NewReader(payload))
	req.Header.Set("Authorization", "Bearer anip_pat_11111111-1111-4111-8111-111111111111_anip-token-secret")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d body=%s", rec.Code, rec.Body.String())
	}

	var result PublishPackageResult
	if err := json.Unmarshal(rec.Body.Bytes(), &result); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if result.Package.PublisherID != "anip" || result.Package.PublisherType != "official" {
		t.Fatalf("expected scoped publisher identity, got %+v", result.Package)
	}
	var owner string
	if err := store.pool.QueryRow(t.Context(), `
		SELECT publisher_id
		FROM registry_artifact_ownership
		WHERE artifact_kind = 'package' AND artifact_id = 'anip/work-item-fronting'
	`).Scan(&owner); err != nil {
		t.Fatalf("read ownership: %v", err)
	}
	if owner != "anip" {
		t.Fatalf("expected anip ownership, got %q", owner)
	}
}

func TestPostgresScopedPublishTokenRejectsWrongScope(t *testing.T) {
	store := newRegistryPostgresStore(t)
	insertScopedPublisherFixture(t, store, "anip", "anip-token-secret", []string{"publish:template"}, []string{"anip"}, nil, nil)

	body := validTestPublishPackageRequest()
	body.PackageID = "anip/work-item-fronting"
	body.PackageVersion = "0.2.0"
	body.ProjectRef = "anip/work-item-fronting"
	payload, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal request: %v", err)
	}

	handler := NewHandlerWithOptions(store, HandlerOptions{})
	req := httptest.NewRequest(http.MethodPost, "/registry-api/v1/publications", bytes.NewReader(payload))
	req.Header.Set("Authorization", "Bearer anip_pat_11111111-1111-4111-8111-111111111111_anip-token-secret")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d body=%s", rec.Code, rec.Body.String())
	}
}

func TestPostgresPublisherSelfServiceTokenLifecycle(t *testing.T) {
	store := newRegistryPostgresStore(t)
	insertScopedPublisherFixture(t, store, "anip", "anip-token-secret", []string{"publish:package", "manage:tokens"}, []string{"anip"}, nil, nil)

	handler := NewHandlerWithOptions(store, HandlerOptions{})
	bearer := "Bearer anip_pat_11111111-1111-4111-8111-111111111111_anip-token-secret"

	publisherReq := httptest.NewRequest(http.MethodGet, "/registry-api/v1/me/publisher", nil)
	publisherReq.Header.Set("Authorization", bearer)
	publisherRec := httptest.NewRecorder()
	handler.ServeHTTP(publisherRec, publisherReq)
	if publisherRec.Code != http.StatusOK {
		t.Fatalf("expected publisher introspection 200, got %d body=%s", publisherRec.Code, publisherRec.Body.String())
	}
	var publisherPayload struct {
		Publisher RegistryPublisher `json:"publisher"`
	}
	if err := json.Unmarshal(publisherRec.Body.Bytes(), &publisherPayload); err != nil {
		t.Fatalf("decode publisher payload: %v", err)
	}
	if publisherPayload.Publisher.PublisherID != "anip" || publisherPayload.Publisher.TrustLevel != "official" {
		t.Fatalf("unexpected publisher payload %+v", publisherPayload)
	}

	body := validTestPublishPackageRequest()
	body.PackageID = "anip/work-item-fronting"
	body.PackageVersion = "0.2.0"
	body.ProjectRef = "anip/work-item-fronting"
	publishPayload, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal publish request: %v", err)
	}
	publishReq := httptest.NewRequest(http.MethodPost, "/registry-api/v1/publications", bytes.NewReader(publishPayload))
	publishReq.Header.Set("Authorization", bearer)
	publishRec := httptest.NewRecorder()
	handler.ServeHTTP(publishRec, publishReq)
	if publishRec.Code != http.StatusCreated {
		t.Fatalf("expected publish 201, got %d body=%s", publishRec.Code, publishRec.Body.String())
	}

	artifactsReq := httptest.NewRequest(http.MethodGet, "/registry-api/v1/me/artifacts", nil)
	artifactsReq.Header.Set("Authorization", bearer)
	artifactsRec := httptest.NewRecorder()
	handler.ServeHTTP(artifactsRec, artifactsReq)
	if artifactsRec.Code != http.StatusOK {
		t.Fatalf("expected artifacts 200, got %d body=%s", artifactsRec.Code, artifactsRec.Body.String())
	}
	var artifactsPayload struct {
		Items []PublisherArtifactSummary `json:"items"`
	}
	if err := json.Unmarshal(artifactsRec.Body.Bytes(), &artifactsPayload); err != nil {
		t.Fatalf("decode artifacts payload: %v", err)
	}
	if len(artifactsPayload.Items) != 1 ||
		artifactsPayload.Items[0].ArtifactKind != "package" ||
		artifactsPayload.Items[0].ArtifactID != "anip/work-item-fronting" {
		t.Fatalf("unexpected artifacts %+v", artifactsPayload.Items)
	}

	createPayload, err := json.Marshal(CreatePublishTokenRequest{
		Label: "release bot",
		Scopes: RegistryPublishTokenScopes{
			Operations: []string{"publish:package"},
			Namespaces: []string{"anip"},
		},
	})
	if err != nil {
		t.Fatalf("marshal create token request: %v", err)
	}
	createReq := httptest.NewRequest(http.MethodPost, "/registry-api/v1/me/tokens", bytes.NewReader(createPayload))
	createReq.Header.Set("Authorization", bearer)
	createRec := httptest.NewRecorder()
	handler.ServeHTTP(createRec, createReq)
	if createRec.Code != http.StatusCreated {
		t.Fatalf("expected create token 201, got %d body=%s", createRec.Code, createRec.Body.String())
	}
	var createResult CreatePublishTokenResult
	if err := json.Unmarshal(createRec.Body.Bytes(), &createResult); err != nil {
		t.Fatalf("decode create token result: %v", err)
	}
	if createResult.BearerToken == "" || createResult.Token.TokenID == "" || createResult.Token.Label != "release bot" {
		t.Fatalf("unexpected create token result %+v", createResult)
	}
	if createResult.Token.TokenHash != "" {
		t.Fatalf("token hash must not be exposed: %+v", createResult.Token)
	}

	listReq := httptest.NewRequest(http.MethodGet, "/registry-api/v1/me/tokens", nil)
	listReq.Header.Set("Authorization", bearer)
	listRec := httptest.NewRecorder()
	handler.ServeHTTP(listRec, listReq)
	if listRec.Code != http.StatusOK {
		t.Fatalf("expected token list 200, got %d body=%s", listRec.Code, listRec.Body.String())
	}
	var listPayload struct {
		Items []RegistryPublishTokenSummary `json:"items"`
	}
	if err := json.Unmarshal(listRec.Body.Bytes(), &listPayload); err != nil {
		t.Fatalf("decode token list: %v", err)
	}
	if len(listPayload.Items) != 2 {
		t.Fatalf("expected original and created tokens, got %+v", listPayload.Items)
	}

	revokeReq := httptest.NewRequest(http.MethodDelete, "/registry-api/v1/me/tokens/"+createResult.Token.TokenID, nil)
	revokeReq.Header.Set("Authorization", bearer)
	revokeRec := httptest.NewRecorder()
	handler.ServeHTTP(revokeRec, revokeReq)
	if revokeRec.Code != http.StatusOK {
		t.Fatalf("expected revoke 200, got %d body=%s", revokeRec.Code, revokeRec.Body.String())
	}
	var revokePayload struct {
		Token RegistryPublishTokenSummary `json:"token"`
	}
	if err := json.Unmarshal(revokeRec.Body.Bytes(), &revokePayload); err != nil {
		t.Fatalf("decode revoke payload: %v", err)
	}
	if revokePayload.Token.RevokedAt == "" {
		t.Fatalf("expected revoked_at after revocation, got %+v", revokePayload.Token)
	}
}

func TestPostgresPublisherSelfServiceRejectsTokenWithoutManagementScope(t *testing.T) {
	store := newRegistryPostgresStore(t)
	insertScopedPublisherFixture(t, store, "anip", "anip-token-secret", []string{"publish:package"}, []string{"anip"}, nil, nil)

	handler := NewHandlerWithOptions(store, HandlerOptions{})
	req := httptest.NewRequest(http.MethodGet, "/registry-api/v1/me/tokens", nil)
	req.Header.Set("Authorization", "Bearer anip_pat_11111111-1111-4111-8111-111111111111_anip-token-secret")
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusForbidden {
		t.Fatalf("expected 403 for publish-only token management request, got %d body=%s", rec.Code, rec.Body.String())
	}
}

func TestPostgresPublisherSelfServiceProfileAndNamespaceManagement(t *testing.T) {
	store := newRegistryPostgresStore(t)
	insertScopedPublisherFixture(t, store, "anip", "anip-token-secret", []string{"publish:package", "manage:tokens", "manage:publisher"}, []string{"anip"}, nil, nil)

	handler := NewHandlerWithOptions(store, HandlerOptions{})
	bearer := "Bearer anip_pat_11111111-1111-4111-8111-111111111111_anip-token-secret"

	contextReq := httptest.NewRequest(http.MethodGet, "/registry-api/v1/me/publisher", nil)
	contextReq.Header.Set("Authorization", bearer)
	contextRec := httptest.NewRecorder()
	handler.ServeHTTP(contextRec, contextReq)
	if contextRec.Code != http.StatusOK {
		t.Fatalf("expected publisher context 200, got %d body=%s", contextRec.Code, contextRec.Body.String())
	}
	var contextResult PublisherSelfServiceContext
	if err := json.Unmarshal(contextRec.Body.Bytes(), &contextResult); err != nil {
		t.Fatalf("decode publisher context: %v", err)
	}
	if contextResult.Publisher.PublisherID != "anip" || !slices.Contains(contextResult.Scopes.Operations, "manage:publisher") {
		t.Fatalf("unexpected publisher context %+v", contextResult)
	}

	updatePayload, err := json.Marshal(UpdatePublisherRequest{
		DisplayName: "ANIP Protocol",
		Description: "Canonical ANIP public publisher.",
		WebsiteURL:  "https://anip.dev",
	})
	if err != nil {
		t.Fatalf("marshal publisher update: %v", err)
	}
	updateReq := httptest.NewRequest(http.MethodPatch, "/registry-api/v1/me/publisher", bytes.NewReader(updatePayload))
	updateReq.Header.Set("Authorization", bearer)
	updateRec := httptest.NewRecorder()
	handler.ServeHTTP(updateRec, updateReq)
	if updateRec.Code != http.StatusOK {
		t.Fatalf("expected publisher update 200, got %d body=%s", updateRec.Code, updateRec.Body.String())
	}
	var updateResult struct {
		Publisher RegistryPublisher `json:"publisher"`
	}
	if err := json.Unmarshal(updateRec.Body.Bytes(), &updateResult); err != nil {
		t.Fatalf("decode publisher update: %v", err)
	}
	if updateResult.Publisher.DisplayName != "ANIP Protocol" || updateResult.Publisher.Description != "Canonical ANIP public publisher." {
		t.Fatalf("unexpected updated publisher %+v", updateResult.Publisher)
	}

	listReq := httptest.NewRequest(http.MethodGet, "/registry-api/v1/me/namespaces", nil)
	listReq.Header.Set("Authorization", bearer)
	listRec := httptest.NewRecorder()
	handler.ServeHTTP(listRec, listReq)
	if listRec.Code != http.StatusOK {
		t.Fatalf("expected namespace list 200, got %d body=%s", listRec.Code, listRec.Body.String())
	}
	var listResult struct {
		Items []RegistryNamespaceSummary `json:"items"`
	}
	if err := json.Unmarshal(listRec.Body.Bytes(), &listResult); err != nil {
		t.Fatalf("decode namespace list: %v", err)
	}
	if len(listResult.Items) != 1 || listResult.Items[0].Namespace != "anip" {
		t.Fatalf("unexpected initial namespaces %+v", listResult.Items)
	}

	createPayload, err := json.Marshal(CreateNamespaceRequest{
		Namespace:     "anip-labs",
		ArtifactKinds: []string{"package", "template"},
	})
	if err != nil {
		t.Fatalf("marshal namespace create: %v", err)
	}
	createReq := httptest.NewRequest(http.MethodPost, "/registry-api/v1/me/namespaces", bytes.NewReader(createPayload))
	createReq.Header.Set("Authorization", bearer)
	createRec := httptest.NewRecorder()
	handler.ServeHTTP(createRec, createReq)
	if createRec.Code != http.StatusCreated {
		t.Fatalf("expected namespace create 201, got %d body=%s", createRec.Code, createRec.Body.String())
	}
	var createResult struct {
		Namespace RegistryNamespaceSummary `json:"namespace"`
	}
	if err := json.Unmarshal(createRec.Body.Bytes(), &createResult); err != nil {
		t.Fatalf("decode namespace create: %v", err)
	}
	if createResult.Namespace.Namespace != "anip-labs" || createResult.Namespace.PublisherID != "anip" {
		t.Fatalf("unexpected created namespace %+v", createResult.Namespace)
	}

	conflictReq := httptest.NewRequest(http.MethodPost, "/registry-api/v1/me/namespaces", bytes.NewReader(createPayload))
	conflictReq.Header.Set("Authorization", bearer)
	conflictRec := httptest.NewRecorder()
	handler.ServeHTTP(conflictRec, conflictReq)
	if conflictRec.Code != http.StatusConflict {
		t.Fatalf("expected namespace conflict 409, got %d body=%s", conflictRec.Code, conflictRec.Body.String())
	}
}

func insertScopedPublisherFixture(t *testing.T, store *PostgresStore, publisherID string, secret string, operations []string, namespaces []string, packageIDs []string, templateIDs []string) {
	t.Helper()
	scopes := map[string]any{
		"operations":   operations,
		"namespaces":   namespaces,
		"package_ids":  packageIDs,
		"template_ids": templateIDs,
	}
	scopesBytes, err := json.Marshal(scopes)
	if err != nil {
		t.Fatalf("marshal token scopes: %v", err)
	}
	if _, err := store.pool.Exec(t.Context(), `
		INSERT INTO registry_publishers (
			publisher_id, publisher_type, display_name, description, website_url, status, trust_level
		) VALUES (
			$1, 'official', 'ANIP', 'Official ANIP publisher', 'https://anip.dev', 'active', 'official'
		)
	`, publisherID); err != nil {
		t.Fatalf("insert publisher: %v", err)
	}
	if _, err := store.pool.Exec(t.Context(), `
		INSERT INTO registry_namespaces (
			namespace, publisher_id, artifact_kinds, status
		) VALUES (
			'anip', $1, '["package","template"]'::jsonb, 'active'
		)
	`, publisherID); err != nil {
		t.Fatalf("insert namespace: %v", err)
	}
	if _, err := store.pool.Exec(t.Context(), `
		INSERT INTO registry_publish_tokens (
			token_id, publisher_id, token_hash, label, scopes
		) VALUES (
			'11111111-1111-4111-8111-111111111111', $1, $2, 'test token', $3
		)
	`, publisherID, RegistryPublishTokenSecretHash(secret), scopesBytes); err != nil {
		t.Fatalf("insert token: %v", err)
	}
}
