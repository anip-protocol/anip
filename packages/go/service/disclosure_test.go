package service

import "testing"

func TestResolveDisclosureLevel_FixedModes(t *testing.T) {
	for _, level := range []string{"full", "reduced", "redacted"} {
		got := ResolveDisclosureLevel(level, nil, nil)
		if got != level {
			t.Errorf("ResolveDisclosureLevel(%q) = %q, want %q", level, got, level)
		}
	}
}

func TestResolveDisclosureLevel_PolicyNoPolicy(t *testing.T) {
	got := ResolveDisclosureLevel("policy", nil, nil)
	if got != "redacted" {
		t.Errorf("policy mode with nil policy should default to redacted, got %q", got)
	}
}

func TestResolveDisclosureLevel_PolicyWithCallerClass(t *testing.T) {
	claims := map[string]any{"anip:caller_class": "internal"}
	policy := map[string]string{
		"internal": "full",
		"default":  "redacted",
	}
	got := ResolveDisclosureLevel("policy", claims, policy)
	if got != "full" {
		t.Errorf("internal caller should get full, got %q", got)
	}
}

func TestResolveDisclosureLevel_PolicyFallsBackToDefault(t *testing.T) {
	claims := map[string]any{"anip:caller_class": "unknown_class"}
	policy := map[string]string{
		"internal": "full",
		"default":  "reduced",
	}
	got := ResolveDisclosureLevel("policy", claims, policy)
	if got != "reduced" {
		t.Errorf("unknown caller should fall back to default, got %q", got)
	}
}

func TestResolveDisclosureLevel_PolicyFromScope(t *testing.T) {
	claims := map[string]any{
		"scope": []any{"travel.search", "audit:full"},
	}
	policy := map[string]string{
		"audit_full": "full",
		"default":    "redacted",
	}
	got := ResolveDisclosureLevel("policy", claims, policy)
	if got != "full" {
		t.Errorf("audit:full scope should resolve to audit_full class, got %q", got)
	}
}
