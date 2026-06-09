# 2026-05-28 Composition Contract Validation Plan

## Goal

Make Studio reject invalid composed-capability contracts before Developer Revision save, package export, registry publish, code generation, or LLM benchmark runs.

The immediate failure came from a fresh GTM Autopilot project whose generated contract passed Studio readiness but failed Phase 7 of the 350-question bank. The contract represented composed capabilities with syntactically valid JSONPath mappings, but semantically invalid mappings:

- `cohort_ref` was mapped directly into a child `target_ref`.
- Optional parent `target_ref` with `on_missing=omit` was mapped into a required child `target_ref`.

Those are generic contract modeling errors, not GTM-specific runtime failures.

## Non-Goals

- Do not patch GTM question-bank cases.
- Do not add GTM-specific planner hints.
- Do not weaken runtime clarification behavior.
- Do not bypass source-doc or developer-evidence flows.
- Do not introduce a new ANIP spec version unless existing `anip/0.24` fields prove insufficient.

## Design Principles

1. Composition metadata is contract truth.
2. A composed capability can hide internal steps from the agent, but it cannot hide unresolved required child inputs.
3. Parent-to-child input mapping must be type/semantic-compatible.
4. A provider-owned derived value must come from a prior composition step output, not from an unrelated parent input.
5. Autopilot can draft composition metadata, but save/package must be blocked by deterministic validation.
6. Provider-owned internal derivation is not automatically composition. If Studio cannot name valid child capabilities, valid mappings, and a supported authority boundary, the capability is atomic with provider-owned backend logic.

## Phase 1: Deterministic Composition Mapping Validator

Add generic validation to `validateDeveloperDefinitionRequiredFields(...)`.

Rules:

- Every `$.input.<name>` mapping must reference an existing parent capability input.
- Every mapped child input name must reference an existing child capability input.
- A required child input mapped from a parent input must be satisfied by one of:
  - a required parent input;
  - a parent input with safe missing behavior such as `use_default` or `use_actor_scope`;
  - a previous composition step output.
- A direct parent input mapping must reject clearly incompatible semantic classes.
- Entity/reference child inputs must not be mapped directly from cohort, time, scope, quantity, category, audience, or policy inputs.
- Step-output mappings remain allowed because they represent provider-owned derivation, but the step must be declared earlier.
- `kind=composed` is allowed only when the contract declares executable child steps. If a provider internally chooses a target, ranks candidates, or prepares a preview without exposing those as child ANIP capabilities under the supported authority boundary, the capability must remain `kind=atomic`.

Expected impact:

- `cohort_ref -> target_ref` fails.
- optional `target_ref(on_missing=omit) -> required child target_ref` fails.
- valid parent `account_ref(entity_reference) -> child target_ref(entity_reference)` remains valid.
- valid derived `$.steps.select_target.output.selected_target_ref -> child target_ref` remains valid.

## Phase 2: Evidence Scaffold Guidance

Update developer evidence scaffold README/CSV guidance so developers and AI helpers understand how to model derived values:

- Do not map cohort/scope/time inputs directly to concrete entity target inputs.
- Add a provider-owned selection/lookup step when a child requires a concrete entity derived from a cohort, ranking, bottleneck, forecast, or other broad input.
- Map the child concrete input from `$.steps.<step>.output.<field>`.
- If a child input can only be provided by the caller, keep it required and let Studio clarify.
- If no valid same-service child capability exists for the provider-owned selection/lookup, do not invent a composition. Mark the capability atomic and describe the provider-owned backend operation, produced effects, forbidden effects, approval policy, and output shape in runtime governance.

## Phase 3: Tests

Add focused tests:

- Reject parent `cohort_reference` mapped to child `entity_reference`.
- Reject optional parent input with `on_missing=omit` mapped to required child input.
- Accept prior-step output mapped to required child entity input.
- Preserve existing valid composition tests.

## Phase 4: Fresh GTM Repro Gate

After implementation:

1. Create a new Studio project from the 10 GTM business docs and filled developer evidence.
2. Run Autopilot to saved Product Revision and Developer Revision.
3. Confirm `Capability Formalization`, `Coverage`, `App Glue`, and `Developer Definition` show zero errors/warnings.
4. Export package.
5. Generate Python services.
6. Run Phase 7 first.
7. If Phase 7 passes, run full `350 + 140`.
8. Then regenerate and run against TypeScript, Go, Java, and C#.

Fresh GTM modeling expectations:

- `gtm.at_risk_followup_preparation`: composed only if it can declare same-service steps such as risk summary followed by follow-up preparation.
- `gtm.at_risk_reassignment_preparation`: composed only if it can declare same-service steps such as risk summary followed by reassignment preparation.
- `gtm.prioritized_routing_preparation`: composed only if it declares the prioritization step before routing and maps only valid parent inputs or prior step outputs.
- Outreach capabilities that derive a target internally but do not have a valid same-service target-selection child capability remain atomic/provider-owned. They must not fake composition by mapping `cohort_ref` or optional `target_ref` into a required child `target_ref`.

## Release Gate

This issue is closed only when:

- invalid composed mappings are blocked deterministically;
- fresh GTM package cannot be exported with the bad mappings;
- fresh GTM generated Python passes Phase 7;
- full GTM bank passes after Phase 7 passes.
