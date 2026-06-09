# GTM Showcase Phase 4 Live Proof

This document records the first live Phase 4 proof on the GTM showcase stack.

The goal of this slice was to prove that ANIP can front an existing REST-backed
prioritization system without turning the agent runtime into a prompt-owned
scoring or routing workflow.

This is the first live service in the showcase that is not a direct data-access
surface over the GTM warehouse. Instead, it is:

- a Studio-generated Application Integration design
- a live REST backend with bounded scoring and routing operations
- an ANIP wrapper service in front of that backend
- a thin LLM runtime consuming the ANIP contract

## What Was Added

- `gtm-prioritization-backend`
  - deterministic REST backend for scoring, prioritization, and routing preview
- `gtm-prioritization-service`
  - native ANIP service generated from the Studio application-integration path
- live Compose wiring for the third GTM business service
- LLM runtime catalog loading for the third service
- Phase 4 regression suite for:
  - bounded scoring reads
  - bounded account prioritization
  - clarification on underspecified cohorts
  - approval-gated routing
  - routing denial for unauthorized actors

## Capabilities Now Live

- `gtm.score_leads`
- `gtm.prioritize_accounts`
- `gtm.route_leads`

These capabilities are exposed through `anip-gtm-prioritization-showcase`.

## What Was Proven

### Cube-backed aggregate reads without changing the ANIP contract

Before moving to Phase 5, the pipeline service was tightened so aggregate-heavy
pipeline summaries now execute through Cube instead of direct warehouse SQL.

The important boundary did not change:

- dbt still owns joins and modeling
- Cube now owns the reusable aggregate read path for `gtm.pipeline_summary`
- the ANIP service still owns clarification, restriction, denial, approval, actor policy, and audit

The regression harness stayed on the same external contract and remained green.
That is the right proof for this migration: semantic execution moved, governed
behavior did not.

### ANIP in front of an existing REST backend

The prioritization backend is a separate REST service with its own internal
objects and operations.

The ANIP service sits in front of it and owns:

- actor-aware scope enforcement
- clarification on missing cohort or route target
- bounded output shape
- denial for unsupported ranking or outreach behavior
- approval-gated routing preview
- auditability through the ANIP audit endpoint

That matters because it proves the showcase is not limited to greenfield ANIP
data-access services. ANIP can also govern existing REST systems cleanly.

### Thin runtime still holds

The LLM runtime stayed thin.

The only new runtime work was mechanical normalization for:

- cohort literals like `inbound leads from last week` -> `inbound_last_week`
- metadata-driven enum/default normalization from capability-declared
  `allowed_values` and `default`
- route target normalization like `to sales` -> `sales`

The service still owns the real behavior:

- clarification
- denial
- approval boundary
- actor-aware routing authority

### Approval-gated routing

The live Phase 4 routing path now proves:

- `rev_ops_manager` can request routing preview
- the prioritization service returns `approval_required`
- the response includes a durable `approval_request_id`
- `sales_leader` can approve that exact request
- the approval record persists requester, approver, required role, and preview

### Actor-aware prioritization behavior

The prioritization service now uses the same actor identity path as the earlier
services.

That means:

- authorized actors can score and prioritize bounded cohorts
- unauthorized actors are denied routing
- conflicting owner scope can be restricted by the ANIP service if requested

## Regression Result

Live Phase 4 regression:

- `6 / 6` passed

Saved artifacts:

- [gtm_phase4_llm_runtime-2026-04-13T06-10-36Z.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/regression-runs/gtm_phase4_llm_runtime-2026-04-13T06-10-36Z.md)
- [gtm_phase4_llm_runtime-latest.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/regression-runs/gtm_phase4_llm_runtime-latest.md)

After Phase 4 landed, the earlier suites were rerun against the expanded stack:

- Phase 1: `22 / 22`
- Phase 2: `9 / 9`
- Phase 3: `9 / 9`
- Phase 4: `6 / 6`

So the third service did not break the earlier bounded-service proof.

## Why This Matters

This is the point where the showcase stops looking like:

- one warehouse
- one service
- one agent

and starts looking like a real governed GTM architecture:

- internal CRM state via ANIP
- enrichment via ANIP
- prioritization via ANIP over an existing REST backend
- actor-aware approval and auditability across services

That is a stronger enterprise story because it shows ANIP can unify different
internal implementation styles behind one governed surface.
