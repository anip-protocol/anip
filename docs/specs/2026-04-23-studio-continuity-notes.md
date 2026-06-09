# Studio Continuity Notes

Date: 2026-04-23

## Purpose

This note preserves the current Studio implementation state, the architecture decisions that are already in place, the main recovery constraints, and the next steps. It is intended to prevent repeated context loss and to keep future work anchored to the correct repository and the correct product model.

## Program Goal

The program goal for this phase is to make Studio a credible deterministic authoring and proof environment for governed ANIP service fronting.

That means:

- users can model governed behavior in Studio without falling back to prompt glue or local skills
- governed integration-fronting projects can stay simpler than full greenfield ANIP builds while still producing formal contract truth
- Studio can export a stable ANIP Service Definition
- a standalone generator can turn that definition into a runnable service project
- Studio can then prove the generated service against saved contract identity with real runtime evidence

In short, the goal is not only to design ANIP fronting inside Studio. The goal is to get from governed intent to saved contract to generated runnable service to verification evidence in one coherent deterministic flow.

## What We Were Actively Building

The active work during this phase has been the convergence of four tracks into one usable flow.

### 1. Governed integration-fronting as a first-class Studio project type

The main product goal was to make API, MCP, database, and hybrid fronting a first-class Studio experience instead of forcing those efforts through the same full-shape path used by standard projects.

The intended fronting experience is:

- Product Design captures intent, actors, business areas, permission posture, requirements, and scenarios
- Developer Design maps real backend operations into governed ANIP capabilities
- the resulting Developer Definition compiles a fronting contract without demanding unnecessary classic service-build artifacts

### 2. Standalone ANIP generation instead of Studio-owned generation logic

Another active goal was to stop treating generation as something buried inside the UI.

The intended model is:

- Studio authors and exports the canonical machine-readable contract
- a standalone generator CLI consumes that contract
- build packs provide the generic runnable host per language
- extension seams remain explicit

The first complete implementation of this exists now for TypeScript.

### 3. Real proof, not only contract export

The work was not limited to "can Studio save a definition". The target was stronger:

- save Developer Definition
- generate a runnable service project
- run the generated service locally
- capture observed service metadata
- save evaluation evidence
- prove alignment against the saved compiled contract identity

That proof has been completed for the TypeScript issue-tracker fronting showcase.

### 4. Reduce Studio UX noise while preserving rigor

A parallel goal was to make Studio less overwhelming without weakening the deterministic model.

That included:

- consolidating assistant flows around a dedicated assistant page
- restoring global runtime configuration access
- making many dense authoring pages read-first instead of field-heavy by default
- keeping fronting projects visibly simpler than standard projects
- surfacing errors and evidence status more clearly in navigation and overview pages

## Definition of Done for This Phase

This phase should be considered done only when the following are all true.

### Studio modeling and contract

- governed integration-fronting projects are stable and do not regress into standard-project complexity
- Product Design and Developer Design show only the required fronting surfaces
- Developer Definition can be saved deterministically for governed fronting without requiring a classic locked service shape
- issue surfacing distinguishes advisory problems from actual blocking contract problems

### Generation

- Studio can invoke the standalone generator from a saved Service Definition
- the generator emits a runnable TypeScript project from the fronting contract
- generation evidence records mode, inputs, outputs, and contract identity

### Proof and verification

- Studio can run local proof directly from saved generation evidence
- observed service metadata and evaluation evidence are tied to a specific generation run
- Verification and PM Review can target a selected generation run instead of silently following the latest artifact
- saved runtime proof can be shown as aligned or stale against the saved compiled contract and generation run

### Operational safety

- all work happens only in the live repo
- the legacy repo is no longer part of the implementation workflow
- the continuity note and design docs are sufficient for restart without relying on conversational memory

## What This Note Should Preserve

This continuity note should preserve only the memory that is difficult to reconstruct from source code, tests, and commit history, and that materially changes future decisions.

The note should preserve:

- operating constraints such as the one true live repo and forbidden paths
- product intent and the target workflow for the current phase
- architectural decisions about what is canonical, what is derived, and where truth lives
- proof-state memory about what has already been validated end to end
- known traps, mismatches, and failure modes that can easily be repeated
- the current frontier of meaningful next steps
- safe restart and recovery instructions

The note should not try to preserve:

- every small fix
- long chronological work logs
- transient shell activity
- implementation details that are already obvious from the current source
- broad conversational history that does not change technical decisions

In short, this note should preserve decision memory, constraint memory, proof-state memory, and recovery memory. It should not become an exhaust log.

## Repository Rules

### Live repository

The only valid working repository for Studio and ANIP implementation work is:

`/Users/samirski/Development/ANIP`

All real edits, builds, tests, and verification must happen there.

### Legacy repository

The old codex-side copy was renamed and must not be used for live work:

`/Users/samirski/Development/codex/ANIP_LEGACY_DONT_TOUCH`

That tree is legacy salvage input only. It is not a mirror, not a backup to sync from, and not a safe place to restore files from.

### Non-negotiable workflow rule

Do not copy application source files from the legacy tree into the live repo.

That specifically includes:

- `studio/src/*`
- `studio/server/*`
- runtime packages
- generator packages
- shared schemas

If legacy content must be preserved, preserve it as documentation or archive material, not as code copied into the active implementation.

## What Went Wrong Previously

The major regressions were caused by an unsafe dual-repo workflow.

The specific failure pattern was:

1. Work was performed in both the live repo and the codex repo.
2. Whole files were copied between the two trees.
3. The codex tree was not actually a clean mirror.
4. Older UI shell state and older feature logic overwrote newer live state.
5. A stale frontend process sometimes served older assets, which made verification harder.

The practical result was that committed work in the live repo was not enough by itself to protect against new regressions if later whole-file copies reintroduced older code.

## Current Protection Rules

Use these rules going forward.

1. Only edit `/Users/samirski/Development/ANIP`.
2. Treat `/Users/samirski/Development/codex/ANIP_LEGACY_DONT_TOUCH` as read-only archive material.
3. Never copy app source wholesale between repos.
4. Use small, surgical patches only.
5. Build and verify the exact surface after each fix batch.
6. Commit frequently after verified fixes.
7. When UI behavior looks wrong, verify the running frontend is actually serving the live repo.

## Current Architecture Direction

Studio is now carrying three aligned directions at once.

### 1. Studio remains deterministic

Studio itself is still deterministic.

That means:

- the canonical source of truth is stored artifacts and compiled contracts
- AI assistance is optional
- accepted AI output must become deterministic project artifacts before it counts as truth
- generation and verification run against saved compiled contract identity, not unsaved page state

### 2. Governed integration fronting is now a first-class project type

There are two project types in Studio:

- `standard`
- `governed_service_project`

The governed type is for API, MCP, database, or hybrid fronting.

This project type intentionally reduces PM and Developer Design scope where appropriate.

For governed fronting projects:

- Product Design focuses on intent, actors, business areas, permission posture, requirements, and scenarios
- backend shape/capability mapping happens in Developer Design
- Developer Definition does not require the full classic service-build shape path
- Integration Fronting is a first-class Developer Design surface

### 3. Studio is moving toward ANIP Service Definition plus standalone generation

The current direction is:

- Studio authors and saves the machine-readable contract
- a standalone generator CLI consumes that contract
- language-specific build packs generate runnable projects
- extension points remain explicit seams
- verification ties runtime evidence back to saved generation evidence and saved compiled contract identity

This is now partially implemented for TypeScript.

## Core Concepts Already Implemented

### A. Saved compiled contract identity

Developer Definition now produces a saved compiled contract identity.

Verification is tied to that saved identity, not only to current page state.

This is critical because it lets Studio say:

- what contract was generated
- what contract was evaluated
- whether observed runtime proof actually matches the saved compiled contract

### B. Generation evidence is saved as its own artifact

Studio now saves developer generation runs.

These runs include:

- contract identity
- generator inputs
- output bundle artifacts
- generated files for the TypeScript service project

### C. Evidence is now generation-run aware

Evaluation evidence and observed service evidence now carry:

- generation run artifact id
- generation dependency mode

This matters because “latest generation” and “latest runtime proof” are not always the same thing.

Studio can now distinguish:

- proof against a local runnable bundle
- proof against a portable export bundle

### D. Local proof can be launched from Studio

Studio now has first-class local proof actions.

These can be launched from:

- Verification
- PM Review
- Developer Definition / generation results

The local proof flow builds the generated TypeScript service, runs it locally, probes it, and persists observed service metadata plus evaluation evidence back into Studio.

## TypeScript Generator / Build-Pack State

### Current implementation

There is now a standalone TypeScript generator package.

Design doc:

`docs/specs/2026-04-23-anip-generator-build-pack-cli-design.md`

Current implementation status:

- standalone CLI exists
- Studio can invoke it
- it consumes the saved Service Definition shape
- it emits a runnable TypeScript ANIP service project
- the generated project includes a generic HTTP host and runtime wiring
- the generated project includes adapter and policy seams
- smoke tests exist for the generated TypeScript project

### What is already proven

The issue-tracker fronting showcase has already been taken through:

1. saved Developer Definition
2. standalone generator invocation
3. saved generation run
4. materialized TypeScript service project
5. runnable local service proof
6. observed service metadata save
7. evaluation evidence save
8. Verification alignment

This means the path is no longer theoretical.

### What is not done yet

The platform is not yet complete across all intended languages.

Still missing:

- Python build pack
- Java build pack
- Go build pack
- C# build pack
- final packaging/registry delivery model

The first end-to-end proof exists in TypeScript only.

## Generation Dependency Modes

Studio now supports two explicit generation dependency modes.

### Local workspace proof

This mode is intended for local runnable proof.

Characteristics:

- generated project can use local workspace dependency wiring
- easiest path for live runtime proof during development
- useful for Studio-driven validation and demonstration

### Portable registry export

This mode is intended for export/distribution posture.

Characteristics:

- generated bundle carries registry-style dependencies
- portable bundle shape is preserved
- local proof is not silently assumed

This distinction is now persisted in generation evidence.

## Governed Fronting Contract Model

### Semantic inputs vs backend inputs

A major improvement already implemented is the separation between semantic ANIP contract inputs and backend realization inputs.

The intended model is:

- semantic inputs stay explicit and stable
- backend binding inputs may be implicit, hybrid, or explicit

Implemented backend input modes:

- `implicit`
- `hybrid`
- `explicit`

This avoids forcing users to manually restate every raw backend parameter while still preserving stable governed semantics.

### Backend binding model

Fronting mappings now support per-binding realization instead of one flattened backend block.

Each backend binding can carry:

- backend kind
- connection reference
- raw operation references
- backend input mode
- derived backend inputs
- explicit backend overrides
- discovery match ids

### Drift handling

Binding drift is now evaluated per backend binding, not only at the mapping level.

That means Studio can tell the difference between:

- stable governed semantic contract
- stale backend realization

This is the right boundary.

## Current Studio UX State

### General shell

Recovered and committed:

- global `Configure LLM` button in the Studio header
- left-navigation issue badges/indicators
- consistent top-level section styling for Product Design and Developer Design
- Verification no longer incorrectly inherits unrelated section issues
- breadcrumbs use leave-project confirmation behavior
- left navigation is no longer collapsible
- more modern scrollbar styling

### Assistant configuration

The intended placement is now global in the Studio header, next to the time configuration control.

The runtime configuration surface is not supposed to disappear just because the assistant page is hidden or not active.

### Assistant model

Assistant UX has been consolidated toward a dedicated project assistant page, rather than scattering assistant panels everywhere.

### Review-card behavior

A significant UI cleanup already happened:

- many pages now default to read-first/collapsed review cards rather than exposing all inputs immediately
- this was especially important on Developer pages and Integration Fronting pages
- explicit “View saved values” and collapse/expand affordances were added

This reduced the earlier problem where pages looked busy, cluttered, and intimidating before the user even started.

## Live Fronting Showcase

The important current showcase project is:

`project-issue-tracker-fronting-showcase`

This is intentionally generic rather than Jira-hardcoded, but it is the issue-tracker / native API + MCP fronting showcase.

It demonstrates:

- governed ANIP fronting over existing backend operations
- native API + MCP-compatible fronting architecture
- saved compiled contract identity
- standalone generation
- local runnable proof
- verification evidence alignment

## Important Distinction: Nav Issues vs Generation Gating

This is currently one of the most important unresolved UX problems.

### What exists today

Studio currently has at least two different issue systems in play.

1. Page/section issue aggregation
   - built by `buildProjectIssueIndex(...)`
   - used by navigation and overview surfaces
   - historically counted raw issue messages

2. Developer Definition generation gating
   - driven by the Developer Definition draft and compiled-contract validator
   - used when saving and generating the compiled Developer Definition

### Why this caused confusion

This means it is currently possible for Studio to show:

- many Product Design or Developer Design issues in navigation or overview
- while generation still succeeds

That is not because Studio is blindly ignoring errors.
It is because the nav/overview issue counts and the generation validator are not the same gate.

### Current interpretation

If Product Design shows a large count like `38`, that may mean:

- 38 aggregated issue messages

It does not necessarily mean:

- 38 broken pages
- 38 blocking failures
- generation must fail

This is misleading UX and needs cleanup.

### Intended correction

The correct behavior should be:

- top-level Product/Developer indicators should reflect affected pages, not raw message count
- Studio should distinguish advisory/source-quality problems from actual blocking contract problems
- generation readiness should be surfaced from the real compiled-contract validator, not inferred from nav noise

At the time of writing this note, that cleanup is still in progress and should be treated as an active follow-up task.

## Fronting Simplification Status

The fronting simplification should still be intact.

The important live-code invariants are:

- governed fronting projects do not require a classic locked service shape the way standard projects do
- Product Design is reduced to the PM surfaces that still matter for fronting
- Developer Definition and Coverage are allowed to function without a classic service shape when project type is `governed_service_project`
- Integration Fronting remains the first-class Developer surface for backend mapping

This must be preserved. Any future work that makes fronting projects feel like full standard projects again is a regression.

## Salvage Review of Legacy Repo

A targeted salvage review was already done against the legacy codex tree.

Reviewed files included:

- `studio/src/design/developer-definition.ts`
- `studio/src/views/IntegrationFrontingView.vue`
- `studio/src/views/DeveloperDefinitionView.vue`
- `studio/src/views/ProjectVerificationView.vue`
- `studio/src/design/traceability.ts`
- `studio/src/design/use-developer-definition-editor.ts`
- `studio/src/design/product-design.ts`
- `studio/src/design/project-api.ts`
- `studio/src/design/types.ts`
- `studio/src/views/DeveloperDesignHomeView.vue`
- `studio/src/views/PmReviewView.vue`
- `studio/src/views/SourceDocsView.vue`

Conclusion:

No Studio code from the legacy tree should be ported into the live repo from those reviewed files.

The live repo is ahead. The legacy code is mostly older or thinner and would reintroduce regressions.

### Legacy material worth preserving

One legacy document was identified as worth keeping as design rationale:

`docs/specs/2026-04-14-studio-project-flow-redesign.md`

That should be preserved as documentation, not treated as authoritative code.

## Legacy Scripts Folder

The legacy `scripts/` folder is not part of the current Studio source of truth.

It appears to contain mostly helper or GTM-focused utilities, not core Studio runtime logic.

It should be reviewed separately before any script is copied or reused.

Do not assume those scripts are current or authoritative.

## Recent Important Commits in Live Repo

Recent live-repo commits that matter for continuity include:

- `6dd48c70` `Restore Studio header config and issue indicators`
- `819bbf45` `Expose local proof actions across Studio evidence flows`
- `6c6bde06` `Add Studio local runtime proof action`
- `35688cb8` `Select verification evidence by generation run`
- `ace1e608` `Track generation mode across verification evidence`
- `ac9170aa` `Expose Studio generation dependency modes`
- `5150931b` `Generate runnable TypeScript fronting services`
- `7edb6b3d` `Isolate Studio tests and normalize generator input`

These commits are part of the current live implementation baseline and should be treated as the continuity spine for this phase of work.

## Runtime / Dev Environment Notes

### Studio runtime

Typical local runtime:

- frontend: `http://localhost:5173/studio/`
- backend: `http://127.0.0.1:8100`

### Important verification habit

When UI behavior looks wrong:

1. confirm the frontend process is serving the live repo
2. confirm the backend is the expected live backend
3. hard refresh before concluding the source is wrong

This matters because stale frontend processes have previously made good code look broken.

## Known Open Work

At the time of writing, the highest-value remaining work includes:

1. Fix section issue surfacing
   - top-level Product/Developer indicators should count affected pages, not raw messages
   - distinguish blocking contract issues from advisory issues
   - make generation readiness explicit and sourced from the real validator

2. Continue packaging direction
   - blueprint export posture
   - build-pack separation
   - eventual registry alignment

3. Add next build packs after TypeScript
   - likely Python first, unless distribution/CLI concerns force a different order

4. Preserve fronting simplification
   - do not let fronting projects drift back into standard-project complexity

## What Must Never Be Done Again

1. Do not use `/Users/samirski/Development/codex/ANIP_LEGACY_DONT_TOUCH` for live code edits.
2. Do not copy whole UI or server files from the legacy repo into the live repo.
3. Do not treat nav issue counts as equivalent to compiled-contract generation blocking.
4. Do not hide important global controls like runtime/LLM config behind assistant-page visibility.
5. Do not let Verification inherit generic issues from other sections if it is a single-page nav item.

## Practical Restart Checklist

If work resumes later and context is thin, do this first.

1. Open the live repo only:
   - `/Users/samirski/Development/ANIP`
2. Check recent commits.
3. Start Studio frontend and backend from the live repo.
4. Verify the issue-tracker fronting showcase still loads.
5. Verify the global `Configure LLM` button exists in the Studio header.
6. Verify Product Design and Developer Design nav indicators render correctly.
7. Re-read this note and:
   - `docs/specs/2026-04-21-anip-integration-fronting-studio-design.md`
   - `docs/specs/2026-04-21-anip-service-blueprint-registry-trust-model.md`
   - `docs/specs/2026-04-23-anip-generator-build-pack-cli-design.md`

## Summary

The current system is not broken conceptually. The core direction is sound.

The important things that are now real are:

- governed integration-fronting as a first-class project type
- saved compiled contract identity
- generation evidence tied to compiled contract identity
- selected generation run as the target for verification
- local proof from Studio
- standalone TypeScript generator/build-pack path
- runnable generated TypeScript service proof

The biggest remaining risk is not architecture. The biggest remaining risk is operational confusion and UX inconsistency:

- wrong repo
- wrong running process
- misleading issue counts
- mixing advisory problems with real generation blockers

Protect against those, and the current implementation direction is usable and recoverable.
