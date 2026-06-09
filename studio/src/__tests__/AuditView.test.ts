import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { AnipClientKey } from '@anip-dev/vue'
import AuditView from '../views/AuditView.vue'

const recordRuntimeObservation = vi.fn()
const { projectStore } = vi.hoisted(() => ({
  projectStore: {
    activeProject: { id: 'proj-1' },
    activeScenarioId: 'scn-1',
  },
}))

vi.mock('../store', () => ({
  store: {
    baseUrl: 'http://localhost:9100',
    bearer: 'demo-human-key',
    connected: true,
    error: '',
    loading: false,
    serviceId: '',
  },
}))

vi.mock('../design/store', () => ({
  recordRuntimeObservation: (observation: any) => recordRuntimeObservation(observation),
}))

vi.mock('../design/project-store', () => ({
  projectStore,
}))

const mockDiscover = vi.fn()
const mockQueryAudit = vi.fn()

const mockClient = {
  discover: (...args: any[]) => mockDiscover(...args),
  queryAudit: (...args: any[]) => mockQueryAudit(...args),
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory('/studio'),
    routes: [
      { path: '/inspect/audit', name: 'audit', component: AuditView },
      { path: '/design/projects/:projectId/evaluations/:id', name: 'evaluation', component: { template: '<div />' } },
    ],
  })
}

async function mountView(
  initialRoute = '/inspect/audit?capability=gtm.execute_followup_tasks&invocationId=inv-123&taskId=task-1',
) {
  const router = makeRouter()
  router.push(initialRoute)
  await router.isReady()

  const wrapper = mount(AuditView, {
    global: {
      plugins: [router],
      provide: {
        [AnipClientKey as symbol]: mockClient,
      },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  mockDiscover.mockReset()
  mockQueryAudit.mockReset()
  recordRuntimeObservation.mockReset()
  mockDiscover.mockResolvedValue({
    capabilityNames: ['gtm.execute_followup_tasks'],
    capabilities: {},
  })
  mockQueryAudit.mockResolvedValue({
    count: 1,
    entries: [{
      invocation_id: 'inv-123',
      capability: 'gtm.execute_followup_tasks',
      success: false,
      failure_type: 'approval_required',
      event_class: 'high_risk_denial',
      task_id: 'task-1',
    }],
  })
})

describe('AuditView', () => {
  it('hydrates filters from route query and fetches audit entries immediately when already authenticated', async () => {
    const { wrapper } = await mountView()

    expect(mockQueryAudit).toHaveBeenCalledWith('demo-human-key', {
      capability: 'gtm.execute_followup_tasks',
      since: undefined,
      limit: 50,
      invocationId: 'inv-123',
      taskId: 'task-1',
      parentInvocationId: undefined,
    })

    const inputs = wrapper.findAll('input')
    expect(inputs.some((input) => (input.element as HTMLInputElement).value === 'inv-123')).toBe(true)
    expect(wrapper.text()).toContain('Audit Log')
    expect(wrapper.text()).toContain('inv-123')
  })

  it('can record an audit entry as runtime evidence for later evaluation use', async () => {
    const { wrapper } = await mountView()

    await wrapper.find('.entry-row').trigger('click')
    await flushPromises()
    await wrapper.find('.detail-action-btn').trigger('click')

    expect(recordRuntimeObservation).toHaveBeenCalledWith(expect.objectContaining({
      observation_id: 'inv-123',
      source: 'audit',
      invocation_id: 'inv-123',
      invoked_capability: 'gtm.execute_followup_tasks',
      observed_outcome: 'approval_required',
      reason_code: 'approval_required',
      task_id: 'task-1',
      backend_context: 'high_risk_denial',
    }))
    expect(wrapper.text()).toContain('Added to Studio runtime observations')
  })

  it('can hand an audit invocation into the active evaluation flow', async () => {
    const { wrapper, router } = await mountView()

    await wrapper.find('.entry-row').trigger('click')
    await flushPromises()

    const buttons = wrapper.findAll('.detail-action-btn')
    const openButton = buttons.find((node) => node.text().includes('Open in Evaluation'))
    expect(openButton).toBeTruthy()
    await openButton!.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('evaluation')
    expect(router.currentRoute.value.params.projectId).toBe('proj-1')
    expect(router.currentRoute.value.params.id).toBe('scn-1')
    expect(router.currentRoute.value.query.auditInvocationId).toBe('inv-123')
  })
})
