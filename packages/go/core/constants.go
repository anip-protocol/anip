package core

import (
	"crypto/rand"
	"fmt"
)

// RecoveryClassMap maps each canonical resolution action to its recovery class.
var RecoveryClassMap = map[string]string{
	"retry_now":                          "retry_now",
	"wait_and_retry":                     "wait_then_retry",
	"obtain_binding":                     "refresh_then_retry",
	"refresh_binding":                    "refresh_then_retry",
	"obtain_quote_first":                 "refresh_then_retry",
	"revalidate_state":                   "revalidate_then_retry",
	"request_broader_scope":              "redelegation_then_retry",
	"request_budget_increase":            "redelegation_then_retry",
	"request_budget_bound_delegation":    "redelegation_then_retry",
	"request_matching_currency_delegation": "redelegation_then_retry",
	"request_new_delegation":             "redelegation_then_retry",
	"request_capability_binding":         "redelegation_then_retry",
	"request_deeper_delegation":          "redelegation_then_retry",
	"escalate_to_root_principal":         "terminal",
	"provide_credentials":                "retry_now",
	"check_manifest":                     "revalidate_then_retry",
	"contact_service_owner":              "terminal",
	"narrow_scope":                       "terminal",
	"preserve_budget_constraint":         "terminal",
	"narrow_budget":                      "terminal",
	"match_parent_currency":              "terminal",
	"register_missing_ancestor":          "redelegation_then_retry",
	"reduce_delegation_depth":            "terminal",
	"refresh_delegation_chain":           "redelegation_then_retry",
	"register_parent_token_first":        "redelegation_then_retry",
	"narrow_constraints":                 "terminal",
	"preserve_constraint":                "terminal",
	"register_token":                     "redelegation_then_retry",
	"use_token_task_id":                  "revalidate_then_retry",
	"provide_priced_binding":             "refresh_then_retry",
	"list_checkpoints":                   "revalidate_then_retry",
}

// RecoveryClassForAction returns the recovery class for a given action.
// Panics if the action is not in the map.
func RecoveryClassForAction(action string) string {
	cls, ok := RecoveryClassMap[action]
	if !ok {
		panic(fmt.Sprintf("no recovery class mapped for action: %q", action))
	}
	return cls
}

// ProtocolVersion is the current ANIP protocol version.
const ProtocolVersion = "anip/0.15"

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
	FailureNonDelegableAction          = "non_delegable_action"
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
