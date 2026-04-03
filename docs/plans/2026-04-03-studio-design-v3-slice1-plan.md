# ANIP Studio: Design V3 Slice 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make requirements, scenarios, and proposal surface declarations safely editable in Studio, backed by schema validation and structured `declared_surfaces` replacing the evaluator's text-matching heuristic.

**Architecture:** Add `declared_surfaces` to proposal schema + update evaluator. Expand scenario schema categories to 5. Add `ajv` for in-browser JSON Schema validation. Build form-based editors for requirements (structured sections + key-value editor for flexible parts), scenarios, and proposal declared_surfaces. YAML import/export with round-trip safety. Diff tracking for draft state.

**Tech Stack:** Vue 3, TypeScript, ajv (JSON Schema validation), js-yaml, Python (evaluator)

**Proposal:** `docs/proposals/anip-studio-design-v3-slice1-proposal.md`

---

## File Structure

```
# Schemas
tooling/schemas/proposal.schema.json              # MODIFY: add declared_surfaces
tooling/schemas/scenario.schema.json              # MODIFY: expand category enum (add recovery, cross_service)

# Evaluator
tooling/bin/anip_design_validate.py               # MODIFY: prefer declared_surfaces over text heuristic

# Example packs
tooling/examples/*/proposal.yaml                  # MODIFY: add declared_surfaces to all 13 packs

# Evaluator tests
tooling/tests/test_evaluator.py                   # MODIFY: add declared_surfaces preference tests

# Studio dependencies
studio/package.json                               # MODIFY: add ajv as runtime dep, move js-yaml to runtime

# Studio types + store
studio/src/design/types.ts                        # MODIFY: add DeclaredSurfaces, ValidationError, EditState
studio/src/design/store.ts                        # MODIFY: add draft state, dirty tracking, validation

# Schema data for browser validation
studio/src/design/schemas.ts                      # CREATE: bundled JSON schemas for ajv validation

# Import/Export
studio/src/design/io.ts                           # CREATE: YAML import/export + file picker

# Diff utility
studio/src/design/diff.ts                         # CREATE: structured field diff

# Editor toolbar
studio/src/design/components/EditorToolbar.vue    # CREATE: dirty indicator, validate, export, discard
studio/src/design/components/KeyValueEditor.vue   # CREATE: dynamic key-value editor for flexible sections
studio/src/design/components/StringListEditor.vue  # CREATE: editable string list (add/remove/reorder)

# Views
studio/src/views/RequirementsView.vue             # MODIFY: add form editing per section
studio/src/views/ScenarioDetailView.vue           # MODIFY: add form editing
studio/src/views/ProposalView.vue                 # MODIFY: add declared_surfaces toggle section

# Regenerated packs
studio/src/design/data/packs.generated.ts         # UPDATE: regenerate with declared_surfaces
```

---

## Task 1: Schema Updates + Evaluator

**Files:**
- Modify: `tooling/schemas/proposal.schema.json`
- Modify: `tooling/schemas/scenario.schema.json`
- Modify: `tooling/bin/anip_design_validate.py`
- Modify: `tooling/tests/test_evaluator.py`

- [ ] **Step 1: Add `declared_surfaces` to proposal schema**

In `tooling/schemas/proposal.schema.json`, add inside `proposal.properties`:

```json
"declared_surfaces": {
  "type": "object",
  "description": "Machine-readable declaration of which ANIP semantic surfaces are present in this design. When present, the evaluator prefers this over heuristic text inference.",
  "additionalProperties": false,
  "properties": {
    "budget_enforcement": { "type": "boolean", "default": false },
    "binding_requirements": { "type": "boolean", "default": false },
    "authority_posture": { "type": "boolean", "default": false },
    "recovery_class": { "type": "boolean", "default": false },
    "refresh_via": { "type": "boolean", "default": false },
    "verify_via": { "type": "boolean", "default": false },
    "followup_via": { "type": "boolean", "default": false },
    "cross_service_handoff": { "type": "boolean", "default": false },
    "cross_service_continuity": { "type": "boolean", "default": false },
    "cross_service_reconstruction": { "type": "boolean", "default": false }
  }
}
```

- [ ] **Step 2: Expand scenario category enum**

In `tooling/schemas/scenario.schema.json`, change the `category` enum from:
```json
["safety", "orchestration", "observability"]
```
to:
```json
["safety", "recovery", "orchestration", "cross_service", "observability"]
```

- [ ] **Step 3: Update evaluator to prefer declared_surfaces**

In `tooling/bin/anip_design_validate.py`, modify `_extract_proposal_surfaces()`:

```python
def _extract_proposal_surfaces(proposal: dict[str, Any]) -> dict[str, bool]:
    # V3: prefer structured declared_surfaces when present.
    # IMPORTANT: return the SAME key names the existing evaluator consumers expect.
    # Do NOT rename keys — only change how values are derived.
    declared = proposal.get("declared_surfaces")
    if declared and isinstance(declared, dict):
        return {
            # Same keys as V2 heuristic output — consumers unchanged
            "budget_enforcement": declared.get("budget_enforcement", False),
            "binding": declared.get("binding_requirements", False),
            "authority_posture": declared.get("authority_posture", False),
            "recovery_class": declared.get("recovery_class", False),
            "refresh_via": declared.get("refresh_via", False),
            "verify_via": declared.get("verify_via", False),
            "followup_via": declared.get("followup_via", False),
            "cross_service_hints": declared.get("cross_service_handoff", False),
            "upstream_service": declared.get("cross_service_continuity", False),
            "cross_service_reconstruction": declared.get("cross_service_reconstruction", False),
            "audit": True,  # always true if structured declarations present
            "lineage": True,
        }
    # V2 fallback: heuristic text matching
    # ... existing code unchanged ...
```

**IMPORTANT:** The returned dict uses the SAME key names as the V2 heuristic path (`budget_enforcement`, `refresh_via`, `cross_service_hints`, `audit`, `lineage`, etc.). No key renames. Only the value derivation changes — from text scanning to boolean lookup. All downstream consumer code in `evaluate_safety`, `evaluate_orchestration`, `evaluate_cross_service`, etc. works without changes.

- [ ] **Step 4: Add evaluator tests for declared_surfaces**

In `tooling/tests/test_evaluator.py`, add:
- `test_declared_surfaces_preferred_over_text` — proposal with declared_surfaces produces different (more accurate) result than same proposal text without it
- `test_declared_surfaces_false_produces_glue` — declared_surfaces with `refresh_via: false` produces glue noting the gap
- `test_declared_surfaces_absent_falls_back_to_text` — no declared_surfaces → V2 heuristic behavior unchanged
- `test_declared_surfaces_all_true_credits_correctly` — all surfaces true → maximum credit in handled_by_anip

Run: `python3 -m pytest tooling/tests/ -v`

- [ ] **Step 5: Commit**

```bash
git add tooling/
git commit -m "feat: add declared_surfaces to proposal schema, evaluator prefers structured declarations"
```

---

## Task 2: Migrate All 13 Packs + Regenerate

**Files:**
- Modify: `tooling/examples/*/proposal.yaml` (all 13)
- Update: `studio/src/design/data/packs.generated.ts`

- [ ] **Step 1: Add declared_surfaces to all 13 packs**

For each pack, read its `proposal.yaml` and add `declared_surfaces` based on what the proposal actually declares in its text/components. Use the evaluator's existing `_extract_proposal_surfaces` heuristic output as a guide, then set each boolean honestly.

Write a migration script or do it manually. Each pack gets a `declared_surfaces` block at the end of its `proposal` section.

- [ ] **Step 2: Re-evaluate all packs**

```bash
for pack in tooling/examples/*/; do
  [ -f "$pack/requirements.yaml" ] && [ -f "$pack/proposal.yaml" ] && [ -f "$pack/scenario.yaml" ] || continue
  python3 tooling/bin/anip_design_validate.py \
    --requirements "$pack/requirements.yaml" \
    --proposal "$pack/proposal.yaml" \
    --scenario "$pack/scenario.yaml" \
    --evaluation-out "$pack/evaluation.yaml"
done
```

- [ ] **Step 3: Regenerate Studio packs**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build:packs
```

- [ ] **Step 4: Commit**

```bash
git add tooling/examples/ studio/src/design/data/packs.generated.ts
git commit -m "feat: add declared_surfaces to all 13 packs, re-evaluate with structured declarations"
```

---

## Task 3: Studio Dependencies + Schema Bundle + Types

**Files:**
- Modify: `studio/package.json`
- Create: `studio/src/design/schemas.ts`
- Modify: `studio/src/design/types.ts`

- [ ] **Step 1: Add ajv as runtime dep, move js-yaml to runtime**

```bash
cd /Users/samirski/Development/ANIP/studio && npm install ajv js-yaml
```

`js-yaml` is already a devDependency — this moves it to dependencies. `ajv` is new.

- [ ] **Step 2: Create schema bundle**

Create `studio/src/design/schemas.ts` that imports the 3 truth-layer schemas as JSON and exports compiled ajv validators:

```typescript
import Ajv from 'ajv'
import requirementsSchema from '../../../tooling/schemas/requirements.schema.json'
import proposalSchema from '../../../tooling/schemas/proposal.schema.json'
import scenarioSchema from '../../../tooling/schemas/scenario.schema.json'

const ajv = new Ajv({ allErrors: true })

export const validateRequirements = ajv.compile(requirementsSchema)
export const validateProposal = ajv.compile(proposalSchema)
export const validateScenario = ajv.compile(scenarioSchema)
```

Note: Vite supports JSON imports natively. If TypeScript complains about JSON imports, add `"resolveJsonModule": true` to `tsconfig.json`.

- [ ] **Step 3: Update types**

In `studio/src/design/types.ts`, add:

```typescript
export interface DeclaredSurfaces {
  budget_enforcement: boolean
  binding_requirements: boolean
  authority_posture: boolean
  recovery_class: boolean
  refresh_via: boolean
  verify_via: boolean
  followup_via: boolean
  cross_service_handoff: boolean
  cross_service_continuity: boolean
  cross_service_reconstruction: boolean
}

export interface ValidationError {
  path: string
  message: string
}

export type EditState = 'read' | 'draft' | 'exported'
```

- [ ] **Step 4: Commit**

```bash
git add studio/package.json studio/package-lock.json studio/src/design/schemas.ts studio/src/design/types.ts
git commit -m "feat(studio): add ajv schema validation + DeclaredSurfaces types"
```

---

## Task 4: Store — Draft State, Validation, Dirty Tracking

**Files:**
- Modify: `studio/src/design/store.ts`

- [ ] **Step 1: Extend design store**

Add to the reactive store:

```typescript
// V3 Slice 1 — editing state
draftRequirements: null as Record<string, any> | null,
draftScenario: null as Record<string, any> | null,
draftDeclaredSurfaces: null as DeclaredSurfaces | null,
originalRequirements: null as Record<string, any> | null,
originalScenario: null as Record<string, any> | null,
editState: 'read' as EditState,
validationErrors: [] as ValidationError[],
```

Add functions:
- `startEditing()` — copies current pack data into draft + original, sets editState to 'draft'
- `discardEdits()` — clears drafts, resets to 'read'
- `isDirty()` — compares draft against original, returns boolean
- `getChangedFields()` — returns list of changed field paths
- `validateDraft()` — runs ajv against draft, populates validationErrors
- `updateDraftRequirements(path, value)` — set a field in draft requirements
- `updateDraftScenario(path, value)` — set a field in draft scenario
- `updateDeclaredSurface(key, value)` — toggle a declared surface
- `composeDraftProposal()` — merges `draftDeclaredSurfaces` into the original pack proposal and returns a complete proposal object. This is used for both live validation AND export:
  ```typescript
  function composeDraftProposal(): Record<string, any> | null {
    const pack = getActivePack()
    if (!pack?.proposal) return null
    const base = structuredClone(pack.proposal)
    if (designStore.draftDeclaredSurfaces) {
      base.proposal.declared_surfaces = { ...designStore.draftDeclaredSurfaces }
    }
    return base
  }
  ```
- Update `runLiveValidation()` to use `composeDraftProposal()` instead of the static pack proposal
- Export YAML for proposal uses `composeDraftProposal()` to include current toggle state

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/store.ts
git commit -m "feat(studio): add draft state, validation, dirty tracking to design store"
```

---

## Task 5: Import/Export + Diff Utilities

**Files:**
- Create: `studio/src/design/io.ts`
- Create: `studio/src/design/diff.ts`

- [ ] **Step 1: Create YAML import/export**

`studio/src/design/io.ts`:

```typescript
import yaml from 'js-yaml'

export function parseYaml(text: string): Record<string, any> {
  return yaml.load(text) as Record<string, any>
}

export function dumpYaml(data: Record<string, any>): string {
  return yaml.dump(data, { sortKeys: false, lineWidth: -1 })
}

export function downloadYaml(data: Record<string, any>, filename: string) {
  const text = dumpYaml(data)
  const blob = new Blob([text], { type: 'text/yaml' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function copyYamlToClipboard(data: Record<string, any>) {
  navigator.clipboard.writeText(dumpYaml(data))
}

export async function importYamlFile(): Promise<Record<string, any>> {
  return new Promise((resolve, reject) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.yaml,.yml'
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return reject(new Error('No file selected'))
      const text = await file.text()
      resolve(parseYaml(text))
    }
    input.click()
  })
}
```

- [ ] **Step 2: Create structured diff utility**

`studio/src/design/diff.ts`:

```typescript
export interface FieldChange {
  path: string
  before: any
  after: any
}

export function diffObjects(original: Record<string, any>, current: Record<string, any>, prefix = ''): FieldChange[] {
  const changes: FieldChange[] = []
  const allKeys = new Set([...Object.keys(original), ...Object.keys(current)])

  for (const key of allKeys) {
    const path = prefix ? `${prefix}.${key}` : key
    const a = original[key]
    const b = current[key]

    if (typeof a === 'object' && a !== null && typeof b === 'object' && b !== null && !Array.isArray(a) && !Array.isArray(b)) {
      changes.push(...diffObjects(a, b, path))
    } else if (JSON.stringify(a) !== JSON.stringify(b)) {
      changes.push({ path, before: a, after: b })
    }
  }
  return changes
}
```

- [ ] **Step 3: Commit**

```bash
git add studio/src/design/io.ts studio/src/design/diff.ts
git commit -m "feat(studio): add YAML import/export + structured diff utility"
```

---

## Task 6: Shared Editor Components

**Files:**
- Create: `studio/src/design/components/EditorToolbar.vue`
- Create: `studio/src/design/components/KeyValueEditor.vue`
- Create: `studio/src/design/components/StringListEditor.vue`

- [ ] **Step 1: EditorToolbar**

Persistent toolbar for editor views:
- Dirty indicator: "N changes" badge (or "No changes")
- Validation status: green checkmark or red "N errors" with expandable error list
- Export YAML button (downloads file)
- Copy YAML button (clipboard)
- Discard changes button (resets to original)

Props: none (reads from designStore directly).

- [ ] **Step 2: KeyValueEditor**

Dynamic key-value editor for flexible schema sections (risk_profile, business_constraints):
- Shows existing key-value pairs
- Add new key + value (with type selector: string, number, boolean)
- Edit existing values inline
- Delete keys
- For nested objects (risk_profile capabilities), renders recursively

Props: `modelValue: Record<string, any>`, emits `update:modelValue`.

- [ ] **Step 3: StringListEditor**

Editable string list for expected_behavior, expected_anip_support, etc.:
- Shows items as editable text inputs
- Add new item button
- Delete item button per row
- Drag to reorder (optional — simple up/down buttons acceptable for Slice 1)

Props: `modelValue: string[]`, emits `update:modelValue`.

- [ ] **Step 4: Commit**

```bash
git add studio/src/design/components/
git commit -m "feat(studio): add EditorToolbar, KeyValueEditor, StringListEditor components"
```

---

## Task 7: Requirements Editor

**Files:**
- Modify: `studio/src/views/RequirementsView.vue`

- [ ] **Step 1: Make sections editable**

Read the current RequirementsView.vue. Transform each read-only section into an edit/view toggle:

- **System** — text inputs for name, domain, deployment_intent
- **Transports** — toggle switches for http, stdio, grpc
- **Trust** — dropdown for mode, toggle for checkpoints
- **Auth** — toggles for delegation_tokens, purpose_binding, scoped_authority
- **Permissions** — toggles for preflight_discovery, restricted_vs_denied
- **Audit** — toggles for durable, searchable
- **Lineage** — toggles for invocation_id, client_reference_id, task_id, parent_invocation_id
- **Risk Profile** — KeyValueEditor component (dynamic, preserves unknown keys)
- **Business Constraints** — KeyValueEditor component (dynamic, preserves unknown keys)
- **Scale** — dropdown for shape_preference, toggle for high_availability

Each section has inline edit mode. Changes update `designStore.draftRequirements`.

Add EditorToolbar at the top of the view.

- [ ] **Step 2: Wire validation**

On every change, call `designStore.validateDraft()`. Show validation errors inline next to affected fields.

- [ ] **Step 3: Build and verify**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add studio/src/views/RequirementsView.vue
git commit -m "feat(studio): make Requirements view editable with form sections + validation"
```

---

## Task 8: Scenario Editor

**Files:**
- Modify: `studio/src/views/ScenarioDetailView.vue`

- [ ] **Step 1: Make fields editable**

- **Name** — text input (validated against `^[a-z0-9_\-]+$`)
- **Category** — dropdown with 5 options (safety, recovery, orchestration, cross_service, observability)
- **Narrative** — textarea
- **Context** — KeyValueEditor (dynamic, preserves all keys)
- **Expected Behavior** — StringListEditor
- **Expected ANIP Support** — StringListEditor

Changes update `designStore.draftScenario`.

Add EditorToolbar at the top.

- [ ] **Step 2: Wire validation**

- [ ] **Step 3: Commit**

```bash
git add studio/src/views/ScenarioDetailView.vue
git commit -m "feat(studio): make Scenario view editable with form fields + validation"
```

---

## Task 9: Proposal Declared Surfaces Editor

**Files:**
- Modify: `studio/src/views/ProposalView.vue`

- [ ] **Step 1: Add declared_surfaces toggle grid**

At the top of ProposalView, add a "Declared Surfaces" section with 10 toggle switches:

Each toggle shows:
- Surface name (human-readable label)
- Short description
- On/Off state from `designStore.draftDeclaredSurfaces`

Toggling updates the store. Rest of proposal remains read-only.

Add EditorToolbar.

- [ ] **Step 2: Commit**

```bash
git add studio/src/views/ProposalView.vue
git commit -m "feat(studio): add declared_surfaces toggle editor to Proposal view"
```

---

## Task 10: Build + Polish + Tests

- [ ] **Step 1: Full Studio build**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build
```

- [ ] **Step 2: Verify round-trip**

Load a pack → edit requirements → export YAML → re-import → verify identical structure. Repeat for scenario.

- [ ] **Step 3: Verify declared_surfaces evaluation**

Load a pack → toggle declared_surfaces → run live validation → verify evaluation changes based on toggles.

- [ ] **Step 4: Verify diff**

Edit fields → verify changes panel shows correct before/after.

- [ ] **Step 5: Run all existing tests**

```bash
python3 -m pytest tooling/tests/ -v
cd studio && npx vitest run
```

- [ ] **Step 6: Commit**

```bash
git add studio/
git commit -m "feat(studio): Design V3 Slice 1 complete — authoring foundation"
```
