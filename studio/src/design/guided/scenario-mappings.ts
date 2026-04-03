// studio/src/design/guided/scenario-mappings.ts

import { SCENARIO_GUIDED_SECTIONS } from './scenario-questions'
import { getNestedValue, setNestedValue } from './mappings'

/**
 * Derive a slug from a human-friendly title.
 * "Book Flight Over Budget" → "book_flight_over_budget"
 */
export function titleToSlug(title: string): string {
  return title
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_\-]/g, '')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
}

/**
 * Derive a human-friendly title from a slug.
 * "book_flight_over_budget" → "book flight over budget"
 */
export function slugToTitle(slug: string): string {
  return slug.replace(/[_\-]/g, ' ')
}

/**
 * Read the answer for a scenario question from the artifact.
 * Special handling:
 * - 'scenario-title': reads scenario.name and converts slug → title
 * - 'context-expected-cost' / 'context-budget-limit': read as string for text input
 */
export function readScenarioAnswer(
  questionId: string,
  artifact: Record<string, any>,
): any {
  const question = SCENARIO_GUIDED_SECTIONS.flatMap((s) => s.questions).find(
    (q) => q.id === questionId,
  )
  if (!question) return undefined

  // Special: title ↔ slug
  if (questionId === 'scenario-title') {
    const slug = getNestedValue(artifact, 'scenario.name')
    return slug ? slugToTitle(slug) : ''
  }

  // Special: numeric context fields read as string for text input
  if (questionId === 'context-expected-cost' || questionId === 'context-budget-limit') {
    const mapping = question.fieldMappings[0]
    if (!mapping) return question.defaultValue
    const value = getNestedValue(artifact, mapping.path)
    return value !== undefined ? String(value) : ''
  }

  // Standard read via primary mapping
  const mapping = question.fieldMappings[0]
  if (!mapping) return question.defaultValue
  const value = getNestedValue(artifact, mapping.path)
  return value !== undefined ? value : question.defaultValue
}

/**
 * Apply a scenario answer to the artifact.
 * Special handling:
 * - 'scenario-title': converts title → slug and writes to scenario.name
 * - 'context-expected-cost' / 'context-budget-limit': parse as number
 * - empty string / 'not_specified': removes the field
 */
export function applyScenarioAnswer(
  questionId: string,
  answer: any,
  artifact: Record<string, any>,
): void {
  const question = SCENARIO_GUIDED_SECTIONS.flatMap((s) => s.questions).find(
    (q) => q.id === questionId,
  )
  if (!question) return

  // Special: title → slug
  if (questionId === 'scenario-title') {
    const slug = titleToSlug(answer || '')
    setNestedValue(artifact, 'scenario.name', slug || undefined)
    return
  }

  // Special: numeric context fields
  if (questionId === 'context-expected-cost' || questionId === 'context-budget-limit') {
    const mapping = question.fieldMappings[0]
    if (!mapping) return
    const str = String(answer ?? '').trim()
    if (str === '') {
      setNestedValue(artifact, mapping.path, undefined)
    } else {
      const num = Number(str)
      setNestedValue(artifact, mapping.path, isNaN(num) ? str : num)
    }
    return
  }

  // Standard: write to all mapped fields
  const shouldDelete = answer === undefined || answer === 'not_specified' || answer === ''
  for (const mapping of question.fieldMappings) {
    setNestedValue(artifact, mapping.path, shouldDelete ? undefined : answer)
  }
}

/**
 * Hydrate all scenario guided answers from the artifact.
 */
export function hydrateScenarioAnswers(
  artifact: Record<string, any>,
): Record<string, any> {
  const answers: Record<string, any> = {}
  for (const section of SCENARIO_GUIDED_SECTIONS) {
    for (const question of section.questions) {
      answers[question.id] = readScenarioAnswer(question.id, artifact)
    }
  }
  return answers
}

/**
 * Apply all scenario guided answers to the artifact.
 */
export function applyAllScenarioAnswers(
  answers: Record<string, any>,
  artifact: Record<string, any>,
): void {
  for (const [questionId, answer] of Object.entries(answers)) {
    applyScenarioAnswer(questionId, answer, artifact)
  }
}
