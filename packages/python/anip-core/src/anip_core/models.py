"""ANIP protocol models — all Pydantic types for the ANIP protocol."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


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
    parent_token: str | None = None  # JWT string of parent (for child issuance)
    purpose_parameters: dict[str, Any] = Field(default_factory=dict)
    ttl_hours: int = 2
    caller_class: str | None = None


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


class ANIPFailure(BaseModel):
    type: str
    detail: str
    resolution: Resolution
    retry: bool = True


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
    protocol: str = "anip/0.17"
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
