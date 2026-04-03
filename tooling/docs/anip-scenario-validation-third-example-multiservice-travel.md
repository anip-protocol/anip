# ANIP Scenario Validation: Third Worked Example (Multi-Service Travel)

## Purpose

This is the first full multi-service worked example for ANIP’s
Scenario-Driven Execution Design method.

It is meant to show where the ANIP story becomes most compelling:

- multiple services
- split authority
- split responsibility
- cross-service lineage
- cross-service audit reconstruction
- less bespoke orchestration and observability glue

This is a stronger realism test than the earlier single-service examples.

## The Question

The system we are evaluating should answer:

> Can an agent safely move from planning in one service to booking in another service, while preserving task identity, invocation lineage, and useful auditability, without forcing the team to build bespoke cross-service glue?

That is a very realistic agent-system question.

In practice, this is where teams often end up building:

- handoff wrappers
- cross-service correlation IDs
- orchestration branches
- policy glue
- custom traces just to understand what happened

That is exactly what this example is designed to expose.

## Services In Scope

This example uses two ANIP services.

### Service A: `travel-search`

Responsibilities:

- search flights
- compare options
- return candidate itineraries

Risk profile:

- mostly read-like
- low side-effect

### Service B: `travel-booking`

Responsibilities:

- book a chosen flight
- create an irreversible reservation
- enforce stricter authority and budget-sensitive behavior

Risk profile:

- irreversible side effect
- cost-bearing action
- stronger audit importance

This split is intentionally realistic:

- one service helps the agent decide
- another service performs the risky action

## Step 1: Requirements

Below is a plausible `requirements.yaml`.

```yaml
system:
  name: travel-multiservice-estate
  domain: travel
  deployment_intent: multi_service_agent_execution

services:
  - name: travel-search
    role: planning
    public_http: true
  - name: travel-booking
    role: execution
    public_http: true

transports:
  http: true
  stdio: false
  grpc: false

trust:
  mode: signed
  checkpoints: false

auth:
  delegation_tokens: true
  purpose_binding: true
  scoped_authority: true
  service_to_service_handoffs: true

permissions:
  preflight_discovery: true
  restricted_vs_denied: true
  grantable_requirements: true

audit:
  durable: true
  searchable: true
  cross_service_reconstruction_required: true

lineage:
  invocation_id: true
  client_reference_id: true
  task_id: true
  parent_invocation_id: true
  cross_service_continuity_required: true

risk_profile:
  service_a:
    search_flights:
      side_effect: none
  service_b:
    book_flight:
      side_effect: irreversible
      cost_visibility_required: true
      recovery_guidance_required: true

business_constraints:
  agent_must_compare_before_booking: true
  booking_budget_limit_required: true
  booking_service_must_be_auditable_independently: true
  cross_service_action_chain_must_be_reconstructable: true

scale:
  shape_preference: multi_service_estate
  high_availability: false
```

## What These Requirements Imply

This already tells us a lot:

- the system is not one ANIP service
- planning and execution are intentionally split
- cross-service lineage matters
- booking must be independently auditable
- task continuity matters across service boundaries

That is exactly where ordinary agent designs start accumulating glue.

## Step 2: Proposed Structure

Below is the proposed `proposal.yaml`.

```yaml
proposal:
  recommended_shape: multi_service_estate

  rationale:
    - planning and booking are split across service boundaries
    - each service needs its own audit integrity
    - cross-service lineage is a hard requirement
    - one monolith would reduce realism and hide the handoff problem

  service_shapes:
    travel-search:
      shape: production_single_service
    travel-booking:
      shape: production_single_service

  shared_requirements:
    - task_id propagation across services
    - parent_invocation_id propagation across service hops
    - durable audit in both services
    - searchable audit in both services
    - consistent delegation and purpose semantics

  required_components:
    - manifest_generator_per_service
    - token_verifier_per_service
    - permission_evaluator_per_service
    - invocation_executor_per_service
    - failure_mapper_per_service
    - durable_audit_store_per_service
    - lineage_recorder_per_service
    - handoff_propagation_rules

  optional_components:
    - shared_search_layer_for_audit_views
    - central_aggregated_lineage_index
    - external_policy_service
    - approval_service

  key_runtime_requirements:
    - search results should be linkable to later booking actions
    - booking failures should preserve parent invocation lineage
    - task identity should survive cross-service execution
    - each service should remain independently auditable

  anti_pattern_warnings:
    - do_not_rely_on_custom_headers_as_the_primary_lineage_surface
    - do_not_push_cross_service_correlation_only_into_logs
    - do_not_make_booking_service_depend_on_search_service_local_state
    - do_not_hide_handoff_logic_only_in_wrapper_code

  expected_glue_reduction:
    safety:
      - cross_service_permission_probe_glue
      - invoke_then_fail_booking_glue
    orchestration:
      - planning_to_booking_wrapper_glue
      - parent_child_handoff_glue
    observability:
      - cross_service_trace_stitching
      - workflow_reconstruction_across_services
```

## What This Proposal Is Saying

The proposal is deliberately conservative.

It does **not** say:

- build one giant control plane now
- build a workflow engine
- centralize everything

It says:

- keep both services as real services
- require consistent lineage and audit semantics across them
- make cross-service handoff a first-class design concern

That is realistic and aligned with ANIP’s current posture.

## Step 3: Scenario

Below is the scenario definition.

```yaml
scenario:
  name: search_then_book_across_services_with_budget_constraint
  category: orchestration

  narrative: >
    An agent searches for flights in the search service, selects the cheapest
    viable result, then attempts to book that flight through the booking
    service. The chosen option costs 800 USD while the user’s practical budget
    limit is 500 USD. The system must preserve task identity and parent/child
    invocation lineage across the service boundary.

  context:
    task_id: trip-q2-customer-42
    parent_search_invocation_id: inv-a1b2c3d4e5f6
    selected_capability_service_a: search_flights
    selected_capability_service_b: book_flight
    selected_flight: DL310
    selected_cost: 800
    budget_limit: 500
    token_scope_service_a:
      - flights:search
    token_scope_service_b:
      - flights:book
    side_effect_service_b: irreversible

  expected_behavior:
    - search_service_returns_candidates
    - booking_service_receives_task_identity
    - booking_service_receives_parent_invocation_lineage
    - system_does_not_execute_blindly_if_budget_control_exists
    - both_services_produce_useful_audit_entries
    - operator_can_reconstruct_the_cross_service_chain

  expected_anip_support:
    - permission_discovery
    - side_effect_visibility
    - cost_visibility
    - task_id_support
    - parent_invocation_id_support
    - audit_queryability
    - structured_failure
```

## What This Scenario Is Really Testing

This scenario is not merely:

- can Service A call Service B

It is testing whether the design can avoid common cross-service glue:

- carrying custom correlation headers between services
- inventing ad hoc parent/child trace rules
- stitching logs manually to reconstruct the chain
- wrapping the booking step in a large bespoke orchestration layer

That is what makes this a strong ANIP demo case.

## Step 4: Evaluation

## Evaluation Result

**Scenario:** `search_then_book_across_services_with_budget_constraint`  
**Result:** `PARTIAL`

### Summary

This design is meaningfully stronger than a normal multi-service tool-calling
setup, and it removes a lot of cross-service observability and orchestration
glue.

But it does **not** fully solve the scenario unless the budget constraint is
represented in an enforceable control surface visible to the booking path.

So the correct result is:

- `PARTIAL`

not:

- `HANDLED`

## Handled by ANIP

### 1. Cross-service lineage continuity

The design can preserve:

- `task_id`
- `parent_invocation_id`
- per-service `invocation_id`
- per-service audit records

That is a major improvement.

Without this, teams usually build:

- custom correlation headers
- tracing tags
- orchestration-local IDs
- separate reconstruction tooling

ANIP removes a large amount of that observability glue.

### 2. Independent yet linkable audit surfaces

Both services can remain independently auditable while still contributing to a
shared task narrative.

That is very important in real multi-service systems.

It means:

- Service A can audit search
- Service B can audit booking
- operators can still connect the action chain

without building as much bespoke stitching logic.

### 3. Cleaner planning-to-execution handoff

The design can carry enough execution context from the planning step to the
booking step that the handoff does not become a pure custom wrapper boundary.

That removes a meaningful amount of orchestration glue.

## Glue You Will Still Write

### Result

**Still requires glue**

### Glue you will still write

- you will still write budget-enforcement logic unless the budget limit is represented in delegation, permission evaluation, or another ANIP-visible control surface in the booking path
- you will still write handoff policy logic if the booking service must interpret planning outputs under organization-specific rules
- you may still write a small cross-service aggregation layer if operators need one unified search view rather than per-service audit queries

## Glue Category

- safety
- orchestration
- some observability glue outside the protocol

## Why This Is Partial Rather Than Full

This design already solves a large part of the multi-service problem:

- lineage is much cleaner
- audit is much cleaner
- handoff semantics are much cleaner

That alone is a big deal.

But the core safety question in this scenario is still:

> does the system reliably stop an over-budget booking across the service boundary without depending on bespoke logic?

If budget is not represented as an enforceable control surface, the answer is:

- not yet

So the scenario is:

- meaningfully improved
- but not fully solved

That is exactly what `PARTIAL` should capture.

## What Would Improve The Result

This scenario would move closer to `HANDLED` if:

### 1. Budget became enforceable in the booking path

Examples:

- budget carried in delegation purpose or bound policy
- permission discovery reflects budget-based blocking
- booking invoke returns a structured pre-side-effect budget block

### 2. Cross-service lineage queries became easier

Examples:

- shared lineage-aware search across service audits
- aggregated task-chain inspection layer

This is not required for ANIP to help, but it would reduce the remaining
observability glue further.

### 3. Handoff policy became more explicit

Examples:

- stronger composition hints
- more explicit handoff contracts between planning and execution services

That would reduce orchestration glue further.

## Evaluation Output As Structured Markdown

```md
# Evaluation: search_then_book_across_services_with_budget_constraint

Result: PARTIAL

Handled by ANIP:
- cross-service task identity continuity
- parent invocation lineage
- independent but linkable audit records
- cleaner planning-to-booking handoff
- structured failure surfaces

Glue you will still write:
- you will still write budget-enforcement logic in the booking path
- you will still write some organization-specific handoff policy logic
- you may still write a cross-service audit aggregation layer

Glue category:
- safety
- orchestration
- observability

Why:
- ANIP removes a large amount of cross-service correlation and trace-stitching
  glue, but the budget-control requirement is still not fully encoded as an
  enforceable ANIP-visible control surface

What would improve the result:
- enforceable budget control in delegation or permissions
- easier cross-service lineage query support
- clearer planning-to-execution composition hints
```

## Why This Example Is A Stronger Demo Than Single-Service

This is where the ANIP story becomes harder to dismiss.

Single-service examples can still sound like:

- better API design
- richer metadata

This example shows:

- cross-service task continuity
- cross-service auditability
- cross-service glue reduction

That is much closer to what real teams struggle with.

It makes the ANIP value more visible because it targets:

- service boundaries
- lineage loss
- orchestration glue
- observability glue

all at once.

## What Studio Could Become Here

This is probably where Studio starts becoming something much more ambitious.

A future Studio could support:

### 1. Multi-service system modeling

The user defines:

- several services
- their roles
- shared lineage requirements
- audit expectations
- trust posture

### 2. Proposal view

Studio proposes:

- recommended deployment shape
- required capabilities per service
- shared lineage requirements
- anti-pattern warnings

### 3. Scenario runner

The user picks:

- canonical multi-service scenarios
- or uploads their own

Studio evaluates:

- handled / partial / requires glue

### 4. Glue Gap Analysis

Studio highlights:

- what ANIP covers already
- what glue still remains
- where the cross-service gaps are

At that point Studio is no longer just:

- a manifest viewer
- an invoke console

It becomes:

- a design and execution validation workspace

That is a much bigger and more interesting future.

## Final Summary

This first multi-service worked example shows why the methodology matters.

The proposal is already strong enough to remove a lot of:

- cross-service correlation glue
- trace-stitching glue
- handoff wrapper glue

But it still exposes the remaining truth:

- some critical enforcement logic is still outside the protocol-visible design

That is exactly the kind of honest, useful answer this system should produce.
