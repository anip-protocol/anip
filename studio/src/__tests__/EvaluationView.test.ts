import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { reactive } from 'vue'

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockEvaluation = {
  evaluation: {
    scenario_name: 'book_flight_over_budget',
    result: 'PARTIAL' as const,
    handled_by_anip: ['permission discovery', 'task identity'],
    glue_you_will_still_write: ['you will still write budget-enforcement logic here'],
    glue_category: ['safety', 'orchestration'],
    why: ['the design improves the decision surface substantially before action'],
    what_would_improve: ['represent budget as enforceable authority'],
    confidence: 'high',
  },
}

const mockLiveEvaluation = {
  evaluation: {
    scenario_name: 'book_flight_over_budget',
    result: 'HANDLED' as const,
    handled_by_anip: ['permission discovery', 'task identity', 'budget enforcement'],
    glue_you_will_still_write: [] as string[],
    glue_category: [] as string[],
    why: ['live validation resolved all surfaces'],
    what_would_improve: [] as string[],
    confidence: 'high',
  },
}

const mockPack = {
  meta: {
    id: 'travel-single',
    name: 'travel-service',
    domain: 'travel',
    category: 'safety',
    narrative: 'An agent books a flight that exceeds the budget.',
    result: 'PARTIAL',
    isMultiService: false,
  },
  requirements: { system: { name: 'travel-service', domain: 'travel', deployment_intent: 'single' } },
  proposal: { proposal: { recommended_shape: 'production_single_service', rationale: [], required_components: [], anti_pattern_warnings: [], expected_glue_reduction: {} } },
  scenario: { scenario: { name: 'book_flight_over_budget', category: 'safety', narrative: '', context: {}, expected_behavior: [], expected_anip_support: [] } },
  evaluation: mockEvaluation,
}

// ---------------------------------------------------------------------------
// Mock the design store -- must not reference outer variables in factory
// ---------------------------------------------------------------------------

const mockRunLiveValidation = vi.fn()

vi.mock('../design/store', () => {
  const { reactive: r } = require('vue')
  const state = r({
    packs: [] as any[],
    activePackId: null as string | null,
    liveEvaluation: null as any,
    validating: false,
    validationError: null as string | null,
    apiAvailable: false,
  })
  return {
    designStore: state,
    setActivePack: (id: string) => { state.activePackId = id },
    runLiveValidation: () => {},
  }
})

// Import the mocked store so tests can manipulate it
import { designStore } from '../design/store'

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function makeRouter() {
  return createRouter({
    history: createMemoryHistory('/studio'),
    routes: [
      { path: '/design/evaluation/:pack', name: 'evaluation', component: () => import('../views/EvaluationView.vue') },
    ],
  })
}

async function mountView(packId = 'travel-single') {
  const router = makeRouter()
  router.push(`/design/evaluation/${packId}`)
  await router.isReady()

  const wrapper = mount({
    template: '<router-view />',
  }, {
    global: { plugins: [router] },
  })
  await flushPromises()
  return { wrapper, router }
}

// ---------------------------------------------------------------------------
// Reset state before each test
// ---------------------------------------------------------------------------

beforeEach(() => {
  designStore.packs = [JSON.parse(JSON.stringify(mockPack))]
  designStore.activePackId = null
  designStore.liveEvaluation = null
  designStore.validating = false
  designStore.validationError = null
  designStore.apiAvailable = false
  mockRunLiveValidation.mockReset()
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('EvaluationView', () => {
  describe('Run Validation button visibility', () => {
    it('hides "Run Validation" button when apiAvailable is false', async () => {
      designStore.apiAvailable = false
      const { wrapper } = await mountView()

      expect(wrapper.find('.run-btn').exists()).toBe(false)
    })

    it('shows "Run Validation" button when apiAvailable is true', async () => {
      designStore.apiAvailable = true
      const { wrapper } = await mountView()

      expect(wrapper.find('.run-btn').exists()).toBe(true)
      expect(wrapper.find('.run-btn').text()).toBe('Run Validation')
    })
  })

  describe('source badges', () => {
    it('displays "Pre-computed" badge when showing static evaluation', async () => {
      designStore.liveEvaluation = null
      const { wrapper } = await mountView()

      const badge = wrapper.find('.source-badge')
      expect(badge.exists()).toBe(true)
      expect(badge.text()).toBe('Pre-computed')
      expect(badge.classes()).toContain('precomputed')
    })

    it('displays "Live result" badge when liveEvaluation exists in store', async () => {
      designStore.liveEvaluation = JSON.parse(JSON.stringify(mockLiveEvaluation))
      const { wrapper } = await mountView()

      const badge = wrapper.find('.source-badge.live')
      expect(badge.exists()).toBe(true)
      expect(badge.text()).toBe('Live result')
    })
  })

  describe('reset to pre-computed', () => {
    it('shows "Reset to pre-computed" button when live evaluation is present', async () => {
      designStore.liveEvaluation = JSON.parse(JSON.stringify(mockLiveEvaluation))
      const { wrapper } = await mountView()

      const resetBtn = wrapper.find('.reset-btn')
      expect(resetBtn.exists()).toBe(true)
      expect(resetBtn.text()).toBe('Reset to pre-computed')
    })

    it('clears liveEvaluation from store when "Reset to pre-computed" is clicked', async () => {
      designStore.liveEvaluation = JSON.parse(JSON.stringify(mockLiveEvaluation))
      const { wrapper } = await mountView()

      expect(designStore.liveEvaluation).not.toBeNull()

      await wrapper.find('.reset-btn').trigger('click')
      await flushPromises()

      expect(designStore.liveEvaluation).toBeNull()
      expect(designStore.validationError).toBeNull()
    })

    it('hides "Reset to pre-computed" button when showing static evaluation', async () => {
      designStore.liveEvaluation = null
      const { wrapper } = await mountView()

      expect(wrapper.find('.reset-btn').exists()).toBe(false)
    })
  })

  describe('evaluation content rendering', () => {
    it('renders pre-computed evaluation data by default', async () => {
      const { wrapper } = await mountView()

      expect(wrapper.text()).toContain('PARTIAL')
      expect(wrapper.text()).toContain('permission discovery')
      expect(wrapper.text()).toContain('budget-enforcement')
    })

    it('renders live evaluation data when present', async () => {
      designStore.liveEvaluation = JSON.parse(JSON.stringify(mockLiveEvaluation))
      const { wrapper } = await mountView()

      expect(wrapper.text()).toContain('HANDLED')
      expect(wrapper.text()).toContain('budget enforcement')
      expect(wrapper.text()).toContain('live validation resolved')
    })
  })
})
