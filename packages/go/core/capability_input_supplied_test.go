package core

import "testing"

// SPEC.md §6.3: a required input must be supplied unless its resolution block
// sets on_missing (§4.10).
func TestCapabilityInputMustBeSupplied(t *testing.T) {
	clarify := ResolutionBehaviorClarify
	cases := map[string]struct {
		input CapabilityInput
		want  bool
	}{
		"required":                    {CapabilityInput{Name: "a", Required: true}, true},
		"optional":                    {CapabilityInput{Name: "a", Required: false}, false},
		"required, resolution only":   {CapabilityInput{Name: "a", Required: true, Resolution: &InputResolution{Mode: ResolutionModeClarify}}, true},
		"required, on_ambiguous only": {CapabilityInput{Name: "a", Required: true, Resolution: &InputResolution{Mode: ResolutionModeClarify, OnAmbiguous: &clarify}}, true},
		"required, on_missing":        {CapabilityInput{Name: "a", Required: true, Resolution: &InputResolution{Mode: ResolutionModeClarify, OnMissing: &clarify}}, false},
		"optional, on_missing":        {CapabilityInput{Name: "a", Required: false, Resolution: &InputResolution{Mode: ResolutionModeClarify, OnMissing: &clarify}}, false},
		"required with default":       {CapabilityInput{Name: "a", Required: true, Default: 1}, true},
	}
	for name, tc := range cases {
		if got := tc.input.MustBeSupplied(); got != tc.want {
			t.Errorf("%s: MustBeSupplied() = %v, want %v", name, got, tc.want)
		}
	}
}
