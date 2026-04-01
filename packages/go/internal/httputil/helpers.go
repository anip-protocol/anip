// Package httputil provides shared HTTP helpers for ANIP protocol bindings.
package httputil

import (
	"strings"

	"github.com/anip-protocol/anip/packages/go/core"
)

// ExtractBearer extracts the token from an "Authorization: Bearer <token>" header value.
func ExtractBearer(authHeader string) string {
	if !strings.HasPrefix(authHeader, "Bearer ") {
		return ""
	}
	return strings.TrimSpace(authHeader[7:])
}

// FailureResponse formats an ANIPError as (statusCode, responseBody).
func FailureResponse(anipErr *core.ANIPError) (int, map[string]any) {
	status := core.FailureStatusCode(anipErr.ErrorType)
	resolution := anipErr.Resolution
	if resolution == nil {
		resolution = DefaultResolution(anipErr.ErrorType)
	}
	resp := map[string]any{
		"success": false,
		"failure": BuildFailureBody(anipErr.ErrorType, anipErr.Detail, resolution, anipErr.Retry),
	}
	return status, resp
}

// SimpleFailureResponse formats a simple failure as (statusCode, responseBody).
func SimpleFailureResponse(failureType, detail string, resolution *core.Resolution) (int, map[string]any) {
	status := core.FailureStatusCode(failureType)
	resp := map[string]any{
		"success": false,
		"failure": BuildFailureBody(failureType, detail, resolution, false),
	}
	return status, resp
}

// AuthFailureTokenEndpoint returns the standard 401 for missing API key on POST /anip/tokens.
func AuthFailureTokenEndpoint() (int, map[string]any) {
	resp := map[string]any{
		"success": false,
		"failure": map[string]any{
			"type":   core.FailureAuthRequired,
			"detail": "A valid API key is required to issue delegation tokens",
			"resolution": map[string]any{
				"action":                  "provide_credentials",
				"recovery_class":          core.RecoveryClassForAction("provide_credentials"),
				"requires":               "API key in Authorization header",
				"grantable_by":           nil,
				"estimated_availability": nil,
			},
			"retry": true,
		},
	}
	return 401, resp
}

// AuthFailureJWTEndpoint returns the standard 401 for missing JWT on protected routes.
func AuthFailureJWTEndpoint() (int, map[string]any) {
	resp := map[string]any{
		"success": false,
		"failure": map[string]any{
			"type":   core.FailureAuthRequired,
			"detail": "A valid delegation token (JWT) is required in the Authorization header",
			"resolution": map[string]any{
				"action":                  "request_new_delegation",
				"recovery_class":          core.RecoveryClassForAction("request_new_delegation"),
				"requires":               "Bearer token from POST /anip/tokens",
				"grantable_by":           nil,
				"estimated_availability": nil,
			},
			"retry": true,
		},
	}
	return 401, resp
}

// BuildFailureBody builds the failure body map used in ANIP error responses.
func BuildFailureBody(failureType, detail string, resolution *core.Resolution, retry bool) map[string]any {
	body := map[string]any{
		"type":   failureType,
		"detail": detail,
		"retry":  retry,
	}
	if resolution != nil {
		body["resolution"] = map[string]any{
			"action":                  resolution.Action,
			"recovery_class":          resolution.RecoveryClass,
			"requires":               nilIfEmpty(resolution.Requires),
			"grantable_by":           nilIfEmpty(resolution.GrantableBy),
			"estimated_availability": nilIfEmpty(resolution.EstimatedAvailability),
		}
	} else {
		body["resolution"] = map[string]any{
			"action":                  "contact_service_owner",
			"recovery_class":          core.RecoveryClassForAction("contact_service_owner"),
			"requires":               nil,
			"grantable_by":           nil,
			"estimated_availability": nil,
		}
	}
	return body
}

// DefaultResolution returns a default resolution for known failure types.
func DefaultResolution(failureType string) *core.Resolution {
	switch failureType {
	case core.FailureInvalidToken, core.FailureTokenExpired:
		return &core.Resolution{
			Action:        "request_new_delegation",
			RecoveryClass: core.RecoveryClassForAction("request_new_delegation"),
			Requires:      "Valid JWT from POST /anip/tokens",
		}
	case core.FailureScopeInsufficient:
		return &core.Resolution{
			Action:        "request_broader_scope",
			RecoveryClass: core.RecoveryClassForAction("request_broader_scope"),
			Requires:      "Token with required scope",
		}
	case core.FailureUnknownCapability:
		return &core.Resolution{
			Action:        "check_manifest",
			RecoveryClass: core.RecoveryClassForAction("check_manifest"),
			Requires:      "Valid capability name from GET /anip/manifest",
		}
	default:
		return &core.Resolution{
			Action:        "contact_service_owner",
			RecoveryClass: core.RecoveryClassForAction("contact_service_owner"),
		}
	}
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}
