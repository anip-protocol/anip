package core

// ANIPError is a structured protocol failure.
type ANIPError struct {
	ErrorType  string      `json:"type"`
	Detail     string      `json:"detail"`
	Resolution *Resolution `json:"resolution,omitempty"`
	Retry      bool        `json:"retry"`
}

// Resolution describes how a failure can be resolved.
type Resolution struct {
	Action                string `json:"action"`
	Requires              string `json:"requires,omitempty"`
	GrantableBy           string `json:"grantable_by,omitempty"`
	EstimatedAvailability string `json:"estimated_availability,omitempty"`
}

// Error implements the error interface.
func (e *ANIPError) Error() string {
	return e.ErrorType + ": " + e.Detail
}

// NewANIPError creates a new ANIPError.
func NewANIPError(errType, detail string) *ANIPError {
	return &ANIPError{ErrorType: errType, Detail: detail}
}

// WithResolution adds a resolution to the error.
func (e *ANIPError) WithResolution(action string) *ANIPError {
	e.Resolution = &Resolution{Action: action}
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
		FailureControlRequirementUnsatisfied, FailurePurposeMismatch, FailureScopeEscalation:
		return 403
	case FailureUnknownCapability, FailureNotFound:
		return 404
	case FailureUnavailable, FailureConcurrentLock:
		return 409
	case FailureInternalError:
		return 500
	case FailureInvalidParameters:
		return 400
	default:
		return 400
	}
}
