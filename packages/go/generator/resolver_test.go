package generator

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/anip-protocol/anip/packages/go/registryapi"
)

func validResolverTestServiceDefinition(systemName string) map[string]any {
	return map[string]any{
		"artifact_type":           "anip_service_definition",
		"contract_schema_version": "anip-service-definition/v1",
		"identity": map[string]any{
			"system_name": systemName,
		},
		"service_topology_bindings": []any{
			map[string]any{
				"service_id":   "work-item",
				"service_name": systemName,
			},
		},
		"capability_formalizations": []any{
			map[string]any{
				"service_id":        "work-item",
				"capability_id":     "work_item.search",
				"kind":              "atomic",
				"title":             "Search Work Items",
				"summary":           "Search work items.",
				"intent_type":       "read_only",
				"operation_type":    "query",
				"side_effect_level": "none",
				"backend_operation": "searchWorkItems",
				"path_template":     "/work-items/search",
				"output_shape":      "work_item_search_result",
				"inputs":            []any{},
			},
		},
	}
}

func validResolverAgentReadiness() map[string]any {
	return map[string]any{
		"artifact_type": "agent_consumption_readiness",
		"status":        "ready",
		"score":         float64(100),
		"summary": map[string]any{
			"blockers":          float64(0),
			"warnings":          float64(0),
			"info":              float64(0),
			"probes":            float64(1),
			"required_app_glue": float64(0),
		},
		"findings":          []any{},
		"probes":            []any{map[string]any{"id": "probe-1", "expected_outcome": "success"}},
		"required_app_glue": []any{},
	}
}

func validResolverAgentConsumability() map[string]any {
	return map[string]any{
		"artifact_type":  "agent_consumability_metadata",
		"schema_version": "anip-agent-consumability/v0",
		"capabilities": map[string]any{
			"work_item.search": map[string]any{
				"intent": map[string]any{
					"category": "work.item.search",
					"summary":  "Search work items.",
				},
				"business_effects": map[string]any{
					"produces":         []any{"data.read"},
					"does_not_produce": []any{"system.mutation"},
				},
			},
		},
	}
}

func validResolverManifest(name string) map[string]any {
	return map[string]any{
		"anip_spec_version":           "anip/0.24",
		"name":                        name,
		"agent_consumption_readiness": validResolverAgentReadiness(),
		"agent_consumability":         validResolverAgentConsumability(),
	}
}

func TestResolveServiceDefinitionFromFile(t *testing.T) {
	tempDir := t.TempDir()
	definitionPath := filepath.Join(tempDir, "anip-service-definition.json")
	definitionBytes, err := json.Marshal(validResolverTestServiceDefinition("Test"))
	if err != nil {
		t.Fatalf("marshal definition: %v", err)
	}
	if err := os.WriteFile(definitionPath, definitionBytes, 0o600); err != nil {
		t.Fatalf("write definition file: %v", err)
	}

	resolved, err := ResolveServiceDefinition(context.Background(), nil, ResolveServiceDefinitionOptions{
		DefinitionPath: definitionPath,
	})
	if err != nil {
		t.Fatalf("ResolveServiceDefinition: %v", err)
	}
	if resolved.SourceKind != "file" {
		t.Fatalf("expected file source, got %q", resolved.SourceKind)
	}
	if resolved.SchemaVersion != "anip-service-definition/v1" {
		t.Fatalf("unexpected schema version %q", resolved.SchemaVersion)
	}
}

func TestResolveServiceDefinitionRejectsUnknownBusinessEffect(t *testing.T) {
	tempDir := t.TempDir()
	definitionPath := filepath.Join(tempDir, "anip-service-definition.json")
	definition := validResolverTestServiceDefinition("Test")
	capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
	capability["business_effects"] = map[string]any{
		"produces":         []any{"content.summary"},
		"does_not_produce": []any{"external_send"},
	}
	definitionBytes, err := json.Marshal(definition)
	if err != nil {
		t.Fatalf("marshal definition: %v", err)
	}
	if err := os.WriteFile(definitionPath, definitionBytes, 0o600); err != nil {
		t.Fatalf("write definition file: %v", err)
	}

	_, err = ResolveServiceDefinition(context.Background(), nil, ResolveServiceDefinitionOptions{
		DefinitionPath: definitionPath,
	})
	if err == nil || !strings.Contains(err.Error(), "unknown effect \"external_send\"") {
		t.Fatalf("expected unknown effect rejection, got %v", err)
	}
}

func TestResolveServiceDefinitionFromRegistry(t *testing.T) {
	store := registryapi.NewMemoryStore()
	_, err := store.PublishPackage(registryapi.PublishPackageRequest{
		PackageID:            "work-item-fronting",
		PackageVersion:       "0.2.0",
		ProjectRef:           "work-item-fronting",
		ProductRevisionRef:   "product-r3",
		DeveloperRevisionRef: "developer-r5",
		ContractSignature:    "sha256:test-signature",
		SchemaVersion:        "anip-service-definition/v1",
		Manifest:             validResolverManifest("Work Item Fronting"),
		ServiceDefinition:    validResolverTestServiceDefinition("Work Item Fronting"),
		RecommendedLock:      map[string]any{"verifier_pack": map[string]any{"name": "anip-verifier"}},
	})
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}
	server := httptest.NewServer(registryapi.NewHandler(store))
	defer server.Close()

	resolved, err := ResolveServiceDefinition(context.Background(), server.Client(), ResolveServiceDefinitionOptions{
		RegistryBase:   server.URL,
		PackageID:      "work-item-fronting",
		PackageVersion: "0.2.0",
	})
	if err != nil {
		t.Fatalf("ResolveServiceDefinition: %v", err)
	}
	if resolved.SourceKind != "registry" {
		t.Fatalf("expected registry source, got %q", resolved.SourceKind)
	}
	if resolved.PackageID != "work-item-fronting" || resolved.PackageVersion != "0.2.0" {
		t.Fatalf("unexpected package identity %s@%s", resolved.PackageID, resolved.PackageVersion)
	}
	if resolved.DefinitionDigest == "" || resolved.ManifestDigest == "" || resolved.LockDigest == "" {
		t.Fatalf("expected trusted registry digests, got %+v", resolved)
	}
	if resolved.ReceiptSignature == "" || len(resolved.RegistryTrustChecks) == 0 {
		t.Fatalf("expected trusted registry receipt checks, got %+v", resolved)
	}
	if resolved.AgentReadiness["status"] != "ready" {
		t.Fatalf("expected readiness metadata, got %+v", resolved.AgentReadiness)
	}
	if resolved.AgentConsumability["schema_version"] != "anip-agent-consumability/v0" {
		t.Fatalf("expected consumability metadata, got %+v", resolved.AgentConsumability)
	}
}

func TestResolveServiceDefinitionFromRegistryRejectsUntrustedReceipt(t *testing.T) {
	store := registryapi.NewMemoryStore()
	_, err := store.PublishPackage(registryapi.PublishPackageRequest{
		PackageID:            "work-item-fronting",
		PackageVersion:       "0.2.0",
		ProjectRef:           "work-item-fronting",
		ProductRevisionRef:   "product-r3",
		DeveloperRevisionRef: "developer-r5",
		ContractSignature:    "sha256:test-signature",
		SchemaVersion:        "anip-service-definition/v1",
		Manifest:             validResolverManifest("Work Item Fronting"),
		ServiceDefinition:    validResolverTestServiceDefinition("Work Item Fronting"),
		RecommendedLock:      map[string]any{"verifier_pack": map[string]any{"name": "anip-verifier"}},
	})
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}
	handler := registryapi.NewHandler(store)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/registry-api/v1/packages/work-item-fronting/0.2.0/receipt" {
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{
				"receipt_id":"receipt-test",
				"package_id":"work-item-fronting",
				"package_version":"0.2.0",
				"registry_signature":"ed25519:anip-registry-dev-ed25519-v1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==",
				"signature_algorithm":"ed25519",
				"key_id":"anip-registry-dev-ed25519-v1",
				"issued_at":"2026-04-24T00:00:00Z"
			}`))
			return
		}
		handler.ServeHTTP(w, r)
	}))
	defer server.Close()

	_, err = ResolveServiceDefinition(context.Background(), server.Client(), ResolveServiceDefinitionOptions{
		RegistryBase: server.URL,
		PackageRef:   "work-item-fronting@0.2.0",
	})
	if err == nil {
		t.Fatal("expected untrusted registry package to be rejected")
	}
}

func TestResolveServiceDefinitionFromPackageBundle(t *testing.T) {
	tempDir := t.TempDir()
	bundlePath := filepath.Join(tempDir, "work-item-fronting-0.2.0.anip-package.json")
	definition := validResolverTestServiceDefinition("Work Item Fronting")
	manifest := validResolverManifest("Work Item Fronting")
	lock := map[string]any{"verifier_pack": map[string]any{"name": "anip-verifier"}}
	signature, err := computePackageExecutionSignature(manifest, definition, lock, []map[string]any{}, nil)
	if err != nil {
		t.Fatalf("compute package execution signature: %v", err)
	}
	manifest["package_execution_signature"] = signature
	lock["package_execution_signature"] = signature
	bundle := map[string]any{
		"bundle_schema_version": "anip-package-bundle/v1",
		"authority":             "local-studio",
		"package": map[string]any{
			"package_id":                  "work-item-fronting",
			"package_version":             "0.2.0",
			"contract_signature":          "sha256:test-signature",
			"schema_version":              "anip-service-definition/v1",
			"manifest_digest":             "sha256:manifest-digest",
			"definition_digest":           "sha256:def-digest",
			"lock_digest":                 "sha256:lock-digest",
			"package_execution_signature": signature,
			"manifest":                    manifest,
			"service_definition":          definition,
			"recommended_lock":            lock,
		},
		"receipt": map[string]any{
			"registry_signature": "sha256:receipt-signature",
			"issued_at":          "2026-04-24T00:00:00Z",
			"authority":          "local-studio",
		},
		"digests": map[string]any{
			"package_execution": signature,
		},
	}
	bundleBytes, err := json.Marshal(bundle)
	if err != nil {
		t.Fatalf("marshal package bundle: %v", err)
	}
	if err := os.WriteFile(bundlePath, bundleBytes, 0o600); err != nil {
		t.Fatalf("write package bundle: %v", err)
	}

	resolved, err := ResolveServiceDefinition(context.Background(), nil, ResolveServiceDefinitionOptions{
		PackageBundle: bundlePath,
	})
	if err != nil {
		t.Fatalf("ResolveServiceDefinition: %v", err)
	}
	if resolved.SourceKind != "package-bundle" {
		t.Fatalf("expected package-bundle source, got %q", resolved.SourceKind)
	}
	if resolved.PackageID != "work-item-fronting" || resolved.PackageVersion != "0.2.0" {
		t.Fatalf("unexpected package identity %s@%s", resolved.PackageID, resolved.PackageVersion)
	}
	if resolved.DefinitionDigest != "sha256:def-digest" || resolved.ManifestDigest != "sha256:manifest-digest" {
		t.Fatalf("unexpected bundle digests %+v", resolved)
	}
	if resolved.ReceiptSignature != "sha256:receipt-signature" || resolved.ReceiptAuthority != "local-studio" {
		t.Fatalf("unexpected receipt metadata %+v", resolved)
	}
	if resolved.AgentReadiness["status"] != "ready" {
		t.Fatalf("expected readiness metadata, got %+v", resolved.AgentReadiness)
	}
	if resolved.AgentConsumability["schema_version"] != "anip-agent-consumability/v0" {
		t.Fatalf("expected consumability metadata, got %+v", resolved.AgentConsumability)
	}
}
