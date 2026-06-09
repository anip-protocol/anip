import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import RequirementsView from '../views/RequirementsView.vue'

const {
  applyAssistantProposal,
  clarifyDesignSectionWithAssistant,
  createRequirements,
  deleteRequirements,
  loadProject,
  openArtifactForEditing,
  projectStore,
  refreshArtifacts,
  setRequirementsRole,
  updateRequirements,
  designStore,
  updateDraftField,
  updateGuidedAnswer,
  discardEdits,
} = vi.hoisted(() => ({
  applyAssistantProposal: vi.fn(),
  clarifyDesignSectionWithAssistant: vi.fn(),
  createRequirements: vi.fn(),
  deleteRequirements: vi.fn(),
  loadProject: vi.fn(),
  openArtifactForEditing: vi.fn(),
  refreshArtifacts: vi.fn().mockResolvedValue(undefined),
  setRequirementsRole: vi.fn(),
  updateRequirements: vi.fn(),
  updateDraftField: vi.fn(),
  updateGuidedAnswer: vi.fn(),
  discardEdits: vi.fn(),
  designStore: {
    editState: 'view',
    draftRequirements: null,
    guidedAnswers: {},
    completenessHints: [],
    requirementsMode: 'guided',
    showFieldMappings: false,
    validationErrors: [],
  },
  projectStore: {
    activeProject: { id: 'proj-1', name: 'Revenue Ops Assistant' },
    artifacts: {
      requirements: [
        {
          id: 'req-1',
          project_id: 'proj-1',
          title: 'Requirements',
          status: 'active',
          role: 'primary',
          data: {
            system: { name: 'Revenue Ops Assistant' },
          },
          content_hash: 'req-hash-1',
          created_at: '2026-04-19T00:00:00Z',
          updated_at: '2026-04-19T00:00:00Z',
        },
      ],
      scenarios: [],
      documents: [
        {
          id: 'doc-1',
          project_id: 'proj-1',
          title: 'Business Spec',
          kind: 'brief',
          filename: 'brief.md',
          media_type: 'text/markdown',
          source_path: '/tmp/brief.md',
          content_hash: 'doc-hash-1',
          created_at: '2026-04-19T00:00:00Z',
          updated_at: '2026-04-19T00:00:00Z',
        },
      ],
      pmArtifacts: [
        {
          id: 'summary-1',
          project_id: 'proj-1',
          title: 'Business Summary',
          status: 'draft',
          data: {
            artifact_type: 'product_summary',
            product_purpose: 'Help operators answer governed revenue questions.',
            business_problem: '',
            business_goals: [],
            supported_question_families: [],
            governed_behavior_summary: '',
            approval_posture_summary: '',
            multi_step_composition_rules: [],
            why_now: '',
            success_outcome_summary: '',
          },
          content_hash: 'summary-hash-1',
          created_at: '2026-04-19T00:00:00Z',
          updated_at: '2026-04-19T00:00:00Z',
        },
      ],
    },
  },
}))

const {
  proposeBusinessSummaryWithAssistant,
} = vi.hoisted(() => ({
  proposeBusinessSummaryWithAssistant: vi.fn(),
}))

vi.mock('../design/store', () => ({
  designStore,
  updateDraftField: (...args: any[]) => updateDraftField(...args),
  setRequirementsMode: (mode: string) => {
    designStore.requirementsMode = mode
  },
  updateGuidedAnswer: (...args: any[]) => updateGuidedAnswer(...args),
  discardEdits: (...args: any[]) => discardEdits(...args),
}))

vi.mock('../design/project-store', () => ({
  loadProject: (...args: any[]) => loadProject(...args),
  projectStore,
  openArtifactForEditing: (...args: any[]) => openArtifactForEditing(...args),
  refreshArtifacts: (...args: any[]) => refreshArtifacts(...args),
}))

vi.mock('../design/project-api', () => ({
  createRequirements: (...args: any[]) => createRequirements(...args),
  deleteRequirements: (...args: any[]) => deleteRequirements(...args),
  setRequirementsRole: (...args: any[]) => setRequirementsRole(...args),
  updateRequirements: (...args: any[]) => updateRequirements(...args),
  applyAssistantProposal: (...args: any[]) => applyAssistantProposal(...args),
  clarifyDesignSectionWithAssistant: (...args: any[]) => clarifyDesignSectionWithAssistant(...args),
  suggestNextStepWithAssistant: vi.fn(),
  proposeRequirementsWithAssistant: vi.fn(),
  proposeScenariosWithAssistant: vi.fn(),
  proposeBusinessSummaryWithAssistant: (...args: any[]) => proposeBusinessSummaryWithAssistant(...args),
  proposeActorModelWithAssistant: vi.fn(),
  proposeBusinessAreasWithAssistant: vi.fn(),
  proposePermissionIntentWithAssistant: vi.fn(),
  proposeNonGoalsWithAssistant: vi.fn(),
  proposeSuccessCriteriaWithAssistant: vi.fn(),
  proposeServiceDesignWithAssistant: vi.fn(),
  proposeCapabilityFormalizationWithAssistant: vi.fn(),
  proposeRuntimePolicyBindingsWithAssistant: vi.fn(),
  proposeInputContractsWithAssistant: vi.fn(),
  proposeVerificationExpectationsWithAssistant: vi.fn(),
  proposeBackendBindingsWithAssistant: vi.fn(),
  identifyMissingBusinessInfoWithAssistant: vi.fn(),
}))

vi.mock('../design/guided/questions', () => ({
  GUIDED_SECTIONS: [],
}))

vi.mock('../design/guided/mappings', () => ({
  hydrateAnswersFromArtifact: vi.fn(() => ({})),
}))

vi.mock('../design/guided/hints', () => ({
  evaluateCompleteness: vi.fn(() => []),
}))

vi.mock('../design/confirm', () => ({
  requestConfirmation: vi.fn().mockResolvedValue(true),
}))

vi.mock('../design/api', () => ({
  runValidation: vi.fn(() => []),
  runShapeValidation: vi.fn(() => []),
}))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory('/studio'),
    routes: [
      {
        path: '/design/projects/:projectId/requirements',
        name: 'requirements-list',
        component: { template: '<div>Requirements List</div>' },
      },
      {
        path: '/design/projects/:projectId/requirements/:id',
        name: 'requirements',
        component: RequirementsView,
      },
      {
        path: '/design/projects/:projectId/product-summary',
        name: 'product-summary',
        component: { template: '<div>Product Summary</div>' },
      },
      {
        path: '/design/projects/:projectId/assistant',
        name: 'project-ai-assistant',
        component: { template: '<div>Project AI Assistant</div>' },
      },
      {
        path: '/design/projects/:projectId/pm/assistant',
        name: 'project-product-ai-assistant',
        component: { template: '<div>Product Design AI Assistant</div>' },
      },
    ],
  })
}

async function mountView() {
  const router = makeRouter()
  router.push('/design/projects/proj-1/requirements/req-1')
  await router.isReady()

  return mount(RequirementsView, {
    global: {
      plugins: [router],
      stubs: {
        GuidedSection: { template: '<div data-test="guided-section" />' },
        RequirementsSummary: { template: '<div data-test="requirements-summary" />' },
        CompletenessHints: { template: '<div data-test="completeness-hints" />' },
        EditorToolbar: { template: '<div data-test="editor-toolbar" />' },
        KeyValueEditor: { template: '<div data-test="key-value-editor" />' },
      },
    },
  })
}

describe('RequirementsView assistant entry point', () => {
  beforeEach(() => {
    vi.stubGlobal('crypto', { randomUUID: () => 'uuid-1' })
    applyAssistantProposal.mockReset()
    clarifyDesignSectionWithAssistant.mockReset()
    proposeBusinessSummaryWithAssistant.mockReset()
    refreshArtifacts.mockClear()
    loadProject.mockClear()
    openArtifactForEditing.mockClear()
    designStore.requirementsMode = 'guided'
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('links users to the dedicated PM AI Assistant page instead of embedding the assistant workflow', async () => {
    clarifyDesignSectionWithAssistant.mockResolvedValue({
      title: 'Clarify Product Summary',
      summary: 'One targeted clarification is needed before drafting.',
      mode: 'pm',
      capability: 'clarify_design_section',
      questions_for_user: ['What business problem is it solving?'],
      watchouts: [],
      next_steps: [],
      proposal: {
        proposal_kind: 'clarification_questions',
        mode: 'pm',
        section_key: 'product_summary',
        questions: [
          {
            question_id: 'q-1',
            prompt: 'What business problem is it solving?',
            why_it_matters: 'The summary is not stable without the business problem.',
            target_artifact: 'product_summary',
          },
        ],
      },
    })
    applyAssistantProposal.mockResolvedValue({ id: 'pm-artifact-1' })
    proposeBusinessSummaryWithAssistant.mockResolvedValue({
      title: 'Business Summary Draft',
      summary: 'Drafted summary from the saved clarification.',
      mode: 'pm',
      capability: 'propose_business_summary',
      questions_for_user: [],
      watchouts: [],
      next_steps: [],
      proposal: {
        proposal_kind: 'patch_candidates',
        artifact_type: 'product_summary',
        patches: [
          {
            path: '/business_problem',
            op: 'replace',
            value: 'Operators rely on manual interpretation and hidden escalation paths.',
            rationale: 'Derived from the saved clarification and source brief.',
          },
        ],
      },
    })

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Need AI help?')
    expect(wrapper.text()).toContain('dedicated project AI Assistant page')
    expect(wrapper.text()).toContain('Open Product Design AI Assistant')

    await wrapper.findAll('button').find((node) => node.text() === 'Open Product Design AI Assistant')!.trigger('click')
    await flushPromises()

    expect(wrapper.vm.$route.fullPath).toBe('/design/projects/proj-1/pm/assistant')
    expect(clarifyDesignSectionWithAssistant).not.toHaveBeenCalled()
    expect(applyAssistantProposal).not.toHaveBeenCalled()
    expect(proposeBusinessSummaryWithAssistant).not.toHaveBeenCalled()
  })
})
