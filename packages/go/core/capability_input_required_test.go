package core

import (
	"encoding/json"
	"strings"
	"testing"
)

// SPEC.md §4.1: "required defaults to true ... Runtimes MUST apply this
// default wherever a declaration is read".
func TestCapabilityInputRequiredDefaultsToTrueWhenDecoding(t *testing.T) {
	cases := map[string]struct {
		json string
		want bool
	}{
		"absent":         {`{"name":"origin","type":"string"}`, true},
		"null":           {`{"name":"origin","type":"string","required":null}`, true},
		"explicit true":  {`{"name":"origin","type":"string","required":true}`, true},
		"explicit false": {`{"name":"origin","type":"string","required":false}`, false},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			var input CapabilityInput
			if err := json.Unmarshal([]byte(tc.json), &input); err != nil {
				t.Fatalf("Unmarshal: %v", err)
			}
			if input.Required != tc.want {
				t.Fatalf("Required = %v, want %v", input.Required, tc.want)
			}
			if input.Name != "origin" || input.Type != "string" {
				t.Fatalf("other fields lost: %#v", input)
			}
		})
	}
}

func TestCapabilityInputDecodingKeepsEveryOtherField(t *testing.T) {
	raw := `{"name":"cohort","type":"string","default":"all","description":"Cohort",
	  "semantic_type":"cohort_reference","entity_reference":true,"allowed_values":["all","new"],
	  "catalog_ref":"gtm.cohort_catalog","input_meanings":[{"label":"All","value":"all"}],
	  "resolution":{"mode":"closed_values","on_missing":"use_default"}}`
	var input CapabilityInput
	if err := json.Unmarshal([]byte(raw), &input); err != nil {
		t.Fatalf("Unmarshal: %v", err)
	}
	if !input.Required {
		t.Fatal("Required must default to true")
	}
	if input.Default != "all" || input.Description != "Cohort" || input.SemanticType == nil || *input.SemanticType != "cohort_reference" ||
		!input.EntityReference || len(input.AllowedValues) != 2 || input.CatalogRef == nil || len(input.InputMeanings) != 1 ||
		input.Resolution == nil || input.Resolution.Mode != ResolutionModeClosedValues {
		t.Fatalf("fields lost in decoding: %#v", input)
	}

	// The nested decoders still reject what they rejected before.
	if err := json.Unmarshal([]byte(`{"name":"x","type":"string","resolution":{"mode":"guess"}}`), &input); err == nil {
		t.Fatal("an unknown resolution.mode must still be rejected")
	}
	if err := json.Unmarshal([]byte(`{"name":"x","type":"string","required":"yes"}`), &input); err == nil {
		t.Fatal("a required member that is not a boolean must be rejected")
	}
}

// Serialisation always writes required, so a reader that has not applied the
// default yet sees what the declaration means.
func TestCapabilityInputAlwaysMarshalsRequired(t *testing.T) {
	for _, required := range []bool{true, false} {
		data, err := json.Marshal(CapabilityInput{Name: "origin", Type: "string", Required: required})
		if err != nil {
			t.Fatalf("Marshal: %v", err)
		}
		want := `"required":false`
		if required {
			want = `"required":true`
		}
		if !strings.Contains(string(data), want) {
			t.Fatalf("Marshal = %s, want it to contain %s", data, want)
		}
	}
}

func TestManifestDecodingAppliesTheRequiredDefault(t *testing.T) {
	raw := `{"protocol":"` + ProtocolVersion + `","capabilities":{"search_flights":{
	  "name":"search_flights","description":"Search","contract_version":"1.0",
	  "inputs":[{"name":"origin","type":"airport_code"},
	            {"name":"max_stops","type":"integer","required":false},
	            {"name":"date","type":"date","required":true}],
	  "output":{"type":"object","fields":[]},"side_effect":{"type":"read"},"minimum_scope":["travel.search"]}}}`
	var manifest ANIPManifest
	if err := json.Unmarshal([]byte(raw), &manifest); err != nil {
		t.Fatalf("Unmarshal: %v", err)
	}
	inputs := manifest.Capabilities["search_flights"].Inputs
	if len(inputs) != 3 {
		t.Fatalf("expected three inputs, got %#v", inputs)
	}
	got := []bool{inputs[0].Required, inputs[1].Required, inputs[2].Required}
	if !got[0] || got[1] || !got[2] {
		t.Fatalf("required = %v, want [true false true]", got)
	}

	// A round trip does not change the meaning.
	data, err := json.Marshal(manifest)
	if err != nil {
		t.Fatalf("Marshal: %v", err)
	}
	var again ANIPManifest
	if err := json.Unmarshal(data, &again); err != nil {
		t.Fatalf("Unmarshal round trip: %v", err)
	}
	for i, input := range again.Capabilities["search_flights"].Inputs {
		if input.Required != got[i] {
			t.Fatalf("round trip changed required of %s", input.Name)
		}
	}
}
