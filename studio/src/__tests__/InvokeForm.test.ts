import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import InvokeForm from '../components/InvokeForm.vue'

const makeDeclaration = (inputs: any[] = []) => ({
  inputs,
  side_effect: { type: 'read' },
})

describe('InvokeForm', () => {
  it('renders input fields from declaration', () => {
    const wrapper = mount(InvokeForm, {
      props: {
        declaration: makeDeclaration([
          { name: 'origin', type: 'string', required: true },
          { name: 'destination', type: 'string', required: true },
        ]),
        capabilityName: 'search_flights',
      },
    })

    const inputs = wrapper.findAll('.field-input')
    expect(inputs).toHaveLength(2)
    expect(wrapper.findAll('.field-name').map(n => n.text())).toEqual(['origin', 'destination'])
  })

  it('shows "no inputs" message when declaration has no inputs', () => {
    const wrapper = mount(InvokeForm, {
      props: {
        declaration: makeDeclaration([]),
        capabilityName: 'health_check',
      },
    })

    expect(wrapper.find('.no-inputs').text()).toBe('This capability takes no inputs.')
  })

  it('shows capability name on the invoke button', () => {
    const wrapper = mount(InvokeForm, {
      props: {
        declaration: makeDeclaration([]),
        capabilityName: 'search_flights',
      },
    })

    expect(wrapper.find('.invoke-btn').text()).toContain('search_flights')
  })

  it('disables invoke button when required fields are empty', () => {
    const wrapper = mount(InvokeForm, {
      props: {
        declaration: makeDeclaration([
          { name: 'origin', type: 'string', required: true },
        ]),
        capabilityName: 'search_flights',
      },
    })

    expect(wrapper.find('.invoke-btn').attributes('disabled')).toBeDefined()
  })

  it('enables invoke button when required fields are filled', async () => {
    const wrapper = mount(InvokeForm, {
      props: {
        declaration: makeDeclaration([
          { name: 'origin', type: 'string', required: true },
        ]),
        capabilityName: 'search_flights',
      },
    })

    await wrapper.find('.field-input').setValue('SEA')
    expect(wrapper.find('.invoke-btn').attributes('disabled')).toBeUndefined()
  })

  it('disables invoke button when disabled prop is true', async () => {
    const wrapper = mount(InvokeForm, {
      props: {
        declaration: makeDeclaration([
          { name: 'origin', type: 'string', required: true },
        ]),
        capabilityName: 'search_flights',
        disabled: true,
      },
    })

    await wrapper.find('.field-input').setValue('SEA')
    expect(wrapper.find('.invoke-btn').attributes('disabled')).toBeDefined()
  })

  it('emits submit with input values when invoked', async () => {
    const wrapper = mount(InvokeForm, {
      props: {
        declaration: makeDeclaration([
          { name: 'origin', type: 'string', required: true },
        ]),
        capabilityName: 'search_flights',
      },
    })

    await wrapper.find('.field-input').setValue('SEA')
    await wrapper.find('.invoke-btn').trigger('click')

    expect(wrapper.emitted('submit')).toBeTruthy()
    expect(wrapper.emitted('submit')![0]).toEqual([{ origin: 'SEA' }])
  })

  it('pre-fills defaults from declaration', () => {
    const wrapper = mount(InvokeForm, {
      props: {
        declaration: makeDeclaration([
          { name: 'origin', type: 'string', required: true, default: 'SEA' },
        ]),
        capabilityName: 'search_flights',
      },
    })

    const input = wrapper.find('.field-input').element as HTMLInputElement
    expect(input.value).toBe('SEA')
  })

  it('pre-fills from initialValues over defaults', () => {
    const wrapper = mount(InvokeForm, {
      props: {
        declaration: makeDeclaration([
          { name: 'origin', type: 'string', required: true, default: 'SEA' },
        ]),
        capabilityName: 'search_flights',
        initialValues: { origin: 'LAX' },
      },
    })

    const input = wrapper.find('.field-input').element as HTMLInputElement
    expect(input.value).toBe('LAX')
  })

  it('marks required fields with asterisk', () => {
    const wrapper = mount(InvokeForm, {
      props: {
        declaration: makeDeclaration([
          { name: 'origin', type: 'string', required: true },
          { name: 'note', type: 'string', required: false },
        ]),
        capabilityName: 'test',
      },
    })

    const requiredMarkers = wrapper.findAll('.field-required')
    expect(requiredMarkers).toHaveLength(1)
  })
})
