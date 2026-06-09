"""Pydantic request/response models for the ANIP Studio workspace API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


ProjectType = Literal["standard", "governed_service_project"]
IntegrationProfileKind = Literal["none", "native_api", "mcp", "database", "hybrid"]
BackendKind = Literal["native_api", "mcp", "database", "hybrid"]
ConnectionAuthMode = Literal["user_delegated", "service_delegated", "external"]


def default_integration_profile() -> dict[str, Any]:
    return {"kind": "none", "systems": []}


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------

class CreateWorkspace(BaseModel):
    id: str
    name: str
    summary: str = ""


class UpdateWorkspace(BaseModel):
    name: Optional[str] = None
    summary: Optional[str] = None


class CloneWorkspace(BaseModel):
    id: Optional[str] = None
    name: str
    summary: str = ""


class WorkspaceOut(BaseModel):
    id: str
    name: str
    summary: str
    created_at: datetime
    updated_at: datetime


class WorkspaceDetail(WorkspaceOut):
    projects_count: int


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

class CreateProject(BaseModel):
    id: str
    workspace_id: Optional[str] = None
    name: str
    summary: str = ""
    domain: str = ""
    labels: list[str] = Field(default_factory=list)
    project_type: ProjectType = "standard"
    integration_profile: dict[str, Any] = Field(default_factory=default_integration_profile)


class UpdateProject(BaseModel):
    name: Optional[str] = None
    summary: Optional[str] = None
    domain: Optional[str] = None
    labels: Optional[list[str]] = None
    project_type: Optional[ProjectType] = None
    integration_profile: Optional[dict[str, Any]] = None


class CloneProject(BaseModel):
    id: Optional[str] = None
    workspace_id: Optional[str] = None
    name: str
    summary: Optional[str] = None


class ProjectOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    summary: str
    domain: str
    labels: list[str]
    project_type: ProjectType = "standard"
    integration_profile: dict[str, Any] = Field(default_factory=default_integration_profile)
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectOut):
    requirements_count: int
    scenarios_count: int
    proposals_count: int
    evaluations_count: int
    shapes_count: int = 0
    documents_count: int = 0
    pm_artifacts_count: int = 0


# ---------------------------------------------------------------------------
# Integration Fronting Foundation
# ---------------------------------------------------------------------------

class WorkspaceConnectionBase(BaseModel):
    display_name: str
    backend_kind: BackendKind
    system_kind: str = ""
    endpoint_ref: str = ""
    auth_mode: ConnectionAuthMode
    identity_provider_ref: str = ""
    secret_ref: str = ""
    allowed_project_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateWorkspaceConnection(WorkspaceConnectionBase):
    id: str


class UpdateWorkspaceConnection(BaseModel):
    display_name: Optional[str] = None
    backend_kind: Optional[BackendKind] = None
    system_kind: Optional[str] = None
    endpoint_ref: Optional[str] = None
    auth_mode: Optional[ConnectionAuthMode] = None
    identity_provider_ref: Optional[str] = None
    secret_ref: Optional[str] = None
    allowed_project_refs: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class WorkspaceConnectionOut(WorkspaceConnectionBase):
    id: str
    workspace_id: str
    created_at: datetime
    updated_at: datetime


class IntegrationDiscoveryRecordBase(BaseModel):
    connection_id: Optional[str] = None
    operation_id: str
    backend_kind: BackendKind
    method: str = ""
    path_template: str = ""
    side_effect_level: str = "read"
    input_schema_summary: dict[str, Any] = Field(default_factory=dict)
    risk_notes: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class CreateIntegrationDiscoveryRecord(IntegrationDiscoveryRecordBase):
    id: str


class UpdateIntegrationDiscoveryRecord(BaseModel):
    connection_id: Optional[str] = None
    operation_id: Optional[str] = None
    backend_kind: Optional[BackendKind] = None
    method: Optional[str] = None
    path_template: Optional[str] = None
    side_effect_level: Optional[str] = None
    input_schema_summary: Optional[dict[str, Any]] = None
    risk_notes: Optional[list[str]] = None
    data: Optional[dict[str, Any]] = None


class IntegrationDiscoveryRecordOut(IntegrationDiscoveryRecordBase):
    id: str
    project_id: str
    content_hash: str = ""
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Generic Artifacts (requirements_sets, scenarios)
# ---------------------------------------------------------------------------

class CreateArtifact(BaseModel):
    id: str
    title: str
    data: dict


class UpdateArtifact(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    data: Optional[dict] = None


class ArtifactOut(BaseModel):
    id: str
    project_id: str
    title: str
    status: str
    data: dict
    content_hash: str = ""
    role: str = ""
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------

class CreateProposal(BaseModel):
    id: str
    title: str
    requirements_id: str
    data: dict


class ProposalOut(ArtifactOut):
    requirements_id: str


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------

class CreateShape(BaseModel):
    id: str
    title: str
    requirements_id: str
    data: dict


class UpdateShape(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    data: Optional[dict] = None


class ShapeOut(ArtifactOut):
    requirements_id: str


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

class CreateEvaluation(BaseModel):
    id: str
    proposal_id: Optional[str] = None
    scenario_id: str
    requirements_id: str
    shape_id: Optional[str] = None
    source: str = "manual"
    data: dict
    input_snapshot: dict


class EvaluationOut(BaseModel):
    id: str
    project_id: str
    proposal_id: Optional[str] = None
    scenario_id: str
    requirements_id: str
    shape_id: Optional[str] = None
    result: str
    source: str
    data: dict
    input_snapshot: dict
    requirements_hash: str = ""
    proposal_hash: str = ""
    scenario_hash: str = ""
    shape_hash: str = ""
    derived_expectations: Optional[list] = None
    is_stale: bool = False
    stale_artifacts: list[str] = Field(default_factory=list)
    created_at: datetime


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

class CreateVocabulary(BaseModel):
    project_id: Optional[str] = None
    category: str
    value: str
    origin: str = "custom"
    description: str = ""


class VocabularyOut(BaseModel):
    id: int
    project_id: Optional[str]
    category: str
    value: str
    origin: str
    description: str
    evaluator_recognized: bool = False


# ---------------------------------------------------------------------------
# Requirements Role
# ---------------------------------------------------------------------------

class SetRoleRequest(BaseModel):
    role: str


# Alias used by the router endpoint
SetRequirementsRole = SetRoleRequest


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------

class ImportArtifact(BaseModel):
    type: str
    data: dict


class ImportRequest(BaseModel):
    artifacts: list[ImportArtifact]


class ImportResult(BaseModel):
    imported: int
    errors: list[str]


# ---------------------------------------------------------------------------
# Project Documents
# ---------------------------------------------------------------------------

class CreateProjectDocument(BaseModel):
    id: str
    title: str
    kind: str = "reference"
    filename: str
    media_type: str = "application/octet-stream"
    source_path: str = ""
    content_base64: str


class ProjectDocumentOut(BaseModel):
    id: str
    project_id: str
    title: str
    kind: str
    filename: str
    media_type: str
    source_path: str
    content_hash: str
    created_at: datetime
    updated_at: datetime


class RuntimeStatusOut(BaseModel):
    studio_api_reachable: bool
    assistant_provider: str
    assistant_model: str | None = None
    assistant_base_url: str | None = None
    llm_enabled: bool
    llm_ready: bool
    api_key_configured: bool
    api_key_source: str = "none"
    provider_source: str = "default"
    model_source: str = "default"
    base_url_source: str = "default"
    read_only_mode: bool = False
    read_only_reason: str | None = None


class AssistantRuntimeConfigOut(BaseModel):
    assistant_provider: str
    assistant_model: str | None = None
    assistant_base_url: str | None = None
    temperature: float
    timeout_seconds: float
    strict: bool
    api_key_configured: bool
    stored_api_key_configured: bool
    provider_source: str = "default"
    model_source: str = "default"
    base_url_source: str = "default"
    api_key_source: str = "none"
    temperature_source: str = "default"
    timeout_seconds_source: str = "default"
    strict_source: str = "default"
    read_only_mode: bool = False
    read_only_reason: str | None = None


class SimulatorRuntimeConfigOut(BaseModel):
    simulator_provider: str
    simulator_model: str | None = None
    simulator_base_url: str | None = None
    temperature: float
    timeout_seconds: float
    api_key_configured: bool
    stored_api_key_configured: bool
    provider_source: str = "default"
    model_source: str = "default"
    base_url_source: str = "default"
    api_key_source: str = "none"
    temperature_source: str = "default"
    timeout_seconds_source: str = "default"
    read_only_mode: bool = False
    read_only_reason: str | None = None


class RegistryTrustPolicyOut(BaseModel):
    registry_url: str
    registry_url_source: str = "default"
    required_registry_mode: str | None = None
    required_registry_mode_source: str = "unset"
    trusted_registry_key_id: str | None = None
    trusted_registry_key_id_source: str = "unset"
    publish_token_configured: bool = False
    publish_token_source: str = "none"
    production_mode_detected: bool = False
    allows_development_registry: bool = True
    key_pinned: bool = False
    warning: str | None = None


class StudioSettingsOut(BaseModel):
    assistant: AssistantRuntimeConfigOut
    simulator: SimulatorRuntimeConfigOut
    registry: RegistryTrustPolicyOut


class UpdateRegistryTrustPolicy(BaseModel):
    registry_url: Optional[str] = None
    required_registry_mode: Optional[str] = None
    trusted_registry_key_id: Optional[str] = None
    registry_publish_token: Optional[str] = None
    clear_registry_publish_token: bool = False


class UpdateAssistantRuntimeConfig(BaseModel):
    assistant_provider: Optional[str] = None
    assistant_model: Optional[str] = None
    assistant_base_url: Optional[str] = None
    assistant_api_key: Optional[str] = None
    clear_assistant_api_key: bool = False
    temperature: Optional[float] = None
    timeout_seconds: Optional[float] = None
    strict: Optional[bool] = None


class UpdateSimulatorRuntimeConfig(BaseModel):
    simulator_provider: Optional[str] = None
    simulator_model: Optional[str] = None
    simulator_base_url: Optional[str] = None
    simulator_api_key: Optional[str] = None
    clear_simulator_api_key: bool = False
    temperature: Optional[float] = None
    timeout_seconds: Optional[float] = None


class UpdateStudioSettings(BaseModel):
    assistant: UpdateAssistantRuntimeConfig | None = None
    simulator: UpdateSimulatorRuntimeConfig | None = None
    registry: UpdateRegistryTrustPolicy | None = None


class AgentConsumptionSimulationRequest(BaseModel):
    project: dict[str, Any] | None = None
    developer_definition: dict[str, Any] = Field(default_factory=dict)
    readiness: dict[str, Any] = Field(default_factory=dict)
    agent_consumability: dict[str, Any] = Field(default_factory=dict)
    probes: list[dict[str, Any]] = Field(default_factory=list)


class AgentConsumptionSimulationResult(BaseModel):
    artifact_type: str
    schema_version: str
    simulator_runtime: dict[str, Any]
    cases: list[dict[str, Any]]
    summary: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Assistant Proposal Acceptance
# ---------------------------------------------------------------------------

class ApplyAssistantProposal(BaseModel):
    artifact_id: str
    title: str
    capability: str
    proposal: dict
    accepted_item_ids: list[str] = Field(default_factory=list)
    rejected_item_ids: list[str] = Field(default_factory=list)
    accepted_answers: dict[str, str] = Field(default_factory=dict)
    notes: str = ""


class AppendAssistantAuditEvent(BaseModel):
    event_type: str
    lane: str
    bundle_artifact_id: Optional[str] = None
    section_id: Optional[str] = None
    section_title: Optional[str] = None
    selected_ids: list[str] = Field(default_factory=list)
    clarification_question_ids: list[str] = Field(default_factory=list)
    source_document_id: Optional[str] = None
    source_document_title: Optional[str] = None
    baseline_locked_at: Optional[str] = None
    section_count: Optional[int] = None
    status: str = "ok"
    error: Optional[str] = None
    assistant_runtime: Optional[dict] = None
