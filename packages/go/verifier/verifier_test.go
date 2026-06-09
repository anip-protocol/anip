package verifier

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/anip-protocol/anip/packages/go/generator"
	"github.com/anip-protocol/anip/packages/go/registryapi"
)

const testRegistryPublishToken = "test-publish-token"

func newVerifierRegistryHandler(store registryapi.Store) http.Handler {
	return registryapi.NewHandlerWithOptions(store, registryapi.HandlerOptions{
		PublishToken:  testRegistryPublishToken,
		PublisherID:   "studio-test",
		PublisherType: "studio",
	})
}

func postRegistryPublication(serverURL string, body []byte) (*http.Response, error) {
	req, err := http.NewRequest(http.MethodPost, serverURL+"/registry-api/v1/publications", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+testRegistryPublishToken)
	return http.DefaultClient.Do(req)
}

func validVerifierTestServiceDefinition() map[string]any {
	return map[string]any{
		"artifact_type":           "anip_service_definition",
		"contract_schema_version": "anip-service-definition/v1",
		"compiled_contract_identity": map[string]any{
			"signature":           "sha256:test-contract",
			"signature_algorithm": "sha256",
		},
		"identity": map[string]any{
			"system_name": "Work Item Fronting",
		},
		"service_topology_bindings": []any{
			map[string]any{
				"service_id":   "work-item",
				"service_name": "Work Item Fronting",
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

func validVerifierAgentReadiness() map[string]any {
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

func TestComputedAgentReadinessFlagsRequiredInputsWithoutMeaning(t *testing.T) {
	result := &Result{}
	result.addComputedAgentReadinessChecks(&generator.AnipServiceDefinition{
		CapabilityFormalizations: []generator.CapabilityFormalization{
			{
				CapabilityID: "jira.story.prepare",
				Inputs: []generator.CapabilityInputFormalization{
					{
						InputName: "summary",
						Required:  true,
					},
					{
						InputName:    "project_key",
						Required:     true,
						SemanticType: "project_scope",
					},
				},
			},
		},
	})

	check := result.Checks[0]
	if check.Name != "agent_consumption_required_inputs_classified" {
		t.Fatalf("unexpected check: %+v", check)
	}
	if check.Status != "fail" {
		t.Fatalf("expected missing classification to fail, got %+v", check)
	}
	if !strings.Contains(check.Detail, "jira.story.prepare.summary") {
		t.Fatalf("expected missing input detail, got %+v", check)
	}
}

func validVerifierAgentConsumability() map[string]any {
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

func validVerifierManifest(name string) map[string]any {
	return map[string]any{
		"anip_spec_version":           "anip/0.24",
		"name":                        name,
		"agent_consumption_readiness": validVerifierAgentReadiness(),
		"agent_consumability":         validVerifierAgentConsumability(),
	}
}

func validVerifierLock() map[string]any {
	return map[string]any{
		"verifier_pack": map[string]any{"name": "anip-verifier"},
		"agent_consumption_readiness": map[string]any{
			"status": "ready",
			"score":  float64(100),
			"summary": map[string]any{
				"blockers":          float64(0),
				"warnings":          float64(0),
				"info":              float64(0),
				"probes":            float64(1),
				"required_app_glue": float64(0),
			},
		},
		"agent_consumability": map[string]any{
			"schema_version":   "anip-agent-consumability/v0",
			"capability_count": float64(1),
		},
	}
}

func TestVerifyLocalServiceDefinition(t *testing.T) {
	fixturePath := filepath.Join("..", "generator", "testdata", "work-item-fronting-definition.json")

	result, err := VerifyServiceDefinition(context.Background(), nil, VerifyOptions{
		DefinitionPath: fixturePath,
	})
	if err != nil {
		t.Fatalf("VerifyServiceDefinition: %v", err)
	}
	if result.Status != "ok" {
		t.Fatalf("expected ok result, got %+v", result)
	}
	if result.SourceKind != "file" {
		t.Fatalf("unexpected source kind %q", result.SourceKind)
	}
	if result.DefinitionDigest == "" {
		t.Fatal("expected computed definition digest")
	}
	if !hasCheckStatus(result, "service_definition_shape_valid", "pass") {
		t.Fatalf("expected service definition shape check to pass, got %+v", result.Checks)
	}
	if !hasCheckStatus(result, "integration_fronting_capabilities_formalized", "pass") {
		t.Fatalf("expected integration fronting capability check to pass, got %+v", result.Checks)
	}
	if !hasCheckStatus(result, "integration_fronting_raw_operations_governed", "pass") {
		t.Fatalf("expected integration fronting raw operation check to pass, got %+v", result.Checks)
	}
}

func TestVerifyLocalServiceDefinitionFlagsInvalidV023Shape(t *testing.T) {
	definition := validVerifierTestServiceDefinition()
	capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
	capability["kind"] = "atomic"
	capability["composition"] = map[string]any{
		"authority_boundary": "same_service",
		"steps": []any{
			map[string]any{"id": "search", "capability": "work_item.search"},
		},
	}
	data, err := json.Marshal(definition)
	if err != nil {
		t.Fatalf("marshal definition: %v", err)
	}
	path := filepath.Join(t.TempDir(), "anip-service-definition.json")
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write definition: %v", err)
	}

	result, err := VerifyServiceDefinition(context.Background(), nil, VerifyOptions{
		DefinitionPath: path,
	})
	if err == nil {
		t.Fatalf("expected invalid v0.23 shape to fail current validation, got %+v", result)
	}
	if !strings.Contains(err.Error(), "composition must be null/absent when kind is atomic") {
		t.Fatalf("expected composition validation failure, got %v", err)
	}
}

func TestVerifyLocalServiceDefinitionFlagsInvalidIntegrationFrontingMapping(t *testing.T) {
	definition := validVerifierTestServiceDefinition()
	definition["integration_fronting"] = map[string]any{
		"project_type": "governed_service_project",
		"capability_mappings": []any{
			map[string]any{
				"capability_id":      "work_item.missing",
				"service_id":         "work-item",
				"backend_kind":       "native_api",
				"connection_ref":     "conn-work-items",
				"raw_operation_refs": []any{"native.search_work_items"},
			},
		},
	}
	data, err := json.Marshal(definition)
	if err != nil {
		t.Fatalf("marshal definition: %v", err)
	}
	path := filepath.Join(t.TempDir(), "anip-service-definition.json")
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write definition: %v", err)
	}

	result, err := VerifyServiceDefinition(context.Background(), nil, VerifyOptions{
		DefinitionPath: path,
	})
	if err == nil {
		t.Fatalf("expected invalid integration fronting mapping to fail current validation, got %+v", result)
	}
	if !strings.Contains(err.Error(), "is not a formalized capability") {
		t.Fatalf("expected integration fronting validation failure, got %v", err)
	}
}

func publishRegistryVerifierFixture(t *testing.T, handler http.Handler) *httptest.Server {
	t.Helper()
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)

	publish := registryapi.PublishPackageRequest{
		PackageID:            "work-item-fronting",
		PackageVersion:       "0.2.0",
		ProjectRef:           "work-item-fronting",
		ProductRevisionRef:   "product-r3",
		DeveloperRevisionRef: "developer-r5",
		ContractSignature:    "sha256:test-contract",
		Lineage: map[string]any{
			"project_ref": "work-item-fronting",
			"product_revision": map[string]any{
				"ref":             "product-r3",
				"artifact_id":     "product-r3",
				"revision_number": float64(3),
			},
			"developer_revision": map[string]any{
				"ref":                "developer-r5",
				"artifact_id":        "developer-r5",
				"revision_number":    float64(5),
				"contract_signature": "sha256:test-contract",
			},
		},
		SchemaVersion:     "anip-service-definition/v1",
		Manifest:          validVerifierManifest("Work Item Fronting"),
		ServiceDefinition: validVerifierTestServiceDefinition(),
		RecommendedLock:   validVerifierLock(),
	}
	body, err := json.Marshal(publish)
	if err != nil {
		t.Fatalf("marshal publish request: %v", err)
	}
	resp, err := postRegistryPublication(server.URL, body)
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("expected publish status 201, got %d", resp.StatusCode)
	}
	return server
}

func TestVerifyRegistryServiceDefinition(t *testing.T) {
	store := registryapi.NewMemoryStore()
	handler := newVerifierRegistryHandler(store)
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)

	serviceDefinition := validVerifierTestServiceDefinition()
	publish := registryapi.PublishPackageRequest{
		PackageID:            "work-item-fronting",
		PackageVersion:       "0.2.0",
		ProjectRef:           "work-item-fronting",
		ProductRevisionRef:   "product-r3",
		DeveloperRevisionRef: "developer-r5",
		ContractSignature:    "sha256:test-contract",
		Lineage: map[string]any{
			"project_ref": "work-item-fronting",
			"product_revision": map[string]any{
				"ref":             "product-r3",
				"artifact_id":     "product-r3",
				"revision_number": float64(3),
			},
			"developer_revision": map[string]any{
				"ref":                "developer-r5",
				"artifact_id":        "developer-r5",
				"revision_number":    float64(5),
				"contract_signature": "sha256:test-contract",
			},
		},
		SchemaVersion:     "anip-service-definition/v1",
		Manifest:          validVerifierManifest("Work Item Fronting"),
		ServiceDefinition: serviceDefinition,
		RecommendedLock:   validVerifierLock(),
	}
	body, err := json.Marshal(publish)
	if err != nil {
		t.Fatalf("marshal publish request: %v", err)
	}
	resp, err := postRegistryPublication(server.URL, body)
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("expected publish status 201, got %d", resp.StatusCode)
	}

	result, err := VerifyServiceDefinition(context.Background(), server.Client(), VerifyOptions{
		RegistryBase:              server.URL,
		PackageID:                 "work-item-fronting",
		PackageVersion:            "0.2.0",
		ExpectedContractSignature: "sha256:test-contract",
		RequiredRegistryMode:      "dev",
		TrustedRegistryKeyID:      registryapi.NewDevRegistrySigner().KeyID,
	})
	if err != nil {
		t.Fatalf("VerifyServiceDefinition: %v", err)
	}
	if result.Status != "ok" {
		t.Fatalf("expected ok result, got %+v", result)
	}
	if result.SourceKind != "registry" {
		t.Fatalf("unexpected source kind %q", result.SourceKind)
	}
	if result.RegistryDefinitionDigest == "" || result.RegistryReceiptSignature == "" {
		t.Fatalf("expected registry digest and receipt signature, got %+v", result)
	}
	if result.ReceiptStatus != "verified" {
		t.Fatalf("expected verified receipt status, got %+v", result)
	}
	if result.RegistrySigningMode != "dev" || result.RegistryActiveKeyID == "" {
		t.Fatalf("expected registry signing posture, got %+v", result)
	}
	if result.ProductRevision.(map[string]any)["ref"] != "product-r3" || result.DeveloperRevision.(map[string]any)["ref"] != "developer-r5" {
		t.Fatalf("expected revision metadata, got product=%+v developer=%+v", result.ProductRevision, result.DeveloperRevision)
	}
	if !hasCheckStatus(result, "registry_receipt_signature_valid", "pass") {
		t.Fatalf("expected valid registry receipt signature check, got %+v", result.Checks)
	}
	if !hasCheckStatus(result, "registry_trust_policy_signing_mode_matches", "pass") || !hasCheckStatus(result, "registry_trust_policy_receipt_key_matches", "pass") {
		t.Fatalf("expected registry trust policy checks to pass, got %+v", result.Checks)
	}
	if result.AgentConsumability["schema_version"] != "anip-agent-consumability/v0" {
		t.Fatalf("expected consumability metadata, got %+v", result.AgentConsumability)
	}
	if !hasCheckStatus(result, "agent_consumability_has_capability_hints", "pass") {
		t.Fatalf("expected consumability metadata check to pass, got %+v", result.Checks)
	}
}

func TestVerifyRegistryServiceDefinitionWithLockFile(t *testing.T) {
	store := registryapi.NewMemoryStore()
	handler := newVerifierRegistryHandler(store)
	server := publishRegistryVerifierFixture(t, handler)
	client := server.Client()

	var lock generator.PackageLock
	if err := fetchVerifierTestJSON(client, server.URL+"/registry-api/v1/packages/work-item-fronting/0.2.0/lock", &lock); err != nil {
		t.Fatalf("fetch lock: %v", err)
	}
	lockPath := filepath.Join(t.TempDir(), "work-item-fronting.anip.lock.json")
	lockBytes, err := json.Marshal(lock)
	if err != nil {
		t.Fatalf("marshal lock: %v", err)
	}
	if err := os.WriteFile(lockPath, lockBytes, 0o600); err != nil {
		t.Fatalf("write lock: %v", err)
	}

	result, err := VerifyServiceDefinition(context.Background(), client, VerifyOptions{
		LockFile: lockPath,
	})
	if err != nil {
		t.Fatalf("VerifyServiceDefinition: %v", err)
	}
	if result.Status != "ok" || result.PackageID != "work-item-fronting" {
		t.Fatalf("expected lock-driven registry verification, got %+v", result)
	}
	if !hasCheckStatus(result, "package_lock_matches", "pass") {
		t.Fatalf("expected package lock check to pass, got %+v", result.Checks)
	}

	lock.LockDigest = "sha256:not-the-same-lock"
	badLockBytes, err := json.Marshal(lock)
	if err != nil {
		t.Fatalf("marshal bad lock: %v", err)
	}
	badLockPath := filepath.Join(t.TempDir(), "bad.anip.lock.json")
	if err := os.WriteFile(badLockPath, badLockBytes, 0o600); err != nil {
		t.Fatalf("write bad lock: %v", err)
	}
	badResult, err := VerifyServiceDefinition(context.Background(), client, VerifyOptions{
		LockFile: badLockPath,
	})
	if err != nil {
		t.Fatalf("VerifyServiceDefinition with bad lock should return failed result, not error: %v", err)
	}
	if badResult.Status != "failed" || !hasCheckStatus(badResult, "package_lock_matches", "fail") {
		t.Fatalf("expected package lock check to fail, got %+v", badResult)
	}
}

func TestVerifyRemoteRegistryPackageBundleWithBundledKey(t *testing.T) {
	store := registryapi.NewMemoryStore()
	handler := newVerifierRegistryHandler(store)
	server := publishRegistryVerifierFixture(t, handler)
	client := server.Client()

	var packageRecord map[string]any
	if err := fetchVerifierTestJSON(client, server.URL+"/registry-api/v1/packages/work-item-fronting/0.2.0", &packageRecord); err != nil {
		t.Fatalf("fetch package: %v", err)
	}
	var receipt map[string]any
	if err := fetchVerifierTestJSON(client, server.URL+"/registry-api/v1/packages/work-item-fronting/0.2.0/receipt", &receipt); err != nil {
		t.Fatalf("fetch receipt: %v", err)
	}
	var keys struct {
		Items []map[string]any `json:"items"`
	}
	if err := fetchVerifierTestJSON(client, server.URL+"/registry-api/v1/keys", &keys); err != nil {
		t.Fatalf("fetch keys: %v", err)
	}

	bundle := map[string]any{
		"bundle_schema_version": "anip-package-bundle/v1",
		"authority":             "remote-registry",
		"publication": map[string]any{
			"package_id":         packageRecord["package_id"],
			"package_version":    packageRecord["package_version"],
			"contract_signature": packageRecord["contract_signature"],
			"lineage":            packageRecord["lineage"],
		},
		"package":            packageRecord,
		"receipt":            receipt,
		"lineage":            packageRecord["lineage"],
		"manifest":           packageRecord["manifest"],
		"service_definition": packageRecord["service_definition"],
		"lock":               packageRecord["recommended_lock"],
		"registry_keys":      keys.Items,
	}
	bundlePath := filepath.Join(t.TempDir(), "remote.anip-package.json")
	bytes, err := json.Marshal(bundle)
	if err != nil {
		t.Fatalf("marshal bundle: %v", err)
	}
	if err := os.WriteFile(bundlePath, bytes, 0o600); err != nil {
		t.Fatalf("write bundle: %v", err)
	}

	result, err := VerifyServiceDefinition(context.Background(), nil, VerifyOptions{PackageBundle: bundlePath})
	if err != nil {
		t.Fatalf("VerifyServiceDefinition: %v", err)
	}
	if result.Status != "ok" || result.ReceiptStatus != "verified" {
		t.Fatalf("expected verified remote bundle, got %+v", result)
	}
	if !hasCheckStatus(result, "bundle_receipt_signature_valid", "pass") {
		t.Fatalf("expected bundle ed25519 receipt verification, got %+v", result.Checks)
	}
}

func currentRuntimeAgentReadiness() map[string]any {
	return map[string]any{
		"artifact_type": "agent_consumption_readiness",
		"status":        "ready",
		"score":         float64(100),
		"summary": map[string]any{
			"blockers":          float64(0),
			"warnings":          float64(0),
			"info":              float64(0),
			"probes":            float64(2),
			"required_app_glue": float64(0),
		},
		"findings": []any{},
		"probes": []any{
			map[string]any{"id": "current-runtime-composition", "expected_outcome": "success"},
			map[string]any{"id": "current-runtime-approval-grant", "expected_outcome": "approval_required"},
		},
		"required_app_glue": []any{},
	}
}

func currentRuntimeAgentConsumability() map[string]any {
	return map[string]any{
		"artifact_type":  "agent_consumability_metadata",
		"schema_version": "anip-agent-consumability/v0",
		"capabilities": map[string]any{
			"compat.lookup_and_prepare": map[string]any{
				"intent": map[string]any{
					"category": "compat.lookup.prepare",
					"summary":  "Lookup compatibility records and prepare a governed change as one bounded capability.",
				},
				"business_effects": map[string]any{
					"produces":         []any{"approval.request", "system.preview_mutation"},
					"does_not_produce": []any{"external_dispatch", "system.mutation"},
				},
				"required_context": []any{
					map[string]any{"input": "query", "missing_behavior": "clarify"},
				},
				"app_glue": map[string]any{
					"required": false,
				},
			},
		},
	}
}

func currentRuntimeManifest() map[string]any {
	return map[string]any{
		"anip_spec_version":           "anip/0.24",
		"name":                        "Current Runtime Compatibility Service",
		"agent_consumption_readiness": currentRuntimeAgentReadiness(),
		"agent_consumability":         currentRuntimeAgentConsumability(),
	}
}

func currentRuntimeLock() map[string]any {
	lock := validVerifierLock()
	lock["agent_consumption_readiness"] = currentRuntimeAgentReadiness()
	lock["agent_consumability"] = currentRuntimeAgentConsumability()
	return lock
}

func TestCurrentRuntimeFixtureRegistryBundleAndGenerationHarness(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "testdata", "current-runtime-service-definition.json"))
	if err != nil {
		t.Fatalf("read fixture: %v", err)
	}
	var serviceDefinition map[string]any
	if err := json.Unmarshal(data, &serviceDefinition); err != nil {
		t.Fatalf("decode fixture: %v", err)
	}

	store := registryapi.NewMemoryStore()
	handler := newVerifierRegistryHandler(store)
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)

	publish := registryapi.PublishPackageRequest{
		PackageID:            "current-runtime-compatibility-service",
		PackageVersion:       "1.0.0",
		ProjectRef:           "studio:current-runtime-compatibility-service",
		ProductRevisionRef:   "product-r1",
		DeveloperRevisionRef: "developer-r1",
		ContractSignature:    "sha256:current-runtime-contract",
		Lineage: map[string]any{
			"project_ref": "studio:current-runtime-compatibility-service",
			"product_revision": map[string]any{
				"ref":             "product-r1",
				"artifact_id":     "product-r1",
				"revision_number": float64(1),
			},
			"developer_revision": map[string]any{
				"ref":                "developer-r1",
				"artifact_id":        "developer-r1",
				"revision_number":    float64(1),
				"contract_signature": "sha256:current-runtime-contract",
			},
		},
		SchemaVersion:     "anip-service-definition/v1",
		Manifest:          currentRuntimeManifest(),
		ServiceDefinition: serviceDefinition,
		RecommendedLock:   currentRuntimeLock(),
	}
	body, err := json.Marshal(publish)
	if err != nil {
		t.Fatalf("marshal publish request: %v", err)
	}
	resp, err := postRegistryPublication(server.URL, body)
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("expected publish status 201, got %d", resp.StatusCode)
	}

	registryResult, err := VerifyServiceDefinition(context.Background(), server.Client(), VerifyOptions{
		RegistryBase:         server.URL,
		PackageRef:           "current-runtime-compatibility-service@1.0.0",
		TrustedRegistryKeyID: registryapi.NewDevRegistrySigner().KeyID,
		RequiredRegistryMode: "dev",
	})
	if err != nil {
		t.Fatalf("verify registry package: %v", err)
	}
	if registryResult.Status != "ok" || registryResult.ReceiptStatus != "verified" {
		t.Fatalf("expected verified registry result, got %+v", registryResult)
	}
	if registryResult.AgentConsumability["schema_version"] != "anip-agent-consumability/v0" {
		t.Fatalf("expected registry verifier consumability metadata, got %+v", registryResult.AgentConsumability)
	}
	if !hasCheckStatus(registryResult, "agent_consumability_has_capability_hints", "pass") {
		t.Fatalf("expected registry verifier consumability check, got %+v", registryResult.Checks)
	}

	var packageRecord map[string]any
	if err := fetchVerifierTestJSON(server.Client(), server.URL+"/registry-api/v1/packages/current-runtime-compatibility-service/1.0.0", &packageRecord); err != nil {
		t.Fatalf("fetch package: %v", err)
	}
	var receipt map[string]any
	if err := fetchVerifierTestJSON(server.Client(), server.URL+"/registry-api/v1/packages/current-runtime-compatibility-service/1.0.0/receipt", &receipt); err != nil {
		t.Fatalf("fetch receipt: %v", err)
	}
	var keys struct {
		Items []map[string]any `json:"items"`
	}
	if err := fetchVerifierTestJSON(server.Client(), server.URL+"/registry-api/v1/keys", &keys); err != nil {
		t.Fatalf("fetch keys: %v", err)
	}
	bundle := map[string]any{
		"bundle_schema_version": "anip-package-bundle/v1",
		"authority":             "remote-registry",
		"publication": map[string]any{
			"package_id":         packageRecord["package_id"],
			"package_version":    packageRecord["package_version"],
			"contract_signature": packageRecord["contract_signature"],
			"lineage":            packageRecord["lineage"],
		},
		"package":            packageRecord,
		"receipt":            receipt,
		"lineage":            packageRecord["lineage"],
		"manifest":           packageRecord["manifest"],
		"service_definition": packageRecord["service_definition"],
		"lock":               packageRecord["recommended_lock"],
		"registry_keys":      keys.Items,
	}
	bundlePath := filepath.Join(t.TempDir(), "current-runtime.anip-package.json")
	bundleBytes, err := json.Marshal(bundle)
	if err != nil {
		t.Fatalf("marshal bundle: %v", err)
	}
	if err := os.WriteFile(bundlePath, bundleBytes, 0o600); err != nil {
		t.Fatalf("write bundle: %v", err)
	}

	bundleResult, err := VerifyServiceDefinition(context.Background(), nil, VerifyOptions{PackageBundle: bundlePath})
	if err != nil {
		t.Fatalf("verify bundle: %v", err)
	}
	if bundleResult.Status != "ok" || bundleResult.ReceiptStatus != "verified" {
		t.Fatalf("expected verified bundle result, got %+v", bundleResult)
	}
	if bundleResult.AgentReadiness["status"] != "ready" {
		t.Fatalf("expected bundle verifier readiness metadata, got %+v", bundleResult.AgentReadiness)
	}

	resolved, err := generator.ResolveServiceDefinition(context.Background(), nil, generator.ResolveServiceDefinitionOptions{PackageBundle: bundlePath})
	if err != nil {
		t.Fatalf("resolve bundle for generation: %v", err)
	}
	definition, err := generator.ParseServiceDefinition(resolved.DefinitionBytes)
	if err != nil {
		t.Fatalf("parse resolved definition: %v", err)
	}
	if _, err := generator.BuildTypeScriptProject(definition, generator.BuildTypeScriptProjectOptions{DependencySource: generator.DependencySourceLocal, HttpRuntime: generator.HttpRuntimeHono, Port: 4100}); err != nil {
		t.Fatalf("typescript generation: %v", err)
	}
	if _, err := generator.BuildGoProject(definition, generator.BuildGoProjectOptions{DependencySource: generator.DependencySourceLocal, Port: 4100}); err != nil {
		t.Fatalf("go generation: %v", err)
	}
	if _, err := generator.BuildPythonProject(definition, generator.BuildPythonProjectOptions{DependencySource: generator.DependencySourceLocal, Port: 4100}); err != nil {
		t.Fatalf("python generation: %v", err)
	}
	if _, err := generator.BuildJavaProject(definition, generator.BuildJavaProjectOptions{DependencySource: generator.DependencySourceLocal, Port: 4100}); err != nil {
		t.Fatalf("java generation: %v", err)
	}
	if _, err := generator.BuildCSharpProject(definition, generator.BuildCSharpProjectOptions{DependencySource: generator.DependencySourceLocal, Port: 4100}); err != nil {
		t.Fatalf("csharp generation: %v", err)
	}
	if resolved.AgentConsumability["schema_version"] != "anip-agent-consumability/v0" {
		t.Fatalf("expected resolved consumability metadata, got %+v", resolved.AgentConsumability)
	}
	agentKit, err := generator.BuildAgentConsumptionKit(resolved)
	if err != nil {
		t.Fatalf("agent consumption kit generation: %v", err)
	}
	agentKitContent := generatedVerifierProjectContent(agentKit)
	for _, expected := range []string{"compat.lookup_and_prepare", "compat.lookup.prepare", "approval.request"} {
		if !strings.Contains(agentKitContent, expected) {
			t.Fatalf("agent consumption kit does not preserve %q", expected)
		}
	}
}

func generatedVerifierProjectContent(files []generator.GeneratedFile) string {
	var builder strings.Builder
	for _, file := range files {
		builder.WriteString(file.Content)
		builder.WriteByte('\n')
	}
	return builder.String()
}

func fetchVerifierTestJSON(client *http.Client, url string, target any) error {
	resp, err := client.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return json.NewDecoder(resp.Body).Decode(target)
}

func TestVerifyRegistryServiceDefinitionFailsRequiredProductionMode(t *testing.T) {
	server := publishRegistryVerifierFixture(t, newVerifierRegistryHandler(registryapi.NewMemoryStore()))

	result, err := VerifyServiceDefinition(context.Background(), server.Client(), VerifyOptions{
		RegistryBase:         server.URL,
		PackageID:            "work-item-fronting",
		PackageVersion:       "0.2.0",
		RequiredRegistryMode: "production",
	})
	if err != nil {
		t.Fatalf("VerifyServiceDefinition: %v", err)
	}
	if result.Status != "failed" {
		t.Fatalf("expected failed result, got %+v", result)
	}
	if !hasCheckStatus(result, "registry_trust_policy_signing_mode_matches", "fail") {
		t.Fatalf("expected signing mode trust policy failure, got %+v", result.Checks)
	}
}

func TestVerifyRegistryServiceDefinitionFailsTrustedKeyMismatch(t *testing.T) {
	server := publishRegistryVerifierFixture(t, newVerifierRegistryHandler(registryapi.NewMemoryStore()))

	result, err := VerifyServiceDefinition(context.Background(), server.Client(), VerifyOptions{
		RegistryBase:              server.URL,
		PackageID:                 "work-item-fronting",
		PackageVersion:            "0.2.0",
		TrustedRegistryKeyID:      "registry-prod-2026-04",
		RequiredRegistryMode:      "dev",
		ExpectedContractSignature: "sha256:test-contract",
	})
	if err != nil {
		t.Fatalf("VerifyServiceDefinition: %v", err)
	}
	if result.Status != "failed" {
		t.Fatalf("expected failed result, got %+v", result)
	}
	if !hasCheckStatus(result, "registry_trust_policy_receipt_key_matches", "fail") {
		t.Fatalf("expected trusted key policy failure, got %+v", result.Checks)
	}
}

func TestVerifyRegistryServiceDefinitionFailsTamperedReceiptSignature(t *testing.T) {
	store := registryapi.NewMemoryStore()
	handler := newVerifierRegistryHandler(store)
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
	t.Cleanup(server.Close)

	publish := registryapi.PublishPackageRequest{
		PackageID:            "work-item-fronting",
		PackageVersion:       "0.2.0",
		ProjectRef:           "work-item-fronting",
		ProductRevisionRef:   "product-r3",
		DeveloperRevisionRef: "developer-r5",
		ContractSignature:    "sha256:test-contract",
		SchemaVersion:        "anip-service-definition/v1",
		Manifest:             validVerifierManifest("Work Item Fronting"),
		ServiceDefinition:    validVerifierTestServiceDefinition(),
		RecommendedLock:      validVerifierLock(),
	}
	body, err := json.Marshal(publish)
	if err != nil {
		t.Fatalf("marshal publish request: %v", err)
	}
	resp, err := postRegistryPublication(server.URL, body)
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("expected publish status 201, got %d", resp.StatusCode)
	}

	result, err := VerifyServiceDefinition(context.Background(), server.Client(), VerifyOptions{
		RegistryBase:   server.URL,
		PackageID:      "work-item-fronting",
		PackageVersion: "0.2.0",
	})
	if err != nil {
		t.Fatalf("VerifyServiceDefinition: %v", err)
	}
	if result.Status != "failed" {
		t.Fatalf("expected failed result, got %+v", result)
	}
	if !hasCheckStatus(result, "registry_receipt_signature_valid", "fail") {
		t.Fatalf("expected invalid registry receipt signature check, got %+v", result.Checks)
	}
}

func TestVerifyRegistryServiceDefinitionWithRotatedPreviousKey(t *testing.T) {
	oldSeed := sha256.Sum256([]byte("old-registry-key"))
	newSeed := sha256.Sum256([]byte("new-registry-key"))
	oldSigner, err := registryapi.NewRegistrySigner("registry-old", ed25519.NewKeyFromSeed(oldSeed[:]))
	if err != nil {
		t.Fatalf("create old signer: %v", err)
	}
	newSigner, err := registryapi.NewRegistrySigner("registry-new", ed25519.NewKeyFromSeed(newSeed[:]))
	if err != nil {
		t.Fatalf("create new signer: %v", err)
	}
	store := registryapi.NewMemoryStoreWithSignerAndPublicKeys(oldSigner, []registryapi.RegistryPublicKey{
		newSigner.PublicKeyRecord(),
	})
	handler := newVerifierRegistryHandler(store)
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)

	serviceDefinition := validVerifierTestServiceDefinition()
	publish := registryapi.PublishPackageRequest{
		PackageID:            "work-item-fronting",
		PackageVersion:       "0.2.0",
		ProjectRef:           "work-item-fronting",
		ProductRevisionRef:   "product-r3",
		DeveloperRevisionRef: "developer-r5",
		ContractSignature:    "sha256:test-contract",
		SchemaVersion:        "anip-service-definition/v1",
		Manifest:             validVerifierManifest("Work Item Fronting"),
		ServiceDefinition:    serviceDefinition,
		RecommendedLock:      validVerifierLock(),
	}
	body, err := json.Marshal(publish)
	if err != nil {
		t.Fatalf("marshal publish request: %v", err)
	}
	resp, err := postRegistryPublication(server.URL, body)
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("expected publish status 201, got %d", resp.StatusCode)
	}

	result, err := VerifyServiceDefinition(context.Background(), server.Client(), VerifyOptions{
		RegistryBase:   server.URL,
		PackageID:      "work-item-fronting",
		PackageVersion: "0.2.0",
	})
	if err != nil {
		t.Fatalf("VerifyServiceDefinition: %v", err)
	}
	if result.Status != "ok" {
		t.Fatalf("expected ok result, got %+v", result)
	}
	if !hasCheckStatus(result, "registry_receipt_signature_valid", "pass") {
		t.Fatalf("expected signature to validate with previous key, got %+v", result.Checks)
	}
}

func TestVerifyPackageBundleServiceDefinition(t *testing.T) {
	tempDir := t.TempDir()
	bundlePath := filepath.Join(tempDir, "work-item-fronting-0.2.0.anip-package.json")
	serviceDefinition := validVerifierTestServiceDefinition()
	manifest := validVerifierManifest("Work Item Fronting")
	manifest["version"] = "0.2.0"
	lock := validVerifierLock()
	lineage := map[string]any{
		"project_ref": "work-item-fronting",
		"product_revision": map[string]any{
			"ref":             "product-r3",
			"artifact_id":     "product-r3",
			"revision_number": float64(3),
		},
		"developer_revision": map[string]any{
			"ref":                "developer-r5",
			"artifact_id":        "developer-r5",
			"revision_number":    float64(5),
			"contract_signature": "sha256:test-contract",
		},
	}
	definitionDigest, err := computeCanonicalDigest(serviceDefinition)
	if err != nil {
		t.Fatalf("compute definition digest: %v", err)
	}
	manifestDigest, err := computeCanonicalDigest(manifest)
	if err != nil {
		t.Fatalf("compute manifest digest: %v", err)
	}
	issuedAt := "2026-04-24T00:00:00Z"
	receiptSignature, err := computeCanonicalDigest(map[string]any{
		"authority":          "local-studio",
		"package_id":         "work-item-fronting",
		"package_version":    "0.2.0",
		"contract_signature": "sha256:test-contract",
		"definition_digest":  definitionDigest,
		"lineage":            lineage,
		"manifest_digest":    manifestDigest,
		"issued_at":          issuedAt,
	})
	if err != nil {
		t.Fatalf("compute receipt signature: %v", err)
	}

	bundle := map[string]any{
		"bundle_schema_version": "anip-package-bundle/v1",
		"authority":             "local-studio",
		"publication": map[string]any{
			"package_id":         "work-item-fronting",
			"package_version":    "0.2.0",
			"contract_signature": "sha256:test-contract",
		},
		"package": map[string]any{
			"package_id":             "work-item-fronting",
			"package_version":        "0.2.0",
			"contract_signature":     "sha256:test-contract",
			"lineage":                lineage,
			"schema_version":         "anip-service-definition/v1",
			"manifest_digest":        manifestDigest,
			"definition_digest":      definitionDigest,
			"manifest":               manifest,
			"service_definition":     serviceDefinition,
			"recommended_lock":       lock,
			"developer_revision_ref": "developer-r5",
			"product_revision_ref":   "product-r3",
			"project_ref":            "work-item-fronting",
		},
		"lineage": lineage,
		"receipt": map[string]any{
			"registry_signature": receiptSignature,
			"issued_at":          issuedAt,
			"authority":          "local-studio",
		},
		"manifest":           manifest,
		"service_definition": serviceDefinition,
		"lock":               lock,
	}
	bytes, err := json.Marshal(bundle)
	if err != nil {
		t.Fatalf("marshal bundle: %v", err)
	}
	if err := os.WriteFile(bundlePath, bytes, 0o600); err != nil {
		t.Fatalf("write bundle: %v", err)
	}

	result, err := VerifyServiceDefinition(context.Background(), nil, VerifyOptions{
		PackageBundle:             bundlePath,
		ExpectedContractSignature: "sha256:test-contract",
	})
	if err != nil {
		t.Fatalf("VerifyServiceDefinition: %v", err)
	}
	if result.Status != "ok" {
		t.Fatalf("expected ok result, got %+v", result)
	}
	if result.SourceKind != "package-bundle" {
		t.Fatalf("unexpected source kind %q", result.SourceKind)
	}
	if result.RegistryReceiptSignature != receiptSignature {
		t.Fatalf("unexpected receipt signature %q", result.RegistryReceiptSignature)
	}
	if result.ReceiptStatus != "verified" {
		t.Fatalf("expected verified receipt status, got %+v", result)
	}
	if result.Lineage["project_ref"] != "work-item-fronting" {
		t.Fatalf("expected lineage in verifier result, got %+v", result.Lineage)
	}
	if result.ProductRevision.(map[string]any)["ref"] != "product-r3" || result.DeveloperRevision.(map[string]any)["ref"] != "developer-r5" {
		t.Fatalf("expected flattened revision metadata, got product=%+v developer=%+v", result.ProductRevision, result.DeveloperRevision)
	}
}

func TestVerifyLegacyPackageBundleWithoutLineage(t *testing.T) {
	tempDir := t.TempDir()
	bundlePath := filepath.Join(tempDir, "legacy.anip-package.json")
	serviceDefinition := map[string]any{
		"artifact_type":           "anip_service_definition",
		"contract_schema_version": "anip-service-definition/v1",
		"compiled_contract_identity": map[string]any{
			"signature": "sha256:legacy-contract",
		},
	}
	manifest := validVerifierManifest("Legacy Bundle")
	lock := validVerifierLock()
	definitionDigest, err := computeCanonicalDigest(serviceDefinition)
	if err != nil {
		t.Fatalf("compute definition digest: %v", err)
	}
	manifestDigest, err := computeCanonicalDigest(manifest)
	if err != nil {
		t.Fatalf("compute manifest digest: %v", err)
	}
	issuedAt := "2026-04-24T00:00:00Z"
	receiptSignature, err := computeCanonicalDigest(map[string]any{
		"authority":          "local-studio",
		"package_id":         "legacy-fronting",
		"package_version":    "0.1.0",
		"contract_signature": "sha256:legacy-contract",
		"definition_digest":  definitionDigest,
		"manifest_digest":    manifestDigest,
		"issued_at":          issuedAt,
	})
	if err != nil {
		t.Fatalf("compute receipt signature: %v", err)
	}
	bundle := map[string]any{
		"bundle_schema_version": "anip-package-bundle/v1",
		"authority":             "local-studio",
		"package": map[string]any{
			"package_id":         "legacy-fronting",
			"package_version":    "0.1.0",
			"contract_signature": "sha256:legacy-contract",
			"schema_version":     "anip-service-definition/v1",
			"manifest_digest":    manifestDigest,
			"definition_digest":  definitionDigest,
			"manifest":           manifest,
			"service_definition": serviceDefinition,
			"recommended_lock":   lock,
		},
		"receipt": map[string]any{
			"registry_signature": receiptSignature,
			"issued_at":          issuedAt,
			"authority":          "local-studio",
		},
		"manifest":           manifest,
		"service_definition": serviceDefinition,
		"lock":               lock,
	}
	bytes, err := json.Marshal(bundle)
	if err != nil {
		t.Fatalf("marshal bundle: %v", err)
	}
	if err := os.WriteFile(bundlePath, bytes, 0o600); err != nil {
		t.Fatalf("write bundle: %v", err)
	}

	result, err := VerifyServiceDefinition(context.Background(), nil, VerifyOptions{PackageBundle: bundlePath})
	if err == nil {
		t.Fatalf("expected legacy bundle to fail current service-definition validation, got %+v", result)
	}
	if !strings.Contains(err.Error(), "resolved service definition failed validation") {
		t.Fatalf("expected current validation failure, got %v", err)
	}
}

func hasCheckStatus(result *Result, name string, status string) bool {
	for _, check := range result.Checks {
		if check.Name == name && check.Status == status {
			return true
		}
	}
	return false
}
