import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { AnipClientKey } from '@anip-dev/vue'
import InvokeView from '../views/InvokeView.vue'

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

const normalizedManifest = {
  protocol: 'anip/0.22',
  capabilities: {
    search_flights: {
      name: 'search_flights',
      description: 'Search flights',
      sideEffect: { type: 'read' },
      minimumScope: ['flights:search'],
      responseModes: ['unary'],
    },
    book_flight: {
      name: 'book_flight',
      description: 'Book a flight',
      sideEffect: { type: 'write' },
      minimumScope: ['flights:book'],
      responseModes: ['unary'],
      cost: { financial: { currency: 'USD', estimatedAmount: 1000 } },
    },
  },
}

const mockGetManifest = vi.fn()
const mockQueryPermissions = vi.fn()
const mockInvoke = vi.fn()

const mockClient = {
  discover: vi.fn(),
  getManifest: (...args: any[]) => mockGetManifest(...args),
  getCapability(name: string) {
    return normalizedManifest.capabilities[name as keyof typeof normalizedManifest.capabilities] ?? null
  },
  queryPermissions: (...args: any[]) => mockQueryPermissions(...args),
  invoke: (...args: any[]) => mockInvoke(...args),
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory('/studio'),
    routes: [{ path: '/invoke/:capability?', name: 'invoke', component: InvokeView }],
  })
}

async function mountView(initialRoute = '/invoke') {
  const router = makeRouter()
  router.push(initialRoute)
  await router.isReady()

  const wrapper = mount(InvokeView, {
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
  mockGetManifest.mockReset()
  mockQueryPermissions.mockReset()
  mockInvoke.mockReset()
  mockGetManifest.mockResolvedValue(normalizedManifest)
  mockQueryPermissions.mockResolvedValue({ available: [], restricted: [], denied: [] })
})

describe('InvokeView', () => {
  it('loads the manifest through @anip-dev/vue on mount', async () => {
    await mountView()
    expect(mockGetManifest).toHaveBeenCalledTimes(1)
  })

  it('shows capability picker when no capability in route', async () => {
    const { wrapper } = await mountView('/invoke')

    expect(wrapper.find('.picker').exists()).toBe(true)
    const items = wrapper.findAll('.picker-item')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('search_flights')
    expect(items[1].text()).toContain('book_flight')
  })

  it('renders permissions panel for selected capability', async () => {
    const { wrapper } = await mountView('/invoke/search_flights')
    const panel = wrapper.findComponent({ name: 'PermissionsPanel' })

    expect(panel.exists()).toBe(true)
    expect(panel.props('bearer')).toBe('demo-human-key')
    expect(panel.props('capability')).toBe('search_flights')
  })

  it('calls invoke through the ANIP Vue adapter and shows a normalized result', async () => {
    mockInvoke.mockResolvedValue({
      success: true,
      invocationId: 'inv-1',
      result: { flights: [] },
    })

    const { wrapper } = await mountView('/invoke/search_flights')
    const form = wrapper.findComponent({ name: 'InvokeForm' })

    form.vm.$emit('submit', { origin: 'SEA', destination: 'SFO' })
    await flushPromises()

    expect(mockInvoke).toHaveBeenCalledWith(
      'demo-human-key',
      'search_flights',
      { origin: 'SEA', destination: 'SFO' },
      { taskId: undefined, parentInvocationId: undefined },
    )

    const result = wrapper.findComponent({ name: 'InvokeResult' })
    expect(result.props('result')).toEqual({
      success: true,
      invocation_id: 'inv-1',
      task_id: undefined,
      result: { flights: [] },
      failure: undefined,
      budget_context: undefined,
      stream_summary: undefined,
    })
  })

  it('clears the previous result when switching capabilities', async () => {
    mockInvoke.mockResolvedValue({
      success: true,
      invocationId: 'inv-1',
      result: {},
    })

    const { wrapper, router } = await mountView('/invoke/search_flights')
    const form = wrapper.findComponent({ name: 'InvokeForm' })

    form.vm.$emit('submit', { origin: 'SEA' })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'InvokeResult' }).props('result')).not.toBeNull()

    router.push('/invoke/book_flight')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'InvokeResult' }).props('result')).toBeNull()
  })

  it('surfaces transport errors from the adapter', async () => {
    mockInvoke.mockRejectedValue(new Error('Network error'))

    const { wrapper } = await mountView('/invoke/search_flights')
    const form = wrapper.findComponent({ name: 'InvokeForm' })

    form.vm.$emit('submit', { origin: 'SEA' })
    await flushPromises()

    expect(wrapper.text()).toContain('Network error')
    expect(wrapper.findComponent({ name: 'InvokeResult' }).props('result')).toBeNull()
  })
})
