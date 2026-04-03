# ANIP Scenario Validation: First Worked Example

## Purpose

This document is a full first example of the scenario-validation system.

It shows one complete loop:

1. requirements are captured
2. a proposed ANIP structure is produced
3. a scenario is evaluated against that structure
4. the output identifies what ANIP covers and what glue still remains

This example uses the travel domain because it is:

- easy to understand
- already present in ANIP showcase form
- strong enough to demonstrate safety, orchestration, and observability value

## The Question

The system we are evaluating should answer:

> Can an agent safely handle flight booking with budget constraints and produce a useful audit trail without bespoke glue?

That is a concrete, real question.

This is exactly the kind of thing teams end up wrapping in:

- preflight checks
- budget guards
- escalation logic
- custom tracing

The point of the scenario system is to expose whether ANIP actually removes
those layers or whether the team still has to write them.

## Step 1: Requirements

Below is a plausible first `requirements.yaml`.

```yaml
system:
  name: travel-booking-service
  domain: travel
  deployment_intent: public_http_service

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

permissions:
  preflight_discovery: true
  restricted_vs_denied: true

audit:
  durable: true
  searchable: true

lineage:
  invocation_id: true
  client_reference_id: true
  task_id: true
  parent_invocation_id: true

risk_profile:
  capabilities:
    search_flights:
      side_effect: none
    book_flight:
      side_effect: irreversible
      cost_visibility_required: true
      recovery_guidance_required: true

business_constraints:
  booking_budget_limit_required: true
  over_budget_actions_must_not_execute: true
  blocked_actions_should_escalate_cleanly: true

scale:
  shape_preference: production_single_service
  high_availability: false
```

## Why These Requirements Matter

This is not an abstract service.

The requirements already imply:

- the service must support delegated authority
- the caller must be able to inspect permissions before execution
- booking is irreversible and cost-sensitive
- audit and lineage are important
- the system must help stop over-budget actions before blind execution

That is enough to make this a strong first ANIP design case.

## Step 2: Proposed Structure

Below is the proposed `proposal.yaml` that a first ANIP structure planner could
produce.

```yaml
proposal:
  recommended_shape: production_single_service

  rationale:
    - public HTTP surface is required
    - durable audit and searchable execution history are required
    - signed trust is sufficient; checkpoints are not required
    - one service boundary is enough for the current domain

  required_components:
    - capability_registry
    - manifest_generator
    - token_verifier
    - delegation_engine
    - permission_evaluator
    - invocation_executor
    - failure_mapper
    - durable_audit_store
    - lineage_recorder
    - http_adapter

  optional_components:
    - token_issuer
    - embedded_studio
    - graphql_adapter
    - rest_adapter
    - mcp_adapter

  key_runtime_requirements:
    - expose side_effect posture for book_flight
    - expose cost metadata for book_flight
    - support permission discovery before invoke
    - persist invocation_id, client_reference_id, task_id, parent_invocation_id
    - return structured failures with recovery guidance

  anti_pattern_warnings:
    - do_not_leave_budget_reasoning_only_in_prompt_logic
    - do_not_rely_on_invoke_then_fail_as_primary_permission_model
    - do_not_push_lineage_only_into_logs

  expected_glue_reduction:
    safety:
      - permission_wrapper_glue
      - invoke_then_fail_budget_glue
      - blocked_action_recovery_glue
    orchestration:
      - some_preflight_wrapper_logic
    observability:
      - correlation_id_stitching
      - audit_reconstruction_logic
```

## What This Proposal Is Saying

The proposed structure is intentionally modest.

It is **not** saying:

- build a control plane
- split policy from execution
- create a workflow engine

It is saying:

- one production-grade ANIP service is enough
- but it must actually expose the ANIP semantics needed for safe booking

That is a realistic first recommendation.

## Step 3: Scenario

Now we test that proposal against one real scenario.

Below is the scenario definition.

```yaml
scenario:
  name: book_flight_over_budget
  category: safety

  narrative: >
    An agent is helping a user plan travel. The user has delegated booking
    authority, but only within a practical budget boundary of 500 USD.
    A candidate flight costs 800 USD.

  context:
    capability: book_flight
    side_effect: irreversible
    expected_cost: 800
    budget_limit: 500
    token_scope:
      - flights:book
    permissions_state: available
    task_id: trip-planning-q2
    client_reference_id: step-3-book
    parent_invocation_id: inv-a1b2c3d4e5f6

  expected_behavior:
    - do_not_execute
    - explain_budget_conflict
    - preserve_task_identity
    - preserve_parent_invocation_lineage
    - produce_audit_entry
    - prefer_escalation_or_replan_over_blind_retry

  expected_anip_support:
    - cost_visibility
    - side_effect_visibility
    - structured_failure
    - task_id_support
    - parent_invocation_id_support
    - audit_queryability
```

## What This Scenario Is Really Testing

This scenario is not just checking whether a booking API returns an error.

It is checking whether the design can avoid common glue patterns:

- a custom budget wrapper around every booking call
- prompt-level instructions telling the agent not to overspend
- blind invoke and retry behavior
- a separate trace-stitching layer for the task flow

That is exactly what makes it useful.

## Step 4: Evaluation

Below is what the first evaluator output should look like.

## Evaluation Result

**Scenario:** `book_flight_over_budget`  
**Result:** `partially_handled`

### Summary

The proposed ANIP structure is strong enough to remove a meaningful amount of
glue, but it does **not** fully solve the scenario by itself unless the budget
constraint is represented in a real enforcement surface.

ANIP can already cover:

- visibility of booking side effects
- visibility of expected or actual cost
- permission discovery before execution
- structured failure output
- task and invocation lineage
- durable audit recording

But the design still needs one more layer to make “do not execute over budget”
truly reliable.

## What ANIP Handles Cleanly

### 1. Action understanding before execution

The design can expose:

- `book_flight` is irreversible
- booking carries cost semantics
- the caller has booking authority

That removes a large amount of blind-action glue.

### 2. Recovery and explanation after a blocked action

If the runtime returns a structured failure such as a budget or policy block,
the agent can:

- explain why it did not proceed
- preserve lineage in the audit trail
- escalate or replan instead of retrying blindly

That removes a large amount of blocked-action recovery glue.

### 3. Observability and reconstruction

With:

- `invocation_id`
- `client_reference_id`
- `task_id`
- `parent_invocation_id`

the system can reconstruct what happened without custom trace stitching.

That removes a large amount of observability glue.

## What Still Requires Glue

This is the most important section.

### Result

**Still requires glue**

### Glue you will still write

- you will still write budget-policy enforcement unless the budget limit is represented in delegation, permission evaluation, or a protocol-visible control layer
- you will still write approval or escalation routing if the organization requires a human to approve over-budget bookings
- you may still write comparison/replanning logic if the agent must search for cheaper alternatives before escalation

### Glue category

- safety glue
- some orchestration glue

## Why It Is Not A Full Pass Yet

The scenario says:

> do not execute when cost is 800 and the budget limit is 500

If ANIP only exposes cost and side-effect posture, the agent is better
informed, but the system still depends on:

- model reasoning
- wrapper logic
- external policy logic

That is an improvement, but it is not a full guarantee.

So the correct evaluator result is not:

- `handled_by_anip`

It is:

- `partially_handled`

That honesty is exactly what makes the system credible.

## What Would Turn This Into A Full Pass

This scenario would move closer to:

- `handled_by_anip`

if one of the following became true:

### Option 1: Budget is part of enforceable authority

Examples:

- delegation or purpose binding carries budget constraints
- permission discovery can report the booking as blocked under the current budget

### Option 2: Policy is surfaced cleanly through ANIP-visible failure/recovery

Examples:

- invoke returns a structured `budget_exceeded` or equivalent block before side effects happen
- recovery guidance says replan or escalate

### Option 3: Scenario scope is weakened

If the scenario changes from:

- “the system must prevent over-budget execution”

to:

- “the system should inform the agent of cost before execution”

then the current ANIP structure is much closer to a full pass.

## Evaluation Output As Structured Markdown

This is what a v1 evaluator could literally emit:

```md
# Evaluation: book_flight_over_budget

Result: PARTIAL

Handled by ANIP:
- side-effect visibility
- cost visibility
- permission discovery
- structured failure
- task identity
- parent invocation lineage
- audit recording

Glue you will still write:
- budget enforcement logic
- approval or escalation routing
- fallback replanning logic

Glue category:
- safety
- orchestration

Why:
- ANIP improves the decision surface, but this design does not yet make the
  budget limit an enforceable protocol-visible constraint.
```

## Why This Example Is Valuable

This worked example proves what the scenario-validation system is for.

It does **not** just say:

- here is a recommended ANIP shape

It says:

- here is what ANIP already solves
- here is what it does not solve yet
- here is the glue the team would still write

That is the right output.

## What Studio Could Become

This is where Studio gets interesting.

Today, Studio is mostly:

- inspection
- invocation
- permissions
- audit viewing

With scenario validation, Studio could evolve into something broader:

### 1. Requirements workspace

The user defines:

- transport needs
- trust posture
- audit expectations
- lineage expectations
- scale assumptions

### 2. Structure proposal view

Studio proposes:

- deployment shape
- required components
- optional components
- anti-pattern warnings

### 3. Scenario pack runner

Studio lets the user:

- pick canonical scenarios
- add custom scenarios
- run evaluation against the proposal

### 4. Glue-gap report

Studio highlights:

- handled by ANIP
- partially handled
- still requires glue
- which glue category remains

That would make Studio more than a protocol inspector.
It would make it an ANIP design and validation cockpit.

## Final Summary

This first worked example shows the intended system clearly:

- requirements describe the target system
- the proposal suggests a valid ANIP structure
- the scenario tests that structure against reality
- the evaluation exposes remaining glue

That is the real point.

The planner helps.
The scenario reveals truth.
The evaluation tells the team whether they are actually removing glue or just
moving it around.
