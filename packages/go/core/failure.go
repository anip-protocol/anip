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

// FailureStatusCode maps failure types to HTTP status codes.
func FailureStatusCode(failureType string) int {
	switch failureType {
	case FailureAuthRequired, FailureInvalidToken, FailureTokenExpired:
		return 401
	case FailureScopeInsufficient, FailureBudgetExceeded, FailureBudgetCurrencyMismatch,
		FailureBudgetNotEnforceable, FailureBindingMissing, FailureBindingStale,
		FailureControlRequirementUnsatisfied, FailurePurposeMismatch, FailureScopeEscalation,
		// v0.23: approver does not have authority for this capability.
		"approver_not_authorized":
		return 403
	case FailureUnknownCapability, FailureNotFound,
		// v0.23: approval_request_id refers to nothing.
		"approval_request_not_found":
		return 404
	case FailureUnavailable, FailureConcurrentLock,
		// v0.23: state-conflict failures from §4.7 / §4.8 / §4.9.
		"approval_request_already_decided", "approval_request_expired",
		"grant_consumed", "grant_expired":
		return 409
	case FailureInternalError:
		return 500
	case FailureInvalidParameters:
		return 400
	default:
		return 400
	}
}
