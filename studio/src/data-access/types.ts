export type DataAccessBackendType =
  | 'curated_sql'
  | 'cube_rest'
  | 'snowflake_sql'
  | 'snowflake_semantic'
  | 'databricks_sql'
  | 'databricks_genie'
  | 'dbt_semantic'
  | 'internal_metrics_api'
  | 'custom_adapter'

export type DataAccessGrain = 'aggregate' | 'entity_detail'

export type DataAccessImplementationLanguage = 'typescript' | 'python'

export type DataAccessResultMode = 'exploratory' | 'decision_grade'

export type DataAccessGovernedOutcome =
  | 'available'
  | 'restricted'
  | 'denied'
  | 'clarification_required'

export type DataAccessClarificationRuleKey =
  | 'ambiguous_ranking_metric'
  | 'ambiguous_time_semantics'
  | 'ambiguous_entity_grain'
  | 'ambiguous_account_hierarchy'

export type DataAccessScenarioCategory =
  | 'allowed'
  | 'restricted'
  | 'denied'
  | 'clarification_required'

export interface DataAccessMetricDef {
  key: string
  label: string
  description?: string
}

export interface DataAccessDimensionDef {
  key: string
  label: string
  description?: string
}

export interface DataAccessFilterDef {
  key: string
  label: string
  description?: string
}

export interface DataAccessBackendConfig {
  type: DataAccessBackendType
  targetLabel: string
  adapterMode: 'generated_scaffold' | 'manual'
  implementationLanguage: DataAccessImplementationLanguage
  notes?: string
}

export interface DataAccessDomainConfig {
  name: string
  metrics: DataAccessMetricDef[]
  dimensions: DataAccessDimensionDef[]
  filters: DataAccessFilterDef[]
  grains: DataAccessGrain[]
  resultModes: DataAccessResultMode[]
}

export interface DataAccessMetricRule {
  metricKey: string
  restrictedToRoles: string[]
  deniedRoles?: string[]
  notes?: string
}

export interface DataAccessDimensionRule {
  dimensionKey: string
  restrictedToRoles: string[]
  deniedRoles?: string[]
  notes?: string
}

export interface DataAccessLimitRule {
  appliesToRoles: string[]
  grain: DataAccessGrain
  maxRows: number
  notes?: string
}

export interface DataAccessUseRule {
  appliesToRoles: string[]
  exportAllowed: boolean
  downstreamUse: 'display_only' | 'analysis_only' | 'decision_support'
  downgradeDecisionGrade?: boolean
  notes?: string
}

export interface DataAccessPermissionConfig {
  metricRules: DataAccessMetricRule[]
  dimensionRules: DataAccessDimensionRule[]
  limitRules: DataAccessLimitRule[]
  useRules: DataAccessUseRule[]
}

export interface DataAccessClarificationRule {
  key: DataAccessClarificationRuleKey
  enabled: boolean
  promptHint?: string
}

export interface DataAccessClarificationConfig {
  rules: DataAccessClarificationRule[]
}

export interface DataAccessScenarioPackConfig {
  categories: DataAccessScenarioCategory[]
  targetCount: number
}

export interface DataAccessCapabilityInputDef {
  inputName: string
  inputType: string
  required: boolean
  summary?: string
}

export interface DataAccessServiceCapabilityDef {
  capabilityId: string
  title: string
  summary: string
  operationType: 'read' | 'write'
  sideEffectLevel: string
  backendOperation: string
  minimumScope: string[]
  requiredInputs: DataAccessCapabilityInputDef[]
  optionalInputs: DataAccessCapabilityInputDef[]
  clarificationRules: string[]
  denialRules: string[]
  approvalRules: string[]
  boundedEvidence: string[]
  notes: string[]
}

export interface DataAccessServiceContract {
  serviceId: string
  serviceName: string
  serviceSummary: string
  capabilities: DataAccessServiceCapabilityDef[]
}

export interface DataAccessProjectState {
  kind: 'governed_data_access'
  version: 1
  name: string
  description: string
  backend: DataAccessBackendConfig
  domain: DataAccessDomainConfig
  governedOutcomes: Record<DataAccessGovernedOutcome, boolean>
  permissions: DataAccessPermissionConfig
  clarification: DataAccessClarificationConfig
  scenarioPack: DataAccessScenarioPackConfig
  serviceContract?: DataAccessServiceContract | null
}

export type DataAccessGeneratedOutputKind =
  | 'design_packet'
  | 'anip_capability_scaffold'
  | 'backend_adapter_scaffold'
  | 'scenario_pack_json'
  | 'scenario_manifest_json'

export interface DataAccessGeneratedOutput {
  kind: DataAccessGeneratedOutputKind
  title: string
  filename: string
  contentType: 'markdown' | 'json' | 'typescript' | 'python' | 'text'
  content: string
  generatedAt: string
}

export interface DataAccessGeneratedBundle {
  designPacket: DataAccessGeneratedOutput
  anipCapabilityScaffold: DataAccessGeneratedOutput
  backendAdapterScaffold: DataAccessGeneratedOutput
  scenarioPackJson: DataAccessGeneratedOutput
  scenarioManifestJson: DataAccessGeneratedOutput
}

export interface SavedDataAccessProjectSummary {
  id: string
  name: string
  studio_project_id: string | null
  created_at: string
  updated_at: string
}

export interface SavedDataAccessProjectRecord extends SavedDataAccessProjectSummary {
  state: DataAccessProjectState
}

export interface DataAccessViewState {
  project: DataAccessProjectState | null
  generated: DataAccessGeneratedBundle | null
  activeSection:
    | 'backend'
    | 'domain'
    | 'outcomes'
    | 'permissions'
    | 'clarification'
    | 'scenario_pack'
    | 'outputs'
  loading: boolean
  error: string | null
  dirty: boolean
}
