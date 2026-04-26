"""ANIP protocol models — all Pydantic types for the ANIP protocol."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# --- Side-effect Typing ---


class SideEffectType(str, Enum):
    READ = "read"
    WRITE = "write"
    IRREVERSIBLE = "irreversible"
    TRANSACTIONAL = "transactional"


class ResponseMode(str, Enum):
    UNARY = "unary"
    STREAMING = "streaming"


class SideEffect(BaseModel):
    type: SideEffectType
    rollback_window: str | None = None  # ISO 8601 duration or "none" or "not_applicable"


# --- Delegation Chain ---


class Purpose(BaseModel):
    capability: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    task_id: str | None = None


class ConcurrentBranches(str, Enum):
    ALLOWED = "allowed"
    EXCLUSIVE = "exclusive"


class Budget(BaseModel):
    currency: str
    max_amount: float


class DelegationConstraints(BaseModel):
    max_delegation_depth: int = 3
    concurrent_branches: ConcurrentBranches = ConcurrentBranches.ALLOWED
    budget: Budget | None = None


class DelegationToken(BaseModel):
    token_id: str
    issuer: str
    subject: str
    scope: list[str]
    purpose: Purpose
    parent: str | None = None  # None for root tokens (issued by humans)
    expires: datetime
    constraints: DelegationConstraints = Field(default_factory=DelegationConstraints)
    root_principal: str | None = None  # The human at the root of the delegation chain
    caller_class: str | None = None  # Issuer-supplied caller classification


class TokenRequest(BaseModel):
    """Client request for token issuance. Server controls signing and metadata."""
    subject: str
    scope: list[str]
    capability: str
    parent_token: str | None = None  # Token ID string of the parent token (not a JWT). The service looks up the parent by ID in storage.
    purpose_parameters: dict[str, Any] = Field(default_factory=dict)
    ttl_hours: int = 2
    caller_class: str | None = None
    concurrent_branches: ConcurrentBranches | None = None


# --- Cross-Service Handoff ---


class ServiceCapabilityRef(BaseModel):
    service: str
    capability: str


class CrossServiceHints(BaseModel):
    handoff_to: list[ServiceCapabilityRef] = Field(default_factory=list)
    refresh_via: list[ServiceCapabilityRef] = Field(default_factory=list)
    verify_via: list[ServiceCapabilityRef] = Field(default_factory=list)
    followup_via: list[ServiceCapabilityRef] = Field(default_factory=list)


# --- Cross-Service Contract (v0.21) ---


class CrossServiceContractEntry(BaseModel):
    target: ServiceCapabilityRef
    required_for_task_completion: bool = False
    continuity: Literal["same_task"] = "same_task"
    completion_mode: Literal[
        "downstream_acceptance", "followup_status", "verification_result"
    ]


class CrossServiceContract(BaseModel):
    handoff: list[CrossServiceContractEntry] = Field(default_factory=list)
    followup: list[CrossServiceContractEntry] = Field(default_factory=list)
    verification: list[CrossServiceContractEntry] = Field(default_factory=list)


# --- Recovery Target (v0.21) ---


class RecoveryTarget(BaseModel):
    kind: Literal["refresh", "redelegation", "revalidation", "escalation"]
    target: ServiceCapabilityRef | None = None
    continuity: Literal["same_task"] = "same_task"
    retry_after_target: bool = False


# --- Capability Declaration ---


class CapabilityInput(BaseModel):
    name: str
    type: str
    required: bool = True
    default: Any = None
    description: str = ""


class CapabilityOutput(BaseModel):
    type: str
    fields: list[str]


class CostCertainty(str, Enum):
    FIXED = "fixed"
    ESTIMATED = "estimated"
    DYNAMIC = "dynamic"


class FinancialCost(BaseModel):
    currency: str
    amount: float | None = None        # for fixed costs
    range_min: float | None = None     # for estimated costs
    range_max: float | None = None     # for estimated costs
    typical: float | None = None       # for estimated costs
    upper_bound: float | None = None   # for dynamic costs


class Cost(BaseModel):
    certainty: CostCertainty = CostCertainty.FIXED
    financial: FinancialCost | None = None
    determined_by: str | None = None  # capability that resolves actual cost (for estimated)
    factors: list[str] | None = None  # what drives cost variation (for dynamic)
    compute: dict[str, Any] | None = None
    rate_limit: dict[str, Any] | None = None


class CostActual(BaseModel):
    financial: FinancialCost
    variance_from_estimate: str | None = None


class CapabilityRequirement(BaseModel):
    capability: str
    reason: str


class CapabilityComposition(BaseModel):
    capability: str
    optional: bool = True


class SessionType(str, Enum):
    STATELESS = "stateless"
    CONTINUATION = "continuation"
    WORKFLOW = "workflow"


class SessionInfo(BaseModel):
    type: SessionType = SessionType.STATELESS


class ObservabilityContract(BaseModel):
    logged: bool = True
    retention: str = "P90D"
    fields_logged: list[str] = Field(default_factory=list)
    audit_accessible_by: list[str] = Field(default_factory=list)


class BindingRequirement(BaseModel):
    type: str  # "quote", "offer", "price_lock"
    field: str  # which param must carry the reference
    source_capability: str | None = None  # advisory
    max_age: str | None = None  # ISO 8601 duration, e.g. "PT15M"


class ControlRequirement(BaseModel):
    type: str  # "cost_ceiling", "stronger_delegation_required"
    enforcement: str = "reject"  # "reject" only; "warn" deferred to future slice


# --- v0.23: Capability Composition ---


CapabilityKind = Literal["atomic", "composed"]
AuthorityBoundary = Literal["same_service", "same_package", "external_service"]
EmptyResultPolicy = Literal["return_success_no_results", "clarify", "deny"]
FailurePolicyOutcome = Literal["propagate", "fail_parent"]


class CompositionStep(BaseModel):
    """One step in a composed capability. v0.23. See SPEC.md §4.6."""
    id: str
    capability: str
    empty_result_source: bool = False
    empty_result_path: str | None = None


class FailurePolicy(BaseModel):
    """Per-child-outcome failure handling. v0.23. See SPEC.md §4.6."""
    child_clarification: FailurePolicyOutcome = "propagate"
    child_denial: FailurePolicyOutcome = "propagate"
    child_approval_required: FailurePolicyOutcome = "propagate"
    child_error: FailurePolicyOutcome = "fail_parent"


class AuditPolicy(BaseModel):
    """Audit behavior for composed capabilities. v0.23. See SPEC.md §4.6."""
    record_child_invocations: bool
    parent_task_lineage: bool


class Composition(BaseModel):
    """Declarative composition for kind=composed capabilities. v0.23. See SPEC.md §4.6."""
    authority_boundary: AuthorityBoundary
    steps: list[CompositionStep]
    input_mapping: dict[str, dict[str, str]]
    output_mapping: dict[str, str]
    empty_result_policy: EmptyResultPolicy | None = None
    empty_result_output: dict[str, Any] | None = None
    failure_policy: FailurePolicy
    audit_policy: AuditPolicy


# --- v0.23: Approval Grants ---


GrantType = Literal["one_time", "session_bound"]
ApprovalRequestStatus = Literal["pending", "approved", "denied", "expired"]


class GrantPolicy(BaseModel):
    """Constrains what an approver MAY issue for a given request. v0.23. See SPEC.md §4.7."""
    allowed_grant_types: list[GrantType]
    default_grant_type: GrantType
    expires_in_seconds: int
    max_uses: int


class ApprovalRequiredMetadata(BaseModel):
    """Metadata attached to an approval_required failure. v0.23. See SPEC.md §4.7."""
    approval_request_id: str
    preview_digest: str
    requested_parameters_digest: str
    grant_policy: GrantPolicy


class ApprovalRequest(BaseModel):
    """Persistent record of a request for human/principal approval. v0.23. See SPEC.md §4.7."""
    approval_request_id: str
    capability: str
    scope: list[str]
    requester: dict[str, Any]
    parent_invocation_id: str | None = None
    preview: dict[str, Any]
    preview_digest: str
    requested_parameters: dict[str, Any]
    requested_parameters_digest: str
    grant_policy: GrantPolicy
    status: ApprovalRequestStatus
    approver: dict[str, Any] | None = None
    decided_at: str | None = None
    created_at: str
    expires_at: str

    @model_validator(mode="after")
    def _validate_status_invariants(self) -> "ApprovalRequest":
        # SPEC.md §4.7: pending -> no approver, no decided_at;
        # approved/denied -> both required; expired -> decided_at required, approver null.
        status = self.status
        if status == "pending":
            if self.approver is not None or self.decided_at is not None:
                raise ValueError("pending requests must have approver=None and decided_at=None")
        elif status in ("approved", "denied"):
            if self.approver is None or self.decided_at is None:
                raise ValueError(f"{status} requests require approver and decided_at")
        elif status == "expired":
            if self.approver is not None:
                raise ValueError("expired requests must have approver=None (time-driven, no human decided)")
            if self.decided_at is None:
                raise ValueError("expired requests must have decided_at set")
        return self


class ApprovalGrant(BaseModel):
    """Signed authorization object issued after approval. v0.23. See SPEC.md §4.8."""
    grant_id: str
    approval_request_id: str
    grant_type: GrantType
    capability: str
    scope: list[str]
    approved_parameters_digest: str
    preview_digest: str
    requester: dict[str, Any]
    approver: dict[str, Any]
    issued_at: str
    expires_at: str
    max_uses: int
    use_count: int = 0
    session_id: str | None = None
    signature: str

    @model_validator(mode="after")
    def _validate_grant_type_invariants(self) -> "ApprovalGrant":
        # SPEC.md §4.8: one_time -> max_uses=1, session_id=None;
        # session_bound -> session_id required (non-null).
        if self.grant_type == "one_time":
            if self.max_uses != 1:
                raise ValueError("one_time grants must have max_uses=1")
            if self.session_id is not None:
                raise ValueError("one_time grants must have session_id=None")
        elif self.grant_type == "session_bound":
            if not self.session_id:
                raise ValueError("session_bound grants require a non-empty session_id")
        return self


class IssueApprovalGrantRequest(BaseModel):
    """Request body for POST {approval_grants}. v0.23. See SPEC.md §4.9."""
    approval_request_id: str
    grant_type: GrantType
    session_id: str | None = None
    expires_in_seconds: int | None = None
    max_uses: int | None = None

    @model_validator(mode="after")
    def _validate_grant_type_invariants(self) -> "IssueApprovalGrantRequest":
        # SPEC.md §4.9: session_id required iff session_bound.
        if self.grant_type == "session_bound":
            if not self.session_id:
                raise ValueError("session_bound grant issuance requires a non-empty session_id")
        elif self.grant_type == "one_time":
            if self.session_id is not None:
                raise ValueError("one_time grant issuance must not carry session_id")
            if self.max_uses is not None and self.max_uses != 1:
                raise ValueError("one_time grant issuance max_uses must be 1 or omitted")
        return self


class IssueApprovalGrantResponse(BaseModel):
    """Response body for POST {approval_grants}. v0.23. See SPEC.md §4.9."""
    grant: ApprovalGrant


class CapabilityDeclaration(BaseModel):
    name: str
    description: str
    contract_version: str = "1.0"
    inputs: list[CapabilityInput]
    output: CapabilityOutput
    side_effect: SideEffect
    minimum_scope: list[str]  # delegation scopes needed to invoke this (AND semantics)
    cost: Cost | None = None
    requires: list[CapabilityRequirement] = Field(default_factory=list)
    composes_with: list[CapabilityComposition] = Field(default_factory=list)
    session: SessionInfo = Field(default_factory=SessionInfo)
    observability: ObservabilityContract | None = None
    response_modes: list[ResponseMode] = Field(default_factory=lambda: [ResponseMode.UNARY])
    requires_binding: list[BindingRequirement] = Field(default_factory=list)
    control_requirements: list[ControlRequirement] = Field(default_factory=list)
    refresh_via: list[str] = Field(default_factory=list)
    verify_via: list[str] = Field(default_factory=list)
    cross_service: CrossServiceHints | None = None
    cross_service_contract: CrossServiceContract | None = None
    # v0.23
    kind: CapabilityKind = "atomic"
    composition: Composition | None = None
    grant_policy: GrantPolicy | None = None

    @model_validator(mode="after")
    def _validate_kind_composition(self) -> "CapabilityDeclaration":
        # SPEC.md §4.1, §4.6: composed requires composition; atomic forbids it.
        # The third rule catches the omitted-kind case (defaulting to atomic):
        # composition non-null implies kind must be "composed".
        if self.kind == "composed" and self.composition is None:
            raise ValueError("kind='composed' requires composition")
        if self.kind == "atomic" and self.composition is not None:
            raise ValueError("kind='atomic' must not carry composition")
        return self


# --- Permission Discovery ---


class AvailableCapability(BaseModel):
    capability: str
    scope_match: str
    constraints: dict[str, Any] = Field(default_factory=dict)


class RestrictedCapability(BaseModel):
    capability: str
    reason: str
    reason_type: str
    grantable_by: str
    unmet_token_requirements: list[str] = Field(default_factory=list)
    resolution_hint: str | None = None


class DeniedCapability(BaseModel):
    capability: str
    reason: str
    reason_type: str


class PermissionResponse(BaseModel):
    available: list[AvailableCapability] = Field(default_factory=list)
    restricted: list[RestrictedCapability] = Field(default_factory=list)
    denied: list[DeniedCapability] = Field(default_factory=list)


# --- Failure Semantics ---


class Resolution(BaseModel):
    action: str
    recovery_class: str
    requires: str | None = None
    grantable_by: str | None = None
    estimated_availability: str | None = None
    recovery_target: RecoveryTarget | None = None


class ANIPFailure(BaseModel):
    type: str
    detail: str
    resolution: Resolution
    retry: bool = True
    approval_required: ApprovalRequiredMetadata | None = None  # v0.23, present iff type='approval_required'

    @model_validator(mode="after")
    def _validate_approval_required_metadata(self) -> "ANIPFailure":
        # SPEC.md §4.7: approval_required metadata is present iff type='approval_required'.
        if self.type == "approval_required":
            if self.approval_required is None:
                raise ValueError("type='approval_required' failures require approval_required metadata")
        else:
            if self.approval_required is not None:
                raise ValueError(
                    "approval_required metadata may only be set when type='approval_required'"
                )
        return self


# --- Manifest ---


class ProfileVersions(BaseModel):
    core: str = "1.0"
    cost: str | None = None
    capability_graph: str | None = None
    state_session: str | None = None
    observability: str | None = None


class ManifestMetadata(BaseModel):
    version: str = "0.10.0"
    sha256: str = ""  # Set at build time
    issued_at: str = ""  # Set at build time
    expires_at: str = ""  # Set at build time


class ServiceIdentity(BaseModel):
    id: str = "anip-flight-service"
    jwks_uri: str = "/.well-known/jwks.json"
    issuer_mode: str = "first-party"


# --- v0.3 Trust ---


class AnchoringPolicy(BaseModel):
    cadence: str | None = None
    max_lag: int | None = None
    sink: list[str] | None = None


class TrustPolicyTrigger(BaseModel):
    trigger: dict[str, Any]
    action: str


class TrustPosture(BaseModel):
    level: str = "signed"
    anchoring: AnchoringPolicy | None = None
    policies: list[TrustPolicyTrigger] | None = None


# --- Security Hardening Enums (v0.8) ---


class EventClass(str, Enum):
    HIGH_RISK_SUCCESS = "high_risk_success"
    HIGH_RISK_DENIAL = "high_risk_denial"
    LOW_RISK_SUCCESS = "low_risk_success"
    REPEATED_LOW_VALUE_DENIAL = "repeated_low_value_denial"
    MALFORMED_OR_SPAM = "malformed_or_spam"


class RetentionTier(str, Enum):
    LONG = "long"
    MEDIUM = "medium"
    SHORT = "short"
    AGGREGATE_ONLY = "aggregate_only"


class DisclosureLevel(str, Enum):
    FULL = "full"
    REDUCED = "reduced"
    REDACTED = "redacted"
    POLICY = "policy"


# --- Discovery Posture (v0.7) ---


class AuditPosture(BaseModel):
    enabled: bool = True
    signed: bool = True
    queryable: bool = True
    retention: str = "P90D"
    retention_enforced: bool = False


class ClientReferenceIdPosture(BaseModel):
    supported: bool = True
    max_length: int = 256
    opaque: bool = True
    propagation: Literal["bounded", "local_only", "policy"] = "bounded"


class LineagePosture(BaseModel):
    invocation_id: bool = True
    client_reference_id: ClientReferenceIdPosture = Field(default_factory=ClientReferenceIdPosture)


class MetadataPolicy(BaseModel):
    bounded_lineage: bool = True
    freeform_context: bool = False
    downstream_propagation: Literal["minimal", "policy", "service_defined"] = "minimal"


class FailureDisclosure(BaseModel):
    detail_level: Literal["full", "reduced", "redacted", "policy"] = "redacted"
    caller_classes: list[str] | None = None


class AnchoringPosture(BaseModel):
    enabled: bool = False
    cadence: str | None = None
    max_lag: int | None = None
    proofs_available: bool = False


class DiscoveryPosture(BaseModel):
    audit: AuditPosture = Field(default_factory=AuditPosture)
    lineage: LineagePosture = Field(default_factory=LineagePosture)
    metadata_policy: MetadataPolicy = Field(default_factory=MetadataPolicy)
    failure_disclosure: FailureDisclosure = Field(default_factory=FailureDisclosure)
    anchoring: AnchoringPosture = Field(default_factory=AnchoringPosture)


class ANIPManifest(BaseModel):
    protocol: str = "anip/0.22"
    profile: ProfileVersions
    capabilities: dict[str, CapabilityDeclaration]
    manifest_metadata: ManifestMetadata | None = None
    service_identity: ServiceIdentity | None = None
    trust: TrustPosture | None = None


# --- Invocation ---


class TokenPresentation(BaseModel):
    """JWT token presentation for v0.2 protected endpoints."""
    token: str  # JWT string


class InvokeRequest(BaseModel):
    """Invocation request with JWT token."""
    token: str  # JWT string
    parameters: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] | None = None
    client_reference_id: str | None = Field(default=None, max_length=256)
    task_id: str | None = Field(default=None, max_length=256)
    parent_invocation_id: str | None = Field(default=None, pattern=r"^inv-[0-9a-f]{12}$")
    stream: bool = False
    approval_grant: str | None = None  # v0.23: grant_id supplied on continuation invocations


class StreamSummary(BaseModel):
    """Runtime-managed metadata for streaming invocations."""
    response_mode: str = "streaming"
    events_emitted: int
    events_delivered: int
    duration_ms: int
    client_disconnected: bool


class InvokeResponse(BaseModel):
    success: bool
    invocation_id: str = Field(pattern=r"^inv-[0-9a-f]{12}$")
    client_reference_id: str | None = None
    task_id: str | None = None
    parent_invocation_id: str | None = None
    result: dict[str, Any] | None = None
    cost_actual: CostActual | None = None
    failure: ANIPFailure | None = None
    session: dict[str, Any] | None = None
    stream_summary: StreamSummary | None = None


# --- Checkpoint ---


class CheckpointBody(BaseModel):
    version: str = "1.0"
    service_id: str
    checkpoint_id: str
    range: dict[str, int]  # {first_sequence, last_sequence}
    merkle_root: str
    previous_checkpoint: str | None = None
    timestamp: str
    entry_count: int


class CheckpointDetailResponse(BaseModel):
    """Response wrapper for checkpoint detail endpoint. Separate from the signed CheckpointBody."""
    checkpoint: dict[str, Any]
    inclusion_proof: dict[str, Any] | None = None
    consistency_proof: dict[str, Any] | None = None
    proof_unavailable: str | None = None
    expires_hint: str | None = None  # best-effort, informational, not part of signed body
