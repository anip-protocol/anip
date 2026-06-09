export type ApplicationIntegrationBackendType =
  | 'rest_api'
  | 'graphql_api'
  | 'mcp_server'
  | 'internal_http_service'
  | 'custom_adapter'

export type ApplicationIntegrationImplementationLanguage = 'typescript' | 'python'

export type ApplicationIntegrationAuthType =
  | 'none'
  | 'api_key'
  | 'bearer_token'
  | 'oauth2'
  | 'session_cookie'
  | 'custom'

export type ApplicationIntegrationIntentType =
  | 'search'
  | 'retrieve'
  | 'summarize'
  | 'create'
  | 'update'
  | 'delete'
  | 'trigger_workflow'

export type ApplicationIntegrationOperationType = 'read' | 'write'

export type ApplicationIntegrationSideEffectLevel =
  | 'read_only'
  | 'low_risk_write'
  | 'approval_required_write'
  | 'high_risk_write'

export type ApplicationIntegrationGovernedOutcome =
  | 'available'
  | 'restricted'
  | 'denied'
  | 'clarification_required'
  | 'approval_required'

export interface ApplicationIntegrationBackendConfig {
  backendType: ApplicationIntegrationBackendType
  systemName: string
  environment: 'development' | 'staging' | 'production'
  baseUrl: string
  authType: ApplicationIntegrationAuthType
  authNotes: string
  adapterTarget: string
  seedProfile: string | null
  implementationLanguage: ApplicationIntegrationImplementationLanguage
}

export interface ApplicationIntegrationFieldDefinition {
  fieldName: string
  fieldType: 'string' | 'number' | 'boolean' | 'date' | 'datetime' | 'enum' | 'reference' | 'text'
  required: boolean
  filterable: boolean
  writable: boolean
  sensitive: boolean
  summary: string
}

export interface ApplicationIntegrationRelationshipDefinition {
  relationshipName: string
  targetObjectName: string
  cardinality: 'one_to_one' | 'one_to_many' | 'many_to_one'
  summary: string
}

export interface ApplicationIntegrationObjectDefinition {
  objectId: string
  name: string
  summary: string
  keyField: string
  fields: ApplicationIntegrationFieldDefinition[]
  relationships: ApplicationIntegrationRelationshipDefinition[]
  sensitiveFieldNames: string[]
}

export interface ApplicationIntegrationInputDefinition {
  inputName: string
  inputType: 'string' | 'number' | 'boolean' | 'date' | 'datetime' | 'enum' | 'object_ref' | 'text'
  required: boolean
  summary: string
}

export interface ApplicationIntegrationBackendOperationMapping {
  backendOperation: string
  httpMethod: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE' | 'CUSTOM'
  pathTemplate: string
  requestMappingSummary: string
  responseMappingSummary: string
  errorMappingSummary: string
}

export interface ApplicationIntegrationCapabilityDefinition {
  capabilityId: string
  title: string
  summary: string
  objectScope: string[]
  intentType: ApplicationIntegrationIntentType
  operationType: ApplicationIntegrationOperationType
  sideEffectLevel: ApplicationIntegrationSideEffectLevel
  requiredInputs: ApplicationIntegrationInputDefinition[]
  optionalInputs: ApplicationIntegrationInputDefinition[]
  supportedFilters: string[]
  outputShape: 'record' | 'record_list' | 'summary' | 'action_receipt'
  backendMapping: ApplicationIntegrationBackendOperationMapping
}

export interface ApplicationIntegrationPermissionRule {
  ruleId: string
  scopeType: 'object' | 'field' | 'capability'
  scopeName: string
  actorConstraint: string
  purposeConstraint: string
  allowed: boolean
  summary: string
}

export interface ApplicationIntegrationClarificationRule {
  ruleId: string
  triggerType:
    | 'ambiguous_record'
    | 'ambiguous_object'
    | 'missing_required_input'
    | 'ambiguous_assignee'
    | 'ambiguous_due_date'
  capabilityId: string | null
  summary: string
  promptHint: string
  enabled: boolean
}

export interface ApplicationIntegrationRestrictionRule {
  ruleId: string
  restrictionType: 'result_limit' | 'field_projection' | 'allowed_assignees' | 'supported_object_subset'
  capabilityId: string | null
  summary: string
  value: string
  enabled: boolean
}

export interface ApplicationIntegrationDenialRule {
  ruleId: string
  denialType: 'unsupported_object' | 'forbidden_field' | 'forbidden_mutation' | 'missing_purpose' | 'authority_missing'
  capabilityId: string | null
  summary: string
  enabled: boolean
}

export interface ApplicationIntegrationApprovalRule {
  ruleId: string
  capabilityId: string
  required: boolean
  approverType: 'user' | 'manager' | 'system_policy'
  summary: string
}

export interface ApplicationIntegrationSafeDefaults {
  defaultResultLimit: number
  requireApprovalForWrites: boolean
  requireClarificationOnAmbiguousRecord: boolean
  dryRunBeforeWrite: boolean
}

export interface ApplicationIntegrationGovernanceConfig {
  permissionRules: ApplicationIntegrationPermissionRule[]
  clarificationRules: ApplicationIntegrationClarificationRule[]
  restrictionRules: ApplicationIntegrationRestrictionRule[]
  denialRules: ApplicationIntegrationDenialRule[]
  approvalRules: ApplicationIntegrationApprovalRule[]
  safeDefaults: ApplicationIntegrationSafeDefaults
}

export interface ApplicationIntegrationScenarioDefinition {
  scenarioId: string
  title: string
  request: string
  capabilityHint: string | null
  expectedOutcome: ApplicationIntegrationGovernedOutcome
  expectedBackendOperation: string | null
  notes: string
}

export interface ApplicationIntegrationProjectMetadata {
  createdAt: string
  updatedAt: string
  sourcePacketId: string | null
  derivationSummary: string | null
}

export interface ApplicationIntegrationProjectState {
  kind: 'application_integration'
  version: 1
  title: string
  summary: string
  backend: ApplicationIntegrationBackendConfig
  objects: ApplicationIntegrationObjectDefinition[]
  capabilities: ApplicationIntegrationCapabilityDefinition[]
  governance: ApplicationIntegrationGovernanceConfig
  scenarios: ApplicationIntegrationScenarioDefinition[]
  metadata: ApplicationIntegrationProjectMetadata
}

export type ApplicationIntegrationGeneratedOutputKind =
  | 'design_packet'
  | 'anip_capability_scaffold'
  | 'backend_adapter_scaffold'
  | 'scenario_pack_json'
  | 'scenario_manifest_json'
  | 'policy_stub'

export interface ApplicationIntegrationGeneratedOutput {
  kind: ApplicationIntegrationGeneratedOutputKind
  title: string
  filename: string
  contentType: 'markdown' | 'json' | 'typescript' | 'python' | 'text' | 'yaml'
  content: string
  generatedAt: string
}

export interface ApplicationIntegrationGeneratedBundle {
  designPacket: ApplicationIntegrationGeneratedOutput
  anipCapabilityScaffold: ApplicationIntegrationGeneratedOutput
  backendAdapterScaffold: ApplicationIntegrationGeneratedOutput
  scenarioPackJson: ApplicationIntegrationGeneratedOutput
  scenarioManifestJson: ApplicationIntegrationGeneratedOutput
  policyStub: ApplicationIntegrationGeneratedOutput
}


export interface SavedApplicationIntegrationProjectSummary {
  id: string
  title: string
  studio_project_id: string | null
  created_at: string
  updated_at: string
}

export interface SavedApplicationIntegrationProjectRecord extends SavedApplicationIntegrationProjectSummary {
  state: ApplicationIntegrationProjectState
}
