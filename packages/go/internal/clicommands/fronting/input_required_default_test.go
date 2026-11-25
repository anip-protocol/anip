package fronting

import (
	"encoding/json"
	"testing"
)

// SPEC.md §4.1: a starter input that does not state required is required.
func TestStarterInputRequiredDefaultsToTrue(t *testing.T) {
	var inputs []StarterInput
	if err := json.Unmarshal([]byte(`[
	  {"name": "project_key", "type": "string"},
	  {"name": "limit", "type": "integer", "required": false, "default_value": "25"},
	  {"name": "query", "type": "string", "required": true},
	  {"name": "cursor", "type": "string", "required": null}
	]`), &inputs); err != nil {
		t.Fatalf("Unmarshal: %v", err)
	}
	want := []bool{true, false, true, true}
	for i, input := range inputs {
		if input.Required != want[i] {
			t.Errorf("%s: Required = %v, want %v", input.Name, input.Required, want[i])
		}
	}
	if inputs[1].DefaultValue != "25" || inputs[1].Type != "integer" {
		t.Fatalf("other fields lost in decoding: %#v", inputs[1])
	}

	built := buildInputs(inputs)
	required, optional := inputNamesByRequired(built)
	if len(required) != 3 || len(optional) != 1 || optional[0] != "limit" {
		t.Fatalf("required=%v optional=%v", required, optional)
	}
}
