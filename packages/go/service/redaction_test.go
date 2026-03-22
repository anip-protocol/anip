package service

import "testing"

func TestRedactFailure_Full(t *testing.T) {
	failure := map[string]any{
		"type":   "scope_insufficient",
		"detail": "Need travel.book scope",
		"retry":  false,
		"resolution": map[string]any{
			"action":       "request_scope",
			"requires":     []string{"travel.book"},
			"grantable_by": "human:samir@example.com",
		},
	}
	result := RedactFailure(failure, "full")
	if result["detail"] != "Need travel.book scope" {
		t.Error("full mode should preserve detail")
	}
	res := result["resolution"].(map[string]any)
	if res["grantable_by"] != "human:samir@example.com" {
		t.Error("full mode should preserve grantable_by")
	}
}

func TestRedactFailure_Reduced(t *testing.T) {
	failure := map[string]any{
		"type":   "scope_insufficient",
		"detail": "Need travel.book scope",
		"retry":  false,
		"resolution": map[string]any{
			"action":       "request_scope",
			"requires":     []string{"travel.book"},
			"grantable_by": "human:samir@example.com",
		},
	}
	result := RedactFailure(failure, "reduced")
	if result["detail"] != "Need travel.book scope" {
		t.Error("reduced should preserve detail (under 200 chars)")
	}
	res := result["resolution"].(map[string]any)
	if res["grantable_by"] != nil {
		t.Error("reduced should null grantable_by")
	}
	if res["action"] != "request_scope" {
		t.Error("reduced should preserve action")
	}
}

func TestRedactFailure_Redacted(t *testing.T) {
	failure := map[string]any{
		"type":   "scope_insufficient",
		"detail": "Need travel.book scope with specific user context",
		"retry":  false,
		"resolution": map[string]any{
			"action":       "request_scope",
			"requires":     []string{"travel.book"},
			"grantable_by": "human:samir@example.com",
		},
	}
	result := RedactFailure(failure, "redacted")
	if result["detail"] != "Insufficient scope for this capability" {
		t.Errorf("redacted detail = %q, want generic message", result["detail"])
	}
	if result["type"] != "scope_insufficient" {
		t.Error("type should never be redacted")
	}
	if result["retry"] != false {
		t.Error("retry should never be redacted")
	}
	res := result["resolution"].(map[string]any)
	if res["action"] != "request_scope" {
		t.Error("action should never be redacted")
	}
	if res["requires"] != nil {
		t.Error("redacted should null requires")
	}
	if res["grantable_by"] != nil {
		t.Error("redacted should null grantable_by")
	}
}

func TestRedactFailure_ReducedTruncatesLongDetail(t *testing.T) {
	longDetail := ""
	for i := 0; i < 300; i++ {
		longDetail += "x"
	}
	failure := map[string]any{
		"type":   "internal_error",
		"detail": longDetail,
		"retry":  false,
	}
	result := RedactFailure(failure, "reduced")
	detail := result["detail"].(string)
	if len(detail) > 200 {
		t.Errorf("reduced should truncate detail to 200 chars, got %d", len(detail))
	}
}

func TestRedactFailure_TypeAndRetryNeverRedacted(t *testing.T) {
	failure := map[string]any{
		"type":   "token_expired",
		"detail": "Token XYZ expired at ...",
		"retry":  true,
	}
	for _, level := range []string{"full", "reduced", "redacted"} {
		result := RedactFailure(failure, level)
		if result["type"] != "token_expired" {
			t.Errorf("level=%q: type was redacted", level)
		}
		if result["retry"] != true {
			t.Errorf("level=%q: retry was redacted", level)
		}
	}
}
