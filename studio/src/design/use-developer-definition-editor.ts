import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { ApplicationIntegrationProjectState } from '../application-integration/types'
import {
  createPmArtifact,
  updatePmArtifact,
} from './project-api'
import {
  buildDeveloperDefinitionContract,
  buildDeveloperDefinitionData,
  clearAssistantSeededFieldsForSection,
  DEVELOPER_DEFINITION_SECTIONS,
  developerDefinitionArtifactId,
  developerDefinitionRevisionArtifactId,
  developerDefinitionMatchesCurrentContext,
  developerDefinitionTargetStatus,
  findDeveloperDefinitionArtifact,
  findLatestDeveloperDefinitionRevisionArtifact,
  stableStringify,
  summarizeAssistantSeededFields,
  summarizeCoverageForDefinitionSection,
  validateDeveloperDefinitionRequiredFields,
} from './developer-definition'
import {
  buildHighRiskConfirmationReport,
  highRiskConfirmationReportFromArtifacts,
  unresolvedHighRiskConfirmationItems,
} from './high-risk-confirmations'
import type {
  ArtifactRecord,
  DeveloperCapabilityFormalization,
  DeveloperArchitectureShape,
  DeveloperBaselineData,
  DeveloperCodegenAdapter,
  DeveloperCompiledContractIdentity,
  DeveloperDefinitionData,
  DeveloperDefinitionRevisionData,
  DeveloperDefinitionSavedRevision,
  DeveloperDeliveryModel,
  DeveloperLayoutStrategy,
  DeveloperScalabilityProfile,
  DeveloperScenarioFormalization,
  DeveloperScenarioOrchestrationStep,
  DeveloperScenarioOutcomeType,
  DeveloperScenarioStepKind,
  DeveloperScenarioStopCondition,
  DeveloperServiceGenerationMode,
  DeveloperTransportProtocol,
  TraceabilityCoverageItem,
  TraceabilityRecordData,
} from './project-types'
import { loadProject, projectStore } from './project-store'
import type { ScenarioAdditionalContextEntry, ScenarioAdditionalContextSemanticType } from './types'
import {
  analyzeAgentConsumptionReadiness,
  applyReadinessFindingReviews,
  normalizeReadinessFindingReviews,
} from './agent-consumption-readiness'
import {
  buildTraceabilityRecord,
  developerBaselineMatchesCurrentContext,
  findDeveloperBaselineArtifact,
  findTraceabilityArtifact,
  hasReviewedCoverageResolution,
  summarizeCoverage,
  traceabilityArtifactId,
} from './traceability'

const APPLICATION_INTEGRATION_BACKEND_TYPES = new Set([
  'rest_api',
  'graphql_api',
  'mcp_server',
  'internal_http_service',
  'custom_adapter',
])
const APPLICATION_INTEGRATION_ENVIRONMENTS = new Set(['development', 'staging', 'production'])
const APPLICATION_INTEGRATION_AUTH_TYPES = new Set([
  'none',
  'api_key',
  'bearer_token',
  'oauth2',
  'session_cookie',
  'custom',
])
const APPLICATION_INTEGRATION_PERMISSION_SCOPE_TYPES = new Set(['object', 'field', 'capability'])
const APPLICATION_INTEGRATION_CLARIFICATION_TRIGGER_TYPES = new Set([
  'ambiguous_record',
  'ambiguous_object',
  'missing_required_input',
  'ambiguous_assignee',
  'ambiguous_due_date',
])
const APPLICATION_INTEGRATION_RESTRICTION_TYPES = new Set([
  'result_limit',
  'field_projection',
  'allowed_assignees',
  'supported_object_subset',
])
const APPLICATION_INTEGRATION_DENIAL_TYPES = new Set([
  'unsupported_object',
  'forbidden_field',
  'forbidden_mutation',
  'missing_purpose',
  'authority_missing',
])
const APPLICATION_INTEGRATION_APPROVER_TYPES = new Set(['user', 'manager', 'system_policy'])

export function normalizeApplicationIntegrationBackendType(value: string): ApplicationIntegrationProjectState['backend']['backendType'] {
  return APPLICATION_INTEGRATION_BACKEND_TYPES.has(value)
    ? value as ApplicationIntegrationProjectState['backend']['backendType']
    : 'custom_adapter'
}

export function normalizeApplicationIntegrationEnvironment(value: string): ApplicationIntegrationProjectState['backend']['environment'] {
  return APPLICATION_INTEGRATION_ENVIRONMENTS.has(value)
    ? value as ApplicationIntegrationProjectState['backend']['environment']
    : 'production'
}

export function normalizeApplicationIntegrationAuthType(value: string): ApplicationIntegrationProjectState['backend']['authType'] {
  return APPLICATION_INTEGRATION_AUTH_TYPES.has(value)
    ? value as ApplicationIntegrationProjectState['backend']['authType']
    : 'custom'
}

export function normalizeApplicationIntegrationPermissionScopeType(
  value: string,
): ApplicationIntegrationProjectState['governance']['permissionRules'][number]['scopeType'] {
  const candidate = value.trim().toLowerCase()
  if (APPLICATION_INTEGRATION_PERMISSION_SCOPE_TYPES.has(candidate)) {
    return candidate as ApplicationIntegrationProjectState['governance']['permissionRules'][number]['scopeType']
  }
  return 'capability'
}

export function normalizeApplicationIntegrationClarificationTriggerType(
  value: string,
): ApplicationIntegrationProjectState['governance']['clarificationRules'][number]['triggerType'] {
  const candidate = value.trim().toLowerCase()
  if (APPLICATION_INTEGRATION_CLARIFICATION_TRIGGER_TYPES.has(candidate)) {
    return candidate as ApplicationIntegrationProjectState['governance']['clarificationRules'][number]['triggerType']
  }
  if (candidate.includes('assignee')) return 'ambiguous_assignee'
  if (candidate.includes('date') || candidate.includes('due')) return 'ambiguous_due_date'
  if (candidate.includes('record')) return 'ambiguous_record'
  if (candidate.includes('object')) return 'ambiguous_object'
  return 'missing_required_input'
}

export function normalizeApplicationIntegrationRestrictionType(
  value: string,
): ApplicationIntegrationProjectState['governance']['restrictionRules'][number]['restrictionType'] {
  const candidate = value.trim().toLowerCase()
  if (APPLICATION_INTEGRATION_RESTRICTION_TYPES.has(candidate)) {
    return candidate as ApplicationIntegrationProjectState['governance']['restrictionRules'][number]['restrictionType']
  }
  if (candidate.includes('limit')) return 'result_limit'
  if (candidate.includes('field')) return 'field_projection'
  if (candidate.includes('assignee')) return 'allowed_assignees'
  return 'supported_object_subset'
}

export function normalizeApplicationIntegrationDenialType(
  value: string,
): ApplicationIntegrationProjectState['governance']['denialRules'][number]['denialType'] {
  const candidate = value.trim().toLowerCase()
  if (APPLICATION_INTEGRATION_DENIAL_TYPES.has(candidate)) {
    return candidate as ApplicationIntegrationProjectState['governance']['denialRules'][number]['denialType']
  }
  if (candidate.includes('field')) return 'forbidden_field'
  if (candidate.includes('mutation') || candidate.includes('write')) return 'forbidden_mutation'
  if (candidate.includes('purpose')) return 'missing_purpose'
  if (candidate.includes('object')) return 'unsupported_object'
  return 'authority_missing'
}

export function normalizeApplicationIntegrationApproverType(
  value: string,
): ApplicationIntegrationProjectState['governance']['approvalRules'][number]['approverType'] {
  const candidate = value.trim().toLowerCase()
  if (APPLICATION_INTEGRATION_APPROVER_TYPES.has(candidate)) {
    return candidate as ApplicationIntegrationProjectState['governance']['approvalRules'][number]['approverType']
  }
  if (candidate.includes('manager') || candidate.includes('leader')) return 'manager'
  if (candidate.includes('policy') || candidate.includes('system')) return 'system_policy'
  return 'user'
}

export const SERVICE_GENERATION_OPTIONS: Array<{ value: DeveloperServiceGenerationMode; label: string; description: string }> = [
  {
    value: 'from_service_design',
    label: 'Generate From Service Design',
    description: 'Generate one scaffold per selected service boundary in the locked Service Design.',
  },
  {
    value: 'single_service_scaffold',
    label: 'Collapse To One Service',
    description: 'Generate one service scaffold even if Product Design currently models multiple service boundaries.',
  },
  {
    value: 'selected_services',
    label: 'Generate Selected Services Only',
    description: 'Generate only the explicitly selected subset of service boundaries.',
  },
]

export const DELIVERY_MODEL_OPTIONS: Array<{ value: DeveloperDeliveryModel; label: string; description: string }> = [
  {
    value: 'embedded_existing_product',
    label: 'Embedded in existing product',
    description: 'Treat the generated ANIP surface as part of an existing product or platform boundary.',
  },
  {
    value: 'standalone_service',
    label: 'One standalone service',
    description: 'Treat the generated ANIP surface as one primary deployable service.',
  },
  {
    value: 'multiple_coordinated_services',
    label: 'Multiple coordinated services',
    description: 'Treat the generated implementation as multiple bounded services that coordinate together.',
  },
]

export const ARCHITECTURE_SHAPE_OPTIONS: Array<{ value: DeveloperArchitectureShape; label: string; description: string }> = [
  {
    value: 'single_service',
    label: 'Single service',
    description: 'One generated service boundary is expected to carry the implementation.',
  },
  {
    value: 'multi_service_estate',
    label: 'Multiple service boundaries',
    description: 'Multiple generated service boundaries are expected to exist in the final implementation.',
  },
]

export const SCALABILITY_OPTIONS: Array<{ value: DeveloperScalabilityProfile; label: string; description: string }> = [
  {
    value: 'single_instance',
    label: 'Single Instance',
    description: 'Generate scaffolds assuming one running service instance and no scale-specific topology.',
  },
  {
    value: 'stateless_horizontal',
    label: 'Stateless Horizontal Scale',
    description: 'Generate stateless service scaffolds intended to run behind replicas/load balancing.',
  },
  {
    value: 'control_plane_workers',
    label: 'Control Plane + Workers',
    description: 'Generate scaffolds expecting coordinator and worker roles or separate async execution paths.',
  },
  {
    value: 'mixed',
    label: 'Mixed Posture',
    description: 'Keep scaling requirements explicit in the contract because different services will scale differently.',
  },
]

export const PROTOCOL_OPTIONS: Array<{ value: DeveloperTransportProtocol; label: string; description: string }> = [
  {
    value: 'anip_http',
    label: 'ANIP over HTTP',
    description: 'Expose generated services as ANIP-discoverable HTTP services with manifests, capability metadata, and invoke surfaces.',
  },
  {
    value: 'grpc',
    label: 'gRPC',
    description: 'Generate gRPC-facing service surfaces or adapters in addition to ANIP-facing behavior.',
  },
  {
    value: 'async_events',
    label: 'Async Events',
    description: 'Generate event-driven or background-processing stubs alongside request/response surfaces.',
  },
]

export const ADAPTER_OPTIONS: Array<{ value: DeveloperCodegenAdapter; label: string; description: string }> = [
  {
    value: 'python_fastapi',
    label: 'Python + FastAPI',
    description: 'Generate Python ANIP scaffolds using the FastAPI integration path.',
  },
  {
    value: 'typescript_node',
    label: 'TypeScript + Node',
    description: 'Generate TypeScript/Node ANIP scaffolds for service implementations and adapters.',
  },
]

export const LAYOUT_OPTIONS: Array<{ value: DeveloperLayoutStrategy; label: string; description: string }> = [
  {
    value: 'monorepo',
    label: 'Monorepo Layout',
    description: 'Emit generated artifacts into one shared repo layout with multiple services or packages.',
  },
  {
    value: 'multi_repo',
    label: 'Multi-Repo Layout',
    description: 'Structure generation for separate service repositories or independently-owned codebases.',
  },
]

export const DATA_ACCESS_BACKEND_BINDING_OPTIONS = [
  { value: 'curated_sql', label: 'Curated SQL' },
  { value: 'cube_rest', label: 'Cube REST' },
  { value: 'snowflake_sql', label: 'Snowflake SQL' },
  { value: 'snowflake_semantic', label: 'Snowflake Semantic' },
  { value: 'databricks_sql', label: 'Databricks SQL' },
  { value: 'databricks_genie', label: 'Databricks Genie' },
  { value: 'dbt_semantic', label: 'dbt Semantic' },
  { value: 'internal_metrics_api', label: 'Internal Metrics API' },
  { value: 'custom_adapter', label: 'Custom Adapter' },
] as const

export const APPLICATION_INTEGRATION_BACKEND_BINDING_OPTIONS = [
  { value: 'rest_api', label: 'REST API' },
  { value: 'graphql_api', label: 'GraphQL API' },
  { value: 'mcp_server', label: 'MCP Server' },
  { value: 'internal_http_service', label: 'Internal HTTP Service' },
  { value: 'custom_adapter', label: 'Custom Adapter' },
] as const

export const APPLICATION_INTEGRATION_ENVIRONMENT_OPTIONS = [
  { value: 'development', label: 'Development' },
  { value: 'staging', label: 'Staging' },
  { value: 'production', label: 'Production' },
] as const

export const APPLICATION_INTEGRATION_AUTH_TYPE_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'api_key', label: 'API Key' },
  { value: 'bearer_token', label: 'Bearer Token' },
  { value: 'oauth2', label: 'OAuth2' },
  { value: 'session_cookie', label: 'Session Cookie' },
  { value: 'custom', label: 'Custom' },
] as const

export const STOP_CONDITION_OPTIONS: Array<{ value: DeveloperScenarioStopCondition; label: string; description: string }> = [
  { value: 'continue', label: 'Continue', description: 'This step continues into the next step when it succeeds.' },
  { value: 'approval_required', label: 'Approval Required', description: 'This step must stop and return an approval-required outcome before execution continues.' },
  { value: 'clarification_required', label: 'Clarification Required', description: 'This step must stop and request clarification before execution continues.' },
  { value: 'safe_stop', label: 'Safe Stop', description: 'This step stops safely without pretending the scenario completed.' },
  { value: 'complete', label: 'Complete', description: 'This step is the successful end of the scenario flow.' },
]

export const STEP_KIND_OPTIONS: Array<{ value: DeveloperScenarioStepKind; label: string; description: string }> = [
  { value: 'capability_execution', label: 'Executable Capability Step', description: 'This step should bind to a concrete ANIP capability and generate executable service behavior.' },
  { value: 'handoff_only', label: 'Handoff Only', description: 'This step represents a service handoff or boundary. It does not bind directly to a concrete capability.' },
]

export const OUTCOME_TYPE_OPTIONS: Array<{ value: DeveloperScenarioOutcomeType; label: string; description: string }> = [
  { value: 'intermediate_result', label: 'Intermediate Result', description: 'The step produces a normal intermediate result and the flow continues.' },
  { value: 'handoff', label: 'Handoff', description: 'The step hands work to another service or boundary without directly executing a capability.' },
  { value: 'approval_required', label: 'Approval Required', description: 'The step returns an approval-required outcome before execution continues.' },
  { value: 'clarification_required', label: 'Clarification Required', description: 'The step returns a clarification-required outcome before execution continues.' },
  { value: 'safe_stop', label: 'Safe Stop', description: 'The step stops safely without pretending the scenario completed.' },
  { value: 'completed', label: 'Completed', description: 'The step successfully completes the scenario or a major terminal branch.' },
]

export const SCENARIO_FORMALIZATION_FIELD_GUIDE = [
  {
    field: 'Primary Capability',
    definition: 'The main capability or action this scenario is testing or driving.',
    usage: 'Generation uses this as the primary capability anchor for this scenario entry. Verification uses it to know which capability outcome to inspect first.',
    predefined: 'Pre-filled from Product Design only when the scenario already names a capability in guided context. Otherwise developer-defined.',
  },
  {
    field: 'Actor Context',
    definition: 'The actor or caller posture this scenario assumes.',
    usage: 'Use this when behavior depends on who is calling, such as trust, approval, restriction, or role-based visibility.',
    predefined: 'Pre-filled when Product Design marks an Additional Context entry as Actor Context. Otherwise developer-defined.',
  },
  {
    field: 'Business Scope',
    definition: 'The business slice this scenario is limited to, such as region, account segment, team, or ownership boundary.',
    usage: 'Use this only when readiness or verification needs a business boundary. Runtime enforcement belongs in capability, policy, or service behavior.',
    predefined: 'Pre-filled when Product Design marks an Additional Context entry as Business Scope. Otherwise developer-defined.',
  },
  {
    field: 'Time Scope',
    definition: 'The time window or period the scenario depends on.',
    usage: 'Use this only when readiness or verification needs an explicit time boundary such as a quarter, date range, or reporting period.',
    predefined: 'Pre-filled when Product Design marks an Additional Context entry as Time Scope. Otherwise developer-defined.',
  },
  {
    field: 'Participating Services',
    definition: 'The services that actually participate in this scenario.',
    usage: 'This narrows scenario coverage to the relevant service boundaries. Verification should not assume every service participates just because the project has multiple services.',
    predefined: 'Pre-filled first from the Product Design Participating Services field, and secondarily from typed Additional Context entries kept for backward compatibility. Developers can refine the final list.',
  },
  {
    field: 'Orchestration Steps',
    definition: 'The structured ordered steps or handoffs the implementation is expected to preserve.',
    usage: 'Readiness and verification use these explicit step rows, not free text, to flag where cross-service behavior, stop points, and capability ownership need review.',
    predefined: 'Pre-filled from Product Design orchestration text when available, then refined by developers into structured step rows.',
  },
  {
    field: 'Required Behaviors',
    definition: 'The scenario outcomes or safety properties the implementation must preserve.',
    usage: 'These are scenario-level expectations. Select only behaviors that should be checked or intentionally mapped into capability, policy, or app-glue decisions.',
    predefined: 'Pre-populated and selected by default from Product Design scenario expectations. Developers can refine the final contract only if they intentionally need to narrow it.',
  },
  {
    field: 'Required ANIP Support',
    definition: 'The protocol-visible ANIP support the implementation must expose for this scenario.',
    usage: 'These are scenario-level protocol expectations, not global service flags. Select the ANIP-visible outcomes and metadata that readiness or verification should look for.',
    predefined: 'Pre-populated and selected by default from Product Design scenario expectations. Developers can refine the final contract only if they intentionally need to narrow it.',
  },
]

export const SCENARIO_CORE_FIELD_GUIDE = SCENARIO_FORMALIZATION_FIELD_GUIDE.filter((entry) =>
  ['Primary Capability', 'Actor Context', 'Business Scope', 'Time Scope'].includes(entry.field),
)

export const SCENARIO_FORMALIZATION_HELP: Record<string, {
  title: string
  summary: string
  inlineDetails: string[]
  bullets: string[]
  example?: string
}> = {
  coreFields: {
    title: 'Core Scenario Fields',
    summary: 'These fields turn one PM scenario into explicit coverage evidence that readiness and verification can use.',
    inlineDetails: [
      'Fill these only with values that materially affect scenario coverage or review.',
      'Product Design may prefill some values. Developers refine them into exact reviewable identifiers and boundaries.',
    ],
    bullets: [
      'Primary Capability names the main capability this scenario is exercising.',
      'Actor Context is only for caller-specific policy, approval, or visibility behavior.',
      'Business Scope is for business boundaries like region, tenant, segment, or ownership scope that the implementation must preserve.',
      'Time Scope is only for scenarios that depend on an explicit time boundary such as a quarter or reporting window.',
    ],
    example: 'A quarterly approval scenario might target capability `operations.prepare_action_preview`, actor context `regional_manager`, business scope `enterprise_segment`, and time scope `fy2026_q2`.',
  },
  participatingServices: {
    title: 'Participating Services',
    summary: 'This is the set of service boundaries that actually participate in this scenario.',
    inlineDetails: [
      'It is scenario-level, not project-global. A multi-service project does not imply every scenario touches every service.',
      'Studio uses this to make scenario coverage and verification ownership explicit.',
    ],
    bullets: [
      'These values are prefilled from Product Design Participating Services when available.',
      'Keep the list narrow. Only include services that must participate for this scenario to be implemented correctly.',
      'Verification later uses the same set to know where behavior, lineage, or handoffs should appear.',
    ],
    example: 'A bounded action-preparation scenario may involve `eligibility-review` and `notification-drafting`, but not `billing`.',
  },
  orchestrationSteps: {
    title: 'Orchestration Steps',
    summary: 'This is the structured scenario flow that readiness and verification should preserve as reviewed intent.',
    inlineDetails: [
      'Each row is one explicit step in execution order.',
      'Use service, step kind, capability binding, structured outcome type, and stop condition so Studio does not have to guess from prose.',
    ],
    bullets: [
      'This is how multi-step behavior becomes explicit instead of being guessed from narrative text.',
      'Readiness and verification use these rows to identify cross-service behavior, stop points, and handoffs.',
      'Each step should be specific enough that reviewers can decide whether the behavior belongs in a capability, a policy, service code, or app glue.',
    ],
    example: 'Step 1: service `eligibility-review`, step kind `capability execution`, capability `operations.prepare_assignment_preview`, outcome type `approval required`, stop condition `approval_required`.',
  },
  orchestrationStepFields: {
    title: 'Orchestration Step Fields',
    summary: 'Each step row needs enough structure that Studio can review the behavior without reading free text.',
    inlineDetails: [
      'Service tells Studio which service boundary owns or performs the step.',
      'Step Kind tells Studio whether the step binds to a real capability or is only a service handoff.',
      'Capability ID names the exact capability surface for executable steps.',
      'Outcome Type states the structured result this step produces or returns before the flow continues or stops.',
      'Outcome Notes are optional explanatory notes and do not drive generation directly.',
      'Stop Condition tells Studio whether the step continues normally, stops for approval, asks for clarification, stops safely, or completes the scenario.',
    ],
    bullets: [
      'Service is the implementation boundary for the step.',
      'Step Kind = Executable Capability Step means Capability ID becomes required because scenario coverage needs a concrete ANIP surface to review.',
      'Step Kind = Handoff Only means the step represents a service transition or boundary and does not require Capability ID.',
      'Outcome Type is structured review data. Outcome Notes are only explanatory context for humans and verification review.',
      'Studio uses Service + Step Kind + Capability ID + Outcome Type + Stop Condition to keep scenario coverage deterministic.',
    ],
    example: 'Service `notification-drafting`, step kind `capability execution`, capability `operations.prepare_followup_preview`, outcome type `approval required`, stop condition `approval_required`.',
  },
  requiredBehaviors: {
    title: 'Required Behaviors',
    summary: 'These are the scenario-level behaviors readiness and verification should preserve.',
    inlineDetails: [
      'They come from Product Design and are selected by default for fresh or reset developer definitions.',
      'They do not automatically apply to every service. Participating services, orchestration, and capability choice determine where each behavior lands.',
    ],
    bullets: [
      'Use this list to keep scenario outcomes explicit and verifiable.',
      'A behavior here should correspond to something the implementation must preserve, not a vague aspiration.',
      'If a PM-selected behavior is intentionally out of scope for ANIP-native behavior, that should be handled consciously, not silently dropped.',
    ],
    example: 'For a safe-stop scenario, the required behavior may be `clarification required before final execution`.',
  },
  requiredAnipSupport: {
    title: 'Required ANIP Support',
    summary: 'These are the protocol-visible ANIP outcomes, metadata, and semantics that must be exposed for this scenario.',
    inlineDetails: [
      'They come from Product Design and are selected by default for fresh or reset developer definitions.',
      'They are scenario-level expectations, not blanket flags for every generated service.',
    ],
    bullets: [
      'Use this list for explicit outcomes like approval required, clarification required, auditable execution path, or bounded capability contracts.',
      'Capability Formalization, policy, and service behavior decide where these expectations become runtime behavior.',
      'Verification later checks these as contract-visible behavior, not hidden implementation details.',
    ],
    example: 'A governed write scenario may require `approval_required_outcome` and `auditable_execution_path` to be visible on the ANIP surface.',
  },
  implementationNotes: {
    title: 'Implementation Notes',
    summary: 'Use this for technical notes that clarify how the scenario should be implemented without changing the formal contract fields above.',
    inlineDetails: [
      'Keep this concise and implementation-facing.',
      'Use it for ownership notes, stop conditions, temporary constraints, or non-obvious technical caveats.',
    ],
    bullets: [
      'This field supplements the contract. It should not replace a missing formal field.',
      'If a fact affects generation or verification deterministically, put it in a structured field instead of burying it here.',
    ],
    example: 'Route through the prioritization service first because scoring logic is owned there, but stop before the downstream execution call.',
  },
}

function humanizeContractValue(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function semanticTypeLabel(semanticType: ScenarioAdditionalContextSemanticType): string {
  const labels: Record<ScenarioAdditionalContextSemanticType, string> = {
    descriptive_only: 'Descriptive Only',
    actor_context: 'Actor Context',
    business_scope: 'Business Scope',
    time_scope: 'Time Scope',
    participating_services: 'Participating Services',
    orchestration_step: 'Orchestration Step',
  }
  return labels[semanticType]
}

function normalizeSemanticType(entry: Record<string, any>): ScenarioAdditionalContextSemanticType {
  const semanticType = String(entry.semantic_type ?? '').trim()
  if (
    semanticType === 'actor_context'
    || semanticType === 'business_scope'
    || semanticType === 'time_scope'
    || semanticType === 'participating_services'
    || semanticType === 'orchestration_step'
    || semanticType === 'descriptive_only'
  ) {
    return semanticType
  }
  return 'descriptive_only'
}

function newOrchestrationStep(index: number): DeveloperScenarioOrchestrationStep {
  return {
    id: `step_${index + 1}`,
    service_id: '',
    step_kind: 'capability_execution',
    capability_id: '',
    outcome_type: 'intermediate_result',
    outcome_notes: '',
    stop_condition: 'continue',
  }
}

export function useDeveloperDefinitionEditor() {
  const route = useRoute()
  const projectId = computed(() => route.params.projectId as string)
  const project = computed(() => projectStore.activeProject)
  const requirements = computed(() => projectStore.artifacts.requirements)
  const scenarios = computed(() => projectStore.artifacts.scenarios)
  const shapes = computed(() => projectStore.artifacts.shapes)

  const loadingDrafts = ref(false)
  const saving = ref(false)
  const loadError = ref<string | null>(null)
  const saveError = ref<string | null>(null)
  const draft = ref<DeveloperDefinitionData | null>(null)
  const expandedScenarioHelpCards = ref<Record<string, boolean>>({})
  const activeScenarioHelpCard = ref<string | null>(null)

  async function ensureLoaded() {
    if (!projectId.value) return
    if (projectStore.activeProject?.id === projectId.value) return
    await loadProject(projectId.value)
  }

  const currentRequirements = computed(() =>
    requirements.value.find((item) => item.role === 'primary')
    ?? requirements.value[0]
    ?? null,
  )

  const currentShape = computed(() =>
    shapes.value.find((item) => item.id === projectStore.activeShapeId)
    ?? (shapes.value.length === 1 ? shapes.value[0] : null)
    ?? shapes.value[0]
    ?? null,
  )

  const currentScenarios = computed(() => scenarios.value)

  const baselineArtifact = computed(() => findDeveloperBaselineArtifact(projectStore.artifacts.pmArtifacts))
  const baseline = computed(() =>
    (baselineArtifact.value?.data as DeveloperBaselineData | undefined) ?? null,
  )
  const baselineAligned = computed(() =>
    developerBaselineMatchesCurrentContext({
      baseline: baseline.value,
      requirements: currentRequirements.value,
      scenarios: currentScenarios.value,
      shape: currentShape.value,
      pmArtifacts: projectStore.artifacts.pmArtifacts,
    }),
  )

  const lockedRequirements = computed(() =>
    requirements.value.find((item) => item.id === baseline.value?.source_inputs.requirements_id)
    ?? null,
  )

  const lockedScenarios = computed(() =>
    (baseline.value?.source_inputs.scenario_ids ?? [])
      .map((id) => scenarios.value.find((item) => item.id === id) ?? null)
      .filter((item): item is NonNullable<typeof item> => item != null),
  )

  const lockedShape = computed(() =>
    shapes.value.find((item) => item.id === baseline.value?.source_inputs.shape_id)
    ?? null,
  )

  const traceabilityArtifact = computed(() => findTraceabilityArtifact(projectStore.artifacts.pmArtifacts))
  const traceabilityRecord = computed(() =>
    (traceabilityArtifact.value?.data as TraceabilityRecordData | undefined) ?? null,
  )

  const definitionArtifact = computed(() => findDeveloperDefinitionArtifact(projectStore.artifacts.pmArtifacts))
  const latestDefinitionRevisionArtifact = computed(() =>
    findLatestDeveloperDefinitionRevisionArtifact(projectStore.artifacts.pmArtifacts),
  )
  const savedDefinition = computed(() =>
    (definitionArtifact.value?.data as DeveloperDefinitionData | undefined) ?? null,
  )
  const requiresLockedShape = computed(() => project.value?.project_type !== 'governed_service_project')

  const definitionReady = computed(() =>
    !!project.value
    && !!baseline.value
    && baselineAligned.value
    && !!lockedRequirements.value
    && lockedScenarios.value.length > 0
    && (!requiresLockedShape.value || !!lockedShape.value),
  )

  function syncDraft() {
    if (!project.value || !definitionReady.value) {
      draft.value = null
      return
    }
    const existingDefinition = savedDefinition.value ?? draft.value
    draft.value = buildDeveloperDefinitionData({
      project: project.value,
      baseline: baseline.value,
      requirements: lockedRequirements.value,
      scenarios: lockedScenarios.value,
      shape: lockedShape.value,
      pmArtifacts: projectStore.artifacts.pmArtifacts,
      existing: existingDefinition,
    })
  }

  function resetDefinition() {
    saveError.value = null
    syncDraft()
  }

  onMounted(async () => {
    await ensureLoaded()
    syncDraft()
  })

  watch(
    () => [
      projectId.value,
      traceabilityArtifact.value?.updated_at,
      baseline.value?.locked_at,
      definitionArtifact.value?.updated_at,
      latestDefinitionRevisionArtifact.value?.updated_at,
    ] as const,
    async () => {
      await ensureLoaded()
      syncDraft()
    },
  )

  const serviceOptions = computed(() => {
    const shapeData = ((lockedShape.value?.data?.shape ?? lockedShape.value?.data) as Record<string, any> | undefined) ?? {}
    const services = Array.isArray(shapeData.services) ? shapeData.services : []
    return services.map((service: Record<string, any>) => ({
      id: String(service.id ?? ''),
      label: String(service.name ?? service.id ?? 'Service'),
    })).filter((item) => item.id)
  })

  const definitionAligned = computed(() =>
    developerDefinitionMatchesCurrentContext({
      definition: savedDefinition.value,
      baseline: baseline.value,
      requirements: lockedRequirements.value,
      scenarios: lockedScenarios.value,
      shape: lockedShape.value,
    }),
  )

  const definitionContractBase = computed(() => {
    if (!project.value || !definitionReady.value || !draft.value) return null
    return buildDeveloperDefinitionContract({
      project: project.value,
      baseline: baseline.value,
      requirements: lockedRequirements.value,
      scenarios: lockedScenarios.value,
      shape: lockedShape.value,
      traceability: traceabilityRecord.value,
      developerDefinition: draft.value,
    })
  })

  const definitionContract = ref<Record<string, any> | null>(null)
  const definitionContractIdentity = ref<DeveloperCompiledContractIdentity | null>(null)

  const definition = computed(() => draft.value as DeveloperDefinitionData)

  const derivedTraceabilityRecord = computed<TraceabilityRecordData | null>(() => {
    if (!definitionReady.value || !baseline.value) return null
    return buildTraceabilityRecord({
      pmArtifacts: projectStore.artifacts.pmArtifacts,
      requirements: lockedRequirements.value,
      scenarios: lockedScenarios.value,
      shape: lockedShape.value,
      baselineLockedAt: baseline.value.locked_at,
      existing: traceabilityRecord.value,
      reducedFrontingProductDesign: project.value?.project_type === 'governed_service_project',
    })
  })

  function effectiveDefinitionCoverageItem(item: TraceabilityCoverageItem): TraceabilityCoverageItem {
    if (item.mapping_mode !== 'automatic' || !item.mapping_target_key) return item
    if (hasReviewedCoverageResolution(item)) return item
    return {
      ...item,
      status: developerDefinitionTargetStatus(item.mapping_target_key, {
        developerDefinition: draft.value,
      }),
    }
  }

  const definitionCoverage = computed(() =>
    (derivedTraceabilityRecord.value?.coverage ?? []).map((item) => effectiveDefinitionCoverageItem(item)),
  )

  const definitionJson = computed(() =>
    definitionContract.value ? JSON.stringify(definitionContract.value, null, 2) : '',
  )

  function cloneState<T>(value: T): T {
    return JSON.parse(JSON.stringify(value)) as T
  }

  async function sha256Hex(input: string): Promise<string | null> {
    if (!globalThis.crypto?.subtle) return null
    const buffer = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(input))
    return Array.from(new Uint8Array(buffer)).map((value) => value.toString(16).padStart(2, '0')).join('')
  }

  function contractIdentityPayload(baseContract: Record<string, any>) {
    const payload = cloneState(baseContract)
    delete payload.generated_at
    delete payload.compiled_contract_identity
    delete payload.source
    delete payload.studio_traceability
    delete payload.generator_launch
    return payload
  }

  async function materializeDefinitionContract(baseContract: Record<string, any> | null) {
    if (!baseContract || !project.value) {
      return {
        contract: null as Record<string, any> | null,
        identity: null as DeveloperCompiledContractIdentity | null,
      }
    }
    const canonicalJson = stableStringify(contractIdentityPayload(baseContract))
    const identity: DeveloperCompiledContractIdentity = {
      artifact_name: `${project.value.id}-developer-definition.json`,
      canonical_format: 'stable-json-v1',
      signature_algorithm: 'sha256',
      signature: await sha256Hex(canonicalJson),
      generated_at: new Date().toISOString(),
    }
    return {
      identity,
      contract: {
        ...baseContract,
        compiled_contract_identity: {
          artifact_name: identity.artifact_name,
          canonical_format: identity.canonical_format,
          signature_algorithm: identity.signature_algorithm,
          signature: identity.signature,
          generated_at: identity.generated_at,
          revision_number: draft.value?.saved_revision?.revision_number ?? null,
          revision_artifact_id: draft.value?.saved_revision?.revision_artifact_id ?? null,
          previous_revision_artifact_id: draft.value?.saved_revision?.previous_revision_artifact_id ?? null,
          requirements_hash: draft.value?.source_inputs.requirements_hash ?? null,
          scenario_set_hash: draft.value?.source_inputs.scenario_set_hash ?? null,
          service_design_hash: draft.value?.source_inputs.shape_hash ?? null,
          baseline_locked_at: draft.value?.source_inputs.baseline_locked_at ?? null,
          developer_definition_saved_at: draft.value?.saved_at ?? null,
        },
      },
    }
  }

  let contractBuildToken = 0
  watch(
    definitionContractBase,
    async (baseContract) => {
      const token = ++contractBuildToken
      const materialized = await materializeDefinitionContract(baseContract as Record<string, any> | null)
      if (token !== contractBuildToken) return
      definitionContract.value = materialized.contract
      definitionContractIdentity.value = materialized.identity
    },
    { immediate: true },
  )

  const sectionCards = computed(() => {
    const assistantSeeded = summarizeAssistantSeededFields(draft.value, projectStore.artifacts.pmArtifacts)
    const sections = project.value?.project_type === 'governed_service_project'
      ? DEVELOPER_DEFINITION_SECTIONS.filter((section) => section.id !== 'data_contracts')
      : DEVELOPER_DEFINITION_SECTIONS
    return sections.map((section) => ({
      ...section,
      coverage: summarizeCoverageForDefinitionSection(definitionCoverage.value, section.id),
      assistant_seeded: assistantSeeded[section.id],
    }))
  })

  function definitionArtifactForRisk(): ArtifactRecord | null {
    if (!project.value || !draft.value) return null
    return {
      id: definitionArtifact.value?.id ?? developerDefinitionArtifactId(project.value.id),
      project_id: project.value.id,
      title: 'Developer Definition',
      status: 'draft',
      data: draft.value,
      content_hash: '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
  }

  function saveBlockedMessageForHighRisk(title: string, id: string): string {
    if (id === 'developer-clarification:capability_contracts') {
      return 'Capability input contracts are unresolved. Provide reviewed implementation input names, types, required flags, defaults, and allowed values before saving Developer Definition.'
    }
    return `High-risk Developer Design confirmation is unresolved: ${title}. Confirm or intentionally defer it before saving Developer Definition.`
  }

  function reviewedReadinessReportForDraft(): ReturnType<typeof analyzeAgentConsumptionReadiness> | null {
    if (!draft.value) return null
    return applyReadinessFindingReviews(
      analyzeAgentConsumptionReadiness(draft.value),
      normalizeReadinessFindingReviews(derivedTraceabilityRecord.value?.agent_consumption_readiness?.finding_reviews),
    )
  }

  function readinessSaveBlockedMessage(): string | null {
    const report = reviewedReadinessReportForDraft()
    if (!report) return 'Agent Consumption Readiness could not be evaluated for this Developer Definition draft.'
    if (report.summary.blockers > 0) {
      return `Agent Consumption Readiness is blocked (score ${report.score}/100): ${report.summary.blockers} blocker${report.summary.blockers === 1 ? '' : 's'} must be resolved in Agent & App Glue before saving Developer Definition.`
    }
    if (report.summary.warnings > 0) {
      return `Agent Consumption Readiness needs review (score ${report.score}/100): ${report.summary.warnings} warning${report.summary.warnings === 1 ? '' : 's'} must be resolved or classified in Agent & App Glue before saving Developer Definition.`
    }
    return null
  }

  const definitionSaveBlockedReason = computed(() => {
    if (!project.value || !draft.value) return 'Developer Definition draft is not ready yet.'
    const validationIssues = validateDeveloperDefinitionRequiredFields(draft.value)
    if (validationIssues.length) {
      const visibleIssues = validationIssues.slice(0, 8).map((issue) => issue.message).join(' ')
      const remainingCount = validationIssues.length - 8
      return `Developer Definition has ${validationIssues.length} required field${validationIssues.length === 1 ? '' : 's'} missing. ${visibleIssues}${remainingCount > 0 ? ` Plus ${remainingCount} more.` : ''}`
    }
    if (!derivedTraceabilityRecord.value) {
      return 'Coverage Mapping must be created and reviewed before saving Developer Definition.'
    }
    const coverageSummary = summarizeCoverage(definitionCoverage.value)
    if (coverageSummary.missing > 0 || coverageSummary.partial > 0) {
      const unresolvedParts = [
        coverageSummary.missing > 0 ? `${coverageSummary.missing} missing` : '',
        coverageSummary.partial > 0 ? `${coverageSummary.partial} partial` : '',
      ].filter(Boolean).join(' and ')
      return `Coverage Mapping is not generation-ready: ${unresolvedParts} Product Design item${coverageSummary.missing + coverageSummary.partial === 1 ? '' : 's'} remain unresolved.`
    }
    const readinessBlock = readinessSaveBlockedMessage()
    if (readinessBlock) return readinessBlock
    const riskDefinitionArtifact = definitionArtifactForRisk()
    if (!riskDefinitionArtifact) return 'Developer Definition draft is not ready yet.'
    const pmArtifactsForRisk = definitionArtifact.value
      ? projectStore.artifacts.pmArtifacts.map((artifact) =>
          artifact.id === definitionArtifact.value?.id ? riskDefinitionArtifact : artifact,
        )
      : [...projectStore.artifacts.pmArtifacts, riskDefinitionArtifact]
    const highRiskReport = buildHighRiskConfirmationReport({
      project: project.value,
      pmArtifacts: pmArtifactsForRisk,
      documents: projectStore.artifacts.documents,
      requirements: projectStore.artifacts.requirements,
      scenarios: projectStore.artifacts.scenarios,
      shapes: projectStore.artifacts.shapes,
      existing: highRiskConfirmationReportFromArtifacts(projectStore.artifacts.pmArtifacts),
    })
    const unresolvedHighRisk = unresolvedHighRiskConfirmationItems(highRiskReport)
    if (unresolvedHighRisk.length > 0) {
      const first = unresolvedHighRisk[0]
      return saveBlockedMessageForHighRisk(first.title, first.id)
    }
    return null
  })

  function clearAssistantSeededSection(sectionId: typeof DEVELOPER_DEFINITION_SECTIONS[number]['id']) {
    if (!draft.value) return
    clearAssistantSeededFieldsForSection(draft.value, projectStore.artifacts.pmArtifacts, sectionId)
  }

  function scenarioArtifactById(scenarioId: string) {
    return lockedScenarios.value.find((scenario) => scenario.id === scenarioId) ?? null
  }

  function scenarioSourceValues(scenarioId: string, key: 'expected_behavior' | 'expected_anip_support'): string[] {
    const scenario = scenarioArtifactById(scenarioId)
    const scenarioData = (scenario?.data?.scenario ?? {}) as Record<string, any>
    const raw = Array.isArray(scenarioData[key]) ? scenarioData[key] : []
    return raw.filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
  }

  function scenarioAdditionalContext(
    scenarioId: string,
  ): Array<{ key: string; value: string; description: string; semantic_type: ScenarioAdditionalContextSemanticType }> {
    const scenario = scenarioArtifactById(scenarioId)
    const scenarioData = (scenario?.data?.scenario ?? {}) as Record<string, any>
    const additional = Array.isArray(scenarioData.additional_context) ? scenarioData.additional_context : []
    return additional.map((entry: ScenarioAdditionalContextEntry | Record<string, any>) => ({
      key: String(entry.key ?? ''),
      value: String(entry.value ?? ''),
      description: String(entry.description ?? ''),
      semantic_type: normalizeSemanticType(entry as Record<string, any>),
    }))
  }

  function scenarioPrimaryCapabilitySuggestion(scenarioId: string): string {
    const scenario = scenarioArtifactById(scenarioId)
    return String((scenario?.data?.scenario?.context?.capability ?? '') || '')
  }

  function toggleScenarioFormalizationService(scenarioId: string, serviceId: string) {
    if (!draft.value) return
    const formalization = draft.value.scenario_formalizations.find((item) => item.scenario_id === scenarioId)
    if (!formalization) return
    const set = new Set(formalization.participating_service_ids)
    if (set.has(serviceId)) set.delete(serviceId)
    else set.add(serviceId)
    formalization.participating_service_ids = [...set]
  }

  function toggleScenarioFormalizationValue(
    scenarioId: string,
    kind: 'required_behaviors' | 'required_anip_support',
    value: string,
  ) {
    if (!draft.value) return
    const formalization = draft.value.scenario_formalizations.find((item) => item.scenario_id === scenarioId)
    if (!formalization) return
    const set = new Set(formalization[kind])
    if (set.has(value)) set.delete(value)
    else set.add(value)
    formalization[kind] = [...set]
  }

  function orchestrationStepsForScenario(scenarioId: string): DeveloperScenarioOrchestrationStep[] {
    return draft.value?.scenario_formalizations.find((item) => item.scenario_id === scenarioId)?.orchestration_steps ?? []
  }

  function addOrchestrationStep(scenarioId: string) {
    if (!draft.value) return
    const formalization = draft.value.scenario_formalizations.find((item) => item.scenario_id === scenarioId)
    if (!formalization) return
    formalization.orchestration_steps.push(newOrchestrationStep(formalization.orchestration_steps.length))
  }

  function updateOrchestrationStep(
    scenarioId: string,
    stepId: string,
    field: keyof Omit<DeveloperScenarioOrchestrationStep, 'id'>,
    value: string,
  ) {
    if (!draft.value) return
    const formalization = draft.value.scenario_formalizations.find((item) => item.scenario_id === scenarioId)
    const step = formalization?.orchestration_steps.find((entry) => entry.id === stepId)
    if (!step) return
    if (field === 'stop_condition') {
      step.stop_condition = value as DeveloperScenarioStopCondition
      return
    }
    if (field === 'step_kind') {
      step.step_kind = value as DeveloperScenarioStepKind
      if (step.step_kind === 'handoff_only') {
        step.capability_id = ''
      }
      return
    }
    if (field === 'outcome_type') {
      step.outcome_type = value as DeveloperScenarioOutcomeType
      return
    }
    step[field] = value
  }

  function removeOrchestrationStep(scenarioId: string, stepId: string) {
    if (!draft.value) return
    const formalization = draft.value.scenario_formalizations.find((item) => item.scenario_id === scenarioId)
    if (!formalization) return
    formalization.orchestration_steps = formalization.orchestration_steps.filter((entry) => entry.id !== stepId)
  }

  const generatedCodeSummary = computed(() => {
    if (!draft.value) return []
    const lines: string[] = []
    const selectedServices = serviceOptions.value.filter((service) =>
      draft.value!.generation.selected_service_ids.includes(service.id),
    )

    if (draft.value.generation.service_generation_mode === 'from_service_design') {
      lines.push(`Generate one service scaffold per Service Design boundary (${serviceOptions.value.length} service${serviceOptions.value.length === 1 ? '' : 's'}).`)
    } else if (draft.value.generation.service_generation_mode === 'single_service_scaffold') {
      lines.push('Generate one consolidated service scaffold even though Product Design may describe multiple service boundaries.')
    } else {
      lines.push(`Generate only the selected service boundaries (${selectedServices.map((item) => item.label).join(', ') || 'none selected'}).`)
    }

    const protocolLabels = PROTOCOL_OPTIONS
      .filter((item) => draft.value!.generation.protocols.includes(item.value))
      .map((item) => item.label)
    lines.push(`Expose generated services through ${protocolLabels.join(', ') || 'no protocol selected yet'}.`)

    const scalability = SCALABILITY_OPTIONS.find((item) => item.value === draft.value?.generation.scalability_profile)
    if (scalability) {
      lines.push(`Scaffolds should assume a ${scalability.label.toLowerCase()} deployment posture.`)
    }

    const adapter = ADAPTER_OPTIONS.find((item) => item.value === draft.value?.generation.codegen_adapter)
    if (adapter) {
      lines.push(`Primary generated code target: ${adapter.label}.`)
    }

    const layout = LAYOUT_OPTIONS.find((item) => item.value === draft.value?.generation.layout_strategy)
    if (layout) {
      lines.push(`Repository/layout expectation: ${layout.label}.`)
    }

    const delivery = DELIVERY_MODEL_OPTIONS.find((item) => item.value === draft.value?.identity.delivery_model)
    const architecture = ARCHITECTURE_SHAPE_OPTIONS.find((item) => item.value === draft.value?.identity.architecture_shape)
    lines.push(`System identity is ${draft.value.identity.system_name} in domain ${draft.value.identity.domain_name || 'not specified yet'}, delivered as ${delivery?.label.toLowerCase() || 'an unspecified delivery model'} with ${architecture?.label.toLowerCase() || 'an unspecified architecture shape'}.`)
    lines.push(`Generated package namespace will start with ${draft.value.naming.namespace}.${draft.value.naming.package_prefix} and service names will be prefixed with ${draft.value.naming.service_name_prefix}.`)
    return lines
  })

  function toggleProtocol(protocol: DeveloperTransportProtocol) {
    if (!draft.value) return
    const set = new Set(draft.value.generation.protocols)
    if (set.has(protocol)) set.delete(protocol)
    else set.add(protocol)
    draft.value.generation.protocols = [...set]
  }

  function toggleServiceSelection(serviceId: string) {
    if (!draft.value) return
    const set = new Set(draft.value.generation.selected_service_ids)
    if (set.has(serviceId)) set.delete(serviceId)
    else set.add(serviceId)
    draft.value.generation.selected_service_ids = [...set]
  }

  function toggleVerificationTargetService(
    kind: 'supported_question_family_bindings' | 'business_goal_bindings',
    id: string,
    serviceId: string,
  ) {
    if (!draft.value) return
    const entry = draft.value.verification[kind].find((item) => item.id === id)
    if (!entry) return
    const set = new Set(entry.target_service_ids)
    if (set.has(serviceId)) set.delete(serviceId)
    else set.add(serviceId)
    entry.target_service_ids = [...set]
  }

  function toggleCompositionRuleScenario(ruleId: string, scenarioId: string) {
    if (!draft.value) return
    const rule = draft.value.composition_rules.find((item) => item.id === ruleId)
    if (!rule) return
    const set = new Set(rule.affected_scenario_ids)
    if (set.has(scenarioId)) set.delete(scenarioId)
    else set.add(scenarioId)
    rule.affected_scenario_ids = [...set]
  }

  async function saveDefinition() {
    if (!project.value || !draft.value) return
    saving.value = true
    saveError.value = null
    try {
      if (definitionSaveBlockedReason.value) throw new Error(definitionSaveBlockedReason.value)
      const riskDefinitionArtifact = definitionArtifactForRisk()
      if (!riskDefinitionArtifact) throw new Error('Developer Definition draft is not ready yet.')
      const pmArtifactsForRisk = definitionArtifact.value
        ? projectStore.artifacts.pmArtifacts.map((artifact) =>
            artifact.id === definitionArtifact.value?.id ? riskDefinitionArtifact : artifact,
          )
        : [...projectStore.artifacts.pmArtifacts, riskDefinitionArtifact]
      const highRiskReport = buildHighRiskConfirmationReport({
        project: project.value,
        pmArtifacts: pmArtifactsForRisk,
        documents: projectStore.artifacts.documents,
        requirements: projectStore.artifacts.requirements,
        scenarios: projectStore.artifacts.scenarios,
        shapes: projectStore.artifacts.shapes,
        existing: highRiskConfirmationReportFromArtifacts(projectStore.artifacts.pmArtifacts),
      })
      const unresolvedHighRisk = unresolvedHighRiskConfirmationItems(highRiskReport)
      if (unresolvedHighRisk.length > 0) {
        const first = unresolvedHighRisk[0]
        throw new Error(saveBlockedMessageForHighRisk(first.title, first.id))
      }
      const currentTraceability = derivedTraceabilityRecord.value
      if (!currentTraceability) throw new Error('Coverage Mapping must be created and reviewed before saving Developer Definition.')
      const reviewedReadiness = reviewedReadinessReportForDraft()
      if (!reviewedReadiness) throw new Error('Agent Consumption Readiness could not be evaluated for this Developer Definition draft.')
      if (reviewedReadiness.summary.blockers > 0) {
        throw new Error(`Agent Consumption Readiness is blocked (score ${reviewedReadiness.score}/100): ${reviewedReadiness.summary.blockers} blocker${reviewedReadiness.summary.blockers === 1 ? '' : 's'} must be resolved in Agent & App Glue before saving Developer Definition.`)
      }
      if (reviewedReadiness.summary.warnings > 0) {
        throw new Error(`Agent Consumption Readiness needs review (score ${reviewedReadiness.score}/100): ${reviewedReadiness.summary.warnings} warning${reviewedReadiness.summary.warnings === 1 ? '' : 's'} must be resolved or classified in Agent & App Glue before saving Developer Definition.`)
      }
      const traceabilityPayload: TraceabilityRecordData = {
        ...currentTraceability,
        coverage: definitionCoverage.value.map((item) => JSON.parse(JSON.stringify(item))),
        agent_consumption_readiness: JSON.parse(JSON.stringify(reviewedReadiness)),
        high_risk_confirmations: highRiskReport,
        developer_status: 'ready_for_pm_review',
        developer_marked_at: new Date().toISOString(),
      }
      const materialized = await materializeDefinitionContract(definitionContractBase.value as Record<string, any> | null)
      const latestSavedRevision = (
        latestDefinitionRevisionArtifact.value?.data as DeveloperDefinitionRevisionData | undefined
      )?.saved_revision
        ?? savedDefinition.value?.saved_revision
        ?? null
      const latestSavedSignature = (
        latestDefinitionRevisionArtifact.value?.data as DeveloperDefinitionRevisionData | undefined
      )?.compiled_contract_identity?.signature
        ?? savedDefinition.value?.compiled_contract_identity?.signature
        ?? null
      const shouldCreateRevision = Boolean(materialized.identity?.signature)
        && (!latestSavedRevision || materialized.identity?.signature !== latestSavedSignature)
      const nextRevisionNumber = (latestSavedRevision?.revision_number ?? 0) + (shouldCreateRevision ? 1 : 0)
      const savedAt = new Date().toISOString()
      const savedRevision: DeveloperDefinitionSavedRevision | null = shouldCreateRevision
        ? {
            revision_number: nextRevisionNumber,
            revision_artifact_id: developerDefinitionRevisionArtifactId(project.value.id, nextRevisionNumber),
            previous_revision_artifact_id: latestSavedRevision?.revision_artifact_id ?? null,
            saved_at: savedAt,
          }
        : latestSavedRevision

      const payload: DeveloperDefinitionData = {
        ...draft.value,
        artifact_type: 'developer_definition',
        compiled_contract_identity: materialized.identity,
        saved_revision: savedRevision,
        saved_at: savedRevision?.saved_at ?? savedAt,
      }

      if (shouldCreateRevision && savedRevision) {
        const revisionPayload: DeveloperDefinitionRevisionData = {
          ...payload,
          artifact_type: 'developer_definition_revision',
          saved_revision: savedRevision,
        }
        await createPmArtifact(project.value.id, {
          id: savedRevision.revision_artifact_id,
          title: `Developer Definition Revision ${savedRevision.revision_number}`,
          data: revisionPayload,
        })
      }

      if (definitionArtifact.value) {
        await updatePmArtifact(project.value.id, definitionArtifact.value.id, {
          title: 'Developer Definition',
          status: 'active',
          data: payload,
        })
      } else {
        const createdDefinition = await createPmArtifact(project.value.id, {
          id: developerDefinitionArtifactId(project.value.id),
          title: 'Developer Definition',
          data: payload,
        })
        await updatePmArtifact(project.value.id, createdDefinition.id, {
          status: 'active',
        })
      }
      if (traceabilityArtifact.value) {
        await updatePmArtifact(project.value.id, traceabilityArtifact.value.id, {
          title: 'Design Traceability',
          status: 'active',
          data: traceabilityPayload,
        })
      } else {
        await createPmArtifact(project.value.id, {
          id: traceabilityArtifactId(project.value.id),
          title: 'Design Traceability',
          data: traceabilityPayload,
        })
      }
      draft.value = payload
      await loadProject(project.value.id)
    } catch (err) {
      saveError.value = err instanceof Error ? err.message : String(err)
    } finally {
      saving.value = false
    }
  }

  async function saveDraft() {
    if (!project.value || !draft.value) return
    saving.value = true
    saveError.value = null
    try {
      const savedAt = new Date().toISOString()
      const payload: DeveloperDefinitionData = {
        ...JSON.parse(JSON.stringify(draft.value)),
        artifact_type: 'developer_definition',
        compiled_contract_identity: null,
        saved_revision: null,
        saved_at: savedAt,
      }

      if (definitionArtifact.value) {
        await updatePmArtifact(project.value.id, definitionArtifact.value.id, {
          title: 'Developer Definition Draft',
          status: 'draft',
          data: payload,
        })
      } else {
        const createdDefinition = await createPmArtifact(project.value.id, {
          id: developerDefinitionArtifactId(project.value.id),
          title: 'Developer Definition Draft',
          data: payload,
        })
        await updatePmArtifact(project.value.id, createdDefinition.id, {
          status: 'draft',
        })
      }
      draft.value = payload
      await loadProject(project.value.id)
    } catch (err) {
      saveError.value = err instanceof Error ? err.message : String(err)
    } finally {
      saving.value = false
    }
  }

  function exportDefinition() {
    if (!definitionContract.value || !project.value) return
    const blob = new Blob([definitionJson.value], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${project.value.id}-anip-service-definition.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  function toggleScenarioHelpCard(id: string) {
    expandedScenarioHelpCards.value = {
      ...expandedScenarioHelpCards.value,
      [id]: !expandedScenarioHelpCards.value[id],
    }
  }

  function openScenarioHelpCard(id: string) {
    activeScenarioHelpCard.value = id
  }

  function closeScenarioHelpCard() {
    activeScenarioHelpCard.value = null
  }

  function setScenarioField(formalization: DeveloperScenarioFormalization, field: 'primary_capability' | 'actor_context' | 'business_scope' | 'time_scope' | 'implementation_notes', value: string) {
    formalization[field] = value
  }

  function setCapabilityField(
    capability: DeveloperCapabilityFormalization,
    field: Exclude<keyof DeveloperCapabilityFormalization, 'id' | 'source_kind'>,
    value: string,
  ) {
    capability[field] = value as never
  }

  return {
    project,
    loadingDrafts,
    saving,
    loadError,
    saveError,
    baseline,
    baselineAligned,
    lockedRequirements,
    lockedScenarios,
    lockedShape,
    traceabilityRecord,
    savedDefinition,
    definitionReady,
    serviceOptions,
    definitionAligned,
    definitionContract,
    definitionContractIdentity,
    definition,
    definitionJson,
    sectionCards,
    definitionSaveBlockedReason,
    clearAssistantSeededSection,
    expandedScenarioHelpCards,
    activeScenarioHelpCard,
    generatedCodeSummary,
    scenarioSourceValues,
    scenarioAdditionalContext,
    scenarioPrimaryCapabilitySuggestion,
    toggleScenarioFormalizationService,
    toggleScenarioFormalizationValue,
    orchestrationStepsForScenario,
    addOrchestrationStep,
    updateOrchestrationStep,
    removeOrchestrationStep,
    toggleProtocol,
    toggleServiceSelection,
    toggleVerificationTargetService,
    toggleCompositionRuleScenario,
    saveDefinition,
    saveDraft,
    resetDefinition,
    exportDefinition,
    toggleScenarioHelpCard,
    openScenarioHelpCard,
    closeScenarioHelpCard,
    setScenarioField,
    setCapabilityField,
    humanizeContractValue,
    semanticTypeLabel,
  }
}
