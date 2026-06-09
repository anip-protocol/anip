import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import EvaluationView from '../views/EvaluationView.vue'

const {
  createEvaluation,
  generateDriftAnalysis,
  refreshArtifacts,
  clearPendingRuntimeObservation,
  recordRuntimeObservation,
  fetchAudit,
  designStore,
  projectStore,
} = vi.hoisted(() => ({
  createEvaluation: vi.fn(),
  generateDriftAnalysis: vi.fn().mockResolvedValue(null),
  refreshArtifacts: vi.fn(),
  clearPendingRuntimeObservation: vi.fn(),
  recordRuntimeObservation: vi.fn((observation: any) => {
    designStore.pendingRuntimeObservation = observation
    designStore.runtimeObservationHistory = [
      observation,
      ...designStore.runtimeObservationHistory.filter((item: any) => item.observation_id !== observation.observation_id),
    ]
  }),
  fetchAudit: vi.fn(),
  designStore: {
    liveEvaluation: {
      evaluation: {
        scenario_name: 'account_risk_review',
        result: 'PARTIAL',
        handled_by_anip: ['clarification handling'],
        glue_you_will_still_write: [],
        glue_category: ['clarification'],
        why: ['Need clearer next-step handling.'],
        what_would_improve: ['Attach runtime evidence to the saved evaluation.'],
      },
    },
    observedServiceMetadata: {
      source: 'inspect_discovery',
      observed_at: '2026-04-11T11:00:00Z',
      service_id: 'svc-gtm',
      base_url: 'http://localhost:9100',
      protocol: 'anip/0.2',
      trust_level: 'anchored',
      compliance: 'full',
      capabilities: [
        {
          id: 'gtm.account_risk_summary',
          side_effect: 'read',
          minimum_scope: ['accounts.read'],
          financial: false,
          contract: 'AccountRiskSummary',
          requires_binding: [],
          control_requirements: [],
          refresh_via: [],
          verify_via: [],
          followup_via: [],
          cross_service_handoff: [],
          cross_service_refresh: [],
          cross_service_verify: [],
          cross_service_followup: [],
        },
        {
          id: 'gtm.pipeline_summary',
          side_effect: 'read',
          minimum_scope: ['pipeline.read'],
          financial: false,
          contract: 'PipelineSummary',
          requires_binding: [],
          control_requirements: [],
          refresh_via: [],
          verify_via: [],
          followup_via: [],
          cross_service_handoff: [],
          cross_service_refresh: [],
          cross_service_verify: [],
          cross_service_followup: [],
        },
      ],
    },
    selectedObservedServiceMetadataId: null as string | null,
    pendingRuntimeObservation: {
      observation_id: 'obs-1',
      observed_at: '2026-04-11T10:00:00Z',
      invocation_id: 'inv-123',
      invoked_capability: 'gtm.account_risk_summary',
      observed_outcome: 'clarification_required',
      reason_code: 'clarification_loop_detected',
      unresolved_inputs: ['risk_cohort'],
      retry_without_progress: true,
      agent_behavior: 'retried same capability without resolving inputs',
      backend_context: 'gtm.account_risk_summary:read',
    },
    validating: false,
    validationError: null,
    apiAvailable: false,
    draftRequirements: null,
    draftScenario: null,
    originalProposal: null,
    runtimeObservationHistory: [
      {
        observation_id: 'obs-1',
        observed_at: '2026-04-11T10:00:00Z',
        invocation_id: 'inv-123',
        invoked_capability: 'gtm.account_risk_summary',
        observed_outcome: 'clarification_required',
        reason_code: 'clarification_loop_detected',
        unresolved_inputs: ['risk_cohort'],
        retry_without_progress: true,
        agent_behavior: 'retried same capability without resolving inputs',
        backend_context: 'gtm.account_risk_summary:read',
      },
      {
        observation_id: 'obs-2',
        observed_at: '2026-04-11T10:05:00Z',
        invocation_id: 'inv-456',
        invoked_capability: 'gtm.pipeline_summary',
        observed_outcome: 'available',
        reason_code: null,
        unresolved_inputs: [],
        retry_without_progress: false,
        agent_behavior: null,
        backend_context: 'gtm.pipeline_summary:read',
      },
    ],
  },
  projectStore: {
    activeProject: { id: 'proj-1' },
    runtimeStatus: {
      read_only_mode: false,
      read_only_reason: null,
    },
    activeRequirementsId: 'req-1',
    activeProposalId: 'prop-1',
    activeShapeId: null,
    artifacts: {
      requirements: [{ id: 'req-1', data: { requirements: { goals: ['Review account risk'] } } }],
      proposals: [{
        id: 'prop-1',
        data: {
          proposal: {
            recommended_shape: 'single_service',
            declared_surfaces: {
              authority_posture: true,
              binding_requirements: true,
            },
          },
        },
      }],
      serviceMetadata: [],
      shapes: [],
      scenarios: [{
        id: 'scn-1',
        title: 'Account Risk Review',
        data: {
          scenario: {
            name: 'account_risk_review',
            context: { capability: 'gtm.account_risk_summary' },
          },
        },
      }],
      pmArtifacts: [
        {
          id: 'developer-definition-1',
          title: 'Developer Definition',
          data: {
            artifact_type: 'developer_definition',
            compiled_contract_identity: {
              signature: 'compiled-contract-sig-1',
              artifact_name: 'Developer Definition',
            },
          },
        },
      ],
      evaluations: [],
    },
  },
}))

vi.mock('../design/store', () => ({
  designStore,
  composeDraftProposal: () => null,
  clearPendingRuntimeObservation: (...args: any[]) => clearPendingRuntimeObservation(...args),
  recordRuntimeObservation: (observation: any) => recordRuntimeObservation(observation),
  setSelectedObservedServiceMetadataId: (artifactId: string | null) => {
    designStore.selectedObservedServiceMetadataId = artifactId
  },
}))

vi.mock('../design/project-store', () => ({
  projectStore,
  loadProject: vi.fn(),
  refreshArtifacts: (...args: any[]) => refreshArtifacts(...args),
}))

vi.mock('../design/project-api', () => ({
  createEvaluation: (...args: any[]) => createEvaluation(...args),
  explainEvaluationWithAssistant: vi.fn(),
  generateDriftAnalysis: (...args: any[]) => generateDriftAnalysis(...args),
}))

vi.mock('../api', () => ({
  fetchAudit: (...args: any[]) => fetchAudit(...args),
}))

vi.mock('../design/api', () => ({
  runShapeValidation: vi.fn(),
  runValidation: vi.fn(),
}))

vi.mock('../store', () => ({
  store: {
    baseUrl: 'http://localhost:9100',
    bearer: 'demo-human-key',
    connected: true,
    serviceId: '',
    error: '',
    loading: false,
  },
}))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory('/studio'),
    routes: [
      { path: '/design/projects/:projectId/evaluations/:id', name: 'evaluation', component: EvaluationView },
      { path: '/inspect/audit', name: 'audit', component: { template: '<div />' } },
    ],
  })
}

async function mountView() {
  const router = makeRouter()
  router.push('/design/projects/proj-1/evaluations/scn-1')
  await router.isReady()

  const wrapper = mount(EvaluationView, {
    global: {
      plugins: [router],
      stubs: {
        StudioAssistantPanel: true,
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

function findButtonByText(wrapper: any, text: string) {
  return wrapper.findAll('button').find((node: any) => node.text().includes(text))
}

beforeEach(() => {
  createEvaluation.mockReset()
  refreshArtifacts.mockReset()
  generateDriftAnalysis.mockReset()
  generateDriftAnalysis.mockResolvedValue(null)
  clearPendingRuntimeObservation.mockReset()
  recordRuntimeObservation.mockClear()
  fetchAudit.mockReset()
  createEvaluation.mockResolvedValue({ id: 'eval-saved-1' })
  refreshArtifacts.mockResolvedValue(undefined)
  fetchAudit.mockResolvedValue({
    count: 1,
    entries: [
      {
        invocation_id: 'inv-999',
        capability: 'gtm.execute_followup_tasks',
        success: false,
        failure_type: 'approval_required',
        event_class: 'high_risk_denial',
        task_id: 'task-9',
      },
    ],
  })
  designStore.liveEvaluation = {
    evaluation: {
      scenario_name: 'account_risk_review',
      result: 'PARTIAL',
      handled_by_anip: ['clarification handling'],
      glue_you_will_still_write: [],
      glue_category: ['clarification'],
      why: ['Need clearer next-step handling.'],
      what_would_improve: ['Attach runtime evidence to the saved evaluation.'],
    },
  }
  designStore.observedServiceMetadata = {
    source: 'inspect_discovery',
    observed_at: '2026-04-11T11:00:00Z',
    service_id: 'svc-gtm',
    base_url: 'http://localhost:9100',
    protocol: 'anip/0.2',
    trust_level: 'anchored',
    compliance: 'full',
    capabilities: [
        {
          id: 'gtm.account_risk_summary',
          side_effect: 'read',
          minimum_scope: ['accounts.read'],
          financial: false,
          contract: 'AccountRiskSummary',
          requires_binding: [],
          control_requirements: [],
          refresh_via: [],
          verify_via: [],
          followup_via: [],
          cross_service_handoff: [],
          cross_service_refresh: [],
          cross_service_verify: [],
          cross_service_followup: [],
        },
        {
          id: 'gtm.pipeline_summary',
          side_effect: 'read',
          minimum_scope: ['pipeline.read'],
          financial: false,
          contract: 'PipelineSummary',
          requires_binding: [],
          control_requirements: [],
          refresh_via: [],
          verify_via: [],
          followup_via: [],
          cross_service_handoff: [],
          cross_service_refresh: [],
          cross_service_verify: [],
          cross_service_followup: [],
        },
    ],
  }
  designStore.pendingRuntimeObservation = {
    observation_id: 'obs-1',
    observed_at: '2026-04-11T10:00:00Z',
    invocation_id: 'inv-123',
    invoked_capability: 'gtm.account_risk_summary',
    observed_outcome: 'clarification_required',
    reason_code: 'clarification_loop_detected',
    unresolved_inputs: ['risk_cohort'],
    retry_without_progress: true,
    agent_behavior: 'retried same capability without resolving inputs',
    backend_context: 'gtm.account_risk_summary:read',
  }
  designStore.runtimeObservationHistory = [
    { ...designStore.pendingRuntimeObservation },
    {
      observation_id: 'obs-2',
      observed_at: '2026-04-11T10:05:00Z',
      invocation_id: 'inv-456',
      invoked_capability: 'gtm.pipeline_summary',
      observed_outcome: 'available',
      reason_code: null,
      unresolved_inputs: [],
      retry_without_progress: false,
      agent_behavior: null,
      backend_context: 'gtm.pipeline_summary:read',
    },
  ]
  designStore.selectedObservedServiceMetadataId = null
  ;(projectStore.artifacts as any).serviceMetadata = []
  ;(projectStore.artifacts as any).pmArtifacts = [
    {
      id: 'developer-definition-1',
      title: 'Developer Definition',
      data: {
        artifact_type: 'developer_definition',
        source_inputs: {
          product_revision_artifact_id: 'product-revision-1',
          product_revision_number: 2,
        },
        compiled_contract_identity: {
          signature: 'compiled-contract-sig-1',
          artifact_name: 'Developer Definition',
        },
        saved_revision: {
          revision_artifact_id: 'developer-revision-1',
          revision_number: 4,
        },
      },
    },
    {
      id: 'developer-generation-run-1',
      title: 'Developer Generation Run',
      data: {
        artifact_type: 'developer_generation_run',
        generated_at: '2026-04-11T12:00:00Z',
        compiled_contract_identity: {
          signature: 'compiled-contract-sig-1',
          artifact_name: 'Developer Definition',
        },
        definition_revision_artifact_id: 'developer-revision-1',
        definition_revision_number: 4,
        source_inputs: {
          product_revision_artifact_id: 'product-revision-1',
          product_revision_number: 2,
        },
        generator_inputs: {
          runtime_target_mode: 'compiled_contract',
          primary_output_mode: 'runtime_target',
          dependency_source: 'local',
        },
        outputs: {
          runtime_target: [],
        },
      },
    },
  ]
  projectStore.artifacts.evaluations = []
})

describe('EvaluationView', () => {
  it('attaches the pending runtime observation when saving a live evaluation', async () => {
    vi.spyOn(globalThis.crypto, 'randomUUID').mockReturnValue('00000000-0000-4000-8000-000000000001')
    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('Attach latest runtime observation from')
    const select = wrapper.find('.runtime-select')
    expect(select.exists()).toBe(true)
    await select.setValue('obs-2')
    const saveButton = findButtonByText(wrapper, 'Save to Project')
    expect(saveButton).toBeTruthy()
    await saveButton!.trigger('click')
    await flushPromises()

    expect(createEvaluation).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      id: '00000000-0000-4000-8000-000000000001',
      scenario_id: 'scn-1',
      requirements_id: 'req-1',
      proposal_id: 'prop-1',
      data: expect.objectContaining({
        evidence: expect.objectContaining({
          definition_revision_artifact_id: 'developer-revision-1',
          definition_revision_number: 4,
          product_revision_artifact_id: 'product-revision-1',
          product_revision_number: 2,
          service_metadata_snapshot: expect.objectContaining({
            service_id: 'svc-gtm',
            protocol: 'anip/0.2',
          }),
        }),
        evaluation: expect.objectContaining({
          runtime_observations: expect.objectContaining({
            observation_id: 'obs-2',
            invocation_id: 'inv-456',
            invoked_capability: 'gtm.pipeline_summary',
          }),
          runtime_observation_history: expect.arrayContaining([
            expect.objectContaining({ observation_id: 'obs-1' }),
            expect.objectContaining({ observation_id: 'obs-2' }),
          ]),
        }),
      }),
    }))
    expect(clearPendingRuntimeObservation).toHaveBeenCalled()
  })

  it('imports a runtime observation from audit and saves the imported trace', async () => {
    vi.spyOn(globalThis.crypto, 'randomUUID').mockReturnValue('00000000-0000-4000-8000-000000000002')
    const { wrapper } = await mountView()

    const auditInput = wrapper.find('input[placeholder="invocation_id"]')
    expect(auditInput.exists()).toBe(true)
    await auditInput.setValue('inv-999')
    await wrapper.find('.import-btn').trigger('click')
    await flushPromises()

    expect(fetchAudit).toHaveBeenCalledWith('http://localhost:9100', 'demo-human-key', {
      invocationId: 'inv-999',
      limit: '5',
    })
    expect(wrapper.text()).toContain('Imported gtm.execute_followup_tasks (inv-999)')

    const saveButton = findButtonByText(wrapper, 'Save to Project')
    expect(saveButton).toBeTruthy()
    await saveButton!.trigger('click')
    await flushPromises()

    expect(createEvaluation).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      id: '00000000-0000-4000-8000-000000000002',
      data: expect.objectContaining({
        evaluation: expect.objectContaining({
          runtime_observations: expect.objectContaining({
            observation_id: 'inv-999',
            invocation_id: 'inv-999',
            invoked_capability: 'gtm.execute_followup_tasks',
            observed_outcome: 'approval_required',
            reason_code: 'approval_required',
            task_id: 'task-9',
          }),
          runtime_observation_history: expect.arrayContaining([
            expect.objectContaining({ observation_id: 'inv-999' }),
          ]),
        }),
      }),
    }))
  })

  it('can load recent audit traces and use one as runtime evidence', async () => {
    vi.spyOn(globalThis.crypto, 'randomUUID').mockReturnValue('00000000-0000-4000-8000-000000000003')
    fetchAudit.mockResolvedValueOnce({
      count: 2,
      entries: [
        {
          invocation_id: 'inv-777',
          capability: 'gtm.prepare_followup_tasks',
          success: true,
          event_class: 'low_risk_success',
        },
        {
          invocation_id: 'inv-778',
          capability: 'gtm.execute_followup_tasks',
          success: false,
          failure_type: 'approval_required',
          event_class: 'high_risk_denial',
          task_id: 'task-77',
        },
      ],
    })

    const { wrapper } = await mountView()

    const loadButton = findButtonByText(wrapper, 'Load recent audit traces')
    expect(loadButton).toBeTruthy()
    await loadButton!.trigger('click')
    await flushPromises()

    expect(fetchAudit).toHaveBeenCalledWith('http://localhost:9100', 'demo-human-key', {
      limit: '10',
    })
    expect(wrapper.text()).toContain('gtm.prepare_followup_tasks')
    expect(wrapper.text()).toContain('gtm.execute_followup_tasks')

    const traceButtons = wrapper.findAll('.audit-trace-item')
    expect(traceButtons).toHaveLength(2)
    await traceButtons[1].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Imported gtm.execute_followup_tasks (inv-778)')

    const saveButton = findButtonByText(wrapper, 'Save to Project')
    expect(saveButton).toBeTruthy()
    await saveButton!.trigger('click')
    await flushPromises()

    expect(createEvaluation).toHaveBeenCalledWith('proj-1', expect.objectContaining({
      id: '00000000-0000-4000-8000-000000000003',
      data: expect.objectContaining({
        evaluation: expect.objectContaining({
          runtime_observations: expect.objectContaining({
            observation_id: 'inv-778',
            invocation_id: 'inv-778',
            invoked_capability: 'gtm.execute_followup_tasks',
            observed_outcome: 'approval_required',
            task_id: 'task-77',
          }),
          runtime_observation_history: expect.arrayContaining([
            expect.objectContaining({ observation_id: 'obs-1' }),
            expect.objectContaining({ observation_id: 'inv-778' }),
          ]),
        }),
      }),
    }))
  })

  it('imports runtime evidence from the auditInvocationId route query', async () => {
    fetchAudit.mockResolvedValueOnce({
      count: 1,
      entries: [
        {
          invocation_id: 'inv-route',
          capability: 'gtm.prepare_followup_tasks',
          success: false,
          failure_type: 'clarification_required',
          event_class: 'low_risk_success',
        },
      ],
    })

    const router = makeRouter()
    router.push('/design/projects/proj-1/evaluations/scn-1?auditInvocationId=inv-route')
    await router.isReady()

    const wrapper = mount(EvaluationView, {
      global: {
        plugins: [router],
        stubs: {
          StudioAssistantPanel: true,
        },
      },
    })
    await flushPromises()

    expect(fetchAudit).toHaveBeenCalledWith('http://localhost:9100', 'demo-human-key', {
      invocationId: 'inv-route',
      limit: '5',
    })
    expect(wrapper.text()).toContain('Imported gtm.prepare_followup_tasks (inv-route)')
  })

  it('shows intended versus observed service metadata side by side', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('Intended Design vs Observed Implementation')
    expect(wrapper.text()).toContain('Intended Design')
    expect(wrapper.text()).toContain('Observed Implementation')
    expect(wrapper.text()).toContain('gtm.account_risk_summary')
    expect(wrapper.text()).toContain('gtm.pipeline_summary')
    expect(wrapper.text()).toContain('authority_posture')
    expect(wrapper.text()).toContain('binding_requirements')
    expect(wrapper.text()).toContain('Aligned capabilities:')
    expect(wrapper.text()).toContain('Missing from implementation: none')
    expect(wrapper.text()).toContain('Broader than intended: gtm.pipeline_summary')
    expect(wrapper.text()).toContain('Source: live inspect session')
  })

  it('respects the selected persisted observed metadata snapshot', async () => {
    ;(projectStore.artifacts as any).serviceMetadata = [
      {
        id: 'service-metadata-svc-a',
        title: 'Observed Service Metadata: svc-a',
        data: {
          source: 'inspect_discovery',
          observed_at: '2026-04-11T12:00:00Z',
          service_id: 'svc-a',
          protocol: 'anip/0.2',
          trust_level: 'anchored',
          capabilities: [{
            id: 'gtm.account_risk_summary',
            minimum_scope: [],
            financial: false,
            requires_binding: [],
            control_requirements: [],
            refresh_via: [],
            verify_via: [],
            followup_via: [],
            cross_service_handoff: [],
            cross_service_refresh: [],
            cross_service_verify: [],
            cross_service_followup: [],
          }],
        },
      },
      {
        id: 'service-metadata-svc-b',
        title: 'Observed Service Metadata: svc-b',
        data: {
          source: 'inspect_discovery',
          observed_at: '2026-04-11T12:05:00Z',
          service_id: 'svc-b',
          protocol: 'anip/0.2',
          trust_level: 'signed',
          capabilities: [{
            id: 'gtm.pipeline_summary',
            minimum_scope: [],
            financial: false,
            requires_binding: [],
            control_requirements: [],
            refresh_via: [],
            verify_via: [],
            followup_via: [],
            cross_service_handoff: [],
            cross_service_refresh: [],
            cross_service_verify: [],
            cross_service_followup: [],
          }],
        },
      },
    ]
    designStore.selectedObservedServiceMetadataId = 'service-metadata-svc-b'

    const { wrapper } = await mountView()

    expect(wrapper.text()).toContain('Service: svc-b')
    expect(wrapper.text()).toContain('Source: selected project artifact (service-metadata-svc-b)')
    expect(wrapper.text()).toContain('Capabilities: gtm.pipeline_summary')
  })

  it('passes the selected observed metadata snapshot into drift analysis', async () => {
    ;(projectStore.artifacts as any).serviceMetadata = [
      {
        id: 'service-metadata-svc-a',
        title: 'Observed Service Metadata: svc-a',
        data: {
          source: 'inspect_discovery',
          observed_at: '2026-04-11T12:00:00Z',
          service_id: 'svc-a',
          protocol: 'anip/0.2',
          trust_level: 'anchored',
          capabilities: [{
            id: 'gtm.account_risk_summary',
            minimum_scope: [],
            financial: false,
            requires_binding: [],
            control_requirements: [],
            refresh_via: [],
            verify_via: [],
            followup_via: [],
            cross_service_handoff: [],
            cross_service_refresh: [],
            cross_service_verify: [],
            cross_service_followup: [],
          }],
        },
      },
      {
        id: 'service-metadata-svc-b',
        title: 'Observed Service Metadata: svc-b',
        data: {
          source: 'inspect_discovery',
          observed_at: '2026-04-11T12:05:00Z',
          service_id: 'svc-b',
          protocol: 'anip/0.2',
          trust_level: 'signed',
          capabilities: [{
            id: 'gtm.pipeline_summary',
            minimum_scope: [],
            financial: false,
            requires_binding: [],
            control_requirements: [],
            refresh_via: [],
            verify_via: [],
            followup_via: [],
            cross_service_handoff: [],
            cross_service_refresh: [],
            cross_service_verify: [],
            cross_service_followup: [],
          }],
        },
      },
    ]
    ;(projectStore.artifacts as any).evaluations = [
      {
        id: 'scn-1',
        scenario_id: 'scn-1',
        requirements_id: 'req-1',
        proposal_id: 'prop-1',
        shape_id: null,
        data: {
          evaluation: {
            scenario_name: 'account_risk_review',
            result: 'HANDLED',
            handled_by_anip: ['summary generation'],
            glue_you_will_still_write: [],
            glue_category: [],
            why: ['Observed metadata should line up with the intended capability surface.'],
            what_would_improve: [],
          },
        },
        input_snapshot: {},
      },
    ] as any
    designStore.selectedObservedServiceMetadataId = 'service-metadata-svc-b'

    await mountView()

    expect(generateDriftAnalysis).toHaveBeenCalledWith(expect.objectContaining({
      project_id: 'proj-1',
      evaluation_id: 'scn-1',
      service_metadata_artifact_id: 'service-metadata-svc-b',
      metadata_comparison: expect.objectContaining({
        missing_capabilities: ['gtm.account_risk_summary'],
        extra_capabilities: ['gtm.pipeline_summary'],
        observed: expect.objectContaining({
          service_id: 'svc-b',
        }),
      }),
    }))
  })

  it('uses stored service metadata snapshots when inspect metadata is not in memory', async () => {
    ;(designStore as any).liveEvaluation = null
    ;(designStore as any).observedServiceMetadata = null
    ;(projectStore.artifacts as any).evaluations = [
      {
        id: 'eval-1',
        scenario_id: 'scn-1',
        requirements_id: 'req-1',
        proposal_id: 'prop-1',
        shape_id: null,
        data: {
          evaluation: {
            scenario_name: 'account_risk_review',
            result: 'HANDLED',
            handled_by_anip: ['summary generation'],
            glue_you_will_still_write: [],
            glue_category: [],
            why: ['Observed metadata matches the intended capability.'],
            what_would_improve: [],
          },
          evidence: {
            service_metadata_snapshot: {
              source: 'inspect_discovery',
              observed_at: '2026-04-11T12:00:00Z',
              service_id: 'svc-stored',
              protocol: 'anip/0.2',
              trust_level: 'anchored',
              capabilities: [
                {
                  id: 'gtm.account_risk_summary',
                  minimum_scope: ['accounts.read'],
                  financial: false,
                  contract: 'AccountRiskSummary',
                  requires_binding: [],
                  control_requirements: [],
                  refresh_via: [],
                  verify_via: [],
                  followup_via: [],
                  cross_service_handoff: [],
                  cross_service_refresh: [],
                  cross_service_verify: [],
                  cross_service_followup: [],
                },
              ],
            },
          },
        },
        input_snapshot: {
          scenario: {
            scenario: {
              name: 'account_risk_review',
              context: { capability: 'gtm.account_risk_summary' },
            },
          },
          proposal: {
            proposal: {
              recommended_shape: 'single_service',
              declared_surfaces: {
                authority_posture: true,
                binding_requirements: true,
              },
            },
          },
        },
      },
    ] as any

    const router = makeRouter()
    router.push('/design/projects/proj-1/evaluations/eval-1')
    await router.isReady()

    const wrapper = mount(EvaluationView, {
      global: {
        plugins: [router],
        stubs: {
          StudioAssistantPanel: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Intended Design vs Observed Implementation')
    expect(wrapper.text()).toContain('svc-stored')
    expect(wrapper.text()).toContain('Aligned capabilities: gtm.account_risk_summary')
    expect(wrapper.text()).toContain('Source: saved evaluation snapshot (eval-1)')
  })
})
