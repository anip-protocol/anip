import type { AgentConsumptionReadinessFinding } from './agent-consumption-readiness'
import type { AgentConsumabilityBusinessLanguageRule, AgentConsumabilitySelectionHint } from './agent-consumability'

export function semanticInterpretationRuleForFinding(
  finding: AgentConsumptionReadinessFinding,
  note?: string,
): AgentConsumabilityBusinessLanguageRule | null {
  if (!finding.capability_id) return null
  if (finding.category !== 'derived_target') return null
  const reviewedNote = note?.trim()
  const baseInterpretation = 'Do not pass vague target wording as a literal input. The consuming app should select a reviewed bounded target group or ask for clarification before invoking the capability.'
  return {
    id: stableSemanticRuleId(finding.capability_id, 'derived-target-semantics'),
    meaning: 'User asks the app or service to choose a target group from business wording such as top, ranked, selected, recommended, or at-risk records.',
    owner: 'agent_app_glue',
    applies_when: {
      any_terms: ['top', 'ranked', 'selected', 'recommended', 'at-risk', 'highest priority'],
      exclude_terms: ['raw', 'export', 'download', 'send', 'email', 'message', 'draft', 'write', 'generate'],
    },
    interpretation: reviewedNote ? `${reviewedNote} ${baseInterpretation}` : baseInterpretation,
    agent_action: 'clarify',
  }
}

export function mergeSemanticInterpretationRule(
  existing: AgentConsumabilityBusinessLanguageRule[] | undefined,
  next: AgentConsumabilityBusinessLanguageRule | null,
): AgentConsumabilityBusinessLanguageRule[] | undefined {
  if (!next) return existing
  const current = existing ?? []
  const withoutDuplicate = current.filter((rule) => rule.id !== next.id)
  return [...withoutDuplicate, next]
}

export function selectionHintForSemanticRule(
  capabilityId: string | undefined,
  rule: AgentConsumabilityBusinessLanguageRule | null,
): AgentConsumabilitySelectionHint | null {
  if (!capabilityId || !rule?.applies_when) return null
  const hint: AgentConsumabilitySelectionHint = {
    capability: capabilityId,
  }
  if (rule.applies_when.all_terms?.length) hint.all_terms = [...rule.applies_when.all_terms]
  if (rule.applies_when.any_terms?.length) hint.any_terms = [...rule.applies_when.any_terms]
  if (rule.applies_when.exclude_terms?.length) hint.exclude_terms = [...rule.applies_when.exclude_terms]
  return hint.all_terms || hint.any_terms ? hint : null
}

export function mergeSelectionHint(
  existing: AgentConsumabilitySelectionHint[] | undefined,
  next: AgentConsumabilitySelectionHint | null,
): AgentConsumabilitySelectionHint[] | undefined {
  if (!next) return existing
  const current = existing ?? []
  const key = selectionHintKey(next)
  const withoutDuplicate = current.filter((hint) => selectionHintKey(hint) !== key)
  return [...withoutDuplicate, next]
}

function stableSemanticRuleId(capabilityId: string, suffix: string): string {
  return `${capabilityId}-${suffix}`
    .replace(/[^a-z0-9-]+/gi, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
}

function selectionHintKey(hint: AgentConsumabilitySelectionHint): string {
  return JSON.stringify({
    capability: hint.capability,
    all_terms: [...(hint.all_terms ?? [])].sort(),
    any_terms: [...(hint.any_terms ?? [])].sort(),
    exclude_terms: [...(hint.exclude_terms ?? [])].sort(),
  })
}
