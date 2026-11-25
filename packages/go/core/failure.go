package core

// ANIPError is a structured protocol failure.
type ANIPError struct {
	ErrorType        string                    `json:"type"`
	Detail           string                    `json:"detail"`
	Resolution       *Resolution               `json:"resolution,omitempty"`
	Retry            bool                      `json:"retry"`
	ApprovalRequired *ApprovalRequiredMetadata `json:"approval_required,omitempty"` // v0.23
}

// Resolution describes how a failure can be resolved.
type Resolution struct {
	Action                string          `json:"action"`
	RecoveryClass         string          `json:"recovery_class"`
	Requires              string          `json:"requires,omitempty"`
	GrantableBy           string          `json:"grantable_by,omitempty"`
	EstimatedAvailability string          `json:"estimated_availability,omitempty"`
	RecoveryTarget        *RecoveryTarget `json:"recovery_target,omitempty"`
}

// Error implements the error interface.
func (e *ANIPError) Error() string {
	return e.ErrorType + ": " + e.Detail
}

// NewANIPError creates a new ANIPError.
func NewANIPError(errType, detail string) *ANIPError {
	return &ANIPError{ErrorType: errType, Detail: detail}
}

// WithResolution adds a resolution to the error, automatically mapping recovery_class.
func (e *ANIPError) WithResolution(action string) *ANIPError {
	e.Resolution = &Resolution{Action: action, RecoveryClass: RecoveryClassForAction(action)}
	return e
}

// WithRetry marks the error as retryable.
func (e *ANIPError) WithRetry() *ANIPError {
	e.Retry = true
	return e
}

// InvalidParametersResolution is the resolution every invalid_parameters
// failure carries (SPEC.md §6.3): the caller corrects the request and sends a
// new one, nothing outside the request has to change. requires says what a
// correct request looks like.
func InvalidParametersResolution(requires string) *Resolution {
	return &Resolution{
		Action:        "retry_now",
		RecoveryClass: RecoveryClassForAction("retry_now"),
		Requires:      requires,
	}
}

// FailureStatusCode maps a failure type to its HTTP status. It is the table
// of SPEC.md §6.3 "HTTP Status Codes" and the one mapping every HTTP binding
// of this runtime uses (protocol endpoints and the REST adapter); a type the
// table does not list, including one a capability handler defines, is 400.
func FailureStatusCode(failureType string) int {
	switch failureType {
	// The caller has not presented a usable credential.
	case FailureAuthRequired, FailureInvalidToken, FailureTokenExpired,
		FailureTokenNotRegistered:
		return 401
	// The credential is valid; its delegated authority (scope, purpose,
	// chain, budget, binding, control requirement, approver role, the
	// principal a grant was issued to) does not cover the request.
	case FailureScopeInsufficient, FailureInsufficientAuthority,
		FailurePurposeMismatch, FailureScopeEscalation,
		FailureConstraintEscalation, FailureBrokenDelegationChain,
		FailureDelegationDepthExceeded, FailureParentTokenExpired,
		FailureBudgetExceeded, FailureBudgetCurrencyMismatch,
		FailureBudgetNotEnforceable, FailureBindingMissing,
		FailureBindingStale, FailureControlRequirementUnsatisfied,
		"approver_not_authorized", "grant_requester_mismatch":
		return 403
	// The named capability, resource or approval request does not exist.
	case FailureUnknownCapability, FailureNotFound,
		"approval_request_not_found":
		return 404
	// The request conflicts with the current state of a grant, an approval
	// request or a lock.
	case "grant_consumed", "grant_expired",
		"approval_request_already_decided", "approval_request_expired",
		FailureConcurrentLock, FailureConcurrentRequestRejected,
		FailureUnavailable:
		return 409
	// The service failed.
	case FailureInternalError:
		return 500
	case FailureServiceUnavailable:
		return 503
	// Everything else: the caller has to change the request.
	default:
		return 400
	}
}
