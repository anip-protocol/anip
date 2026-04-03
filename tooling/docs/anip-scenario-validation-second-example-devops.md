# ANIP Scenario Validation: Second Worked Example (DevOps)

## Purpose

This is the second full worked example of ANIP’s scenario-validation system.

It follows the same structure as the travel example:

1. requirements
2. proposed structure
3. scenario
4. evaluation

The domain is devops because it is excellent for:

- authority-sensitive actions
- irreversible or high-risk operations
- clear escalation needs
- strong audit and lineage value

## The Question

The system we are evaluating should answer:

> Can an agent safely handle a high-risk infrastructure action when the caller lacks sufficient authority, without relying on blind retries or bespoke escalation glue?

That is a very real modern agent problem.

It is also one of the best places to show the difference between:

- a callable interface
- and a governed execution interface

## Step 1: Requirements

Below is a plausible `requirements.yaml`.

```yaml
system:
  name: devops-operations-service
  domain: devops
  deployment_intent: internal_control_surface

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
  grantable_requirements: true

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
    list_clusters:
      side_effect: none
    delete_cluster:
      side_effect: irreversible
      high_risk: true
      recovery_guidance_required: true

business_constraints:
  production_cluster_deletion_requires_strong_authority: true
  blocked_high_risk_actions_should_escalate_cleanly: true
  repeated_blind_retry_is_unacceptable: true

scale:
  shape_preference: production_single_service
  high_availability: false
```

## Step 2: Proposed Structure

Below is the proposed `proposal.yaml` for the Approach artifact.

```yaml
proposal:
  recommended_shape: production_single_service

  rationale:
    - internal HTTP control surface is sufficient
    - durable audit and lineage are required
    - permission discovery is critical before destructive actions
    - no separate worker split is necessary yet

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
    - checkpoint_worker
    - embedded_studio

  key_runtime_requirements:
    - expose high-risk irreversible posture for delete_cluster
    - support permission discovery before invocation
    - distinguish restricted vs denied
    - preserve task and invocation lineage
    - return structured failure with escalation-friendly recovery data

  anti_pattern_warnings:
    - do_not_rely_on_delete_then_parse_error
    - do_not_hide_authority_requirements_only_in_docs
    - do_not_push_lineage_only_into_logs

  expected_glue_reduction:
    safety:
      - destructive_action_wrapper_glue
      - blind_retry_glue
    orchestration:
      - ad_hoc_escalation_branches
    observability:
      - incident_trace_stitching
      - action_chain_reconstruction
```

## Step 3: Scenario

Below is the scenario definition.

```yaml
scenario:
  name: delete_production_cluster_without_permission
  category: safety

  narrative: >
    An agent is operating on behalf of an engineer. The engineer can inspect
    clusters but does not hold authority to delete a production cluster.
    The agent is asked to delete cluster prod-eu-1.

  context:
    capability: delete_cluster
    target: prod-eu-1
    side_effect: irreversible
    risk: high
    token_scope:
      - clusters:read
    permissions_state: denied
    task_id: incident-cleanup-2026-03
    client_reference_id: step-7-delete
    parent_invocation_id: inv-a1b2c3d4e5f6

  expected_behavior:
    - do_not_execute
    - do_not_retry_blindly
    - explain_authority_gap
    - preserve_task_identity
    - preserve_parent_invocation_lineage
    - produce_audit_entry
    - suggest_escalation_or_human_hand_off

  expected_anip_support:
    - permission_discovery
    - irreversible_side_effect_visibility
    - structured_failure
    - resolution_guidance
    - task_id_support
    - parent_invocation_id_support
    - audit_queryability
```

## Step 4: Evaluation

## Evaluation Result

**Scenario:** `delete_production_cluster_without_permission`  
**Result:** `HANDLED`

### Summary

This proposed ANIP design is strong enough to handle the scenario cleanly.

The scenario’s core requirement is not:

- “delete the cluster”

It is:

- “correctly refuse the destructive action, explain why, preserve lineage, and support escalation without blind retries”

That is exactly the kind of scenario ANIP is well suited to handle.

## Handled by ANIP

### 1. Pre-execution authority understanding

The design supports permission discovery before invoke.

That means the agent can know:

- it lacks the required authority
- the action is high-risk
- the action is irreversible

This removes a large amount of destructive-action wrapper glue.

### 2. Correct blocked-action behavior

With structured failures and recovery guidance, the system can:

- refuse execution
- explain the authority gap
- avoid blind retry
- recommend escalation or human handoff

This removes a large amount of blocked-action orchestration glue.

### 3. Observability and incident reconstruction

With:

- `invocation_id`
- `client_reference_id`
- `task_id`
- `parent_invocation_id`
- durable audit

the system can reconstruct how the action request arose and why it was blocked.

This removes a large amount of observability glue.

## Glue You Will Still Write

### Result

**Handled by ANIP**

### Remaining custom logic

- you may still write organization-specific approval workflow logic if escalation goes into a real ticketing or approval system
- you may still write post-escalation operational process logic outside ANIP

These are acceptable because they are not the core scenario gap.

The core scenario behavior is already handled cleanly by the ANIP design.

## Glue Category

- minimal orchestration glue outside the protocol

## Why This Is A Full Pass

This scenario is a full pass because the core question is:

> Can the system safely refuse a destructive action without authority and behave usefully afterward?

The answer is yes.

The design does not need a bespoke wrapper just to:

- understand the authority problem
- avoid execution
- avoid blind retry
- preserve traceability

That is exactly what `HANDLED` should mean.

## What Would Make It Even Stronger

The scenario is already handled, but these additions could improve operator
experience:

- explicit approval-aware declarations
- stronger escalation vocabulary
- tighter integration with org-specific approval systems

Those are improvements, not prerequisites for passing the scenario.

## Evaluation Output As Structured Markdown

```md
# Evaluation: delete_production_cluster_without_permission

Result: HANDLED

Handled by ANIP:
- permission discovery
- high-risk side-effect visibility
- structured blocked-action failure
- escalation-friendly recovery guidance
- task identity
- parent invocation lineage
- durable audit

Glue you will still write:
- you may still write organization-specific approval workflow integration here

Glue category:
- orchestration

Why:
- the core scenario is safe refusal with explainability and traceability, and
  the proposed ANIP design already provides those capabilities

What would improve the result:
- approval-aware declarations
- tighter approval-system integration
```

## Why This Example Matters

This example complements the travel example well.

The travel case showed:

- `PARTIAL`

because ANIP improved the decision surface but did not yet make the key
constraint enforceable.

The devops case shows:

- `HANDLED`

because the main requirement is safe refusal and clean escalation, which ANIP
can already support well.

That contrast is very important.

It shows the scenario system is not biased toward:

- always passing
- or always failing

It can distinguish:

- fully handled
- partially handled
- still requires glue

## What Studio Could Become Here

In a future Studio evolution, this scenario could appear as:

- a saved devops scenario pack
- a design proposal preview
- a validation result card
- a glue-gap summary

A user could see:

- requirements
- proposed shape
- scenario status: `HANDLED`
- remaining external orchestration points

That would make Studio much more than a protocol viewer.
It would make it a design validation workspace.

## Final Summary

This worked example shows what a full pass looks like.

The system:

- understands enough before acting
- blocks the action correctly
- avoids blind retry
- explains the failure
- preserves lineage
- records the event durably

That is exactly the kind of scenario ANIP should be able to handle cleanly.
