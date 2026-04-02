# ANIP Studio: Design V1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first real `ANIP Studio: Design` vertical slice — scenario browsing, guided requirements/proposal viewing, and Glue Gap Analysis rendering, backed by bundled example packs from `tooling/examples/`.

**Architecture:** Extend the existing Vue 3 + Vite Studio app with a top-level Inspect/Design mode switcher. Design mode uses a separate sidebar, views, and data store. Example packs are converted from YAML to JSON at build time by a Node script, then loaded as static imports. No backend required for V1.

**Tech Stack:** Vue 3, TypeScript, Vite, vue-router, js-yaml (build-time only)

**Proposal:** `docs/proposals/anip-studio-design-v1-proposal.md`

---

## File Structure

```
# Build-time pack converter
studio/scripts/build-design-packs.ts         # CREATE: scan tooling/examples/*, convert YAML → JSON

# Generated data (gitignored, built fresh)
studio/src/design/data/packs.generated.ts    # AUTO-GENERATED: pack index + all pack data

# Design store
studio/src/design/store.ts                   # CREATE: reactive design store (active pack, loaded artifacts)
studio/src/design/types.ts                   # CREATE: TypeScript interfaces for Requirements, Proposal, Scenario, Evaluation

# Views
studio/src/design/views/DesignHomeView.vue   # CREATE: landing page
studio/src/design/views/ScenarioBrowserView.vue  # CREATE: pack list with cards
studio/src/design/views/ScenarioDetailView.vue   # CREATE: single scenario narrative + context
studio/src/design/views/RequirementsView.vue     # CREATE: guided requirements rendering
studio/src/design/views/ProposalView.vue         # CREATE: structured proposal rendering
studio/src/design/views/EvaluationView.vue       # CREATE: Glue Gap Analysis display

# Shared components
studio/src/design/components/ResultBadge.vue     # CREATE: HANDLED/PARTIAL/REQUIRES_GLUE badge
studio/src/design/components/SurfaceTag.vue      # CREATE: mini-card for handled surfaces / components
studio/src/design/components/CategoryBadge.vue   # CREATE: colored pill for glue categories
studio/src/design/components/SectionCard.vue     # CREATE: reusable bordered section container
studio/src/design/components/GlueList.vue        # CREATE: bullet list for flat glue strings

# Modified existing files
studio/src/App.vue                           # MODIFY: add mode switcher, conditional sidebar, Studio home
studio/src/router.ts                         # MODIFY: add /inspect/* and /design/* routes, / as Studio home
studio/src/theme.css                         # MODIFY: add design-mode color variables
```

---

## Task 1: Data Layer — Build Script + Types

**Files:**
- Create: `studio/src/design/types.ts`
- Create: `studio/scripts/build-design-packs.ts`
- Create: `studio/src/design/data/packs.generated.ts` (auto-generated)

- [ ] **Step 1: Create TypeScript interfaces**

Create `studio/src/design/types.ts` with interfaces matching the tooling YAML schemas:

```typescript
export interface PackMeta {
  id: string            // directory name, e.g. "travel-single"
  name: string          // derived from system.name or scenario.name
  domain: string        // from requirements.system.domain
  category: string      // from scenario.scenario.category
  narrative: string     // from scenario.scenario.narrative
  result: string        // from evaluation.evaluation.result
  isMultiService: boolean
}

export interface Requirements {
  system: { name: string; domain: string; deployment_intent: string }
  transports: Record<string, boolean>
  trust: { mode: string; checkpoints: boolean }
  auth: Record<string, boolean>
  permissions: Record<string, boolean>
  audit: Record<string, boolean>
  lineage: Record<string, boolean>
  risk_profile: { capabilities: Record<string, any> }
  business_constraints: Record<string, boolean>
  scale: Record<string, any>
}

export interface Proposal {
  proposal: {
    recommended_shape: string
    rationale: string[]
    required_components: string[]
    optional_components: string[]
    key_runtime_requirements: string[]
    anti_pattern_warnings: string[]
    expected_glue_reduction: Record<string, string[]>
  }
}

export interface Scenario {
  scenario: {
    name: string
    category: string
    narrative: string
    context: Record<string, any>
    expected_behavior: string[]
    expected_anip_support: string[]
  }
}

export interface Evaluation {
  evaluation: {
    scenario_name: string
    result: 'HANDLED' | 'PARTIAL' | 'REQUIRES_GLUE'
    handled_by_anip: string[]
    glue_you_will_still_write: string[]
    glue_category: string[]
    why: string[]
    what_would_improve: string[]
    confidence?: string
    notes?: string[]
  }
}

export interface DesignPack {
  meta: PackMeta
  requirements: Requirements
  proposal: Proposal | null    // null when proposal.yaml is missing
  scenario: Scenario
  evaluation: Evaluation | null // null when evaluation.yaml is missing
}
```

- [ ] **Step 2: Create build script**

Create `studio/scripts/build-design-packs.ts`. This script:
1. Scans all subdirectories in the TOOLING examples path (configurable, default `../../tooling/examples/` relative to the script, or use an env var / CLI arg pointing to the codex tooling)
2. For each directory containing at least `requirements.yaml` and `scenario.yaml`:
   - Reads `requirements.yaml` and `scenario.yaml` (required)
   - Reads `proposal.yaml` and `evaluation.yaml` if present (optional — null when missing)
   - Extracts metadata (id from dir name, domain from requirements, category from scenario, etc.)
   - Bundles into a `DesignPack` object
3. Writes a single `studio/src/design/data/packs.generated.ts` file exporting:
   - `PACKS: DesignPack[]` (all packs)

Add dev dependencies: `cd studio && npm install --save-dev js-yaml @types/js-yaml tsx`

Add to `package.json` scripts: `"build:packs": "npx tsx scripts/build-design-packs.ts"`

**IMPORTANT:** The script must read from a configurable path. The tooling examples live in the codex repo (`/Users/samirski/Development/codex/ANIP/tooling/examples/`), not in the main ANIP repo. The build script should accept a `--source` CLI arg or `DESIGN_PACKS_SOURCE` env variable, with a sensible default.

- [ ] **Step 3: Run the build script to generate the data file**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build:packs -- --source /Users/samirski/Development/codex/ANIP/tooling/examples
```

Verify the generated file exists and contains packs. The number depends on how many directories have at least `requirements.yaml` + `scenario.yaml`.

- [ ] **Step 4: Add generated file to .gitignore**

The generated `packs.generated.ts` should be gitignored since it's derived from the tooling examples. Add to `studio/.gitignore`:
```
src/design/data/packs.generated.ts
```

Actually — **reconsider**: if the Studio is built in CI without access to the codex tooling repo, the generated file needs to be committed. **Commit the generated file** and update it when packs change. Don't gitignore it.

- [ ] **Step 5: Commit**

```bash
git add studio/
git commit -m "feat(studio): add design data layer — types, build script, generated packs"
```

---

## Task 2: Design Store

**Files:**
- Create: `studio/src/design/store.ts`

- [ ] **Step 1: Create the design store**

```typescript
import { reactive } from 'vue'
import type { DesignPack, PackMeta } from './types'
import { PACKS } from './data/packs.generated'

interface DesignState {
  packs: DesignPack[]
  activePackId: string | null
}

export const designStore = reactive<DesignState>({
  packs: PACKS,
  activePackId: null,
})

export function getActivePack(): DesignPack | null {
  if (!designStore.activePackId) return null
  return designStore.packs.find(p => p.meta.id === designStore.activePackId) ?? null
}

export function setActivePack(id: string) {
  designStore.activePackId = id
}

export function getPackMetas(): PackMeta[] {
  return designStore.packs.map(p => p.meta)
}
```

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/store.ts
git commit -m "feat(studio): add design store for pack loading and selection"
```

---

## Task 3: Router + App Shell — Mode Switcher

**Files:**
- Modify: `studio/src/router.ts`
- Modify: `studio/src/App.vue`
- Modify: `studio/src/theme.css`

- [ ] **Step 1: Update router**

Restructure routes:
- `/` → `StudioHome` (neutral welcome, no redirect)
- `/inspect/discovery` through `/inspect/invoke/:capability?` → existing views
- `/inspect` → redirect to `/inspect/discovery`
- `/design` → `DesignHomeView`
- `/design/scenarios` → `ScenarioBrowserView`
- `/design/scenarios/:pack` → `ScenarioDetailView`
- `/design/requirements/:pack` → `RequirementsView`
- `/design/proposal/:pack` → `ProposalView`
- `/design/evaluation/:pack` → `EvaluationView`

Keep backward compat: old routes like `/manifest` redirect to `/inspect/manifest`.

- [ ] **Step 2: Update App.vue — mode switcher + conditional sidebar**

Add a mode switcher in the header (two tabs: Inspect / Design). The active mode determines which sidebar navigation shows.

When on `/` (Studio home), show neither sidebar — just the welcome content with two entry points.

When on `/inspect/*`, show the existing Inspect sidebar (Discovery, Manifest, JWKS, Audit, Checkpoints, Invoke). The connect bar is only shown in Inspect mode.

When on `/design/*`, show the Design sidebar (Home, Scenarios, Requirements, Proposal, Evaluation). No connect bar needed.

- [ ] **Step 3: Add design theme variables to theme.css**

```css
--design-handled: #34d399;
--design-partial: #fbbf24;
--design-glue: #f87171;
--design-info: #60a5fa;
--design-category-safety: #f87171;
--design-category-orchestration: #fbbf24;
--design-category-observability: #60a5fa;
--design-category-cross-service: #a78bfa;
```

- [ ] **Step 4: Build and verify**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add studio/src/
git commit -m "feat(studio): add Inspect/Design mode switcher, Studio home, design routes"
```

---

## Task 4: Shared Design Components

**Files:**
- Create: `studio/src/design/components/ResultBadge.vue`
- Create: `studio/src/design/components/SurfaceTag.vue`
- Create: `studio/src/design/components/CategoryBadge.vue`
- Create: `studio/src/design/components/SectionCard.vue`
- Create: `studio/src/design/components/GlueList.vue`

- [ ] **Step 1: ResultBadge**

Large centered status badge. Props: `result: 'HANDLED' | 'PARTIAL' | 'REQUIRES_GLUE'`. Colors: HANDLED=green, PARTIAL=amber, REQUIRES_GLUE=red. Include a subtitle explaining each state.

- [ ] **Step 2: SurfaceTag**

Compact green-bordered pill for handled surfaces. Props: `label: string`.

- [ ] **Step 3: CategoryBadge**

Colored pill for glue categories. Props: `category: string`. Colors: safety=red, orchestration=amber, observability=blue, cross_service=purple.

- [ ] **Step 4: SectionCard**

Bordered container with optional header. Props: `title?: string`, `icon?: string`. Slot for content.

- [ ] **Step 5: GlueList**

Bullet list from string array. Props: `items: string[]`. Renders as styled `<ul>` with readable line height.

- [ ] **Step 6: Commit**

```bash
git add studio/src/design/components/
git commit -m "feat(studio): add shared Design components — ResultBadge, SurfaceTag, CategoryBadge, SectionCard, GlueList"
```

---

## Task 5: Design Home View

**Files:**
- Create: `studio/src/design/views/DesignHomeView.vue`

- [ ] **Step 1: Build the landing page**

Sections:
1. Hero: "ANIP Studio: Design" + tagline ("Design systems. Validate with real scenarios. See what glue you'll still write.")
2. How it works: 5-step flow (Requirements → Proposal → Scenarios → Validation → Glue Gap Analysis) with icons
3. Example packs: card grid showing all available packs from `getPackMetas()`. Each card shows: name, domain, category badge, narrative excerpt, result badge, "Explore →" link.

Clicking a pack card navigates to `/design/scenarios/{pack.id}`.

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/views/DesignHomeView.vue
git commit -m "feat(studio): add Design home landing page"
```

---

## Task 6: Scenario Browser + Detail Views

**Files:**
- Create: `studio/src/design/views/ScenarioBrowserView.vue`
- Create: `studio/src/design/views/ScenarioDetailView.vue`

- [ ] **Step 1: ScenarioBrowserView**

Full pack list with cards (same as Design home pack grid but as a dedicated page). Filter/sort later — V1 just lists all packs.

- [ ] **Step 2: ScenarioDetailView**

Two-column layout:
- **Left:** Scenario name, category badge, narrative (rendered as readable paragraph), context fields rendered as labeled cards (capability, side_effect, budget, expected_cost, etc.), expected behavior as checklist, expected ANIP support as tag list.
- **Right:** Quick links to Requirements, Proposal, Evaluation for this pack. Result badge preview.

Route param `:pack` sets the active pack in the design store.

- [ ] **Step 3: Commit**

```bash
git add studio/src/design/views/ScenarioBrowserView.vue studio/src/design/views/ScenarioDetailView.vue
git commit -m "feat(studio): add Scenario browser and detail views"
```

---

## Task 7: Requirements View

**Files:**
- Create: `studio/src/design/views/RequirementsView.vue`

- [ ] **Step 1: Build guided requirements rendering**

Sections using SectionCard:
- **System** — name, domain, deployment intent
- **Transports** — checkmark grid (HTTP, stdio, gRPC)
- **Trust & Auth** — trust mode, delegation tokens, scoped authority
- **Audit & Lineage** — durable, searchable, task_id, parent_invocation
- **Risk Profile** — capability mini-cards showing side_effect type and requirements
- **Business Constraints** — bullet list of constraint labels
- **Scale** — shape preference, HA status

All labels are plain language, not YAML keys. Use SectionCard for each group.

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/views/RequirementsView.vue
git commit -m "feat(studio): add guided Requirements view"
```

---

## Task 8: Proposal View

**Files:**
- Create: `studio/src/design/views/ProposalView.vue`

- [ ] **Step 1: Build structured proposal rendering**

Sections:
- **Shape** — recommended deployment shape as header
- **Rationale** — bullet list
- **Required Components** — colored pill tags
- **Optional Components** — pill tags (dimmer)
- **Key Runtime Requirements** — bullet list
- **Anti-Pattern Warnings** — warning-styled bullet list
- **Expected Glue Reduction** — grouped by category (safety, orchestration, observability), each with bullet items

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/views/ProposalView.vue
git commit -m "feat(studio): add Proposal view"
```

---

## Task 9: Evaluation / Glue Gap Analysis View

**Files:**
- Create: `studio/src/design/views/EvaluationView.vue`

- [ ] **Step 1: Build the Glue Gap Analysis view**

This is the most important view. Layout:

1. **Result badge** — large centered ResultBadge component
2. **Handled by ANIP** — responsive grid of SurfaceTag components from `handled_by_anip` string array
3. **Glue You Will Still Write** — GlueList component from `glue_you_will_still_write` string array
4. **Categories** — row of CategoryBadge components from `glue_category` string array (applies to whole evaluation)
5. **Why** — bullet list from `why` string array
6. **What Would Improve** — bullet list from `what_would_improve` string array
7. **Confidence** — badge if present
8. **Notes** — if present

Every rendered value comes directly from the evaluation artifact. No UI-side interpretation or scoring.

**When evaluation is null** (pack has no `evaluation.yaml`): show a clean "Evaluation not yet available" message with an explanation that this pack hasn't been evaluated yet. Same pattern for ProposalView when proposal is null.

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/views/EvaluationView.vue
git commit -m "feat(studio): add Evaluation / Glue Gap Analysis view"
```

---

## Task 10: Build, Test, Polish

- [ ] **Step 1: Build the full Studio**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build
```

Fix any TypeScript or build errors.

- [ ] **Step 2: Run dev server and verify all views**

```bash
npm run dev
```

Verify:
- `/` shows Studio home with Inspect and Design entry points
- Clicking Design shows the Design landing with all packs
- Clicking a pack navigates through Scenario → Requirements → Proposal → Evaluation
- Inspect mode still works when connected to a service
- Dark theme looks good, typography is readable
- Responsive behavior works on smaller screens

- [ ] **Step 3: Commit**

**Do NOT run `studio/sync.sh`.** Design is standalone only — it does NOT ship inside embedded runtime packages. The embedded packages continue shipping the pre-Design Studio build (Inspect only). The standalone Studio (with both Inspect and Design) is built separately and deployed via Docker or hosted web.

```bash
git add studio/
git commit -m "feat(studio): complete Design V1 — build and polish (standalone only, not embedded)"
```
