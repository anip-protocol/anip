import type { ObservedServiceMetadata, ServiceMetadataComparison } from './types'

// Types mirroring the backend Pydantic models for the workspace API.

export interface WorkspaceSummary {
  id: string
  name: string
  summary: string
  created_at: string
  updated_at: string
}

export interface WorkspaceDetail extends WorkspaceSummary {
  projects_count: number
}

export type ProjectType = 'standard' | 'governed_service_project'
export type IntegrationProfileKind = 'none' | 'native_api' | 'mcp' | 'database' | 'hybrid'
export type IntegrationBackendKind = 'native_api' | 'mcp' | 'database' | 'hybrid'
export type IntegrationAuthMode = 'user_delegated' | 'service_delegated' | 'external'
export type BackendInputMode = 'implicit' | 'hybrid' | 'explicit'

export interface IntegrationProfileSystem {
  system_id: string
  display_name?: string
  backend_kind: IntegrationBackendKind
  auth_mode: IntegrationAuthMode
  connection_ref?: string
}

export interface IntegrationProfile {
  kind: IntegrationProfileKind
  systems: IntegrationProfileSystem[]
}

export interface ProjectSummary {
  id: string
  workspace_id: string
  name: string
  summary: string
  domain: string
  labels: string[]
  project_type?: ProjectType
  integration_profile?: IntegrationProfile
  created_at: string
  updated_at: string
}

export interface ProjectDetail extends ProjectSummary {
  requirements_count: number
  scenarios_count: number
  proposals_count: number
  evaluations_count: number
  shapes_count: number
  service_metadata_count?: number
  documents_count?: number
  pm_artifacts_count?: number
}

export interface ProjectDocumentRecord {
  id: string
  project_id: string
  title: string
  kind: string
  filename: string
  media_type: string
  source_path: string
  content_hash: string
  created_at: string
  updated_at: string
}

export interface RuntimeStatus {
  studio_api_reachable: boolean
  assistant_provider: string
  assistant_model?: string | null
  assistant_base_url?: string | null
  llm_enabled: boolean
  llm_ready: boolean
  api_key_configured: boolean
  api_key_source: string
  provider_source: string
  model_source: string
  base_url_source: string
  read_only_mode: boolean
  read_only_reason?: string | null
}

export interface AssistantRuntimeConfig {
  assistant_provider: string
  assistant_model?: string | null
  assistant_base_url?: string | null
  temperature: number
  timeout_seconds: number
  strict: boolean
  api_key_configured: boolean
  stored_api_key_configured: boolean
  provider_source: string
  model_source: string
  base_url_source: string
  api_key_source: string
  temperature_source: string
  timeout_seconds_source: string
  strict_source: string
  read_only_mode: boolean
  read_only_reason?: string | null
}

export interface SimulatorRuntimeConfig {
  simulator_provider: string
  simulator_model?: string | null
  simulator_base_url?: string | null
  temperature: number
  timeout_seconds: number
  api_key_configured: boolean
  stored_api_key_configured: boolean
  provider_source: string
  model_source: string
  base_url_source: string
  api_key_source: string
  temperature_source: string
  timeout_seconds_source: string
  read_only_mode: boolean
  read_only_reason?: string | null
}

export interface RegistryTrustPolicyConfig {
  registry_url: string
  registry_url_source: string
  required_registry_mode?: string | null
  required_registry_mode_source: string
  trusted_registry_key_id?: string | null
  trusted_registry_key_id_source: string
  publish_token_configured: boolean
  publish_token_source: string
  production_mode_detected: boolean
  allows_development_registry: boolean
  key_pinned: boolean
  warning?: string | null
}

export interface DesktopStorageStatus {
  studio_mode: string
  backend: string
  database_url_configured: boolean
  sqlite_path?: string | null
  showcase_preload_enabled: boolean
  seed_profile: string
  central_install_recommendation: string
}

export interface StudioSettings {
  assistant: AssistantRuntimeConfig
  simulator: SimulatorRuntimeConfig
  registry: RegistryTrustPolicyConfig
  desktop_storage: DesktopStorageStatus
}

export interface ArtifactRecord {
  id: string
  project_id: string
  title: string
  status: string
  data: Record<string, any>
  content_hash: string
  created_at: string
  updated_at: string
}

export interface RequirementsRecord extends ArtifactRecord {
  role: 'primary' | 'alternative'
}

export interface ProposalRecord extends ArtifactRecord {
  requirements_id: string
}

export interface ShapeRecord extends ArtifactRecord {
  requirements_id: string
}

export interface EvaluationRecord {
  id: string
  project_id: string
  proposal_id: string | null
  scenario_id: string
  requirements_id: string
  shape_id: string | null
  result: string
  source: string
  data: Record<string, any>
  input_snapshot: Record<string, any>
  requirements_hash: string
  proposal_hash: string
  scenario_hash: string
  shape_hash: string
  derived_expectations: Record<string, any> | null
  is_stale: boolean
  stale_artifacts: string[]
  created_at: string
}

export interface VocabularyEntry {
  id: number
  project_id: string | null
  category: string
  value: string
  origin: 'canonical' | 'project' | 'custom'
  evaluator_recognized: boolean
  description: string
}

export interface CreateProject {
  id: string
  workspace_id?: string
  name: string
  summary?: string
  domain?: string
  labels?: string[]
  project_type?: ProjectType
  integration_profile?: IntegrationProfile
}

export interface WorkspaceConnection {
  id: string
  workspace_id: string
  display_name: string
  backend_kind: IntegrationBackendKind
  system_kind: string
  endpoint_ref: string
  auth_mode: IntegrationAuthMode
  identity_provider_ref: string
  secret_ref: string
  allowed_project_refs: string[]
  metadata: Record<string, any>
  created_at: string
  updated_at: string
}

export interface IntegrationDiscoveryRecord {
  id: string
  project_id: string
  connection_id?: string | null
  operation_id: string
  backend_kind: IntegrationBackendKind
  method: string
  path_template: string
  side_effect_level: string
  input_schema_summary: Record<string, any>
  risk_notes: string[]
  data: Record<string, any>
  content_hash: string
  created_at: string
  updated_at: string
}

export interface ImportResult {
  imported: number
  errors: string[]
}

export interface AssistantExplanation {
  title: string
  summary: string
  focused_answer?: string | null
  action_label?: string | null
  action_path?: string | null
  highlights: string[]
  watchouts: string[]
  next_steps: string[]
}

export type StudioAssistantMode = 'pm' | 'dev'

export type DesignSectionSufficiencyStatus = 'ready' | 'draftable' | 'needs_clarification' | 'blocked'

export interface DesignSectionSufficiencyCard {
  key: string
  title: string
  status: DesignSectionSufficiencyStatus
  detail: string
  path: string
  action_label: string
  questions: string[]
}

export interface AssistantProposalItem {
  client_id: string
  title: string
  body: string
  confidence: 'low' | 'medium' | 'high'
  rationale: string
  structured_data?: Record<string, any>
}

export interface AssistantPatchCandidate {
  path: string
  op: 'add' | 'replace' | 'remove'
  value?: Record<string, any> | string | number | boolean | null
  rationale: string
}

export interface AssistantClarificationQuestion {
  question_id: string
  prompt: string
  why_it_matters: string
  target_artifact: string
  answer?: string
}

export interface AssistantCandidateBlocksProposal {
  proposal_kind: 'candidate_blocks'
  artifact_type: string
  items: AssistantProposalItem[]
}

export interface AssistantPatchCandidatesProposal {
  proposal_kind: 'patch_candidates'
  artifact_type: string
  patches: AssistantPatchCandidate[]
}

export interface AssistantClarificationQuestionsProposal {
  proposal_kind: 'clarification_questions'
  mode?: StudioAssistantMode
  section_key?: string
  questions: AssistantClarificationQuestion[]
}

export type AssistantProposal =
  | AssistantCandidateBlocksProposal
  | AssistantPatchCandidatesProposal
  | AssistantClarificationQuestionsProposal

export interface AssistantProposalEnvelope {
  title: string
  summary: string
  mode: StudioAssistantMode
  capability: string
  questions_for_user: string[]
  watchouts: string[]
  next_steps: string[]
  proposal: AssistantProposal
}

export type AssistantServiceGranularity = 'coarse' | 'balanced' | 'fine' | 'source_defined'

export interface AssistantServiceTopologyPreference {
  granularity: AssistantServiceGranularity
  target_service_count?: number | null
  preserve_source_services?: boolean
  rationale?: string
}

export interface IntentInterpretation {
  title: string
  summary: string
  recommended_shape_type: 'single_service' | 'multi_service' | string
  recommended_shape_reason: string
  requirements_focus: string[]
  scenario_starters: string[]
  domain_concepts: string[]
  service_suggestions: string[]
  next_steps: string[]
}

export interface PendingIntentDraft {
  source_intent: string
  interpretation: IntentInterpretation
}

export interface BusinessPacket {
  packet_kind: 'business_packet'
  version: 1
  profile: string
  source: {
    studio_area: 'product_design'
    project_id: string
    project_name: string
    requirements_id?: string | null
    scenario_id?: string | null
    shape_id?: string | null
    evaluation_id?: string | null
  }
  generated_at: string
  payload: {
    intent: {
      problem_statement: string
      goals: string[]
      non_goals: string[]
      intended_consumers: string[]
    }
    constraints: {
      business: string[]
      operational: string[]
      risk: string[]
      backend_preferences: string[]
    }
    scenarios: Array<{
      id: string
      title: string
      description: string
      expected_outcome?: string | null
    }>
    success_criteria: string[]
    current_posture: {
      recommended_shape?: string | null
      working_well: string[]
      needs_change: string[]
    }
    references: {
      requirements_snapshot: Record<string, any>
      scenario_snapshot: Record<string, any>
      shape_snapshot: Record<string, any>
      evaluation_snapshot: Record<string, any>
    }
  }
}

export interface DerivationReport {
  mapped_fields: string[]
  suggested_fields: string[]
  unresolved_fields: string[]
  notes: string[]
}

export interface DriftAnalysis {
  scenario_id: string
  expected_outcome?: string | null
  observed_outcome?: string | null
  gap_category:
    | 'business_intent_underspecified'
    | 'developer_binding_incomplete'
    | 'service_metadata_insufficient'
    | 'agent_planning_misaligned'
    | 'clarification_loop_detected'
    | 'restriction_mapping_missing'
    | 'approval_control_missing'
    | 'backend_semantics_mismatch'
  likely_owner:
    | 'business_design'
    | 'developer_design'
    | 'service_implementation'
    | 'adapter'
    | 'consuming_agent'
    | 'backend'
  fix_priority: 'low' | 'medium' | 'high'
  recommended_fix: string
  diagnostic_evidence: {
    capability_id?: string | null
    reason_code?: string | null
    agent_behavior?: string | null
    backend_context?: string | null
    observation_source?: string | null
    observed_at?: string | null
    service_metadata_artifact_id?: string | null
    service_metadata_mismatch?: string | null
  }
}

export type GlueAnalysis = DriftAnalysis

export type CoverageStatus =
  | 'not_addressed'
  | 'partially_addressed'
  | 'addressed'
  | 'deferred'
  | 'not_applicable'

export type DeveloperCoverageState =
  | 'not_started'
  | 'in_progress'
  | 'ready_for_pm_review'

export type PmReviewState = 'pending' | 'approved' | 'changes_requested'

export interface DeveloperBaselineData {
  artifact_type: 'developer_baseline'
  source_inputs: {
    product_revision_artifact_id?: string | null
    product_revision_number?: number | null
    product_design_hash?: string | null
    requirements_id: string | null
    requirements_hash: string | null
    scenario_ids: string[]
    primary_scenario_id: string | null
    scenario_set_hash: string | null
    shape_id: string | null
    shape_hash: string | null
  }
  locked_at: string
  note: string
}

export type DeveloperServiceGenerationMode =
  | 'from_service_design'
  | 'single_service_scaffold'
  | 'selected_services'

export type DeveloperScalabilityProfile =
  | 'single_instance'
  | 'stateless_horizontal'
  | 'control_plane_workers'
  | 'mixed'

export type DeveloperTransportProtocol =
  | 'anip_http'
  | 'grpc'
  | 'async_events'

export type DeveloperCodegenAdapter =
  | 'python_fastapi'
  | 'typescript_node'

export type DeveloperLayoutStrategy =
  | 'monorepo'
  | 'multi_repo'

export type DeveloperDeliveryModel =
  | 'embedded_existing_product'
  | 'standalone_service'
  | 'multiple_coordinated_services'

export type DeveloperArchitectureShape =
  | 'single_service'
  | 'multi_service_estate'

export type DeveloperScenarioStopCondition =
  | 'continue'
  | 'approval_required'
  | 'clarification_required'
  | 'safe_stop'
  | 'complete'

export type DeveloperScenarioStepKind =
  | 'capability_execution'
  | 'handoff_only'

export type DeveloperScenarioOutcomeType =
  | 'intermediate_result'
  | 'handoff'
  | 'approval_required'
  | 'clarification_required'
  | 'safe_stop'
  | 'completed'

export interface DeveloperScenarioOrchestrationStep {
  id: string
  service_id: string
  step_kind: DeveloperScenarioStepKind
  capability_id: string
  outcome_type: DeveloperScenarioOutcomeType
  outcome_notes: string
  stop_condition: DeveloperScenarioStopCondition
}

export interface DeveloperScenarioFormalization {
  scenario_id: string
  scenario_title: string
  scenario_key: string
  primary_capability: string
  actor_context: string
  business_scope: string
  time_scope: string
  side_effect_formalization: string
  expected_cost_formalization: string
  budget_guard_formalization: string
  permission_formalization: string
  task_tracking_formalization: string
  participating_service_ids: string[]
  orchestration_steps: DeveloperScenarioOrchestrationStep[]
  required_behaviors: string[]
  required_anip_support: string[]
  implementation_notes: string
}

export interface DeveloperActorExpectationBinding {
  id: string
  actor_id: string
  actor_title: string
  summary_formalization: string
  visibility_formalization: string
  action_formalization: string
  approval_formalization: string
}

export interface DeveloperCompositionRuleBinding {
  id: string
  rule: string
  affected_scenario_ids: string[]
  formalization_strategy: string
}

export type DeveloperCapabilityKind = 'atomic' | 'composed'

export type DeveloperGrantType = 'one_time' | 'session_bound'

export interface DeveloperGrantPolicy {
  allowed_grant_types: DeveloperGrantType[]
  default_grant_type: DeveloperGrantType
  expires_in_seconds: number
  max_uses: number
}

export interface DeveloperCompositionStep {
  id: string
  capability: string
  step_order?: number
  empty_result_source?: boolean
  empty_result_path?: string | null
}

export interface DeveloperComposition {
  authority_boundary: 'same_service' | 'same_package' | 'external_service'
  steps: DeveloperCompositionStep[]
  input_mapping: Record<string, Record<string, string>>
  output_mapping: Record<string, string>
  empty_result_policy?: 'return_success_no_results' | 'clarify' | 'deny' | null
  empty_result_output?: Record<string, unknown> | null
  failure_policy: {
    child_clarification: 'propagate' | 'fail_parent'
    child_denial: 'propagate' | 'fail_parent'
    child_approval_required: 'propagate' | 'fail_parent'
    child_error: 'propagate' | 'fail_parent'
  }
  audit_policy: {
    record_child_invocations: boolean
    parent_task_lineage: boolean
  }
}

export interface DeveloperPermissionIntentRuleBinding {
  id: string
  actor_id: string
  business_area: string
  business_area_label: string
  access_posture: string
  governed_outcome_type: string
  governed_outcome: string
  target_service_ids: string[]
  target_capability_ids?: string[]
  formalization_strategy: string
}

export type DeveloperImplementationFitCategory =
  | 'native_anip'
  | 'contract_gap'
  | 'custom_service_logic'
  | 'agent_app_glue'
  | 'external_integration'
  | 'unsupported'

export interface DeveloperImplementationFit {
  category: DeveloperImplementationFitCategory
  rationale: string
}

export interface DeveloperBusinessEffects {
  produces: string[]
  does_not_produce: string[]
}

export interface DeveloperCapabilityFormalization {
  id: string
  kind?: DeveloperCapabilityKind
  composition?: DeveloperComposition | null
  grant_policy?: DeveloperGrantPolicy | null
  source_kind: 'application_integration' | 'data_access' | 'contract_native'
  service_id: string
  capability_id: string
  title: string
  summary: string
  entity_targeted?: boolean
  subject_kind?: string
  context_type?: string
  output_intent?: string
  intent_type: string
  operation_type: string
  side_effect_level: string
  implementation_fit?: DeveloperImplementationFit
  business_effects?: DeveloperBusinessEffects
  minimum_scope?: string[]
  backend_operation: string
  path_template: string
  output_shape: string
  inputs: DeveloperCapabilityInputFormalization[]
}

export interface DeveloperIntegrationFrontingCapabilityMapping {
  id: string
  capability_id: string
  title: string
  intent: string
  service_id: string
  service_name: string
  backend_kind: IntegrationBackendKind
  connection_ref: string
  raw_operation_refs: string[]
  backend_bindings: DeveloperIntegrationFrontingBackendBinding[]
  execution_posture: string
  side_effect_level: string
  grant_policy?: DeveloperGrantPolicy | null
  subject_kind: string
  context_type: string
  output_intent: string
  business_effects?: DeveloperBusinessEffects
  required_inputs: string[]
  optional_inputs: string[]
  input_metadata?: DeveloperCapabilityInputFormalization[]
  backend_input_mode: BackendInputMode
  derived_required_backend_inputs: string[]
  derived_optional_backend_inputs: string[]
  explicit_required_backend_inputs: string[]
  explicit_optional_backend_inputs: string[]
  approval_rule_refs: string[]
  denial_rule_refs: string[]
  clarification_rule_refs: string[]
  audit_required: boolean
  outbound_controls?: Record<string, unknown>
}

export interface DeveloperIntegrationFrontingBackendBinding {
  backend_kind: IntegrationBackendKind
  connection_ref: string
  raw_operation_refs: string[]
  backend_input_mode?: BackendInputMode
  derived_required_backend_inputs?: string[]
  derived_optional_backend_inputs?: string[]
  explicit_required_backend_inputs?: string[]
  explicit_optional_backend_inputs?: string[]
  matched_discovery_record_ids?: string[]
  status?: 'ready' | 'stale' | 'missing'
  status_detail?: string
}

export interface DeveloperCapabilityInputFormalization {
  input_name: string
  input_type: string
  required: boolean
  summary: string
  default_value: string
  allowed_values: string[]
  semantic_type?: string
  input_format?: string
  validation_pattern?: string
  clarification_hint?: string
  entity_reference?: boolean
  reference_catalog?: string[]
  semantic_aliases?: string[]
  normalization_hint?: string
  normalization_context?: string
  allowed_value_semantics?: Array<{
    value: string
    aliases: string[]
  }>
  resolution?: DeveloperCapabilityInputResolution
  catalog_ref?: string
}

export type DeveloperCapabilityInputResolutionMode =
  | 'closed_values'
  | 'backend_resolved'
  | 'app_selected'
  | 'actor_policy'
  | 'actor_policy_or_explicit'
  | 'explicit_only'
  | 'clarify'

export type DeveloperCapabilityInputResolutionBehavior =
  | 'clarify'
  | 'use_default'
  | 'use_actor_scope'
  | 'app_select_or_clarify'
  | 'deny'
  | 'deny_or_clarify'
  | 'omit'

export interface DeveloperCapabilityInputResolution {
  mode: DeveloperCapabilityInputResolutionMode
  resolver_ref?: string
  on_missing?: DeveloperCapabilityInputResolutionBehavior
  on_ambiguous?: DeveloperCapabilityInputResolutionBehavior
  on_unresolved?: DeveloperCapabilityInputResolutionBehavior
}

export interface DeveloperServiceTopologyBinding {
  id: string
  service_id: string
  service_name: string
  source_role: string
  source_capabilities: string[]
  source_concepts: string[]
  formalized_capability_ids: string[]
  owned_concept_ids: string[]
  implementation_notes: string
}

export interface DeveloperDomainConceptBinding {
  id: string
  concept_id: string
  concept_name: string
  concept_detail: string
  technical_representation: string
}

export interface DeveloperApplicationIntegrationSafeDefaults {
  default_result_limit: number
  require_approval_for_writes: boolean
  require_clarification_on_ambiguous_record: boolean
  dry_run_before_write: boolean
}

export interface DeveloperApplicationIntegrationPermissionRule {
  rule_id: string
  scope_type: string
  scope_name: string
  actor_constraint: string
  purpose_constraint: string
  allowed: boolean
  summary: string
}

export interface DeveloperApplicationIntegrationClarificationRule {
  rule_id: string
  trigger_type: string
  capability_id: string
  summary: string
  prompt_hint: string
  enabled: boolean
}

export interface DeveloperApplicationIntegrationRestrictionRule {
  rule_id: string
  restriction_type: string
  capability_id: string
  summary: string
  value: string
  enabled: boolean
}

export interface DeveloperApplicationIntegrationDenialRule {
  rule_id: string
  denial_type: string
  capability_id: string
  summary: string
  enabled: boolean
}

export interface DeveloperApplicationIntegrationApprovalRule {
  rule_id: string
  capability_id: string
  required: boolean
  approver_type: string
  summary: string
}

export interface DeveloperApplicationIntegrationGovernanceFormalization {
  safe_defaults: DeveloperApplicationIntegrationSafeDefaults
  permission_rules: DeveloperApplicationIntegrationPermissionRule[]
  clarification_rules: DeveloperApplicationIntegrationClarificationRule[]
  restriction_rules: DeveloperApplicationIntegrationRestrictionRule[]
  denial_rules: DeveloperApplicationIntegrationDenialRule[]
  approval_rules: DeveloperApplicationIntegrationApprovalRule[]
}

export interface DeveloperDataAccessMetricRule {
  metric_key: string
  restricted_to_roles: string[]
  denied_roles: string[]
  notes: string
}

export interface DeveloperDataAccessDimensionRule {
  dimension_key: string
  restricted_to_roles: string[]
  denied_roles: string[]
  notes: string
}

export interface DeveloperDataAccessLimitRule {
  applies_to_roles: string[]
  grain: string
  max_rows: number
  notes: string
}

export interface DeveloperDataAccessUseRule {
  applies_to_roles: string[]
  export_allowed: boolean
  downstream_use: string
  downgrade_decision_grade: boolean
  notes: string
}

export interface DeveloperDataAccessClarificationRule {
  key: string
  enabled: boolean
  prompt_hint: string
}

export interface DeveloperDataAccessGovernanceFormalization {
  governed_outcomes: string[]
  metric_rules: DeveloperDataAccessMetricRule[]
  dimension_rules: DeveloperDataAccessDimensionRule[]
  limit_rules: DeveloperDataAccessLimitRule[]
  use_rules: DeveloperDataAccessUseRule[]
  clarification_rules: DeveloperDataAccessClarificationRule[]
}

export interface DeveloperDataMetricDefinition {
  key: string
  label: string
  description: string
}

export interface DeveloperDataDimensionDefinition {
  key: string
  label: string
  description: string
}

export interface DeveloperDataFilterDefinition {
  key: string
  label: string
  description: string
}

export interface DeveloperDataDomainFormalization {
  domain_name: string
  metrics: DeveloperDataMetricDefinition[]
  dimensions: DeveloperDataDimensionDefinition[]
  filters: DeveloperDataFilterDefinition[]
  grains: string[]
  result_modes: string[]
}

export interface DeveloperApplicationObjectFieldFormalization {
  field_name: string
  field_type: string
  required: boolean
  filterable: boolean
  writable: boolean
  sensitive: boolean
  summary: string
}

export interface DeveloperApplicationObjectRelationshipFormalization {
  relationship_name: string
  target_object_name: string
  cardinality: string
  summary: string
}

export interface DeveloperApplicationObjectFormalization {
  object_id: string
  name: string
  summary: string
  key_field: string
  fields: DeveloperApplicationObjectFieldFormalization[]
  relationships: DeveloperApplicationObjectRelationshipFormalization[]
  sensitive_field_names: string[]
}

export interface DeveloperSupportedQuestionFamilyBinding {
  id: string
  question_family: string
  target_service_ids: string[]
  verification_strategy: string
  evidence_signal: string
}

export interface DeveloperBusinessGoalBinding {
  id: string
  business_goal: string
  target_service_ids: string[]
  verification_strategy: string
  evidence_signal: string
}

export interface DeveloperNonGoalGuard {
  id: string
  non_goal: string
  guard_strategy: string
  evidence_signal: string
}

export interface DeveloperSuccessCriteriaCheck {
  id: string
  success_criterion: string
  evidence_expectation: string
  review_method: string
  verification_strategy: string
}

export interface DeveloperDataAccessScenarioPackExpectation {
  categories: string[]
  target_count: number
}

export interface DeveloperCompiledContractIdentity {
  artifact_name: string
  canonical_format: 'stable-json-v1'
  signature_algorithm: 'sha256'
  signature: string | null
  generated_at: string
}

export interface DeveloperDefinitionSavedRevision {
  revision_number: number
  revision_artifact_id: string
  previous_revision_artifact_id: string | null
  saved_at: string
}

export interface EvaluationObservedServiceEvidenceSummary {
  status: 'ready' | 'stale' | 'missing'
  label: string
  detail: string
  signature: string
  artifactId: string | null
  generationRunArtifactId: string | null
  generationDependencySource: 'local' | 'registry' | null
  service: string
  protocol: string
  profile: string
  capabilityCount: number
  source: string
  expectedServices: string[]
  expectedProtocols: string[]
  alignedCapabilities: string[]
  missingCapabilities: string[]
  extraCapabilities: string[]
}

export interface EvaluationEvidenceEnvelope {
  compiled_contract_identity: DeveloperCompiledContractIdentity | null
  generation_run_artifact_id: string | null
  generation_dependency_source: 'local' | 'registry' | null
  definition_revision_artifact_id: string | null
  definition_revision_number: number | null
  product_revision_artifact_id?: string | null
  product_revision_number?: number | null
  service_metadata_snapshot: ObservedServiceMetadata | null
  observed_service_evidence: EvaluationObservedServiceEvidenceSummary | null
  metadata_comparison: ServiceMetadataComparison | null
}

export interface DeveloperGeneratedArtifactOutput {
  kind: string
  title: string
  filename: string
  content_type: string
  generated_at: string
  content: string
  content_length: number
}

export interface DeveloperGeneratedServiceTarget {
  service_id: string
  service_name: string
  owned_capability_ids: string[]
  participating_scenario_ids: string[]
}

export interface DeveloperGeneratedCapabilityOwnership {
  capability_id: string
  service_id: string | null
  source_kind: string
}

export interface DeveloperGeneratedStructureSummary {
  service_ids: string[]
  protocols: string[]
  services: DeveloperGeneratedServiceTarget[]
  capability_ownership: DeveloperGeneratedCapabilityOwnership[]
  scenario_ids: string[]
  data_access_backend_type: string | null
  application_integration_backend_type: string | null
  integration_fronting_mapping_count: number
  generated_output_kinds: string[]
}

export interface DeveloperGeneratedIntegrationAdapterBinding {
  binding_id: string
  capability_id: string
  service_id: string
  service_name: string
  backend_kind: IntegrationBackendKind
  connection_ref: string
  raw_operation_refs: string[]
  backend_bindings: DeveloperIntegrationFrontingBackendBinding[]
  execution_posture: string
  side_effect_level: string
  subject_kind: string
  context_type: string
  output_intent: string
  required_inputs: string[]
  optional_inputs: string[]
  backend_input_mode: BackendInputMode
  derived_required_backend_inputs: string[]
  derived_optional_backend_inputs: string[]
  explicit_required_backend_inputs: string[]
  explicit_optional_backend_inputs: string[]
  governance: {
    approval_rule_refs: string[]
    denial_rule_refs: string[]
    clarification_rule_refs: string[]
    audit_required: boolean
  }
  outbound_controls?: Record<string, unknown>
}

export interface DeveloperGeneratedConformanceReport {
  report_kind: 'anip_local_conformance_report'
  generated_at: string
  service_definition_digest: string | null
  service_definition_digest_algorithm: string
  checks: Array<{
    id: string
    label: string
    status: 'passed' | 'failed'
    detail: string
  }>
  summary: {
    status: 'passed' | 'failed'
    passed: number
    failed: number
  }
}

export interface DeveloperGeneratedRuntimeCapability {
  capability_id: string
  title: string
  source_kind: string
  operation_type: string
  side_effect_level: string
  implementation_fit?: DeveloperImplementationFit
  business_effects?: DeveloperBusinessEffects
  backend_operation: string
  path_template: string
  output_shape: string
}

export interface DeveloperGeneratedRuntimeService {
  service_id: string
  service_name: string
  source_role: string
  protocols: string[]
  owned_concept_ids: string[]
  participating_scenario_ids: string[]
  orchestration_step_ids: string[]
  backend_bindings: string[]
  capabilities: DeveloperGeneratedRuntimeCapability[]
}

export interface DeveloperGeneratedRuntimeTarget {
  system_name: string
  domain_name: string
  delivery_model: string
  architecture_shape: string
  service_generation_mode: string
  protocols: string[]
  services: DeveloperGeneratedRuntimeService[]
  required_behavior_tokens: string[]
  required_anip_support_tokens: string[]
  extension_point_ids: string[]
}

export interface DeveloperExtensionPoint {
  id: string
  label: string
  ownership: 'generated' | 'generated_with_extension' | 'extension_only'
  plugin_surface: string
  rationale: string
}

export interface DeveloperGenerationRunData {
  artifact_type: 'developer_generation_run'
  launch_surface: 'developer_definition'
  generated_at: string
  compiled_contract_identity: DeveloperCompiledContractIdentity | null
  definition_revision_artifact_id: string | null
  definition_revision_number: number | null
  source_inputs: {
    product_revision_artifact_id?: string | null
    product_revision_number?: number | null
    product_design_hash?: string | null
    requirements_id: string | null
    requirements_hash: string | null
    scenario_ids: string[]
    scenario_set_hash: string | null
    shape_id: string | null
    shape_hash: string | null
    baseline_locked_at: string | null
  }
  generator_inputs: {
    runtime_target_mode: 'compiled_contract'
    primary_output_mode: 'runtime_target'
    dependency_source?: 'registry' | 'local'
    toolchain?: 'go_external'
    studio_generation_mode?: 'contract_projection_only'
    external_generator_required?: boolean
  }
  generated_structure: DeveloperGeneratedStructureSummary
  runtime_target: DeveloperGeneratedRuntimeTarget
  extension_manifest: DeveloperExtensionPoint[]
  outputs: {
    runtime_target: DeveloperGeneratedArtifactOutput[]
  }
}

export interface DeveloperServiceBackendBinding {
  service_id: string
  service_name: string
  uses_data_access_backend: boolean
  data_access_backend_type: string
  data_access_target_label: string
  uses_application_integration_backend: boolean
  application_integration_backend_type: string
  application_integration_system_name: string
  application_integration_environment: string
  application_integration_auth_type: string
  application_integration_adapter_target: string
}

export interface DeveloperDefinitionData {
  artifact_type: 'developer_definition'
  source_inputs: {
    product_revision_artifact_id?: string | null
    product_revision_number?: number | null
    product_design_hash?: string | null
    requirements_id: string | null
    requirements_hash: string | null
    scenario_ids: string[]
    scenario_set_hash: string | null
    shape_id: string | null
    shape_hash: string | null
    baseline_locked_at: string | null
  }
  product_alignment: {
    governed_behavior_formalization: string
    approval_posture_formalization: string
  }
  identity: {
    system_name: string
    domain_name: string
    delivery_model: DeveloperDeliveryModel
    architecture_shape: DeveloperArchitectureShape
    high_availability_required: boolean
  }
  authority: {
    trust_mode: string
    trust_checkpoints_required: boolean
    spending_actions_present: boolean
    irreversible_actions_present: boolean
    cost_visibility_required: boolean
    preflight_authority_discovery: boolean
    grantable_restrictions: boolean
    restricted_vs_denied: boolean
    delegation_tokens: boolean
    scoped_authority: boolean
    purpose_binding: boolean
    approval_expectation: string
    recovery_sensitive: boolean
    blocked_failure_posture: string
  }
  audit: {
    durable_records_required: boolean
    searchable_history_required: boolean
    invocation_tracking: boolean
    task_tracking: boolean
    parent_invocation_tracking: boolean
    client_reference_ids: boolean
    service_handoffs_required: boolean
    cross_service_reconstruction_required: boolean
    cross_service_continuity_required: boolean
  }
  backend_bindings: {
    data_access_backend_type: string
    data_access_target_label: string
    application_integration_backend_type: string
    application_integration_system_name: string
    application_integration_environment: string
    application_integration_auth_type: string
    application_integration_adapter_target: string
  }
  integration_fronting?: {
    project_type: ProjectType
    integration_profile: IntegrationProfile
    capability_mappings: DeveloperIntegrationFrontingCapabilityMapping[]
  }
  service_backend_bindings: DeveloperServiceBackendBinding[]
  application_integration_governance: DeveloperApplicationIntegrationGovernanceFormalization
  data_access_governance: DeveloperDataAccessGovernanceFormalization
  data_domain: DeveloperDataDomainFormalization
  domain_concept_bindings: DeveloperDomainConceptBinding[]
  application_object_model: DeveloperApplicationObjectFormalization[]
  capability_formalizations: DeveloperCapabilityFormalization[]
  service_topology_bindings: DeveloperServiceTopologyBinding[]
  actor_expectations: DeveloperActorExpectationBinding[]
  permission_intent_bindings: DeveloperPermissionIntentRuleBinding[]
  scenario_formalizations: DeveloperScenarioFormalization[]
  composition_rules: DeveloperCompositionRuleBinding[]
  verification: {
    supported_question_family_bindings: DeveloperSupportedQuestionFamilyBinding[]
    business_goal_bindings: DeveloperBusinessGoalBinding[]
    non_goal_guards: DeveloperNonGoalGuard[]
    success_criteria_checks: DeveloperSuccessCriteriaCheck[]
    data_access_scenario_pack: DeveloperDataAccessScenarioPackExpectation
  }
  generation: {
    service_generation_mode: DeveloperServiceGenerationMode
    selected_service_ids: string[]
    scalability_profile: DeveloperScalabilityProfile
    protocols: DeveloperTransportProtocol[]
    codegen_adapter: DeveloperCodegenAdapter
    layout_strategy: DeveloperLayoutStrategy
  }
  naming: {
    namespace: string
    package_prefix: string
    service_name_prefix: string
  }
  rationale: string
  compiled_contract_identity: DeveloperCompiledContractIdentity | null
  saved_revision: DeveloperDefinitionSavedRevision | null
  saved_at: string | null
}

export interface DeveloperDefinitionRevisionData extends Omit<DeveloperDefinitionData, 'artifact_type'> {
  artifact_type: 'developer_definition_revision'
}

export interface TraceabilityCoverageItem {
  id: string
  source: 'product_summary' | 'actor_model' | 'permission_intent' | 'non_goals' | 'success_criteria' | 'requirements' | 'scenario' | 'shape' | 'integration_fronting'
  section: string
  label: string
  detail: string
  status: CoverageStatus
  rationale: string
  linked_surfaces: string[]
  mapping_mode?: 'automatic' | 'manual'
  mapping_note?: string
  mapping_target_key?: string
  mapping_target_label?: string
  operator_resolution?: {
    choice_id: string
    applied_at: string
    target_artifact: string
    summary: string
    requires_review: boolean
    changes: string[]
  }
}

export type HighRiskConfirmationCategory =
  | 'clarification'
  | 'capability_identity'
  | 'service_ownership'
  | 'permission_mapping'
  | 'composition_ambiguity'
  | 'unsafe_boundary'
  | 'agent_readiness'

export type HighRiskConfirmationSeverity = 'blocker' | 'warning'

export interface HighRiskConfirmationItem {
  id: string
  category: HighRiskConfirmationCategory
  severity: HighRiskConfirmationSeverity
  title: string
  detail: string
  recommendation: string
  source: 'product_design' | 'developer_design' | 'assistant' | 'readiness'
  target_route?: string
  related_ids?: string[]
}

export interface HighRiskConfirmationReview {
  id: string
  status: 'confirmed' | 'deferred'
  note: string
  reviewed_at: string
}

export interface HighRiskConfirmationReport {
  artifact_type: 'high_risk_confirmations'
  generated_at: string
  summary: {
    total: number
    unresolved: number
    confirmed: number
    deferred: number
    blockers: number
    warnings: number
  }
  items: HighRiskConfirmationItem[]
  reviews?: Record<string, HighRiskConfirmationReview>
}

export interface TraceabilityRecordData {
  artifact_type: 'design_traceability'
  source_inputs: {
    requirements_id: string | null
    scenario_id: string | null
    scenario_ids?: string[]
    shape_id: string | null
    baseline_locked_at?: string | null
  }
  developer_status: DeveloperCoverageState
  developer_note: string
  developer_marked_at: string | null
  pm_review_status: PmReviewState
  pm_review_note: string
  pm_reviewed_at: string | null
  pm_review_contract_signature: string | null
  pm_review_generation_signature: string | null
  pm_review_generation_artifact_id: string | null
  pm_review_definition_revision_artifact_id?: string | null
  pm_review_definition_revision_number?: number | null
  pm_review_product_revision_artifact_id?: string | null
  pm_review_product_revision_number?: number | null
  pm_review_evaluation_signature: string | null
  pm_review_evaluation_id: string | null
  pm_review_observed_service_signature: string | null
  pm_review_observed_service_artifact_id: string | null
  coverage: TraceabilityCoverageItem[]
  high_risk_confirmations?: HighRiskConfirmationReport
  agent_consumption_readiness?: {
    artifact_type: 'agent_consumption_readiness'
    status: 'ready' | 'needs_review' | 'blocked'
    score: number
    summary: {
      blockers: number
      warnings: number
      info: number
      probes: number
      required_app_glue: number
    }
    findings: Array<Record<string, unknown>>
    probes: Array<Record<string, unknown>>
    required_app_glue: Array<Record<string, unknown>>
    finding_reviews?: Record<string, {
      id: string
      decision: 'contract_composition' | 'explicit_app_glue' | 'acceptable_warning' | 'follow_up'
      note: string
      reviewed_at: string
      review_method?: 'manual' | 'automation_harness'
    }>
  }
  agent_consumability_reviews?: Record<string, {
    capability_id: string
    reviewed_at: string
    intent_category?: string
    intent_summary?: string
    app_glue_required?: boolean
    app_glue_reason?: string
    intent_rules?: Array<{
      id: string
      meaning: string
      owner: 'product_contract' | 'developer_contract' | 'service' | 'agent_app_glue'
      applies_when?: string
      agent_action?: string
      service_behavior?: string
    }>
    business_language_rules?: Array<{
      id: string
      meaning: string
      owner: 'product_contract' | 'developer_contract' | 'service' | 'agent_app_glue'
      applies_when: {
        all_terms?: string[]
        any_terms?: string[]
        exclude_terms?: string[]
      }
      interpretation: string
      agent_action?: 'treat_as_supported' | 'treat_as_purpose' | 'prefer_capability' | 'clarify'
      target_capability?: string
      suppress_unsupported_effects?: string[]
    }>
  }>
}
