# Design V3 Slice 3: Guided Scenario Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users create and refine scenario artifacts through a guided, plain-language experience while still producing the same canonical `Scenario` artifact used by validation and agents.

**Architecture:** Two lenses over one truth layer — the same pattern as Slice 2 for requirements. A new `guided/scenario-*` module set defines scenario-specific question configuration, artifact mapping with slug derivation, a scenario summary generator, and a scenario hint engine. The existing guided Vue components (`GuidedSection`, `GuidedQuestion`, `CompletenessHints`, `FieldChip`) are reused as-is. Store gains scenario-specific guided state (`scenarioMode`, `guidedScenarioAnswers`, `scenarioHints`). `ScenarioDetailView` gets a Guided/Advanced mode toggle parallel to `RequirementsView`.

**Tech Stack:** Vue 3, TypeScript, existing design store (reactive + watch), existing guided components, existing schema validation (AJV 2020)

---

## Scope Notes

- **`scenario.context` is intentionally flexible.** The guided flow offers structured prompts for common context keys observed in existing packs (capability, side_effect, cost/budget, permissions, identity/lineage), but always includes the existing `KeyValueEditor` for domain-specific context. Guided questions write into specific context keys; the fallback editor writes arbitrary keys. Both operate on the same `context` object.
- **`expected_behavior` and `expected_anip_support` are string arrays.** The guided flow offers common suggestions as clickable chips, but the user can also type free-text entries. There is no hidden ontology — stored output is always the canonical string array.
- **Slug derivation for `scenario.name`.** Guided mode lets the user enter a human-friendly title and auto-derives the slug (`lowercase`, `spaces→underscores`, `strip non-alphanumeric`). Advanced mode still exposes the exact stored slug. Both write to the same `scenario.name` field.

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/design/guided/scenario-questions.ts` | Scenario question definitions grouped by 5 sections, with field mappings |
| `src/design/guided/scenario-mappings.ts` | Bidirectional scenario mapping with slug derivation and suggestion list helpers |
| `src/design/guided/scenario-summary.ts` | Human-readable scenario summary from artifact state |
| `src/design/guided/scenario-hints.ts` | Scenario completeness/ambiguity hint engine (category-aware) |
| `src/design/components/ScenarioSummary.vue` | Scenario summary panel component |
| `src/design/components/SuggestionChips.vue` | Clickable chip suggestions for string array fields (behavior/support) |

### Modified Files

| File | Changes |
|------|---------|
| `src/design/types.ts` | Add `ScenarioMode` type |
| `src/design/store.ts` | Add `scenarioMode`, `guidedScenarioAnswers`, `scenarioHints`; add scenario hydration/apply functions; wire into `startEditing()`/`discardEdits()`/watcher |
| `src/views/ScenarioDetailView.vue` | Add Guided/Advanced mode toggle; render guided content inline when in guided mode |

### Reused Files (no changes needed)

| File | Usage |
|------|-------|
| `src/design/guided/types.ts` | `GuidedQuestion`, `GuidedSection`, `CompletenessHint`, `FieldMapping`, `AnswerType` — already generic |
| `src/design/components/GuidedSection.vue` | Renders scenario guided sections identically to requirements |
| `src/design/components/GuidedQuestion.vue` | Renders individual scenario questions |
| `src/design/components/CompletenessHints.vue` | Displays scenario hints |
| `src/design/components/FieldChip.vue` | Shows scenario field mappings |

---

## Task 1: Scenario Question Configuration

Define the 5 scenario-guided sections and their questions.

**Files:**
- Create: `studio/src/design/guided/scenario-questions.ts`

- [ ] **Step 1: Write the scenario question definitions**

```typescript
// studio/src/design/guided/scenario-questions.ts

import type { GuidedSection } from './types'

/** Common expected_behavior suggestions by category */
export const BEHAVIOR_SUGGESTIONS: Record<string, string[]> = {
  safety: [
    'do_not_execute',
    'explain_budget_conflict',
    'explain_authority_gap',
    'prefer_escalation_or_replan_over_blind_retry',
    'preserve_task_identity',
    'preserve_parent_invocation_lineage',
    'produce_audit_entry',
  ],
  recovery: [
    'retry_with_backoff',
    'escalate_to_human_on_failure',
    'preserve_task_identity',
    'produce_audit_entry',
    'do_not_retry_blindly',
  ],
  orchestration: [
    'preserve_task_identity',
    'preserve_parent_invocation_lineage',
    'produce_audit_entry',
    'system_does_not_execute_blindly_if_budget_control_exists',
    'operator_can_reconstruct_the_cross_service_chain',
  ],
  cross_service: [
    'preserve_task_identity',
    'preserve_parent_invocation_lineage',
    'both_services_produce_useful_audit_entries',
    'operator_can_reconstruct_the_cross_service_chain',
    'produce_audit_entry',
  ],
  observability: [
    'produce_audit_entry',
    'preserve_task_identity',
    'audit_entries_are_searchable',
    'operator_can_trace_invocation_chain',
  ],
}

/** Common expected_anip_support suggestions by category */
export const SUPPORT_SUGGESTIONS: Record<string, string[]> = {
  safety: [
    'cost_visibility',
    'side_effect_visibility',
    'structured_failure',
    'permission_discovery',
    'resolution_guidance',
    'task_id_support',
    'parent_invocation_id_support',
    'audit_queryability',
  ],
  recovery: [
    'structured_failure',
    'resolution_guidance',
    'task_id_support',
    'parent_invocation_id_support',
    'audit_queryability',
  ],
  orchestration: [
    'permission_discovery',
    'side_effect_visibility',
    'cost_visibility',
    'task_id_support',
    'parent_invocation_id_support',
    'audit_queryability',
    'structured_failure',
  ],
  cross_service: [
    'task_id_support',
    'parent_invocation_id_support',
    'audit_queryability',
    'cross_service_verification_guidance',
    'structured_failure',
  ],
  observability: [
    'task_id_support',
    'parent_invocation_id_support',
    'audit_queryability',
  ],
}

export const SCENARIO_GUIDED_SECTIONS: GuidedSection[] = [
  // Section 1: Scenario Basics
  {
    id: 'scenario-basics',
    title: 'Scenario Basics',
    description: 'What is this situation and what kind of problem does it represent?',
    questions: [
      {
        id: 'scenario-title',
        prompt: 'Give this scenario a descriptive title',
        helpText: 'A human-friendly name — the technical slug will be derived automatically (e.g. "Book Flight Over Budget" becomes book_flight_over_budget)',
        answerType: 'text',
        fieldMappings: [{ path: 'scenario.name', label: 'scenario.name' }],
        defaultValue: '',
      },
      {
        id: 'scenario-category',
        prompt: 'What kind of scenario is this?',
        helpText: 'This determines which validation rules apply and which suggestions appear',
        answerType: 'select',
        options: [
          { value: 'safety', label: 'Safety', description: 'Actions that must be blocked or controlled — budget, permissions, irreversible operations' },
          { value: 'recovery', label: 'Recovery', description: 'Handling blocked, failed, or degraded work' },
          { value: 'orchestration', label: 'Orchestration', description: 'Coordinating work across steps, services, or agents' },
          { value: 'cross_service', label: 'Cross-Service', description: 'Work that crosses service boundaries with handoff expectations' },
          { value: 'observability', label: 'Observability', description: 'Audit, traceability, and operational visibility' },
        ],
        fieldMappings: [{ path: 'scenario.category', label: 'scenario.category' }],
        defaultValue: 'safety',
      },
    ],
  },

  // Section 2: Narrative
  {
    id: 'scenario-narrative',
    title: 'Narrative',
    description: 'What is happening in this situation? Tell the story.',
    questions: [
      {
        id: 'scenario-narrative-text',
        prompt: 'Describe the scenario in plain language',
        helpText: 'e.g. "An agent is helping a user book travel within a budget, but the selected flight exceeds the budget limit."',
        answerType: 'text',
        fieldMappings: [{ path: 'scenario.narrative', label: 'scenario.narrative' }],
        defaultValue: '',
      },
    ],
  },

  // Section 3: Execution Context
  {
    id: 'scenario-context',
    title: 'Execution Context',
    description: 'What does the system know at decision time? What facts matter?',
    questions: [
      {
        id: 'context-capability',
        prompt: 'What capability or action is being attempted?',
        helpText: 'e.g. "book_flight", "delete_cluster", "deploy_service"',
        answerType: 'text',
        fieldMappings: [{ path: 'scenario.context.capability', label: 'scenario.context.capability' }],
        defaultValue: '',
      },
      {
        id: 'context-side-effect',
        prompt: 'What kind of side effect does this action have?',
        answerType: 'select',
        options: [
          { value: '', label: 'Not specified', description: 'No side effect information' },
          { value: 'none', label: 'None', description: 'Read-only, no state changes' },
          { value: 'reversible', label: 'Reversible', description: 'Can be undone' },
          { value: 'irreversible', label: 'Irreversible', description: 'Cannot be undone — e.g. sending email, deleting data' },
        ],
        fieldMappings: [{ path: 'scenario.context.side_effect', label: 'scenario.context.side_effect' }],
        defaultValue: '',
      },
      {
        id: 'context-expected-cost',
        prompt: 'What is the expected cost of this action?',
        helpText: 'Leave blank if cost is not relevant. Numeric value — e.g. 800',
        answerType: 'text',
        fieldMappings: [{ path: 'scenario.context.expected_cost', label: 'scenario.context.expected_cost' }],
        defaultValue: '',
      },
      {
        id: 'context-budget-limit',
        prompt: 'What is the budget limit?',
        helpText: 'Leave blank if there is no budget constraint. Numeric value — e.g. 500',
        answerType: 'text',
        fieldMappings: [{ path: 'scenario.context.budget_limit', label: 'scenario.context.budget_limit' }],
        defaultValue: '',
      },
      {
        id: 'context-permissions',
        prompt: 'What is the current permissions state?',
        answerType: 'select',
        options: [
          { value: '', label: 'Not specified', description: 'Permissions are not relevant to this scenario' },
          { value: 'available', label: 'Available', description: 'The agent has the required permissions' },
          { value: 'denied', label: 'Denied', description: 'The agent does not have required permissions' },
          { value: 'restricted', label: 'Restricted', description: 'Permissions exist but are restricted/grantable' },
        ],
        fieldMappings: [{ path: 'scenario.context.permissions_state', label: 'scenario.context.permissions_state' }],
        defaultValue: '',
      },
      {
        id: 'context-task-id',
        prompt: 'What is the task ID for this work?',
        helpText: 'Leave blank if task tracking is not relevant. Additional lineage fields (parent_invocation_id, client_reference_id) can be added in the context editor below.',
        answerType: 'text',
        fieldMappings: [{ path: 'scenario.context.task_id', label: 'scenario.context.task_id' }],
        defaultValue: '',
      },
    ],
  },

  // Sections 4 (Expected Behavior) and 5 (Expected ANIP Support) are NOT part of
  // SCENARIO_GUIDED_SECTIONS. They use SuggestionChips with category-aware suggestions
  // instead of the generic GuidedQuestion component, because expected_behavior and
  // expected_anip_support are string arrays — not single-value answers. The SuggestionChips
  // component writes directly to the draft artifact via updateDraftField.
]
```

- [ ] **Step 2: Verify the file compiles**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add studio/src/design/guided/scenario-questions.ts
git commit -m "feat(studio): add scenario guided question definitions for V3 Slice 3"
```

---

## Task 2: Scenario Mapping Engine

Bidirectional mapping between guided answers and scenario artifact fields, including slug derivation and numeric context field parsing.

**Files:**
- Create: `studio/src/design/guided/scenario-mappings.ts`

- [ ] **Step 1: Write the scenario mapping engine**

```typescript
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
  const question = SCENARIO_GUIDED_SECTIONS.flatMap(s => s.questions).find(q => q.id === questionId)
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
  const question = SCENARIO_GUIDED_SECTIONS.flatMap(s => s.questions).find(q => q.id === questionId)
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
```

- [ ] **Step 2: Verify the file compiles**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add studio/src/design/guided/scenario-mappings.ts
git commit -m "feat(studio): add scenario mapping engine with slug derivation"
```

---

## Task 3: Scenario Summary Generator

Generate a human-readable scenario summary from the artifact state.

**Files:**
- Create: `studio/src/design/guided/scenario-summary.ts`

- [ ] **Step 1: Write the scenario summary generator**

```typescript
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
```

- [ ] **Step 2: Verify the file compiles**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add studio/src/design/guided/scenario-summary.ts
git commit -m "feat(studio): add scenario summary generator"
```

---

## Task 4: Scenario Hint Engine

Category-aware completeness and ambiguity hints for scenario authoring.

**Files:**
- Create: `studio/src/design/guided/scenario-hints.ts`

- [ ] **Step 1: Write the scenario hint engine**

```typescript
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
```

- [ ] **Step 2: Verify the file compiles**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add studio/src/design/guided/scenario-hints.ts
git commit -m "feat(studio): add scenario completeness hint engine (category-aware)"
```

---

## Task 5: Unit Tests for Scenario Guided Logic

Test slug derivation, mapping round-trips, summary, and hints with real pack shapes.

**Files:**
- Create: `studio/src/__tests__/guided-scenario.test.ts`

- [ ] **Step 1: Write the tests**

```typescript
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
    const artifact = { scenario: { name: 'book_flight_over_budget', category: 'safety', narrative: '', context: {}, expected_behavior: [], expected_anip_support: [] } }
    const title = readScenarioAnswer('scenario-title', artifact)
    expect(title).toBe('book flight over budget')

    applyScenarioAnswer('scenario-title', 'Delete Production Cluster', artifact)
    expect(artifact.scenario.name).toBe('delete_production_cluster')
  })

  it('reads and writes category', () => {
    const artifact = { scenario: { name: 'test', category: 'safety', narrative: '', context: {}, expected_behavior: [], expected_anip_support: [] } }
    expect(readScenarioAnswer('scenario-category', artifact)).toBe('safety')

    applyScenarioAnswer('scenario-category', 'recovery', artifact)
    expect(artifact.scenario.category).toBe('recovery')
  })

  it('reads and writes context side_effect', () => {
    const artifact = { scenario: { name: 'test', category: 'safety', narrative: '', context: { side_effect: 'irreversible' }, expected_behavior: [], expected_anip_support: [] } }
    expect(readScenarioAnswer('context-side-effect', artifact)).toBe('irreversible')
  })

  it('parses numeric cost fields from string input', () => {
    const artifact = { scenario: { name: 'test', category: 'safety', narrative: '', context: {}, expected_behavior: [], expected_anip_support: [] } }
    applyScenarioAnswer('context-expected-cost', '800', artifact)
    expect(artifact.scenario.context.expected_cost).toBe(800)
  })

  it('removes cost field when set to empty string', () => {
    const artifact = { scenario: { name: 'test', category: 'safety', narrative: '', context: { expected_cost: 800 }, expected_behavior: [], expected_anip_support: [] } }
    applyScenarioAnswer('context-expected-cost', '', artifact)
    expect(artifact.scenario.context.expected_cost).toBeUndefined()
  })

  it('reads and writes task_id as direct text field', () => {
    const artifact = { scenario: { name: 'test', category: 'safety', narrative: '', context: { task_id: 'trip-q2' }, expected_behavior: [], expected_anip_support: [] } }
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
    const artifact = { scenario: { name: '', category: 'safety', narrative: '', context: {}, expected_behavior: [], expected_anip_support: [] } }
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
        context: { capability: 'book_flight', side_effect: 'irreversible', expected_cost: 800, budget_limit: 500 },
        expected_behavior: ['do_not_execute', 'explain_budget_conflict'],
        expected_anip_support: ['cost_visibility', 'structured_failure'],
      },
    })
    expect(summary.length).toBeGreaterThan(0)
    expect(summary.some(s => s.includes('safety'))).toBe(true)
    expect(summary.some(s => s.includes('book flight'))).toBe(true)
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
    expect(hints.some(h => h.id === 'safety-no-side-effect')).toBe(true)
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
    expect(hints.some(h => h.id === 'cross-service-no-boundary')).toBe(true)
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
    expect(hints.some(h => h.id === 'support-looks-like-behavior')).toBe(true)
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
    expect(hints.some(h => h.id === 'no-anip-support')).toBe(true)
  })

  it('does not warn for well-formed safety scenario', () => {
    const hints = evaluateScenarioCompleteness({
      scenario: {
        name: 'test',
        category: 'safety',
        narrative: 'An agent is helping a user book travel within a budget, but the cost exceeds the limit.',
        context: { capability: 'book_flight', side_effect: 'irreversible', expected_cost: 800, budget_limit: 500 },
        expected_behavior: ['do_not_execute', 'explain_budget_conflict'],
        expected_anip_support: ['cost_visibility', 'structured_failure'],
      },
    })
    expect(hints.some(h => h.id === 'safety-no-side-effect')).toBe(false)
    expect(hints.some(h => h.id === 'no-anip-support')).toBe(false)
  })
})
```

- [ ] **Step 2: Run the tests**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run src/__tests__/guided-scenario.test.ts`
Expected: All tests pass

- [ ] **Step 3: Fix any failures**

- [ ] **Step 4: Commit**

```bash
git add studio/src/__tests__/guided-scenario.test.ts
git commit -m "test(studio): add unit tests for scenario guided mappings, hints, and summary"
```

---

## Task 6: SuggestionChips Component

Clickable chip suggestions for string array fields. Selecting a chip adds it to the array; clicking again removes it. Users can also type free-text entries.

**Files:**
- Create: `studio/src/design/components/SuggestionChips.vue`

- [ ] **Step 1: Write the SuggestionChips component**

```vue
<!-- studio/src/design/components/SuggestionChips.vue -->
<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  modelValue: string[]
  suggestions: string[]
  readonly: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const newEntry = ref('')

function isSelected(suggestion: string): boolean {
  return props.modelValue.includes(suggestion)
}

function toggleSuggestion(suggestion: string) {
  if (props.readonly) return
  if (isSelected(suggestion)) {
    emit('update:modelValue', props.modelValue.filter(s => s !== suggestion))
  } else {
    emit('update:modelValue', [...props.modelValue, suggestion])
  }
}

function addCustomEntry() {
  if (props.readonly) return
  const entry = newEntry.value.trim()
  if (entry && !props.modelValue.includes(entry)) {
    emit('update:modelValue', [...props.modelValue, entry])
  }
  newEntry.value = ''
}

function removeEntry(entry: string) {
  if (props.readonly) return
  emit('update:modelValue', props.modelValue.filter(s => s !== entry))
}
</script>

<template>
  <div class="suggestion-chips">
    <!-- Suggestions -->
    <div class="chip-grid" v-if="suggestions.length > 0">
      <button
        v-for="suggestion in suggestions"
        :key="suggestion"
        class="chip"
        :class="{ selected: isSelected(suggestion), readonly }"
        :disabled="readonly"
        type="button"
        @click="toggleSuggestion(suggestion)"
      >
        {{ suggestion.replace(/_/g, ' ') }}
      </button>
    </div>

    <!-- Custom entry input -->
    <div class="custom-entry" v-if="!readonly">
      <input
        class="form-input"
        type="text"
        v-model="newEntry"
        :placeholder="placeholder ?? 'Add custom entry...'"
        @keydown.enter.prevent="addCustomEntry"
      />
      <button class="add-btn" type="button" @click="addCustomEntry" :disabled="!newEntry.trim()">
        Add
      </button>
    </div>

    <!-- Selected entries (showing custom ones not in suggestions) -->
    <div class="selected-list" v-if="modelValue.length > 0">
      <div
        v-for="entry in modelValue"
        :key="entry"
        class="selected-entry"
      >
        <span class="entry-text">{{ entry.replace(/_/g, ' ') }}</span>
        <button
          v-if="!readonly"
          class="remove-btn"
          type="button"
          @click="removeEntry(entry)"
          title="Remove"
        >
          &#x2715;
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.suggestion-chips {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition);
}

.chip.selected {
  background: rgba(52, 211, 153, 0.12);
  color: var(--success);
  border-color: rgba(52, 211, 153, 0.3);
}

.chip:hover:not(:disabled):not(.selected) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.chip.readonly {
  cursor: default;
}

.chip:disabled {
  opacity: 0.5;
  cursor: default;
}

.custom-entry {
  display: flex;
  gap: 8px;
}

.form-input {
  flex: 1;
  font-size: 13px;
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  outline: none;
}

.add-btn {
  font-size: 12px;
  font-weight: 600;
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition);
}

.add-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.add-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.selected-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.selected-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-secondary);
}

.remove-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  padding: 0 4px;
}

.remove-btn:hover {
  color: var(--error);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/components/SuggestionChips.vue
git commit -m "feat(studio): add SuggestionChips component for string array fields"
```

---

## Task 7: ScenarioSummary Component

Displays the human-readable scenario summary derived from artifact state.

**Files:**
- Create: `studio/src/design/components/ScenarioSummary.vue`

- [ ] **Step 1: Write the ScenarioSummary component**

```vue
<!-- studio/src/design/components/ScenarioSummary.vue -->
<script setup lang="ts">
import { computed } from 'vue'
import { generateScenarioSummary } from '../guided/scenario-summary'

const props = defineProps<{
  scenario: Record<string, any>
}>()

const paragraphs = computed(() => generateScenarioSummary(props.scenario))
</script>

<template>
  <div class="scenario-summary" v-if="paragraphs.length > 0">
    <h3 class="summary-title">Scenario Summary</h3>
    <div class="summary-body">
      <p v-for="(para, i) in paragraphs" :key="i" class="summary-paragraph">
        {{ para }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.scenario-summary {
  background: rgba(96, 165, 250, 0.04);
  border: 1px solid rgba(96, 165, 250, 0.15);
  border-radius: var(--radius-sm, 6px);
  padding: 16px 20px;
  margin-bottom: 16px;
}

.summary-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.summary-body {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.summary-paragraph {
  margin: 0 0 6px;
}

.summary-paragraph:last-child {
  margin-bottom: 0;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/components/ScenarioSummary.vue
git commit -m "feat(studio): add ScenarioSummary component"
```

---

## Task 8: Store Updates — Scenario Guided Mode State

Add `scenarioMode`, `guidedScenarioAnswers`, `scenarioHints` to the design store.

**Files:**
- Modify: `studio/src/design/types.ts`
- Modify: `studio/src/design/store.ts`

- [ ] **Step 1: Add ScenarioMode type to types.ts**

Add to the end of `studio/src/design/types.ts`:
```typescript
export type ScenarioMode = 'guided' | 'advanced'
```

- [ ] **Step 2: Add scenario guided state to store.ts**

Add imports at the top of store.ts:
```typescript
import type { ScenarioMode } from './types'
import { hydrateScenarioAnswers, applyScenarioAnswer } from './guided/scenario-mappings'
import { evaluateScenarioCompleteness } from './guided/scenario-hints'
```

Add to `DesignState` interface:
```typescript
  scenarioMode: ScenarioMode
  guidedScenarioAnswers: Record<string, any>
  scenarioHints: CompletenessHint[]
```

Add default values to reactive state:
```typescript
  scenarioMode: 'guided',
  guidedScenarioAnswers: {},
  scenarioHints: [],
```

- [ ] **Step 3: Add scenario guided functions**

```typescript
/** Toggle between guided and advanced scenario mode. */
export function setScenarioMode(mode: ScenarioMode): void {
  designStore.scenarioMode = mode

  if (mode === 'guided' && designStore.draftScenario) {
    designStore.guidedScenarioAnswers = hydrateScenarioAnswers(designStore.draftScenario)
    designStore.scenarioHints = evaluateScenarioCompleteness(designStore.draftScenario)
  }
}

/** Update a single guided scenario answer and apply it to the draft artifact. */
export function updateGuidedScenarioAnswer(questionId: string, value: any): void {
  designStore.guidedScenarioAnswers[questionId] = value

  if (designStore.draftScenario) {
    applyScenarioAnswer(questionId, value, designStore.draftScenario)
    designStore.scenarioHints = evaluateScenarioCompleteness(designStore.draftScenario)
  }
}
```

- [ ] **Step 4: Wire scenario hydration into startEditing()**

After existing requirements hydration, add:
```typescript
  designStore.guidedScenarioAnswers = hydrateScenarioAnswers(designStore.draftScenario!)
  designStore.scenarioHints = evaluateScenarioCompleteness(designStore.draftScenario!)
```

- [ ] **Step 5: Clear scenario guided state in discardEdits()**

Add:
```typescript
  designStore.guidedScenarioAnswers = {}
  designStore.scenarioHints = []
```

- [ ] **Step 6: Add scenario hints to the debounced watcher**

Update the watch callback to also evaluate scenario hints:
```typescript
    validateTimer = setTimeout(() => {
      validateDraft()
      if (designStore.draftRequirements) {
        designStore.completenessHints = evaluateCompleteness(designStore.draftRequirements)
      }
      if (designStore.draftScenario) {
        designStore.scenarioHints = evaluateScenarioCompleteness(designStore.draftScenario)
      }
    }, 300)
```

- [ ] **Step 7: Verify the store compiles**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 8: Run all tests**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run 2>&1 | tail -15`
Expected: All tests pass

- [ ] **Step 9: Commit**

```bash
git add studio/src/design/store.ts studio/src/design/types.ts
git commit -m "feat(studio): add scenario guided mode state to store"
```

---

## Task 9: ScenarioDetailView — Mode Toggle and Guided Content

Add the Guided/Advanced mode toggle and guided content to ScenarioDetailView.

**Files:**
- Modify: `studio/src/views/ScenarioDetailView.vue`

- [ ] **Step 1: Add imports**

Add to the script setup:
```typescript
import { designStore, setActivePack, updateDraftField, setScenarioMode, updateGuidedScenarioAnswer } from '../design/store'
import { SCENARIO_GUIDED_SECTIONS, BEHAVIOR_SUGGESTIONS, SUPPORT_SUGGESTIONS } from '../design/guided/scenario-questions'
import { hydrateScenarioAnswers } from '../design/guided/scenario-mappings'
import { evaluateScenarioCompleteness } from '../design/guided/scenario-hints'
import GuidedSection from '../design/components/GuidedSection.vue'
import ScenarioSummary from '../design/components/ScenarioSummary.vue'
import CompletenessHints from '../design/components/CompletenessHints.vue'
import SuggestionChips from '../design/components/SuggestionChips.vue'
```

Add computed properties for guided answers and hints (read mode + edit mode):
```typescript
const guidedScenarioAnswers = computed(() => {
  if (isEditing.value) return designStore.guidedScenarioAnswers
  return hydrateScenarioAnswers(pack.value?.scenario ?? {})
})

const scenarioHints = computed(() => {
  if (isEditing.value) return designStore.scenarioHints
  return evaluateScenarioCompleteness(pack.value?.scenario ?? {})
})

const currentCategory = computed(() => {
  return scenario.value?.category ?? 'safety'
})

const behaviorSuggestions = computed(() => {
  return BEHAVIOR_SUGGESTIONS[currentCategory.value] ?? []
})

const supportSuggestions = computed(() => {
  return SUPPORT_SUGGESTIONS[currentCategory.value] ?? []
})
```

- [ ] **Step 2: Add mode toggle to the template**

After the `<h1>` page title (or equivalent header area) and before `<EditorToolbar>`, add:
```html
    <!-- Mode toggle -->
    <div class="mode-toggle">
      <button
        class="mode-btn"
        :class="{ active: designStore.scenarioMode === 'guided' }"
        @click="setScenarioMode('guided')"
        type="button"
      >
        Guided
      </button>
      <button
        class="mode-btn"
        :class="{ active: designStore.scenarioMode === 'advanced' }"
        @click="setScenarioMode('advanced')"
        type="button"
      >
        Advanced
      </button>
    </div>
```

- [ ] **Step 3: Add guided content**

After `<EditorToolbar artifact="scenario" />`, add guided mode content:
```html
    <!-- Guided mode -->
    <template v-if="designStore.scenarioMode === 'guided'">
      <ScenarioSummary :scenario="designStore.draftScenario ?? pack?.scenario ?? {}" />
      <CompletenessHints :hints="scenarioHints" />

      <div class="mapping-toggle" v-if="isEditing">
        <label class="mapping-label">
          <input
            type="checkbox"
            :checked="designStore.showFieldMappings"
            @change="designStore.showFieldMappings = !designStore.showFieldMappings"
          />
          Show technical field mappings
        </label>
      </div>

      <!-- Basics, Narrative, Context sections via GuidedSection -->
      <GuidedSection
        v-for="section in SCENARIO_GUIDED_SECTIONS"
        :key="section.id"
        :section="section"
        :answers="guidedScenarioAnswers"
        :showMappings="designStore.showFieldMappings"
        :readonly="!isEditing"
        @update:answer="updateGuidedScenarioAnswer"
      />

      <!-- Expected Behavior with suggestions -->
      <div class="guided-section-card">
        <h2 class="guided-section-title">Expected Behavior</h2>
        <p class="guided-section-desc">What should the system do in this situation?</p>
        <SuggestionChips
          :modelValue="scenario.expected_behavior ?? []"
          :suggestions="behaviorSuggestions"
          :readonly="!isEditing"
          placeholder="Add custom behavior..."
          @update:modelValue="setField('expected_behavior', $event)"
        />
      </div>

      <!-- Expected ANIP Support with suggestions -->
      <div class="guided-section-card">
        <h2 class="guided-section-title">Expected ANIP Support</h2>
        <p class="guided-section-desc">What should the protocol/interface itself make visible or explicit?</p>
        <SuggestionChips
          :modelValue="scenario.expected_anip_support ?? []"
          :suggestions="supportSuggestions"
          :readonly="!isEditing"
          placeholder="Add custom ANIP support..."
          @update:modelValue="setField('expected_anip_support', $event)"
        />
      </div>

      <!-- Advanced context editor (for domain-specific keys not covered by guided questions) -->
      <div class="guided-section-card" v-if="isEditing">
        <h2 class="guided-section-title">Additional Context</h2>
        <p class="guided-section-desc">Add domain-specific context keys beyond the guided questions above.</p>
        <KeyValueEditor
          :modelValue="scenario.context ?? {}"
          @update:modelValue="setField('context', $event)"
        />
      </div>
    </template>
```

Wrap existing edit + read content in:
```html
    <!-- Advanced mode -->
    <template v-else>
      <!-- ... all existing template content ... -->
    </template>
```

- [ ] **Step 4: Add styles**

Add to `<style scoped>`:
```css
.mode-toggle {
  display: flex;
  gap: 0;
  margin-bottom: 1rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
  width: fit-content;
}

.mode-btn {
  padding: 6px 20px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition);
}

.mode-btn.active {
  background: var(--accent);
  color: var(--text-primary);
}

.mode-btn:hover:not(.active) {
  background: var(--bg-hover);
}

.mapping-toggle {
  margin-bottom: 16px;
}

.mapping-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
}

.mapping-label input[type="checkbox"] {
  cursor: pointer;
}

.guided-section-card {
  background: var(--bg-input, #1a1a2e);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
  padding: 16px 20px;
  margin-bottom: 16px;
}

.guided-section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px;
}

.guided-section-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 12px;
}
```

- [ ] **Step 5: Verify build**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -30`
Expected: No errors

- [ ] **Step 6: Run all tests**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run 2>&1 | tail -15`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add studio/src/views/ScenarioDetailView.vue
git commit -m "feat(studio): add Guided/Advanced mode toggle on ScenarioDetailView"
```

---

## Task 10: EditorToolbar — Scenario Hint Count

Update EditorToolbar to show scenario hints when viewing a scenario artifact.

**Files:**
- Modify: `studio/src/design/components/EditorToolbar.vue`

- [ ] **Step 1: Update hint count to include scenario hints**

Change the existing `hintCount` computed in `EditorToolbar.vue`:

From:
```typescript
const hintCount = computed(() => designStore.completenessHints.length)
```

To:
```typescript
const hintCount = computed(() => {
  if (props.artifact === 'scenario') {
    return designStore.scenarioHints.length
  }
  return designStore.completenessHints.length
})
```

- [ ] **Step 2: Verify**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add studio/src/design/components/EditorToolbar.vue
git commit -m "feat(studio): show scenario-specific hint count in EditorToolbar"
```

---

## Task 11: End-to-End Integration Verification

Verify the full guided scenario flow works.

**Files:**
- No new files

- [ ] **Step 1: Run type-check**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`
Expected: Clean

- [ ] **Step 2: Run all tests**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run 2>&1 | tail -15`
Expected: All tests pass

- [ ] **Step 3: Production build**

Run: `cd /Users/samirski/Development/ANIP/studio && npm run build 2>&1 | tail -10`
Expected: Build succeeds

- [ ] **Step 4: Fix any issues found**

- [ ] **Step 5: Commit fixes**

```bash
git add -A
git commit -m "fix(studio): address integration issues in guided scenario flow"
```

---

## Task 12: Sync Embedded Assets

**Files:**
- Modify: embedded assets across all 5 runtime packages

- [ ] **Step 1: Run sync**

Run: `cd /Users/samirski/Development/ANIP/studio && bash sync.sh`
Expected: Build succeeds, assets copied to 5 runtime packages

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "build(studio): sync embedded assets after V3 Slice 3 guided scenario"
```
