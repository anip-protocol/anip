package core

import "slices"

// v0.23 — Capability Composition and Approval Grants. See SPEC.md §4.6–§4.9.

// --- Capability Composition ---

// CapabilityKind classifies a capability's execution model. v0.23.
const (
	CapabilityKindAtomic   = "atomic"
	CapabilityKindComposed = "composed"
)

// AuthorityBoundary declares where composed steps run. Only same_service is
// supported in v0.23; same_package and external_service are reserved.
const (
	AuthorityBoundarySameService     = "same_service"
	AuthorityBoundarySamePackage     = "same_package"
	AuthorityBoundaryExternalService = "external_service"
)

// EmptyResultPolicy declares how a composition handles an empty intermediate
// result from a step flagged with empty_result_source. v0.23.
const (
	EmptyResultPolicyReturnSuccessNoResults = "return_success_no_results"
	EmptyResultPolicyClarify                = "clarify"
	EmptyResultPolicyDeny                   = "deny"
)

// FailurePolicyOutcome declares how a child step outcome is reflected in the
// parent capability response. v0.23.
const (
	FailurePolicyOutcomePropagate  = "propagate"
	FailurePolicyOutcomeFailParent = "fail_parent"
)

// CompositionStep is one ordered step in a composed capability. v0.23.
type CompositionStep struct {
	ID                string `json:"id"`
	Capability        string `json:"capability"`
	EmptyResultSource bool   `json:"empty_result_source,omitempty"`
	EmptyResultPath   string `json:"empty_result_path,omitempty"`
}

// FailurePolicy declares per-child-outcome failure handling. v0.23.
type FailurePolicy struct {
	ChildClarification    string `json:"child_clarification"`
	ChildDenial           string `json:"child_denial"`
	ChildApprovalRequired string `json:"child_approval_required"`
	ChildError            string `json:"child_error"`
}

// AuditPolicy declares audit behavior for composed capabilities. v0.23.
type AuditPolicy struct {
	RecordChildInvocations bool `json:"record_child_invocations"`
	ParentTaskLineage      bool `json:"parent_task_lineage"`
}

// Composition is the declarative composition for kind=composed capabilities.
// v0.23. See SPEC.md §4.6.
type Composition struct {
	AuthorityBoundary  string                       `json:"authority_boundary"`
	Steps              []CompositionStep            `json:"steps"`
	InputMapping       map[string]map[string]string `json:"input_mapping"`
	OutputMapping      map[string]string            `json:"output_mapping"`
	EmptyResultPolicy  string                       `json:"empty_result_policy,omitempty"`
	EmptyResultOutput  map[string]any               `json:"empty_result_output,omitempty"`
	FailurePolicy      FailurePolicy                `json:"failure_policy"`
	AuditPolicy        AuditPolicy                  `json:"audit_policy"`
}

// --- Approval Grants ---

// GrantType classifies an approval grant. v0.23.
const (
	GrantTypeOneTime      = "one_time"
	GrantTypeSessionBound = "session_bound"
)

// ApprovalRequestStatus is the lifecycle status of an ApprovalRequest. v0.23.
const (
	ApprovalRequestStatusPending  = "pending"
	ApprovalRequestStatusApproved = "approved"
	ApprovalRequestStatusDenied   = "denied"
	ApprovalRequestStatusExpired  = "expired"
)

// GrantPolicy constrains what an approver MAY issue for a given approval
// request. v0.23. See SPEC.md §4.7.
type GrantPolicy struct {
	AllowedGrantTypes []string `json:"allowed_grant_types"`
	DefaultGrantType  string   `json:"default_grant_type"`
	ExpiresInSeconds  int      `json:"expires_in_seconds"`
	MaxUses           int      `json:"max_uses"`
}

// Validate enforces SPEC.md §4.7 invariants:
// default_grant_type MUST appear in allowed_grant_types.
// Returns a non-nil error when the policy is malformed; nil when valid.
// Callers (issuance helpers, schema validators) MUST invoke this before
// trusting the policy.
func (p GrantPolicy) Validate() error {
	if len(p.AllowedGrantTypes) == 0 {
		return &PolicyValidationError{Field: "allowed_grant_types", Reason: "must be non-empty"}
	}
	if p.DefaultGrantType == "" {
		return &PolicyValidationError{Field: "default_grant_type", Reason: "must be set"}
	}
	if !slices.Contains(p.AllowedGrantTypes, p.DefaultGrantType) {
		return &PolicyValidationError{
			Field:  "default_grant_type",
			Reason: "must appear in allowed_grant_types",
		}
	}
	return nil
}

// PolicyValidationError is returned by GrantPolicy.Validate. v0.23.
type PolicyValidationError struct {
	Field  string
	Reason string
}

func (e *PolicyValidationError) Error() string {
	return "GrantPolicy invalid: " + e.Field + ": " + e.Reason
}

// ApprovalRequiredMetadata is attached to an approval_required failure response.
// v0.23. See SPEC.md §4.7.
type ApprovalRequiredMetadata struct {
	ApprovalRequestID         string      `json:"approval_request_id"`
	PreviewDigest             string      `json:"preview_digest"`
	RequestedParametersDigest string      `json:"requested_parameters_digest"`
	GrantPolicy               GrantPolicy `json:"grant_policy"`
}

// ApprovalRequest is the persistent record of a request for human/principal
// approval. Created when a capability raises approval_required. v0.23.
type ApprovalRequest struct {
	ApprovalRequestID         string         `json:"approval_request_id"`
	Capability                string         `json:"capability"`
	Scope                     []string       `json:"scope"`
	Requester                 map[string]any `json:"requester"`
	ParentInvocationID        string         `json:"parent_invocation_id,omitempty"`
	Preview                   map[string]any `json:"preview"`
	PreviewDigest             string         `json:"preview_digest"`
	RequestedParameters       map[string]any `json:"requested_parameters"`
	RequestedParametersDigest string         `json:"requested_parameters_digest"`
	GrantPolicy               GrantPolicy    `json:"grant_policy"`
	Status                    string         `json:"status"`
	Approver                  map[string]any `json:"approver,omitempty"`
	DecidedAt                 string         `json:"decided_at,omitempty"`
	CreatedAt                 string         `json:"created_at"`
	ExpiresAt                 string         `json:"expires_at"`
}

// ApprovalGrant is a signed authorization object issued after approval. v0.23.
// See SPEC.md §4.8.
type ApprovalGrant struct {
	GrantID                   string         `json:"grant_id"`
	ApprovalRequestID         string         `json:"approval_request_id"`
	GrantType                 string         `json:"grant_type"`
	Capability                string         `json:"capability"`
	Scope                     []string       `json:"scope"`
	ApprovedParametersDigest  string         `json:"approved_parameters_digest"`
	PreviewDigest             string         `json:"preview_digest"`
	Requester                 map[string]any `json:"requester"`
	Approver                  map[string]any `json:"approver"`
	IssuedAt                  string         `json:"issued_at"`
	ExpiresAt                 string         `json:"expires_at"`
	MaxUses                   int            `json:"max_uses"`
	UseCount                  int            `json:"use_count"`
	SessionID                 string         `json:"session_id,omitempty"`
	Signature                 string         `json:"signature"`
}

// IssueApprovalGrantRequest is the body for POST {approval_grants}. v0.23.
type IssueApprovalGrantRequest struct {
	ApprovalRequestID string `json:"approval_request_id"`
	GrantType         string `json:"grant_type"`
	SessionID         string `json:"session_id,omitempty"`
	ExpiresInSeconds  int    `json:"expires_in_seconds,omitempty"`
	MaxUses           int    `json:"max_uses,omitempty"`
}

// IssueApprovalGrantResponse is the response body for POST {approval_grants}.
// SPEC.md §4.9: 200 response IS the signed ApprovalGrant — no wrapper.
// Aliased for parity with the request type. v0.23.
type IssueApprovalGrantResponse = ApprovalGrant
