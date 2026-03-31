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
	Limit              int    `json:"limit,omitempty"`
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

	// Close releases storage resources.
	Close() error
}
