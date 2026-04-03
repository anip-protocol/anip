import { describe, it, expect } from 'vitest'
import {
  readAnswerFromArtifact,
  applyAnswerToArtifact,
  hydrateAnswersFromArtifact,
  applyAllAnswersToArtifact,
  collectRiskLeaves,
} from '../design/guided/mappings'
import { evaluateCompleteness } from '../design/guided/hints'
import { generateRequirementsSummary } from '../design/guided/summary'

describe('guided mappings', () => {
  it('round-trips a boolean answer through the artifact', () => {
    const artifact: Record<string, any> = { scale: { shape_preference: 'production_single_service', high_availability: false } }
    applyAnswerToArtifact('high-availability', true, artifact)
    expect(artifact.scale.high_availability).toBe(true)
    const answer = readAnswerFromArtifact('high-availability', artifact)
    expect(answer).toBe(true)
  })

  it('round-trips a select answer through the artifact', () => {
    const artifact: Record<string, any> = { scale: { shape_preference: 'production_single_service', high_availability: false } }
    applyAnswerToArtifact('scale-shape', 'multi_service_estate', artifact)
    expect(artifact.scale.shape_preference).toBe('multi_service_estate')
    const answer = readAnswerFromArtifact('scale-shape', artifact)
    expect(answer).toBe('multi_service_estate')
  })

  it('removes field when answer is not_specified', () => {
    const artifact: Record<string, any> = { business_constraints: { blocked_failure_posture: 'retry_with_backoff' } }
    applyAnswerToArtifact('blocked-failure-expectation', 'not_specified', artifact)
    expect(artifact.business_constraints.blocked_failure_posture).toBeUndefined()
  })

  it('creates intermediate objects when applying to empty artifact', () => {
    const artifact: Record<string, any> = {}
    applyAnswerToArtifact('has-spending', true, artifact)
    expect(artifact.business_constraints.spending_possible).toBe(true)
  })

  it('hydrate + apply round-trips all answers', () => {
    const artifact: Record<string, any> = {
      system: { name: 'Test', domain: 'test', deployment_intent: 'testing' },
      scale: { shape_preference: 'multi_service_estate', high_availability: true },
      trust: { mode: 'signed', checkpoints: true },
      audit: { durable: true, searchable: true },
      lineage: { invocation_id: true },
      auth: { delegation_tokens: true },
      permissions: { preflight_discovery: true },
      business_constraints: { spending_possible: true },
    }
    const answers = hydrateAnswersFromArtifact(artifact)
    expect(answers['system-name']).toBe('Test')
    expect(answers['high-availability']).toBe(true)
    expect(answers['has-spending']).toBe(true)
    expect(answers['trust-mode']).toBe('signed')
    const fresh: Record<string, any> = {}
    applyAllAnswersToArtifact(answers, fresh)
    expect(fresh.system.name).toBe('Test')
    expect(fresh.scale.high_availability).toBe(true)
    expect(fresh.business_constraints.spending_possible).toBe(true)
    expect(fresh.trust.mode).toBe('signed')
  })

  it('falls back to defaultValue when field is missing', () => {
    const artifact: Record<string, any> = {}
    const answer = readAnswerFromArtifact('high-availability', artifact)
    expect(answer).toBe(false)
  })
})

describe('completeness hints', () => {
  it('warns when spending is enabled without approval', () => {
    const hints = evaluateCompleteness({
      business_constraints: { spending_possible: true },
      scale: { shape_preference: 'production_single_service', high_availability: false },
    })
    expect(hints.some(h => h.id === 'spending-no-approval')).toBe(true)
  })

  it('does not warn when spending has approval', () => {
    const hints = evaluateCompleteness({
      business_constraints: { spending_possible: true, approval_expected_for_high_risk: true },
      scale: { shape_preference: 'production_single_service', high_availability: false },
    })
    expect(hints.some(h => h.id === 'spending-no-approval')).toBe(false)
  })

  it('warns about multi-service without reconstruction', () => {
    const hints = evaluateCompleteness({
      scale: { shape_preference: 'multi_service_estate', high_availability: false },
      audit: {},
      lineage: {},
    })
    expect(hints.some(h => h.id === 'multi-service-no-reconstruction')).toBe(true)
    expect(hints.some(h => h.id === 'multi-service-no-continuity')).toBe(true)
  })

  it('warns about durable without searchable', () => {
    const hints = evaluateCompleteness({
      audit: { durable: true },
      scale: { shape_preference: 'production_single_service', high_availability: false },
    })
    expect(hints.some(h => h.id === 'durable-not-searchable')).toBe(true)
  })

  it('warns about recovery-sensitive without posture', () => {
    const hints = evaluateCompleteness({
      business_constraints: { recovery_sensitive: true },
      scale: { shape_preference: 'production_single_service', high_availability: false },
    })
    expect(hints.some(h => h.id === 'recovery-no-posture')).toBe(true)
  })
})

describe('requirements summary', () => {
  it('produces non-empty output for a complete artifact', () => {
    const summary = generateRequirementsSummary({
      system: { name: 'TestSys', domain: 'devops', deployment_intent: 'production' },
      scale: { shape_preference: 'production_single_service', high_availability: false },
      audit: { durable: true, searchable: true },
      lineage: { invocation_id: true },
      business_constraints: { spending_possible: true },
    })
    expect(summary.length).toBeGreaterThan(0)
    expect(summary[0]).toContain('TestSys')
  })

  it('includes risk information when present', () => {
    const summary = generateRequirementsSummary({
      system: { name: 'X', domain: 'fin', deployment_intent: 'prod' },
      scale: { shape_preference: 'production_single_service', high_availability: false },
      business_constraints: { spending_possible: true, cost_visibility_required: true },
    })
    expect(summary.some(s => s.includes('spend money'))).toBe(true)
    expect(summary.some(s => s.includes('Cost visibility'))).toBe(true)
  })

  it('returns empty array for empty artifact', () => {
    const summary = generateRequirementsSummary({})
    expect(summary).toEqual([])
  })

  it('derives irreversibility from risk_profile when business_constraints absent', () => {
    const summary = generateRequirementsSummary({
      system: { name: 'X', domain: 'travel', deployment_intent: 'prod' },
      scale: { shape_preference: 'production_single_service', high_availability: false },
      risk_profile: {
        capabilities: {
          book_flight: { side_effect: 'irreversible', cost_visibility_required: true, recovery_guidance_required: true },
          search_flights: { side_effect: 'none' },
        },
      },
    })
    expect(summary.some(s => s.includes('irreversible'))).toBe(true)
    expect(summary.some(s => s.includes('Cost visibility'))).toBe(true)
    expect(summary.some(s => s.includes('Recovery guidance'))).toBe(true)
  })

  it('finds high-risk caps in nested multi-service risk_profile', () => {
    const summary = generateRequirementsSummary({
      system: { name: 'X', domain: 'devops', deployment_intent: 'prod' },
      scale: { shape_preference: 'multi_service_estate', high_availability: false },
      risk_profile: {
        execution_service: {
          deploy_service: { side_effect: 'irreversible', high_risk: true, recovery_guidance_required: true },
        },
        verification_service: {
          get_deployment_status: { side_effect: 'none' },
        },
      },
    })
    expect(summary.some(s => s.includes('High-risk capabilities'))).toBe(true)
    expect(summary.some(s => s.includes('deploy_service'))).toBe(true)
  })
})

describe('recursive risk_profile walker', () => {
  it('collects leaves from flat capabilities tree', () => {
    const leaves = collectRiskLeaves({
      capabilities: {
        book_flight: { side_effect: 'irreversible', cost_visibility_required: true },
        search_flights: { side_effect: 'none' },
      },
    })
    expect(leaves).toHaveLength(2)
    expect(leaves.find(l => l.name.includes('book_flight'))?.side_effect).toBe('irreversible')
  })

  it('collects leaves from nested multi-service tree', () => {
    const leaves = collectRiskLeaves({
      execution_service: {
        deploy_service: { side_effect: 'irreversible', high_risk: true, recovery_guidance_required: true },
      },
      verification_service: {
        get_deployment_status: { side_effect: 'none' },
      },
    })
    expect(leaves).toHaveLength(2)
    expect(leaves.some(l => l.high_risk === true)).toBe(true)
    expect(leaves.some(l => l.recovery_guidance_required === true)).toBe(true)
  })

  it('handles empty risk_profile', () => {
    const leaves = collectRiskLeaves({})
    expect(leaves).toHaveLength(0)
  })
})

describe('hydration bridging from risk_profile', () => {
  it('derives has-irreversible from risk_profile when business_constraints absent', () => {
    const artifact: Record<string, any> = {
      system: { name: 'Travel', domain: 'travel', deployment_intent: 'prod' },
      risk_profile: {
        capabilities: {
          book_flight: { side_effect: 'irreversible', cost_visibility_required: true, recovery_guidance_required: true },
          search_flights: { side_effect: 'none' },
        },
      },
    }
    const answers = hydrateAnswersFromArtifact(artifact)
    expect(answers['has-irreversible']).toBe(true)
    expect(answers['cost-visibility']).toBe(true)
    expect(answers['recovery-sensitive']).toBe(true)
  })

  it('bridges from risk_profile even when business_constraints has false default', () => {
    const artifact: Record<string, any> = {
      system: { name: 'X', domain: 'x', deployment_intent: 'x' },
      business_constraints: { irreversible_actions_present: false },
      risk_profile: {
        capabilities: {
          do_something: { side_effect: 'irreversible' },
        },
      },
    }
    const answers = hydrateAnswersFromArtifact(artifact)
    expect(answers['has-irreversible']).toBe(true)
  })

  it('derives high-risk approval from nested multi-service risk_profile', () => {
    const artifact: Record<string, any> = {
      system: { name: 'Deploy', domain: 'devops', deployment_intent: 'prod' },
      risk_profile: {
        execution_service: {
          delete_cluster: { side_effect: 'irreversible', high_risk: true },
        },
      },
    }
    const answers = hydrateAnswersFromArtifact(artifact)
    expect(answers['approval-expectation']).toBe(true)
    expect(answers['has-irreversible']).toBe(true)
  })
})

describe('hints with risk_profile bridging', () => {
  it('does not falsely warn about irreversibility when risk_profile has high_risk', () => {
    const hints = evaluateCompleteness({
      scale: { shape_preference: 'production_single_service', high_availability: false },
      risk_profile: {
        capabilities: {
          book_flight: { side_effect: 'irreversible', high_risk: true },
        },
      },
    })
    expect(hints.some(h => h.id === 'spending-no-approval')).toBe(false)
  })

  it('suppresses high-risk-no-cost-visibility when risk_profile has cost_visibility', () => {
    const hints = evaluateCompleteness({
      scale: { shape_preference: 'production_single_service', high_availability: false },
      risk_profile: {
        capabilities: {
          book_flight: { high_risk: true, cost_visibility_required: true },
        },
      },
    })
    expect(hints.some(h => h.id === 'high-risk-no-cost-visibility')).toBe(false)
  })
})
