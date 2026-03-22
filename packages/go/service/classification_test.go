package service

import "testing"

func TestClassifyEvent_HighRiskSuccess(t *testing.T) {
	for _, se := range []string{"write", "irreversible", "transactional"} {
		got := ClassifyEvent(se, true, "")
		if got != "high_risk_success" {
			t.Errorf("ClassifyEvent(%q, true, \"\") = %q, want high_risk_success", se, got)
		}
	}
}

func TestClassifyEvent_LowRiskSuccess(t *testing.T) {
	got := ClassifyEvent("read", true, "")
	if got != "low_risk_success" {
		t.Errorf("ClassifyEvent(read, true, \"\") = %q, want low_risk_success", got)
	}
}

func TestClassifyEvent_MalformedOrSpam(t *testing.T) {
	got := ClassifyEvent("", false, "unknown_capability")
	if got != "malformed_or_spam" {
		t.Errorf("ClassifyEvent(\"\", false, unknown_capability) = %q, want malformed_or_spam", got)
	}
	for _, ft := range []string{"unknown_capability", "streaming_not_supported", "internal_error"} {
		got := ClassifyEvent("read", false, ft)
		if got != "malformed_or_spam" {
			t.Errorf("ClassifyEvent(read, false, %q) = %q, want malformed_or_spam", ft, got)
		}
	}
}

func TestClassifyEvent_HighRiskDenial(t *testing.T) {
	for _, ft := range []string{"scope_insufficient", "invalid_token", "token_expired", "purpose_mismatch"} {
		got := ClassifyEvent("write", false, ft)
		if got != "high_risk_denial" {
			t.Errorf("ClassifyEvent(write, false, %q) = %q, want high_risk_denial", ft, got)
		}
	}
}
