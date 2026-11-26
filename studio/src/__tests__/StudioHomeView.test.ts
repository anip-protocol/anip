import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import StudioHomeView from '../views/StudioHomeView.vue'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

afterEach(() => {
  vi.unstubAllEnvs()
  push.mockReset()
})

function cardTitles(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('.card-title').map((title) => title.text())
}

describe('StudioHomeView', () => {
  it('leads with Inspect and labels Design as experimental', async () => {
    vi.stubEnv('VITE_INSPECT_ONLY', '')
    const wrapper = mount(StudioHomeView)

    expect(cardTitles(wrapper)).toEqual(['Invoke & Inspect', 'Design Experimental'])
    expect(wrapper.find('.card-tag').text()).toBe('Experimental')

    await wrapper.find('.card-btn-design').trigger('click')
    expect(push).toHaveBeenCalledWith('/design')
  })

  it('offers only Inspect in an Inspect-only build, which has no Design routes', async () => {
    vi.stubEnv('VITE_INSPECT_ONLY', 'true')
    const wrapper = mount(StudioHomeView)

    expect(cardTitles(wrapper)).toEqual(['Invoke & Inspect'])
    expect(wrapper.text()).not.toContain('Design')
    expect(wrapper.text()).not.toContain('design')

    await wrapper.find('.card-btn').trigger('click')
    expect(push).toHaveBeenCalledWith('/inspect/discovery')
  })
})
