import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  buildStudioOperatorDecisionQueue,
  buildStudioOperatorHandoffSummary,
  buildStudioOperatorTasks,
  coordinationResolutionChoices,
  createStudioOperatorActivity,
  findStudioOperatorActivityLogArtifact,
  findStudioOperatorHandoffSummaryArtifact,
  nextStudioOperatorTask,
  persistStudioOperatorActivity,
  persistStudioOperatorHandoffSummary,
  STUDIO_OPERATOR_ACTIVITY_LOG_ARTIFACT_TYPE,
  STUDIO_OPERATOR_HANDOFF_SUMMARY_ARTIFACT_TYPE,
  studioOperatorActivityLogFromArtifact,
  studioOperatorHandoffSummaryFromArtifact,
} from '../design/studio-operator'
import type { ArtifactRecord, ProjectDetail, TraceabilityCoverageItem } from '../design/project-types'

const api = vi.hoisted(() => ({
  createPmArtifact: vi.fn(),
  updatePmArtifact: vi.fn(),
}))

vi.mock('../design/project-api', async () => {
  const actual = await vi.importActual<typeof import('../design/project-api')>('../design/project-api')
  return {
    ...actual,
    createPmArtifact: (...args: any[]) => api.createPmArtifact(...args),
    updatePmArtifact: (...args: any[]) => api.updatePmArtifact(...args),
  }
})

const project = {
  id: 'project-1',
  name: 'Operator Test',
} as ProjectDetail

function baseState(overrides = {}) {
  return {
    project,
    documents_count: 0,
    product_blocked: true,
    baseline_locked: false,
    developer_draft_available: false,
    developer_design_saved: false,
    developer_definition_saved: false,
    coverage_blocked: true,
    developer_blocked: true,
    app_readiness_blocked: true,
    source_ready: false,
    developer_ready: false,
    ...overrides,
  }
}

function coordinationItem(overrides = {}): TraceabilityCoverageItem {
  return {
    id: 'shape:coordination:pipeline:enrichment:handoff',
    source: 'shape',
    section: 'Coordination',
    label: 'Pipeline Service -> Enrichment Service',
    detail: 'Pipeline risk outputs can provide account sets for enrichment.',
    status: 'not_addressed',
    rationale: '',
    linked_surfaces: [],
    ...overrides,
  }
}

function artifact(overrides: Partial<ArtifactRecord>): ArtifactRecord {
  return {
    id: 'artifact-1',
    project_id: 'project-1',
    title: 'Artifact',
    status: 'active',
    data: {},
    content_hash: 'hash',
    created_at: '2026-05-03T00:00:00.000Z',
    updated_at: '2026-05-03T00:00:00.000Z',
    ...overrides,
  }
}

describe('studio operator', () => {
  beforeEach(() => {
    api.createPmArtifact.mockReset()
    api.updatePmArtifact.mockReset()
  })

  it('starts with source documents when no sources are attached', () => {
    const tasks = buildStudioOperatorTasks(baseState())

    expect(nextStudioOperatorTask(tasks)?.kind).toBe('source_docs_needed')
    expect(tasks.find((task) => task.kind === 'draft_product_design')?.state).toBe('blocked')
  })

  it('moves to product drafting when source context is ready', () => {
    const tasks = buildStudioOperatorTasks(baseState({
      documents_count: 2,
      source_ready: true,
    }))

    expect(nextStudioOperatorTask(tasks)?.kind).toBe('draft_product_design')
  })

  it('blocks product Autopilot when attached source evidence is not strong enough', () => {
    const tasks = buildStudioOperatorTasks(baseState({
      documents_count: 2,
      source_ready: true,
      source_evidence_ready: false,
      source_evidence_detail: 'Product source evidence is too weak for Autopilot.',
      source_evidence_mode_guidance: 'Use Guided Mode or Manual Mode instead.',
    }))

    expect(nextStudioOperatorTask(tasks)?.kind).toBe('source_docs_needed')
    expect(tasks.find((task) => task.kind === 'source_docs_needed')?.state).toBe('ready')
    expect(tasks.find((task) => task.kind === 'draft_product_design')?.state).toBe('blocked')
    expect(tasks.find((task) => task.kind === 'draft_product_design')?.detail).toContain('too weak')
  })

  it('blocks developer Autopilot when developer evidence is missing input contracts', () => {
    const tasks = buildStudioOperatorTasks(baseState({
      documents_count: 1,
      product_blocked: false,
      baseline_locked: true,
      developer_ready: true,
      source_ready: true,
      source_evidence_ready: false,
      source_evidence_detail: 'Developer source evidence is missing concrete input contracts.',
      source_evidence_mode_guidance: 'Use Guided Mode for targeted implementation questions.',
    }))

    expect(tasks.find((task) => task.kind === 'draft_developer_design')?.state).toBe('blocked')
    expect(tasks.find((task) => task.kind === 'draft_developer_design')?.detail).toContain('input contracts')
    expect(nextStudioOperatorTask(tasks)?.kind).toBe('source_docs_needed')
  })

  it('blocks developer Autopilot when developer evidence has weak input classification', () => {
    const tasks = buildStudioOperatorTasks(baseState({
      documents_count: 1,
      product_blocked: false,
      baseline_locked: true,
      developer_ready: true,
      source_ready: true,
      source_evidence_ready: false,
      source_evidence_detail: 'Developer source evidence has weak input classification.',
      source_evidence_mode_guidance: 'Add semantic_type or entity_reference before rerunning Autopilot.',
    }))

    const developerTask = tasks.find((task) => task.kind === 'draft_developer_design')
    expect(developerTask?.state).toBe('blocked')
    expect(developerTask?.detail).toContain('weak input classification')
    expect(developerTask?.detail).toContain('semantic_type')
    expect(nextStudioOperatorTask(tasks)?.kind).toBe('source_docs_needed')
  })

  it('moves to generation once design and readiness gates are clear', () => {
    const tasks = buildStudioOperatorTasks(baseState({
      documents_count: 2,
      product_blocked: false,
      baseline_locked: true,
      developer_design_saved: true,
      developer_definition_saved: true,
      coverage_blocked: false,
      developer_blocked: false,
      app_readiness_blocked: false,
      source_ready: true,
      developer_ready: true,
    }))

    expect(nextStudioOperatorTask(tasks)?.kind).toBe('open_generation_gate')
    expect(nextStudioOperatorTask(tasks)?.state).toBe('ready')
  })

  it('moves to coverage decisions after Developer Design artifacts exist but definition save is blocked', () => {
    const tasks = buildStudioOperatorTasks(baseState({
      documents_count: 2,
      product_blocked: false,
      baseline_locked: true,
      developer_design_saved: true,
      developer_definition_saved: false,
      coverage_blocked: true,
      developer_blocked: true,
      app_readiness_blocked: false,
      source_ready: true,
      developer_ready: true,
    }))

    expect(tasks.find((task) => task.kind === 'draft_developer_design')?.state).toBe('complete')
    expect(nextStudioOperatorTask(tasks)?.kind).toBe('resolve_coverage_coordination')
  })

  it('moves to app readiness after coverage is saved but app glue is still blocked', () => {
    const tasks = buildStudioOperatorTasks(baseState({
      documents_count: 2,
      product_blocked: false,
      baseline_locked: true,
      developer_design_saved: true,
      developer_definition_saved: false,
      coverage_blocked: false,
      developer_blocked: true,
      app_readiness_blocked: true,
      source_ready: true,
      developer_ready: true,
    }))

    expect(tasks.find((task) => task.kind === 'resolve_coverage_coordination')?.state).toBe('complete')
    expect(nextStudioOperatorTask(tasks)?.kind).toBe('resolve_app_readiness')
  })

  it('labels the developer task as draft review when an assistant draft exists but artifacts are not saved', () => {
    const tasks = buildStudioOperatorTasks(baseState({
      documents_count: 2,
      product_blocked: false,
      baseline_locked: true,
      developer_draft_available: true,
      developer_design_saved: false,
      developer_definition_saved: false,
      coverage_blocked: true,
      developer_blocked: true,
      app_readiness_blocked: false,
      source_ready: true,
      developer_ready: true,
    }))

    const next = nextStudioOperatorTask(tasks)
    expect(next?.kind).toBe('draft_developer_design')
    expect(next?.title).toBe('Review Developer Draft')
    expect(next?.detail).toContain('draft is ready')
  })

  it('builds reviewed coordination patch previews', () => {
    const choices = coordinationResolutionChoices(coordinationItem(), project.id)

    const contractOwned = choices.find((choice) => choice.id === 'contract_owned')
    const appOwned = choices.find((choice) => choice.id === 'app_owned')

    expect(contractOwned?.status).toBe('addressed')
    expect(contractOwned?.patch_preview.requires_review).toBe(true)
    expect(contractOwned?.patch_preview.changes.join('\n')).toContain('composed capability')
    expect(contractOwned?.next_path).toContain('/developer/capability-formalization')

    expect(appOwned?.status).toBe('deferred')
    expect(appOwned?.patch_preview.changes.join('\n')).toContain('consuming app must coordinate')
    expect(appOwned?.next_path).toContain('/developer/app-glue')
  })

  it('creates inspectable activity events', () => {
    const task = buildStudioOperatorTasks(baseState({ documents_count: 1 }))[0]
    const activity = createStudioOperatorActivity({
      title: 'Started: Attach source documents',
      detail: 'Opening source docs.',
      task,
      outcome: 'started',
      now: '2026-05-03T00:00:00.000Z',
    })

    expect(activity.id).toBe('operator:2026-05-03T00:00:00.000Z:started-attach-source-documents')
    expect(activity.task_kind).toBe('source_docs_needed')
    expect(activity.outcome).toBe('started')
  })

  it('finds and reads persisted activity logs defensively', () => {
    const log = artifact({
      id: 'operator-log',
      data: {
        artifact_type: STUDIO_OPERATOR_ACTIVITY_LOG_ARTIFACT_TYPE,
        updated_at: '2026-05-03T00:00:00.000Z',
        events: [],
      },
    })

    expect(findStudioOperatorActivityLogArtifact([artifact({ id: 'other' }), log])?.id).toBe('operator-log')
    expect(studioOperatorActivityLogFromArtifact(log)?.artifact_type).toBe(STUDIO_OPERATOR_ACTIVITY_LOG_ARTIFACT_TYPE)
    expect(studioOperatorActivityLogFromArtifact(artifact({ data: { artifact_type: 'other' } }))).toBeNull()
  })

  it('creates a persisted activity log when none exists', async () => {
    api.createPmArtifact.mockResolvedValue(artifact({ id: 'project-1-studio-operator-activity-log' }))
    const event = createStudioOperatorActivity({
      title: 'Completed: Attach source documents',
      detail: 'Source docs are attached.',
      outcome: 'completed',
      now: '2026-05-03T01:00:00.000Z',
    })

    await persistStudioOperatorActivity({
      projectId: 'project-1',
      pmArtifacts: [],
      event,
    })

    expect(api.createPmArtifact).toHaveBeenCalledWith('project-1', {
      id: 'project-1-studio-operator-activity-log',
      title: 'Studio Autopilot Activity Log',
      data: {
        artifact_type: STUDIO_OPERATOR_ACTIVITY_LOG_ARTIFACT_TYPE,
        events: [event],
        updated_at: event.created_at,
      },
    })
  })

  it('updates the persisted activity log with newest events first', async () => {
    api.updatePmArtifact.mockResolvedValue(artifact({ id: 'operator-log' }))
    const olderEvent = createStudioOperatorActivity({
      title: 'Started: Build Product Design',
      detail: 'Running PM lane.',
      outcome: 'started',
      now: '2026-05-03T01:00:00.000Z',
    })
    const newerEvent = createStudioOperatorActivity({
      title: 'Completed: Build Product Design',
      detail: 'PM lane completed.',
      outcome: 'completed',
      now: '2026-05-03T01:05:00.000Z',
    })
    const log = artifact({
      id: 'operator-log',
      data: {
        artifact_type: STUDIO_OPERATOR_ACTIVITY_LOG_ARTIFACT_TYPE,
        updated_at: olderEvent.created_at,
        events: [olderEvent],
      },
    })

    await persistStudioOperatorActivity({
      projectId: 'project-1',
      pmArtifacts: [log],
      event: newerEvent,
    })

    expect(api.updatePmArtifact).toHaveBeenCalledWith('project-1', 'operator-log', {
      title: 'Studio Autopilot Activity Log',
      status: 'active',
      data: {
        artifact_type: STUDIO_OPERATOR_ACTIVITY_LOG_ARTIFACT_TYPE,
        events: [newerEvent, olderEvent],
        updated_at: newerEvent.created_at,
      },
    })
  })

  it('builds handoff summaries from task state and recent activity', () => {
    const tasks = buildStudioOperatorTasks(baseState({
      documents_count: 2,
      product_blocked: false,
      baseline_locked: true,
      developer_definition_saved: true,
      coverage_blocked: false,
      developer_blocked: false,
      app_readiness_blocked: true,
      source_ready: true,
      developer_ready: true,
    }))
    const activity = createStudioOperatorActivity({
      title: 'Opened review page: Resolve app and readiness decisions',
      detail: '/developer/app-glue',
      outcome: 'needs_review',
      now: '2026-05-03T02:00:00.000Z',
    })

    const summary = buildStudioOperatorHandoffSummary({
      project,
      tasks,
      activities: [activity],
      generatedAt: '2026-05-03T02:01:00.000Z',
    })

    expect(summary.artifact_type).toBe(STUDIO_OPERATOR_HANDOFF_SUMMARY_ARTIFACT_TYPE)
    expect(summary.overall_status).toBe('needs_review')
    expect(summary.next_action?.title).toBe('Resolve app and readiness decisions')
    expect(summary.counts.recent_activity).toBe(1)
    expect(summary.blockers.some((item) => item.title === 'Resolve app and readiness decisions')).toBe(true)
  })

  it('finds and reads persisted handoff summaries defensively', () => {
    const summary = buildStudioOperatorHandoffSummary({
      project,
      tasks: buildStudioOperatorTasks(baseState()),
      activities: [],
      generatedAt: '2026-05-03T02:01:00.000Z',
    })
    const summaryArtifact = artifact({
      id: 'summary-log',
      data: summary,
    })

    expect(findStudioOperatorHandoffSummaryArtifact([artifact({ id: 'other' }), summaryArtifact])?.id).toBe('summary-log')
    expect(studioOperatorHandoffSummaryFromArtifact(summaryArtifact)?.project_id).toBe('project-1')
    expect(studioOperatorHandoffSummaryFromArtifact(artifact({ data: { artifact_type: 'other' } }))).toBeNull()
  })

  it('creates and updates persisted handoff summaries', async () => {
    const summary = buildStudioOperatorHandoffSummary({
      project,
      tasks: buildStudioOperatorTasks(baseState()),
      activities: [],
      generatedAt: '2026-05-03T02:01:00.000Z',
    })
    api.createPmArtifact.mockResolvedValue(artifact({ id: 'project-1-studio-operator-handoff-summary' }))

    await persistStudioOperatorHandoffSummary({
      projectId: 'project-1',
      pmArtifacts: [],
      summary,
    })

    expect(api.createPmArtifact).toHaveBeenCalledWith('project-1', {
      id: 'project-1-studio-operator-handoff-summary',
      title: 'Studio Autopilot Handoff Summary',
      data: summary,
    })

    const existing = artifact({
      id: 'summary-log',
      data: summary,
    })
    api.updatePmArtifact.mockResolvedValue(existing)

    await persistStudioOperatorHandoffSummary({
      projectId: 'project-1',
      pmArtifacts: [existing],
      summary,
    })

    expect(api.updatePmArtifact).toHaveBeenCalledWith('project-1', 'summary-log', {
      title: 'Studio Autopilot Handoff Summary',
      status: 'active',
      data: summary,
    })
  })

  it('builds a prioritized operator decision queue', () => {
    const queue = buildStudioOperatorDecisionQueue({
      projectId: 'project-1',
      coverage: [coordinationItem()],
      highRiskItems: [{
        id: 'capability-identity:canonical-ids',
        category: 'capability_identity',
        severity: 'blocker',
        title: 'Confirm canonical capability IDs',
        detail: '9 capability IDs become durable contract identity.',
        recommendation: 'Confirm these IDs before generation.',
        source: 'developer_design',
        target_route: '/design/projects/project-1/developer/capability-formalization',
        related_ids: ['gtm.pipeline_summary'],
      }],
      readinessReport: {
        artifact_type: 'agent_consumption_readiness',
        status: 'needs_review',
        score: 80,
        summary: {
          blockers: 0,
          warnings: 1,
          info: 0,
          probes: 0,
          required_app_glue: 0,
        },
        findings: [{
          id: 'gtm.pipeline_summary:derived-target',
          severity: 'warning',
          category: 'derived_target',
          owner: 'agent_app_glue',
          title: 'Who chooses the target group?',
          detail: 'Derived target behavior needs a reviewed owner.',
          recommendation: 'Decide whether the app or service chooses the target group.',
          capability_id: 'gtm.pipeline_summary',
          source: 'capability',
        }],
        probes: [],
        required_app_glue: [],
        finding_reviews: {},
      },
    })

    expect(queue.map((item) => item.source)).toEqual(['high_risk', 'readiness', 'coordination'])
    expect(queue[0].severity).toBe('blocker')
    expect(queue[1].route).toContain('/developer/app-glue')
    expect(queue[2].action_label).toBe('Open Coordination Review')
  })

  it('routes missing capability input contracts to capability formalization review', () => {
    const queue = buildStudioOperatorDecisionQueue({
      projectId: 'project-1',
      coverage: [],
      highRiskItems: [{
        id: 'developer-clarification:capability_contracts',
        category: 'clarification',
        severity: 'blocker',
        title: 'Capability Contracts needs confirmation',
        detail: 'What are the reviewed implementation input names, types, required flags, defaults, and allowed values?',
        recommendation: 'Provide reviewed input contracts before saving Developer Definition.',
        source: 'developer_design',
      }],
      readinessReport: null,
    })

    expect(queue).toHaveLength(1)
    expect(queue[0].action_label).toBe('Provide Input Contracts')
    expect(queue[0].route).toBe('/design/projects/project-1/developer/capability-formalization#capability-contracts')
    expect(queue[0].actions).toEqual([])
  })
})
