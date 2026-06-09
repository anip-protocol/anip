# Studio Assistant Capability Surface And Proposal Contract

Date: 2026-04-19

## Purpose

This document defines the bounded assistant capability surface and the structure of assistant outputs.

The objective is to make the assistant:

- useful
- bounded
- testable
- auditable
- deterministic at the persistence boundary

## Capability Groups

### PM Assist Capabilities

Initial PM-facing capabilities:

- `studio.assistant.propose_requirements`
- `studio.assistant.propose_scenarios`
- `studio.assistant.identify_missing_business_info`
- `studio.assistant.propose_actor_model`
- `studio.assistant.propose_business_areas`
- `studio.assistant.propose_non_goals`
- `studio.assistant.propose_success_criteria`
- `studio.assistant.suggest_next_step`

### Dev Assist Capabilities

Initial Developer-facing capabilities:

- `studio.assistant.propose_service_design`
- `studio.assistant.propose_capability_formalization`
- `studio.assistant.propose_scenario_formalization`
- `studio.assistant.propose_runtime_policy_bindings`
- `studio.assistant.propose_input_contracts`
- `studio.assistant.explain_coverage_gaps`
- `studio.assistant.explain_drift`
- `studio.assistant.suggest_next_step`

### Existing Explanation Capabilities

The repo already has explanation-oriented capabilities exposed through the Studio assistant path:

- `studio.assistant.explain_shape`
- `studio.assistant.explain_evaluation`
- `studio.assistant.interpret_project_intent`

These should be treated as the starting point, not the final shape.

## Capability Design Rules

Each assistant capability must be:

- explicit
- bounded
- named for a product action
- able to return structured output

Avoid:

- one generic `chat` capability
- one generic `draft_everything` capability
- a capability that decides project transitions by itself

## Request Envelope

Every assistant request should include:

- `project_id`
- `workspace_id`
- `assistant_mode`
  - `pm`
  - `dev`
- `current_surface`
  - for example:
    - `requirements`
    - `scenarios`
    - `service_design`
    - `developer_definition`
- `source_context`
  - source document excerpts
  - selected artifacts
  - selected scenarios
  - selected requirements
- `workflow_state`
  - current lock state
  - current phase
  - current validation status
- `user_prompt`
- `constraints`
  - optional bounded instructions from UI

The assistant should not re-derive these from vague prose if the backend already knows them.

## Response Envelope

Every assistant response should follow one envelope shape:

- `title`
- `summary`
- `mode`
- `capability`
- `questions_for_user`
- `watchouts`
- `next_steps`
- `proposal`

Where `proposal` is structured and type-specific.

## Proposal Types

### 1. Candidate Blocks

Use when the assistant drafts new artifact content.

Examples:

- candidate requirements
- candidate scenarios
- candidate business areas
- candidate service responsibilities

Shape:

```json
{
  "proposal_kind": "candidate_blocks",
  "artifact_type": "requirements",
  "items": [
    {
      "client_id": "temp-req-1",
      "title": "Requirement title",
      "body": "Structured body",
      "confidence": "high",
      "rationale": "Why this was proposed"
    }
  ]
}
```

### 2. Patch Candidates

Use when the assistant proposes modifications to an existing artifact.

Shape:

```json
{
  "proposal_kind": "patch_candidates",
  "artifact_type": "developer_definition",
  "patches": [
    {
      "path": "/capabilities/3/inputs/0",
      "op": "add",
      "value": {
        "input_name": "quarter",
        "input_type": "string",
        "required": true
      },
      "rationale": "This capability cannot be generated safely without an explicit quarter input."
    }
  ]
}
```

### 3. Clarification Questions

Use when the assistant cannot responsibly propose final structure without more information.

Shape:

```json
{
  "proposal_kind": "clarification_questions",
  "questions": [
    {
      "question_id": "clarify-1",
      "prompt": "Should account managers be limited to region-owned accounts or only receive masked results outside their region?",
      "why_it_matters": "This changes runtime policy bindings and expected restriction behavior.",
      "target_artifact": "permission_intent"
    }
  ]
}
```

### 4. Mixed Proposal

Use when a single operation needs:

- some concrete draft content
- plus explicit questions

That should still be one structured response, not a free-form essay.

## Acceptance Rule

The assistant response is not persisted directly.

The UI/backend should support:

- accept one item
- reject one item
- edit one item before accept
- accept all
- reject all

Acceptance should create normal deterministic artifact writes through existing validation rules.

## What The Assistant May Not Do

The assistant may not:

- lock a baseline
- change workflow state silently
- bypass schema validation
- bypass permissions
- write directly to stored artifacts without user acceptance
- hide unresolved ambiguity in prose

## What The Backend Must Enforce

The backend must enforce:

- schema validity
- artifact ownership rules
- lock rules
- allowed state transitions
- patch target validity
- patch path allowlist
- role permissions

## PM And Dev Mode Differences

The capability surface is shared, but the allowed artifact targets differ.

### PM Mode Target Artifacts

- source docs
- product summary
- actor model
- business areas
- permission intent
- non-goals
- success criteria
- scenarios
- service design

### Dev Mode Target Artifacts

- developer service formalization
- capability formalization
- data contract formalization
- scenario formalization
- runtime policy bindings
- verification expectations
- developer definition

## Evaluation Principle

Assistant quality should be evaluated on:

- usefulness of the proposals
- correctness of structured output
- rate of valid acceptance
- reduction in manual authoring effort
- absence of invalid silent writes

Not on:

- whether the assistant feels conversational
- whether it produces long explanations

The product value is accelerated structured authoring, not chat quality by itself.
