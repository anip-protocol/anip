package registryapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func validTestServiceDefinition(systemName string) map[string]any {
	return map[string]any{
		"artifact_type":           "anip_service_definition",
		"contract_schema_version": "anip-service-definition/v1",
		"compiled_contract_identity": map[string]any{
			"signature":           "sha256:test-contract",
			"signature_algorithm": "sha256",
		},
		"identity": map[string]any{
			"system_name":        systemName,
			"domain_name":        "test",
			"delivery_model":     "standalone_service",
			"architecture_shape": "single_service",
		},
		"service_topology_bindings": []any{
			map[string]any{
				"id":                        "svc-test",
				"service_id":                "test-service",
				"service_name":              systemName,
				"source_role":               "data_access",
				"source_capabilities":       []any{"test.search"},
				"formalized_capability_ids": []any{"test.search"},
				"owned_concept_ids":         []any{"test_record"},
			},
		},
		"capability_formalizations": []any{
			map[string]any{
				"id":                "cap-test-search",
				"source_kind":       "data_access",
				"service_id":        "test-service",
				"capability_id":     "test.search",
				"kind":              "atomic",
				"title":             "Search Test Records",
				"summary":           "Search test records.",
				"intent_type":       "read_only",
				"operation_type":    "query",
				"side_effect_level": "none",
				"backend_operation": "searchTestRecords",
				"path_template":     "/test/search",
				"output_shape":      "test_search_result",
				"inputs": []any{
					map[string]any{
						"input_name": "query",
						"input_type": "string",
						"required":   true,
						"summary":    "Search query.",
					},
				},
			},
		},
	}
}

func validTestAgentReadiness() map[string]any {
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

func validTestAgentConsumabilityFor(capabilityIDs ...string) map[string]any {
	capabilities := map[string]any{}
	for _, capabilityID := range capabilityIDs {
		capabilities[capabilityID] = map[string]any{
			"intent": map[string]any{
				"category": capabilityID,
				"summary":  "Governed capability " + capabilityID + ".",
			},
			"business_effects": map[string]any{
				"produces":         []any{"data.read"},
				"does_not_produce": []any{"system.mutation"},
			},
		}
	}
	return map[string]any{
		"artifact_type":  "agent_consumability_metadata",
		"schema_version": "anip-agent-consumability/v0",
		"capabilities":   capabilities,
	}
}

func validTestPublishPackageRequest() PublishPackageRequest {
	return PublishPackageRequest{
		PackageID:            "work-item-fronting",
		PackageVersion:       "0.2.0",
		ProjectRef:           "work-item-fronting",
		ProductRevisionRef:   "product-r3",
		DeveloperRevisionRef: "developer-r5",
		ContractSignature:    "sha256:test-signature",
		SchemaVersion:        "anip-service-definition/v1",
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
				"contract_signature": "sha256:test-signature",
			},
		},
		Manifest: map[string]any{
			"name":                        "Work Item Fronting",
			"anip_spec_version":           "anip/0.24",
			"agent_consumption_readiness": validTestAgentReadiness(),
			"agent_consumability":         validTestAgentConsumabilityFor("test.search"),
		},
		ServiceDefinition: validTestServiceDefinition("Work Item Fronting"),
		RecommendedLock: map[string]any{
			"build_pack":    map[string]any{"name": "anip-build-pack"},
			"verifier_pack": map[string]any{"name": "anip-verifier"},
		},
		Readme: "Work Item Fronting package for registry validation tests.",
		SourceLinks: []PackageSourceLink{
			{Title: "Test Source", URL: "https://github.com/anip-protocol/anip"},
		},
	}
}

func cloneMap(input map[string]any) map[string]any {
	output := make(map[string]any, len(input))
	for key, value := range input {
		output[key] = value
	}
	return output
}

func TestPublishPackageRejectsInvalidServiceDefinition(t *testing.T) {
	handler := NewHandlerWithOptions(NewMemoryStore(), HandlerOptions{
		PublishToken:                    "test-publish-token",
		LegacyGlobalPublishTokenEnabled: true,
	})
	body := validTestPublishPackageRequest()
	body.ServiceDefinition = map[string]any{
		"artifact_type":           "anip_service_definition",
		"contract_schema_version": "anip-service-definition/v1",
		"identity": map[string]any{
			"artifact_name": "studio-internal-coverage-doc.json",
		},
	}
	payload, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("marshal request: %v", err)
	}

	req := httptest.NewRequest(http.MethodPost, "/registry-api/v1/publications", strings.NewReader(string(payload)))
	req.Header.Set("Authorization", "Bearer test-publish-token")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "identity.system_name") {
		t.Fatalf("expected missing identity error, got %s", rec.Body.String())
	}
}

func TestPublishPackageRejectsMissingANIPSpecVersion(t *testing.T) {
	body := validTestPublishPackageRequest()
	delete(body.Manifest, "anip_spec_version")

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "anip_spec_version must be anip/0.24") {
		t.Fatalf("expected missing anip spec version rejection, got %v", err)
	}
}

func TestPublishPackageRejectsOldANIPSpecVersion(t *testing.T) {
	body := validTestPublishPackageRequest()
	body.Manifest["anip_spec_version"] = "anip/0.23"

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "anip_spec_version must be anip/0.24") {
		t.Fatalf("expected old anip spec version rejection, got %v", err)
	}
}

func TestPublishPackageRejectsInvalidInputResolution(t *testing.T) {
	body := validTestPublishPackageRequest()
	capability := body.ServiceDefinition["capability_formalizations"].([]any)[0].(map[string]any)
	input := capability["inputs"].([]any)[0].(map[string]any)
	input["resolution"] = map[string]any{
		"mode": "not_real",
	}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "invalid resolution.mode") {
		t.Fatalf("expected invalid resolution rejection, got %v", err)
	}
}

func TestPublishPackageRejectsUnknownBusinessEffect(t *testing.T) {
	body := validTestPublishPackageRequest()
	capability := body.ServiceDefinition["capability_formalizations"].([]any)[0].(map[string]any)
	capability["business_effects"] = map[string]any{
		"produces":         []any{"content.summary"},
		"does_not_produce": []any{"external_send"},
	}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "unknown effect \"external_send\"") {
		t.Fatalf("expected unknown effect rejection, got %v", err)
	}
}

func TestPublishPackageRejectsUnknownAgentConsumabilityEffect(t *testing.T) {
	body := validTestPublishPackageRequest()
	body.Manifest["agent_consumability"] = map[string]any{
		"schema_version": "anip-agent-consumability/v0",
		"capabilities": map[string]any{
			"test.search": map[string]any{
				"app_profile": map[string]any{
					"app_boundaries": map[string]any{
						"unsupported_effects": []any{"raw_conversation_export"},
					},
				},
			},
		},
	}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "unknown effect \"raw_conversation_export\"") {
		t.Fatalf("expected unknown consumability effect rejection, got %v", err)
	}
}

func TestPublishPackageRejectsRetiredTypescriptBuildPack(t *testing.T) {
	body := validTestPublishPackageRequest()
	body.Manifest["build_packs"] = map[string]any{
		"recommended": []any{"anip-build-pack-typescript@local"},
	}
	if _, err := NewMemoryStore().PublishPackage(body); err == nil {
		t.Fatal("expected retired TypeScript build-pack to be rejected")
	}
}

func TestPublishPackagePreservesReadmeAndSourceLinks(t *testing.T) {
	body := validTestPublishPackageRequest()
	body.ImplementationMaterials = []PackageImplementationMaterial{
		{
			Title:            "Reviewed App Glue",
			Ref:              "registry://acme/work-item-glue@1.2.3#sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
			BundleTreeSHA256: "sha256:abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd",
		},
	}

	result, err := NewMemoryStore().PublishPackage(body)
	if err != nil {
		t.Fatalf("expected package to publish: %v", err)
	}
	if result.Package.Readme != body.Readme {
		t.Fatalf("expected package readme to round-trip, got %q", result.Package.Readme)
	}
	if len(result.Package.SourceLinks) != 1 || result.Package.SourceLinks[0].URL != body.SourceLinks[0].URL {
		t.Fatalf("expected package source links to round-trip, got %+v", result.Package.SourceLinks)
	}
	if result.Package.Manifest["readme"] != body.Readme {
		t.Fatalf("expected readme in manifest, got %+v", result.Package.Manifest)
	}
	if links, ok := result.Package.Manifest["source_links"].([]any); !ok || len(links) != 1 {
		t.Fatalf("expected source links in manifest, got %+v", result.Package.Manifest["source_links"])
	}
	if len(result.Package.ImplementationMaterials) != 1 || result.Package.ImplementationMaterials[0].Ref != body.ImplementationMaterials[0].Ref {
		t.Fatalf("expected implementation materials to round-trip, got %+v", result.Package.ImplementationMaterials)
	}
	material, ok := result.Package.Manifest["implementation_material"].(map[string]any)
	if !ok {
		t.Fatalf("expected implementation material in signed manifest, got %+v", result.Package.Manifest)
	}
	if bundles, ok := material["custom_code_bundles"].([]any); !ok || len(bundles) != 1 {
		t.Fatalf("expected custom bundle refs in signed manifest, got %+v", material)
	}
}

func TestPublishPackageAcceptsReadmeAndSourceLinksFromManifest(t *testing.T) {
	body := validTestPublishPackageRequest()
	body.Readme = ""
	body.SourceLinks = nil
	body.Manifest["readme"] = "Manifest-owned package readme."
	body.Manifest["source_links"] = []any{
		map[string]any{"title": "Manifest Source", "url": "https://gitlab.com/example/project"},
	}
	body.Manifest["implementation_material"] = map[string]any{
		"custom_code_bundles": []any{
			map[string]any{
				"title": "Manifest Glue",
				"ref":   "git+https://github.com/acme/work-item-glue.git@0123456789abcdef0123456789abcdef01234567#sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
			},
		},
	}

	result, err := NewMemoryStore().PublishPackage(body)
	if err != nil {
		t.Fatalf("expected package to publish: %v", err)
	}
	if result.Package.Readme != "Manifest-owned package readme." {
		t.Fatalf("expected manifest readme to become package readme, got %q", result.Package.Readme)
	}
	if len(result.Package.SourceLinks) != 1 || result.Package.SourceLinks[0].Title != "Manifest Source" {
		t.Fatalf("expected manifest source link to become package source links, got %+v", result.Package.SourceLinks)
	}
	if len(result.Package.ImplementationMaterials) != 1 || result.Package.ImplementationMaterials[0].Title != "Manifest Glue" {
		t.Fatalf("expected manifest implementation materials to become package fields, got %+v", result.Package.ImplementationMaterials)
	}
}

func TestPublishPackageRejectsOversizedReadme(t *testing.T) {
	body := validTestPublishPackageRequest()
	body.Readme = strings.Repeat("x", MaxPackageReadmeBytes+1)

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "readme exceeds") {
		t.Fatalf("expected oversized readme rejection, got %v", err)
	}
}

func TestPublishPackageRejectsOversizedManifest(t *testing.T) {
	body := validTestPublishPackageRequest()
	body.Manifest["notes"] = strings.Repeat("x", MaxPackageManifestBytes+1)

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "manifest exceeds") {
		t.Fatalf("expected oversized manifest rejection, got %v", err)
	}
}

func TestPublishPackageRejectsExcessiveJSONNesting(t *testing.T) {
	body := validTestPublishPackageRequest()
	var nested any = "leaf"
	for i := 0; i < MaxPackageJSONDepth+2; i++ {
		nested = map[string]any{"next": nested}
	}
	body.Manifest["nested"] = nested

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "nesting depth") {
		t.Fatalf("expected excessive nesting rejection, got %v", err)
	}
}

func TestPublishPackageRejectsExcessiveCapabilityCount(t *testing.T) {
	body := validTestPublishPackageRequest()
	capabilities := []any{}
	template := body.ServiceDefinition["capability_formalizations"].([]any)[0].(map[string]any)
	for i := 0; i < MaxPackageCapabilities+1; i++ {
		capability := cloneMap(template)
		capability["id"] = "cap-test-search-extra"
		capability["capability_id"] = "test.search_extra"
		capabilities = append(capabilities, capability)
	}
	body.ServiceDefinition["capability_formalizations"] = capabilities

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "capability count exceeds") {
		t.Fatalf("expected excessive capability count rejection, got %v", err)
	}
}

func TestPublishPackageRejectsOversizedExamples(t *testing.T) {
	body := validTestPublishPackageRequest()
	body.Manifest["examples"] = []any{
		map[string]any{"prompt": strings.Repeat("x", MaxPackageExampleBytes+1)},
	}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "examples exceed") {
		t.Fatalf("expected oversized examples rejection, got %v", err)
	}
}

func TestPublishPackageRejectsSuspiciousBinaryAttachment(t *testing.T) {
	body := validTestPublishPackageRequest()
	body.Manifest["attachments"] = []any{
		map[string]any{"filename": "payload.bin", "content": strings.Repeat("A", 5000)},
	}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "suspicious binary payload") {
		t.Fatalf("expected suspicious binary attachment rejection, got %v", err)
	}
}

func TestPublishPackageRejectsInvalidSourceLink(t *testing.T) {
	body := validTestPublishPackageRequest()
	body.SourceLinks = []PackageSourceLink{{Title: "Local File", URL: "file:///tmp/package"}}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "must be an http(s) URL") {
		t.Fatalf("expected invalid source link rejection, got %v", err)
	}
}

func TestPublishPackageRejectsInvalidImplementationMaterialRef(t *testing.T) {
	body := validTestPublishPackageRequest()
	body.ImplementationMaterials = []PackageImplementationMaterial{
		{
			Title: "Floating Branch",
			Ref:   "git+https://github.com/acme/work-item-glue.git@main#sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
		},
	}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "implementation_materials[0].ref is invalid") {
		t.Fatalf("expected invalid implementation material ref rejection, got %v", err)
	}
}

func TestPublishPackageRejectsUnsafeManifestImplementationMaterialRef(t *testing.T) {
	body := validTestPublishPackageRequest()
	body.Manifest["implementation_material"] = map[string]any{
		"custom_code_bundles": []any{
			map[string]any{
				"ref": "registry://acme/work-item-glue@latest#sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
			},
		},
	}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "implementation_materials[0].ref is invalid") {
		t.Fatalf("expected unsafe manifest implementation material rejection, got %v", err)
	}
}

func TestPublishPackageRejectsAtomicCapabilityWithComposition(t *testing.T) {
	body := validTestPublishPackageRequest()
	capability := body.ServiceDefinition["capability_formalizations"].([]any)[0].(map[string]any)
	capability["kind"] = "atomic"
	capability["composition"] = map[string]any{
		"authority_boundary": "same_service",
	}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "composition must be null") {
		t.Fatalf("expected atomic composition rejection, got %v", err)
	}
}

func TestPublishPackageRejectsInvalidGrantPolicy(t *testing.T) {
	body := validTestPublishPackageRequest()
	capability := body.ServiceDefinition["capability_formalizations"].([]any)[0].(map[string]any)
	capability["grant_policy"] = map[string]any{
		"allowed_grant_types": []any{"one_time"},
		"default_grant_type":  "session_bound",
		"expires_in_seconds":  float64(900),
		"max_uses":            float64(1),
	}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "default_grant_type must appear") {
		t.Fatalf("expected invalid grant policy rejection, got %v", err)
	}
}

func TestPublishPackageRejectsInvalidInputValidationPattern(t *testing.T) {
	body := validTestPublishPackageRequest()
	capability := body.ServiceDefinition["capability_formalizations"].([]any)[0].(map[string]any)
	input := capability["inputs"].([]any)[0].(map[string]any)
	input["validation_pattern"] = "["

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "validation_pattern is invalid") {
		t.Fatalf("expected invalid validation pattern rejection, got %v", err)
	}
}

func TestPublishPackageRejectsInvalidInputFormat(t *testing.T) {
	body := validTestPublishPackageRequest()
	capability := body.ServiceDefinition["capability_formalizations"].([]any)[0].(map[string]any)
	input := capability["inputs"].([]any)[0].(map[string]any)
	input["input_format"] = "quarter-ish"

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "input_format is invalid") {
		t.Fatalf("expected invalid input format rejection, got %v", err)
	}
}

func TestPublishPackageRejectsNonStringAllowedValues(t *testing.T) {
	body := validTestPublishPackageRequest()
	capability := body.ServiceDefinition["capability_formalizations"].([]any)[0].(map[string]any)
	input := capability["inputs"].([]any)[0].(map[string]any)
	input["allowed_values"] = []any{"open", 123}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "allowed_values must be strings") {
		t.Fatalf("expected invalid allowed values rejection, got %v", err)
	}
}

func TestPublishPackageAcceptsComposedCapabilityShape(t *testing.T) {
	body := validTestPublishPackageRequest()
	capabilities := body.ServiceDefinition["capability_formalizations"].([]any)
	child := cloneMap(capabilities[0].(map[string]any))
	child["id"] = "cap-test-search-atomic"
	child["capability_id"] = "test.search_records"
	capabilities = append(capabilities, child)
	body.ServiceDefinition["capability_formalizations"] = capabilities
	body.Manifest["agent_consumability"] = validTestAgentConsumabilityFor("test.search", "test.search_records")
	capability := capabilities[0].(map[string]any)
	capability["kind"] = "composed"
	capability["capability_id"] = "test.search"
	capability["composition"] = map[string]any{
		"authority_boundary": "same_service",
		"steps": []any{
			map[string]any{"id": "search", "capability": "test.search_records", "empty_result_source": true},
		},
		"input_mapping": map[string]any{
			"search": map[string]any{"query": "$.input.query"},
		},
		"output_mapping": map[string]any{
			"items": "$.steps.search.output.items",
		},
		"empty_result_policy": "return_success_no_results",
		"empty_result_output": map[string]any{"items": []any{}},
		"failure_policy": map[string]any{
			"child_clarification":     "propagate",
			"child_denial":            "propagate",
			"child_approval_required": "propagate",
			"child_error":             "fail_parent",
		},
		"audit_policy": map[string]any{
			"record_child_invocations": true,
			"parent_task_lineage":      true,
		},
	}

	if _, err := NewMemoryStore().PublishPackage(body); err != nil {
		t.Fatalf("expected composed package to publish: %v", err)
	}
}

func TestPublishPackageRejectsCrossServiceSameServiceComposition(t *testing.T) {
	body := validTestPublishPackageRequest()
	definition := body.ServiceDefinition
	definition["service_topology_bindings"] = append(definition["service_topology_bindings"].([]any), map[string]any{
		"id":                        "svc-other",
		"service_id":                "other-service",
		"service_name":              "Other Service",
		"source_role":               "data_access",
		"source_capabilities":       []any{"test.other_search"},
		"formalized_capability_ids": []any{"test.other_search"},
		"owned_concept_ids":         []any{"test_record"},
	})
	capabilities := definition["capability_formalizations"].([]any)
	child := cloneMap(capabilities[0].(map[string]any))
	child["id"] = "cap-other-search"
	child["service_id"] = "other-service"
	child["capability_id"] = "test.other_search"
	capabilities = append(capabilities, child)
	definition["capability_formalizations"] = capabilities
	capability := capabilities[0].(map[string]any)
	capability["kind"] = "composed"
	capability["composition"] = map[string]any{
		"authority_boundary": "same_service",
		"steps": []any{
			map[string]any{"id": "other_search", "capability": "test.other_search", "empty_result_source": true},
		},
		"input_mapping": map[string]any{
			"other_search": map[string]any{"query": "$.input.query"},
		},
		"output_mapping": map[string]any{
			"items": "$.steps.other_search.output.items",
		},
		"failure_policy": map[string]any{
			"child_clarification":     "propagate",
			"child_denial":            "propagate",
			"child_approval_required": "propagate",
			"child_error":             "fail_parent",
		},
		"audit_policy": map[string]any{
			"record_child_invocations": true,
			"parent_task_lineage":      true,
		},
	}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "same_service composition requires") {
		t.Fatalf("expected cross-service composition rejection, got %v", err)
	}
}

func TestPublishPackageRejectsMalformedCompositionJSONPath(t *testing.T) {
	body := validTestPublishPackageRequest()
	capabilities := body.ServiceDefinition["capability_formalizations"].([]any)
	child := cloneMap(capabilities[0].(map[string]any))
	child["id"] = "cap-test-search-atomic"
	child["capability_id"] = "test.search_records"
	capabilities = append(capabilities, child)
	body.ServiceDefinition["capability_formalizations"] = capabilities
	capability := capabilities[0].(map[string]any)
	capability["kind"] = "composed"
	capability["composition"] = map[string]any{
		"authority_boundary": "same_service",
		"steps": []any{
			map[string]any{"id": "search", "capability": "test.search_records", "empty_result_source": true},
		},
		"input_mapping": map[string]any{
			"search": map[string]any{"query": "$.input.query"},
		},
		"output_mapping": map[string]any{
			"items": "$.steps.search.output",
		},
		"empty_result_policy": "return_success_no_results",
		"empty_result_output": map[string]any{"items": []any{}},
		"failure_policy": map[string]any{
			"child_clarification":     "propagate",
			"child_denial":            "propagate",
			"child_approval_required": "propagate",
			"child_error":             "fail_parent",
		},
		"audit_policy": map[string]any{
			"record_child_invocations": true,
			"parent_task_lineage":      true,
		},
	}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "malformed JSONPath") {
		t.Fatalf("expected malformed JSONPath rejection, got %v", err)
	}
}

func TestPublishPackageRejectsMissingRequiredCompositionInputMapping(t *testing.T) {
	body := validTestPublishPackageRequest()
	capabilities := body.ServiceDefinition["capability_formalizations"].([]any)
	child := cloneMap(capabilities[0].(map[string]any))
	child["id"] = "cap-test-search-atomic"
	child["capability_id"] = "test.search_records"
	capabilities = append(capabilities, child)
	body.ServiceDefinition["capability_formalizations"] = capabilities
	capability := capabilities[0].(map[string]any)
	capability["kind"] = "composed"
	capability["composition"] = map[string]any{
		"authority_boundary": "same_service",
		"steps": []any{
			map[string]any{"id": "search", "capability": "test.search_records"},
		},
		"input_mapping": map[string]any{
			"search": map[string]any{},
		},
		"output_mapping": map[string]any{
			"items": "$.steps.search.output.items",
		},
		"failure_policy": map[string]any{
			"child_clarification":     "propagate",
			"child_denial":            "propagate",
			"child_approval_required": "propagate",
			"child_error":             "fail_parent",
		},
		"audit_policy": map[string]any{
			"record_child_invocations": true,
			"parent_task_lineage":      true,
		},
	}

	if _, err := NewMemoryStore().PublishPackage(body); err == nil || !strings.Contains(err.Error(), "input_mapping[\"search\"].query is required") {
		t.Fatalf("expected missing required child input mapping rejection, got %v", err)
	}
}
