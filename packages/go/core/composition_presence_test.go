package core

import (
	"encoding/json"
	"reflect"
	"testing"
)

func TestCompositionEmptyResultOutputPresenceRoundTrip(t *testing.T) {
	cases := []struct {
		name   string
		output map[string]any
		wire   string
	}{
		{name: "nil absent"},
		{name: "explicit empty object", output: map[string]any{}, wire: `{}`},
		{name: "populated object", output: map[string]any{"accounts": []any{}, "count": float64(0)}, wire: `{"accounts":[],"count":0}`},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			composition := *composedDecl().Composition
			composition.EmptyResultOutput = tc.output
			data, err := json.Marshal(composition)
			if err != nil {
				t.Fatalf("marshal: %v", err)
			}
			var fields map[string]json.RawMessage
			if err := json.Unmarshal(data, &fields); err != nil {
				t.Fatalf("decode JSON fields: %v", err)
			}
			output, present := fields["empty_result_output"]
			if present != (tc.output != nil) {
				t.Errorf("empty_result_output presence = %v, want %v", present, tc.output != nil)
			}
			if string(output) != tc.wire {
				t.Errorf("empty_result_output JSON = %q, want %q", output, tc.wire)
			}
			got := roundTrip(t, composition)
			if !reflect.DeepEqual(got.EmptyResultOutput, tc.output) {
				t.Errorf("roundtrip empty_result_output = %#v, want %#v", got.EmptyResultOutput, tc.output)
			}
		})
	}
}
