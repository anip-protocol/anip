import type { Requirements } from '../types'
import { GUIDED_SECTIONS } from './questions'

// ---------------------------------------------------------------------------
// Risk profile leaf types and walker
// ---------------------------------------------------------------------------

/** A resolved leaf node from the risk_profile tree */
export interface RiskLeaf {
  /** Dot-separated path from the root of risk_profile, e.g. "capabilities.book_flight" */
  name: string
  side_effect?: string
  high_risk?: boolean
  cost_visibility_required?: boolean
  recovery_guidance_required?: boolean
}

const LEAF_KEYS = new Set([
  'side_effect',
  'high_risk',
  'cost_visibility_required',
  'recovery_guidance_required',
])

function isCapabilityConfig(node: Record<string, any>): boolean {
  return Object.keys(node).some((k) => LEAF_KEYS.has(k))
}

function walkRiskNode(
  node: Record<string, any>,
  prefix: string,
  results: RiskLeaf[],
): void {
  if (isCapabilityConfig(node)) {
    results.push({
      name: prefix,
      side_effect: node['side_effect'],
      high_risk: node['high_risk'],
      cost_visibility_required: node['cost_visibility_required'],
      recovery_guidance_required: node['recovery_guidance_required'],
    })
  } else {
    for (const [key, value] of Object.entries(node)) {
      if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
        const childPath = prefix ? `${prefix}.${key}` : key
        walkRiskNode(value as Record<string, any>, childPath, results)
      }
    }
  }
}

/**
 * Recursively walks the risk_profile object and returns all capability leaf nodes.
 * A node is a leaf (capabilityConfig) if it has any of the leaf keys.
 * Container nodes are walked recursively.
 */
export function collectRiskLeaves(riskProfile: Record<string, any>): RiskLeaf[] {
  const results: RiskLeaf[] = []
  for (const [key, value] of Object.entries(riskProfile)) {
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      walkRiskNode(value as Record<string, any>, key, results)
    }
  }
  return results
}

// ---------------------------------------------------------------------------
// Risk profile bridge
// ---------------------------------------------------------------------------

/**
 * Bridges risk_profile leaf data to guided question IDs.
 * Returns a partial answers map for questions that can be inferred from the
 * risk profile — only sets answers to true, never to false.
 */
export function deriveFromRiskProfile(
  riskProfile: Record<string, any>,
): Partial<Record<string, any>> {
  const leaves = collectRiskLeaves(riskProfile)
  const derived: Partial<Record<string, any>> = {}

  for (const leaf of leaves) {
    if (leaf.side_effect === 'irreversible') {
      derived['has-irreversible'] = true
    }
    if (leaf.cost_visibility_required === true) {
      derived['cost-visibility'] = true
    }
    if (leaf.recovery_guidance_required === true) {
      derived['recovery-sensitive'] = true
    }
    if (leaf.high_risk === true) {
      derived['approval-expectation'] = true
    }
  }

  return derived
}

// ---------------------------------------------------------------------------
// Dot-path helpers
// ---------------------------------------------------------------------------

/**
 * Reads a value at a dot-separated path from a nested object.
 * Returns undefined if the path does not exist.
 */
export function getNestedValue(obj: Record<string, any>, path: string): any {
  const parts = path.split('.')
  let current: any = obj
  for (const part of parts) {
    if (current === null || current === undefined || typeof current !== 'object') {
      return undefined
    }
    current = current[part]
  }
  return current
}

/**
 * Sets a value at a dot-separated path in a nested object.
 * Creates intermediate objects as needed.
 * If value is undefined, deletes the key instead.
 */
export function setNestedValue(
  obj: Record<string, any>,
  path: string,
  value: any,
): void {
  const parts = path.split('.')
  let current: Record<string, any> = obj

  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i]
    if (
      current[part] === null ||
      current[part] === undefined ||
      typeof current[part] !== 'object'
    ) {
      current[part] = {}
    }
    current = current[part]
  }

  const lastKey = parts[parts.length - 1]
  if (value === undefined) {
    delete current[lastKey]
  } else {
    current[lastKey] = value
  }
}

// ---------------------------------------------------------------------------
// Single-question read / write
// ---------------------------------------------------------------------------

/**
 * Reads the answer for a question from the artifact by checking the primary
 * (first) mapped field. Falls back to the question's defaultValue if not present.
 */
export function readAnswerFromArtifact(
  questionId: string,
  artifact: Partial<Requirements>,
): any {
  const question = GUIDED_SECTIONS.flatMap((s) => s.questions).find(
    (q) => q.id === questionId,
  )
  if (!question) return undefined

  const primaryMapping = question.fieldMappings[0]
  if (!primaryMapping) return question.defaultValue

  const value = getNestedValue(artifact as Record<string, any>, primaryMapping.path)
  return value !== undefined ? value : question.defaultValue
}

/**
 * Writes an answer to all mapped fields in the artifact.
 * 'not_specified', empty string, and undefined values delete the field.
 */
export function applyAnswerToArtifact(
  questionId: string,
  answer: any,
  artifact: Partial<Requirements>,
): void {
  const question = GUIDED_SECTIONS.flatMap((s) => s.questions).find(
    (q) => q.id === questionId,
  )
  if (!question) return

  const shouldDelete =
    answer === undefined || answer === 'not_specified' || answer === ''

  for (const mapping of question.fieldMappings) {
    if (shouldDelete) {
      setNestedValue(artifact as Record<string, any>, mapping.path, undefined)
    } else {
      setNestedValue(artifact as Record<string, any>, mapping.path, answer)
    }
  }
}

// ---------------------------------------------------------------------------
// Bulk hydrate / apply
// ---------------------------------------------------------------------------

/**
 * Hydrates a full answers map from the artifact.
 * Reads all questions via their primary field mapping, then bridges from
 * risk_profile: any answers still at their false/undefined default are
 * overridden by derived values from the risk profile.
 */
export function hydrateAnswersFromArtifact(
  artifact: Partial<Requirements>,
): Record<string, any> {
  const allQuestions = GUIDED_SECTIONS.flatMap((s) => s.questions)
  const answers: Record<string, any> = {}

  // Primary read pass
  for (const question of allQuestions) {
    answers[question.id] = readAnswerFromArtifact(question.id, artifact)
  }

  // Bridge from risk_profile
  if (artifact.risk_profile && typeof artifact.risk_profile === 'object') {
    const derived = deriveFromRiskProfile(artifact.risk_profile as Record<string, any>)
    for (const [questionId, derivedValue] of Object.entries(derived)) {
      const question = allQuestions.find((q) => q.id === questionId)
      if (!question) continue
      const currentAnswer = answers[questionId]
      const isAtDefault =
        currentAnswer === undefined ||
        currentAnswer === question.defaultValue ||
        currentAnswer === false
      if (isAtDefault) {
        answers[questionId] = derivedValue
      }
    }
  }

  return answers
}

/**
 * Applies all answers back to the artifact — inverse of hydrateAnswersFromArtifact.
 */
export function applyAllAnswersToArtifact(
  answers: Record<string, any>,
  artifact: Partial<Requirements>,
): void {
  for (const [questionId, answer] of Object.entries(answers)) {
    applyAnswerToArtifact(questionId, answer, artifact)
  }
}
