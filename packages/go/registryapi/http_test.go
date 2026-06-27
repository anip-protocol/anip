package registryapi

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestListPublications(t *testing.T) {
	handler := NewHandler(NewMemoryStore())
	req := httptest.NewRequest(http.MethodGet, "/registry-api/v1/publications", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}

	var payload struct {
		Items []PublicationSummary `json:"items"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatalf("failed to decode payload: %v", err)
	}
	if len(payload.Items) != 1 {
		t.Fatalf("expected 1 publication, got %d", len(payload.Items))
	}
}

func TestHealthIncludesSigningPosture(t *testing.T) {
	handler := NewHandlerWithOptions(NewMemoryStore(), HandlerOptions{
		SigningMode: "production",
		ActiveKeyID: "registry-prod-2026-04",
	})
	req := httptest.NewRequest(http.MethodGet, "/registry-api/v1/healthz", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	var payload struct {
		Status      string `json:"status"`
		Service     string `json:"service"`
		SigningMode string `json:"signing_mode"`
		ActiveKeyID string `json:"active_key_id"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatalf("failed to decode payload: %v", err)
	}
	if payload.SigningMode != "production" || payload.ActiveKeyID != "registry-prod-2026-04" {
		t.Fatalf("unexpected signing posture %+v", payload)
	}
}

func TestReadyzAndMetrics(t *testing.T) {
	metrics := NewRegistryMetrics()
	handler := NewHandlerWithOptions(NewMemoryStore(), HandlerOptions{Metrics: metrics})

	readyReq := httptest.NewRequest(http.MethodGet, "/registry-api/v1/readyz", nil)
	readyRec := httptest.NewRecorder()
	handler.ServeHTTP(readyRec, readyReq)
	if readyRec.Code != http.StatusOK {
		t.Fatalf("expected readyz 200, got %d", readyRec.Code)
	}
	var readyPayload struct {
		Status    string          `json:"status"`
		Service   string          `json:"service"`
		Migration MigrationStatus `json:"migration"`
	}
	if err := json.Unmarshal(readyRec.Body.Bytes(), &readyPayload); err != nil {
		t.Fatalf("decode readyz: %v", err)
	}
	if readyPayload.Status != "ok" || readyPayload.Service != "anip-registry" || !readyPayload.Migration.Applied {
		t.Fatalf("unexpected readyz payload %+v", readyPayload)
	}

	metricsReq := httptest.NewRequest(http.MethodGet, "/registry-api/v1/metrics", nil)
	metricsRec := httptest.NewRecorder()
	handler.ServeHTTP(metricsRec, metricsReq)
	if metricsRec.Code != http.StatusOK {
		t.Fatalf("expected metrics 200, got %d", metricsRec.Code)
	}
	body := metricsRec.Body.String()
	for _, expected := range []string{
		"anip_registry_http_requests_total",
		"anip_registry_readiness_checks_total",
		"anip_registry_migrations_applied",
	} {
		if !strings.Contains(body, expected) {
			t.Fatalf("expected metrics to contain %q, got %s", expected, body)
		}
	}
}

func TestGetPackageReceipt(t *testing.T) {
	handler := NewHandler(NewMemoryStore())
	req := httptest.NewRequest(
		http.MethodGet,
		"/registry-api/v1/packages/issue-tracker-native-and-mcp-fronting/0.1.0/receipt",
		nil,
	)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}

	var payload RegistryReceipt
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatalf("failed to decode payload: %v", err)
	}
	if payload.PackageID != "issue-tracker-native-and-mcp-fronting" {
		t.Fatalf("unexpected package id %q", payload.PackageID)
	}
	if payload.SignatureAlgorithm != SignatureAlgorithmEd25519 || payload.KeyID == "" {
		t.Fatalf("expected signed receipt metadata, got %+v", payload)
	}
}

func TestPackageDetailIncludesDefaultLifecycle(t *testing.T) {
	store := NewMemoryStore()
	request := validTestPublishPackageRequest()
	result, err := store.PublishPackage(request)
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}

	record, ok := store.GetPackage(result.Package.PackageID, result.Package.PackageVersion)
	if !ok {
		t.Fatalf("expected package to exist")
	}
	if record.Lifecycle.Status != PackageLifecycleActive {
		t.Fatalf("expected active lifecycle, got %q", record.Lifecycle.Status)
	}
}

func TestAdminUpdatesPackageLifecycle(t *testing.T) {
	store := NewMemoryStore()
	published, err := store.PublishPackage(validTestPublishPackageRequest())
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}
	handler := NewHandlerWithOptions(store, HandlerOptions{AdminToken: "test-admin-token"})

	payload := map[string]any{
		"status":                      PackageLifecycleDeprecated,
		"reason":                      "later validation found generated-service drift",
		"replacement_package_id":      published.Package.PackageID,
		"replacement_package_version": "0.2.1",
	}
	body, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal lifecycle request: %v", err)
	}
	req := httptest.NewRequest(
		http.MethodPatch,
		"/registry-api/v1/admin/packages/"+published.Package.PackageID+"/"+published.Package.PackageVersion+"/lifecycle",
		bytes.NewReader(body),
	)
	req.Header.Set("Authorization", "Bearer test-admin-token")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected lifecycle update 200, got %d body=%s", rec.Code, rec.Body.String())
	}
	var response struct {
		Package RegistryPackageRecord `json:"package"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &response); err != nil {
		t.Fatalf("decode lifecycle update: %v", err)
	}
	if response.Package.Lifecycle.Status != PackageLifecycleDeprecated {
		t.Fatalf("expected deprecated lifecycle, got %+v", response.Package.Lifecycle)
	}
	if response.Package.Lifecycle.Replacement == nil || response.Package.Lifecycle.Replacement.PackageVersion != "0.2.1" {
		t.Fatalf("expected replacement metadata, got %+v", response.Package.Lifecycle)
	}
	if response.Package.Lifecycle.UpdatedBy == "" || response.Package.Lifecycle.UpdatedAt == "" {
		t.Fatalf("expected lifecycle audit metadata, got %+v", response.Package.Lifecycle)
	}
}

func TestAdminPackageLifecycleRequiresAdminAuth(t *testing.T) {
	store := NewMemoryStore()
	published, err := store.PublishPackage(validTestPublishPackageRequest())
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}
	handler := NewHandlerWithOptions(store, HandlerOptions{AdminToken: "test-admin-token"})

	body := strings.NewReader(`{"status":"deprecated","reason":"bad package"}`)
	req := httptest.NewRequest(
		http.MethodPatch,
		"/registry-api/v1/admin/packages/"+published.Package.PackageID+"/"+published.Package.PackageVersion+"/lifecycle",
		body,
	)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusForbidden {
		t.Fatalf("expected 403 without admin auth, got %d body=%s", rec.Code, rec.Body.String())
	}
}

func TestYankedPackageDownloadRequiresExplicitOverride(t *testing.T) {
	store := NewMemoryStore()
	published, err := store.PublishPackage(validTestPublishPackageRequest())
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}
	if _, ok, err := store.UpdatePackageLifecycle(
		context.Background(),
		published.Package.PackageID,
		published.Package.PackageVersion,
		UpdatePackageLifecycleRequest{Status: PackageLifecycleYanked, Reason: "bad generated-service behavior"},
		"test-admin",
	); err != nil || !ok {
		t.Fatalf("update lifecycle: ok=%v err=%v", ok, err)
	}
	handler := NewHandler(store)

	downloadReq := httptest.NewRequest(
		http.MethodGet,
		"/registry-api/v1/packages/"+published.Package.PackageID+"/"+published.Package.PackageVersion+"/download",
		nil,
	)
	downloadRec := httptest.NewRecorder()
	handler.ServeHTTP(downloadRec, downloadReq)
	if downloadRec.Code != http.StatusGone {
		t.Fatalf("expected yanked download 410, got %d body=%s", downloadRec.Code, downloadRec.Body.String())
	}

	overrideReq := httptest.NewRequest(
		http.MethodGet,
		"/registry-api/v1/packages/"+published.Package.PackageID+"/"+published.Package.PackageVersion+"/download?allow_yanked=true",
		nil,
	)
	overrideRec := httptest.NewRecorder()
	handler.ServeHTTP(overrideRec, overrideReq)
	if overrideRec.Code != http.StatusOK {
		t.Fatalf("expected yanked download override 200, got %d body=%s", overrideRec.Code, overrideRec.Body.String())
	}
}

func TestTakedownPackageDoesNotExposeContents(t *testing.T) {
	store := NewMemoryStore()
	published, err := store.PublishPackage(validTestPublishPackageRequest())
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}
	if _, ok, err := store.UpdatePackageLifecycle(
		context.Background(),
		published.Package.PackageID,
		published.Package.PackageVersion,
		UpdatePackageLifecycleRequest{Status: PackageLifecycleTakedown, Reason: "legal takedown"},
		"test-admin",
	); err != nil || !ok {
		t.Fatalf("update lifecycle: ok=%v err=%v", ok, err)
	}
	handler := NewHandler(store)

	detailReq := httptest.NewRequest(
		http.MethodGet,
		"/registry-api/v1/packages/"+published.Package.PackageID+"/"+published.Package.PackageVersion,
		nil,
	)
	detailRec := httptest.NewRecorder()
	handler.ServeHTTP(detailRec, detailReq)
	if detailRec.Code != http.StatusGone {
		t.Fatalf("expected takedown detail 410, got %d body=%s", detailRec.Code, detailRec.Body.String())
	}
	if strings.Contains(detailRec.Body.String(), "service_definition") {
		t.Fatalf("takedown response should not expose package contents: %s", detailRec.Body.String())
	}
}

func TestDownloadPackageIncrementsDownloadCount(t *testing.T) {
	store := NewMemoryStore()
	handler := NewHandler(store)

	detailReq := httptest.NewRequest(
		http.MethodGet,
		"/registry-api/v1/packages/issue-tracker-native-and-mcp-fronting/0.1.0",
		nil,
	)
	detailRec := httptest.NewRecorder()
	handler.ServeHTTP(detailRec, detailReq)
	if detailRec.Code != http.StatusOK {
		t.Fatalf("expected detail 200, got %d", detailRec.Code)
	}
	var detail RegistryPackageRecord
	if err := json.Unmarshal(detailRec.Body.Bytes(), &detail); err != nil {
		t.Fatalf("decode detail: %v", err)
	}
	if detail.DownloadCount != 0 {
		t.Fatalf("package detail should not increment downloads, got %d", detail.DownloadCount)
	}

	downloadReq := httptest.NewRequest(
		http.MethodGet,
		"/registry-api/v1/packages/issue-tracker-native-and-mcp-fronting/0.1.0/download",
		nil,
	)
	downloadRec := httptest.NewRecorder()
	handler.ServeHTTP(downloadRec, downloadReq)
	if downloadRec.Code != http.StatusOK {
		t.Fatalf("expected download 200, got %d body=%s", downloadRec.Code, downloadRec.Body.String())
	}
	var downloaded RegistryPackageRecord
	if err := json.Unmarshal(downloadRec.Body.Bytes(), &downloaded); err != nil {
		t.Fatalf("decode download: %v", err)
	}
	if downloaded.DownloadCount != 1 {
		t.Fatalf("expected download count 1, got %d", downloaded.DownloadCount)
	}
	if disposition := downloadRec.Header().Get("Content-Disposition"); disposition == "" {
		t.Fatal("expected attachment content disposition")
	}

	listReq := httptest.NewRequest(http.MethodGet, "/registry-api/v1/publications", nil)
	listRec := httptest.NewRecorder()
	handler.ServeHTTP(listRec, listReq)
	if listRec.Code != http.StatusOK {
		t.Fatalf("expected list 200, got %d", listRec.Code)
	}
	var listPayload struct {
		Items []PublicationSummary `json:"items"`
	}
	if err := json.Unmarshal(listRec.Body.Bytes(), &listPayload); err != nil {
		t.Fatalf("decode list: %v", err)
	}
	if len(listPayload.Items) != 1 || listPayload.Items[0].DownloadCount != 1 {
		t.Fatalf("expected list download count 1, got %+v", listPayload.Items)
	}
}

func TestDownloadPackageLockDoesNotIncrementDownloadCount(t *testing.T) {
	store := NewMemoryStore()
	handler := NewHandlerWithOptions(store, HandlerOptions{
		SigningMode: "production",
		ActiveKeyID: "registry-prod-2026-04",
	})

	lockReq := httptest.NewRequest(
		http.MethodGet,
		"/registry-api/v1/packages/issue-tracker-native-and-mcp-fronting/0.1.0/lock",
		nil,
	)
	lockReq.Host = "registry.example.test"
	lockReq.Header.Set("X-Forwarded-Proto", "https")
	lockRec := httptest.NewRecorder()
	handler.ServeHTTP(lockRec, lockReq)
	if lockRec.Code != http.StatusOK {
		t.Fatalf("expected lock 200, got %d body=%s", lockRec.Code, lockRec.Body.String())
	}
	var lock RegistryPackageLock
	if err := json.Unmarshal(lockRec.Body.Bytes(), &lock); err != nil {
		t.Fatalf("decode lock: %v", err)
	}
	if lock.LockSchemaVersion != "anip-package-lock/v1" || lock.ArtifactType != "anip_package_lock" {
		t.Fatalf("unexpected lock identity: %+v", lock)
	}
	if lock.RegistryURL != "https://registry.example.test/registry-api/v1" {
		t.Fatalf("unexpected registry URL %q", lock.RegistryURL)
	}
	if lock.PackageID != "issue-tracker-native-and-mcp-fronting" || lock.DefinitionDigest == "" || lock.LockDigest == "" {
		t.Fatalf("unexpected lock payload: %+v", lock)
	}
	if lock.RegistrySigningMode != "production" || lock.RegistryActiveKeyID != "registry-prod-2026-04" {
		t.Fatalf("expected registry signing posture, got %+v", lock)
	}
	if disposition := lockRec.Header().Get("Content-Disposition"); disposition == "" {
		t.Fatal("expected attachment content disposition")
	}

	detailReq := httptest.NewRequest(
		http.MethodGet,
		"/registry-api/v1/packages/issue-tracker-native-and-mcp-fronting/0.1.0",
		nil,
	)
	detailRec := httptest.NewRecorder()
	handler.ServeHTTP(detailRec, detailReq)
	if detailRec.Code != http.StatusOK {
		t.Fatalf("expected detail 200, got %d", detailRec.Code)
	}
	var detail RegistryPackageRecord
	if err := json.Unmarshal(detailRec.Body.Bytes(), &detail); err != nil {
		t.Fatalf("decode detail: %v", err)
	}
	if detail.DownloadCount != 0 {
		t.Fatalf("lock download should not increment package downloads, got %d", detail.DownloadCount)
	}
}

func TestListPublicKeys(t *testing.T) {
	handler := NewHandler(NewMemoryStore())
	req := httptest.NewRequest(http.MethodGet, "/registry-api/v1/keys", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}

	var payload struct {
		SigningMode string              `json:"signing_mode"`
		ActiveKeyID string              `json:"active_key_id"`
		Items       []RegistryPublicKey `json:"items"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatalf("failed to decode payload: %v", err)
	}
	if len(payload.Items) != 1 {
		t.Fatalf("expected one public key, got %d", len(payload.Items))
	}
	if payload.Items[0].Algorithm != SignatureAlgorithmEd25519 || payload.Items[0].PublicKey == "" {
		t.Fatalf("unexpected public key payload %+v", payload.Items[0])
	}
	if payload.SigningMode != "dev" || payload.ActiveKeyID != payload.Items[0].KeyID {
		t.Fatalf("unexpected signing posture %+v", payload)
	}
}

func TestListPublicKeysIncludesRotationKeys(t *testing.T) {
	active := NewDevRegistrySigner()
	previous, err := NewRegistryPublicKeyFromBase64("previous-key", active.PublicKeyRecord().PublicKey)
	if err != nil {
		t.Fatalf("create previous public key: %v", err)
	}
	handler := NewHandler(NewMemoryStoreWithSignerAndPublicKeys(active, []RegistryPublicKey{previous}))
	req := httptest.NewRequest(http.MethodGet, "/registry-api/v1/keys", nil)
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	var payload struct {
		Items []RegistryPublicKey `json:"items"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatalf("decode public keys: %v", err)
	}
	if len(payload.Items) != 2 {
		t.Fatalf("expected active plus previous key, got %+v", payload.Items)
	}
}

func TestPublishPackage(t *testing.T) {
	handler := NewHandlerWithOptions(NewMemoryStore(), HandlerOptions{
		PublishToken:                    "test-publish-token",
		LegacyGlobalPublishTokenEnabled: true,
		PublisherID:                     "studio-dev",
		PublisherType:                   "studio",
	})
	body := validTestPublishPackageRequest()
	payload, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal request: %v", err)
	}

	req := httptest.NewRequest(http.MethodPost, "/registry-api/v1/publications", bytes.NewReader(payload))
	req.Header.Set("Authorization", "Bearer test-publish-token")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d body=%s", rec.Code, rec.Body.String())
	}

	var result PublishPackageResult
	if err := json.Unmarshal(rec.Body.Bytes(), &result); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if result.Package.PackageID != "work-item-fronting" {
		t.Fatalf("unexpected package id %q", result.Package.PackageID)
	}
	if result.Package.ManifestDigest == "" || result.Package.DefinitionDigest == "" || result.Package.LockDigest == "" {
		t.Fatal("expected server-computed digests")
	}
	if result.Package.Lineage["project_ref"] != "work-item-fronting" {
		t.Fatalf("expected package lineage, got %+v", result.Package.Lineage)
	}
	if result.Package.PublisherID != "studio-dev" || result.Package.PublisherType != "studio" {
		t.Fatalf("expected authenticated publisher identity, got %+v", result.Package)
	}
	if result.Publication.PublisherID != "studio-dev" || result.Receipt.PublisherID != "studio-dev" {
		t.Fatalf("expected publisher identity on publication and receipt, got %+v %+v", result.Publication, result.Receipt)
	}
	if result.Package.Manifest["lineage"] == nil || result.Package.RecommendedLock["lineage"] == nil {
		t.Fatalf("expected lineage embedded into manifest and recommended lock")
	}
	if result.Package.Manifest["service_definition_digest"] != result.Package.DefinitionDigest {
		t.Fatalf("expected manifest definition digest stamped by registry, got %+v", result.Package.Manifest)
	}
	if result.Package.RecommendedLock["service_definition_digest"] != result.Package.DefinitionDigest {
		t.Fatalf("expected recommended lock definition digest stamped by registry, got %+v", result.Package.RecommendedLock)
	}
	if result.Receipt.RegistrySignature == "" {
		t.Fatal("expected registry receipt signature")
	}
	if result.Receipt.SignatureAlgorithm != SignatureAlgorithmEd25519 || result.Receipt.KeyID == "" {
		t.Fatalf("expected Ed25519 receipt metadata, got %+v", result.Receipt)
	}
	if !VerifyRegistrySignature(
		NewDevRegistrySigner().PublicKey,
		buildReceiptPayload(result.Package, result.Receipt.IssuedAt),
		result.Receipt.RegistrySignature,
	) {
		t.Fatal("expected registry receipt signature to verify")
	}
}

func TestPublishPackageRequiresBearerToken(t *testing.T) {
	handler := NewHandlerWithOptions(NewMemoryStore(), HandlerOptions{
		PublishToken:                    "test-publish-token",
		LegacyGlobalPublishTokenEnabled: true,
	})
	payload, err := json.Marshal(PublishPackageRequest{
		PackageID:            "work-item-fronting",
		PackageVersion:       "0.2.0",
		ProjectRef:           "work-item-fronting",
		ProductRevisionRef:   "product-r3",
		DeveloperRevisionRef: "developer-r5",
		ContractSignature:    "sha256:test-signature",
		Manifest:             map[string]any{"name": "Work Item Fronting"},
		ServiceDefinition:    map[string]any{"artifact_type": "anip_service_definition"},
		RecommendedLock:      map[string]any{"build_pack": map[string]any{"name": "anip-build-pack"}},
	})
	if err != nil {
		t.Fatalf("marshal request: %v", err)
	}

	req := httptest.NewRequest(http.MethodPost, "/registry-api/v1/publications", bytes.NewReader(payload))
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 without token, got %d body=%s", rec.Code, rec.Body.String())
	}
}

func TestPublishPackageRejectsLegacyTokenWhenTransitionFlagDisabled(t *testing.T) {
	handler := NewHandlerWithOptions(NewMemoryStore(), HandlerOptions{
		PublishToken: "test-publish-token",
	})
	body := validTestPublishPackageRequest()
	payload, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal request: %v", err)
	}

	req := httptest.NewRequest(http.MethodPost, "/registry-api/v1/publications", bytes.NewReader(payload))
	req.Header.Set("Authorization", "Bearer test-publish-token")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 when legacy token is disabled, got %d body=%s", rec.Code, rec.Body.String())
	}
}
