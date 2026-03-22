package service

import "testing"

func TestStorageRedact_LowValueStripsParameters(t *testing.T) {
	for _, ec := range []string{"low_risk_success", "malformed_or_spam", "repeated_low_value_denial"} {
		entry := map[string]any{
			"event_class": ec,
			"parameters":  map[string]any{"origin": "SEA"},
		}
		result := StorageRedactEntry(entry)
		if result["parameters"] != nil {
			t.Errorf("event_class=%q: parameters should be nil, got %v", ec, result["parameters"])
		}
		if result["storage_redacted"] != true {
			t.Errorf("event_class=%q: storage_redacted should be true", ec)
		}
	}
}

func TestStorageRedact_HighValuePreservesParameters(t *testing.T) {
	for _, ec := range []string{"high_risk_success", "high_risk_denial"} {
		entry := map[string]any{
			"event_class": ec,
			"parameters":  map[string]any{"origin": "SEA"},
		}
		result := StorageRedactEntry(entry)
		if result["parameters"] == nil {
			t.Errorf("event_class=%q: parameters should be preserved", ec)
		}
		if result["storage_redacted"] != false {
			t.Errorf("event_class=%q: storage_redacted should be false", ec)
		}
	}
}

func TestStorageRedact_DoesNotMutateOriginal(t *testing.T) {
	entry := map[string]any{
		"event_class": "low_risk_success",
		"parameters":  map[string]any{"origin": "SEA"},
	}
	_ = StorageRedactEntry(entry)
	if entry["parameters"] == nil {
		t.Error("original entry was mutated")
	}
}
