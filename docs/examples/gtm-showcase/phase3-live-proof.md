# GTM Showcase Phase 3 Live Proof

This document records the first live Phase 3 proof on the GTM showcase stack.

The goal of this slice was not packaging polish. It was to prove that the same
bounded GTM services can now behave differently for different actors while
remaining governed, auditable, and regression-tested.

Studio now also has a generic approval review surface and generic actor-policy
export support, so the actor-aware runtime proof is no longer visible only in
service code and regression artifacts.

## What Was Added

- actor profiles in the live GTM runtime
- actor-aware token issuance into the generated ANIP services
- service-layer role-aware data shaping
- service-layer explicit `restricted` outcomes for conflicting actor scope
- role-aware follow-up preparation denial vs approval stop
- durable approval request creation and approval transition
- role-aware enrichment and lookalike access
- audit query surface through the live ANIP audit endpoint
- Studio-facing approval review surface for linked service endpoints
- Studio Developer Spec exports that make actor identity, authority, and audit expectations explicit

## Actor Profiles Used

- `sales_leader`
  - company-wide pipeline scope
  - full financial visibility
  - full enrichment visibility
  - can prepare follow-up work
  - can approve follow-up work
  - can use lookalike analysis

- `account_manager_east`
  - East-only pipeline scope
  - full financial visibility inside that scope
  - bounded enrichment visibility
  - can prepare follow-up work
  - cannot approve follow-up work
  - can use lookalike analysis

- `sales_analyst`
  - company-wide analytical scope
  - masked financial values
  - bounded enrichment visibility
  - cannot prepare follow-up work
  - cannot approve follow-up work
  - cannot use lookalike analysis

- `rev_ops_manager`
  - company-wide pipeline scope
  - full financial visibility
  - full enrichment visibility
  - can prepare follow-up work
  - cannot approve follow-up work
  - can use lookalike analysis

## What Was Proven

### Same question, different actor, different safe result

The actor-aware regression suite proved:

- `sales_leader` asking for top at-risk accounts gets the company-wide result
  with financial values intact
- `sales_analyst` asking the same question gets the same bounded ranking shape,
  but financial values are masked
- `account_manager_east` asking for top at-risk accounts is automatically
  bounded to East-scope accounts
- `account_manager_east` explicitly asking for West-region at-risk accounts gets
  `restricted` instead of silently receiving broader company scope

### Same action, different authority

- `sales_analyst` asking to prepare follow-up tasks gets `denied`
- `rev_ops_manager` asking the same question gets `approval_required`
- the pipeline service creates a durable `approval_request_id` for the
  `rev_ops_manager` request
- `sales_leader` can approve that exact request and the request transitions to
  `approved`

### Same enrichment domain, different permission posture

- `sales_analyst` can receive bounded enrichment summaries with sensitive
  fields masked
- `sales_analyst` cannot use `gtm.lookalike_accounts`
- `sales_leader` can use `gtm.lookalike_accounts` successfully

### Auditability

The live runtime can query audit entries through the ANIP audit endpoint for a
specific actor and service. The regression suite now verifies more than entry
existence. It asserts the latest audited outcome for selected cases, including:

- actor identity preserved in `root_principal`
- success vs failure posture
- specific governed failure types such as `restricted`, `denied`, and `approval_required`
- signed audit entries on the live runtime path

The regression suite verified that actor-scoped audit entries exist for:

- `sales_leader` on `gtm.account_risk_summary`
- `sales_leader` on `gtm.lookalike_accounts`

For approval behavior, the regression suite now also checks that:

- the approval request is visible in the pending approval surface before approval
- the request transitions to `approved`
- the approved record preserves requester, approver, and required-role semantics

## Regression Result

Live Phase 3 regression:

- `9 / 9` passed

Saved artifacts:

- [gtm_phase3_llm_runtime-2026-04-13T04-55-48Z.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/regression-runs/gtm_phase3_llm_runtime-2026-04-13T04-55-48Z.md)
- [gtm_phase3_llm_runtime-latest.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/regression-runs/gtm_phase3_llm_runtime-latest.md)

The critical result is:

- Phase 1 remained green: `22 / 22`
- Phase 2 remained green: `9 / 9`
- Phase 3 actor-aware regression is green: `9 / 9`

So the realism jump did not break the earlier bounded-service proof.

## Why This Matters

This is where the showcase starts looking production-real.

It now proves:

- business-defined behavior
- Studio-generated bounded services
- live multi-service execution
- actor-aware governed differences
- auditable outcomes
- repeatable regression evidence

That is materially stronger than a generic GTM demo.
