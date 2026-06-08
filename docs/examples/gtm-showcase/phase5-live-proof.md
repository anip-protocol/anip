# GTM Showcase Phase 5 Live Proof

This document records the first live Phase 5 proof on the GTM showcase stack.

The goal of this slice was to prove that ANIP can front an existing MCP-backed
outreach system without turning the agent runtime into a prompt-owned drafting
workflow.

This is the fourth live GTM business service in the showcase. It is:

- a Studio-generated Application Integration design
- a bounded MCP backend for outreach drafting and objection handling
- an ANIP wrapper service in front of that backend
- the same thin LLM runtime consuming the governed ANIP contract

## What Was Added

- `gtm-outreach-mcp-backend`
  - deterministic MCP backend for draft generation and objection variants
- `gtm-outreach-service`
  - native ANIP service generated from the Studio application-integration path
- live Compose wiring for the fourth GTM business service
- LLM runtime catalog loading for the fourth service
- Phase 5 regression coverage for:
  - draft generation
  - clarification on missing target scope
  - denied send requests
  - denied raw-transcript requests
  - actor-aware outreach restrictions

## Capabilities Now Live

- `gtm.draft_outreach_message`
- `gtm.suggest_followup_content`
- `gtm.objection_response_variants`

These capabilities are exposed through `anip-gtm-outreach-showcase`.

## What Was Proven

### ANIP in front of an existing MCP backend

The outreach backend is a separate MCP service with its own tools and internal
payloads.

The ANIP service sits in front of it and owns:

- target clarification
- bounded request shaping
- denial of send-style requests
- denial of raw-transcript requests
- actor-aware objection access
- auditability through the ANIP audit endpoint

That matters because it proves the showcase is not limited to warehouse-backed
or REST-backed services. ANIP can also govern an MCP-based backend cleanly.

### Thin runtime still holds

The LLM runtime stayed thin.

The new runtime work in this slice is still mechanical:

- target normalization from conversational phrasing to bounded `target_ref`
- metadata-driven defaults and enum normalization using service-declared
  `allowed_values` and `default`
- explicit preflight blocking for clearly unsupported requests that should not
  even attempt a governed capability call

The service still owns the real behavior:

- clarification
- denial
- actor-aware restriction
- bounded evidence and output shape

### Generic metadata-driven enum normalization improved quality without moving policy into the prompt

During Phase 4 and Phase 5 validation, the model occasionally produced
descriptive enum values that were semantically reasonable but unsupported by a
capability contract.

The fix was not to make the prompt “smarter,” and not to add GTM-specific logic
to Studio core.

Instead, the runtime now uses capability metadata generically:

- service manifests declare `allowed_values` and optional `default` for inputs
- the runtime canonicalizes exact or obvious variants to those declared values
- when a field has exactly one allowed value, the runtime can safely normalize
  descriptive drift to that single canonical value
- otherwise the request still clarifies or the ANIP service denies

This improved planner robustness without shifting governance into the prompt.

### Actor-aware outreach behavior

The outreach service now uses the same actor identity path as the earlier
services.

That means:

- authorized actors can draft first-touch and follow-up content
- lower-privilege actors can get bounded follow-up variants
- objection-response variants can be denied by role
- denied and allowed outcomes are both audited with actor context preserved

## Regression Result

Live Phase 5 regression:

- `8 / 8` passed

Saved artifacts:

- [gtm_phase5_llm_runtime-2026-04-14T03-32-10Z.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/regression-runs/gtm_phase5_llm_runtime-2026-04-14T03-32-10Z.md)
- [gtm_phase5_llm_runtime-latest.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/regression-runs/gtm_phase5_llm_runtime-latest.md)

After Phase 5 landed, the earlier suites were rerun against the expanded stack:

- Phase 1: `22 / 22`
- Phase 2: `9 / 9`
- Phase 3: `9 / 9`
- Phase 4: `6 / 6`
- Phase 5: `8 / 8`

So the fourth service did not break the earlier bounded-service proof.

## Why This Matters

This is the point where the showcase proves the full four-service GTM story:

- internal CRM state via ANIP
- enrichment via ANIP
- prioritization via ANIP over an existing REST backend
- outreach via ANIP over an existing MCP backend

And the same core ANIP claim still holds:

- the prompt stays thin
- the services own the governed behavior
- backend implementation style can vary without giving governance away
