// studio/src/design/guided/scenario-hints.ts

import type { CompletenessHint } from './types'

/**
 * Evaluate the current scenario artifact and return advisory hints.
 * These are NOT schema validation errors — they are authoring-quality warnings.
 * Category-aware: different categories trigger different checks.
 */
export function evaluateScenarioCompleteness(
  scenario: Record<string, any>,
): CompletenessHint[] {
  const s = scenario?.scenario ?? scenario
  if (!s || typeof s !== 'object') return []

  const hints: CompletenessHint[] = []
  const ctx = s.context ?? {}
  const category = s.category ?? ''
  const behaviors = s.expected_behavior ?? []
  const support = s.expected_anip_support ?? []
  const narrative = s.narrative ?? ''

  // 1. Safety scenario without side_effect in context
  if (
    category === 'safety' &&
    !ctx.side_effect
  ) {
    hints.push({
      id: 'safety-no-side-effect',
      severity: 'warning',
      message: 'Safety scenario without side effect information in context.',
      explanation:
        'Safety scenarios typically involve irreversible or costly actions. ' +
        'Consider specifying the side_effect in the execution context.',
      relatedFields: ['scenario.category', 'scenario.context.side_effect'],
    })
  }

  // 2. Safety scenario with irreversible side_effect but no cost/budget context
  if (
    category === 'safety' &&
    ctx.side_effect === 'irreversible' &&
    ctx.expected_cost === undefined &&
    ctx.budget_limit === undefined &&
    !narrative.toLowerCase().includes('permission') &&
    !narrative.toLowerCase().includes('authority')
  ) {
    hints.push({
      id: 'safety-irreversible-no-constraint',
      severity: 'info',
      message: 'Irreversible action without a cost/budget or authority constraint in context.',
      explanation:
        'Safety scenarios with irreversible actions usually involve a budget limit, ' +
        'cost constraint, or authority gap. Consider whether additional context is needed.',
      relatedFields: [
        'scenario.context.side_effect',
        'scenario.context.expected_cost',
        'scenario.context.budget_limit',
        'scenario.context.permissions_state',
      ],
    })
  }

  // 3. Cross-service scenario without service boundary evidence in context
  if (
    (category === 'cross_service' || category === 'orchestration') &&
    !Object.keys(ctx).some(k => k.includes('service'))
  ) {
    hints.push({
      id: 'cross-service-no-boundary',
      severity: 'warning',
      message: 'Cross-service or orchestration scenario without service boundary information.',
      explanation:
        'Cross-service scenarios should show service boundaries in context. ' +
        'Consider adding context keys that identify different services.',
      relatedFields: ['scenario.category', 'scenario.context'],
    })
  }

  // 4. Expected behavior is thin relative to narrative
  if (
    narrative.length > 100 &&
    behaviors.length < 2
  ) {
    hints.push({
      id: 'thin-behaviors',
      severity: 'info',
      message: 'Only one expected behavior for a detailed narrative.',
      explanation:
        'A detailed narrative usually implies multiple behavioral expectations. ' +
        'Consider whether additional behaviors should be specified.',
      relatedFields: ['scenario.narrative', 'scenario.expected_behavior'],
    })
  }

  // 5. Expected ANIP support that duplicates business behavior
  const businessTerms = ['execute', 'block', 'retry', 'escalate', 'deny', 'approve']
  const suspiciousSupport = support.filter((entry: string) =>
    businessTerms.some(term => entry.toLowerCase().includes(term))
  )
  if (suspiciousSupport.length > 0) {
    hints.push({
      id: 'support-looks-like-behavior',
      severity: 'info',
      message: 'Some ANIP support entries look like business behaviors rather than interface expectations.',
      explanation:
        'Expected ANIP support should describe what the protocol makes visible or explicit — ' +
        'not what the application should do. Consider moving business logic to expected_behavior.',
      relatedFields: ['scenario.expected_anip_support'],
    })
  }

  // 6. No ANIP support defined
  if (support.length === 0 && behaviors.length > 0) {
    hints.push({
      id: 'no-anip-support',
      severity: 'warning',
      message: 'Expected behaviors defined but no ANIP support specified.',
      explanation:
        'Every scenario should define what the protocol interface should provide. ' +
        'This helps separate what ANIP handles from what requires custom glue.',
      relatedFields: ['scenario.expected_behavior', 'scenario.expected_anip_support'],
    })
  }

  // 7. Narrative is empty or very short
  if (narrative.length > 0 && narrative.length < 20) {
    hints.push({
      id: 'short-narrative',
      severity: 'info',
      message: 'Narrative is very short.',
      explanation:
        'A good narrative explains the situation, what the agent is doing, and why the case matters. ' +
        'Consider expanding the narrative for stakeholder clarity.',
      relatedFields: ['scenario.narrative'],
    })
  }

  return hints
}
