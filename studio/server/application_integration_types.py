"""Structured models for Studio's Application Integration design flow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ApplicationIntegrationBackendType = Literal["rest_api", "graphql_api", "mcp_server", "internal_http_service", "custom_adapter"]
ApplicationIntegrationImplementationLanguage = Literal["typescript", "python"]
ApplicationIntegrationAuthType = Literal["none", "api_key", "bearer_token", "oauth2", "session_cookie", "custom"]
ApplicationIntegrationIntentType = Literal["search", "retrieve", "summarize", "create", "update", "delete", "trigger_workflow"]
ApplicationIntegrationOperationType = Literal["read", "write"]
ApplicationIntegrationSideEffectLevel = Literal["read_only", "low_risk_write", "approval_required_write", "high_risk_write"]
ApplicationIntegrationGovernedOutcome = Literal[
    "available", "restricted", "denied", "clarification_required", "approval_required"
]


class ApplicationIntegrationBackendConfig(BaseModel):
    backendType: ApplicationIntegrationBackendType
    systemName: str
    environment: Literal["development", "staging", "production"]
    baseUrl: str
    authType: ApplicationIntegrationAuthType
    authNotes: str = ""
    adapterTarget: str
    seedProfile: str | None = None
    implementationLanguage: ApplicationIntegrationImplementationLanguage = "typescript"


class ApplicationIntegrationFieldDefinition(BaseModel):
    fieldName: str
    fieldType: Literal["string", "number", "boolean", "date", "datetime", "enum", "reference", "text"]
    required: bool = False
    filterable: bool = False
    writable: bool = False
    sensitive: bool = False
    summary: str = ""


class ApplicationIntegrationRelationshipDefinition(BaseModel):
    relationshipName: str
    targetObjectName: str
    cardinality: Literal["one_to_one", "one_to_many", "many_to_one"]
    summary: str = ""


class ApplicationIntegrationObjectDefinition(BaseModel):
    objectId: str
    name: str
    summary: str = ""
    keyField: str
    fields: list[ApplicationIntegrationFieldDefinition] = Field(default_factory=list)
    relationships: list[ApplicationIntegrationRelationshipDefinition] = Field(default_factory=list)
    sensitiveFieldNames: list[str] = Field(default_factory=list)


class ApplicationIntegrationInputDefinition(BaseModel):
    inputName: str
    inputType: Literal["string", "number", "boolean", "date", "datetime", "enum", "object_ref", "text"]
    required: bool = False
    summary: str = ""


class ApplicationIntegrationBackendOperationMapping(BaseModel):
    backendOperation: str
    httpMethod: Literal["GET", "POST", "PATCH", "PUT", "DELETE", "CUSTOM"]
    pathTemplate: str
    requestMappingSummary: str = ""
    responseMappingSummary: str = ""
    errorMappingSummary: str = ""


class ApplicationIntegrationCapabilityDefinition(BaseModel):
    capabilityId: str
    title: str
    summary: str = ""
    objectScope: list[str] = Field(default_factory=list)
    intentType: ApplicationIntegrationIntentType
    operationType: ApplicationIntegrationOperationType
    sideEffectLevel: ApplicationIntegrationSideEffectLevel
    requiredInputs: list[ApplicationIntegrationInputDefinition] = Field(default_factory=list)
    optionalInputs: list[ApplicationIntegrationInputDefinition] = Field(default_factory=list)
    supportedFilters: list[str] = Field(default_factory=list)
    outputShape: Literal["record", "record_list", "summary", "action_receipt"]
    backendMapping: ApplicationIntegrationBackendOperationMapping


class ApplicationIntegrationPermissionRule(BaseModel):
    ruleId: str
    scopeType: Literal["object", "field", "capability"]
    scopeName: str
    actorConstraint: str
    purposeConstraint: str
    allowed: bool = True
    summary: str = ""


class ApplicationIntegrationClarificationRule(BaseModel):
    ruleId: str
    triggerType: Literal["ambiguous_record", "ambiguous_object", "missing_required_input", "ambiguous_assignee", "ambiguous_due_date"]
    capabilityId: str | None = None
    summary: str = ""
    promptHint: str = ""
    enabled: bool = True


class ApplicationIntegrationRestrictionRule(BaseModel):
    ruleId: str
    restrictionType: Literal["result_limit", "field_projection", "allowed_assignees", "supported_object_subset"]
    capabilityId: str | None = None
    summary: str = ""
    value: str = ""
    enabled: bool = True


class ApplicationIntegrationDenialRule(BaseModel):
    ruleId: str
    denialType: Literal["unsupported_object", "forbidden_field", "forbidden_mutation", "missing_purpose", "authority_missing"]
    capabilityId: str | None = None
    summary: str = ""
    enabled: bool = True


class ApplicationIntegrationApprovalRule(BaseModel):
    ruleId: str
    capabilityId: str
    required: bool = True
    approverType: Literal["user", "manager", "system_policy"]
    summary: str = ""


class ApplicationIntegrationSafeDefaults(BaseModel):
    defaultResultLimit: int = 10
    requireApprovalForWrites: bool = True
    requireClarificationOnAmbiguousRecord: bool = True
    dryRunBeforeWrite: bool = True


class ApplicationIntegrationGovernanceConfig(BaseModel):
    permissionRules: list[ApplicationIntegrationPermissionRule] = Field(default_factory=list)
    clarificationRules: list[ApplicationIntegrationClarificationRule] = Field(default_factory=list)
    restrictionRules: list[ApplicationIntegrationRestrictionRule] = Field(default_factory=list)
    denialRules: list[ApplicationIntegrationDenialRule] = Field(default_factory=list)
    approvalRules: list[ApplicationIntegrationApprovalRule] = Field(default_factory=list)
    safeDefaults: ApplicationIntegrationSafeDefaults


class ApplicationIntegrationScenarioDefinition(BaseModel):
    scenarioId: str
    title: str
    request: str
    capabilityHint: str | None = None
    expectedOutcome: ApplicationIntegrationGovernedOutcome
    expectedBackendOperation: str | None = None
    notes: str = ""


class ApplicationIntegrationProjectMetadata(BaseModel):
    createdAt: str
    updatedAt: str
    sourcePacketId: str | None = None
    derivationSummary: str | None = None


class ApplicationIntegrationProjectState(BaseModel):
    kind: Literal["application_integration"] = "application_integration"
    version: Literal[1] = 1
    title: str
    summary: str = ""
    backend: ApplicationIntegrationBackendConfig
    objects: list[ApplicationIntegrationObjectDefinition] = Field(default_factory=list)
    capabilities: list[ApplicationIntegrationCapabilityDefinition] = Field(default_factory=list)
    governance: ApplicationIntegrationGovernanceConfig
    scenarios: list[ApplicationIntegrationScenarioDefinition] = Field(default_factory=list)
    metadata: ApplicationIntegrationProjectMetadata


class ApplicationIntegrationGeneratedOutput(BaseModel):
    kind: Literal[
        "design_packet",
        "anip_capability_scaffold",
        "backend_adapter_scaffold",
        "scenario_pack_json",
        "scenario_manifest_json",
        "policy_stub",
    ]
    title: str
    filename: str
    contentType: Literal["markdown", "json", "typescript", "python", "text", "yaml"]
    content: str
    generatedAt: str


class ApplicationIntegrationGeneratedBundle(BaseModel):
    designPacket: ApplicationIntegrationGeneratedOutput
    anipCapabilityScaffold: ApplicationIntegrationGeneratedOutput
    backendAdapterScaffold: ApplicationIntegrationGeneratedOutput
    scenarioPackJson: ApplicationIntegrationGeneratedOutput
    scenarioManifestJson: ApplicationIntegrationGeneratedOutput
    policyStub: ApplicationIntegrationGeneratedOutput



class CreateApplicationIntegrationProjectRequest(BaseModel):
    id: str
    studio_project_id: str | None = None
    state: ApplicationIntegrationProjectState


class UpdateApplicationIntegrationProjectRequest(BaseModel):
    studio_project_id: str | None = None
    state: ApplicationIntegrationProjectState


class ApplicationIntegrationProjectSummary(BaseModel):
    id: str
    title: str
    studio_project_id: str | None = None
    created_at: str
    updated_at: str


class ApplicationIntegrationProjectRecord(ApplicationIntegrationProjectSummary):
    state: ApplicationIntegrationProjectState
