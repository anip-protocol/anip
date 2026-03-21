package service

// ObservabilityHooks provides optional callbacks for logging, metrics, and tracing.
// All hooks are nil-safe — the caller checks before invoking.
// Hooks must never affect correctness — panics within hooks are recovered.
type ObservabilityHooks struct {
	// Logging hooks
	OnTokenIssued       func(tokenID, subject, capability string)
	OnTokenResolved     func(tokenID, subject string)
	OnInvokeStart       func(invocationID, capability, subject string)
	OnInvokeComplete    func(invocationID, capability string, success bool, durationMs int64)
	OnAuditAppend       func(sequenceNum int, capability, invocationID string)
	OnCheckpointCreated func(checkpointID string, entryCount int)
	OnAuthFailure       func(failureType, detail string)
	OnScopeValidation   func(capability string, granted bool)

	// Metrics hooks
	OnInvokeDuration func(capability string, durationMs int64, success bool)
}

// callHook safely invokes a hook function, recovering from any panics.
func callHook(fn func()) {
	if fn == nil {
		return
	}
	defer func() { recover() }()
	fn()
}
