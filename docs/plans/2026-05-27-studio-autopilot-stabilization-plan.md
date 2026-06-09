# Studio Autopilot Stabilization Plan

Date: 2026-05-27

Status: Draft for implementation

Owner: Studio

## Purpose

Studio must reliably complete a project from source documents to a saved Developer Definition, package, generated services, and tests. The current GTM Autopilot flow proves that the system has useful pieces, but the path is still brittle: source evidence is parsed in more than one place, accepted assistant artifacts can be incomplete, and the Developer Definition builder can materialize a contract that fails validation after Autopilot has already presented the draft as ready.

This plan fixes the system boundary, not the GTM project. The target outcome is a generic Studio pipeline where Autopilot, Guided Mode, and deterministic/manual editing all use the same normalized evidence model and the same final contract validation.

## Current Failure

Fresh GTM source-doc Autopilot can reach Product Design and draft Developer Design, but Developer Capability Formalization still reports errors:

- `At Risk Followup Preparation Composition Steps must have at least one selection.`
- `Composed capabilities must define contract-level composition metadata.`
- Similar missing composition-step errors for six other composed capabilities.

The saved assistant capability proposal contains:

- `kind: "composed"` for the seven composed GTM capabilities.
- `composition: null`.
- duplicated input contracts.
- one bogus capability with ID `capability_id`, likely from loose CSV/header ingestion.

This is unacceptable because Autopilot claimed the draft was ready even though the compiled Developer Definition was not contract-complete.

## Root Causes

### R1. Source Context Duplication

`_dev_source_context` currently builds `requirements_text` from `source_document_text` when no `source_requirements_id` is provided, then concatenates `requirements_text` and `source_document_text` again.

Effect:

- Developer evidence can be parsed twice.
- CSV sections can produce duplicate inputs.
- Header-like rows can leak into capability inventory.

### R2. Multiple Evidence Parsers

Backend Autopilot parsing and frontend Developer Definition building do not share one canonical source-evidence representation.

Effect:

- Backend may accept/persist one structure.
- Frontend builder later materializes another structure.
- Validation failures appear after the assistant draft is "ready."

### R3. Composed Capabilities Are Not First-Class

Studio currently treats `kind: composed` as a flag, but the contract requires actual composition metadata:

- `authority_boundary`
- `steps`
- `input_mapping`
- `output_mapping`
- `failure_policy`
- empty-result policy where relevant
- audit policy where relevant

Effect:

- A composed capability can be accepted without enough data to generate or validate.

### R4. Token-Based Composition Inference Is Too Important

The builder contains token scoring around terms like risk, priority, bottleneck, routing, reassignment, and followup. This can be helpful as review assistance, but it must not be the source of contract truth.

Effect:

- Generic Studio behavior is biased by GTM-like wording.
- Different projects may behave unpredictably based on vocabulary.

### R5. Autopilot Has No Final Compile Gate

Autopilot saves draft proposal sections, but it does not consistently compile the resulting Developer Definition and block "ready for review" when validation fails.

Effect:

- User sees "draft ready."
- Developer pages still show blockers.
- Trust in Autopilot is damaged.

## Principles

1. No new mandatory GTM-only source document.
2. No GTM-specific hardcoded fixes in generic Studio code.
3. Source docs can be Markdown, JSON, or CSV, but once parsed they must become one normalized model.
4. Autopilot may draft; it must not silently invent contract truth.
5. Guided Mode and manual editing must use the same validation boundary as Autopilot.
6. A saved Developer Definition must be generation-ready or explicitly blocked.
7. Readiness proof must include GTM and non-GTM projects.

## Non-Goals

- Do not solve all Studio file-size/refactor debt in this pass.
- Do not redesign the ANIP protocol.
- Do not change GTM generated service behavior until the Studio contract pipeline is stable.
- Do not publish new registry artifacts from this work until release gates pass.
- Do not use seed data as proof for source-doc reproducibility.

## Target Architecture

### New Shared Concept: `DeveloperSourceEvidence`

Studio needs one normalized evidence model produced from uploaded source docs and accepted clarification answers.

Conceptual shape:

```ts
interface DeveloperSourceEvidence {
  source_document_ids: string[]
  capability_inventory: DeveloperEvidenceCapability[]
  input_contracts: DeveloperEvidenceInputContract[]
  runtime_governance: DeveloperEvidenceRuntimeGovernance[]
  compositions: DeveloperEvidenceComposition[]
  actor_policy_notes: DeveloperEvidenceActorPolicy[]
  parse_warnings: DeveloperEvidenceWarning[]
  parse_errors: DeveloperEvidenceError[]
}

interface DeveloperEvidenceCapability {
  capability_id: string
  service_id?: string
  kind: 'atomic' | 'composed'
  title?: string
  summary?: string
  source_ref: SourceRef
}

interface DeveloperEvidenceComposition {
  capability_id: string
  authority_boundary: 'same_service'
  steps: Array<{
    id: string
    capability: string
    empty_result_source?: boolean
  }>
  input_mapping: Record<string, Record<string, string>>
  output_mapping: Record<string, string>
  empty_result_policy?: string
  empty_result_output?: Record<string, unknown>
  failure_policy: {
    child_clarification: 'propagate' | 'fail_parent'
    child_denial: 'propagate' | 'fail_parent'
    child_approval_required: 'propagate' | 'fail_parent'
    child_error: 'propagate' | 'fail_parent'
  }
  audit_policy?: {
    record_child_invocations: boolean
    parent_task_lineage: boolean
  }
  source_ref: SourceRef
}
```

Implementation detail can differ, but the key rule is fixed:

Autopilot, Guided Mode, import buttons, and the Developer Definition builder must consume the same normalized evidence model.

## Phase 0: Freeze The Failure

Goal: create tests that reproduce the current failure before fixing implementation.

Tasks:

1. Add a regression fixture using the current GTM source docs only.
2. Assert that source context is not duplicated.
3. Assert that the parsed capability inventory contains exactly 23 GTM capabilities, not 24.
4. Assert no capability ID equals a CSV header name such as `capability_id`.
5. Assert no capability input appears twice for the same capability/input pair.
6. Assert every `kind=composed` capability is either fully composed or explicitly blocked with a targeted question.

Acceptance:

- The regression fails on current code for the known duplication/composition issues.
- The test does not use seed data.

## Phase 1: Fix Source Context And Strict Parsing

Goal: source docs are parsed once, bounded by document, and invalid rows fail loudly.

Tasks:

1. Fix `_dev_source_context` so `source_document_text` is not duplicated.
2. Track source document boundaries when building assistant context.
3. Parse CSV per document, not across concatenated source text.
4. Reject CSV rows where `capability_id` equals a header cell or is not a canonical capability ID.
5. Deduplicate input contracts by `(capability_id, input_name)` and fail on conflicting duplicates.
6. Deduplicate runtime governance by `capability_id` and fail on conflicting duplicates.
7. Return parse warnings/errors in a structured form, not just buried text.

Acceptance:

- Current GTM docs parse to 23 capabilities.
- No duplicate inputs.
- No `capability_id` bogus capability.
- Parser errors are actionable and point to the source document and row.

## Phase 2: Introduce `DeveloperSourceEvidence`

Goal: backend and frontend stop maintaining competing interpretations of source evidence.

Tasks:

1. Create a shared TypeScript evidence type in `studio/src/design/developer-source-evidence.ts`.
2. Create equivalent Python validation/serialization model in `studio/server`.
3. Define one JSON shape exchanged between backend and frontend.
4. Move CSV/Markdown/JSON parsing into a single evidence parser module.
5. Make backend assistant proposal generation use `DeveloperSourceEvidence`.
6. Make frontend Developer Definition builder use `DeveloperSourceEvidence`.
7. Remove parallel ad hoc extraction paths where possible.

Acceptance:

- `assistant_service.py` no longer has to infer canonical capability inventory independently from arbitrary text for developer contract truth.
- `developer-definition.ts` no longer reparses raw CSV/Markdown evidence independently for contract truth.
- Existing manual import still works, but produces `DeveloperSourceEvidence` first.

## Phase 3: First-Class Composition Metadata

Goal: composed capabilities become explicit contract data, not token-score side effects.

Tasks:

1. Extend developer evidence parsing to support optional composition metadata.
2. Add a neutral composition table format for CSV/Markdown import.
3. Add UI fields in Capability Formalization for:
   - composed/atomic kind
   - child steps
   - input mappings
   - output mappings
   - authority boundary
   - failure policy
   - empty-result behavior
4. If source says `kind=composed` but has no composition, create a blocker with exact missing fields.
5. Autopilot may draft composition suggestions, but the suggestions must be reviewed before becoming contract truth.
6. Token-scored inference may remain only as a "suggested composition candidates" helper, never as silent saved truth.

Acceptance:

- `kind=composed` without `composition.steps` cannot be accepted as a completed capability.
- A user can complete missing composition metadata in Capability Formalization without editing JSON.
- GTM is not special-cased.

## Phase 4: Autopilot Compile Gate

Goal: Autopilot must not show "ready for review" unless the compiled Developer Definition validates.

Tasks:

1. After Developer Autopilot drafts all sections, compile the Developer Definition in memory.
2. Run `validateDeveloperDefinitionRequiredFields`.
3. Run agent consumption readiness.
4. If validation fails, Autopilot state must be `blocked` or `needs_clarification`, not `ready`.
5. Show exact targeted questions/actions:
   - missing composition steps
   - missing input contracts
   - missing coverage mapping
   - unknown effects
   - unreviewed readiness warnings
6. Add UI copy that says: "Autopilot stopped because the contract is incomplete."

Acceptance:

- A draft with seven missing composition definitions cannot be presented as ready.
- The assistant page points to Capability Formalization with exact capability names and missing fields.
- No generated package can be created from an incomplete Autopilot draft.

## Phase 5: Remove GTM Leakage From Generic Logic

Goal: generic Studio code must not depend on GTM vocabulary.

Tasks:

1. Remove `gtm` from generic stopword logic or replace with namespace-neutral handling.
2. Move GTM examples in generic UI placeholders to neutral examples or rotate examples by project type.
3. Remove `q2_pipeline_review_must_be_reproducible_locally` from shared generic artifact rendering or isolate it to showcase-specific docs.
4. Review token heuristics for `risk`, `priority`, `bottleneck`, `routing`, `followup`, etc.
5. Keep domain examples in tests/fixtures only.

Acceptance:

- `rg "\bgtm\b|gtm[._-]|Q2 pipeline|sales_leader|rev_ops"` in generic Studio source returns only fixtures, tests, showcase seed data, or explicitly neutral examples.
- Generic contract behavior does not change based on GTM namespace.

## Phase 6: Release Gates

Goal: prove reproducibility before public release.

Release gate A: Fresh GTM source-doc project

1. Start clean Studio DB.
2. Create new workspace/project.
3. Upload GTM source docs only.
4. Run Product Autopilot.
5. Lock Product r1.
6. Run Developer Autopilot.
7. Resolve any targeted questions in Guided Mode if Autopilot stops.
8. Save Developer Definition revision.
9. Generate package.
10. Generate Python and TypeScript services first.
11. Run 350 + 140 question banks.
12. Expand to Go, Java, C# only after Python/TS pass from the same package.

Release gate B: Simple fronting project

1. Use one realistic fronting source project, preferably Slack or Jira.
2. Run source-doc Autopilot.
3. Save Developer Definition.
4. Generate package.
5. Generate service.
6. Run real credential smoke only if tokens are present.

Release gate C: Minimal non-GTM composed project

Purpose: prove composition is generic.

Example:

- Service: issue triage service.
- Atomic capability: `issue.search_candidates`.
- Atomic capability: `issue.prepare_assignment_preview`.
- Composed capability: `issue.candidate_assignment_preparation`.

Requirements:

- Not GTM.
- Not sales/revenue.
- Has one composed capability with same-service steps.
- Must save Developer Definition and generate package.

Acceptance:

- All three gates pass from clean source-doc projects.
- No seed data is used as proof.
- Failures produce targeted questions, not silent incomplete contracts.

## Phase 7: Refactor Follow-Up

Goal: reduce future brittleness after release blocker is fixed.

Tasks:

1. Split `developer-definition.ts` into:
   - evidence normalization
   - definition builder
   - validation
   - composition helpers
   - package/export helpers
2. Split `assistant_service.py` into:
   - source evidence parser
   - PM assistant capabilities
   - Developer assistant capabilities
   - validation guards
   - deterministic proposal builders
3. Add smaller contract tests around each module.

Acceptance:

- No single Studio design module should keep growing as a 7k-line coordinator.
- New source evidence formats can be added without touching Autopilot orchestration and Developer Definition materialization separately.

## Implementation Order

1. Phase 0: failing regression tests.
2. Phase 1: source duplication and strict parsing.
3. Phase 2: shared evidence model.
4. Phase 3: first-class composition metadata.
5. Phase 4: Autopilot compile gate.
6. Phase 5: GTM leakage cleanup.
7. Phase 6: release gates.
8. Phase 7: follow-up refactor.

Do not run broad 490-question language parity until Phase 6 gate A can produce a clean package from a fresh source-doc project.

## Stop Conditions

Stop and report instead of patching if any of these happen:

- A fix requires GTM-specific code in generic Studio paths.
- Autopilot can only succeed by adding another mandatory GTM source document.
- The Developer Definition builder and assistant parser disagree on capability count.
- A composed capability can be saved with `composition: null`.
- Seed data is required to pass a release gate.

## Definition Of Done

The stabilization work is done when:

- Fresh GTM source-doc project reaches saved Developer Definition with zero blockers.
- The generated package has exactly the expected capability count and no bogus capability IDs.
- Every composed capability has explicit validated composition metadata.
- Fresh simple fronting project reaches saved Developer Definition.
- Fresh minimal non-GTM composed project reaches saved Developer Definition.
- Autopilot stops with targeted questions when source evidence is incomplete.
- No generic Studio logic depends on GTM-specific terms.

