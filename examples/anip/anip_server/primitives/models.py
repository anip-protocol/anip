"""ANIP primitive types — the core data structures of the protocol."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Side-effect Typing ---


class SideEffectType(str, Enum):
    READ = "read"
    WRITE = "write"
    IRREVERSIBLE = "irreversible"
    TRANSACTIONAL = "transactional"


class SideEffect(BaseModel):
    type: SideEffectType
    rollback_window: str | None = None  # ISO 8601 duration or "none" or "not_applicable"


# --- Delegation Chain ---


class Purpose(BaseModel):
    capability: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    task_id: str


class ConcurrentBranches(str, Enum):
    ALLOWED = "allowed"
    EXCLUSIVE = "exclusive"


class DelegationConstraints(BaseModel):
    max_delegation_depth: int = 3
    concurrent_branches: ConcurrentBranches = ConcurrentBranches.ALLOWED


class DelegationToken(BaseModel):
    token_id: str
    issuer: str
    subject: str
    scope: list[str]
    purpose: Purpose
    parent: str | None = None  # None for root tokens (issued by humans)
    expires: datetime
    constraints: DelegationConstraints = Field(default_factory=DelegationConstraints)


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


class Cost(BaseModel):
    certainty: CostCertainty = CostCertainty.FIXED
    financial: dict[str, Any] | None = None
    determined_by: str | None = None  # capability that resolves actual cost (for estimated)
    factors: list[str] | None = None  # what drives cost variation (for dynamic)
    compute: dict[str, Any] | None = None
    rate_limit: dict[str, Any] | None = None


class CostActual(BaseModel):
    financial: dict[str, Any]
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


# --- Permission Discovery ---


class AvailableCapability(BaseModel):
    capability: str
    scope_match: str
    constraints: dict[str, Any] = Field(default_factory=dict)


class RestrictedCapability(BaseModel):
    capability: str
    reason: str
    grantable_by: str


class DeniedCapability(BaseModel):
    capability: str
    reason: str


class PermissionResponse(BaseModel):
    available: list[AvailableCapability] = Field(default_factory=list)
    restricted: list[RestrictedCapability] = Field(default_factory=list)
    denied: list[DeniedCapability] = Field(default_factory=list)


# --- Failure Semantics ---


class Resolution(BaseModel):
    action: str
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


class ANIPManifest(BaseModel):
    protocol: str = "anip/1.0"
    profile: ProfileVersions
    capabilities: dict[str, CapabilityDeclaration]


# --- Invocation ---


class InvokeRequest(BaseModel):
    delegation_token: DelegationToken
    parameters: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] | None = None


class InvokeResponse(BaseModel):
    success: bool
    result: dict[str, Any] | None = None
    cost_actual: CostActual | None = None
    failure: ANIPFailure | None = None
    session: dict[str, Any] | None = None
