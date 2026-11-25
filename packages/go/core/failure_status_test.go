package core

import "testing"

// specHTTPStatus is the table of SPEC.md §6.3 "HTTP Status Codes", row by
// row (it is also HTTP_STATUS in conformance/test_http_status.py).
var specHTTPStatus = map[string]int{
	// 400, stated in the table so that nobody has to infer it.
	"invalid_parameters":               400,
	"streaming_not_supported":          400,
	"approval_required":                400,
	"grant_not_found":                  400,
	"grant_capability_mismatch":        400,
	"grant_scope_mismatch":             400,
	"grant_param_drift":                400,
	"grant_session_invalid":            400,
	"grant_type_not_allowed_by_policy": 400,
	// 401: the caller has not presented a usable credential.
	"authentication_required": 401,
	"invalid_token":           401,
	"token_expired":           401,
	"token_not_registered":    401,
	// 403: the credential is valid, its delegated authority does not cover the request.
	"scope_insufficient":              403,
	"insufficient_authority":          403,
	"purpose_mismatch":                403,
	"scope_escalation":                403,
	"constraint_escalation":           403,
	"broken_delegation_chain":         403,
	"delegation_depth_exceeded":       403,
	"parent_token_expired":            403,
	"budget_exceeded":                 403,
	"budget_currency_mismatch":        403,
	"budget_not_enforceable":          403,
	"binding_missing":                 403,
	"binding_stale":                   403,
	"control_requirement_unsatisfied": 403,
	"approver_not_authorized":         403,
	"grant_requester_mismatch":        403,
	// 404: the named capability, resource or approval request does not exist.
	"unknown_capability":         404,
	"not_found":                  404,
	"approval_request_not_found": 404,
	// 409: conflict with the state of a grant, an approval request or a lock.
	"grant_consumed":                   409,
	"grant_expired":                    409,
	"approval_request_already_decided": 409,
	"approval_request_expired":         409,
	"concurrent_lock":                  409,
	"concurrent_request_rejected":      409,
	"unavailable":                      409,
	// 500 and 503: the service failed.
	"internal_error":      500,
	"service_unavailable": 503,
}

func TestFailureStatusCodeIsTheSpecTable(t *testing.T) {
	if len(specHTTPStatus) != 41 {
		t.Fatalf("the table in SPEC.md §6.3 lists 41 failure types, this copy has %d", len(specHTTPStatus))
	}
	for failureType, want := range specHTTPStatus {
		if got := FailureStatusCode(failureType); got != want {
			t.Errorf("FailureStatusCode(%q) = %d, want %d", failureType, got, want)
		}
	}
}

// "400 ... and every failure type this table does not list, including types a
// capability handler defines".
func TestFailureStatusCodeDefaultsTo400(t *testing.T) {
	for _, failureType := range []string{
		"", "some_unknown_type", "seat_unavailable", "non_delegable_action",
		"composition_child_failed", "denied", "clarification_required",
		"Invalid_Parameters", "internal_error ", "service_unavailable_soon",
	} {
		if got := FailureStatusCode(failureType); got != 400 {
			t.Errorf("FailureStatusCode(%q) = %d, want the default 400", failureType, got)
		}
	}
}

// The constants name the types the table lists.
func TestFailureConstantsUsedByTheTable(t *testing.T) {
	for constant, want := range map[string]string{
		FailureTokenNotRegistered:        "token_not_registered",
		FailureConstraintEscalation:      "constraint_escalation",
		FailureConcurrentRequestRejected: "concurrent_request_rejected",
		FailureServiceUnavailable:        "service_unavailable",
	} {
		if constant != want {
			t.Errorf("constant = %q, want %q", constant, want)
		}
	}
}
