// studio/src/__tests__/guided-scenario.test.ts

import { describe, it, expect } from 'vitest'
import {
  titleToSlug,
  slugToTitle,
  readScenarioAnswer,
  applyScenarioAnswer,
  hydrateScenarioAnswers,
} from '../design/guided/scenario-mappings'
import { generateScenarioSummary } from '../design/guided/scenario-summary'
import { evaluateScenarioCompleteness } from '../design/guided/scenario-hints'

describe('slug derivation', () => {
  it('converts title to slug', () => {
    expect(titleToSlug('Book Flight Over Budget')).toBe('book_flight_over_budget')
  })

  it('handles special characters', () => {
    expect(titleToSlug('Deploy & Verify (Multi-Service)')).toBe('deploy_verify_multi-service')
  })

  it('handles empty string', () => {
    expect(titleToSlug('')).toBe('')
  })

  it('converts slug back to title', () => {
    expect(slugToTitle('book_flight_over_budget')).toBe('book flight over budget')
  })

  it('handles hyphens in slug to title', () => {
    expect(slugToTitle('deploy-verify')).toBe('deploy verify')
  })
})

describe('scenario mappings', () => {
  it('reads and writes scenario-title via slug', () => {
    const artifact = {
      scenario: {
        name: 'book_flight_over_budget',
        category: 'safety',
        narrative: '',
        context: {},
        expected_behavior: [],
        expected_anip_support: [],
      },
    }
    const title = readScenarioAnswer('scenario-title', artifact)
    expect(title).toBe('book flight over budget')

    applyScenarioAnswer('scenario-title', 'Delete Production Cluster', artifact)
    expect(artifact.scenario.name).toBe('delete_production_cluster')
  })

  it('reads and writes category', () => {
    const artifact = {
      scenario: {
        name: 'test',
        category: 'safety',
        narrative: '',
        context: {},
        expected_behavior: [],
        expected_anip_support: [],
      },
    }
    expect(readScenarioAnswer('scenario-category', artifact)).toBe('safety')

    applyScenarioAnswer('scenario-category', 'recovery', artifact)
    expect(artifact.scenario.category).toBe('recovery')
  })

  it('reads and writes context side_effect', () => {
    const artifact = {
      scenario: {
        name: 'test',
        category: 'safety',
        narrative: '',
        context: { side_effect: 'irreversible' },
        expected_behavior: [],
        expected_anip_support: [],
      },
    }
    expect(readScenarioAnswer('context-side-effect', artifact)).toBe('irreversible')
  })

  it('parses numeric cost fields from string input', () => {
    const artifact = {
      scenario: {
        name: 'test',
        category: 'safety',
        narrative: '',
        context: {} as Record<string, any>,
        expected_behavior: [],
        expected_anip_support: [],
      },
    }
    applyScenarioAnswer('context-expected-cost', '800', artifact)
    expect(artifact.scenario.context.expected_cost).toBe(800)
  })

  it('removes cost field when set to empty string', () => {
    const artifact = {
      scenario: {
        name: 'test',
        category: 'safety',
        narrative: '',
        context: { expected_cost: 800 } as Record<string, any>,
        expected_behavior: [],
        expected_anip_support: [],
      },
    }
    applyScenarioAnswer('context-expected-cost', '', artifact)
    expect(artifact.scenario.context.expected_cost).toBeUndefined()
  })

  it('reads and writes task_id as direct text field', () => {
    const artifact = {
      scenario: {
        name: 'test',
        category: 'safety',
        narrative: '',
        context: { task_id: 'trip-q2' } as Record<string, any>,
        expected_behavior: [],
        expected_anip_support: [],
      },
    }
    expect(readScenarioAnswer('context-task-id', artifact)).toBe('trip-q2')

    applyScenarioAnswer('context-task-id', 'new-task', artifact)
    expect(artifact.scenario.context.task_id).toBe('new-task')
  })

  it('hydrates full answer set from travel-single shape', () => {
    const artifact = {
      scenario: {
        name: 'book_flight_over_budget',
        category: 'safety',
        narrative: 'An agent is helping a user book travel within a budget.',
        context: {
          capability: 'book_flight',
          side_effect: 'irreversible',
          expected_cost: 800,
          budget_limit: 500,
          permissions_state: 'available',
          task_id: 'trip-planning-q2',
        },
        expected_behavior: ['do_not_execute', 'explain_budget_conflict'],
        expected_anip_support: ['cost_visibility', 'structured_failure'],
      },
    }
    const answers = hydrateScenarioAnswers(artifact)
    expect(answers['scenario-title']).toBe('book flight over budget')
    expect(answers['scenario-category']).toBe('safety')
    expect(answers['context-capability']).toBe('book_flight')
    expect(answers['context-side-effect']).toBe('irreversible')
    expect(answers['context-expected-cost']).toBe('800')
    expect(answers['context-budget-limit']).toBe('500')
    expect(answers['context-permissions']).toBe('available')
    expect(answers['context-task-id']).toBe('trip-planning-q2')
  })

  it('reads empty scenario defaults', () => {
    const artifact = {
      scenario: {
        name: '',
        category: 'safety',
        narrative: '',
        context: {},
        expected_behavior: [],
        expected_anip_support: [],
      },
    }
    const answers = hydrateScenarioAnswers(artifact)
    expect(answers['scenario-title']).toBe('')
    expect(answers['context-expected-cost']).toBe('')
    expect(answers['context-task-id']).toBe('')
  })
})

describe('scenario summary', () => {
  it('generates summary for complete scenario', () => {
    const summary = generateScenarioSummary({
      scenario: {
        name: 'book_flight_over_budget',
        category: 'safety',
        narrative: 'An agent is helping a user book travel within a budget.',
        context: {
          capability: 'book_flight',
          side_effect: 'irreversible',
          expected_cost: 800,
          budget_limit: 500,
        },
        expected_behavior: ['do_not_execute', 'explain_budget_conflict'],
        expected_anip_support: ['cost_visibility', 'structured_failure'],
      },
    })
    expect(summary.length).toBeGreaterThan(0)
    expect(summary.some((s) => s.includes('safety'))).toBe(true)
    expect(summary.some((s) => s.includes('book flight'))).toBe(true)
  })

  it('returns empty for empty input', () => {
    expect(generateScenarioSummary({})).toEqual([])
  })
})

describe('scenario hints', () => {
  it('warns about safety scenario without side_effect', () => {
    const hints = evaluateScenarioCompleteness({
      scenario: {
        name: 'test',
        category: 'safety',
        narrative: 'An action is attempted.',
        context: { capability: 'something' },
        expected_behavior: ['do_not_execute'],
        expected_anip_support: ['structured_failure'],
      },
    })
    expect(hints.some((h) => h.id === 'safety-no-side-effect')).toBe(true)
  })

  it('warns about cross-service without service boundary', () => {
    const hints = evaluateScenarioCompleteness({
      scenario: {
        name: 'test',
        category: 'cross_service',
        narrative: 'A deployment.',
        context: { capability: 'deploy' },
        expected_behavior: ['preserve_lineage'],
        expected_anip_support: ['task_id_support'],
      },
    })
    expect(hints.some((h) => h.id === 'cross-service-no-boundary')).toBe(true)
  })

  it('flags ANIP support that looks like business behavior', () => {
    const hints = evaluateScenarioCompleteness({
      scenario: {
        name: 'test',
        category: 'safety',
        narrative: 'An action.',
        context: { side_effect: 'irreversible' },
        expected_behavior: ['do_not_execute'],
        expected_anip_support: ['block_the_action', 'retry_automatically'],
      },
    })
    expect(hints.some((h) => h.id === 'support-looks-like-behavior')).toBe(true)
  })

  it('warns about no ANIP support when behaviors exist', () => {
    const hints = evaluateScenarioCompleteness({
      scenario: {
        name: 'test',
        category: 'safety',
        narrative: 'An action.',
        context: { side_effect: 'irreversible' },
        expected_behavior: ['do_not_execute'],
        expected_anip_support: [],
      },
    })
    expect(hints.some((h) => h.id === 'no-anip-support')).toBe(true)
  })

  it('does not warn for well-formed safety scenario', () => {
    const hints = evaluateScenarioCompleteness({
      scenario: {
        name: 'test',
        category: 'safety',
        narrative:
          'An agent is helping a user book travel within a budget, but the cost exceeds the limit.',
        context: {
          capability: 'book_flight',
          side_effect: 'irreversible',
          expected_cost: 800,
          budget_limit: 500,
        },
        expected_behavior: ['do_not_execute', 'explain_budget_conflict'],
        expected_anip_support: ['cost_visibility', 'structured_failure'],
      },
    })
    expect(hints.some((h) => h.id === 'safety-no-side-effect')).toBe(false)
    expect(hints.some((h) => h.id === 'no-anip-support')).toBe(false)
  })
})
