# GTM Showcase Phase 6 Live Proof

This document records the live Phase 6 proof on the GTM showcase stack.

The goal of this phase is to deepen the Maven CRM state layer without turning
the pipeline service into a generic CRM copilot or moving business policy into
the prompt.

The live Phase 6 capabilities are:

- `gtm.pipeline_forecast_summary`
- `gtm.stage_bottleneck_summary`
- `gtm.sales_team_performance_summary`
- `gtm.product_pipeline_summary`
- `gtm.prepare_reassignment_plan`

It is implemented as:

- a Studio-seeded capability expansion on the pipeline service design
- a generated pipeline-service contract update
- Cube-backed aggregate execution over the existing dbt-modeled CRM layer
- the same thin LLM runtime consuming the governed ANIP surface

## What Was Added

- `gtm.pipeline_forecast_summary` on the generated `gtm-pipeline-service`
- `gtm.stage_bottleneck_summary` on the generated `gtm-pipeline-service`
- `gtm.sales_team_performance_summary` on the generated `gtm-pipeline-service`
- `gtm.product_pipeline_summary` on the generated `gtm-pipeline-service`
- `gtm.prepare_reassignment_plan` on the generated `gtm-pipeline-service`
- Cube measures for:
  - forecast base value
  - likely forecast value
  - best-case forecast value
  - risk-adjusted forecast value
  - open opportunity count
  - won opportunity count
  - lost opportunity count
- one allowlisted bottleneck slice surface:
  - `regional_office`
  - `manager_name`
  - `product_name`
- one allowlisted team-performance slice surface:
  - `manager_name`
  - `regional_office`
- one bounded product-performance slice surface:
  - `product_scope`
  - `owner_scope`
  - `limit`
- one approval-gated reassignment surface:
  - `selection_basis`
  - `owner_scope`
  - `limit`
- bounded stage-bottleneck, team-performance, and product-pipeline rollups over
  Cube aggregate reads
- bounded reassignment preview logic over the same modeled pipeline state
- actor-aware masking for users who can see pipeline shape but not full
  financial values
- actor-aware restriction for users who ask for regional scopes outside their
  allowed boundary
- explicit backend and service extension modules for domain-specific
  refinements so regeneration does not trap working behavior in overwritten
  generated files
- generic owner-scope cleanup that drops quarter literals from scope fields
  instead of silently narrowing a read to no rows
- Phase 6 regression coverage for:
  - risk-adjusted Q2 forecast
  - best-case East-region forecast
  - top bottlenecks by region
  - top bottlenecks by product
  - sales-team performance by manager
  - product pipeline performance by product
  - reassignment preview with approval
  - clarification then follow-up resolution for missing quarter
  - masked analyst reads
  - restricted regional overreach

## What Was Proven

### Cube moved further into the live path without changing the ANIP contract

The forecast, bottleneck, team-performance, product-pipeline, and
reassignment-preview capabilities use the same style of bounded ANIP contract
as the earlier pipeline reads:

- declared capability
- declared inputs
- governed clarification, restriction, and masking
- bounded response shape

But the execution path is more semantic-layer-driven:

- dbt still owns the modeled CRM layer and joins
- Cube now owns more of the reusable aggregate forecast, bottleneck,
  team-performance, and product-pipeline semantics
- ANIP still owns governance, actor boundaries, approval, and auditability

That is the correct layering.

### The service, not the prompt, stayed responsible for behavior

The prompt did not become pipeline-analytics business logic.

The runtime improvements in this phase stayed thin and generic:

- if a clarification follow-up turn omits an enum field
- and prior conversation history clearly references one allowed value
- the runtime can carry that exact allowed value forward
- if a free-text scope field contains a quarter literal instead of a real scope
  value
- the runtime drops it as invalid scope instead of letting it silently collapse
  the read to zero rows

That is still thin normalization. It is not prompt-owned analytics policy.

The service kept the real behavior:

- clarification when quarter is missing
- restriction when actor scope is too broad
- masking when financial visibility should be limited
- approval_required for reassignment preview instead of mutation
- denial of unsupported values or requests outside the capability contract

One regeneration-safety improvement also landed in this phase:

- generated bundles now support explicit backend extension modules
- the current GTM product-scope cleanup lives in `backend_extensions.py`
  instead of as a hidden one-off edit in the generated adapter
- regeneration recopies that extension module from the source service directory
- generated bundles now also support explicit service extension modules
- the current pipeline-scope restriction and approval-surface filtering can live
  in `service_extensions.py` instead of being trapped inline in the generated
  service

### Actor-aware Phase 6 behavior is live

The Phase 6 paths now prove that the same capability can produce different
governed results for different actors:

- `sales_leader`
  - full financial forecast and product values
  - approval authority over reassignment previews
- `sales_analyst`
  - success, but forecast and product financial values masked
  - denied for reassignment preview
- `account_manager_east`
  - `restricted` when requesting West-region forecast
  - `restricted` when requesting West-region bottlenecks
  - `restricted` when requesting West-region team performance
- `rev_ops_manager`
  - `approval_required` reassignment preview with a durable approval request

That is production-real behavior, not just BI-style aggregation.

## Regression Result

Live Phase 6 regression:

- `18 / 18` passed

Saved artifacts:

- [gtm_phase6_llm_runtime-2026-04-14T05-36-30Z.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/regression-runs/gtm_phase6_llm_runtime-2026-04-14T05-36-30Z.md)
- [gtm_phase6_llm_runtime-latest.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/regression-runs/gtm_phase6_llm_runtime-latest.md)

After the Phase 6 slice landed, the earlier suites were rerun against the same
stack:

- Phase 1: `22 / 22`
- Phase 2: `9 / 9`
- Phase 3: `9 / 9`
- Phase 4: `6 / 6`
- Phase 5: `8 / 8`
- Phase 6: `18 / 18`

So the expanded Phase 6 slice did not regress the earlier five-phase proof.

## Why This Matters

This phase strengthens the answer to the predictable BI criticism.

The answer is not:

- no exploration

The answer is:

- governed exploration through declared semantic capabilities

These Phase 6 paths show the right split clearly:

- dbt models the business layer
- Cube executes more of the aggregate semantics
- ANIP governs who can ask, what shape is allowed, and how the request fails
  safely

That is stronger than:

- raw SQL from the agent
- or a generic analytics copilot with weak boundaries
