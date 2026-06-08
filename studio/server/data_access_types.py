"""Structured models for Studio's governed data-access design flow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


DataAccessBackendType = Literal[
    "curated_sql",
    "cube_rest",
    "snowflake_sql",
    "databricks_sql",
    "dbt_semantic",
    "internal_metrics_api",
    "custom_adapter",
]
DataAccessGrain = Literal["aggregate", "entity_detail"]
DataAccessImplementationLanguage = Literal["typescript", "python"]
DataAccessResultMode = Literal["exploratory", "decision_grade"]
DataAccessGovernedOutcome = Literal["available", "restricted", "denied", "clarification_required"]
DataAccessClarificationRuleKey = Literal[
    "ambiguous_ranking_metric",
    "ambiguous_time_semantics",
    "ambiguous_entity_grain",
    "ambiguous_account_hierarchy",
]
DataAccessScenarioCategory = Literal["allowed", "restricted", "denied", "clarification_required"]


class DataAccessMetricDef(BaseModel):
    key: str
    label: str
    description: str | None = None


class DataAccessDimensionDef(BaseModel):
    key: str
    label: str
    description: str | None = None


class DataAccessFilterDef(BaseModel):
    key: str
    label: str
    description: str | None = None


class DataAccessBackendConfig(BaseModel):
    type: DataAccessBackendType
    targetLabel: str
    adapterMode: Literal["generated_scaffold", "manual"] = "generated_scaffold"
    implementationLanguage: DataAccessImplementationLanguage = "typescript"
    notes: str | None = None


class DataAccessDomainConfig(BaseModel):
    name: str
    metrics: list[DataAccessMetricDef]
    dimensions: list[DataAccessDimensionDef]
    filters: list[DataAccessFilterDef]
    grains: list[DataAccessGrain]
    resultModes: list[DataAccessResultMode]


class DataAccessMetricRule(BaseModel):
    metricKey: str
    restrictedToRoles: list[str] = Field(default_factory=list)
    deniedRoles: list[str] = Field(default_factory=list)
    notes: str | None = None


class DataAccessDimensionRule(BaseModel):
    dimensionKey: str
    restrictedToRoles: list[str] = Field(default_factory=list)
    deniedRoles: list[str] = Field(default_factory=list)
    notes: str | None = None


class DataAccessLimitRule(BaseModel):
    appliesToRoles: list[str] = Field(default_factory=list)
    grain: DataAccessGrain
    maxRows: int
    notes: str | None = None


class DataAccessUseRule(BaseModel):
    appliesToRoles: list[str] = Field(default_factory=list)
    exportAllowed: bool
    downstreamUse: Literal["display_only", "analysis_only", "decision_support"]
    downgradeDecisionGrade: bool = False
    notes: str | None = None


class DataAccessPermissionConfig(BaseModel):
    metricRules: list[DataAccessMetricRule] = Field(default_factory=list)
    dimensionRules: list[DataAccessDimensionRule] = Field(default_factory=list)
    limitRules: list[DataAccessLimitRule] = Field(default_factory=list)
    useRules: list[DataAccessUseRule] = Field(default_factory=list)


class DataAccessClarificationRule(BaseModel):
    key: DataAccessClarificationRuleKey
    enabled: bool = True
    promptHint: str | None = None


class DataAccessClarificationConfig(BaseModel):
    rules: list[DataAccessClarificationRule] = Field(default_factory=list)


class DataAccessScenarioPackConfig(BaseModel):
    categories: list[DataAccessScenarioCategory] = Field(default_factory=list)
    targetCount: int = 12


class DataAccessCapabilityInputDef(BaseModel):
    inputName: str
    inputType: str
    required: bool = True
    summary: str | None = None


class DataAccessServiceCapabilityDef(BaseModel):
    capabilityId: str
    title: str
    summary: str
    operationType: Literal["read", "write"] = "read"
    sideEffectLevel: str = "read_only"
    backendOperation: str
    minimumScope: list[str] = Field(default_factory=list)
    requiredInputs: list[DataAccessCapabilityInputDef] = Field(default_factory=list)
    optionalInputs: list[DataAccessCapabilityInputDef] = Field(default_factory=list)
    clarificationRules: list[str] = Field(default_factory=list)
    denialRules: list[str] = Field(default_factory=list)
    approvalRules: list[str] = Field(default_factory=list)
    boundedEvidence: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DataAccessServiceContract(BaseModel):
    serviceId: str
    serviceName: str
    serviceSummary: str
    capabilities: list[DataAccessServiceCapabilityDef] = Field(default_factory=list)


class DataAccessProjectState(BaseModel):
    kind: Literal["governed_data_access"] = "governed_data_access"
    version: Literal[1] = 1
    name: str
    description: str = ""
    backend: DataAccessBackendConfig
    domain: DataAccessDomainConfig
    governedOutcomes: dict[DataAccessGovernedOutcome, bool]
    permissions: DataAccessPermissionConfig
    clarification: DataAccessClarificationConfig
    scenarioPack: DataAccessScenarioPackConfig
    serviceContract: DataAccessServiceContract | None = None


class DataAccessGeneratedOutput(BaseModel):
    kind: Literal[
        "design_packet",
        "anip_capability_scaffold",
        "backend_adapter_scaffold",
        "scenario_pack_json",
        "scenario_manifest_json",
    ]
    title: str
    filename: str
    contentType: Literal["markdown", "json", "typescript", "python", "text"]
    content: str
    generatedAt: str


class DataAccessGeneratedBundle(BaseModel):
    designPacket: DataAccessGeneratedOutput
    anipCapabilityScaffold: DataAccessGeneratedOutput
    backendAdapterScaffold: DataAccessGeneratedOutput
    scenarioPackJson: DataAccessGeneratedOutput
    scenarioManifestJson: DataAccessGeneratedOutput


class DraftDataAccessProjectRequest(BaseModel):
    name: str
    description: str = ""
    backendType: DataAccessBackendType = "internal_metrics_api"


class CreateDataAccessProjectRequest(BaseModel):
    id: str
    studio_project_id: str | None = None
    state: DataAccessProjectState


class UpdateDataAccessProjectRequest(BaseModel):
    studio_project_id: str | None = None
    state: DataAccessProjectState


class DataAccessProjectSummary(BaseModel):
    id: str
    name: str
    studio_project_id: str | None = None
    created_at: str
    updated_at: str


class DataAccessProjectRecord(DataAccessProjectSummary):
    state: DataAccessProjectState
