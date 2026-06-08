import { describe, expect, it } from 'vitest'
import type { AgentConsumptionReadinessFinding } from '../design/agent-consumption-readiness'
import {
  mergeSemanticInterpretationRule,
  semanticInterpretationRuleForFinding,
} from '../design/semantic-interpretation-rules'

function finding(overrides: Partial<AgentConsumptionReadinessFinding> = {}): AgentConsumptionReadinessFinding {
  return {
    id: 'gtm.pipeline_summary:derived-target',
    severity: 'warning',
    category: 'derived_target',
    owner: 'agent_app_glue',
    title: 'Who chooses the target group?',
    detail: 'Derived target behavior needs a reviewed owner.',
    recommendation: 'Decide whether the app or service chooses the target group.',
    capability_id: 'gtm.pipeline_summary',
    source: 'capability',
    ...overrides,
  }
}

describe('semantic interpretation rules', () => {
  it('creates reviewed app-language semantics for derived target findings', () => {
    const rule = semanticInterpretationRuleForFinding(
      finding(),
      'App owns target selection before invocation.',
    )

    expect(rule?.id).toBe('gtm-pipeline-summary-derived-target-semantics')
    expect(rule?.owner).toBe('agent_app_glue')
    expect(rule?.agent_action).toBe('clarify')
    expect(rule?.applies_when.any_terms).toContain('top')
    expect(rule?.applies_when.exclude_terms).toContain('export')
    expect(rule?.interpretation).toContain('App owns target selection')
    expect(rule?.interpretation).toContain('Do not pass vague target wording as a literal input')
  })

  it('does not create semantic rules for unrelated readiness categories', () => {
    expect(semanticInterpretationRuleForFinding(finding({
      category: 'unsupported_effect',
      id: 'gtm.pipeline_summary:unsupported-effect',
    }))).toBeNull()
  })

  it('requires a capability anchor before creating a rule', () => {
    expect(semanticInterpretationRuleForFinding(finding({
      capability_id: undefined,
    }))).toBeNull()
  })

  it('merges by stable rule id so assistant suggestions remain reviewable edits', () => {
    const first = semanticInterpretationRuleForFinding(finding(), 'First decision.')
    const second = semanticInterpretationRuleForFinding(finding(), 'Updated decision.')

    const rules = mergeSemanticInterpretationRule(
      mergeSemanticInterpretationRule(undefined, first),
      second,
    )

    expect(rules).toHaveLength(1)
    expect(rules?.[0].interpretation).toContain('Updated decision')
  })
})
