import type {
  DeveloperCapabilityFormalization,
  DeveloperCapabilityInputFormalization,
  DeveloperDefinitionData,
  DeveloperScenarioFormalization,
} from './project-types'
import { effectLabel } from './effect-vocabulary'

export type AgentConsumptionReadinessSeverity = 'blocker' | 'warning' | 'info'

export type AgentConsumptionReadinessCategory =
  | 'clarification_behavior'
  | 'declared_defaults'
  | 'derived_target'
  | 'unsupported_effect'
  | 'approval_boundary'
  | 'output_semantics'
  | 'app_glue'
  | 'composition_candidate'

export type AgentConsumptionReadinessOwner =
  | 'product_contract'
  | 'developer_contract'
  | 'custom_service_logic'
  | 'agent_app_glue'
  | 'generator_runtime'
  | 'unsupported'

export type AgentConsumptionReadinessProbeOutcome =
  | 'success'
  | 'clarification_required'
  | 'denied'
  | 'approval_required'
  | 'unsupported'

export interface AgentConsumptionReadinessFinding {
  id: string
  severity: AgentConsumptionReadinessSeverity
  category: AgentConsumptionReadinessCategory
  owner: AgentConsumptionReadinessOwner
  title: string
  detail: string
  recommendation: string
  capability_id?: string
  input_name?: string
  source: 'capability' | 'scenario' | 'coverage' | 'verification'
}

export interface AgentConsumptionReadinessProbe {
  id: string
  label: string
  prompt: string
  expected_outcome: AgentConsumptionReadinessProbeOutcome
  target_capability_id?: string
  rationale: string
}

export interface AgentConsumptionReadinessRequiredGlue {
  id: string
  title: string
  detail: string
  recommendation: string
  capability_id?: string
  category: AgentConsumptionReadinessCategory
}

export type AgentConsumptionReadinessFindingDecision =
  | 'contract_composition'
  | 'explicit_app_glue'
  | 'acceptable_warning'
  | 'follow_up'

export interface AgentConsumptionReadinessFindingReview {
  id: string
  decision: AgentConsumptionReadinessFindingDecision
  note: string
  reviewed_at: string
  review_method?: 'manual' | 'automation_harness'
}

export interface AgentConsumptionReadinessReport {
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
  findings: AgentConsumptionReadinessFinding[]
  probes: AgentConsumptionReadinessProbe[]
  required_app_glue: AgentConsumptionReadinessRequiredGlue[]
  finding_reviews?: Record<string, AgentConsumptionReadinessFindingReview>
}

const DERIVED_TARGET_TOKENS = [
  'at risk',
  'best',
  'bottleneck',
  'highest',
  'lowest',
  'next',
  'prioriti',
  'rank',
  'recommend',
  'selected',
  'top',
]

const UNSUPPORTED_EFFECT_TOKENS = [
  'dispatch',
  'export',
  'mutate',
  'publish',
  'send',
]

const MUTATING_EFFECT_TOKENS = [
  'approval.request',
  'approval.execute',
  'external_dispatch',
  'system.mutation',
  'system.preview_mutation',
]

const APPROVAL_PREVIEW_DIRECT_INTENT_TOKENS = [
  'approval',
  'mutat',
  'plan',
  'prepare',
  'preview',
  'reassign',
  'execute',
]

const APPROVAL_PREVIEW_FOLLOWUP_TOKENS = [
  'follow up',
  'followup',
]

const APPROVAL_PREVIEW_FOLLOWUP_WORK_TOKENS = [
  'create',
  'mutation',
  'prepare',
  'preview',
  'task',
  'tasks',
]

const STEM_MATCH_TOKENS = new Set([
  'mutat',
  'prioriti',
  'rank',
])

export function readinessStatusLabel(status: AgentConsumptionReadinessReport['status']): string {
  if (status === 'ready') return 'Ready'
  if (status === 'blocked') return 'Blocked'
  return 'Needs Review'
}

export function readinessSeverityLabel(severity: AgentConsumptionReadinessSeverity): string {
  if (severity === 'blocker') return 'Blocker'
  if (severity === 'warning') return 'Warning'
  return 'Info'
}

export function readinessOwnerLabel(owner: AgentConsumptionReadinessOwner): string {
  if (owner === 'developer_contract') return 'Service contract'
  if (owner === 'agent_app_glue') return 'Consuming app'
  if (owner === 'custom_service_logic') return 'Service implementation'
  return owner.replace(/_/g, ' ')
}

export function readinessFindingDecisionLabel(decision: AgentConsumptionReadinessFindingDecision | string): string {
  if (decision === 'contract_composition') return 'Service owns the flow'
  if (decision === 'explicit_app_glue') return 'App owns the decision'
  if (decision === 'acceptable_warning') return 'Accepted limitation'
  if (decision === 'follow_up') return 'Follow-up required'
  return 'Unreviewed'
}

export function normalizeReadinessFindingReviews(
  value: unknown,
): Record<string, AgentConsumptionReadinessFindingReview> {
  if (!value || typeof value !== 'object') return {}
  const entries = Object.entries(value as Record<string, unknown>).filter(([, item]) =>
    item
    && typeof item === 'object'
    && typeof (item as Record<string, unknown>).id === 'string'
    && isReadinessFindingDecision((item as Record<string, unknown>).decision)
    && typeof (item as Record<string, unknown>).note === 'string'
    && typeof (item as Record<string, unknown>).reviewed_at === 'string',
  ) as Array<[string, AgentConsumptionReadinessFindingReview]>
  return Object.fromEntries(entries)
}

export function applyReadinessFindingReviews(
  report: AgentConsumptionReadinessReport,
  reviews: Record<string, AgentConsumptionReadinessFindingReview>,
): AgentConsumptionReadinessReport {
  const activeReviewIds = new Set(report.findings.map((finding) => finding.id))
  const findingReviews = Object.fromEntries(
    Object.entries(reviews).filter(([id]) => activeReviewIds.has(id)),
  )
  const requiredGlue = [...report.required_app_glue]
  for (const finding of report.findings) {
    const review = findingReviews[finding.id]
    if (review?.decision !== 'explicit_app_glue') continue
    const glueId = `${finding.id}:reviewed-app-glue`
    if (requiredGlue.some((item) => item.id === glueId)) continue
    requiredGlue.push({
      id: glueId,
      title: finding.capability_id ? `${finding.capability_id} app glue` : finding.title,
      detail: review.note || finding.detail,
      recommendation: 'Keep this as explicit app-layer behavior. Do not hide it in the generic ANIP runtime or service invocation substrate.',
      capability_id: finding.capability_id,
      category: finding.category,
    })
  }
  const activeFindings = report.findings.filter((finding) => {
    const review = findingReviews[finding.id]
    return !review || review.decision === 'follow_up'
  })
  const blockers = activeFindings.filter((finding) => finding.severity === 'blocker').length
  const warnings = activeFindings.filter((finding) => finding.severity === 'warning').length
  const info = activeFindings.filter((finding) => finding.severity === 'info').length
  const score = readinessScore(blockers, warnings, info)
  return {
    ...report,
    status: readinessStatus(blockers, warnings, score),
    score,
    summary: {
      ...report.summary,
      blockers,
      warnings,
      info,
      required_app_glue: requiredGlue.length,
    },
    required_app_glue: requiredGlue,
    finding_reviews: findingReviews,
  }
}

function isReadinessFindingDecision(value: unknown): value is AgentConsumptionReadinessFindingDecision {
  return value === 'contract_composition'
    || value === 'explicit_app_glue'
    || value === 'acceptable_warning'
    || value === 'follow_up'
}

function readinessScore(blockers: number, warnings: number, info: number): number {
  const blockerPenalty = Math.min(70, blockers * 35)
  const warningPenalty = Math.min(45, warnings * 5)
  const infoPenalty = Math.min(10, info * 2)
  return Math.max(0, 100 - blockerPenalty - warningPenalty - infoPenalty)
}

function readinessStatus(
  blockers: number,
  warnings: number,
  score: number,
): AgentConsumptionReadinessReport['status'] {
  if (blockers > 0) return 'blocked'
  if (warnings > 0) return 'needs_review'
  return score >= 85 ? 'ready' : 'needs_review'
}

function stripNegatedMutationSignals(value: string): string {
  return value
    .replace(/\bnon\s+mutat\w*\b/g, ' ')
    .replace(/\bnonmutat\w*\b/g, ' ')
    .replace(/\bwithout\s+mutat\w*\b/g, ' ')
    .replace(/\bdoes\s+not\s+mutat\w*\b/g, ' ')
    .replace(/\bmust\s+not\s+mutat\w*\b/g, ' ')
    .replace(/\bno\s+mutat\w*\b/g, ' ')
}

function looksApprovalPreviewIntent(value: string): boolean {
  const mutationSignalText = stripNegatedMutationSignals(value)
  if (/\brout(?:e|ing)\b/.test(value)) {
    return hasAnyToken(value, ['approval', 'execute', 'preview'])
      || hasAnyToken(mutationSignalText, ['mutat'])
  }
  if (hasAnyToken(value, APPROVAL_PREVIEW_DIRECT_INTENT_TOKENS.filter((token) => token !== 'mutat'))
    || hasAnyToken(mutationSignalText, ['mutat'])
  ) return true
  return hasAnyToken(value, APPROVAL_PREVIEW_FOLLOWUP_TOKENS)
    && hasAnyToken(value, APPROVAL_PREVIEW_FOLLOWUP_WORK_TOKENS)
}

function hasDerivedTargetIntent(value: string): boolean {
  return hasAnyToken(value, DERIVED_TARGET_TOKENS)
    && hasAnyToken(value, [
      'account',
      'lead',
      'opportunit',
      'record',
      'target',
      'customer',
      'company',
      'cohort',
      'candidate',
    ])
}

function isReferenceScopeInput(input: DeveloperCapabilityInputFormalization): boolean {
  const semanticType = normalizeText(input.semantic_type ?? '')
  return input.entity_reference === true
    || semanticType === 'entity reference'
    || semanticType.endsWith(' reference')
}

function hasExplicitDerivedTargetBinding(capability: DeveloperCapabilityFormalization): boolean {
  const inputs = capability.inputs ?? []
  const hasExplicitTargetInput = inputs.some((input) => {
    const semanticType = normalizeText(input.semantic_type ?? '')
    const resolutionMode = input.resolution?.mode
    const hasRuntimeBoundary = Boolean(
      String(input.default_value ?? '').trim()
      || String(input.clarification_hint ?? '').trim()
      || String(input.input_format ?? '').trim()
      || String(input.validation_pattern ?? '').trim()
      || String(input.catalog_ref ?? '').trim()
      || String(input.resolution?.resolver_ref ?? '').trim()
      || resolutionMode === 'backend_resolved'
      || (resolutionMode === 'closed_values' && (input.allowed_values ?? []).length > 0)
    )
    const serviceOwnedOptionalTarget = !input.required
      && resolutionMode === 'backend_resolved'
      && ['omit', 'use_default'].includes(input.resolution?.on_missing ?? '')
      && (
        input.entity_reference === true
        || semanticType.endsWith('reference')
        || ['selection scope', 'selection_scope', 'target reference', 'target_reference', 'entity reference', 'entity_reference'].includes(semanticType)
      )
    if (serviceOwnedOptionalTarget) return true

    return input.required
      && hasRuntimeBoundary
      && (
        input.entity_reference === true
        || semanticType.endsWith('reference')
        || ['selection scope', 'selection_scope', 'target reference', 'target_reference', 'entity reference', 'entity_reference'].includes(semanticType)
      )
  })
  if (hasExplicitTargetInput) return true

  const hasRankingOrSelectionInput = inputs.some((input) => {
    const inputName = normalizeText(input.input_name ?? '')
    const semanticType = normalizeText(input.semantic_type ?? '')
    return hasAnyToken(`${inputName} ${semanticType}`, ['ranking basis', 'selection basis'])
      && (
        String(input.default_value ?? '').trim().length > 0
        || input.resolution?.on_missing === 'use_default'
        || input.resolution?.mode === 'closed_values'
      )
  })
  const hasBoundedLimitInput = inputs.some((input) => {
    const inputName = normalizeText(input.input_name ?? '')
    const semanticType = normalizeText(input.semantic_type ?? '')
    return hasAnyToken(`${inputName} ${semanticType}`, ['limit', 'quantity limit'])
      && ['omit', 'use_default', 'clarify'].includes(input.resolution?.on_missing ?? '')
  })
  return hasRankingOrSelectionInput && hasBoundedLimitInput
}

function isFormattedBusinessScopeInput(input: DeveloperCapabilityInputFormalization): boolean {
  return Boolean(String(input.input_format ?? '').trim() || String(input.validation_pattern ?? '').trim())
}

function hasExplicitInputClassification(input: DeveloperCapabilityInputFormalization): boolean {
  return Boolean(
    String(input.semantic_type ?? '').trim()
    || String(input.input_format ?? '').trim()
    || String(input.validation_pattern ?? '').trim()
    || String(input.clarification_hint ?? '').trim()
    || input.entity_reference === true
    || (input.allowed_values ?? []).length > 0,
  )
}

export function analyzeAgentConsumptionReadiness(
  definition: DeveloperDefinitionData | null | undefined,
): AgentConsumptionReadinessReport {
  const findings: AgentConsumptionReadinessFinding[] = []
  const probes: AgentConsumptionReadinessProbe[] = []
  const requiredGlue = new Map<string, AgentConsumptionReadinessRequiredGlue>()

  function addFinding(finding: AgentConsumptionReadinessFinding) {
    if (findings.some((existing) => existing.id === finding.id)) return
    findings.push(finding)
  }

  function addProbe(probe: AgentConsumptionReadinessProbe) {
    if (probes.some((existing) => existing.id === probe.id)) return
    probes.push(probe)
  }

  function addGlue(glue: AgentConsumptionReadinessRequiredGlue) {
    if (requiredGlue.has(glue.id)) return
    requiredGlue.set(glue.id, glue)
  }

  if (!definition) {
    return buildReport({
      findings: [{
        id: 'missing-developer-definition',
        severity: 'blocker',
        category: 'clarification_behavior',
        owner: 'developer_contract',
        title: 'Developer Definition is missing',
        detail: 'Studio cannot evaluate agent consumption readiness until a Developer Definition draft exists.',
        recommendation: 'Create and save the Developer Definition before publishing or generating agent-facing services.',
        source: 'coverage',
      }],
      probes,
      requiredGlue: [],
    })
  }

  const capabilities = definition.capability_formalizations ?? []
  for (const capability of capabilities) {
    analyzeCapability(capability, { addFinding, addProbe, addGlue })
  }

  for (const scenario of definition.scenario_formalizations ?? []) {
    analyzeScenario(scenario, definition, { addFinding, addProbe, addGlue })
  }

  if ((definition.verification?.supported_question_family_bindings ?? []).length === 0) {
    addFinding({
      id: 'missing-supported-question-family-bindings',
      severity: capabilities.length > 0 ? 'warning' : 'info',
      category: 'output_semantics',
      owner: 'developer_contract',
      title: 'No supported question families are bound',
      detail: 'Studio cannot derive package-level consumption probes from question-family coverage.',
      recommendation: 'Bind representative question families so simulator probes match real user-facing requests.',
      source: 'verification',
    })
  }

  return buildReport({
    findings,
    probes,
    requiredGlue: Array.from(requiredGlue.values()),
  })
}

function analyzeCapability(
  capability: DeveloperCapabilityFormalization,
  sinks: {
    addFinding: (finding: AgentConsumptionReadinessFinding) => void
    addProbe: (probe: AgentConsumptionReadinessProbe) => void
    addGlue: (glue: AgentConsumptionReadinessRequiredGlue) => void
  },
) {
  const capabilityText = normalizeText([
    capability.capability_id,
    capability.title,
    capability.summary,
    capability.intent_type,
    capability.operation_type,
    capability.output_intent,
  ].join(' '))
  const capabilityId = capability.capability_id || capability.id
  const produces = capability.business_effects?.produces ?? []
  const doesNotProduce = capability.business_effects?.does_not_produce ?? []
  const hasComposition = Boolean(capability.composition?.steps?.length)
  const declaresApprovalPreview = produces.some((effect) => ['approval.request', 'system.preview_mutation'].includes(effect))
    || hasAnyToken(normalizeText(capability.side_effect_level), ['approval', 'write'])
  const looksApprovalPreview = looksApprovalPreviewIntent(capabilityText)
    && !produces.includes('content.draft')
    && !doesNotProduce.some((effect) => ['external_dispatch', 'system.mutation'].includes(effect))

  if (capability.implementation_fit?.category === 'agent_app_glue') {
    sinks.addFinding({
      id: `${capabilityId}:agent-app-glue`,
      severity: 'warning',
      category: 'app_glue',
      owner: 'agent_app_glue',
      title: 'This capability needs app-owned behavior',
      detail: capability.implementation_fit.rationale || 'This capability needs product-specific behavior outside the generic ANIP calling layer.',
      recommendation: 'Document what the app owns, such as user framing, result display, routing preference, or boundary wording.',
      capability_id: capabilityId,
      source: 'capability',
    })
    sinks.addGlue({
      id: `${capabilityId}:app-glue-profile`,
      title: 'App-owned behavior profile',
      detail: 'This capability needs product-specific framing or routing outside the generic ANIP calling layer.',
      recommendation: 'Create a small app profile for capability framing, result display, boundaries, or input meanings.',
      capability_id: capabilityId,
      category: 'app_glue',
    })
  }

  for (const input of capability.inputs ?? []) {
    analyzeInput(capability, input, sinks)
  }

  if (
    hasDerivedTargetIntent(capabilityText)
    && !hasComposition
    && capability.implementation_fit?.category !== 'agent_app_glue'
    && !hasExplicitDerivedTargetBinding(capability)
  ) {
    sinks.addFinding({
      id: `${capabilityId}:derived-target`,
      severity: 'warning',
      category: 'derived_target',
      owner: 'developer_contract',
      title: 'Who chooses the target group?',
      detail: 'This capability may be asked for targets such as top, ranked, selected, recommended, or at-risk records. The package should state whether the service chooses that group, or the consuming app chooses it before calling.',
      recommendation: 'Choose one reviewed path: make the service own the full selection-and-action flow, mark target selection as app-owned glue, or accept that vague target requests must ask for clarification.',
      capability_id: capabilityId,
      source: 'capability',
    })
    sinks.addProbe({
      id: `${capabilityId}:derived-target-probe`,
      label: 'Derived target probe',
      prompt: `Ask ${capabilityId} for a top, selected, or derived target without explicitly naming the target entity.`,
      expected_outcome: 'clarification_required',
      target_capability_id: capabilityId,
      rationale: 'Derived target requests should not silently treat vague business language as literal entity identifiers.',
    })
  }

  const declaresMutation = produces.some((effect) => MUTATING_EFFECT_TOKENS.includes(effect))
    || hasAnyToken(normalizeText(capability.side_effect_level), ['approval', 'write', 'mutation'])
  const hasEffectiveGrantPolicy = Boolean(capability.grant_policy)
    || capability.intent_type === 'approval_gated'
    || capability.operation_type === 'approval_gated'
    || normalizeText(capability.side_effect_level).includes('approval')
  if (declaresMutation && !hasEffectiveGrantPolicy && !hasAnyToken(normalizeText(capability.summary), ['preview', 'draft', 'read-only', 'read only'])) {
    sinks.addFinding({
      id: `${capabilityId}:approval-policy`,
      severity: 'blocker',
      category: 'approval_boundary',
      owner: 'developer_contract',
      title: 'Approval behavior is missing',
      detail: 'This capability appears able to write, dispatch, preview a change, or request approval, but the contract does not define how approval should be granted and resumed.',
      recommendation: 'Either add an approval grant policy, or change the capability to a safe read-only or draft-only behavior.',
      capability_id: capabilityId,
      source: 'capability',
    })
    sinks.addProbe({
      id: `${capabilityId}:approval-probe`,
      label: 'Approval boundary probe',
      prompt: `Invoke ${capabilityId} without an approval grant.`,
      expected_outcome: 'approval_required',
      target_capability_id: capabilityId,
      rationale: 'Approval-gated behavior must expose a predictable ANIP approval outcome.',
    })
  }

  if (looksApprovalPreview && !declaresApprovalPreview && !hasComposition) {
    sinks.addFinding({
      id: `${capabilityId}:approval-effect-drift`,
      severity: 'blocker',
      category: 'approval_boundary',
      owner: 'developer_contract',
      title: 'Approval boundary is unclear',
      detail: 'This capability sounds like it can prepare, preview, route, reassign, or create follow-up work, but it is still marked as read-only.',
      recommendation: 'Either mark it as approval-required preview behavior, or rewrite the capability so it is clearly only returning information.',
      capability_id: capabilityId,
      source: 'capability',
    })
  }

  if (declaresApprovalPreview && hasEffectiveGrantPolicy) {
    sinks.addProbe({
      id: `${capabilityId}:approval-boundary-probe`,
      label: 'Approval-preview boundary probe',
      prompt: `Ask for a read summary and also ask ${capabilityId} to prepare, preview, plan, or route the governed action.`,
      expected_outcome: 'approval_required',
      target_capability_id: capabilityId,
      rationale: 'Compound requests that include approval-preview behavior must select the governed boundary capability instead of a harmless read-only capability.',
    })
  }

  if (doesNotProduce.length > 0) {
    sinks.addProbe({
      id: `${capabilityId}:unsupported-effect-probe`,
      label: 'Unsupported effect probe',
      prompt: `Ask ${capabilityId} to ${doesNotProduce.includes('external_dispatch') ? 'send the result now' : 'perform an explicitly unsupported effect'}.`,
      expected_outcome: 'unsupported',
      target_capability_id: capabilityId,
      rationale: 'Declared business effects should make package boundaries testable before paid LLM benchmark runs.',
    })
  }

  if (!capability.output_shape || normalizeText(capability.output_shape) === 'result') {
    sinks.addFinding({
      id: `${capabilityId}:output-shape`,
      severity: 'info',
      category: 'output_semantics',
      owner: 'developer_contract',
      title: 'Result display may need guidance',
      detail: 'The app can call this capability, but it may not know which result fields are most important to show to the user.',
      recommendation: 'Describe the result shape more clearly, or add app display guidance for the important fields.',
      capability_id: capabilityId,
      source: 'capability',
    })
  }
}

function analyzeInput(
  capability: DeveloperCapabilityFormalization,
  input: DeveloperCapabilityInputFormalization,
  sinks: {
    addFinding: (finding: AgentConsumptionReadinessFinding) => void
    addProbe: (probe: AgentConsumptionReadinessProbe) => void
    addGlue: (glue: AgentConsumptionReadinessRequiredGlue) => void
  },
) {
  const capabilityId = capability.capability_id || capability.id
  const resolution = input.resolution
  const hasDefault = String(input.default_value ?? '').trim().length > 0
    || resolution?.on_missing === 'use_default'
  const hasClarification = String(input.clarification_hint ?? '').trim().length > 0
    || resolution?.on_missing === 'clarify'
    || resolution?.on_ambiguous === 'clarify'
    || resolution?.on_unresolved === 'clarify'
  const hasFormat = String(input.input_format ?? '').trim().length > 0 || String(input.validation_pattern ?? '').trim().length > 0
  const hasOmissionRule = hasDefault
    || hasClarification
    || ['use_actor_scope', 'app_select_or_clarify', 'deny', 'deny_or_clarify', 'omit'].includes(resolution?.on_missing ?? '')
  const hasNormalization = String(input.normalization_hint ?? '').trim().length > 0
    || String(input.normalization_context ?? '').trim().length > 0
    || (input.allowed_value_semantics ?? []).length > 0
    || (resolution?.mode === 'closed_values' && (input.allowed_values ?? []).length > 0)
  const isContextInput = Boolean(input.semantic_type) || isFormattedBusinessScopeInput(input) || input.entity_reference === true
  const isTemporalScopeInput = isFormattedBusinessScopeInput(input)
  const isReferenceScope = isReferenceScopeInput(input)

  if (input.required && !hasExplicitInputClassification(input)) {
    sinks.addFinding({
      id: `${capabilityId}:${input.input_name}:classification`,
      severity: 'blocker',
      category: 'clarification_behavior',
      owner: 'developer_contract',
      title: 'Required input needs meaning',
      detail: `${input.input_name} is required, but the contract does not yet state what kind of business value it represents or how a user should provide it.`,
      recommendation: 'Add semantic_type, input_format, allowed values, entity reference metadata, validation pattern, or clarification guidance before saving Developer Definition.',
      capability_id: capabilityId,
      input_name: input.input_name,
      source: 'capability',
    })
  }

  if (input.required && isContextInput && !hasDefault && !hasClarification && !hasFormat) {
    sinks.addFinding({
      id: `${capabilityId}:${input.input_name}:clarification`,
      severity: 'warning',
      category: 'clarification_behavior',
      owner: 'developer_contract',
      title: 'Missing input needs runtime clarification',
      detail: `${input.input_name} is required and appears to carry business scope or target context, but the contract does not define what the service or consuming app should ask when the user omits it or provides a vague value.`,
      recommendation: 'Add the clarification prompt the runtime should return instead of guessing.',
      capability_id: capabilityId,
      input_name: input.input_name,
      source: 'capability',
    })
    sinks.addProbe({
      id: `${capabilityId}:${input.input_name}:missing-context-probe`,
      label: 'Missing context probe',
      prompt: `Invoke ${capabilityId} without ${input.input_name}.`,
      expected_outcome: 'clarification_required',
      target_capability_id: capabilityId,
      rationale: 'Required business context should produce a predictable clarification outcome.',
    })
  }

  if (input.required && isTemporalScopeInput) {
    sinks.addProbe({
      id: `${capabilityId}:${input.input_name}:ungrounded-scope-probe`,
      label: 'Ungrounded scope probe',
      prompt: `Ask ${capabilityId} using vague time scope such as this quarter without a concrete value for ${input.input_name}.`,
      expected_outcome: 'clarification_required',
      target_capability_id: capabilityId,
      rationale: 'Agents must not invent required temporal business scope from examples or defaults.',
    })
  }

  if (input.required && isReferenceScope) {
    sinks.addProbe({
      id: `${capabilityId}:${input.input_name}:ungrounded-reference-probe`,
      label: 'Ungrounded reference probe',
      prompt: `Ask ${capabilityId} for top or priority results without naming a concrete value for ${input.input_name}.`,
      expected_outcome: 'clarification_required',
      target_capability_id: capabilityId,
      rationale: 'Agents must not synthesize required reference, cohort, owner, or target scope from examples or implied defaults.',
    })
  }

  if (!input.required && isContextInput && !hasOmissionRule) {
    sinks.addFinding({
      id: `${capabilityId}:${input.input_name}:optional-context-default`,
      severity: 'info',
      category: 'declared_defaults',
      owner: 'developer_contract',
      title: 'Optional input needs an omission rule',
      detail: `${input.input_name} is optional but appears to change the business scope. The package should state what happens when the caller omits it.`,
      recommendation: 'Add a default, add a clarification question, or state that the service resolves the scope itself.',
      capability_id: capabilityId,
      input_name: input.input_name,
      source: 'capability',
    })
  }

  if ((input.allowed_values ?? []).length > 0 && !hasNormalization) {
    sinks.addFinding({
      id: `${capabilityId}:${input.input_name}:enum-meaning`,
      severity: 'warning',
      category: 'app_glue',
      owner: 'agent_app_glue',
      title: 'Allowed choices need plain-language meanings',
      detail: `${input.input_name} has allowed values, but the contract does not explain what each choice means in business language.`,
      recommendation: 'Add short meanings for each choice so the app can map user intent without a long phrase list.',
      capability_id: capabilityId,
      input_name: input.input_name,
      source: 'capability',
    })
    sinks.addGlue({
      id: `${capabilityId}:${input.input_name}:input-meanings`,
      title: 'Input meanings',
      detail: `${input.input_name} needs compact value meanings so app prompts can ground user language without hardcoded phrase lists.`,
      recommendation: 'Describe what each allowed value means in business terms.',
      capability_id: capabilityId,
      category: 'app_glue',
    })
  }
}

function analyzeScenario(
  scenario: DeveloperScenarioFormalization,
  definition: DeveloperDefinitionData,
  sinks: {
    addFinding: (finding: AgentConsumptionReadinessFinding) => void
    addProbe: (probe: AgentConsumptionReadinessProbe) => void
    addGlue: (glue: AgentConsumptionReadinessRequiredGlue) => void
  },
) {
  const capabilities = definition.capability_formalizations ?? []
  const scenarioText = normalizeText([
    scenario.scenario_title,
    scenario.business_scope,
    scenario.side_effect_formalization,
    scenario.required_behaviors.join(' '),
    scenario.implementation_notes,
  ].join(' '))
  const scenarioId = scenario.scenario_id || scenario.scenario_key || scenario.scenario_title

  if (hasAnyToken(scenarioText, UNSUPPORTED_EFFECT_TOKENS)) {
    const hasDeclaredBoundary = capabilities.some((capability) =>
      (capability.business_effects?.does_not_produce ?? []).some((effect) =>
        ['external_dispatch', 'raw_data_export', 'system.mutation'].includes(effect),
      ),
    )
    if (!hasDeclaredBoundary) {
      sinks.addFinding({
        id: `${scenarioId}:unsupported-effect-boundary`,
        severity: 'warning',
        category: 'unsupported_effect',
        owner: 'developer_contract',
      title: 'Unsupported user requests need a clear boundary',
      detail: 'This scenario mentions actions such as sending, exporting, publishing, dispatching, or changing downstream systems, but the package does not clearly say whether those actions are unsupported.',
      recommendation: `Declare unsupported outcomes such as ${effectLabel('external_dispatch')}, ${effectLabel('raw_data_export')}, or ${effectLabel('system.mutation')}, or add an approval-required capability if the package should support them.`,
      source: 'scenario',
    })
    }
    sinks.addProbe({
      id: `${scenarioId}:unsupported-effect-probe`,
      label: 'Unsupported scenario effect probe',
      prompt: `Ask the package to send, export, publish, or mutate in the context of ${scenario.scenario_title}.`,
      expected_outcome: hasDeclaredBoundary ? 'unsupported' : 'denied',
      rationale: 'Unsupported business effects should be caught before app glue or benchmark tests discover them.',
    })
  }

  if ((scenario.orchestration_steps ?? []).length > 1) {
    const hasCompositionForScenario = capabilities.some((capability) => capability.composition?.steps?.length)
    const hasFrontingAdapterOwnership = scenarioUsesFrontingAdapterMappings(scenario, definition)
    if (!hasCompositionForScenario && !hasFrontingAdapterOwnership) {
      sinks.addFinding({
        id: `${scenarioId}:composition-candidate`,
        severity: 'warning',
        category: 'composition_candidate',
        owner: 'developer_contract',
        title: 'Who owns the multi-step user request?',
        detail: 'This scenario has more than one step. The contract should state whether one service owns the full flow, or the consuming app coordinates the steps.',
        recommendation: 'Choose one reviewed path: make it a service-owned flow, or mark the remaining coordination as app-owned glue.',
        source: 'scenario',
      })
      sinks.addGlue({
        id: `${scenarioId}:scenario-routing-glue`,
        title: 'Scenario routing preference',
        detail: 'The app may need product-level routing guidance if this multi-step behavior is not a composed ANIP capability.',
        recommendation: 'Keep this guidance in an app profile and do not duplicate service integration mechanics.',
        category: 'composition_candidate',
      })
    }
  }
}

function scenarioUsesFrontingAdapterMappings(
  scenario: DeveloperScenarioFormalization,
  definition: DeveloperDefinitionData,
): boolean {
  const mappings = definition.integration_fronting?.capability_mappings ?? []
  if (mappings.length === 0) return false
  const mappingsByCapability = new Map(mappings.map((mapping) => [mapping.capability_id, mapping]))
  const capabilityIds = (scenario.orchestration_steps ?? [])
    .map((step) => step.capability_id)
    .filter((id) => String(id ?? '').trim().length > 0)
  const targetIds = capabilityIds.length > 0
    ? capabilityIds
    : [scenario.primary_capability].filter((id) => String(id ?? '').trim().length > 0)
  if (targetIds.length === 0) return false
  return targetIds.every((capabilityId) => {
    const mapping = mappingsByCapability.get(capabilityId)
    if (!mapping) return false
    const directRawOperations = mapping.raw_operation_refs ?? []
    const boundRawOperations = (mapping.backend_bindings ?? []).flatMap((binding) => binding.raw_operation_refs ?? [])
    return directRawOperations.length > 0 || boundRawOperations.length > 0
  })
}

function buildReport(params: {
  findings: AgentConsumptionReadinessFinding[]
  probes: AgentConsumptionReadinessProbe[]
  requiredGlue: AgentConsumptionReadinessRequiredGlue[]
}): AgentConsumptionReadinessReport {
  const blockers = params.findings.filter((finding) => finding.severity === 'blocker').length
  const warnings = params.findings.filter((finding) => finding.severity === 'warning').length
  const info = params.findings.filter((finding) => finding.severity === 'info').length
  const score = readinessScore(blockers, warnings, info)
  return {
    artifact_type: 'agent_consumption_readiness',
    status: readinessStatus(blockers, warnings, score),
    score,
    summary: {
      blockers,
      warnings,
      info,
      probes: params.probes.length,
      required_app_glue: params.requiredGlue.length,
    },
    findings: params.findings.sort((left, right) =>
      severityRank(left.severity) - severityRank(right.severity)
      || left.title.localeCompare(right.title),
    ),
    probes: params.probes,
    required_app_glue: params.requiredGlue,
  }
}

function severityRank(severity: AgentConsumptionReadinessSeverity): number {
  if (severity === 'blocker') return 0
  if (severity === 'warning') return 1
  return 2
}

function normalizeText(value: string): string {
  return value.toLowerCase().replace(/[_-]/g, ' ')
}

function hasAnyToken(value: string, tokens: string[]): boolean {
  return tokens.some((token) => {
    const normalizedToken = normalizeText(token).trim()
    if (!normalizedToken) return false
    if (normalizedToken.includes('.')) return value.includes(normalizedToken)
    const escaped = normalizedToken.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    if (STEM_MATCH_TOKENS.has(normalizedToken)) {
      return new RegExp(`\\b${escaped}\\w*\\b`).test(value)
    }
    return new RegExp(`\\b${escaped}\\b`).test(value)
  })
}
