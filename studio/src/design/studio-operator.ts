import { createPmArtifact, updatePmArtifact } from './project-api'
import type {
  ArtifactRecord,
  CoverageStatus,
  HighRiskConfirmationItem,
  ProjectDetail,
  TraceabilityCoverageItem,
} from './project-types'
import type { AgentConsumptionReadinessFinding, AgentConsumptionReadinessReport } from './agent-consumption-readiness'

export const STUDIO_OPERATOR_ACTIVITY_LOG_ARTIFACT_TYPE = 'studio_operator_activity_log'
export const STUDIO_OPERATOR_HANDOFF_SUMMARY_ARTIFACT_TYPE = 'studio_operator_handoff_summary'

export type StudioOperatorTaskKind =
  | 'source_docs_needed'
  | 'draft_product_design'
  | 'lock_product_baseline'
  | 'draft_developer_design'
  | 'resolve_coverage_coordination'
  | 'resolve_app_readiness'
  | 'open_generation_gate'

export type StudioOperatorTaskState = 'ready' | 'blocked' | 'complete'

export interface StudioOperatorTask {
  id: string
  kind: StudioOperatorTaskKind
  title: string
  detail: string
  why_it_matters: string
  safe_action_label: string
  success_condition: string
  state: StudioOperatorTaskState
  target_path?: string | null
  requires_human_decision?: boolean
}

export interface StudioOperatorProjectState {
  project: ProjectDetail | null | undefined
  documents_count: number
  source_docs_label?: string
  source_docs_empty_detail?: string
  source_docs_path?: string | null
  source_evidence_ready?: boolean
  source_evidence_detail?: string
  source_evidence_mode_guidance?: string
  product_blocked: boolean
  baseline_locked: boolean
  developer_draft_available: boolean
  developer_design_saved: boolean
  developer_definition_saved: boolean
  coverage_blocked: boolean
  developer_blocked: boolean
  app_readiness_blocked: boolean
  source_ready: boolean
  developer_ready: boolean
}

export interface CoordinationResolutionChoice {
  id: 'contract_owned' | 'app_owned' | 'deferred' | 'out_of_scope'
  label: string
  plain_language: string
  status: CoverageStatus
  rationale: string
  effect: string
  next_path?: string | null
  patch_preview: {
    title: string
    target_artifact: string
    requires_review: boolean
    changes: string[]
  }
}

export interface StudioOperatorActivity {
  id: string
  created_at: string
  title: string
  detail: string
  task_id?: string
  task_kind?: StudioOperatorTaskKind
  outcome: 'started' | 'completed' | 'needs_review' | 'blocked'
}

export interface StudioOperatorActivityLogData {
  artifact_type: typeof STUDIO_OPERATOR_ACTIVITY_LOG_ARTIFACT_TYPE
  events: StudioOperatorActivity[]
  updated_at: string
}

export interface StudioOperatorHandoffSummaryData {
  artifact_type: typeof STUDIO_OPERATOR_HANDOFF_SUMMARY_ARTIFACT_TYPE
  generated_at: string
  project_id: string
  project_name: string
  overall_status: 'ready_for_generation' | 'needs_review' | 'blocked'
  next_action: {
    title: string
    detail: string
    target_path?: string | null
    requires_human_decision: boolean
  } | null
  counts: {
    complete: number
    ready: number
    blocked: number
    needs_human_decision: number
    recent_activity: number
  }
  blockers: Array<{
    title: string
    detail: string
    target_path?: string | null
    requires_human_decision: boolean
  }>
  completed: Array<{
    title: string
    detail: string
  }>
  recent_activity: StudioOperatorActivity[]
}

export interface StudioOperatorDecisionQueueItem {
  id: string
  source_id: string
  source: 'coordination' | 'high_risk' | 'readiness'
  severity: 'blocker' | 'warning' | 'info'
  title: string
  detail: string
  review_target: string
  why_human: string
  done_when: string
  recommendation: string
  route: string | null
  affected_label?: string
  action_label: string
  actions: StudioOperatorDecisionQueueAction[]
}

export interface StudioOperatorDecisionQueueAction {
  id: string
  label: string
  detail: string
  safe_to_apply: boolean
}

export function createStudioOperatorActivity(args: {
  title: string
  detail: string
  task?: StudioOperatorTask | null
  outcome: StudioOperatorActivity['outcome']
  now?: string
}): StudioOperatorActivity {
  const createdAt = args.now ?? new Date().toISOString()
  return {
    id: `operator:${createdAt}:${slugify(args.title)}`,
    created_at: createdAt,
    title: args.title,
    detail: args.detail,
    task_id: args.task?.id,
    task_kind: args.task?.kind,
    outcome: args.outcome,
  }
}

export function findStudioOperatorActivityLogArtifact(artifacts: ArtifactRecord[]): ArtifactRecord | null {
  return artifacts.find((artifact) => artifact.data?.artifact_type === STUDIO_OPERATOR_ACTIVITY_LOG_ARTIFACT_TYPE) ?? null
}

export function findStudioOperatorHandoffSummaryArtifact(artifacts: ArtifactRecord[]): ArtifactRecord | null {
  return artifacts.find((artifact) => artifact.data?.artifact_type === STUDIO_OPERATOR_HANDOFF_SUMMARY_ARTIFACT_TYPE) ?? null
}

export function studioOperatorActivityLogFromArtifact(artifact: ArtifactRecord | null): StudioOperatorActivityLogData | null {
  const data = artifact?.data
  if (!data || data.artifact_type !== STUDIO_OPERATOR_ACTIVITY_LOG_ARTIFACT_TYPE) return null
  return {
    artifact_type: STUDIO_OPERATOR_ACTIVITY_LOG_ARTIFACT_TYPE,
    events: Array.isArray(data.events) ? data.events as StudioOperatorActivity[] : [],
    updated_at: typeof data.updated_at === 'string' ? data.updated_at : artifact?.updated_at ?? new Date().toISOString(),
  }
}

export function studioOperatorHandoffSummaryFromArtifact(artifact: ArtifactRecord | null): StudioOperatorHandoffSummaryData | null {
  const data = artifact?.data
  if (!data || data.artifact_type !== STUDIO_OPERATOR_HANDOFF_SUMMARY_ARTIFACT_TYPE) return null
  return data as unknown as StudioOperatorHandoffSummaryData
}

export async function persistStudioOperatorActivity(args: {
  projectId: string
  pmArtifacts: ArtifactRecord[]
  event: StudioOperatorActivity
  maxEvents?: number
}): Promise<ArtifactRecord> {
  const existing = findStudioOperatorActivityLogArtifact(args.pmArtifacts)
  const previous = studioOperatorActivityLogFromArtifact(existing)?.events ?? []
  const maxEvents = args.maxEvents ?? 100
  const events = [args.event, ...previous.filter((event) => event.id !== args.event.id)].slice(0, maxEvents)
  const data: StudioOperatorActivityLogData = {
    artifact_type: STUDIO_OPERATOR_ACTIVITY_LOG_ARTIFACT_TYPE,
    events,
    updated_at: args.event.created_at,
  }
  if (existing) {
    return updatePmArtifact(args.projectId, existing.id, {
      title: 'Studio Autopilot Activity Log',
      status: 'active',
      data,
    })
  }
  return createPmArtifact(args.projectId, {
    id: `${args.projectId}-studio-operator-activity-log`,
    title: 'Studio Autopilot Activity Log',
    data,
  })
}

export function buildStudioOperatorHandoffSummary(args: {
  project: ProjectDetail
  tasks: StudioOperatorTask[]
  activities: StudioOperatorActivity[]
  generatedAt?: string
}): StudioOperatorHandoffSummaryData {
  const generatedAt = args.generatedAt ?? new Date().toISOString()
  const nextAction = nextStudioOperatorTask(args.tasks)
  const blockers = args.tasks
    .filter((task) => task.state !== 'complete')
    .map((task) => ({
      title: task.title,
      detail: task.detail,
      target_path: task.target_path,
      requires_human_decision: Boolean(task.requires_human_decision),
    }))
  const completed = args.tasks
    .filter((task) => task.state === 'complete')
    .map((task) => ({
      title: task.title,
      detail: task.success_condition,
    }))
  const readyCount = args.tasks.filter((task) => task.state === 'ready').length
  const blockedCount = args.tasks.filter((task) => task.state === 'blocked').length
  const completeCount = completed.length
  const needsHumanDecisionCount = args.tasks.filter((task) => task.state !== 'complete' && task.requires_human_decision).length
  const overallStatus: StudioOperatorHandoffSummaryData['overall_status'] =
    nextAction?.state === 'blocked'
      ? 'blocked'
      : needsHumanDecisionCount > 0 || readyCount > 0
        ? 'needs_review'
        : 'ready_for_generation'
  return {
    artifact_type: STUDIO_OPERATOR_HANDOFF_SUMMARY_ARTIFACT_TYPE,
    generated_at: generatedAt,
    project_id: args.project.id,
    project_name: args.project.name,
    overall_status: overallStatus,
    next_action: nextAction
      ? {
          title: nextAction.title,
          detail: nextAction.detail,
          target_path: nextAction.target_path,
          requires_human_decision: Boolean(nextAction.requires_human_decision),
        }
      : null,
    counts: {
      complete: completeCount,
      ready: readyCount,
      blocked: blockedCount,
      needs_human_decision: needsHumanDecisionCount,
      recent_activity: args.activities.length,
    },
    blockers,
    completed,
    recent_activity: args.activities.slice(0, 10),
  }
}

export async function persistStudioOperatorHandoffSummary(args: {
  projectId: string
  pmArtifacts: ArtifactRecord[]
  summary: StudioOperatorHandoffSummaryData
}): Promise<ArtifactRecord> {
  const existing = findStudioOperatorHandoffSummaryArtifact(args.pmArtifacts)
  if (existing) {
    return updatePmArtifact(args.projectId, existing.id, {
      title: 'Studio Autopilot Handoff Summary',
      status: 'active',
      data: args.summary,
    })
  }
  return createPmArtifact(args.projectId, {
    id: `${args.projectId}-studio-operator-handoff-summary`,
    title: 'Studio Autopilot Handoff Summary',
    data: args.summary,
  })
}

export function buildStudioOperatorDecisionQueue(args: {
  projectId: string
  coverage: TraceabilityCoverageItem[]
  highRiskItems: HighRiskConfirmationItem[]
  readinessReport?: AgentConsumptionReadinessReport | null
  limit?: number
}): StudioOperatorDecisionQueueItem[] {
  const limit = args.limit ?? 12
  const coordination = args.coverage
    .filter((item) =>
      item.id.startsWith('shape:coordination:')
      && item.status !== 'addressed'
      && item.status !== 'not_applicable'
      && item.status !== 'deferred',
    )
    .map((item): StudioOperatorDecisionQueueItem => ({
      id: `coordination:${item.id}`,
      source_id: item.id,
      source: 'coordination',
      severity: item.status === 'deferred' ? 'info' : 'warning',
      title: 'Service relationship needs a decision',
      detail: item.detail || item.label,
      review_target: `Coverage Mapping -> ${item.label || 'service relationship'}`,
      why_human: 'Studio cannot safely guess whether this relationship is service-owned behavior, consuming-app orchestration, follow-up work, or out of scope.',
      done_when: 'The relationship has a reviewed owner and will not silently become generated behavior.',
      recommendation: 'Decide whether this relationship is owned by a service capability, consuming app glue, follow-up work, or out of scope.',
      route: `/design/projects/${args.projectId}/developer/coverage`,
      affected_label: item.label,
      action_label: 'Open Coordination Review',
      actions: coordinationResolutionChoices(item, args.projectId).map((choice) => ({
        id: choice.id,
        label: choice.label,
        detail: choice.effect,
        safe_to_apply: !choice.patch_preview.requires_review,
      })),
    }))

  const highRisk = args.highRiskItems.map((item): StudioOperatorDecisionQueueItem => ({
    id: `high-risk:${item.id}`,
    source_id: item.id,
    source: 'high_risk',
    severity: item.severity,
    title: item.title,
    detail: item.detail,
    review_target: highRiskReviewTarget(item),
    why_human: highRiskHumanReason(item),
    done_when: highRiskDoneWhen(item),
    recommendation: item.recommendation,
    route: highRiskRoute(args.projectId, item),
    affected_label: item.related_ids?.slice(0, 3).join(', '),
    action_label: highRiskActionLabel(item),
    actions: highRiskActions(item),
  }))

  const reviews = args.readinessReport?.finding_reviews ?? {}
  const readiness = (args.readinessReport?.findings ?? [])
    .filter((finding) => !reviews[finding.id])
    .map((finding): StudioOperatorDecisionQueueItem => ({
      id: `readiness:${finding.id}`,
      source_id: finding.id,
      source: 'readiness',
      severity: finding.severity,
      title: finding.title,
      detail: finding.detail,
      review_target: readinessReviewTarget(finding),
      why_human: readinessHumanReason(finding),
      done_when: readinessDoneWhen(finding),
      recommendation: finding.recommendation,
      route: readinessRoute(args.projectId, finding),
      affected_label: [finding.capability_id, finding.input_name].filter(Boolean).join(' · ') || undefined,
      action_label: finding.owner === 'agent_app_glue' || finding.category === 'app_glue'
        ? 'Open App Glue Review'
        : 'Open Readiness Review',
      actions: readinessActions(finding),
    }))

  return [...highRisk, ...readiness, ...coordination]
    .sort((a, b) => severityRank(a.severity) - severityRank(b.severity))
    .slice(0, limit)
}

function readinessActions(finding: AgentConsumptionReadinessFinding): StudioOperatorDecisionQueueAction[] {
  const actions: StudioOperatorDecisionQueueAction[] = []
  if (finding.owner === 'agent_app_glue' || finding.category === 'app_glue' || finding.category === 'derived_target') {
    actions.push({
      id: 'explicit_app_glue',
      label: 'App owns it',
      detail: 'Classify this as package-specific app guidance, not generic ANIP runtime behavior.',
      safe_to_apply: true,
    })
  }
  if (finding.owner === 'developer_contract' || finding.category === 'composition_candidate' || finding.category === 'approval_boundary') {
    actions.push({
      id: 'contract_composition',
      label: 'Service owns it',
      detail: 'Classify this as service-owned contract behavior; open the editor if structure must be changed.',
      safe_to_apply: true,
    })
  }
  actions.push(
    {
      id: 'acceptable_warning',
      label: 'Accept limitation',
      detail: 'Record that this warning is understood and acceptable for this package revision.',
      safe_to_apply: true,
    },
    {
      id: 'follow_up',
      label: 'Follow up',
      detail: 'Keep this item open as follow-up work rather than treating the package as fully ready.',
      safe_to_apply: true,
    },
  )
  return actions
}

function highRiskRoute(projectId: string, item: HighRiskConfirmationItem): string {
  if (item.id === 'developer-clarification:capability_contracts') {
    return `/design/projects/${projectId}/developer/capability-formalization#capability-contracts`
  }
  if (item.id === 'capability-identity:canonical-ids') {
    const capabilityId = item.related_ids?.find(Boolean)
    return `/design/projects/${projectId}/developer/capability-formalization${capabilityId ? `#${encodeURIComponent(capabilityId)}` : ''}`
  }
  if (item.id === 'capability-identity:service-ownership') {
    const serviceId = item.related_ids?.map((value) => String(value).split(':')[0]).find((value) => value && value !== 'unassigned')
    return `/design/projects/${projectId}/developer/service-formalization${serviceId ? `#${encodeURIComponent(serviceId)}` : ''}`
  }
  if (item.id === 'service-ownership:services-without-capabilities') {
    const serviceId = item.related_ids?.find(Boolean)
    return `/design/projects/${projectId}/developer/service-formalization${serviceId ? `#${encodeURIComponent(serviceId)}` : ''}`
  }
  if (item.category === 'composition_ambiguity') {
    const capabilityId = item.related_ids?.find(Boolean)
    return `/design/projects/${projectId}/developer/capability-formalization${capabilityId ? `#${encodeURIComponent(capabilityId)}` : ''}`
  }
  return item.target_route ?? `/design/projects/${projectId}/developer/coverage`
}

function highRiskActionLabel(item: HighRiskConfirmationItem): string {
  if (item.id === 'developer-clarification:capability_contracts') return 'Provide Input Contracts'
  if (item.category === 'capability_identity') return 'Review Capability IDs'
  if (item.category === 'service_ownership') return 'Review Service Ownership'
  if (item.category === 'composition_ambiguity') return 'Resolve Composition Choice'
  if (item.category === 'permission_mapping') return 'Review Permissions'
  if (item.source === 'product_design') return 'Open Product Review'
  return 'Open Owning Review'
}

function highRiskActions(item: HighRiskConfirmationItem): StudioOperatorDecisionQueueItem['actions'] {
  if (item.id === 'developer-clarification:capability_contracts') {
    return []
  }
  return [
    {
      id: 'confirm',
      label: 'Confirm',
      detail: 'Record that this assumption has been reviewed and accepted as contract or generation truth.',
      safe_to_apply: true,
    },
    {
      id: 'defer',
      label: 'Defer',
      detail: 'Record that this remains intentional follow-up and must not silently become generated behavior.',
      safe_to_apply: true,
    },
  ]
}

function highRiskReviewTarget(item: HighRiskConfirmationItem): string {
  if (item.id === 'developer-clarification:capability_contracts') return 'Capability Formalization -> input contracts'
  if (item.id === 'capability-identity:canonical-ids') return 'Capability Formalization -> stable capability IDs'
  if (item.id === 'capability-identity:service-ownership') return 'Service Formalization -> capability ownership'
  if (item.id === 'service-ownership:services-without-capabilities') return 'Service Formalization -> services without capabilities'
  if (item.category === 'composition_ambiguity') return 'Capability Formalization -> composed capability source choice'
  if (item.category === 'permission_mapping') return 'Actors, Access & Audit -> mapped permission references'
  return item.source === 'product_design' ? 'Product Design review' : 'Developer Design review'
}

function highRiskHumanReason(item: HighRiskConfirmationItem): string {
  if (item.id === 'developer-clarification:capability_contracts') {
    return 'Concrete input names, types, required flags, defaults, and allowed values become generated service contracts. Studio can draft them from source evidence, but final save remains blocked until the contracts are reviewed.'
  }
  if (item.id === 'capability-identity:canonical-ids') {
    return 'Capability IDs become durable Registry, verifier, generator, and consuming-app identity. Renaming them later is a contract revision, not a cosmetic edit.'
  }
  if (item.id === 'capability-identity:service-ownership') {
    return 'Service ownership drives generated service boundaries. Studio can propose owners, but a human must confirm this is the intended architecture.'
  }
  if (item.id === 'service-ownership:services-without-capabilities') {
    return 'A service with no canonical capabilities may be dead architecture, external glue, or a missing contract surface. Studio should not choose silently.'
  }
  if (item.category === 'composition_ambiguity') {
    return 'Multiple source capabilities can plausibly feed the same governed preparation step. Studio must ask instead of silently making one source contract truth.'
  }
  if (item.category === 'permission_mapping') {
    return 'Permission mappings affect runtime access. A guessed actor or business-area binding can grant, restrict, or deny the wrong behavior.'
  }
  return 'This decision would become contract or generated behavior, so Autopilot Mode stops instead of inventing intent.'
}

function highRiskDoneWhen(item: HighRiskConfirmationItem): string {
  if (item.id === 'developer-clarification:capability_contracts') return 'Each source-declared capability has reviewed concrete input contract details.'
  if (item.id === 'capability-identity:canonical-ids') return 'IDs are confirmed as canonical or edited in Capability Formalization.'
  if (item.id === 'capability-identity:service-ownership') return 'Each capability has the intended owning service, or the ambiguity is explicitly deferred.'
  if (item.id === 'service-ownership:services-without-capabilities') return 'Each service either owns canonical capabilities, is merged away, or is explicitly deferred/out of scope.'
  if (item.category === 'composition_ambiguity') return 'The source capability is explicitly chosen in scenario orchestration, the composed capability is edited, or the behavior is marked app-owned/deferred.'
  if (item.category === 'permission_mapping') return 'Mapped permissions are confirmed or corrected before they affect runtime policy.'
  return 'The ambiguity is confirmed, deferred, or fixed in the owning design page.'
}

export function buildStudioOperatorTasks(state: StudioOperatorProjectState): StudioOperatorTask[] {
  const projectId = state.project?.id ?? ''
  const tasks: StudioOperatorTask[] = []
  const sourceEvidenceReady = state.source_evidence_ready ?? state.documents_count > 0
  const sourceEvidenceDetail = state.source_evidence_detail
    ?? (state.documents_count > 0
      ? `${state.documents_count} ${state.source_docs_label ?? 'source document'}${state.documents_count === 1 ? '' : 's'} attached.`
      : state.source_docs_empty_detail ?? 'Attach business and technical source documents before drafting.')
  const sourceEvidenceModeGuidance = state.source_evidence_mode_guidance
    ?? 'Use Guided Mode or Manual Mode when source evidence is incomplete.'

  tasks.push({
    id: 'source-docs',
    kind: 'source_docs_needed',
    title: `Attach ${state.source_docs_label ?? 'source documents'}`,
    detail: sourceEvidenceDetail,
    why_it_matters: 'Source docs ground the assistant and give deterministic Studio pages evidence to validate against.',
    safe_action_label: 'Open Source Docs',
    success_condition: 'Source evidence is readable, lane-appropriate, and specific enough for Autopilot to draft safely.',
    state: sourceEvidenceReady ? 'complete' : 'ready',
    target_path: projectId ? (state.source_docs_path ?? `/design/projects/${projectId}/source-docs`) : null,
  })

  const productNeedsSourceEvidence = state.product_blocked && !sourceEvidenceReady
  tasks.push({
    id: 'product-design',
    kind: 'draft_product_design',
    title: 'Build Product Design',
    detail: productNeedsSourceEvidence
      ? `${sourceEvidenceDetail} ${sourceEvidenceModeGuidance}`
      : state.product_blocked
      ? 'Product Design still has gaps Studio should draft or ask about.'
      : 'Product Design is complete enough for Developer Design handoff.',
    why_it_matters: 'Developer contracts should preserve reviewed product intent instead of inferring it later.',
    safe_action_label: 'Run Product Design step',
    success_condition: 'Product Design has no blocking project-level diagnostics.',
    state: state.product_blocked ? (state.source_ready && sourceEvidenceReady ? 'ready' : 'blocked') : 'complete',
  })

  tasks.push({
    id: 'baseline',
    kind: 'lock_product_baseline',
    title: 'Lock Product Design baseline',
    detail: state.baseline_locked
      ? 'A Product Design baseline is locked for Developer Design.'
      : 'Choose the Product Design revision developers must preserve.',
    why_it_matters: 'A locked baseline prevents generated contracts from drifting away from the PM-approved version.',
    safe_action_label: 'Open Developer Overview',
    success_condition: 'Developer baseline is locked against the current Product Design revision.',
    state: state.baseline_locked ? 'complete' : (state.product_blocked ? 'blocked' : 'ready'),
    target_path: projectId ? `/design/projects/${projectId}/developer` : null,
    requires_human_decision: !state.baseline_locked,
  })

  tasks.push({
    id: 'developer-design',
    kind: 'draft_developer_design',
    title: (state.developer_draft_available && !state.developer_design_saved && !state.developer_definition_saved)
      ? 'Review Developer Draft'
      : 'Create Developer Design',
    detail: !sourceEvidenceReady && !state.developer_design_saved && !state.developer_definition_saved
      ? `${sourceEvidenceDetail} ${sourceEvidenceModeGuidance}`
      : state.developer_definition_saved
      ? 'Developer Definition exists.'
      : state.developer_design_saved
        ? 'Developer Design review artifacts exist. Continue with coverage and readiness decisions before saving the definition.'
        : state.developer_draft_available
          ? 'A Developer Design draft is ready. Review and save the selected sections before moving to coverage and readiness gates.'
      : 'Draft and review the Developer Design from the locked baseline.',
    why_it_matters: 'This turns product intent into concrete services, capabilities, access, audit, app glue, and generation settings.',
    safe_action_label: 'Run Developer Design step',
    success_condition: 'Developer Design review artifacts are saved from the locked baseline.',
    state: (state.developer_design_saved || state.developer_definition_saved) ? 'complete' : (state.developer_ready && sourceEvidenceReady ? 'ready' : 'blocked'),
  })

  tasks.push({
    id: 'coverage-coordination',
    kind: 'resolve_coverage_coordination',
    title: 'Resolve coordination decisions',
    detail: 'Any service-to-service relationship must be represented clearly before it becomes implementation expectation.',
    why_it_matters: 'Coordination can mean service-owned behavior, app-owned orchestration, follow-up work, or out-of-scope design intent. Guessing here creates confusing contracts.',
    safe_action_label: 'Open Autopilot Decisions',
    success_condition: 'Each coordination item is marked addressed, deferred, or not applicable with a reviewed rationale.',
    state: state.coverage_blocked ? 'ready' : 'complete',
    target_path: projectId ? `/design/projects/${projectId}/developer/coverage` : null,
    requires_human_decision: state.coverage_blocked,
  })

  tasks.push({
    id: 'app-readiness',
    kind: 'resolve_app_readiness',
    title: 'Resolve app and readiness decisions',
    detail: state.app_readiness_blocked
      ? 'Agent/app consumption has unresolved decisions.'
      : 'Agent/app consumption decisions are clear enough for the next gate.',
    why_it_matters: 'Package-specific app glue should be explicit and packaged, not hidden in generic runtime code.',
    safe_action_label: 'Open Agent & App Glue',
    success_condition: 'Readiness findings are reviewed or fixed and required app glue is saved.',
    state: state.app_readiness_blocked ? 'ready' : 'complete',
    target_path: projectId ? `/design/projects/${projectId}/developer/app-glue` : null,
    requires_human_decision: state.app_readiness_blocked,
  })

  tasks.push({
    id: 'generation',
    kind: 'open_generation_gate',
    title: 'Generate, verify, or publish',
    detail: 'Use deterministic gates once design, readiness, and coverage are clear.',
    why_it_matters: 'Generation and Registry publication should only happen from reviewed, versioned contract artifacts.',
    safe_action_label: 'Open Developer Definition',
    success_condition: 'Definition, verifier, generator, and publication gates pass.',
    state: state.developer_definition_saved && !state.developer_blocked && !state.app_readiness_blocked ? 'ready' : 'blocked',
    target_path: projectId ? `/design/projects/${projectId}/developer/definition` : null,
  })

  return tasks
}

function readinessRoute(projectId: string, finding: AgentConsumptionReadinessFinding): string {
  if (finding.owner === 'agent_app_glue' || finding.category === 'app_glue' || finding.category === 'derived_target') {
    return `/design/projects/${projectId}/developer/app-glue`
  }
  if (finding.owner === 'developer_contract') {
    return `/design/projects/${projectId}/developer/capability-formalization${finding.capability_id ? `#${encodeURIComponent(finding.capability_id)}` : ''}`
  }
  return `/design/projects/${projectId}/developer/coverage`
}

function readinessReviewTarget(finding: AgentConsumptionReadinessFinding): string {
  const capability = finding.capability_id ? ` -> ${finding.capability_id}` : ''
  if (finding.owner === 'agent_app_glue' || finding.category === 'app_glue' || finding.category === 'derived_target') {
    return `Agent & App Glue${capability}`
  }
  if (finding.owner === 'developer_contract') return `Capability Formalization${capability}`
  return `Coverage Mapping${capability}`
}

function readinessHumanReason(finding: AgentConsumptionReadinessFinding): string {
  if (finding.category === 'derived_target') {
    return 'Target selection changes who or what the app acts on. Studio needs a reviewed owner: service capability, consuming app glue, clarification, or follow-up.'
  }
  if (finding.category === 'approval_boundary') {
    return 'Approval boundaries decide whether a request can continue, preview, or stop. That is product and runtime behavior, not a safe default.'
  }
  if (finding.owner === 'agent_app_glue' || finding.category === 'app_glue') {
    return 'This is package-specific consumption behavior. It belongs in reviewed app guidance, not hidden inside generic ANIP runtime code.'
  }
  return 'This affects how an ANIP-aware app consumes the package, so Studio requires an explicit reviewed decision before generation or publication.'
}

function readinessDoneWhen(finding: AgentConsumptionReadinessFinding): string {
  if (finding.owner === 'agent_app_glue' || finding.category === 'app_glue' || finding.category === 'derived_target') {
    return 'The item is classified as app-owned guidance, service-owned behavior, acceptable limitation, or follow-up.'
  }
  if (finding.owner === 'developer_contract') return 'The capability contract is updated or the finding is explicitly accepted/deferred.'
  return 'The finding has a reviewed classification that package export and handoff can preserve.'
}

function severityRank(value: StudioOperatorDecisionQueueItem['severity']): number {
  if (value === 'blocker') return 0
  if (value === 'warning') return 1
  return 2
}

export function nextStudioOperatorTask(tasks: StudioOperatorTask[]): StudioOperatorTask | null {
  return tasks.find((task) => task.state === 'ready') ?? tasks.find((task) => task.state === 'blocked') ?? null
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    || 'event'
}

export function coordinationResolutionChoices(item: TraceabilityCoverageItem, projectId?: string | null): CoordinationResolutionChoice[] {
  const label = item.label || 'this service relationship'
  const sourceDetail = item.detail || 'No source detail provided.'
  return [
    {
      id: 'contract_owned',
      label: 'Service owns the behavior',
      plain_language: 'Use this when one service should expose a reviewed capability that performs the needed sequence internally.',
      status: 'addressed',
      rationale: `Reviewed coordination for ${label}: represented as contract-owned capability behavior in Developer Design. Confirm the capability contract owns the sequence, inputs, outputs, empty-result behavior, and approval boundary.`,
      effect: 'Marks coverage addressed and sends the user to Capability Formalization to review or create the owned capability.',
      next_path: projectId ? `/design/projects/${projectId}/developer/capability-formalization` : null,
      patch_preview: {
        title: 'Coverage decision plus composed-capability review handoff',
        target_artifact: 'Developer Coverage / Capability Formalization',
        requires_review: true,
        changes: [
          `Mark "${label}" as addressed for the locked Product Design baseline.`,
          `Record that this relationship is expected to be owned by a service capability, not hidden app orchestration.`,
          `Carry this source detail into review: ${sourceDetail}`,
          'Reviewer must confirm or create the composed capability, child steps, input/output mapping, empty-result behavior, and approval boundary before generation.',
        ],
      },
    },
    {
      id: 'app_owned',
      label: 'Consuming app owns orchestration',
      plain_language: 'Use this when the agent/app should decide which service to call first and pass the result into another service.',
      status: 'deferred',
      rationale: `Reviewed coordination for ${label}: consuming-app orchestration owns this relationship. Record app-glue guidance before generation/publication.`,
      effect: 'Marks coverage intentionally deferred and sends the user to Agent & App Glue to package the guidance.',
      next_path: projectId ? `/design/projects/${projectId}/developer/app-glue` : null,
      patch_preview: {
        title: 'Coverage decision plus app-glue handoff',
        target_artifact: 'Developer Coverage / Agent & App Glue',
        requires_review: true,
        changes: [
          `Mark "${label}" as intentionally deferred from contract-owned service behavior.`,
          'Record that the consuming app must coordinate this relationship explicitly.',
          `Carry this source detail into app-glue review: ${sourceDetail}`,
          'Reviewer must save package-specific app guidance before relying on simulator or generation gates.',
        ],
      },
    },
    {
      id: 'deferred',
      label: 'Follow-up work',
      plain_language: 'Use this when the relationship is real but not ready to become contract truth yet.',
      status: 'deferred',
      rationale: `Reviewed coordination for ${label}: intentionally deferred for follow-up implementation detail or app-layer orchestration.`,
      effect: 'Records the decision as deferred so generation is not blocked by an implicit assumption.',
      next_path: null,
      patch_preview: {
        title: 'Intentional follow-up decision',
        target_artifact: 'Developer Coverage',
        requires_review: false,
        changes: [
          `Mark "${label}" as intentionally deferred.`,
          'Record that this relationship is real but not ready to become contract truth in this package revision.',
          `Keep source detail for the follow-up trail: ${sourceDetail}`,
        ],
      },
    },
    {
      id: 'out_of_scope',
      label: 'Out of scope',
      plain_language: 'Use this when the source mentioned the relationship, but this package should not own it.',
      status: 'not_applicable',
      rationale: `Reviewed coordination for ${label}: not applicable because this relationship is out of scope for the package contract.`,
      effect: 'Marks the coverage item not applicable with a reviewed rationale.',
      next_path: null,
      patch_preview: {
        title: 'Out-of-scope coverage decision',
        target_artifact: 'Developer Coverage',
        requires_review: false,
        changes: [
          `Mark "${label}" as not applicable for this package contract.`,
          'Record that this package should not own the relationship.',
          `Keep source detail for auditability: ${sourceDetail}`,
        ],
      },
    },
  ]
}
