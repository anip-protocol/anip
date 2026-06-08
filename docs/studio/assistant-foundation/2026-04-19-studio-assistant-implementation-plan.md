# Studio Assistant Implementation Plan

Date: 2026-04-19

## Goal

Implement optional AI-assisted Studio authoring without weakening deterministic generation and verification.

The result should be:

- one shared assistant service
- PM and Dev assist modes
- proposal-based persistence only
- Studio still fully functional without AI

## Starting Point In The Current Repo

The repo already has several useful starting pieces:

1. Current Studio assistant gateway and capability naming in:
   - [studio/src/design/project-api.ts](/Users/samirski/Development/codex/ANIP/studio/src/design/project-api.ts)

2. Existing explanation/intent capabilities:
   - `studio.assistant.explain_shape`
   - `studio.assistant.explain_evaluation`
   - `studio.assistant.interpret_project_intent`

3. Existing runtime status fields that already surface assistant configuration:
   - `assistant_provider`
   - `assistant_model`

4. A deterministic Studio core with growing structured PM and Dev artifacts.

This means the next work should extend the existing assistant boundary, not create a second one.

## Phase 1: Hard Boundary And Proposal Envelope

### Objective

Make the assistant boundary explicit and safe before adding more capability breadth.

### Work

1. Add a single canonical assistant response envelope.
2. Add proposal kinds:
   - `candidate_blocks`
   - `patch_candidates`
   - `clarification_questions`
3. Add proposal acceptance endpoints in the deterministic backend.
4. Add audit records for:
   - assistant request
   - assistant response
   - accepted proposal items
   - rejected proposal items

### Deliverable

The assistant can return structured proposals, but the backend still decides what gets persisted.

## Phase 2: PM Assist

### Objective

Cover the highest-value PM drafting tasks first.

### First Capability Set

- `studio.assistant.propose_requirements`
- `studio.assistant.propose_scenarios`
- `studio.assistant.identify_missing_business_info`
- `studio.assistant.propose_actor_model`
- `studio.assistant.propose_non_goals`
- `studio.assistant.propose_success_criteria`

### UI Surfaces

- [SourceDocsView.vue](/Users/samirski/Development/codex/ANIP/studio/src/views/SourceDocsView.vue)
- [RequirementsView.vue](/Users/samirski/Development/codex/ANIP/studio/src/views/RequirementsView.vue)
- [ScenariosListView.vue](/Users/samirski/Development/codex/ANIP/studio/src/views/ScenariosListView.vue)
- [ActorModelView.vue](/Users/samirski/Development/codex/ANIP/studio/src/views/ActorModelView.vue)
- [NonGoalsView.vue](/Users/samirski/Development/codex/ANIP/studio/src/views/NonGoalsView.vue)
- [SuccessCriteriaView.vue](/Users/samirski/Development/codex/ANIP/studio/src/views/SuccessCriteriaView.vue)

### Acceptance Criteria

- PM can create a useful first draft from source docs without writing every field manually.
- PM can see exactly what the assistant proposed.
- PM can accept or reject by item.
- persisted artifacts remain schema-valid.

## Phase 3: Dev Assist

### Objective

Help developers refine the project into generation-grade structured contracts.

### First Capability Set

- `studio.assistant.propose_service_design`
- `studio.assistant.propose_capability_formalization`
- `studio.assistant.propose_scenario_formalization`
- `studio.assistant.propose_runtime_policy_bindings`
- `studio.assistant.propose_input_contracts`
- `studio.assistant.explain_coverage_gaps`

### UI Surfaces

- [DeveloperServiceFormalizationView.vue](/Users/samirski/Development/codex/ANIP/studio/src/views/DeveloperServiceFormalizationView.vue)
- [DeveloperCapabilityFormalizationView.vue](/Users/samirski/Development/codex/ANIP/studio/src/views/DeveloperCapabilityFormalizationView.vue)
- [DeveloperScenarioFormalizationView.vue](/Users/samirski/Development/codex/ANIP/studio/src/views/DeveloperScenarioFormalizationView.vue)
- [DeveloperGovernanceBindingsView.vue](/Users/samirski/Development/codex/ANIP/studio/src/views/DeveloperGovernanceBindingsView.vue)
- [DeveloperCoverageView.vue](/Users/samirski/Development/codex/ANIP/studio/src/views/DeveloperCoverageView.vue)
- [DeveloperDefinitionView.vue](/Users/samirski/Development/codex/ANIP/studio/src/views/DeveloperDefinitionView.vue)

### Acceptance Criteria

- developer can get structured proposals for missing formalization fields
- coverage gaps can be explained with concrete next actions
- accepted proposals become normal deterministic Developer Definition state

## Phase 4: Shared Assistant Experience

### Objective

Make the same assistant service usable in both Studio and the dev portal without duplicating logic.

### Work

1. Define a shared assistant client module.
2. Keep request envelopes identical across Studio and dev portal.
3. Keep proposal rendering consistent across both surfaces.

### Rule

The dev portal must not get a second independent assistant logic stack.

## Phase 5: Evaluation And Refinement

### Objective

Make the assistant measurable and regression-testable.

### Required Evaluation Tracks

1. Proposal validity rate
2. Proposal acceptance rate
3. Clarification necessity rate
4. Time-to-first-draft reduction
5. Drift introduced by accepted assistant proposals
6. Generator/verifier success after accepted assistance

## Data Model Additions

The current project model should gain explicit assistant-facing types such as:

- `AssistantProposalEnvelope`
- `AssistantProposalItem`
- `AssistantPatchCandidate`
- `AssistantClarificationQuestion`
- `AssistantAcceptanceRecord`

These belong in the canonical Studio model, not only in UI-local state.

## Backend Work Items

### Deterministic Backend

Add:

- proposal persistence or transient proposal storage
- accept/reject/apply endpoints
- patch validation
- artifact target allowlists
- assistant audit logging

Do not add:

- direct assistant-to-artifact writes without acceptance

### Assistant Service

Extend the existing assistant path with:

- proposal-producing capabilities
- consistent response envelope
- bounded PM and Dev capability surface

## UI Work Items

### Shared Components

Introduce reusable components for:

- proposal cards
- clarification question cards
- diff/patch preview
- per-item accept/reject controls
- assistant next-step suggestions

### Important UX Rule

Assistant results should read as:

- proposed structured work

Not:

- hidden engine output
- magical auto-generated state

## Rollout Order

The correct rollout order is:

1. proposal envelope and acceptance infrastructure
2. PM requirements/scenario drafting
3. PM missing-info identification
4. Dev service/capability formalization help
5. drift and coverage explanation
6. shared dev-portal reuse

## What Not To Do

Do not:

- begin with a giant general-purpose Studio chat
- let the assistant own workflow state
- let prompts encode hidden project semantics
- make the assistant mandatory for normal Studio use

## Definition Of Done

This initiative is done when:

1. Studio manual mode remains complete
2. assistant mode materially reduces authoring effort
3. accepted assistant proposals persist through the same deterministic backend path as manual edits
4. generation and verification consume exactly the same canonical contract as before
5. Studio and dev portal share the same assistant system, not separate ones
