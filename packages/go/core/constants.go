package core

import (
	"crypto/rand"
	"fmt"
)

// ProtocolVersion is the current ANIP protocol version.
const ProtocolVersion = "anip/0.11"

// ManifestVersion is the current manifest metadata version.
const ManifestVersion = "0.10.0"

// Failure type constants.
const (
	FailureAuthRequired                = "authentication_required"
	FailureInvalidToken                = "invalid_token"
	FailureTokenExpired                = "token_expired"
	FailureScopeInsufficient           = "scope_insufficient"
	FailureUnknownCapability           = "unknown_capability"
	FailureBudgetExceeded              = "budget_exceeded"
	FailureBudgetCurrencyMismatch      = "budget_currency_mismatch"
	FailureBudgetNotEnforceable        = "budget_not_enforceable"
	FailureBindingMissing              = "binding_missing"
	FailureBindingStale                = "binding_stale"
	FailureControlRequirementUnsatisfied = "control_requirement_unsatisfied"
	FailurePurposeMismatch             = "purpose_mismatch"
	FailureScopeEscalation             = "scope_escalation"
	FailureNotFound                    = "not_found"
	FailureUnavailable                 = "unavailable"
	FailureConcurrentLock              = "concurrent_lock"
	FailureInternalError               = "internal_error"
	FailureStreamingNotSupported       = "streaming_not_supported"
	FailureInvalidParameters           = "invalid_parameters"
)

// Supported algorithms for signing.
var SupportedAlgorithms = []string{"ES256"}

// Merkle tree hash prefixes per RFC 6962.
const (
	LeafHashPrefix = 0x00
	NodeHashPrefix = 0x01
)

// DefaultProfile is the default ANIP profile version set.
var DefaultProfile = map[string]string{
	"core":             "1.0",
	"cost":             "1.0",
	"capability_graph": "1.0",
	"state_session":    "1.0",
	"observability":    "1.0",
}

// GenerateInvocationID returns a new invocation ID in the format inv-{12 hex chars}.
func GenerateInvocationID() string {
	b := make([]byte, 6)
	_, _ = rand.Read(b)
	return fmt.Sprintf("inv-%x", b)
}
