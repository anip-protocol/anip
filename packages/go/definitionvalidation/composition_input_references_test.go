package definitionvalidation

import (
	"strings"
	"testing"
)

func composedCompatCapability(definition map[string]any) map[string]any {
	for _, entry := range definition["capability_formalizations"].([]any) {
		capability := entry.(map[string]any)
		if capability["capability_id"] == "compat.lookup_and_prepare" {
			return capability
		}
	}
	panic("fixture is missing the composed capability compat.lookup_and_prepare")
}

func compatCompositionInputMapping(definition map[string]any) map[string]any {
	composition := composedCompatCapability(definition)["composition"].(map[string]any)
	return composition["input_mapping"].(map[string]any)
}

func addCompatChildInput(definition map[string]any, capabilityID, name, inputName string) map[string]any {
	for _, entry := range definition["capability_formalizations"].([]any) {
		capability := entry.(map[string]any)
		if capability["capability_id"] != capabilityID {
			continue
		}
		inputs := capability["inputs"].([]any)
		extra := cloneJSONMap(inputs[0].(map[string]any))
		extra["input_name"] = inputName
		extra["name"] = name
		extra["required"] = false
		extra["summary"] = "Additional child input."
		capability["inputs"] = append(inputs, extra)
		return extra
	}
	panic("fixture is missing capability " + capabilityID)
}

func expectCompatDefinitionAccepted(t *testing.T, definition map[string]any) {
	t.Helper()
	if err := ValidateServiceDefinition(definition); err != nil {
		t.Fatalf("ValidateServiceDefinition: unexpected error: %v", err)
	}
}

func expectCompatDefinitionRejected(t *testing.T, definition map[string]any, message string) {
	t.Helper()
	err := ValidateServiceDefinition(definition)
	if err == nil || !strings.Contains(err.Error(), message) {
		t.Fatalf("expected error containing %q, got %v", message, err)
	}
}

func TestCompositionInputMappingRejectsTargetUnknownToStepChild(t *testing.T) {
	definition := loadCompatDefinition(t)
	mapping := compatCompositionInputMapping(definition)
	mapping["lookup"].(map[string]any)["does_not_exist_input"] = "$.input.query"
	expectCompatDefinitionRejected(t, definition, "does_not_exist_input")
}

func TestCompositionInputMappingRejectsInputNameFromAnotherStepChild(t *testing.T) {
	definition := loadCompatDefinition(t)
	mapping := compatCompositionInputMapping(definition)
	mapping["lookup"].(map[string]any)["change_reason"] = "$.input.query"
	expectCompatDefinitionRejected(t, definition, "change_reason")
}

func TestCompositionInputMappingRejectsUnknownParentInputRoot(t *testing.T) {
	definition := loadCompatDefinition(t)
	mapping := compatCompositionInputMapping(definition)
	mapping["lookup"].(map[string]any)["query"] = "$.input.missing_parent_input"
	expectCompatDefinitionRejected(t, definition, "missing_parent_input")
}

func TestCompositionInputMappingAcceptsNestedParentInputPath(t *testing.T) {
	definition := loadCompatDefinition(t)
	mapping := compatCompositionInputMapping(definition)
	mapping["lookup"].(map[string]any)["query"] = "$.input.query.nested.field"
	expectCompatDefinitionAccepted(t, definition)
}

func TestCompositionInputMappingAcceptsParentBeforeChildOrdering(t *testing.T) {
	definition := loadCompatDefinition(t)
	capabilities := definition["capability_formalizations"].([]any)
	definition["capability_formalizations"] = []any{capabilities[2], capabilities[0], capabilities[1], capabilities[3]}
	expectCompatDefinitionAccepted(t, definition)
}

func TestCompositionInputMappingAcceptsArbitraryPriorStepOutputField(t *testing.T) {
	definition := loadCompatDefinition(t)
	mapping := compatCompositionInputMapping(definition)
	mapping["prepare_change"].(map[string]any)["change_reason"] = "$.steps.lookup.output.derived_change_reason"
	expectCompatDefinitionAccepted(t, definition)
}

func TestCompositionInputMappingPrefersTrimmedInputNameOverName(t *testing.T) {
	t.Run("accepts trimmed input_name target", func(t *testing.T) {
		definition := loadCompatDefinition(t)
		addCompatChildInput(definition, "compat.lookup", "raw_name_input", "  trimmed_input  ")
		mapping := compatCompositionInputMapping(definition)
		mapping["lookup"].(map[string]any)["trimmed_input"] = "$.input.query"
		expectCompatDefinitionAccepted(t, definition)
	})
	t.Run("rejects name when trimmed input_name wins", func(t *testing.T) {
		definition := loadCompatDefinition(t)
		addCompatChildInput(definition, "compat.lookup", "raw_name_input", "  trimmed_input  ")
		mapping := compatCompositionInputMapping(definition)
		mapping["lookup"].(map[string]any)["raw_name_input"] = "$.input.query"
		expectCompatDefinitionRejected(t, definition, "raw_name_input")
	})
}

func TestCompositionInputMappingFallsBackToNameForBlankInputName(t *testing.T) {
	definition := loadCompatDefinition(t)
	addCompatChildInput(definition, "compat.lookup", "blank_fallback_input", "   ")
	mapping := compatCompositionInputMapping(definition)
	mapping["lookup"].(map[string]any)["blank_fallback_input"] = "$.input.query"
	expectCompatDefinitionAccepted(t, definition)
}

func TestCompositionInputMappingAllowsOmittedOptionalChildInput(t *testing.T) {
	definition := loadCompatDefinition(t)
	addCompatChildInput(definition, "compat.prepare_change", "optional_detail", "optional_detail")
	expectCompatDefinitionAccepted(t, definition)
}

func TestCompositionInputMappingValidatesPresentOptionalMapping(t *testing.T) {
	definition := loadCompatDefinition(t)
	addCompatChildInput(definition, "compat.prepare_change", "optional_detail", "optional_detail")
	mapping := compatCompositionInputMapping(definition)
	mapping["prepare_change"].(map[string]any)["optional_detail"] = "$.input.missing_optional_root"
	expectCompatDefinitionRejected(t, definition, "missing_optional_root")
}

func TestCompositionInputMappingStillRequiresRequiredChildInput(t *testing.T) {
	definition := loadCompatDefinition(t)
	extra := addCompatChildInput(definition, "compat.prepare_change", "unmapped_required_input", "unmapped_required_input")
	extra["required"] = true
	expectCompatDefinitionRejected(t, definition, "unmapped_required_input")
}

func TestCompositionInputMappingParentAliases(t *testing.T) {
	for _, tc := range []struct {
		name, inputName, path string
		accepted              bool
	}{
		{"trimmed alias", "  query  ", "$.input.query", true},
		{"alias overrides name", "query", "$.input.fallback", false},
		{"blank alias fallback", "   ", "$.input.fallback", true},
		{"missing nested root", "query", "$.input.missing.nested.field", false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			definition := loadCompatDefinition(t)
			input := composedCompatCapability(definition)["inputs"].([]any)[0].(map[string]any)
			input["input_name"] = tc.inputName
			input["name"] = "fallback"
			if strings.TrimSpace(tc.inputName) == "" {
				compatCompositionInputMapping(definition)["prepare_change"].(map[string]any)["query"] = "$.input.fallback"
			}
			compatCompositionInputMapping(definition)["lookup"].(map[string]any)["query"] = tc.path
			if tc.accepted {
				expectCompatDefinitionAccepted(t, definition)
			} else {
				expectCompatDefinitionRejected(t, definition, `composition.input_mapping["lookup"].query references undeclared parent input`)
			}
		})
	}
}

func TestCompositionInputMappingAcceptsPresentOptionalMapping(t *testing.T) {
	definition := loadCompatDefinition(t)
	addCompatChildInput(definition, "compat.prepare_change", "optional_detail", "optional_detail")
	compatCompositionInputMapping(definition)["prepare_change"].(map[string]any)["optional_detail"] = "$.input.query"
	expectCompatDefinitionAccepted(t, definition)
}

func TestCompositionInputMappingUnknownTargetErrorLocation(t *testing.T) {
	definition := loadCompatDefinition(t)
	compatCompositionInputMapping(definition)["lookup"].(map[string]any)["missing_target"] = "$.input.query"
	expectCompatDefinitionRejected(t, definition, `composition.input_mapping["lookup"].missing_target is not a declared input of child capability "compat.lookup"`)
}
