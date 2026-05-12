package core

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestInputResolution_MinimalUnchanged(t *testing.T) {
	// Note on `required` defaulting: Python/TS/Java/C# default missing
	// `required` to true via their respective serializer hooks; Go's plain
	// json.Unmarshal sets bool fields to false when absent. That pre-existing
	// asymmetry is not introduced or fixed by v0.24; do not assert on
	// inp.Required here.
	raw := `{"name":"q","type":"string"}`
	var inp CapabilityInput
	if err := json.Unmarshal([]byte(raw), &inp); err != nil {
		t.Fatalf("v0.23-shaped input should parse: %v", err)
	}
	if inp.Resolution != nil {
		t.Errorf("expected nil Resolution")
	}
	if inp.EntityReference {
		t.Errorf("expected entity_reference=false default")
	}
	if inp.CatalogRef != nil {
		t.Errorf("expected nil CatalogRef")
	}
}

func TestInputResolution_BackendResolved(t *testing.T) {
	raw := `{
		"name":"cohort_ref","type":"string","required":true,
		"semantic_type":"cohort_reference","entity_reference":true,"catalog_ref":"gtm.cohort_catalog",
		"resolution":{"mode":"backend_resolved","resolver_ref":"gtm.cohort_catalog","on_missing":"clarify"}
	}`
	var inp CapabilityInput
	if err := json.Unmarshal([]byte(raw), &inp); err != nil {
		t.Fatalf("parse: %v", err)
	}
	if err := ValidateCapabilityInput(&inp); err != nil {
		t.Fatalf("validate: %v", err)
	}
	if inp.Resolution.Mode != ResolutionModeBackendResolved {
		t.Errorf("mode = %q", inp.Resolution.Mode)
	}
	if *inp.CatalogRef != "gtm.cohort_catalog" {
		t.Errorf("catalog_ref = %q", *inp.CatalogRef)
	}
}

func TestInputResolution_UnknownModeRejectedAtDecode(t *testing.T) {
	raw := `{"name":"x","type":"string","resolution":{"mode":"not_real"}}`
	var inp CapabilityInput
	if err := json.Unmarshal([]byte(raw), &inp); err == nil {
		t.Errorf("expected decode error for unknown mode, got nil")
	}
}

func TestInputResolution_UnknownBehaviorRejectedAtDecode(t *testing.T) {
	raw := `{"name":"x","type":"string","resolution":{"mode":"clarify","on_missing":"bogus"}}`
	var inp CapabilityInput
	if err := json.Unmarshal([]byte(raw), &inp); err == nil {
		t.Errorf("expected decode error for unknown behavior, got nil")
	}
}

func TestInputResolution_MissingModeRejectedAtDecode(t *testing.T) {
	raw := `{"name":"x","type":"string","resolution":{}}`
	var inp CapabilityInput
	if err := json.Unmarshal([]byte(raw), &inp); err == nil {
		t.Errorf("expected decode error for missing resolution.mode, got nil")
	}
}

func TestInputResolution_ClosedValuesRequiresAllowedValues(t *testing.T) {
	raw := `{"name":"x","type":"string","resolution":{"mode":"closed_values"}}`
	var inp CapabilityInput
	_ = json.Unmarshal([]byte(raw), &inp)
	err := ValidateCapabilityInput(&inp)
	if err == nil || !strings.Contains(strings.ToLower(err.Error()), "allowed_values") {
		t.Errorf("expected allowed_values error, got %v", err)
	}
}

func TestInputResolution_UseDefaultRequiresDefault(t *testing.T) {
	raw := `{"name":"x","type":"string","resolution":{"mode":"clarify","on_missing":"use_default"}}`
	var inp CapabilityInput
	_ = json.Unmarshal([]byte(raw), &inp)
	err := ValidateCapabilityInput(&inp)
	if err == nil || !strings.Contains(strings.ToLower(err.Error()), "default") {
		t.Errorf("expected default error, got %v", err)
	}
}

func TestInputResolution_RoundTrip(t *testing.T) {
	original := CapabilityInput{
		Name:            "cohort_ref",
		Type:            "string",
		Required:        true,
		SemanticType:    strPtr("cohort_reference"),
		EntityReference: true,
		CatalogRef:      strPtr("gtm.cohort_catalog"),
		Resolution: &InputResolution{
			Mode:        ResolutionModeBackendResolved,
			ResolverRef: strPtr("gtm.cohort_catalog"),
			OnMissing:   behaviorPtr(ResolutionBehaviorClarify),
		},
	}
	b, err := json.Marshal(original)
	if err != nil {
		t.Fatal(err)
	}
	var rt CapabilityInput
	if err := json.Unmarshal(b, &rt); err != nil {
		t.Fatal(err)
	}
	if rt.Resolution.Mode != original.Resolution.Mode {
		t.Errorf("mode lost in round-trip")
	}
	if *rt.CatalogRef != *original.CatalogRef {
		t.Errorf("catalog_ref lost")
	}
}

func strPtr(s string) *string                              { return &s }
func behaviorPtr(b ResolutionBehavior) *ResolutionBehavior { return &b }
