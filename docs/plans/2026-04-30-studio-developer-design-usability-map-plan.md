# Studio Developer Design Usability Map Plan

Date: 2026-04-30

Status: Proposed

## Problem

Studio is intentionally canonical and deterministic because that is what lets it produce verifiable ANIP contracts, packages, generator inputs, and Registry records. That should not change.

The problem is presentation. Developer Design currently exposes too much dry contract language directly. It can feel like reading a legal document: technically precise, but hard to understand without already knowing how all the pieces connect.

Velocity matters. A PM or developer should not need a month of Studio-specific training before they can understand what Studio is producing, what is blocked, what is native ANIP, and what still needs app or service glue.

## Principle

Keep canonical values in the contract. Translate them in the UI.

Studio should remain deterministic under the hood, but the user-facing layer should explain:

- what the thing means in business language
- where it fits in the ANIP delivery model
- whether it is ready, blocked, warning-only, or explicitly accepted glue
- where the user should click to fix or inspect it

## Human Language Layer

Canonical effect identifiers should remain in contracts, packages, verifier input, generator input, and Registry records. Developer Design should not lead with these raw identifiers:

- `content.draft`
- `content.summary`
- `content.recommendation`
- `data.read`
- `data.aggregate`
- `data.export`
- `raw_data_export`
- `system.preview_mutation`
- `system.mutation`
- `external_dispatch`
- `approval.request`
- `approval.execute`

Instead, Studio should display human-readable labels by default, with technical IDs available in a collapsed “technical details” view.

Initial label mapping:

| Canonical ID | User label | Category | Meaning |
| --- | --- | --- | --- |
| `content.draft` | Draft content | Content | Produces editable draft material. |
| `content.summary` | Summarize information | Content | Produces a bounded explanation or summary. |
| `content.recommendation` | Recommend options | Content | Produces ranked or suggested options. |
| `data.read` | Read bounded data | Data | Reads data within declared scope. |
| `data.aggregate` | Aggregate data | Data | Computes grouped or summarized data. |
| `data.export` | Export data | Data | Produces a data export. |
| `raw_data_export` | Export raw data | Restricted Data | Exposes raw or underlying records. |
| `system.preview_mutation` | Preview a change | System Action | Previews a mutation without executing it. |
| `system.mutation` | Change system state | System Action | Mutates an internal system. |
| `external_dispatch` | Send outside the system | External Action | Sends, publishes, dispatches, or contacts externally. |
| `approval.request` | Ask for approval | Approval | Creates or requires an approval request. |
| `approval.execute` | Execute approved action | Approval | Executes the governed action after approval. |

The label system should be shared across Developer Coverage, Developer Definition, simulator reports, generated package summaries, and Registry/package detail views.

## Visual Contract Maps

Developer Design should add a visual map that connects the pages and artifacts into an understandable model.

The goal is not visual decoration. The map should answer:

- What business capabilities are we delivering?
- Which parts are native ANIP?
- Which parts require custom service logic?
- Which parts require app glue?
- Which parts are approval-gated or unsafe?
- Which Studio page owns each block?
- Where are the blockers and warnings?

## Map 1: Business Capability Map

Audience: PMs, product owners, solution architects, developers.

Suggested layers:

- Source documents
- Product intent
- Business capabilities
- Outcomes/effects
- Approval boundaries
- Required app glue
- Unsupported or out-of-scope behavior

Each block should show:

- human label
- status: ready, warning, blocker, stale, accepted glue
- short explanation
- issue count if applicable
- click target to the owning Studio page

Example flow:

Source Docs -> Product Design -> Business Capability -> Produces “Draft content” -> Requires “Ask for approval” -> App glue: “Product framing/result display”

## Map 2: Technical Delivery Map

Audience: developers and platform owners.

Suggested layers:

- Developer Definition
- Services
- Capabilities
- Inputs/outputs
- Scopes/grants
- Generator target
- Registry package
- Verifier/runtime evidence

Each block should show:

- owning service or artifact
- ready/warning/blocker status
- linked Studio page
- canonical IDs only in technical details
- whether this is generated, custom service logic, app glue, or external integration

Example flow:

Developer Definition -> Pipeline Service -> `gtm.prepare_followup_tasks` -> Ask for approval + Preview a change -> Registry package -> generator -> Runtime verification

## Interaction Model

The map should support progressive disclosure:

- default view shows only major layers and status
- clicking a block opens details
- details include canonical IDs, source artifact, page route, and current issues
- clicking “Open source” navigates to the owning page
- warnings and blockers should be visible on the map and on the owning page

Users should also be able to open the map from individual Developer Design pages, focused on the current block/layer. This helps the user understand why a page exists and how it contributes to the final package.

## Component Strategy

Do not hand-roll a complex graph unless necessary.

Recommended path:

1. Start with a lightweight internal map component using existing Vue/CSS/SVG if it is enough for the first version.
2. If zoom, pan, custom node rendering, and click navigation become important immediately, evaluate `@vue-flow/core`.
3. Keep graph data deterministic and derived from the existing project issue index, Developer Definition, traceability, readiness, and artifact records.

The map should not introduce a new source of truth. It is a visualization of existing deterministic state.

## Phased Implementation

### Phase 1: Human Labels

- Add shared vocabulary helpers for canonical effects and related status terms.
- Replace raw effect IDs in Developer Coverage and Developer Definition primary UI.
- Keep canonical IDs behind a technical-details disclosure.
- Update simulator/readiness summaries to use human labels.

### Phase 2: Lightweight Developer Design Map

- Add a Developer Design map card/page.
- Show business capability map first.
- Use existing issue counts and routes.
- Make blocks clickable.
- Color-code ready, warning, blocker, stale, and accepted glue.

### Phase 3: Technical Delivery Map

- Add service/capability/package/generator/verification map.
- Link services and capabilities to formalization pages.
- Link package/generator/verification nodes to Developer Definition, Registry publication, and Verification pages.

### Phase 4: Page-Level Context

- Add “Where this fits” affordance on Developer Design pages.
- Open a focused map panel/dialog for the current page.
- Show upstream/downstream dependencies and current blockers.

### Phase 5: Optional Rich Graph Component

- Evaluate `@vue-flow/core` only if the lightweight map becomes limiting.
- Requirements before adding dependency:
  - zoom/pan is needed
  - custom nodes are needed
  - graph grows beyond simple layered layout
  - accessibility and keyboard navigation are acceptable

## Non-Goals

- Do not weaken canonical contract generation.
- Do not replace Developer Definition with a diagram-only editor.
- Do not hide blockers behind visual polish.
- Do not imply ANIP eliminates all app glue.
- Do not create a second, divergent source of project truth.

## Success Criteria

- A new user can explain what Developer Design is building after looking at the map.
- Raw canonical IDs are no longer the primary UI language.
- Users can navigate from a diagram block to the exact page that owns it.
- Issue counts on the map match the navigation and page-level blockers.
- Required app glue is shown as an explicit, acceptable implementation category, not as a failure or hidden workaround.
- Studio feels like a product/design tool while still producing deterministic ANIP contracts.
