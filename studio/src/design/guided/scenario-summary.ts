// studio/src/design/guided/scenario-summary.ts

/**
 * Generate a plain-language scenario summary from the artifact.
 * Returns an array of summary paragraphs.
 */
export function generateScenarioSummary(
  scenario: Record<string, any>,
): string[] {
  const s = scenario?.scenario ?? scenario
  if (!s || typeof s !== 'object') return []
  const parts: string[] = []

  // Category label
  const categoryLabels: Record<string, string> = {
    safety: 'a safety scenario',
    recovery: 'a recovery scenario',
    orchestration: 'an orchestration scenario',
    cross_service: 'a cross-service scenario',
    observability: 'an observability scenario',
  }

  // Identity + category
  if (s.name && s.category) {
    const catLabel = categoryLabels[s.category] ?? `a ${s.category} scenario`
    parts.push(`This is ${catLabel}: ${s.name.replace(/[_\-]/g, ' ')}.`)
  }

  // Narrative
  if (s.narrative) {
    parts.push(s.narrative)
  }

  // Context highlights
  const ctx = s.context ?? {}
  const contextHighlights: string[] = []
  if (ctx.capability) contextHighlights.push(`capability: ${ctx.capability}`)
  if (ctx.side_effect) contextHighlights.push(`side effect: ${ctx.side_effect}`)
  if (ctx.expected_cost !== undefined && ctx.budget_limit !== undefined) {
    contextHighlights.push(`cost: ${ctx.expected_cost} against budget limit of ${ctx.budget_limit}`)
  } else if (ctx.expected_cost !== undefined) {
    contextHighlights.push(`expected cost: ${ctx.expected_cost}`)
  }
  if (ctx.permissions_state) contextHighlights.push(`permissions: ${ctx.permissions_state}`)
  if (ctx.task_id) contextHighlights.push(`task: ${ctx.task_id}`)
  if (contextHighlights.length > 0) {
    parts.push(`Key context: ${contextHighlights.join(', ')}.`)
  }

  // Behavior count
  const behaviors = s.expected_behavior ?? []
  if (behaviors.length > 0) {
    parts.push(`${behaviors.length} expected behavior${behaviors.length > 1 ? 's' : ''} defined.`)
  }

  // Support count
  const support = s.expected_anip_support ?? []
  if (support.length > 0) {
    parts.push(`${support.length} expected ANIP support${support.length > 1 ? 's' : ''} defined.`)
  }

  return parts
}
