package definitionvalidation

import (
	"reflect"
	"strings"
	"testing"
)

// compatPrepareChangeFronting gives compat.prepare_change a hybrid backend
// binding: the backend derives query from discovery and explicitly requires
// change_reason. Tests mutate the returned mapping.
func compatPrepareChangeFronting(definition map[string]any) map[string]any {
	mapping := map[string]any{
		"capability_id":                    "compat.prepare_change",
		"service_id":                       "compat-primary-service",
		"backend_kind":                     "native_api",
		"connection_ref":                   "conn-compat",
		"raw_operation_refs":               []any{"native.prepare_change"},
		"backend_input_mode":               "hybrid",
		"derived_required_backend_inputs":  []any{"query"},
		"explicit_required_backend_inputs": []any{"change_reason"},
	}
	definition["integration_fronting"] = map[string]any{
		"capability_mappings": []any{mapping},
	}
	return mapping
}

func compatCapability(definition map[string]any, capabilityID string) map[string]any {
	for _, entry := range definition["capability_formalizations"].([]any) {
		capability := entry.(map[string]any)
		if capability["capability_id"] == capabilityID {
			return capability
		}
	}
	panic("fixture is missing capability " + capabilityID)
}

func removeCompatInput(definition map[string]any, capabilityID, inputName string) {
	capability := compatCapability(definition, capabilityID)
	kept := []any{}
	for _, item := range capability["inputs"].([]any) {
		if item.(map[string]any)["input_name"] != inputName {
			kept = append(kept, item)
		}
	}
	capability["inputs"] = kept
}

func compatInput(definition map[string]any, capabilityID, inputName string) map[string]any {
	for _, item := range compatCapability(definition, capabilityID)["inputs"].([]any) {
		input := item.(map[string]any)
		if input["input_name"] == inputName {
			return input
		}
	}
	return nil
}

func TestBackendInputsDeclaredByCapabilityAreAccepted(t *testing.T) {
	definition := loadCompatDefinition(t)
	compatPrepareChangeFronting(definition)
	expectCompatDefinitionAccepted(t, definition)
}

func TestExplicitBackendInputIsDeclaredWhenCapabilityOmitsIt(t *testing.T) {
	definition := loadCompatDefinition(t)
	compatPrepareChangeFronting(definition)
	removeCompatInput(definition, "compat.prepare_change", "change_reason")
	// The composition still maps change_reason: the explicit backend input is
	// a declared input of the child, so the mapping targets a real input.
	expectCompatDefinitionAccepted(t, definition)

	declared := DeclareExplicitBackendInputs(definition)
	if compatInput(definition, "compat.prepare_change", "change_reason") != nil {
		t.Fatal("DeclareExplicitBackendInputs modified its argument")
	}
	input := compatInput(declared, "compat.prepare_change", "change_reason")
	if input == nil {
		t.Fatal("explicit backend input change_reason was not declared")
	}
	if input["required"] != true || input["input_type"] != "string" {
		t.Fatalf("declared input does not match the explicit required list: %#v", input)
	}
	if err := ValidateServiceDefinition(declared); err != nil {
		t.Fatalf("declared definition is not valid: %v", err)
	}
	again := DeclareExplicitBackendInputs(declared)
	if !reflect.DeepEqual(again, declared) {
		t.Fatal("DeclareExplicitBackendInputs is not idempotent")
	}
}

func TestExplicitOptionalBackendInputIsDeclaredOptional(t *testing.T) {
	definition := loadCompatDefinition(t)
	mapping := compatPrepareChangeFronting(definition)
	mapping["explicit_optional_backend_inputs"] = []any{"urgency"}
	expectCompatDefinitionAccepted(t, definition)
	input := compatInput(DeclareExplicitBackendInputs(definition), "compat.prepare_change", "urgency")
	if input == nil || input["required"] != false {
		t.Fatalf("explicit optional backend input was not declared optional: %#v", input)
	}
}

func TestExplicitBackendInputOnBindingIsDeclared(t *testing.T) {
	definition := loadCompatDefinition(t)
	mapping := compatPrepareChangeFronting(definition)
	removeCompatInput(definition, "compat.prepare_change", "change_reason")
	delete(mapping, "explicit_required_backend_inputs")
	mapping["backend_bindings"] = []any{
		map[string]any{
			"backend_kind":                     "native_api",
			"connection_ref":                   "conn-compat",
			"raw_operation_refs":               []any{"native.prepare_change"},
			"explicit_required_backend_inputs": []any{"change_reason"},
		},
	}
	expectCompatDefinitionAccepted(t, definition)
	if compatInput(DeclareExplicitBackendInputs(definition), "compat.prepare_change", "change_reason") == nil {
		t.Fatal("binding-level explicit backend input was not declared")
	}
}

func TestImplicitModeDoesNotDeclareExplicitLists(t *testing.T) {
	definition := loadCompatDefinition(t)
	mapping := compatPrepareChangeFronting(definition)
	mapping["backend_input_mode"] = "implicit"
	mapping["explicit_required_backend_inputs"] = []any{"ignored_in_implicit_mode"}
	expectCompatDefinitionAccepted(t, definition)
	if compatInput(DeclareExplicitBackendInputs(definition), "compat.prepare_change", "ignored_in_implicit_mode") != nil {
		t.Fatal("implicit mode declared an explicit backend input it does not use")
	}
}

func TestDeclaredExplicitBackendInputMustBeMappedByComposition(t *testing.T) {
	definition := loadCompatDefinition(t)
	compatPrepareChangeFronting(definition)
	removeCompatInput(definition, "compat.prepare_change", "change_reason")
	delete(compatCompositionInputMapping(definition)["prepare_change"].(map[string]any), "change_reason")
	expectCompatDefinitionRejected(t, definition, `input_mapping["prepare_change"].change_reason is required for child capability "compat.prepare_change"`)
}

func TestExplicitRequiredBackendInputDeclaredOptionalIsRejected(t *testing.T) {
	definition := loadCompatDefinition(t)
	compatPrepareChangeFronting(definition)
	compatInput(definition, "compat.prepare_change", "change_reason")["required"] = false
	expectCompatDefinitionRejected(t, definition, `backend input "change_reason" is in explicit_required_backend_inputs, but capability "compat.prepare_change" declares it optional`)
}

func TestExplicitOptionalBackendInputDeclaredRequiredIsRejected(t *testing.T) {
	definition := loadCompatDefinition(t)
	mapping := compatPrepareChangeFronting(definition)
	mapping["explicit_required_backend_inputs"] = []any{}
	mapping["explicit_optional_backend_inputs"] = []any{"change_reason"}
	expectCompatDefinitionRejected(t, definition, `backend input "change_reason" is in explicit_optional_backend_inputs, but capability "compat.prepare_change" declares it required`)
}

func TestDerivedBackendInputWithNoSourceIsRejected(t *testing.T) {
	for _, field := range []string{"derived_required_backend_inputs", "derived_optional_backend_inputs"} {
		t.Run(field, func(t *testing.T) {
			definition := loadCompatDefinition(t)
			mapping := compatPrepareChangeFronting(definition)
			mapping[field] = append(stringAnySlice(mapping[field]), "project_id")
			expectCompatDefinitionRejected(t, definition, `backend input "project_id" has no source`)
		})
	}
}

func TestDerivedRequiredBackendInputDeclaredOptionalNeedsDefault(t *testing.T) {
	definition := loadCompatDefinition(t)
	compatPrepareChangeFronting(definition)
	query := compatInput(definition, "compat.prepare_change", "query")
	query["required"] = false
	expectCompatDefinitionRejected(t, definition, `backend input "query" has no source when the caller omits it`)

	query["default_value"] = "recent"
	expectCompatDefinitionAccepted(t, definition)

	query["resolution"] = map[string]any{"mode": "explicit_only", "on_missing": "omit"}
	expectCompatDefinitionRejected(t, definition, `backend input "query" has no source when the caller omits it`)
}

func TestExplicitBackendInputNameMustBeAnInputName(t *testing.T) {
	definition := loadCompatDefinition(t)
	mapping := compatPrepareChangeFronting(definition)
	mapping["explicit_optional_backend_inputs"] = []any{"not-an-input-name"}
	err := ValidateServiceDefinition(definition)
	if err == nil || !strings.Contains(err.Error(), "explicit_optional_backend_inputs") || !strings.Contains(err.Error(), "not-an-input-name") {
		t.Fatalf("expected an invalid explicit backend input name to be rejected, got %v", err)
	}
}

func stringAnySlice(value any) []any {
	if items, ok := value.([]any); ok {
		return append([]any{}, items...)
	}
	return []any{}
}
