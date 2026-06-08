package definitionvalidation

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func loadCompatDefinition(t *testing.T) map[string]any {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("..", "testdata", "current-runtime-service-definition.json"))
	if err != nil {
		t.Fatalf("read fixture: %v", err)
	}
	var definition map[string]any
	if err := json.Unmarshal(data, &definition); err != nil {
		t.Fatalf("decode fixture: %v", err)
	}
	return definition
}

func cloneJSONMap(input map[string]any) map[string]any {
	data, err := json.Marshal(input)
	if err != nil {
		panic(err)
	}
	var output map[string]any
	if err := json.Unmarshal(data, &output); err != nil {
		panic(err)
	}
	return output
}

func TestValidateServiceDefinitionAcceptsCanonicalCompatibilityFixture(t *testing.T) {
	if err := ValidateServiceDefinition(loadCompatDefinition(t)); err != nil {
		t.Fatalf("ValidateServiceDefinition: %v", err)
	}
}

func TestValidateServiceDefinitionRejectsInvalidCurrentShapes(t *testing.T) {
	cases := []struct {
		name    string
		mutate  func(map[string]any)
		message string
	}{
		{
			name: "cross-service same_service",
			mutate: func(definition map[string]any) {
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				composition := composed["composition"].(map[string]any)
				steps := composition["steps"].([]any)
				steps[1].(map[string]any)["capability"] = "compat.secondary_lookup"
			},
			message: "same_service composition requires service",
		},
		{
			name: "composed calls composed",
			mutate: func(definition map[string]any) {
				capabilities := definition["capability_formalizations"].([]any)
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				nested := cloneJSONMap(composed)
				nested["id"] = "cap-nested-composed"
				nested["capability_id"] = "compat.nested_composed"
				capabilities = append(capabilities, nested)
				definition["capability_formalizations"] = capabilities
				composition := composed["composition"].(map[string]any)
				steps := composition["steps"].([]any)
				steps[1].(map[string]any)["capability"] = "compat.nested_composed"
				steps[1].(map[string]any)["id"] = "nested"
			},
			message: "must be atomic",
		},
		{
			name: "unknown child capability",
			mutate: func(definition map[string]any) {
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				composition := composed["composition"].(map[string]any)
				steps := composition["steps"].([]any)
				steps[1].(map[string]any)["capability"] = "compat.missing"
			},
			message: "is not defined",
		},
		{
			name: "bad jsonpath",
			mutate: func(definition map[string]any) {
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				composition := composed["composition"].(map[string]any)
				output := composition["output_mapping"].(map[string]any)
				output["result"] = "$.steps.prepare_change.output"
			},
			message: "malformed JSONPath",
		},
		{
			name: "missing required child input mapping",
			mutate: func(definition map[string]any) {
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				composition := composed["composition"].(map[string]any)
				inputMapping := composition["input_mapping"].(map[string]any)
				prepareMapping := inputMapping["prepare_change"].(map[string]any)
				delete(prepareMapping, "change_reason")
			},
			message: "composition.input_mapping[\"prepare_change\"].change_reason is required",
		},
		{
			name: "empty result source without policy",
			mutate: func(definition map[string]any) {
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				composition := composed["composition"].(map[string]any)
				delete(composition, "empty_result_policy")
			},
			message: "empty_result_policy is required",
		},
		{
			name: "empty result success without output",
			mutate: func(definition map[string]any) {
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				composition := composed["composition"].(map[string]any)
				delete(composition, "empty_result_output")
			},
			message: "empty_result_output is required",
		},
		{
			name: "empty output mapping",
			mutate: func(definition map[string]any) {
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				composition := composed["composition"].(map[string]any)
				composition["output_mapping"] = map[string]any{}
			},
			message: "output_mapping must contain at least one field",
		},
		{
			name: "unsupported failure policy value",
			mutate: func(definition map[string]any) {
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				composition := composed["composition"].(map[string]any)
				failurePolicy := composition["failure_policy"].(map[string]any)
				failurePolicy["child_error"] = "ignore"
			},
			message: "child_error must be propagate or fail_parent",
		},
		{
			name: "bad grant policy",
			mutate: func(definition map[string]any) {
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				policy := composed["grant_policy"].(map[string]any)
				policy["default_grant_type"] = "organization_wide"
			},
			message: "default_grant_type is invalid",
		},
		{
			name: "default grant type not allowed",
			mutate: func(definition map[string]any) {
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				policy := composed["grant_policy"].(map[string]any)
				policy["allowed_grant_types"] = []any{"one_time"}
				policy["default_grant_type"] = "session_bound"
			},
			message: "default_grant_type must appear in allowed_grant_types",
		},
		{
			name: "zero grant expiry",
			mutate: func(definition map[string]any) {
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				policy := composed["grant_policy"].(map[string]any)
				policy["expires_in_seconds"] = float64(0)
			},
			message: "expires_in_seconds and max_uses must be positive integers",
		},
		{
			name: "fractional grant max uses",
			mutate: func(definition map[string]any) {
				composed := definition["capability_formalizations"].([]any)[2].(map[string]any)
				policy := composed["grant_policy"].(map[string]any)
				policy["max_uses"] = float64(1.5)
			},
			message: "expires_in_seconds and max_uses must be positive integers",
		},
		{
			name: "missing explicit kind",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				delete(capability, "kind")
			},
			message: "kind is required",
		},
		{
			name: "unsupported service ownership mode",
			mutate: func(definition map[string]any) {
				service := definition["service_topology_bindings"].([]any)[0].(map[string]any)
				service["ownership_mode"] = "primary"
			},
			message: "ownership_mode is not supported",
		},
		{
			name: "unsafe service id",
			mutate: func(definition map[string]any) {
				service := definition["service_topology_bindings"].([]any)[0].(map[string]any)
				service["service_id"] = "../escape"
			},
			message: "service_id is invalid",
		},
		{
			name: "unsafe capability id",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				capability["capability_id"] = "Compat.Search"
			},
			message: "capability_id is invalid",
		},
		{
			name: "unsafe backend operation",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				capability["backend_operation"] = "search; rm -rf /"
			},
			message: "backend_operation is invalid",
		},
		{
			name: "unsafe path template",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				capability["path_template"] = "/../secrets"
			},
			message: "path_template is invalid",
		},
		{
			name: "invalid input validation pattern",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				input := capability["inputs"].([]any)[0].(map[string]any)
				input["validation_pattern"] = "["
			},
			message: "validation_pattern is invalid",
		},
		{
			name: "invalid input format",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				input := capability["inputs"].([]any)[0].(map[string]any)
				input["input_format"] = "quarter-ish"
			},
			message: "input_format is invalid",
		},
		{
			name: "non string allowed value",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				input := capability["inputs"].([]any)[0].(map[string]any)
				input["allowed_values"] = []any{"ok", 1}
			},
			message: "allowed_values must be strings",
		},
		{
			name: "unknown input resolution mode",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				input := capability["inputs"].([]any)[0].(map[string]any)
				input["resolution"] = map[string]any{"mode": "guess"}
			},
			message: "invalid resolution.mode",
		},
		{
			name: "missing input resolution mode",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				input := capability["inputs"].([]any)[0].(map[string]any)
				input["resolution"] = map[string]any{}
			},
			message: "resolution.mode is required",
		},
		{
			name: "closed values without allowed values",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				input := capability["inputs"].([]any)[0].(map[string]any)
				input["resolution"] = map[string]any{"mode": "closed_values"}
			},
			message: "closed_values requires non-empty allowed_values",
		},
		{
			name: "use default without default",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				input := capability["inputs"].([]any)[0].(map[string]any)
				delete(input, "default_value")
				input["resolution"] = map[string]any{
					"mode":       "clarify",
					"on_missing": "use_default",
				}
			},
			message: "on_missing=use_default requires a non-null default",
		},
		{
			name: "legacy reference catalog field",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				input := capability["inputs"].([]any)[0].(map[string]any)
				input["reference_catalog"] = "compat.catalog"
			},
			message: "reference_catalog is not supported",
		},
		{
			name: "unknown business effect",
			mutate: func(definition map[string]any) {
				capability := definition["capability_formalizations"].([]any)[0].(map[string]any)
				capability["business_effects"] = map[string]any{
					"produces":         []any{"content.summary"},
					"does_not_produce": []any{"external_send"},
				}
			},
			message: "unknown effect \"external_send\"",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			definition := loadCompatDefinition(t)
			tc.mutate(definition)
			err := ValidateServiceDefinition(definition)
			if err == nil || !strings.Contains(err.Error(), tc.message) {
				t.Fatalf("expected %q error, got %v", tc.message, err)
			}
		})
	}
}
