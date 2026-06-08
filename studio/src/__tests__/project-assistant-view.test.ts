import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ProjectAssistantView from '../views/ProjectAssistantView.vue'
import type { AssistantProposalEnvelope } from '../design/project-types'

const { mocks, projectStore } = vi.hoisted(() => ({
  mocks: {
    appendProjectAssistantAuditEvent: vi.fn(),
    createPmArtifact: vi.fn(),
    getProjectDocumentPreview: vi.fn(),
    loadProject: vi.fn(),
    refreshArtifacts: vi.fn(),
    runDevAssistantAction: vi.fn(),
    runPmAssistantAction: vi.fn(),
    updatePmArtifact: vi.fn(),
  },
  projectStore: {
    activeProject: {
      id: 'proj-1',
      workspace_id: 'workspace-1',
      name: 'Revenue Ops Assistant',
      domain: 'revenue',
      summary: '',
      labels: [],
      created_at: '2026-04-20T00:00:00Z',
      updated_at: '2026-04-20T00:00:00Z',
      requirements_count: 0,
      scenarios_count: 0,
      proposals_count: 0,
      shapes_count: 0,
      evaluations_count: 0,
      documents_count: 1,
    },
    artifacts: {
      documents: [
        {
          id: 'doc-1',
          project_id: 'proj-1',
          title: 'Business Spec',
          kind: 'brief',
          filename: 'business-spec.md',
          media_type: 'text/markdown',
          source_path: '/tmp/business-spec.md',
          content_hash: 'doc-hash',
          created_at: '2026-04-20T00:00:00Z',
          updated_at: '2026-04-20T00:00:00Z',
        },
      ],
      pmArtifacts: [],
      requirements: [
        {
          id: 'req-1',
          project_id: 'proj-1',
          title: 'Requirements',
          status: 'active',
          role: 'primary',
          data: { system: { name: 'Revenue Ops Assistant' } },
          content_hash: 'req-hash',
          created_at: '2026-04-20T00:00:00Z',
          updated_at: '2026-04-20T00:00:00Z',
        },
      ],
      scenarios: [
        {
          id: 'scenario-1',
          project_id: 'proj-1',
          title: 'Approval Scenario',
          status: 'active',
          data: { scenario: { name: 'approval_scenario' } },
          content_hash: 'scenario-hash',
          created_at: '2026-04-20T00:00:00Z',
          updated_at: '2026-04-20T00:00:00Z',
        },
      ],
      serviceMetadata: [],
      proposals: [],
      shapes: [
        {
          id: 'shape-1',
          project_id: 'proj-1',
          title: 'Service Shape',
          status: 'active',
          requirements_id: 'req-1',
          data: { shape: { services: [{ id: 'assistant-service' }] } },
          content_hash: 'shape-hash',
          created_at: '2026-04-20T00:00:00Z',
          updated_at: '2026-04-20T00:00:00Z',
        },
      ],
      evaluations: [],
    },
    activeRequirementsId: 'req-1',
    activeShapeId: 'shape-1',
    loading: false,
    error: null,
    runtimeStatus: {
      studio_api_reachable: true,
      assistant_provider: 'openai',
      assistant_model: 'gpt-5.4',
      assistant_base_url: null,
      llm_enabled: true,
      llm_ready: true,
      api_key_configured: true,
      api_key_source: 'stored',
      provider_source: 'stored',
      model_source: 'stored',
      base_url_source: 'default',
      read_only_mode: false,
      read_only_reason: null,
    },
  },
}))

vi.mock('../design/project-store', () => ({
  projectStore,
  loadProject: (...args: any[]) => mocks.loadProject(...args),
  refreshArtifacts: (...args: any[]) => mocks.refreshArtifacts(...args),
}))

vi.mock('../design/project-api', async () => {
  const actual = await vi.importActual<typeof import('../design/project-api')>('../design/project-api')
  return {
    ...actual,
    createPmArtifact: (...args: any[]) => mocks.createPmArtifact(...args),
    appendProjectAssistantAuditEvent: (...args: any[]) => mocks.appendProjectAssistantAuditEvent(...args),
    getProjectDocumentPreview: (...args: any[]) => mocks.getProjectDocumentPreview(...args),
    updatePmArtifact: (...args: any[]) => mocks.updatePmArtifact(...args),
  }
})

vi.mock('../design/assistant-actions', async () => {
  const actual = await vi.importActual<typeof import('../design/assistant-actions')>('../design/assistant-actions')
  return {
    ...actual,
    runDevAssistantAction: (...args: any[]) => mocks.runDevAssistantAction(...args),
    runPmAssistantAction: (...args: any[]) => mocks.runPmAssistantAction(...args),
  }
})

function clarificationEnvelope(action: string): AssistantProposalEnvelope {
  return {
    title: `${action} needs clarification`,
    summary: 'One decision is missing before this section can be drafted.',
    mode: 'pm',
    capability: action,
    questions_for_user: [],
    watchouts: [],
    next_steps: [],
    proposal: {
      proposal_kind: 'clarification_questions',
      mode: 'pm',
      section_key: action,
      questions: [
        {
          question_id: 'q-approval',
          prompt: 'Which actions require approval?',
          why_it_matters: 'Approval posture changes the saved Product Design artifact.',
          target_artifact: 'product_summary',
        },
      ],
    },
  }
}

function patchEnvelope(action: string): AssistantProposalEnvelope {
  return {
    title: `${action} patch`,
    summary: 'Drafted from source and clarification answers.',
    mode: 'pm',
    capability: action,
    questions_for_user: [],
    watchouts: [],
    next_steps: [],
    proposal: {
      proposal_kind: 'patch_candidates',
      artifact_type: 'product_summary',
      patches: [
        {
          path: '/approval_posture_summary',
          op: 'replace',
          value: 'Approval is required before any write action.',
          rationale: 'Derived from the answered clarification.',
        },
      ],
    },
  }
}

function candidateEnvelope(action: string): AssistantProposalEnvelope {
  return {
    title: `${action} candidates`,
    summary: 'Drafted from source context.',
    mode: 'pm',
    capability: action,
    questions_for_user: [],
    watchouts: [],
    next_steps: [],
    proposal: {
      proposal_kind: 'candidate_blocks',
      artifact_type: action,
      items: [
        {
          client_id: `${action}-1`,
          title: 'Draft item',
          body: 'Drafted candidate body.',
          confidence: 'medium',
          rationale: 'Source contains enough signal.',
        },
      ],
    },
  }
}

function devClarificationEnvelope(action: string): AssistantProposalEnvelope {
  return {
    title: `${action} needs clarification`,
    summary: 'One implementation decision is missing before this section can be drafted.',
    mode: 'dev',
    capability: action,
    questions_for_user: [],
    watchouts: [],
    next_steps: [],
    proposal: {
      proposal_kind: 'clarification_questions',
      mode: 'dev',
      section_key: action,
      questions: [
        {
          question_id: 'q-owner',
          prompt: 'Which service owns this capability?',
          why_it_matters: 'Capability ownership affects the generated contract.',
          target_artifact: 'service_design',
        },
      ],
    },
  }
}

function devPatchEnvelope(action: string): AssistantProposalEnvelope {
  return {
    title: `${action} developer patch`,
    summary: 'Drafted from baseline and clarification answers.',
    mode: 'dev',
    capability: action,
    questions_for_user: [],
    watchouts: [],
    next_steps: [],
    proposal: {
      proposal_kind: 'patch_candidates',
      artifact_type: 'service_design',
      patches: [
        {
          path: '/service_design/data/shape/services/0/id',
          op: 'replace',
          value: 'assistant-service',
          rationale: 'Derived from the answered developer clarification.',
        },
      ],
    },
  }
}

function findButton(wrapper: ReturnType<typeof mount>, label: string) {
  const button = wrapper.findAll('button').find((item) => item.text().includes(label))
  if (!button) throw new Error(`Button not found: ${label}`)
  return button
}

async function mountAssistant(lane: 'pm' | 'dev' | 'developer-query' = 'pm') {
  const router = createRouter({
    history: createMemoryHistory('/studio'),
    routes: [
      {
        path: '/design/projects/:projectId/assistant',
        name: 'project-ai-assistant',
        component: ProjectAssistantView,
      },
      {
        path: '/design/projects/:projectId/pm/assistant',
        name: 'project-product-ai-assistant',
        component: ProjectAssistantView,
        meta: { assistantLane: 'pm' },
      },
      {
        path: '/design/projects/:projectId/developer/assistant',
        name: 'project-developer-ai-assistant',
        component: ProjectAssistantView,
        meta: { assistantLane: 'dev' },
      },
      {
        path: '/design/projects/:projectId/source-docs',
        name: 'source-docs',
        component: { template: '<div>Source Docs</div>' },
      },
      {
        path: '/design/projects/:projectId/developer',
        name: 'developer',
        component: { template: '<div>Developer</div>' },
      },
    ],
  })
  router.push(
    lane === 'dev'
      ? '/design/projects/proj-1/developer/assistant'
      : lane === 'developer-query'
        ? '/design/projects/proj-1/assistant?lane=developer'
        : '/design/projects/proj-1/pm/assistant',
  )
  await router.isReady()
  const wrapper = mount(ProjectAssistantView, {
    global: {
      plugins: [router],
    },
  })
  await flushPromises()
  return wrapper
}

async function switchToGuided(wrapper: ReturnType<typeof mount>) {
  await findButton(wrapper, 'Guided').trigger('click')
  await flushPromises()
}

async function finishSectionDraftTimers() {
  await vi.runAllTimersAsync()
  await flushPromises()
}

describe('ProjectAssistantView', () => {
  beforeEach(() => {
    vi.stubGlobal('crypto', { randomUUID: () => 'uuid-1' })
    mocks.appendProjectAssistantAuditEvent.mockReset()
    mocks.createPmArtifact.mockReset()
    mocks.getProjectDocumentPreview.mockReset()
    mocks.loadProject.mockReset()
    mocks.refreshArtifacts.mockReset()
    mocks.runDevAssistantAction.mockReset()
    mocks.runPmAssistantAction.mockReset()
    mocks.updatePmArtifact.mockReset()
    ;(projectStore.artifacts as any).documents = [
      {
        id: 'doc-1',
        project_id: 'proj-1',
        title: 'Business Spec',
        kind: 'business_spec',
        filename: 'business-spec.md',
        media_type: 'text/markdown',
        source_path: '/tmp/business-spec.md',
        content_hash: 'doc-hash',
        created_at: '2026-04-20T00:00:00Z',
        updated_at: '2026-04-20T00:00:00Z',
      },
    ]
    ;(projectStore.artifacts as any).pmArtifacts = []
    mocks.getProjectDocumentPreview.mockResolvedValue({ content: 'Business spec: approval is unclear.' })
    mocks.createPmArtifact.mockImplementation(async (_projectId: string, payload: any) => ({
      id: payload.id,
      project_id: 'proj-1',
      title: payload.title,
      status: 'draft',
      data: payload.data,
      content_hash: 'hash',
      created_at: '2026-04-20T00:00:00Z',
      updated_at: '2026-04-20T00:00:00Z',
    }))
    mocks.appendProjectAssistantAuditEvent.mockImplementation(async (_projectId: string, payload: any) => ({
      id: 'assistant-audit-log-proj-1',
      project_id: 'proj-1',
      title: 'AI Assistant Audit Log',
      status: 'active',
      data: {
        artifact_type: 'assistant_audit_log',
        events: [payload],
        updated_at: '2026-04-20T00:00:00Z',
      },
      content_hash: 'hash',
      created_at: '2026-04-20T00:00:00Z',
      updated_at: '2026-04-20T00:00:00Z',
    }))
    mocks.updatePmArtifact.mockImplementation(async (_projectId: string, artifactId: string, payload: any) => ({
      id: artifactId,
      project_id: 'proj-1',
      title: payload.title,
      status: payload.status,
      data: payload.data,
      content_hash: 'hash',
      created_at: '2026-04-20T00:00:00Z',
      updated_at: '2026-04-20T00:00:00Z',
    }))
    mocks.refreshArtifacts.mockResolvedValue(undefined)
    mocks.runPmAssistantAction.mockImplementation(async (action: string, args: { sourceText: string }) => {
      if (action === 'business_summary' && args.sourceText.includes('Assistant clarification answers')) {
        return patchEnvelope(action)
      }
      if (action === 'business_summary') return clarificationEnvelope(action)
      return candidateEnvelope(action)
    })
    mocks.runDevAssistantAction.mockImplementation(async (action: string, args: { sourceText: string }) => {
      if (action === 'service_design' && args.sourceText.includes('Assistant clarification answers')) {
        return devPatchEnvelope(action)
      }
      if (action === 'service_design') return devClarificationEnvelope(action)
      return candidateEnvelope(action)
    })
    projectStore.runtimeStatus.studio_api_reachable = true
    projectStore.runtimeStatus.assistant_provider = 'openai'
    projectStore.runtimeStatus.assistant_model = 'gpt-5.4'
    projectStore.runtimeStatus.assistant_base_url = null
    projectStore.runtimeStatus.llm_enabled = true
    projectStore.runtimeStatus.llm_ready = true
    projectStore.runtimeStatus.api_key_configured = true
    projectStore.runtimeStatus.api_key_source = 'stored'
    projectStore.runtimeStatus.provider_source = 'stored'
    projectStore.runtimeStatus.model_source = 'stored'
    projectStore.runtimeStatus.base_url_source = 'default'
    projectStore.runtimeStatus.read_only_mode = false
    projectStore.runtimeStatus.read_only_reason = null
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('drafts from source docs, answers clarification, regenerates one section, and shows used context', async () => {
    vi.useFakeTimers()
    ;(projectStore.artifacts as any).pmArtifacts = [
      {
        id: 'summary-1',
        project_id: 'proj-1',
        title: 'Business Summary',
        status: 'draft',
        data: {
          artifact_type: 'product_summary',
          product_purpose: 'Help revenue teams answer governed questions.',
          business_problem: '',
          business_goals: [],
          supported_question_families: [],
          governed_behavior_summary: '',
          approval_posture_summary: 'Approval posture is not decided yet.',
          multi_step_composition_rules: [],
          why_now: '',
          success_outcome_summary: '',
        },
        content_hash: 'summary-hash',
        created_at: '2026-04-20T00:00:00Z',
        updated_at: '2026-04-20T00:00:00Z',
      },
    ]
    const wrapper = await mountAssistant()
    await switchToGuided(wrapper)

    await findButton(wrapper, 'AI Draft Product Design').trigger('click')
    await finishSectionDraftTimers()

    expect(wrapper.text()).toContain('Which actions require approval?')

    const textarea = wrapper.find('textarea')
    await textarea.setValue('Approval is required before any write action.')
    await textarea.trigger('blur')
    await flushPromises()

    await findButton(wrapper, 'Regenerate Section').trigger('click')
    await flushPromises()

    const businessSummaryCalls = mocks.runPmAssistantAction.mock.calls.filter((call) => call[0] === 'business_summary')
    expect(businessSummaryCalls.at(-1)?.[1].sourceText).toContain('Assistant clarification answers for Business Summary')
    expect(businessSummaryCalls.at(-1)?.[1].sourceText).toContain('Approval is required before any write action.')
    expect(wrapper.text()).toContain('Clarification context used for latest regeneration')
    expect(wrapper.text()).toContain('Approval is required before any write action.')
    expect(wrapper.text()).toContain('Patch preview')
    expect(wrapper.text()).toContain('Approval posture is not decided yet.')
    expect(wrapper.text()).toContain('Save Accepted Section')
  })

  it('treats lane=developer as the developer assistant lane', async () => {
    ;(projectStore.artifacts.documents as any) = [
      {
        id: 'developer-source-1',
        project_id: 'proj-1',
        title: 'Developer Evidence',
        kind: 'developer_interface',
        filename: 'developer-evidence.md',
        media_type: 'text/markdown',
        source_path: '/tmp/developer-evidence.md',
        content_hash: 'developer-doc-hash',
        created_at: '2026-04-20T00:00:00Z',
        updated_at: '2026-04-20T00:00:00Z',
      },
    ]

    const wrapper = await mountAssistant('developer-query')

    expect(wrapper.text()).toContain('Developer AI mode needs a locked Product Design baseline')
    expect(wrapper.text()).toContain('Open Developer Overview')
  })

  it('shows assistant readiness and blocks drafting when the LLM key is missing', async () => {
    projectStore.runtimeStatus.llm_ready = false
    projectStore.runtimeStatus.api_key_configured = false
    projectStore.runtimeStatus.api_key_source = 'none'

    const wrapper = await mountAssistant()

    expect(wrapper.text()).toContain('LLM key missing')
    expect(wrapper.text()).toContain('missing')
    expect(wrapper.text()).toContain('Manual / Deterministic Mode')
    expect(wrapper.text()).toContain('Manual mode is active because the assistant is not configured or Studio is read-only.')
    expect(findButton(wrapper, 'Guided').attributes('disabled')).toBeDefined()
    expect(findButton(wrapper, 'Autopilot').attributes('disabled')).toBeDefined()
  })

  it('drafts developer design from a locked baseline and regenerates one clarified section', async () => {
    vi.useFakeTimers()
    ;(projectStore.artifacts as any).pmArtifacts = [
      {
        id: 'baseline-1',
        project_id: 'proj-1',
        title: 'Developer Baseline',
        status: 'active',
        data: {
          artifact_type: 'developer_baseline',
          source_inputs: {
            requirements_id: 'req-1',
            requirements_hash: 'req-hash',
            scenario_ids: ['scenario-1'],
            primary_scenario_id: 'scenario-1',
            scenario_set_hash: 'scenario-hash',
            shape_id: 'shape-1',
            shape_hash: 'shape-hash',
          },
          locked_at: '2026-04-20T00:00:00Z',
          note: 'Locked for developer drafting.',
        },
        content_hash: 'baseline-hash',
        created_at: '2026-04-20T00:00:00Z',
        updated_at: '2026-04-20T00:00:00Z',
      },
    ]

    const wrapper = await mountAssistant('dev')
    await switchToGuided(wrapper)

    await findButton(wrapper, 'AI Draft Developer Design').trigger('click')
    await finishSectionDraftTimers()

    expect(wrapper.text()).toContain('Which service owns this capability?')

    const textarea = wrapper.find('textarea')
    await textarea.setValue('assistant-service owns the capability.')
    await textarea.trigger('blur')
    await flushPromises()

    await findButton(wrapper, 'Regenerate Section').trigger('click')
    await flushPromises()

    const serviceDesignCalls = mocks.runDevAssistantAction.mock.calls.filter((call) => call[0] === 'service_design')
    expect(serviceDesignCalls.at(0)?.[1].sourceText).toContain('locked_product_design_baseline')
    expect(serviceDesignCalls.at(-1)?.[1].sourceText).toContain('Assistant clarification answers for Service Design')
    expect(serviceDesignCalls.at(-1)?.[1].sourceText).toContain('assistant-service owns the capability.')
    expect(wrapper.text()).toContain('Clarification context used for latest regeneration')
    expect(wrapper.text()).toContain('assistant-service owns the capability.')
    expect(wrapper.text()).toContain('Patch preview')
    expect(wrapper.text()).toContain('REPLACE /service_design/data/shape/services/0/id')
  })
})
