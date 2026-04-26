package server

import "github.com/anip-protocol/anip/packages/go/core"

// AuditFilters specifies optional filters for querying audit entries.
type AuditFilters struct {
	Capability         string `json:"capability,omitempty"`
	RootPrincipal      string `json:"root_principal,omitempty"`
	Since              string `json:"since,omitempty"`
	InvocationID       string `json:"invocation_id,omitempty"`
	ClientReferenceID  string `json:"client_reference_id,omitempty"`
	TaskID             string `json:"task_id,omitempty"`
	ParentInvocationID string `json:"parent_invocation_id,omitempty"`
	EventClass         string `json:"event_class,omitempty"`
	ApprovalRequestID  string `json:"approval_request_id,omitempty"`
	ApprovalGrantID    string `json:"approval_grant_id,omitempty"`
	Limit              int    `json:"limit,omitempty"`
}

// ApprovalDecisionResult is the outcome of an atomic
// approve_request_and_store_grant operation. v0.23 §4.9 / Decision 0.9a.
//
// On success, OK is true and Grant carries the persisted grant.
// On failure, OK is false and Reason is one of:
//   - "approval_request_not_found"
//   - "approval_request_expired"
//   - "approval_request_already_decided"
type ApprovalDecisionResult struct {
	OK     bool
	Reason string
	Grant  *core.ApprovalGrant
}

// GrantReservationResult is the outcome of an atomic try_reserve_grant
// operation. v0.23 §4.8 Phase B. Reason on failure is one of:
//   - "grant_not_found"
//   - "grant_expired"
//   - "grant_consumed"
type GrantReservationResult struct {
	OK     bool
	Reason string
	Grant  *core.ApprovalGrant
}

// Storage is the abstract storage interface for ANIP server components.
type Storage interface {
	// Tokens
	StoreToken(token *core.DelegationToken) error
	LoadToken(tokenID string) (*core.DelegationToken, error)

	// Audit
	AppendAuditEntry(entry *core.AuditEntry) (*core.AuditEntry, error)
	QueryAuditEntries(filters AuditFilters) ([]core.AuditEntry, error)
	GetMaxAuditSequence() (int, error)
	GetAuditEntriesRange(first, last int) ([]core.AuditEntry, error)
	UpdateAuditSignature(seqNum int, signature string) error

	// Checkpoints
	StoreCheckpoint(cp *core.Checkpoint, signature string) error
	ListCheckpoints(limit int) ([]core.Checkpoint, error)
	GetCheckpointByID(id string) (*core.Checkpoint, error)

	// Retention
	DeleteExpiredAuditEntries(now string) (int, error)

	// Leases (for horizontal scaling coordination)
	TryAcquireExclusive(key, holder string, ttlSeconds int) (bool, error)
	ReleaseExclusive(key, holder string) error
	TryAcquireLeader(role, holder string, ttlSeconds int) (bool, error)
	ReleaseLeader(role, holder string) error

	// v0.23: Approval requests + grants. See SPEC.md §4.7 / §4.8 / §4.9.
	// StoreApprovalRequest is idempotent on approval_request_id when content
	// is identical; conflicting re-store with the same id returns an error.
	StoreApprovalRequest(req *core.ApprovalRequest) error
	GetApprovalRequest(id string) (*core.ApprovalRequest, error)
	// ApproveRequestAndStoreGrant is the atomic security boundary for
	// issuance: conditional UPDATE of the request to status=approved AND
	// INSERT of the grant inside one transaction.
	ApproveRequestAndStoreGrant(
		approvalRequestID string,
		grant *core.ApprovalGrant,
		approver map[string]any,
		decidedAtIso string,
		nowIso string,
	) (ApprovalDecisionResult, error)
	// StoreGrant is internal/test-only: persists a grant without going
	// through the atomic approval pathway. Tests use it to seed fixtures.
	StoreGrant(grant *core.ApprovalGrant) error
	GetGrant(grantID string) (*core.ApprovalGrant, error)
	// TryReserveGrant atomically increments use_count if the grant is still
	// usable; returns the updated grant on success.
	TryReserveGrant(grantID string, nowIso string) (GrantReservationResult, error)

	// Close releases storage resources.
	Close() error
}
