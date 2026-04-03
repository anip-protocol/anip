# Design V3 Slice 2: Guided Requirements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users define RequirementsSet through a guided, plain-language experience while still producing the same canonical requirements artifact used by validation and agents.

**Architecture:** Two lenses over one truth layer. The guided flow is a question-based input lens that maps answers to canonical artifact fields. The advanced flow is the existing field-level editor. Both operate on the same in-memory draft object managed by `store.ts`. A new `guided/` module defines question configuration, artifact mapping rules, a summary generator, and a completeness hint engine — all derived from artifact state, never hidden UI-only semantics.

**Tech Stack:** Vue 3, TypeScript, existing design store (reactive + watch), existing EditorToolbar, existing schema validation (AJV 2020)

---

## Scope Notes

The following artifact fields are **not covered by guided questions** in this slice because their structure does not lend itself to simple question-answer patterns:

- **`risk_profile`**: A tree of arbitrary capability names with nested `capabilityConfig` nodes. The guided flow captures risk intent via `business_constraints` (spending, irreversibility, cost visibility). Detailed per-capability risk configuration remains advanced-mode only via the `KeyValueEditor`.
- **`services`**: An array of `{name, role, public_http?, internal_only?}` objects. Adding named services requires a dynamic list editor beyond question-answer patterns. The guided flow covers cross-service _expectations_ (handoffs, reconstruction, continuity) but not the service inventory itself.
- **`transports`**: Required schema fields but purely technical (http/stdio/grpc toggles). Covered by advanced mode only.

These are intentional scope boundaries — later slices may add richer guided editors for these.

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/design/guided/questions.ts` | Question definitions grouped by section, with field mappings and answer-to-value transforms |
| `src/design/guided/mappings.ts` | Applies guided answers to the draft artifact; reads artifact state back into guided answers |
| `src/design/guided/summary.ts` | Generates human-readable requirements summary from artifact state |
| `src/design/guided/hints.ts` | Completeness and ambiguity hint engine — advisory warnings derived from artifact state |
| `src/design/guided/types.ts` | Type definitions for guided questions, sections, answers, hints |
| `src/design/components/GuidedSection.vue` | Reusable card component for one guided section (title, questions, field chips) |
| `src/design/components/GuidedQuestion.vue` | Single question renderer (supports boolean, select, text answer types) |
| `src/design/components/RequirementsSummary.vue` | Human-readable summary panel derived from artifact |
| `src/design/components/CompletenessHints.vue` | Advisory hint display with expandable explanations |
| `src/design/components/FieldChip.vue` | Small chip showing which artifact field(s) a guided answer maps to |

### Modified Files

| File | Changes |
|------|---------|
| `src/design/store.ts` | Add `requirementsMode: 'guided' \| 'advanced'` to state; add guided answer hydration on `startEditing()`; add completeness hint evaluation |
| `src/design/types.ts` | Add `RequirementsMode` type |
| `src/views/RequirementsView.vue` | Add Guided/Advanced mode toggle; render guided content inline; fix pre-existing bugs in advanced mode (trust `attested` option, scale enum values, business_constraints string rendering) |
| `src/design/components/EditorToolbar.vue` | Add completeness hint count badge alongside validation errors |

---

## Task 1: Guided Types and Question Configuration

Define the type system and question definitions that drive the entire guided experience.

**Files:**
- Create: `studio/src/design/guided/types.ts`
- Create: `studio/src/design/guided/questions.ts`

- [ ] **Step 1: Write the guided type definitions**

```typescript
// studio/src/design/guided/types.ts

/** Answer types supported by guided questions */
export type AnswerType = 'boolean' | 'select' | 'text'

/** A single option for select-type answers */
export interface SelectOption {
  value: string
  label: string
  description?: string
}

/** Maps a guided answer to one or more artifact fields */
export interface FieldMapping {
  /** Dot-separated path into the requirements artifact (e.g. "audit.durable") */
  path: string
  /** Human-readable label for the mapped field */
  label: string
}

/** A single guided question */
export interface GuidedQuestion {
  id: string
  prompt: string
  helpText?: string
  answerType: AnswerType
  /** For select answers */
  options?: SelectOption[]
  /** Which artifact fields this question maps to */
  fieldMappings: FieldMapping[]
  /** Default answer value when starting fresh */
  defaultValue: any
}

/** A section grouping related questions */
export interface GuidedSection {
  id: string
  title: string
  description: string
  questions: GuidedQuestion[]
}

/** An advisory completeness/ambiguity hint */
export interface CompletenessHint {
  id: string
  severity: 'info' | 'warning'
  message: string
  explanation: string
  /** Which artifact fields are relevant to this hint */
  relatedFields: string[]
}
```

- [ ] **Step 2: Write the question definitions for all 6 sections**

```typescript
// studio/src/design/guided/questions.ts

import type { GuidedSection } from './types'

export const GUIDED_SECTIONS: GuidedSection[] = [
  // Section 1: System Basics
  {
    id: 'system-basics',
    title: 'System Basics',
    description: 'What is this system and how will it be deployed?',
    questions: [
      {
        id: 'system-name',
        prompt: 'What is the name of this system?',
        answerType: 'text',
        fieldMappings: [{ path: 'system.name', label: 'system.name' }],
        defaultValue: '',
      },
      {
        id: 'system-domain',
        prompt: 'What domain does this system serve?',
        helpText: 'e.g. fintech, healthcare, devops, e-commerce',
        answerType: 'text',
        fieldMappings: [{ path: 'system.domain', label: 'system.domain' }],
        defaultValue: '',
      },
      {
        id: 'deployment-intent',
        prompt: 'How will this system be deployed?',
        helpText: 'Describe the deployment target — e.g. "production SaaS", "internal tooling", "embedded in CLI"',
        answerType: 'text',
        fieldMappings: [{ path: 'system.deployment_intent', label: 'system.deployment_intent' }],
        defaultValue: '',
      },
      {
        id: 'scale-shape',
        prompt: 'What is the expected deployment shape?',
        answerType: 'select',
        options: [
          { value: 'embedded_single_process', label: 'Embedded / Single Process', description: 'Runs inside another application' },
          { value: 'production_single_service', label: 'Single Service', description: 'One standalone service' },
          { value: 'horizontally_scaled', label: 'Horizontally Scaled', description: 'Multiple instances of one service' },
          { value: 'control_plane_worker_split', label: 'Control Plane + Workers', description: 'Separate control and worker processes' },
          { value: 'multi_service_estate', label: 'Multi-Service Estate', description: 'Multiple cooperating services' },
        ],
        fieldMappings: [{ path: 'scale.shape_preference', label: 'scale.shape_preference' }],
        defaultValue: 'production_single_service',
      },
      {
        id: 'high-availability',
        prompt: 'Does this system require high availability?',
        answerType: 'boolean',
        fieldMappings: [{ path: 'scale.high_availability', label: 'scale.high_availability' }],
        defaultValue: false,
      },
      {
        id: 'trust-mode',
        prompt: 'What level of trust verification does this system require?',
        helpText: 'Unsigned: no verification. Signed: cryptographic signatures. Anchored: trust anchored to known roots. Attested: hardware-backed attestation.',
        answerType: 'select',
        options: [
          { value: 'unsigned', label: 'Unsigned', description: 'No cryptographic verification' },
          { value: 'signed', label: 'Signed', description: 'Cryptographic signatures on messages' },
          { value: 'anchored', label: 'Anchored', description: 'Trust anchored to known roots' },
          { value: 'attested', label: 'Attested', description: 'Hardware-backed attestation' },
        ],
        fieldMappings: [{ path: 'trust.mode', label: 'trust.mode' }],
        defaultValue: 'unsigned',
      },
      {
        id: 'trust-checkpoints',
        prompt: 'Should the system support trust checkpoints?',
        helpText: 'Checkpoints allow verifying trust state at key points during execution',
        answerType: 'boolean',
        fieldMappings: [{ path: 'trust.checkpoints', label: 'trust.checkpoints' }],
        defaultValue: false,
      },
    ],
  },

  // Section 2: Risk and Side Effects
  {
    id: 'risk-side-effects',
    title: 'Risk and Side Effects',
    description: 'Can actions spend money, cause irreversible changes, or carry high risk?',
    questions: [
      {
        id: 'has-spending',
        prompt: 'Can any action in this system spend money?',
        helpText: 'e.g. purchasing, billing, resource provisioning with cost',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'business_constraints.spending_possible', label: 'business_constraints.spending_possible' },
        ],
        defaultValue: false,
      },
      {
        id: 'has-irreversible',
        prompt: 'Are any actions irreversible?',
        helpText: 'e.g. deleting data, sending emails, executing trades',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'business_constraints.irreversible_actions_present', label: 'business_constraints.irreversible_actions_present' },
        ],
        defaultValue: false,
      },
      {
        id: 'cost-visibility',
        prompt: 'Should the user or agent see cost before acting?',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'business_constraints.cost_visibility_required', label: 'business_constraints.cost_visibility_required' },
        ],
        defaultValue: false,
      },
    ],
  },

  // Section 3: Authority and Approval Expectations
  {
    id: 'authority-approval',
    title: 'Authority and Approval Expectations',
    description: 'What control or approval posture is expected for this system?',
    questions: [
      {
        id: 'preflight-discovery',
        prompt: 'Should missing authority be visible before acting?',
        helpText: 'Agents can discover what they are allowed to do before attempting actions',
        answerType: 'boolean',
        fieldMappings: [{ path: 'permissions.preflight_discovery', label: 'permissions.preflight_discovery' }],
        defaultValue: false,
      },
      {
        id: 'grantable-restrictions',
        prompt: 'Should restricted actions be grantable by a higher authority?',
        helpText: 'Some actions may be restricted but upgradeable if the right authority grants access',
        answerType: 'boolean',
        fieldMappings: [{ path: 'permissions.grantable_requirements', label: 'permissions.grantable_requirements' }],
        defaultValue: false,
      },
      {
        id: 'restricted-vs-denied',
        prompt: 'Should the system distinguish between "restricted" and "denied"?',
        helpText: '"Restricted" means potentially grantable; "denied" means never allowed',
        answerType: 'boolean',
        fieldMappings: [{ path: 'permissions.restricted_vs_denied', label: 'permissions.restricted_vs_denied' }],
        defaultValue: false,
      },
      {
        id: 'delegation-tokens',
        prompt: 'Will authority be delegated via tokens?',
        helpText: 'Delegation tokens carry scoped authority from a principal to an agent',
        answerType: 'boolean',
        fieldMappings: [{ path: 'auth.delegation_tokens', label: 'auth.delegation_tokens' }],
        defaultValue: false,
      },
      {
        id: 'scoped-authority',
        prompt: 'Should authority be scoped to specific purposes?',
        answerType: 'boolean',
        fieldMappings: [{ path: 'auth.scoped_authority', label: 'auth.scoped_authority' }],
        defaultValue: false,
      },
      {
        id: 'purpose-binding',
        prompt: 'Should actions be bound to a declared purpose?',
        helpText: 'Purpose binding ensures agents act within the intent of their delegated authority',
        answerType: 'boolean',
        fieldMappings: [{ path: 'auth.purpose_binding', label: 'auth.purpose_binding' }],
        defaultValue: false,
      },
      {
        id: 'approval-expectation',
        prompt: 'Are there high-risk actions that should have stronger control or approval expectations?',
        helpText: 'This captures approval intent as a business constraint — the system does not yet have a first-class approval model',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'business_constraints.approval_expected_for_high_risk', label: 'business_constraints.approval_expected_for_high_risk' },
        ],
        defaultValue: false,
      },
    ],
  },

  // Section 4: Recovery Expectations
  {
    id: 'recovery-expectations',
    title: 'Recovery Expectations',
    description: 'How should blocked or failed work be handled?',
    questions: [
      {
        id: 'recovery-sensitive',
        prompt: 'Is this system sensitive to how failed or blocked work is recovered?',
        helpText: 'e.g. should the system have explicit guidance for retrying, re-validating, or escalating',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'business_constraints.recovery_sensitive', label: 'business_constraints.recovery_sensitive' },
        ],
        defaultValue: false,
      },
      {
        id: 'blocked-failure-expectation',
        prompt: 'What should happen when work is blocked or fails?',
        helpText: 'Describe the expected behavior — this is captured as a business constraint',
        answerType: 'select',
        options: [
          { value: 'not_specified', label: 'Not specified', description: 'No particular expectation' },
          { value: 'retry_with_backoff', label: 'Retry with backoff', description: 'Automatically retry failed operations' },
          { value: 'escalate_to_human', label: 'Escalate to human', description: 'Alert a human operator when work is blocked' },
          { value: 'fail_safe', label: 'Fail safe', description: 'Stop and leave system in a safe state' },
        ],
        fieldMappings: [
          { path: 'business_constraints.blocked_failure_posture', label: 'business_constraints.blocked_failure_posture' },
        ],
        defaultValue: 'not_specified',
      },
    ],
  },

  // Section 5: Audit and Traceability
  {
    id: 'audit-traceability',
    title: 'Audit and Traceability',
    description: 'Do you need to know what happened later?',
    questions: [
      {
        id: 'needs-audit',
        prompt: 'Do you need a durable record of what happened?',
        helpText: 'Durable audit means actions are recorded in a way that survives restarts',
        answerType: 'boolean',
        fieldMappings: [{ path: 'audit.durable', label: 'audit.durable' }],
        defaultValue: false,
      },
      {
        id: 'needs-searchable',
        prompt: 'Do you need to search through those records?',
        helpText: 'Searchable audit allows querying by time, action, actor, etc.',
        answerType: 'boolean',
        fieldMappings: [{ path: 'audit.searchable', label: 'audit.searchable' }],
        defaultValue: false,
      },
      {
        id: 'invocation-tracking',
        prompt: 'Should each action be individually trackable?',
        helpText: 'Invocation IDs let you trace exactly what happened for each call',
        answerType: 'boolean',
        fieldMappings: [{ path: 'lineage.invocation_id', label: 'lineage.invocation_id' }],
        defaultValue: false,
      },
      {
        id: 'task-tracking',
        prompt: 'Should related actions be grouped into tasks?',
        helpText: 'Task IDs group multiple invocations into a logical unit of work',
        answerType: 'boolean',
        fieldMappings: [
          { path: 'lineage.task_id', label: 'lineage.task_id' },
        ],
        defaultValue: false,
      },
      {
        id: 'parent-tracking',
        prompt: 'Should actions track which action triggered them?',
        helpText: 'Parent invocation IDs create a call chain for debugging and reconstruction',
        answerType: 'boolean',
        fieldMappings: [{ path: 'lineage.parent_invocation_id', label: 'lineage.parent_invocation_id' }],
        defaultValue: false,
      },
      {
        id: 'client-reference',
        prompt: 'Should callers be able to attach their own reference IDs?',
        helpText: 'Client reference IDs let external systems correlate their requests with your system',
        answerType: 'boolean',
        fieldMappings: [{ path: 'lineage.client_reference_id', label: 'lineage.client_reference_id' }],
        defaultValue: false,
      },
    ],
  },

  // Section 6: Multi-Service Expectations
  {
    id: 'multi-service',
    title: 'Multi-Service Expectations',
    description: 'Will work cross multiple services?',
    questions: [
      {
        id: 'service-handoffs',
        prompt: 'Will agents hand off work between services?',
        helpText: 'Service-to-service handoffs require coordinated authority passing',
        answerType: 'boolean',
        fieldMappings: [{ path: 'auth.service_to_service_handoffs', label: 'auth.service_to_service_handoffs' }],
        defaultValue: false,
      },
      {
        id: 'cross-service-reconstruction',
        prompt: 'Do you need to reconstruct what happened across multiple services?',
        helpText: 'Cross-service reconstruction lets you trace a request across service boundaries',
        answerType: 'boolean',
        fieldMappings: [{ path: 'audit.cross_service_reconstruction_required', label: 'audit.cross_service_reconstruction_required' }],
        defaultValue: false,
      },
      {
        id: 'cross-service-continuity',
        prompt: 'Should lineage be maintained across service boundaries?',
        helpText: 'Cross-service continuity preserves invocation chains across services',
        answerType: 'boolean',
        fieldMappings: [{ path: 'lineage.cross_service_continuity_required', label: 'lineage.cross_service_continuity_required' }],
        defaultValue: false,
      },
    ],
  },
]
```

- [ ] **Step 3: Verify the file compiles**

Run: `cd /Users/samirski/Development/ANIP/studio && npx tsc --noEmit src/design/guided/types.ts src/design/guided/questions.ts 2>&1 | head -20`
Expected: No errors (or only unrelated existing warnings)

- [ ] **Step 4: Commit**

```bash
git add studio/src/design/guided/types.ts studio/src/design/guided/questions.ts
git commit -m "feat(studio): add guided question types and section definitions for V3 Slice 2"
```

---

## Task 2: Guided-to-Artifact Mapping Engine

Build the bidirectional mapping between guided answers and artifact fields.

**Files:**
- Create: `studio/src/design/guided/mappings.ts`

- [ ] **Step 1: Write the mapping engine**

```typescript
// studio/src/design/guided/mappings.ts

import { GUIDED_SECTIONS } from './questions'
import type { GuidedQuestion } from './types'

/**
 * A capabilityConfig leaf node from the recursive riskNode tree.
 */
interface RiskLeaf {
  name: string
  side_effect?: string
  high_risk?: boolean
  cost_visibility_required?: boolean
  recovery_guidance_required?: boolean
}

/**
 * Recursively walk a riskNode tree and collect all capabilityConfig leaf nodes.
 * A node is a leaf if it has any capabilityConfig field (side_effect, high_risk,
 * cost_visibility_required, recovery_guidance_required). Otherwise it is a
 * container whose values are child riskNodes.
 */
function collectRiskLeaves(
  node: Record<string, any>,
  prefix: string = '',
): RiskLeaf[] {
  const CAP_FIELDS = new Set(['side_effect', 'high_risk', 'cost_visibility_required', 'recovery_guidance_required'])
  const keys = Object.keys(node)
  const isLeaf = keys.some(k => CAP_FIELDS.has(k))

  if (isLeaf) {
    return [{
      name: prefix || '(root)',
      side_effect: node.side_effect,
      high_risk: node.high_risk,
      cost_visibility_required: node.cost_visibility_required,
      recovery_guidance_required: node.recovery_guidance_required,
    }]
  }

  // Container node — recurse into children
  const leaves: RiskLeaf[] = []
  for (const [key, child] of Object.entries(node)) {
    if (child && typeof child === 'object') {
      leaves.push(...collectRiskLeaves(child, prefix ? `${prefix}.${key}` : key))
    }
  }
  return leaves
}

/**
 * Derive system-level risk/intent booleans from the risk_profile tree.
 * This bridges existing packs (which express intent in risk_profile leaf nodes)
 * to the guided question model (which uses business_constraints.* keys).
 *
 * Returns partial answers keyed by guided question IDs.
 */
function deriveFromRiskProfile(riskProfile: Record<string, any>): Record<string, any> {
  const leaves = collectRiskLeaves(riskProfile)
  const derived: Record<string, any> = {}

  const hasIrreversible = leaves.some(l => l.side_effect === 'irreversible')
  const hasCostVisibility = leaves.some(l => l.cost_visibility_required === true)
  const hasRecoveryGuidance = leaves.some(l => l.recovery_guidance_required === true)
  const hasHighRisk = leaves.some(l => l.high_risk === true)

  if (hasIrreversible) derived['has-irreversible'] = true
  if (hasCostVisibility) derived['cost-visibility'] = true
  if (hasRecoveryGuidance) derived['recovery-sensitive'] = true
  if (hasHighRisk) derived['approval-expectation'] = true

  return derived
}

// Re-export collectRiskLeaves for use by summary and hint modules
export { collectRiskLeaves }
export type { RiskLeaf }

/**
 * Read a dot-separated path from a nested object.
 * Returns undefined if path does not exist.
 */
function getNestedValue(obj: Record<string, any>, path: string): any {
  const keys = path.split('.')
  let current: any = obj
  for (const key of keys) {
    if (current === undefined || current === null) return undefined
    current = current[key]
  }
  return current
}

/**
 * Set a dot-separated path in a nested object, creating intermediate objects as needed.
 */
function setNestedValue(obj: Record<string, any>, path: string, value: any): void {
  const keys = path.split('.')
  let target = obj
  for (let i = 0; i < keys.length - 1; i++) {
    if (target[keys[i]] === undefined || target[keys[i]] === null) {
      target[keys[i]] = {}
    }
    target = target[keys[i]]
  }
  target[keys[keys.length - 1]] = value
}

/**
 * Read the current answer for a guided question from the artifact.
 * For questions mapping to a single field, returns that field's value.
 * Falls back to the question's defaultValue if the field is undefined.
 */
export function readAnswerFromArtifact(
  question: GuidedQuestion,
  artifact: Record<string, any>,
): any {
  if (question.fieldMappings.length === 0) return question.defaultValue

  const primaryMapping = question.fieldMappings[0]
  const value = getNestedValue(artifact, primaryMapping.path)
  return value !== undefined ? value : question.defaultValue
}

/**
 * Apply a guided answer to the artifact by writing to all mapped fields.
 * For boolean questions: writes the boolean value.
 * For select questions: writes the selected string value.
 * For text questions: writes the string value.
 *
 * Special case: if answer equals 'not_specified', the field is removed
 * (set to undefined) rather than written, to keep the artifact clean.
 */
export function applyAnswerToArtifact(
  question: GuidedQuestion,
  answer: any,
  artifact: Record<string, any>,
): void {
  for (const mapping of question.fieldMappings) {
    if (answer === 'not_specified' || answer === '' || answer === undefined) {
      // Remove field — do not write placeholder values
      const keys = mapping.path.split('.')
      let target: any = artifact
      for (let i = 0; i < keys.length - 1; i++) {
        if (target[keys[i]] === undefined) return
        target = target[keys[i]]
      }
      delete target[keys[keys.length - 1]]
    } else {
      setNestedValue(artifact, mapping.path, answer)
    }
  }
}

/**
 * Hydrate all guided answers from the current artifact state.
 * Returns a map of question ID → current answer value.
 *
 * Uses bridging logic: when business_constraints.* fields are absent but
 * equivalent intent is expressed in risk_profile leaf nodes (side_effect,
 * cost_visibility_required, recovery_guidance_required, high_risk), the
 * answers are derived from risk_profile instead of showing false defaults.
 */
export function hydrateAnswersFromArtifact(
  artifact: Record<string, any>,
): Record<string, any> {
  const answers: Record<string, any> = {}
  for (const section of GUIDED_SECTIONS) {
    for (const question of section.questions) {
      answers[question.id] = readAnswerFromArtifact(question, artifact)
    }
  }

  // Bridge: derive answers from risk_profile when business_constraints keys are absent
  if (artifact.risk_profile && typeof artifact.risk_profile === 'object') {
    const derived = deriveFromRiskProfile(artifact.risk_profile)
    for (const [qId, value] of Object.entries(derived)) {
      // Only fill in if the mapped field wasn't already set (i.e. answer is still the default)
      if (answers[qId] === false || answers[qId] === undefined) {
        answers[qId] = value
      }
    }
  }

  return answers
}

/**
 * Apply all guided answers to an artifact.
 * This is the inverse of hydrateAnswersFromArtifact.
 */
export function applyAllAnswersToArtifact(
  answers: Record<string, any>,
  artifact: Record<string, any>,
): void {
  for (const section of GUIDED_SECTIONS) {
    for (const question of section.questions) {
      if (question.id in answers) {
        applyAnswerToArtifact(question, answers[question.id], artifact)
      }
    }
  }
}
```

- [ ] **Step 2: Verify the file compiles**

Run: `cd /Users/samirski/Development/ANIP/studio && npx tsc --noEmit src/design/guided/mappings.ts 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add studio/src/design/guided/mappings.ts
git commit -m "feat(studio): add guided-to-artifact bidirectional mapping engine"
```

---

## Task 3: Requirements Summary Generator

Generate a human-readable summary from the current requirements artifact state.

**Files:**
- Create: `studio/src/design/guided/summary.ts`

- [ ] **Step 1: Write the summary generator**

```typescript
// studio/src/design/guided/summary.ts

import { collectRiskLeaves } from './mappings'

/**
 * Generate a plain-language requirements summary from the artifact.
 * Each paragraph covers one aspect. Returns an array of summary paragraphs.
 *
 * Uses the recursive risk_profile walker to derive risk/recovery/cost intent
 * from existing packs that express these in capabilityConfig leaf nodes rather
 * than (or in addition to) business_constraints.* keys.
 */
export function generateRequirementsSummary(
  req: Record<string, any>,
): string[] {
  const parts: string[] = []

  // System identity
  if (req.system) {
    parts.push(
      `${req.system.name} is a ${req.system.domain} system intended for ${req.system.deployment_intent}.`,
    )
  }

  // Scale
  if (req.scale) {
    const shapeLabels: Record<string, string> = {
      embedded_single_process: 'an embedded single-process deployment',
      production_single_service: 'a single production service',
      horizontally_scaled: 'a horizontally scaled deployment',
      control_plane_worker_split: 'a control-plane and worker split',
      multi_service_estate: 'a multi-service estate',
    }
    const shape = shapeLabels[req.scale.shape_preference] ?? req.scale.shape_preference
    const ha = req.scale.high_availability ? ' with high availability' : ''
    parts.push(`It targets ${shape}${ha}.`)
  }

  // Collect risk_profile leaves (recursive walk)
  const riskLeaves = req.risk_profile ? collectRiskLeaves(req.risk_profile) : []
  const hasIrreversibleLeaf = riskLeaves.some(l => l.side_effect === 'irreversible')
  const hasCostVisibilityLeaf = riskLeaves.some(l => l.cost_visibility_required === true)
  const hasRecoveryLeaf = riskLeaves.some(l => l.recovery_guidance_required === true)

  // Risk and side effects — merge business_constraints and risk_profile sources
  const bc = req.business_constraints ?? {}
  const riskParts: string[] = []
  if (bc.spending_possible) riskParts.push('actions that can spend money')
  if (bc.irreversible_actions_present || hasIrreversibleLeaf) riskParts.push('irreversible actions')
  if (riskParts.length > 0) {
    const hasCostVis = bc.cost_visibility_required || hasCostVisibilityLeaf
    const costNote = hasCostVis ? ' Cost visibility is required before acting.' : ''
    parts.push(`The system involves ${riskParts.join(' and ')}.${costNote}`)
  }

  // Risk profile capabilities — recursive walk for high_risk
  if (riskLeaves.length > 0) {
    const highRiskLeaves = riskLeaves.filter(l => l.high_risk === true)
    if (highRiskLeaves.length > 0) {
      parts.push(`High-risk capabilities: ${highRiskLeaves.map(l => l.name).join(', ')}.`)
    }
  }

  // Authority and control
  const authParts: string[] = []
  if (req.permissions?.preflight_discovery) authParts.push('preflight authority discovery')
  if (req.permissions?.grantable_requirements) authParts.push('grantable restrictions')
  if (req.permissions?.restricted_vs_denied) authParts.push('restricted vs denied distinction')
  if (req.auth?.delegation_tokens) authParts.push('delegation tokens')
  if (req.auth?.scoped_authority) authParts.push('scoped authority')
  if (req.auth?.purpose_binding) authParts.push('purpose binding')
  if (authParts.length > 0) {
    parts.push(`Authority posture includes: ${authParts.join(', ')}.`)
  }
  if (bc.approval_expected_for_high_risk) {
    parts.push('Stronger control or approval expectations are expected for high-risk actions.')
  }

  // Recovery — merge business_constraints and risk_profile sources
  const isRecoverySensitive = bc.recovery_sensitive || hasRecoveryLeaf
  if (isRecoverySensitive) {
    const posture = bc.blocked_failure_posture
    if (posture && posture !== 'not_specified') {
      const postureLabels: Record<string, string> = {
        retry_with_backoff: 'automatic retry with backoff',
        escalate_to_human: 'escalation to a human operator',
        fail_safe: 'fail-safe shutdown',
      }
      parts.push(`Recovery is important — the expected posture for blocked or failed work is ${postureLabels[posture] ?? posture}.`)
    } else if (hasRecoveryLeaf && !bc.recovery_sensitive) {
      const recoveryCaps = riskLeaves.filter(l => l.recovery_guidance_required === true).map(l => l.name)
      parts.push(`Recovery guidance is required for: ${recoveryCaps.join(', ')}.`)
    } else {
      parts.push('Recovery expectations are flagged as important but no specific posture is defined.')
    }
  }

  // Audit and traceability
  const auditParts: string[] = []
  if (req.audit?.durable) auditParts.push('durable records')
  if (req.audit?.searchable) auditParts.push('searchable history')
  if (req.audit?.cross_service_reconstruction_required) auditParts.push('cross-service reconstruction')
  if (auditParts.length > 0) {
    parts.push(`Traceability requirements: ${auditParts.join(', ')}.`)
  }

  const lineageParts: string[] = []
  if (req.lineage?.invocation_id) lineageParts.push('invocation tracking')
  if (req.lineage?.task_id) lineageParts.push('task grouping')
  if (req.lineage?.parent_invocation_id) lineageParts.push('parent chain tracking')
  if (req.lineage?.client_reference_id) lineageParts.push('client reference IDs')
  if (req.lineage?.cross_service_continuity_required) lineageParts.push('cross-service continuity')
  if (lineageParts.length > 0) {
    parts.push(`Lineage features: ${lineageParts.join(', ')}.`)
  }

  // Multi-service
  if (req.auth?.service_to_service_handoffs) {
    parts.push('Work crosses service boundaries with explicit handoff expectations.')
  }

  // Services inventory
  if (req.services && req.services.length > 0) {
    const names = req.services.map((s: any) => s.name)
    parts.push(`Service inventory: ${names.join(', ')}.`)
  }

  return parts
}
```

- [ ] **Step 2: Verify the file compiles**

Run: `cd /Users/samirski/Development/ANIP/studio && npx tsc --noEmit src/design/guided/summary.ts 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add studio/src/design/guided/summary.ts
git commit -m "feat(studio): add requirements summary generator derived from artifact state"
```

---

## Task 4: Completeness and Ambiguity Hint Engine

Advisory warnings derived from artifact state — not schema errors, but design-quality hints.

**Files:**
- Create: `studio/src/design/guided/hints.ts`

- [ ] **Step 1: Write the hint engine**

```typescript
// studio/src/design/guided/hints.ts

import type { CompletenessHint } from './types'
import { collectRiskLeaves } from './mappings'

/**
 * Evaluate the current requirements artifact and return advisory hints
 * about completeness and potential ambiguity.
 *
 * These are NOT schema validation errors — they are design-quality warnings.
 * They never modify the artifact.
 *
 * Uses the recursive risk_profile walker so nested multi-service risk trees
 * are fully traversed, not just top-level entries.
 */
export function evaluateCompleteness(req: Record<string, any>): CompletenessHint[] {
  const hints: CompletenessHint[] = []
  const bc = req.business_constraints ?? {}
  const riskLeaves = req.risk_profile ? collectRiskLeaves(req.risk_profile) : []

  // Derive intent from risk_profile leaves
  const hasIrreversibleLeaf = riskLeaves.some(l => l.side_effect === 'irreversible')
  const hasHighRiskLeaf = riskLeaves.some(l => l.high_risk === true)
  const hasCostVisibilityLeaf = riskLeaves.some(l => l.cost_visibility_required === true)

  // 1. Spending or irreversible actions without approval expectations
  if (
    (bc.spending_possible || bc.irreversible_actions_present || hasIrreversibleLeaf) &&
    !bc.approval_expected_for_high_risk && !hasHighRiskLeaf
  ) {
    hints.push({
      id: 'spending-no-approval',
      severity: 'warning',
      message: 'Spending or irreversible actions are indicated, but no approval expectation is captured.',
      explanation:
        'Consider whether high-risk actions should have stronger control or approval expectations. ' +
        'You can set this in the Authority and Approval section.',
      relatedFields: [
        'business_constraints.spending_possible',
        'business_constraints.irreversible_actions_present',
        'business_constraints.approval_expected_for_high_risk',
      ],
    })
  }

  // 2. Multi-service shape without cross-service reconstruction
  if (
    req.scale?.shape_preference === 'multi_service_estate' &&
    !req.audit?.cross_service_reconstruction_required
  ) {
    hints.push({
      id: 'multi-service-no-reconstruction',
      severity: 'warning',
      message: 'Multi-service shape is selected, but cross-service reconstruction is not required.',
      explanation:
        'In multi-service estates, operators typically need to reconstruct what happened across services. ' +
        'Consider enabling cross-service reconstruction in the Audit and Traceability section.',
      relatedFields: [
        'scale.shape_preference',
        'audit.cross_service_reconstruction_required',
      ],
    })
  }

  // 3. Multi-service shape without cross-service continuity
  if (
    req.scale?.shape_preference === 'multi_service_estate' &&
    !req.lineage?.cross_service_continuity_required
  ) {
    hints.push({
      id: 'multi-service-no-continuity',
      severity: 'info',
      message: 'Multi-service shape is selected, but cross-service lineage continuity is not required.',
      explanation:
        'Cross-service continuity preserves invocation chains across service boundaries. ' +
        'This is usually important for debugging in multi-service architectures.',
      relatedFields: [
        'scale.shape_preference',
        'lineage.cross_service_continuity_required',
      ],
    })
  }

  // 4. Durable audit without searchable audit
  if (req.audit?.durable && !req.audit?.searchable) {
    hints.push({
      id: 'durable-not-searchable',
      severity: 'info',
      message: 'Durable audit is required, but searchable audit is not specified.',
      explanation:
        'Durable records are useful for compliance, but without searchability ' +
        'operators may struggle to find specific events. Consider whether search is needed.',
      relatedFields: ['audit.durable', 'audit.searchable'],
    })
  }

  // 5. Recovery-sensitive system without blocked/failure posture
  if (
    bc.recovery_sensitive &&
    (!bc.blocked_failure_posture || bc.blocked_failure_posture === 'not_specified')
  ) {
    hints.push({
      id: 'recovery-no-posture',
      severity: 'warning',
      message: 'System is marked recovery-sensitive, but no blocked/failure posture is specified.',
      explanation:
        'If recovery is important, specify what should happen when work is blocked or fails. ' +
        'Options include retry with backoff, escalation to human, or fail-safe behavior.',
      relatedFields: [
        'business_constraints.recovery_sensitive',
        'business_constraints.blocked_failure_posture',
      ],
    })
  }

  // 6. Service-to-service handoffs without multi-service shape
  if (
    req.auth?.service_to_service_handoffs &&
    req.scale?.shape_preference !== 'multi_service_estate' &&
    req.scale?.shape_preference !== 'control_plane_worker_split'
  ) {
    hints.push({
      id: 'handoffs-not-multi-service',
      severity: 'info',
      message: 'Service-to-service handoffs are enabled, but the deployment shape is not multi-service.',
      explanation:
        'Service handoffs typically apply to multi-service or control-plane architectures. ' +
        'Verify that the deployment shape matches the handoff expectations.',
      relatedFields: [
        'auth.service_to_service_handoffs',
        'scale.shape_preference',
      ],
    })
  }

  // 7. High-risk capabilities in risk_profile without cost visibility (recursive)
  if (riskLeaves.length > 0) {
    if (hasHighRiskLeaf && !bc.cost_visibility_required && !hasCostVisibilityLeaf) {
      hints.push({
        id: 'high-risk-no-cost-visibility',
        severity: 'info',
        message: 'High-risk capabilities are defined, but cost visibility is not required.',
        explanation:
          'High-risk capabilities often involve cost. Consider whether operators should see ' +
          'cost information before high-risk actions are executed.',
        relatedFields: [
          'risk_profile',
          'business_constraints.cost_visibility_required',
        ],
      })
    }
  }

  return hints
}
```

- [ ] **Step 2: Verify the file compiles**

Run: `cd /Users/samirski/Development/ANIP/studio && npx tsc --noEmit src/design/guided/hints.ts 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add studio/src/design/guided/hints.ts
git commit -m "feat(studio): add completeness and ambiguity hint engine for requirements"
```

---

## Task 5: Unit Tests for Guided Logic Modules

Test the mapping engine, hint engine, and summary generator with known artifact states.

**Files:**
- Create: `studio/src/__tests__/guided.test.ts`

- [ ] **Step 1: Write unit tests**

```typescript
// studio/src/__tests__/guided.test.ts

import { describe, it, expect } from 'vitest'
import { GUIDED_SECTIONS } from '../design/guided/questions'
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
    const question = GUIDED_SECTIONS[0].questions.find(q => q.id === 'high-availability')!
    const artifact: Record<string, any> = { scale: { shape_preference: 'production_single_service', high_availability: false } }

    // Apply true
    applyAnswerToArtifact(question, true, artifact)
    expect(artifact.scale.high_availability).toBe(true)

    // Read back
    const answer = readAnswerFromArtifact(question, artifact)
    expect(answer).toBe(true)
  })

  it('round-trips a select answer through the artifact', () => {
    const question = GUIDED_SECTIONS[0].questions.find(q => q.id === 'scale-shape')!
    const artifact: Record<string, any> = { scale: { shape_preference: 'production_single_service', high_availability: false } }

    applyAnswerToArtifact(question, 'multi_service_estate', artifact)
    expect(artifact.scale.shape_preference).toBe('multi_service_estate')

    const answer = readAnswerFromArtifact(question, artifact)
    expect(answer).toBe('multi_service_estate')
  })

  it('removes field when answer is not_specified', () => {
    const question = GUIDED_SECTIONS[3].questions.find(q => q.id === 'blocked-failure-expectation')!
    const artifact: Record<string, any> = { business_constraints: { blocked_failure_posture: 'retry_with_backoff' } }

    applyAnswerToArtifact(question, 'not_specified', artifact)
    expect(artifact.business_constraints.blocked_failure_posture).toBeUndefined()
  })

  it('creates intermediate objects when applying to empty artifact', () => {
    const question = GUIDED_SECTIONS[1].questions.find(q => q.id === 'has-spending')!
    const artifact: Record<string, any> = {}

    applyAnswerToArtifact(question, true, artifact)
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

    // Apply to fresh artifact and verify round-trip
    const fresh: Record<string, any> = {}
    applyAllAnswersToArtifact(answers, fresh)
    expect(fresh.system.name).toBe('Test')
    expect(fresh.scale.high_availability).toBe(true)
    expect(fresh.business_constraints.spending_possible).toBe(true)
    expect(fresh.trust.mode).toBe('signed')
  })

  it('falls back to defaultValue when field is missing', () => {
    const question = GUIDED_SECTIONS[0].questions.find(q => q.id === 'high-availability')!
    const artifact: Record<string, any> = {}
    const answer = readAnswerFromArtifact(question, artifact)
    expect(answer).toBe(false) // defaultValue
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
    // business_constraints.irreversible_actions_present is explicitly false, but since
    // hydrateAnswersFromArtifact reads the mapped field first and gets false,
    // then bridging fills in has-irreversible=true (because false === default)
    // This is correct: the risk_profile says there ARE irreversible actions
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
  it('does not falsely warn about irreversibility when risk_profile expresses it', () => {
    const hints = evaluateCompleteness({
      scale: { shape_preference: 'production_single_service', high_availability: false },
      risk_profile: {
        capabilities: {
          book_flight: { side_effect: 'irreversible', high_risk: true },
        },
      },
    })
    // Has irreversible actions but also has high_risk flag, so no spending-no-approval warning
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
```

- [ ] **Step 2: Run the tests**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run src/__tests__/guided.test.ts`
Expected: All tests pass

- [ ] **Step 3: Fix any failures**

- [ ] **Step 4: Commit**

```bash
git add studio/src/__tests__/guided.test.ts
git commit -m "test(studio): add unit tests for guided mappings, hints, and summary"
```

---

## Task 6: FieldChip Component

Small UI component showing which artifact field(s) a guided answer maps to. Used in guided questions for mapping transparency.

**Files:**
- Create: `studio/src/design/components/FieldChip.vue`

- [ ] **Step 1: Write the FieldChip component**

```vue
<!-- studio/src/design/components/FieldChip.vue -->
<script setup lang="ts">
defineProps<{
  path: string
  label?: string
}>()
</script>

<template>
  <span class="field-chip" :title="path">
    {{ label ?? path }}
  </span>
</template>

<style scoped>
.field-chip {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-family: var(--font-mono, monospace);
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
  white-space: nowrap;
  cursor: default;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/components/FieldChip.vue
git commit -m "feat(studio): add FieldChip component for artifact mapping visibility"
```

---

## Task 7: GuidedQuestion Component

Renders a single guided question with answer input and field mapping chips.

**Files:**
- Create: `studio/src/design/components/GuidedQuestion.vue`

- [ ] **Step 1: Write the GuidedQuestion component**

```vue
<!-- studio/src/design/components/GuidedQuestion.vue -->
<script setup lang="ts">
import type { GuidedQuestion } from '../guided/types'
import FieldChip from './FieldChip.vue'

const props = defineProps<{
  question: GuidedQuestion
  modelValue: any
  showMappings: boolean
  readonly: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: any]
}>()

function onBooleanToggle() {
  if (props.readonly) return
  emit('update:modelValue', !props.modelValue)
}

function onSelectChange(event: Event) {
  if (props.readonly) return
  emit('update:modelValue', (event.target as HTMLSelectElement).value)
}

function onTextInput(event: Event) {
  if (props.readonly) return
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}
</script>

<template>
  <div class="guided-question" :class="{ readonly }">
    <div class="question-header">
      <span class="question-prompt">{{ question.prompt }}</span>
      <span v-if="question.helpText" class="question-help">{{ question.helpText }}</span>
    </div>

    <div class="question-answer">
      <!-- Boolean toggle -->
      <template v-if="question.answerType === 'boolean'">
        <button
          class="toggle-switch"
          :class="{ on: modelValue, off: !modelValue }"
          :disabled="readonly"
          type="button"
          @click="onBooleanToggle"
        >
          {{ modelValue ? 'Yes' : 'No' }}
        </button>
      </template>

      <!-- Select dropdown -->
      <template v-else-if="question.answerType === 'select'">
        <select
          class="form-select"
          :value="modelValue"
          :disabled="readonly"
          @change="onSelectChange"
        >
          <option
            v-for="opt in question.options"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </option>
        </select>
        <span
          v-if="question.options?.find(o => o.value === modelValue)?.description"
          class="option-desc"
        >
          {{ question.options?.find(o => o.value === modelValue)?.description }}
        </span>
      </template>

      <!-- Text input -->
      <template v-else-if="question.answerType === 'text'">
        <input
          class="form-input"
          type="text"
          :value="modelValue"
          :disabled="readonly"
          :placeholder="question.helpText ?? ''"
          @input="onTextInput"
        />
      </template>
    </div>

    <!-- Field mapping chips -->
    <div v-if="showMappings && question.fieldMappings.length > 0" class="field-mappings">
      <FieldChip
        v-for="mapping in question.fieldMappings"
        :key="mapping.path"
        :path="mapping.path"
        :label="mapping.label"
      />
    </div>
  </div>
</template>

<style scoped>
.guided-question {
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.guided-question:last-child {
  border-bottom: none;
}

.question-header {
  margin-bottom: 8px;
}

.question-prompt {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  display: block;
  margin-bottom: 2px;
}

.question-help {
  font-size: 12px;
  color: var(--text-muted);
  display: block;
}

.question-answer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.option-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.field-mappings {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.toggle-switch {
  padding: 4px 14px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-radius: 12px;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition);
  min-width: 60px;
  text-align: center;
  background: transparent;
  color: var(--text-muted);
}

.toggle-switch.on {
  background: rgba(52, 211, 153, 0.12);
  color: var(--success);
  border-color: rgba(52, 211, 153, 0.3);
}

.toggle-switch:disabled {
  opacity: 0.5;
  cursor: default;
}

.toggle-switch:hover:not(:disabled) {
  background: var(--bg-hover);
}

.form-select {
  font-size: 13px;
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
}

.form-select:disabled {
  opacity: 0.5;
  cursor: default;
}

.form-input {
  font-size: 13px;
  padding: 6px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  outline: none;
  width: 100%;
  max-width: 400px;
  box-sizing: border-box;
}

.form-input:disabled {
  opacity: 0.5;
  cursor: default;
}

.readonly .question-prompt {
  color: var(--text-secondary);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/components/GuidedQuestion.vue
git commit -m "feat(studio): add GuidedQuestion component with answer types and field chips"
```

---

## Task 8: GuidedSection Component

A card component grouping related guided questions into a section.

**Files:**
- Create: `studio/src/design/components/GuidedSection.vue`

- [ ] **Step 1: Write the GuidedSection component**

```vue
<!-- studio/src/design/components/GuidedSection.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import type { GuidedSection } from '../guided/types'
import GuidedQuestion from './GuidedQuestion.vue'

const props = defineProps<{
  section: GuidedSection
  answers: Record<string, any>
  showMappings: boolean
  readonly: boolean
}>()

const emit = defineEmits<{
  'update:answer': [questionId: string, value: any]
}>()

const collapsed = ref(false)

function onAnswerUpdate(questionId: string, value: any) {
  emit('update:answer', questionId, value)
}
</script>

<template>
  <div class="guided-section">
    <div class="section-header" @click="collapsed = !collapsed">
      <div class="section-title-row">
        <span class="collapse-icon">{{ collapsed ? '\u25b8' : '\u25be' }}</span>
        <h2 class="section-title">{{ section.title }}</h2>
        <span class="question-count">{{ section.questions.length }} questions</span>
      </div>
      <p class="section-description">{{ section.description }}</p>
    </div>
    <div v-if="!collapsed" class="section-body">
      <GuidedQuestion
        v-for="q in section.questions"
        :key="q.id"
        :question="q"
        :modelValue="answers[q.id]"
        :showMappings="showMappings"
        :readonly="readonly"
        @update:modelValue="onAnswerUpdate(q.id, $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.guided-section {
  background: var(--bg-input, #1a1a2e);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
  margin-bottom: 16px;
  overflow: hidden;
}

.section-header {
  padding: 16px 20px 12px;
  cursor: pointer;
  user-select: none;
}

.section-header:hover {
  background: rgba(255, 255, 255, 0.02);
}

.section-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.collapse-icon {
  font-size: 12px;
  color: var(--text-muted);
  width: 12px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  flex: 1;
}

.question-count {
  font-size: 12px;
  color: var(--text-muted);
}

.section-description {
  font-size: 13px;
  color: var(--text-muted);
  margin: 4px 0 0 20px;
}

.section-body {
  padding: 0 20px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/components/GuidedSection.vue
git commit -m "feat(studio): add GuidedSection card component for grouped questions"
```

---

## Task 9: RequirementsSummary Component

Displays the human-readable requirements summary derived from artifact state.

**Files:**
- Create: `studio/src/design/components/RequirementsSummary.vue`

- [ ] **Step 1: Write the RequirementsSummary component**

```vue
<!-- studio/src/design/components/RequirementsSummary.vue -->
<script setup lang="ts">
import { computed } from 'vue'
import { generateRequirementsSummary } from '../guided/summary'

const props = defineProps<{
  requirements: Record<string, any>
}>()

const paragraphs = computed(() => generateRequirementsSummary(props.requirements))
</script>

<template>
  <div class="requirements-summary" v-if="paragraphs.length > 0">
    <h3 class="summary-title">Requirements Summary</h3>
    <div class="summary-body">
      <p v-for="(para, i) in paragraphs" :key="i" class="summary-paragraph">
        {{ para }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.requirements-summary {
  background: rgba(52, 211, 153, 0.04);
  border: 1px solid rgba(52, 211, 153, 0.15);
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
git add studio/src/design/components/RequirementsSummary.vue
git commit -m "feat(studio): add RequirementsSummary component derived from artifact"
```

---

## Task 10: CompletenessHints Component

Displays advisory hints about requirements quality — expandable explanations.

**Files:**
- Create: `studio/src/design/components/CompletenessHints.vue`

- [ ] **Step 1: Write the CompletenessHints component**

```vue
<!-- studio/src/design/components/CompletenessHints.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import type { CompletenessHint } from '../guided/types'
import FieldChip from './FieldChip.vue'

defineProps<{
  hints: CompletenessHint[]
}>()

const expandedIds = ref<Set<string>>(new Set())

function toggleExpanded(id: string) {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id)
  } else {
    expandedIds.value.add(id)
  }
}
</script>

<template>
  <div class="completeness-hints" v-if="hints.length > 0">
    <h3 class="hints-title">
      Design Hints
      <span class="hint-count">{{ hints.length }}</span>
    </h3>
    <div
      v-for="hint in hints"
      :key="hint.id"
      class="hint-item"
      :class="hint.severity"
    >
      <div class="hint-header" @click="toggleExpanded(hint.id)">
        <span class="hint-icon">{{ hint.severity === 'warning' ? '\u26a0' : '\u2139' }}</span>
        <span class="hint-message">{{ hint.message }}</span>
        <span class="expand-icon">{{ expandedIds.has(hint.id) ? '\u25be' : '\u25b8' }}</span>
      </div>
      <div v-if="expandedIds.has(hint.id)" class="hint-detail">
        <p class="hint-explanation">{{ hint.explanation }}</p>
        <div class="hint-fields">
          <FieldChip
            v-for="field in hint.relatedFields"
            :key="field"
            :path="field"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.completeness-hints {
  margin-bottom: 16px;
}

.hints-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.hint-count {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 1px 8px;
}

.hint-item {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 6px);
  margin-bottom: 6px;
  overflow: hidden;
}

.hint-item.warning {
  border-color: rgba(251, 191, 36, 0.3);
  background: rgba(251, 191, 36, 0.04);
}

.hint-item.info {
  border-color: rgba(96, 165, 250, 0.3);
  background: rgba(96, 165, 250, 0.04);
}

.hint-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
}

.hint-header:hover {
  background: rgba(255, 255, 255, 0.02);
}

.hint-icon {
  font-size: 14px;
  flex-shrink: 0;
  margin-top: 1px;
}

.hint-message {
  font-size: 13px;
  color: var(--text-secondary);
  flex: 1;
}

.expand-icon {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.hint-detail {
  padding: 0 14px 12px 36px;
}

.hint-explanation {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
  margin: 0 0 8px;
}

.hint-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/components/CompletenessHints.vue
git commit -m "feat(studio): add CompletenessHints component with expandable explanations"
```

---

## Task 11: Store Updates — Guided Mode State

Add `requirementsMode` to the design store and wire guided answer hydration.

**Files:**
- Modify: `studio/src/design/store.ts`
- Modify: `studio/src/design/types.ts`

- [ ] **Step 1: Add RequirementsMode type and fix business_constraints type in types.ts**

Add to `studio/src/design/types.ts`:
```typescript
export type RequirementsMode = 'guided' | 'advanced'
```

Also fix the `business_constraints` type in the `Requirements` interface to match the schema (which allows boolean, string, or number values — not just booleans):
```typescript
// Change from:
business_constraints?: Record<string, boolean>
// To:
business_constraints?: Record<string, boolean | string | number>
```

- [ ] **Step 2: Add guided state to store.ts**

Add the following imports to the top of `store.ts`:
```typescript
import type { RequirementsMode } from './types'
import type { CompletenessHint } from './guided/types'
import { hydrateAnswersFromArtifact, applyAnswerToArtifact } from './guided/mappings'
import { evaluateCompleteness } from './guided/hints'
import { GUIDED_SECTIONS } from './guided/questions'
```

Add state properties to the `DesignState` interface:
```typescript
requirementsMode: RequirementsMode
guidedAnswers: Record<string, any>
completenessHints: CompletenessHint[]
showFieldMappings: boolean
```

Add default values to the reactive state:
```typescript
requirementsMode: 'guided',
guidedAnswers: {},
completenessHints: [],
showFieldMappings: false,
```

- [ ] **Step 3: Add guided mode functions to store.ts**

```typescript
/** Toggle between guided and advanced requirements mode.
 *  Re-hydrates guided answers from the current draft when switching to guided. */
export function setRequirementsMode(mode: RequirementsMode): void {
  designStore.requirementsMode = mode

  if (mode === 'guided' && designStore.draftRequirements) {
    designStore.guidedAnswers = hydrateAnswersFromArtifact(designStore.draftRequirements)
    designStore.completenessHints = evaluateCompleteness(designStore.draftRequirements)
  }
}

/** Toggle field mapping chip visibility */
export function toggleFieldMappings(): void {
  designStore.showFieldMappings = !designStore.showFieldMappings
}

/** Update a single guided answer and apply it to the draft artifact */
export function updateGuidedAnswer(questionId: string, value: any): void {
  designStore.guidedAnswers[questionId] = value

  // Find the question definition and apply to draft
  for (const section of GUIDED_SECTIONS) {
    const question = section.questions.find(q => q.id === questionId)
    if (question && designStore.draftRequirements) {
      applyAnswerToArtifact(question, value, designStore.draftRequirements)
      break
    }
  }

  // Re-evaluate completeness hints
  if (designStore.draftRequirements) {
    designStore.completenessHints = evaluateCompleteness(designStore.draftRequirements)
  }
}
```

- [ ] **Step 4: Wire hydration into startEditing()**

In `startEditing()`, after the existing draft setup (after `designStore.editState = 'draft'`), add:
```typescript
// Hydrate guided answers from the draft artifact
designStore.guidedAnswers = hydrateAnswersFromArtifact(designStore.draftRequirements!)
designStore.completenessHints = evaluateCompleteness(designStore.draftRequirements!)
```

- [ ] **Step 5: Clear guided state in discardEdits()**

In `discardEdits()`, add:
```typescript
designStore.guidedAnswers = {}
designStore.completenessHints = []
```

- [ ] **Step 6: Add completeness hint re-evaluation to the existing draft watcher**

Update the existing `watch()` at the bottom of store.ts to also re-evaluate completeness hints:
```typescript
watch(
  () => [designStore.draftRequirements, designStore.draftScenario, designStore.draftDeclaredSurfaces],
  () => {
    if (designStore.editState !== 'draft') return
    if (validateTimer) clearTimeout(validateTimer)
    validateTimer = setTimeout(() => {
      validateDraft()
      if (designStore.draftRequirements) {
        designStore.completenessHints = evaluateCompleteness(designStore.draftRequirements)
      }
    }, 300)
  },
  { deep: true },
)
```

- [ ] **Step 7: Verify the store compiles**

Run: `cd /Users/samirski/Development/ANIP/studio && npx tsc --noEmit src/design/store.ts 2>&1 | head -20`
Expected: No errors

- [ ] **Step 8: Commit**

```bash
git add studio/src/design/store.ts studio/src/design/types.ts
git commit -m "feat(studio): add guided mode state, answer hydration, and hint evaluation to store"
```

---

## Task 12: RequirementsView — Mode Toggle and Guided Content Integration

Add the Guided/Advanced mode toggle to RequirementsView. The view provides shared chrome (title, toolbar, mode toggle) and conditionally renders guided sections or the existing advanced editor. Also fix pre-existing bugs in the advanced editor.

**Files:**
- Modify: `studio/src/views/RequirementsView.vue`

- [ ] **Step 1: Add imports for guided components and store functions**

Add to the `<script setup>` in `RequirementsView.vue`:
```typescript
import { designStore, setActivePack, updateDraftField, setRequirementsMode, updateGuidedAnswer } from '../design/store'
import { GUIDED_SECTIONS } from '../design/guided/questions'
import { hydrateAnswersFromArtifact } from '../design/guided/mappings'
import { evaluateCompleteness } from '../design/guided/hints'
import GuidedSection from '../design/components/GuidedSection.vue'
import RequirementsSummary from '../design/components/RequirementsSummary.vue'
import CompletenessHints from '../design/components/CompletenessHints.vue'
```

Add a computed property for guided answers that works in both read and edit mode:
```typescript
const guidedAnswers = computed(() => {
  if (isEditing.value) return designStore.guidedAnswers
  return hydrateAnswersFromArtifact(req.value ?? {})
})

const completenessHints = computed(() => {
  if (isEditing.value) return designStore.completenessHints
  return evaluateCompleteness(req.value ?? {})
})
```

- [ ] **Step 2: Add mode toggle and guided content to the template**

After the page title and before EditorToolbar, add:
```html
<!-- Mode toggle -->
<div class="mode-toggle">
  <button
    class="mode-btn"
    :class="{ active: designStore.requirementsMode === 'guided' }"
    @click="setRequirementsMode('guided')"
    type="button"
  >
    Guided
  </button>
  <button
    class="mode-btn"
    :class="{ active: designStore.requirementsMode === 'advanced' }"
    @click="setRequirementsMode('advanced')"
    type="button"
  >
    Advanced
  </button>
</div>
```

After EditorToolbar, add guided mode content (before the existing advanced sections):
```html
<!-- Guided mode -->
<template v-if="designStore.requirementsMode === 'guided'">
  <RequirementsSummary :requirements="req" />
  <CompletenessHints :hints="completenessHints" />

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

  <GuidedSection
    v-for="section in GUIDED_SECTIONS"
    :key="section.id"
    :section="section"
    :answers="guidedAnswers"
    :showMappings="designStore.showFieldMappings"
    :readonly="!isEditing"
    @update:answer="updateGuidedAnswer"
  />
</template>
```

Wrap all existing advanced sections (System through Scale) in:
```html
<template v-else>
  <!-- ... all existing sections ... -->
</template>
```

- [ ] **Step 3: Fix pre-existing bugs in the advanced editor**

Fix the trust mode select (line ~162) — add the missing `attested` option:
```html
<select class="form-select" :value="req.trust.mode" @change="setTrustMode">
  <option value="unsigned">unsigned</option>
  <option value="signed">signed</option>
  <option value="anchored">anchored</option>
  <option value="attested">attested</option>
</select>
```

Fix the scale shape_preference select (line ~348) — use correct schema enum values:
```html
<select
  class="form-select"
  :value="req.scale?.shape_preference ?? ''"
  @change="setScaleShapePreference"
>
  <option value="">-- select --</option>
  <option value="embedded_single_process">embedded_single_process</option>
  <option value="production_single_service">production_single_service</option>
  <option value="horizontally_scaled">horizontally_scaled</option>
  <option value="control_plane_worker_split">control_plane_worker_split</option>
  <option value="multi_service_estate">multi_service_estate</option>
</select>
```

Fix the business constraints display (line ~330) — handle string values, not just booleans:
```html
<template v-for="key in businessConstraintKeys" :key="key">
  <dt>{{ key }}</dt>
  <dd>{{ typeof req.business_constraints![key] === 'boolean' ? (req.business_constraints![key] ? 'Yes' : 'No') : req.business_constraints![key] }}</dd>
</template>
```

- [ ] **Step 4: Add mode toggle and mapping toggle styles**

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
```

- [ ] **Step 5: Verify the build compiles**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -30`
Expected: No errors (or only pre-existing warnings)

- [ ] **Step 6: Commit**

```bash
git add studio/src/views/RequirementsView.vue
git commit -m "feat(studio): add Guided/Advanced mode toggle on RequirementsView and fix pre-existing bugs"
```

---

## Task 13: EditorToolbar Hint Badge

Add completeness hint count to EditorToolbar alongside validation error count.

**Files:**
- Modify: `studio/src/design/components/EditorToolbar.vue`

- [ ] **Step 1: Add hint count badge to EditorToolbar**

In the EditorToolbar script setup, add:
```typescript
import { designStore } from '../store'

const hintCount = computed(() => designStore.completenessHints.length)
```

Add a hint badge in the toolbar status area (next to the validation status button):

```html
<span v-if="hintCount > 0" class="hint-badge" :title="`${hintCount} design hint(s)`">
  {{ hintCount }} hint{{ hintCount === 1 ? '' : 's' }}
</span>
```

```css
.hint-badge {
  font-size: 11px;
  font-weight: 600;
  color: rgba(251, 191, 36, 0.9);
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.25);
  border-radius: 10px;
  padding: 2px 10px;
}
```

- [ ] **Step 2: Verify the build compiles**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add studio/src/design/components/EditorToolbar.vue
git commit -m "feat(studio): add completeness hint badge to EditorToolbar"
```

---

## Task 14: End-to-End Integration Test

Verify the complete guided flow works — start editing, answer questions in guided mode, switch to advanced mode, verify artifact fields are set, switch back, verify answers are preserved.

**Files:**
- No new files — manual verification via dev server

- [ ] **Step 1: Start the dev server**

Run: `cd /Users/samirski/Development/ANIP/studio && npm run dev`

- [ ] **Step 2: Manual verification checklist**

Verify each of these in the browser:

1. Navigate to a requirements pack
2. Mode toggle shows "Guided" and "Advanced" buttons
3. Guided mode renders sections as collapsible cards with read-only values
4. Requirements Summary shows at the top, derived from artifact
5. Click "Start Editing" — guided questions become interactive
6. Answer a boolean question (e.g., "Can any action spend money?" → Yes)
7. Verify the field mapping chip shows `business_constraints.spending_possible` when "Show technical field mappings" is checked
8. Switch to "Advanced" mode — verify `business_constraints.spending_possible` is set to `true`
9. Switch back to "Guided" — verify the answer is still "Yes"
10. Trigger a completeness hint (e.g., enable spending without approval expectation)
11. Verify the hint appears with expandable explanation
12. Verify the EditorToolbar shows hint count badge
13. Verify completeness hints also appear in non-editing (read) mode
14. Click "Discard" — verify all state resets
15. Verify advanced mode fixes: trust `attested` option present, correct scale enum values, string business_constraints render properly

- [ ] **Step 3: Run unit tests**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run`
Expected: All tests pass including the new guided tests

- [ ] **Step 4: Run type-check and lint**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit && npm run lint 2>&1 | tail -20`
Expected: No errors

- [ ] **Step 5: Fix any issues found**

Address any rendering, state, or styling issues discovered during testing.

- [ ] **Step 6: Commit any fixes**

```bash
git add -A
git commit -m "fix(studio): address integration issues in guided requirements flow"
```

---

## Task 15: Sync Embedded Assets

Run `sync.sh` to rebuild the embedded Studio assets used by runtime packages.

**Files:**
- Modify: `studio/sync.sh` output (embedded assets in runtime packages)

- [ ] **Step 1: Run sync**

Run: `cd /Users/samirski/Development/ANIP/studio && bash sync.sh`
Expected: Build succeeds and assets are copied to runtime packages

- [ ] **Step 2: Commit synced assets**

```bash
git add -A
git commit -m "build(studio): sync embedded assets after V3 Slice 2 guided requirements"
```
