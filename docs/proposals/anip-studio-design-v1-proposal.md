# ANIP Studio: Design V1 — Design Proposal

## 1. Information Architecture

### Top-Level Studio Split

The header brand stays `ANIP Studio`. Below the brand, add a **mode switcher** — two tabs in the header area:

```
◆ ANIP Studio    [ Inspect | Design ]    [Connected badge / URL]
```

- **Inspect** — the existing protocol inspector (Discovery, Manifest, JWKS, Audit, Checkpoints, Invoke). Requires a connected service.
- **Design** — scenario-driven execution design and validation. Works locally with artifact packs. Does NOT require a connected service.

The sidebar navigation changes based on the active mode:

**Inspect sidebar** (current — unchanged):
- Discovery, Manifest, JWKS, Audit, Checkpoints, Invoke

**Design sidebar:**
- Home (landing/explainer)
- Scenarios (browser + detail)
- Requirements (guided view)
- Proposal (structured view)
- Evaluation (Glue Gap Analysis)

### Route Structure

```
/inspect/                 → redirect to /inspect/discovery
/inspect/discovery        → existing DiscoveryView
/inspect/manifest         → existing ManifestView
/inspect/jwks             → existing JwksView
/inspect/audit            → existing AuditView
/inspect/checkpoints      → existing CheckpointsView
/inspect/invoke/:cap?     → existing InvokeView

/design/                  → DesignHomeView (landing)
/design/scenarios         → ScenarioBrowserView
/design/scenarios/:pack   → ScenarioDetailView
/design/requirements/:pack → RequirementsView
/design/proposal/:pack    → ProposalView
/design/evaluation/:pack  → EvaluationView
```

Existing `/` redirects to `/inspect/` to preserve backward compat.

### Welcome Screen

When no mode is selected (or first load), show a welcome that presents both modes:

```
◆ ANIP Studio

[Inspect]                        [Design]
Connect to an ANIP service       Design and validate ANIP systems
to explore its protocol          against real execution scenarios
surfaces.
                                 Browse example packs or create
                                 your own requirements and
                                 scenarios.
```

---

## 2. Design Mode Views

### 2.1 Design Home (Landing)

**Purpose:** Explain what Design mode does, in product language.

**Layout:**
```
┌──────────────────────────────────────┐
│          ANIP Studio: Design         │
│                                      │
│   Design systems. Validate with      │
│   real scenarios. See what glue      │
│   you'll still write.                │
│                                      │
│   ┌──────────┐  ┌──────────┐        │
│   │ Browse    │  │ What is  │        │
│   │ Examples  │  │ this?    │        │
│   └──────────┘  └──────────┘        │
│                                      │
│   ── How It Works ──                 │
│                                      │
│   1. Define requirements             │
│   2. Propose a structure             │
│   3. Write scenarios                 │
│   4. Run validation                  │
│   5. Read the Glue Gap Analysis      │
│                                      │
│   ── Example Packs ──                │
│                                      │
│   [Travel Single]  [DevOps]  [Multi] │
└──────────────────────────────────────┘
```

**Key elements:**
- Headline: plain language, not jargon
- Two CTAs: "Browse Examples" + "What is Glue Gap Analysis?"
- How-it-works flow (5 steps, icons)
- Example pack cards at the bottom

### 2.2 Scenario Browser

**Purpose:** Browse available example packs, pick one to explore.

**Layout:**
```
┌──────────────────────────────────────┐
│  Scenarios                           │
│                                      │
│  ┌─────────────────────────────────┐ │
│  │ ✈ Travel — Single Service       │ │
│  │ Budget-constrained flight       │ │
│  │ booking with safety controls    │ │
│  │ Category: safety                │ │
│  │ [Explore →]                     │ │
│  └─────────────────────────────────┘ │
│                                      │
│  ┌─────────────────────────────────┐ │
│  │ 🔧 DevOps — Single Service     │ │
│  │ Destructive infra action with   │ │
│  │ non-delegable controls          │ │
│  │ Category: safety                │ │
│  │ [Explore →]                     │ │
│  └─────────────────────────────────┘ │
│                                      │
│  ┌─────────────────────────────────┐ │
│  │ ✈ Travel — Multi-Service       │ │
│  │ Cross-service search + book     │ │
│  │ with handoff and refresh        │ │
│  │ Category: cross_service         │ │
│  │ [Explore →]                     │ │
│  └─────────────────────────────────┘ │
└──────────────────────────────────────┘
```

Each card shows: icon, name, narrative excerpt, category badge, explore button.

### 2.3 Scenario Detail

**Purpose:** Show the full scenario in human-readable form after selecting a pack.

**Layout:** Two-column — left is the scenario narrative + context, right is quick links to the other artifact views for this pack.

```
┌───────────────────────┬──────────────┐
│  book_flight_over_     │  This Pack   │
│  budget                │              │
│                        │  [Require-   │
│  Category: safety      │   ments →]   │
│                        │  [Proposal   │
│  ── Narrative ──       │   →]         │
│                        │  [Evalua-    │
│  An agent is helping   │   tion →]    │
│  a user plan travel... │              │
│                        │              │
│  ── Context ──         │  Result:     │
│                        │  ┌─────────┐ │
│  Capability: book_     │  │ PARTIAL │ │
│  flight                │  └─────────┘ │
│  Side effect:          │              │
│  irreversible          │              │
│  Budget: $500          │              │
│  Expected cost: $800   │              │
│                        │              │
│  ── Expected ──        │              │
│  Behavior              │              │
│                        │              │
│  • Do not execute      │              │
│  • Explain budget      │              │
│  • Preserve lineage    │              │
│  • Produce audit       │              │
└───────────────────────┴──────────────┘
```

Context fields rendered as labeled cards, not raw YAML keys.

### 2.4 Requirements View

**Purpose:** Show requirements in guided, human-readable form.

**Layout:** Sectioned cards matching the YAML structure but with plain labels.

```
┌──────────────────────────────────────┐
│  Requirements: travel-booking-service│
│                                      │
│  ── System ──                        │
│  Domain: Travel                      │
│  Deployment: Public HTTP service     │
│                                      │
│  ── Transports ──                    │
│  [✓ HTTP]  [✗ stdio]  [✗ gRPC]      │
│                                      │
│  ── Trust & Auth ──                  │
│  Trust: Signed manifests             │
│  Delegation tokens: Yes              │
│  Scoped authority: Yes               │
│                                      │
│  ── Audit & Lineage ──              │
│  Durable audit: Yes                  │
│  Task ID: Yes                        │
│  Parent invocation: Yes              │
│                                      │
│  ── Risk Profile ──                  │
│  ┌────────────────┐ ┌──────────────┐ │
│  │ search_flights │ │ book_flight  │ │
│  │ Side effect:   │ │ Side effect: │ │
│  │ none           │ │ irreversible │ │
│  │                │ │ Cost vis: ✓  │ │
│  │                │ │ Recovery: ✓  │ │
│  └────────────────┘ └──────────────┘ │
│                                      │
│  ── Business Constraints ──          │
│  • Budget limit required             │
│  • Over-budget must not execute      │
│  • Blocked actions should escalate   │
└──────────────────────────────────────┘
```

Checkmarks, badges, capability mini-cards. No raw YAML.

### 2.5 Proposal View

**Purpose:** Show the proposed ANIP structure.

**Layout:**

```
┌──────────────────────────────────────┐
│  Proposal                            │
│  Shape: Production single service    │
│                                      │
│  ── Rationale ──                     │
│  • Public HTTP surface required      │
│  • Durable audit + searchable        │
│  • Signed trust sufficient           │
│  • Single service boundary enough    │
│                                      │
│  ── Required Components ──           │
│  [capability_registry]               │
│  [manifest_generator]                │
│  [token_verifier]                    │
│  [delegation_engine]  ...            │
│                                      │
│  ── Optional Components ──           │
│  [token_issuer]  [studio]            │
│  [graphql]  [rest]  [mcp]            │
│                                      │
│  ── Key Runtime Requirements ──      │
│  • Expose side_effect for book       │
│  • Expose cost metadata              │
│  • Support permission discovery      │
│  • Persist lineage fields            │
│                                      │
│  ── Expected Glue Reduction ──       │
│  Safety:                             │
│    • Permission wrapper glue         │
│    • Budget enforcement glue         │
│  Orchestration:                      │
│    • Preflight wrapper logic         │
│  Observability:                      │
│    • Correlation ID stitching        │
└──────────────────────────────────────┘
```

Component tags as colored pills. Rationale as bullet cards. Glue reduction grouped by category.

### 2.6 Evaluation / Glue Gap Analysis View

**Purpose:** The most important view — show what ANIP handles and what glue remains.

**Layout:**

```
┌──────────────────────────────────────┐
│  Evaluation: book_flight_over_budget │
│                                      │
│  ┌──────────────────────────────────┐│
│  │         ██  PARTIAL  ██          ││
│  │                                  ││
│  │  ANIP handles significant parts  ││
│  │  of this scenario, but some      ││
│  │  glue is still required.         ││
│  └──────────────────────────────────┘│
│                                      │
│  ── Handled by ANIP ──       ✓      │
│  ┌─────────────┐ ┌─────────────┐    │
│  │ Task        │ │ Parent      │    │
│  │ identity    │ │ invocation  │    │
│  │             │ │ lineage     │    │
│  └─────────────┘ └─────────────┘    │
│  ┌─────────────┐ ┌─────────────┐    │
│  │ Durable     │ │ Structured  │    │
│  │ audit       │ │ failure     │    │
│  └─────────────┘ └─────────────┘    │
│  ┌─────────────┐ ┌─────────────┐    │
│  │ Side-effect │ │ Cost        │    │
│  │ visibility  │ │ visibility  │    │
│  └─────────────┘ └─────────────┘    │
│                                      │
│  ── Glue You Will Still Write ── ⚠  │
│                                      │
│  ┌──────────────────────────────────┐│
│  │ Budget enforcement logic         ││
│  │ ─────────────────────            ││
│  │ Unless the budget limit is       ││
│  │ represented in delegation,       ││
│  │ permission evaluation, or a      ││
│  │ protocol-visible control layer.  ││
│  │                                  ││
│  │ Category: safety                 ││
│  └──────────────────────────────────┘│
│                                      │
│  ┌──────────────────────────────────┐│
│  │ Approval / escalation routing    ││
│  │ ─────────────────────            ││
│  │ If the organization requires a   ││
│  │ human to approve over-budget     ││
│  │ bookings.                        ││
│  │                                  ││
│  │ Category: orchestration          ││
│  └──────────────────────────────────┘│
│                                      │
│  ── Why ──                           │
│  The design improves the decision    │
│  surface substantially, but budget   │
│  control is not yet enforceable.     │
│                                      │
│  ── What Would Improve This ──       │
│  • Represent budget as enforceable   │
│    authority binding                 │
│  • Expose budget-based blocking in   │
│    permission discovery              │
└──────────────────────────────────────┘
```

**Result badge:** Large, centered, color-coded:
- `HANDLED` → green
- `PARTIAL` → amber/yellow
- `REQUIRES_GLUE` → red

**Handled surfaces:** Green-bordered mini-cards in a responsive grid.

**Glue items:** Each as an expandable card with explanation + category badge.

**Why + What Would Improve:** Prose sections at the bottom.

---

## 3. Data Loading Architecture

### V1: Static Example Packs

Example packs are bundled as JSON at build time from the `tooling/examples/` YAML files:

```
studio/src/data/
  packs.ts          # index of available packs
  travel-single.ts  # { requirements, proposal, scenario, evaluation }
  devops-single.ts
  travel-multi.ts
```

A build-time script (`scripts/build-design-packs.ts`) reads the YAML files and the validator output, converts to JSON, and writes the `.ts` data modules. This keeps the truth layer in YAML while the UI consumes typed JSON.

### V1 Store

```typescript
interface DesignStore {
  packs: PackIndex[]           // available packs
  activePack: string | null    // selected pack ID
  requirements: Requirements | null
  proposal: Proposal | null
  scenario: Scenario | null
  evaluation: Evaluation | null
}
```

Simple reactive store (same pattern as existing `store.ts`).

### Future: API Layer

The store interface is designed so that `loadPack(id)` can later become an API call instead of a static import. Every UI action maps to a clean data operation:

- `listPacks()` → list available packs
- `loadPack(id)` → load all 4 artifacts for a pack
- `runEvaluation(requirements, proposal, scenario)` → trigger validator (future)

---

## 4. Visual Design

### Colors and Theme

Reuse the existing dark theme CSS variables. Add Design-mode-specific accents:

```css
--design-handled: #34d399;      /* green — handled surfaces */
--design-partial: #fbbf24;      /* amber — partial result */
--design-glue: #f87171;         /* red — requires glue */
--design-info: #60a5fa;         /* blue — informational */
--design-category-safety: #f87171;
--design-category-orchestration: #fbbf24;
--design-category-observability: #60a5fa;
--design-category-cross-service: #a78bfa;
```

### Component Patterns

- **Section cards** — bordered containers with header + content, used for requirements sections, proposal blocks
- **Mini-cards** — compact badges for handled surfaces, components, capabilities
- **Result badge** — large centered status indicator (HANDLED/PARTIAL/REQUIRES_GLUE)
- **Glue cards** — expandable cards with explanation, each tagged with a category badge
- **Category badges** — colored pills: safety=red, orchestration=amber, observability=blue, cross_service=purple

### Typography

Same as existing Studio — system font stack for UI, monospace for technical values. Plain language headers, not YAML key names.

---

## 5. V1 Scope vs Deferred

### V1 (this build)

- Studio IA: Inspect/Design mode switcher
- Design landing page
- Scenario browser with 3 example packs
- Scenario detail view (narrative + context)
- Requirements view (guided cards)
- Proposal view (structured components)
- Evaluation/Glue Gap Analysis view
- Static data from bundled example packs
- Dark theme, responsive

### Deferred

- Live scenario authoring (create/edit requirements, scenarios)
- Live validation (run the evaluator from the UI)
- Legacy comparison mode
- Starter pack generation
- API backend / persistence
- Agent workflow integration
- Multi-user collaboration
- Docker standalone deployment for Design mode
- Full example-pack CRUD

---

## 6. Component Inventory

New Vue components needed:

| Component | Purpose |
|-----------|---------|
| `DesignHomeView.vue` | Landing page for Design mode |
| `ScenarioBrowserView.vue` | Pack list with cards |
| `ScenarioDetailView.vue` | Single scenario narrative + context |
| `RequirementsView.vue` | Guided requirements rendering |
| `ProposalView.vue` | Structured proposal rendering |
| `EvaluationView.vue` | Glue Gap Analysis display |
| `ResultBadge.vue` | Large HANDLED/PARTIAL/REQUIRES_GLUE badge |
| `GlueCard.vue` | Expandable card for a single glue item |
| `SurfaceTag.vue` | Mini-card for handled surfaces / components |
| `CategoryBadge.vue` | Colored pill for glue categories |
| `SectionCard.vue` | Reusable bordered section container |

Modified components:

| Component | Change |
|-----------|--------|
| `App.vue` | Add mode switcher (Inspect/Design), conditional sidebar |
| `router.ts` | Add `/inspect/*` and `/design/*` routes |

---

## 7. Architecture Notes for Future

- Every view reads from `DesignStore` — swap static imports for API calls later
- Pack loading is a single async function — replace with `fetch()` when API exists
- All data types are TypeScript interfaces — reusable for API response typing
- No hidden UI-only logic — every rendered value comes from the artifact data
- The evaluation view renders the exact same fields the validator produces — no UI-side scoring or interpretation
