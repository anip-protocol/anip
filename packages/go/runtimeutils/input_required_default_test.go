package runtimeutils

import (
	"reflect"
	"testing"
)

// SPEC.md §4.1: an input spec that does not state required is required.
func TestMissingRequiredInputNamesTreatsUnstatedRequiredAsRequired(t *testing.T) {
	metadata := CapabilityMetadata{
		"input_specs": []any{
			map[string]any{"name": "account_ref"},
			map[string]any{"name": "quarter", "required": true},
			map[string]any{"name": "notes", "required": false},
		},
	}
	got := MissingRequiredInputNames("please run it", metadata)
	if want := []string{"account_ref", "quarter"}; !reflect.DeepEqual(got, want) {
		t.Fatalf("MissingRequiredInputNames = %v, want %v", got, want)
	}
}
