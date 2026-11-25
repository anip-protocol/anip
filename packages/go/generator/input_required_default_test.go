package generator

import (
	"encoding/json"
	"strings"
	"testing"
)

// SPEC.md §4.1: required defaults to true wherever a declaration is read,
// and serialisation always writes it.
func TestServiceDefinitionInputRequiredDefaultsToTrue(t *testing.T) {
	definition, err := ParseServiceDefinition([]byte(`{
	  "capability_formalizations": [{
	    "capability_id": "example.lookup",
	    "inputs": [
	      {"input_name": "query", "input_type": "string"},
	      {"input_name": "limit", "input_type": "integer", "required": false, "default_value": "10"},
	      {"input_name": "region", "input_type": "string", "required": true},
	      {"input_name": "cursor", "input_type": "string", "required": null}
	    ]
	  }]
	}`))
	if err != nil {
		t.Fatalf("ParseServiceDefinition: %v", err)
	}
	inputs := definition.CapabilityFormalizations[0].Inputs
	want := map[string]bool{"query": true, "limit": false, "region": true, "cursor": true}
	if len(inputs) != len(want) {
		t.Fatalf("expected %d inputs, got %#v", len(want), inputs)
	}
	for _, input := range inputs {
		if input.Required != want[input.InputName] {
			t.Errorf("%s: Required = %v, want %v", input.InputName, input.Required, want[input.InputName])
		}
	}
	if inputs[1].DefaultValue != "10" || inputs[1].InputType != "integer" {
		t.Fatalf("other fields lost in decoding: %#v", inputs[1])
	}

	normalized, err := NormalizeServiceDefinitionBytes(definition)
	if err != nil {
		t.Fatalf("NormalizeServiceDefinitionBytes: %v", err)
	}
	if got := strings.Count(string(normalized), `"required": true`); got != 3 {
		t.Fatalf("the normalized definition states required: true %d times, want 3:\n%s", got, normalized)
	}
	if got := strings.Count(string(normalized), `"required": false`); got != 1 {
		t.Fatalf("the normalized definition states required: false %d times, want 1", got)
	}

	var bad CapabilityInputFormalization
	if err := json.Unmarshal([]byte(`{"input_name":"x","required":"yes"}`), &bad); err == nil {
		t.Fatal("a required member that is not a boolean must be rejected")
	}
}

// An input the definition does not mark optional lands in required_inputs,
// from which every target emits required = true.
func TestGenerationModelTreatsUnstatedRequiredAsRequired(t *testing.T) {
	var capability CapabilityFormalization
	if err := json.Unmarshal([]byte(`{"capability_id":"example.lookup","inputs":[
	  {"input_name":"query","input_type":"string"},
	  {"input_name":"limit","input_type":"integer","required":false}]}`), &capability); err != nil {
		t.Fatalf("Unmarshal: %v", err)
	}
	var required, optional []string
	for _, input := range capability.Inputs {
		if input.Required {
			required = append(required, input.InputName)
		} else {
			optional = append(optional, input.InputName)
		}
	}
	if len(required) != 1 || required[0] != "query" || len(optional) != 1 || optional[0] != "limit" {
		t.Fatalf("required=%v optional=%v, want [query] [limit]", required, optional)
	}
}

// The agent-consumption kit reads the definition as a map.
func TestAgentConsumptionKitTreatsUnstatedRequiredAsRequired(t *testing.T) {
	formalization := map[string]any{
		"inputs": []any{
			map[string]any{"input_name": "target"},
			map[string]any{"input_name": "persona", "required": false},
		},
	}
	contexts := effectiveAgentRequiredContext([]any{
		map[string]any{"input": "target", "missing_behavior": "clarify_or_app_select"},
		map[string]any{"input": "persona", "missing_behavior": "clarify_or_app_select"},
	}, formalization)
	behaviors := map[string]string{}
	for _, item := range contexts {
		context, _ := item.(map[string]any)
		behaviors[stringValue(context["input"])] = stringValue(context["missing_behavior"])
	}
	if behaviors["target"] != "clarify_or_app_select" || behaviors["persona"] != "optional" {
		t.Fatalf("unexpected missing behaviors: %+v", behaviors)
	}
}
