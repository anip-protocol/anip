import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PermissionsPanel from '../components/PermissionsPanel.vue'

// Mock the store and api modules
vi.mock('../store', () => ({
  store: { baseUrl: 'http://localhost:9100', bearer: '', connected: true },
}))

const mockFetchPermissions = vi.fn()
vi.mock('../api', () => ({
  fetchPermissions: (...args: any[]) => mockFetchPermissions(...args),
}))

beforeEach(() => {
  mockFetchPermissions.mockReset()
})

describe('PermissionsPanel', () => {
  it('shows neutral state when no bearer token', () => {
    const wrapper = mount(PermissionsPanel, {
      props: { bearer: '', capability: 'search_flights' },
    })

    expect(wrapper.text()).toContain('Enter a bearer token to inspect permissions')
  })

  it('shows neutral state when no capability', () => {
    const wrapper = mount(PermissionsPanel, {
      props: { bearer: 'token', capability: null },
    })

    expect(wrapper.text()).toContain('Select a capability to inspect permissions')
  })

  it('shows available state when capability is in available bucket', async () => {
    mockFetchPermissions.mockResolvedValue({
      available: [{ capability: 'search_flights', scope_match: 'flights:search' }],
      restricted: [],
      denied: [],
    })

    const wrapper = mount(PermissionsPanel, {
      props: { bearer: 'token', capability: 'search_flights' },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Available')
    expect(wrapper.text()).toContain('flights:search')
    expect(wrapper.find('.available-dot').exists()).toBe(true)
  })

  it('shows restricted state with reason', async () => {
    mockFetchPermissions.mockResolvedValue({
      available: [],
      restricted: [{ capability: 'book_flight', reason: 'missing scope', grantable_by: 'human' }],
      denied: [],
    })

    const wrapper = mount(PermissionsPanel, {
      props: { bearer: 'token', capability: 'book_flight' },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Restricted')
    expect(wrapper.text()).toContain('missing scope')
    expect(wrapper.text()).toContain('Grantable by: human')
    expect(wrapper.find('.restricted-dot').exists()).toBe(true)
  })

  it('shows denied state with reason', async () => {
    mockFetchPermissions.mockResolvedValue({
      available: [],
      restricted: [],
      denied: [{ capability: 'admin_reset', reason: 'requires admin principal' }],
    })

    const wrapper = mount(PermissionsPanel, {
      props: { bearer: 'token', capability: 'admin_reset' },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Denied')
    expect(wrapper.text()).toContain('requires admin principal')
    expect(wrapper.find('.denied-dot').exists()).toBe(true)
  })

  it('shows error state on fetch failure', async () => {
    mockFetchPermissions.mockRejectedValue(new Error('Permissions: 401'))

    const wrapper = mount(PermissionsPanel, {
      props: { bearer: 'bad-token', capability: 'search_flights' },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Unable to check permissions')
    expect(wrapper.text()).toContain('Permissions: 401')
    expect(wrapper.find('.error-dot').exists()).toBe(true)
  })

  it('shows advisory note', () => {
    const wrapper = mount(PermissionsPanel, {
      props: { bearer: '', capability: null },
    })

    expect(wrapper.text()).toContain('Advisory')
    expect(wrapper.text()).toContain('invocation result is authoritative')
  })

  it('treats capability not in any bucket as denied', async () => {
    mockFetchPermissions.mockResolvedValue({
      available: [],
      restricted: [],
      denied: [],
    })

    const wrapper = mount(PermissionsPanel, {
      props: { bearer: 'token', capability: 'unknown_cap' },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Denied')
  })

  it('shows refresh button after result', async () => {
    mockFetchPermissions.mockResolvedValue({
      available: [{ capability: 'search_flights', scope_match: 'flights:search' }],
      restricted: [],
      denied: [],
    })

    const wrapper = mount(PermissionsPanel, {
      props: { bearer: 'token', capability: 'search_flights' },
    })

    await flushPromises()

    expect(wrapper.find('.refresh-btn').exists()).toBe(true)
  })
})
