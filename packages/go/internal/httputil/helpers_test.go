package httputil

import (
	"reflect"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
)

// SPEC.md §6.3: invalid_parameters is corrected by the caller and sent again,
// so its resolution is retry_now wherever a binding supplies the default.
func TestInvalidParametersDefaultResolutionIsRetryNow(t *testing.T) {
	resolution := DefaultResolution(core.FailureInvalidParameters)
	if resolution.Action != "retry_now" || resolution.RecoveryClass != "retry_now" || resolution.Requires == "" {
		t.Fatalf("DefaultResolution(invalid_parameters) = %#v, want retry_now / retry_now with a requires text", resolution)
	}

	wantResolution := map[string]any{
		"action":                 "retry_now",
		"recovery_class":         "retry_now",
		"requires":               resolution.Requires,
		"grantable_by":           nil,
		"estimated_availability": nil,
	}
	wantFailure := map[string]any{
		"type":       "invalid_parameters",
		"detail":     "request body must be JSON",
		"resolution": wantResolution,
		"retry":      false,
	}

	status, body := SimpleFailureResponse(core.FailureInvalidParameters, "request body must be JSON", nil)
	if status != 400 || !reflect.DeepEqual(body["failure"], wantFailure) {
		t.Fatalf("SimpleFailureResponse = %d %#v, want 400 %#v", status, body["failure"], wantFailure)
	}

	status, body = FailureResponse(core.NewANIPError(core.FailureInvalidParameters, "request body must be JSON"))
	if status != 400 || !reflect.DeepEqual(body["failure"], wantFailure) {
		t.Fatalf("FailureResponse = %d %#v, want 400 %#v", status, body["failure"], wantFailure)
	}
}

// A failure type without a specific default keeps contact_service_owner, and
// an explicit resolution is never replaced.
func TestSimpleFailureResponseOtherResolutions(t *testing.T) {
	_, body := SimpleFailureResponse(core.FailureInternalError, "lookup failed", nil)
	resolution := body["failure"].(map[string]any)["resolution"].(map[string]any)
	if resolution["action"] != "contact_service_owner" || resolution["recovery_class"] != "terminal" {
		t.Fatalf("internal_error resolution = %#v", resolution)
	}

	explicit := &core.Resolution{Action: "wait_and_retry", RecoveryClass: core.RecoveryClassForAction("wait_and_retry")}
	_, body = SimpleFailureResponse(core.FailureInvalidParameters, "x", explicit)
	resolution = body["failure"].(map[string]any)["resolution"].(map[string]any)
	if resolution["action"] != "wait_and_retry" {
		t.Fatalf("an explicit resolution was replaced: %#v", resolution)
	}
}
