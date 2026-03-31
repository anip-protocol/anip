import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import InvokeResult from '../components/InvokeResult.vue'

describe('InvokeResult', () => {
  it('renders nothing when result is null', () => {
    const wrapper = mount(InvokeResult, {
      props: { result: null },
    })

    expect(wrapper.find('.invoke-result').exists()).toBe(false)
  })

  it('renders success with invocation_id', () => {
    const wrapper = mount(InvokeResult, {
      props: {
        result: {
          success: true,
          invocation_id: 'inv-123',
          result: { flights: [] },
        },
      },
    })

    expect(wrapper.find('.invoke-result').exists()).toBe(true)
    expect(wrapper.text()).toContain('Success')
    expect(wrapper.find('.invocation-id').text()).toBe('inv-123')
  })

  it('renders client_reference_id when present on success', () => {
    const wrapper = mount(InvokeResult, {
      props: {
        result: {
          success: true,
          invocation_id: 'inv-1',
          client_reference_id: 'ref-abc',
          result: {},
        },
      },
    })

    expect(wrapper.text()).toContain('client_reference_id')
    expect(wrapper.text()).toContain('ref-abc')
  })

  it('renders cost_actual when present on success', () => {
    const wrapper = mount(InvokeResult, {
      props: {
        result: {
          success: true,
          invocation_id: 'inv-1',
          cost_actual: { currency: 'USD', amount: 12.50 },
          result: {},
        },
      },
    })

    expect(wrapper.text()).toContain('cost_actual')
    expect(wrapper.text()).toContain('USD')
    expect(wrapper.text()).toContain('12.5')
  })

  it('renders structured failure with type and detail', () => {
    const wrapper = mount(InvokeResult, {
      props: {
        result: {
          success: false,
          invocation_id: 'inv-2',
          failure: {
            type: 'budget_exceeded',
            detail: 'Over budget by $287',
            retry: false,
            resolution: { action: 'request_increase' },
          },
        },
      },
    })

    expect(wrapper.text()).toContain('Failed')
    expect(wrapper.text()).toContain('budget_exceeded')
    expect(wrapper.text()).toContain('Over budget by $287')
  })

  it('renders resolution callout', () => {
    const wrapper = mount(InvokeResult, {
      props: {
        result: {
          success: false,
          invocation_id: 'inv-3',
          failure: {
            type: 'scope_insufficient',
            detail: 'Missing scope',
            retry: false,
            resolution: {
              action: 'request_broader_scope',
              requires: 'flights:book',
              grantable_by: 'human',
              estimated_availability: 'immediate',
            },
          },
        },
      },
    })

    expect(wrapper.find('.resolution-callout').exists()).toBe(true)
    expect(wrapper.text()).toContain('request_broader_scope')
    expect(wrapper.text()).toContain('flights:book')
    expect(wrapper.text()).toContain('human')
    expect(wrapper.text()).toContain('immediate')
  })

  it('shows retryable status', () => {
    const wrapper = mount(InvokeResult, {
      props: {
        result: {
          success: false,
          invocation_id: 'inv-4',
          failure: { type: 'rate_limited', detail: 'Too many requests', retry: true, resolution: { action: 'wait' } },
        },
      },
    })

    expect(wrapper.text()).toContain('Retryable')
    expect(wrapper.text()).toContain('yes')
  })

  it('shows non-retryable status', () => {
    const wrapper = mount(InvokeResult, {
      props: {
        result: {
          success: false,
          invocation_id: 'inv-5',
          failure: { type: 'denied', detail: 'Denied', retry: false, resolution: { action: 'contact admin' } },
        },
      },
    })

    expect(wrapper.text()).toContain('Retryable')
    expect(wrapper.text()).toContain('no')
  })

  it('renders invocation_id on failure', () => {
    const wrapper = mount(InvokeResult, {
      props: {
        result: {
          success: false,
          invocation_id: 'inv-fail-1',
          failure: { type: 'error', detail: 'Oops', retry: false, resolution: { action: 'retry' } },
        },
      },
    })

    expect(wrapper.find('.invocation-id').text()).toBe('inv-fail-1')
  })
})
