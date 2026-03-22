package service

import "maps"

// genericMessages maps failure types to generic disclosure messages
// used at the "redacted" level. Per SPEC §6.8.
var genericMessages = map[string]string{
	"scope_insufficient":        "Insufficient scope for this capability",
	"invalid_token":             "Authentication failed",
	"token_expired":             "Token has expired",
	"purpose_mismatch":          "Token purpose does not match this capability",
	"insufficient_authority":    "Insufficient authority for this action",
	"unknown_capability":        "Capability not found",
	"not_found":                 "Resource not found",
	"unavailable":               "Service temporarily unavailable",
	"concurrent_lock":           "Operation conflict",
	"internal_error":            "Internal error",
	"streaming_not_supported":   "Streaming not supported for this capability",
	"scope_escalation":          "Scope escalation not permitted",
}

// RedactFailure applies disclosure-level redaction to a failure response.
// The input is NOT mutated; a new map is returned.
//
// Rules (never redacted): type, retry, resolution.action
// "full": everything as-is
// "reduced": detail truncated to 200 chars, resolution.grantable_by nulled
// "redacted": detail replaced with generic message, resolution fields nulled except action
func RedactFailure(failure map[string]any, level string) map[string]any {
	if level == "full" {
		return copyMap(failure)
	}

	result := copyMap(failure)

	if level == "reduced" {
		if detail, ok := result["detail"].(string); ok && len(detail) > 200 {
			result["detail"] = detail[:200]
		}
		if res, ok := result["resolution"].(map[string]any); ok {
			resCopy := copyMap(res)
			resCopy["grantable_by"] = nil
			result["resolution"] = resCopy
		}
		return result
	}

	// "redacted" mode
	failType, _ := result["type"].(string)
	if msg, ok := genericMessages[failType]; ok {
		result["detail"] = msg
	} else {
		result["detail"] = "Request failed"
	}

	if res, ok := result["resolution"].(map[string]any); ok {
		resCopy := make(map[string]any)
		resCopy["action"] = res["action"]
		resCopy["requires"] = nil
		resCopy["grantable_by"] = nil
		resCopy["estimated_availability"] = nil
		result["resolution"] = resCopy
	}

	return result
}

func copyMap(m map[string]any) map[string]any {
	c := make(map[string]any, len(m))
	maps.Copy(c, m)
	return c
}
