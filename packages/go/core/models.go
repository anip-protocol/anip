package core

// --- Financial Cost ---

// FinancialCost describes the financial cost of a capability invocation.
type FinancialCost struct {
	Currency   string   `json:"currency"`
	Amount     *float64 `json:"amount,omitempty"`
	RangeMin   *float64 `json:"range_min,omitempty"`
	RangeMax   *float64 `json:"range_max,omitempty"`
	Typical    *float64 `json:"typical,omitempty"`
	UpperBound *float64 `json:"upper_bound,omitempty"`
}

// --- Budget ---

// Budget constrains the maximum spend for a delegation token or invocation.
type Budget struct {
	Currency  string  `json:"currency"`
	MaxAmount float64 `json:"max_amount"`
}

// BudgetContext provides budget evaluation details in invocation responses.
type BudgetContext struct {
	BudgetMax       float64  `json:"budget_max"`
	BudgetCurrency  string   `json:"budget_currency"`
	CostCheckAmount *float64 `json:"cost_check_amount,omitempty"`
	CostCertainty   string   `json:"cost_certainty,omitempty"`
	CostActual      *float64 `json:"cost_actual,omitempty"`
	WithinBudget    bool     `json:"within_budget"`
}

// --- Binding and Control Requirements ---

// BindingRequirement declares that a capability requires a bound value.
type BindingRequirement struct {
	Type             string `json:"type"`
	Field            string `json:"field"`
	SourceCapability string `json:"source_capability,omitempty"`
	MaxAge           string `json:"max_age,omitempty"`
}

// ControlRequirement declares a control that must be satisfied before invocation.
type ControlRequirement struct {
	Type        string `json:"type"`
	Enforcement string `json:"enforcement"`
}

// --- Side-effect Typing ---

// SideEffect describes the side-effect characteristics of a capability.
type SideEffect struct {
	Type           string `json:"type"`                      // "read", "write", "irreversible", "transactional"
	RollbackWindow string `json:"rollback_window,omitempty"` // ISO 8601 duration, "none", or "not_applicable"
}

// --- Capability Declaration ---

// CapabilityInput describes a single input parameter for a capability.
type CapabilityInput struct {
	Name        string `json:"name"`
	Type        string `json:"type"`
	Required    bool   `json:"required"`
	Default     any    `json:"default,omitempty"`
	Description string `json:"description,omitempty"`
}

// CapabilityOutput describes the output of a capability.
type CapabilityOutput struct {
	Type   string   `json:"type"`
	Fields []string `json:"fields"`
}

// Cost describes the cost characteristics of a capability.
type Cost struct {
	Certainty    string         `json:"certainty"`              // "fixed", "estimated", "dynamic"
	Financial    *FinancialCost `json:"financial,omitempty"`
	DeterminedBy string         `json:"determined_by,omitempty"` // capability that resolves actual cost
	Factors      []string       `json:"factors,omitempty"`       // what drives cost variation (for dynamic)
	Compute      map[string]any `json:"compute,omitempty"`
	RateLimit    map[string]any `json:"rate_limit,omitempty"`
}

// CostActual is the actual cost incurred by an invocation.
type CostActual struct {
	Financial            *FinancialCost `json:"financial"`
	VarianceFromEstimate string         `json:"variance_from_estimate,omitempty"`
}

// CapabilityRequirement describes a capability that must be invoked first.
type CapabilityRequirement struct {
	Capability string `json:"capability"`
	Reason     string `json:"reason"`
}

// CapabilityComposition describes a capability that can be composed with.
type CapabilityComposition struct {
	Capability string `json:"capability"`
	Optional   bool   `json:"optional"`
}

// SessionInfo describes session behavior for a capability.
type SessionInfo struct {
	Type string `json:"type"` // "stateless", "continuation", "workflow"
}

// ObservabilityContract describes the observability guarantees.
type ObservabilityContract struct {
	Logged            bool     `json:"logged"`
	Retention         string   `json:"retention"`
	FieldsLogged      []string `json:"fields_logged"`
	AuditAccessibleBy []string `json:"audit_accessible_by"`
}

// CapabilityDeclaration is the full declaration of a service capability.
type CapabilityDeclaration struct {
	Name                string                  `json:"name"`
	Description         string                  `json:"description"`
	ContractVersion     string                  `json:"contract_version"`
	Inputs              []CapabilityInput       `json:"inputs"`
	Output              CapabilityOutput        `json:"output"`
	SideEffect          SideEffect              `json:"side_effect"`
	MinimumScope        []string                `json:"minimum_scope"`
	Cost                *Cost                   `json:"cost,omitempty"`
	Requires            []CapabilityRequirement `json:"requires,omitempty"`
	ComposesWith        []CapabilityComposition `json:"composes_with,omitempty"`
	Session             *SessionInfo            `json:"session,omitempty"`
	Observability       *ObservabilityContract  `json:"observability,omitempty"`
	ResponseModes       []string                `json:"response_modes,omitempty"`
	RequiresBinding     []BindingRequirement    `json:"requires_binding,omitempty"`
	ControlRequirements []ControlRequirement    `json:"control_requirements,omitempty"`
	RefreshVia          []string                `json:"refresh_via,omitempty"`
	VerifyVia           []string                `json:"verify_via,omitempty"`
}

// --- Delegation Chain ---

// Purpose describes the intended use of a delegation token.
type Purpose struct {
	Capability string         `json:"capability"`
	Parameters map[string]any `json:"parameters"`
	TaskID     string         `json:"task_id,omitempty"`
}

// DelegationConstraints constrains how delegation tokens can be sub-delegated.
type DelegationConstraints struct {
	MaxDelegationDepth int     `json:"max_delegation_depth"`
	ConcurrentBranches string  `json:"concurrent_branches"` // "allowed" or "exclusive"
	Budget             *Budget `json:"budget,omitempty"`
}

// DelegationToken is a stored delegation token record.
type DelegationToken struct {
	TokenID       string                `json:"token_id"`
	Issuer        string                `json:"issuer"`
	Subject       string                `json:"subject"`
	Scope         []string              `json:"scope"`
	Purpose       Purpose               `json:"purpose"`
	Parent        string                `json:"parent,omitempty"` // empty for root tokens
	Expires       string                `json:"expires"`
	Constraints   DelegationConstraints `json:"constraints"`
	RootPrincipal string                `json:"root_principal,omitempty"`
	CallerClass   string                `json:"caller_class,omitempty"`
}

// TokenRequest is the client's request body for token issuance.
type TokenRequest struct {
	Subject           string         `json:"subject"`
	Scope             []string       `json:"scope"`
	Capability        string         `json:"capability"`
	ParentToken       string         `json:"parent_token,omitempty"` // JWT string of parent
	PurposeParameters map[string]any `json:"purpose_parameters,omitempty"`
	TTLHours          int            `json:"ttl_hours,omitempty"`
	CallerClass       string         `json:"caller_class,omitempty"`
	Budget            *Budget        `json:"budget,omitempty"`
}

// TokenResponse is the server's response to token issuance.
type TokenResponse struct {
	Issued  bool    `json:"issued"`
	TokenID string  `json:"token_id"`
	Token   string  `json:"token"` // JWT string
	Expires string  `json:"expires"`
	Budget  *Budget `json:"budget,omitempty"` // Echoed when budget was requested
}

// --- Permission Discovery ---

// AvailableCapability describes a capability the token can invoke.
type AvailableCapability struct {
	Capability string         `json:"capability"`
	ScopeMatch string         `json:"scope_match"`
	Constraints map[string]any `json:"constraints"`
}

// RestrictedCapability describes a capability the token lacks scope for.
type RestrictedCapability struct {
	Capability             string   `json:"capability"`
	Reason                 string   `json:"reason"`
	ReasonType             string   `json:"reason_type"`
	GrantableBy            string   `json:"grantable_by"`
	UnmetTokenRequirements []string `json:"unmet_token_requirements,omitempty"`
	ResolutionHint         string   `json:"resolution_hint,omitempty"`
}

// DeniedCapability describes a capability that cannot be granted.
type DeniedCapability struct {
	Capability string `json:"capability"`
	Reason     string `json:"reason"`
	ReasonType string `json:"reason_type"`
}

// PermissionResponse is the response from the permissions endpoint.
type PermissionResponse struct {
	Available  []AvailableCapability  `json:"available"`
	Restricted []RestrictedCapability `json:"restricted"`
	Denied     []DeniedCapability     `json:"denied"`
}

// --- Invocation ---

// InvokeRequest is the client's invocation request body.
type InvokeRequest struct {
	Token              string         `json:"token"` // JWT string
	Parameters         map[string]any `json:"parameters"`
	Budget             map[string]any `json:"budget,omitempty"`
	ClientReferenceID  string         `json:"client_reference_id,omitempty"`
	TaskID             string         `json:"task_id,omitempty"`
	ParentInvocationID string         `json:"parent_invocation_id,omitempty"`
	Stream             bool           `json:"stream,omitempty"`
}

// InvokeResponse is the server's invocation response.
type InvokeResponse struct {
	Success            bool           `json:"success"`
	InvocationID       string         `json:"invocation_id"`
	ClientReferenceID  string         `json:"client_reference_id,omitempty"`
	TaskID             string         `json:"task_id,omitempty"`
	ParentInvocationID string         `json:"parent_invocation_id,omitempty"`
	Result             any            `json:"result,omitempty"`
	CostActual         *CostActual    `json:"cost_actual,omitempty"`
	Failure            *ANIPError     `json:"failure,omitempty"`
	BudgetContext      *BudgetContext `json:"budget_context,omitempty"`
}

// --- Audit ---

// AuditEntry is a single audit log record.
type AuditEntry struct {
	SequenceNumber      int            `json:"sequence_number"`
	Timestamp           string         `json:"timestamp"`
	Capability          string         `json:"capability"`
	TokenID             string         `json:"token_id,omitempty"`
	Issuer              string         `json:"issuer,omitempty"`
	Subject             string         `json:"subject,omitempty"`
	RootPrincipal       string         `json:"root_principal,omitempty"`
	Parameters          map[string]any `json:"parameters,omitempty"`
	Success             bool           `json:"success"`
	ResultSummary       map[string]any `json:"result_summary,omitempty"`
	FailureType         string         `json:"failure_type,omitempty"`
	CostActual          *CostActual    `json:"cost_actual,omitempty"`
	DelegationChain     []string       `json:"delegation_chain,omitempty"`
	InvocationID        string         `json:"invocation_id,omitempty"`
	ClientReferenceID   string         `json:"client_reference_id,omitempty"`
	TaskID              string         `json:"task_id,omitempty"`
	ParentInvocationID  string         `json:"parent_invocation_id,omitempty"`
	PreviousHash        string         `json:"previous_hash,omitempty"`
	Signature           string         `json:"signature,omitempty"`
	EventClass          string         `json:"event_class,omitempty"`
	RetentionTier       string         `json:"retention_tier,omitempty"`
	ExpiresAt           string         `json:"expires_at,omitempty"`
	StorageRedacted     bool           `json:"storage_redacted,omitempty"`
	EntryType            string            `json:"entry_type,omitempty"`
	GroupingKey          map[string]string `json:"grouping_key,omitempty"`
	AggregationWindow    map[string]string `json:"aggregation_window,omitempty"`
	AggregationCount     int               `json:"aggregation_count,omitempty"`
	FirstSeen            string            `json:"first_seen,omitempty"`
	LastSeen             string            `json:"last_seen,omitempty"`
	RepresentativeDetail string            `json:"representative_detail,omitempty"`
	StreamSummary        map[string]any    `json:"stream_summary,omitempty"`
}

// AuditResponse wraps audit query results.
type AuditResponse struct {
	Entries          []AuditEntry `json:"entries"`
	Count            int          `json:"count"`
	RootPrincipal    string       `json:"root_principal,omitempty"`
	CapabilityFilter *string      `json:"capability_filter"`
	SinceFilter      *string      `json:"since_filter"`
}

// --- Checkpoints ---

// Checkpoint is a Merkle checkpoint over a range of audit entries.
type Checkpoint struct {
	Version            string         `json:"version"`
	ServiceID          string         `json:"service_id"`
	CheckpointID       string         `json:"checkpoint_id"`
	Range              map[string]int `json:"range"` // {first_sequence, last_sequence}
	MerkleRoot         string         `json:"merkle_root"`
	PreviousCheckpoint string         `json:"previous_checkpoint,omitempty"`
	Timestamp          string         `json:"timestamp"`
	EntryCount         int            `json:"entry_count"`
}

// CheckpointListResponse is the response from the checkpoint list endpoint.
type CheckpointListResponse struct {
	Checkpoints []Checkpoint `json:"checkpoints"`
	NextCursor  string       `json:"next_cursor,omitempty"`
}

// CheckpointDetailResponse is the response from the checkpoint detail endpoint.
type CheckpointDetailResponse struct {
	Checkpoint       map[string]any `json:"checkpoint"`
	InclusionProof   map[string]any `json:"inclusion_proof,omitempty"`
	ConsistencyProof map[string]any `json:"consistency_proof,omitempty"`
	ProofUnavailable string         `json:"proof_unavailable,omitempty"`
	ExpiresHint      string         `json:"expires_hint,omitempty"`
}

// --- Manifest ---

// ProfileVersions describes the profile versions supported by the service.
type ProfileVersions struct {
	Core             string `json:"core"`
	Cost             string `json:"cost,omitempty"`
	CapabilityGraph  string `json:"capability_graph,omitempty"`
	StateSession     string `json:"state_session,omitempty"`
	Observability    string `json:"observability,omitempty"`
}

// ManifestMetadata describes metadata about the manifest document.
type ManifestMetadata struct {
	Version  string `json:"version"`
	SHA256   string `json:"sha256"`
	IssuedAt string `json:"issued_at"`
	ExpiresAt string `json:"expires_at"`
}

// ServiceIdentity describes the service's identity for token verification.
type ServiceIdentity struct {
	ID         string `json:"id"`
	JWKSURI    string `json:"jwks_uri"`
	IssuerMode string `json:"issuer_mode"`
}

// TrustPosture describes the service's trust level.
type TrustPosture struct {
	Level     string         `json:"level"` // "signed" or "anchored"
	Anchoring map[string]any `json:"anchoring,omitempty"`
	Policies  []any          `json:"policies,omitempty"`
}

// AuditPosture describes audit behavior in the discovery document.
type AuditPosture struct {
	Enabled           bool   `json:"enabled"`
	Signed            bool   `json:"signed"`
	Queryable         bool   `json:"queryable"`
	Retention         string `json:"retention"`
	RetentionEnforced bool   `json:"retention_enforced"`
}

// ClientReferenceIDPosture describes client_reference_id support.
type ClientReferenceIDPosture struct {
	Supported   bool   `json:"supported"`
	MaxLength   int    `json:"max_length"`
	Opaque      bool   `json:"opaque"`
	Propagation string `json:"propagation"`
}

// LineagePosture describes lineage tracking support.
type LineagePosture struct {
	InvocationID      bool                     `json:"invocation_id"`
	ClientReferenceID ClientReferenceIDPosture `json:"client_reference_id"`
}

// MetadataPolicy describes metadata propagation policy.
type MetadataPolicy struct {
	BoundedLineage        bool   `json:"bounded_lineage"`
	FreeformContext       bool   `json:"freeform_context"`
	DownstreamPropagation string `json:"downstream_propagation"`
}

// FailureDisclosure describes failure detail disclosure policy.
type FailureDisclosure struct {
	DetailLevel  string   `json:"detail_level"`
	CallerClasses []string `json:"caller_classes,omitempty"`
}

// AnchoringPosture describes anchoring support in discovery.
type AnchoringPosture struct {
	Enabled         bool   `json:"enabled"`
	Cadence         string `json:"cadence,omitempty"`
	MaxLag          int    `json:"max_lag,omitempty"`
	ProofsAvailable bool   `json:"proofs_available"`
}

// DiscoveryPosture describes the service's operational posture.
type DiscoveryPosture struct {
	Audit             AuditPosture      `json:"audit"`
	Lineage           LineagePosture    `json:"lineage"`
	MetadataPolicy    MetadataPolicy    `json:"metadata_policy"`
	FailureDisclosure FailureDisclosure `json:"failure_disclosure"`
	Anchoring         AnchoringPosture  `json:"anchoring"`
}

// ANIPManifest is the full service manifest.
type ANIPManifest struct {
	Protocol         string                            `json:"protocol"`
	Profile          ProfileVersions                   `json:"profile"`
	Capabilities     map[string]CapabilityDeclaration  `json:"capabilities"`
	ManifestMetadata *ManifestMetadata                 `json:"manifest_metadata,omitempty"`
	ServiceIdentity  *ServiceIdentity                  `json:"service_identity,omitempty"`
	Trust            *TrustPosture                     `json:"trust,omitempty"`
}
