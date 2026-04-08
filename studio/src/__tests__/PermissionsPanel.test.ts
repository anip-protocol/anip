import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { AnipClientKey } from '@anip-dev/vue'
import PermissionsPanel from '../components/PermissionsPanel.vue'

const mockQueryPermissions = vi.fn()

const mockClient = {
  queryPermissions: (...args: any[]) => mockQueryPermissions(...args),
}

function mountPanel(props: { bearer: string; capability: string | null }) {
  return mount(PermissionsPanel, {
    props,
    global: {
      provide: {
        [AnipClientKey as symbol]: mockClient,
      },
    },
  })
}

beforeEach(() => {
  mockQueryPermissions.mockReset()
})

describe('PermissionsPanel', () => {
  it('shows neutral state when no bearer token', () => {
    const wrapper = mountPanel({ bearer: '', capability: 'search_flights' })
    expect(wrapper.text()).toContain('Enter a bearer token to inspect permissions')
  })

  it('shows neutral state when no capability', () => {
    const wrapper = mountPanel({ bearer: 'token', capability: null })
    expect(wrapper.text()).toContain('Select a capability to inspect permissions')
  })

  it('shows available state when capability is in available bucket', async () => {
    mockQueryPermissions.mockResolvedValue({
      available: [{ capability: 'search_flights', scopeMatch: 'flights:search' }],
      restricted: [],
      denied: [],
    })

    const wrapper = mountPanel({ bearer: 'token', capability: 'search_flights' })
    await flushPromises()

    expect(wrapper.text()).toContain('Available')
    expect(wrapper.text()).toContain('flights:search')
    expect(wrapper.find('.available-dot').exists()).toBe(true)
  })

  it('shows restricted state with normalized detail', async () => {
    mockQueryPermissions.mockResolvedValue({
      available: [],
      restricted: [{
        capability: 'book_flight',
        reasonType: 'insufficient_scope',
        reason: 'missing scope',
        grantableBy: 'human',
        resolutionHint: 'Request a stronger token',
      }],
      denied: [],
    })

    const wrapper = mountPanel({ bearer: 'token', capability: 'book_flight' })
    await flushPromises()

    expect(wrapper.text()).toContain('Restricted')
    expect(wrapper.text()).toContain('missing scope')
    expect(wrapper.text()).toContain('Grantable by: human')
    expect(wrapper.text()).toContain('Request a stronger token')
    expect(wrapper.find('.restricted-dot').exists()).toBe(true)
  })

  it('shows denied state with reason', async () => {
    mockQueryPermissions.mockResolvedValue({
      available: [],
      restricted: [],
      denied: [{ capability: 'admin_reset', reasonType: 'non_delegable', reason: 'requires admin principal' }],
    })

    const wrapper = mountPanel({ bearer: 'token', capability: 'admin_reset' })
    await flushPromises()

    expect(wrapper.text()).toContain('Denied')
    expect(wrapper.text()).toContain('requires admin principal')
    expect(wrapper.find('.denied-dot').exists()).toBe(true)
  })

  it('shows error state on query failure', async () => {
    mockQueryPermissions.mockRejectedValue(new Error('Permissions query failed'))

    const wrapper = mountPanel({ bearer: 'bad-token', capability: 'search_flights' })
    await flushPromises()

    expect(wrapper.text()).toContain('Unable to check permissions')
    expect(wrapper.text()).toContain('Permissions query failed')
    expect(wrapper.find('.error-dot').exists()).toBe(true)
  })
})
