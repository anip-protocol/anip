import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import InvokeView from '../views/InvokeView.vue'

// Mock store
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

const mockManifest = {
  capabilities: {
    search_flights: {
      description: 'Search flights',
      side_effect: { type: 'read' },
      minimum_scope: ['flights:search'],
      inputs: [
        { name: 'origin', type: 'string', required: true },
        { name: 'destination', type: 'string', required: true },
      ],
    },
    book_flight: {
      description: 'Book a flight',
      side_effect: { type: 'write' },
      minimum_scope: ['flights:book'],
      cost: { financial: { currency: 'USD', range_min: 100, range_max: 1000 } },
      inputs: [
        { name: 'flight_number', type: 'string', required: true },
      ],
    },
  },
}

const mockFetchManifest = vi.fn()
const mockInvokeCapability = vi.fn()
const mockFetchPermissions = vi.fn()

vi.mock('../api', () => ({
  fetchManifest: (...args: any[]) => mockFetchManifest(...args),
  invokeCapability: (...args: any[]) => mockInvokeCapability(...args),
  fetchPermissions: (...args: any[]) => mockFetchPermissions(...args),
}))

function makeRouter(_initialRoute = '/invoke') {
  return createRouter({
    history: createMemoryHistory('/studio'),
    routes: [
      { path: '/invoke/:capability?', name: 'invoke', component: InvokeView },
    ],
  })
}

async function mountView(initialRoute = '/invoke') {
  const router = makeRouter()
  router.push(initialRoute)
  await router.isReady()

  const wrapper = mount(InvokeView, {
    global: { plugins: [router] },
  })
  await flushPromises()
  return { wrapper, router }
}

beforeEach(() => {
  mockFetchManifest.mockReset()
  mockInvokeCapability.mockReset()
  mockFetchPermissions.mockReset()
  mockFetchManifest.mockResolvedValue({ manifest: mockManifest, signature: 'sig' })
  mockFetchPermissions.mockResolvedValue({ available: [], restricted: [], denied: [] })
})

describe('InvokeView', () => {
  describe('manifest loading', () => {
    it('fetches manifest on mount', async () => {
      await mountView()
      expect(mockFetchManifest).toHaveBeenCalledWith('http://localhost:9100')
    })

    it('shows error state when manifest fetch fails', async () => {
      mockFetchManifest.mockRejectedValue(new Error('Manifest: 500'))
      const { wrapper } = await mountView()

      expect(wrapper.text()).toContain('Manifest: 500')
      expect(wrapper.find('.retry-btn').exists()).toBe(true)
    })

    it('retries manifest fetch on retry button click', async () => {
      mockFetchManifest.mockRejectedValueOnce(new Error('Manifest: 500'))
      const { wrapper } = await mountView()

      mockFetchManifest.mockResolvedValue({ manifest: mockManifest, signature: 'sig' })
      await wrapper.find('.retry-btn').trigger('click')
      await flushPromises()

      expect(mockFetchManifest).toHaveBeenCalledTimes(2)
    })
  })

  describe('capability picker', () => {
    it('shows capability picker when no capability in route', async () => {
      const { wrapper } = await mountView('/invoke')

      expect(wrapper.find('.picker').exists()).toBe(true)
      const items = wrapper.findAll('.picker-item')
      expect(items).toHaveLength(2)
      expect(items[0].text()).toContain('search_flights')
      expect(items[1].text()).toContain('book_flight')
    })

    it('navigates to capability on picker item click', async () => {
      const { wrapper, router } = await mountView('/invoke')

      await wrapper.findAll('.picker-item')[0].trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/invoke/search_flights')
    })
  })

  describe('route param sync', () => {
    it('auto-selects capability from route param', async () => {
      const { wrapper } = await mountView('/invoke/search_flights')

      expect(wrapper.find('.declaration-bar').exists()).toBe(true)
      expect(wrapper.find('.cap-name').text()).toBe('search_flights')
    })

    it('clears selection when navigating back to /invoke', async () => {
      const { wrapper, router } = await mountView('/invoke/search_flights')

      expect(wrapper.find('.declaration-bar').exists()).toBe(true)

      router.push('/invoke')
      await flushPromises()

      expect(wrapper.find('.picker').exists()).toBe(true)
      expect(wrapper.find('.declaration-bar').exists()).toBe(false)
    })
  })

  describe('invalid capability', () => {
    it('shows error for unknown capability deep link', async () => {
      const { wrapper } = await mountView('/invoke/nonexistent_cap')

      expect(wrapper.text()).toContain('Unknown capability')
      expect(wrapper.text()).toContain('nonexistent_cap')
      expect(wrapper.find('.retry-btn').text()).toContain('Back to picker')
    })

    it('navigates to picker when clicking back from invalid capability', async () => {
      const { wrapper, router } = await mountView('/invoke/nonexistent_cap')

      await wrapper.find('.retry-btn').trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/invoke')
    })
  })

  describe('declaration bar', () => {
    it('shows side-effect badge', async () => {
      const { wrapper } = await mountView('/invoke/search_flights')

      expect(wrapper.text()).toContain('Read')
    })

    it('shows scope chips', async () => {
      const { wrapper } = await mountView('/invoke/search_flights')

      expect(wrapper.find('.scope-chip').text()).toBe('flights:search')
    })

    it('shows cost summary when present', async () => {
      const { wrapper } = await mountView('/invoke/book_flight')

      expect(wrapper.find('.cost-summary').text()).toContain('USD')
    })

    it('shows back button that returns to picker', async () => {
      const { wrapper, router } = await mountView('/invoke/search_flights')

      await wrapper.find('.back-btn').trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/invoke')
    })
  })

  describe('child component wiring', () => {
    it('renders BearerInput', async () => {
      const { wrapper } = await mountView('/invoke/search_flights')
      expect(wrapper.findComponent({ name: 'BearerInput' }).exists()).toBe(true)
    })

    it('renders PermissionsPanel with correct props', async () => {
      const { wrapper } = await mountView('/invoke/search_flights')
      const panel = wrapper.findComponent({ name: 'PermissionsPanel' })
      expect(panel.exists()).toBe(true)
      expect(panel.props('bearer')).toBe('demo-human-key')
      expect(panel.props('capability')).toBe('search_flights')
    })

    it('renders InvokeForm with correct props', async () => {
      const { wrapper } = await mountView('/invoke/search_flights')
      const form = wrapper.findComponent({ name: 'InvokeForm' })
      expect(form.exists()).toBe(true)
      expect(form.props('capabilityName')).toBe('search_flights')
      expect(form.props('disabled')).toBe(false)
    })

    it('renders InvokeResult (initially null)', async () => {
      const { wrapper } = await mountView('/invoke/search_flights')
      const result = wrapper.findComponent({ name: 'InvokeResult' })
      expect(result.exists()).toBe(true)
      expect(result.props('result')).toBeNull()
    })
  })

  describe('invocation', () => {
    it('calls invokeCapability and shows result on form submit', async () => {
      mockInvokeCapability.mockResolvedValue({
        success: true,
        invocation_id: 'inv-1',
        result: { flights: [] },
      })

      const { wrapper } = await mountView('/invoke/search_flights')
      const form = wrapper.findComponent({ name: 'InvokeForm' })

      form.vm.$emit('submit', { origin: 'SEA', destination: 'SFO' })
      await flushPromises()

      expect(mockInvokeCapability).toHaveBeenCalledWith(
        'http://localhost:9100', 'demo-human-key', 'search_flights',
        { origin: 'SEA', destination: 'SFO' }, {},
      )

      const result = wrapper.findComponent({ name: 'InvokeResult' })
      expect(result.props('result')).toEqual({
        success: true,
        invocation_id: 'inv-1',
        result: { flights: [] },
      })
    })

    it('wraps transport errors as failure-like objects', async () => {
      mockInvokeCapability.mockRejectedValue(new Error('Network error'))

      const { wrapper } = await mountView('/invoke/search_flights')
      const form = wrapper.findComponent({ name: 'InvokeForm' })

      form.vm.$emit('submit', { origin: 'SEA' })
      await flushPromises()

      const result = wrapper.findComponent({ name: 'InvokeResult' })
      const resultData = result.props('result')
      expect(resultData.success).toBe(false)
      expect(resultData.failure.type).toBe('transport_error')
      expect(resultData.failure.detail).toBe('Network error')
    })

    it('clears result when switching capabilities', async () => {
      mockInvokeCapability.mockResolvedValue({
        success: true, invocation_id: 'inv-1', result: {},
      })

      const { wrapper, router } = await mountView('/invoke/search_flights')
      const form = wrapper.findComponent({ name: 'InvokeForm' })

      form.vm.$emit('submit', { origin: 'SEA' })
      await flushPromises()

      // Result should be populated
      expect(wrapper.findComponent({ name: 'InvokeResult' }).props('result')).not.toBeNull()

      // Switch capability
      router.push('/invoke/book_flight')
      await flushPromises()

      // Result should be cleared
      expect(wrapper.findComponent({ name: 'InvokeResult' }).props('result')).toBeNull()
    })
  })
})
