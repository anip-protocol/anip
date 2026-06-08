# GTM Showcase Implementation Plan

## Implementation Doctrine

Build this showcase in stages.

Do not start by trying to answer every GTM question in the first cut.

The right first version is a bounded, credible, end-to-end loop that proves the
ANIP value clearly.

## Showcase Objectives

The showcase has to preserve the following proof chain:

1. source business spec
2. translated behavior specification in Studio
3. completed developer design in Studio
4. generated code used by the showcase services
5. validation of the running services against intended behavior and observed
   ANIP metadata
6. execution through one or more agent runtimes and a simple UI

That objective is not optional. It is the point of the showcase.

## Phase 1

### Goal

Build the first serious internal GTM loop:

- pipeline analysis
- account risk review
- stalled-opportunity review
- follow-up preparation that stops at approval

### Deliverables

- Postgres dataset load for the Maven CRM dataset
- dbt project modeling the CRM tables
- Cube semantic layer over the modeled GTM data
- `gtm-pipeline-service`
- initial Studio project preload
- one simple agent UI
- one baseline agent implementation

Phase 1 should stay on one anchor dataset and one bounded service. It should
not require enrichment, lead scoring, or outreach datasets to succeed.

### Required capabilities

- `gtm.pipeline_summary`
- `gtm.stalled_opportunity_review`
- `gtm.account_risk_summary`
- `gtm.prepare_followup_tasks`

### Questions to support first

- “Which deals in our Q2 pipeline are at risk this quarter, and why?”
- “Show me all opportunities stuck in negotiation longer than 30 days.”
- “Rank our top 10 deals by close probability and identify which ones need follow-up.”
- “Prepare follow-up tasks for the highest-risk accounts in my Q2 pipeline.”

### Hero demo path

Phase 1 should be optimized around one demonstrable flow:

1. ask for at-risk Q2 deals
2. clarify missing scope or ranking basis when needed
3. return a bounded risk summary with explicit evidence
4. identify the accounts that need follow-up
5. prepare follow-up tasks
6. stop at `approval_required` before any side effect
7. validate the behavior in Studio against intended design and observed metadata

## Phase 2

### Goal

Turn the first loop into a multi-service ANIP proof.

### Deliverables

- dedicated `gtm-enrichment-service`
- dedicated `gtm-outreach-service`
- cross-service capability flows
- optional second dataset for enrichment
- optional prioritization/scoring layer
- stronger approval and restriction demonstrations
- second agent runtime
- richer validation packet in Studio

### Immediate next implementation slice

Phase 2 should start by adding one new bounded service, not by broadening the
existing pipeline service into a GTM super-service.

The recommended next service is:

- `gtm-enrichment-service`

Reason:

- it proves a second bounded service boundary clearly
- it creates a real cross-service ANIP flow
- it is easier to keep governed than jumping straight to outreach generation

The first Phase 2 capability set should be narrow:

- `gtm.account_enrichment_summary`
- `gtm.lookalike_accounts`
- optional later:
  - `gtm.buying_committee_summary`

Phase 2 should preserve the same rule as Phase 1:

- bounded service first
- then agent/runtime usage
- then validation and regression coverage

### Recommended Phase 2 dataset pairing

The cleanest Phase 2 pairing is:

- `Maven Analytics CRM`
- plus one enrichment dataset:
  - `Bright Data B2B`, or
  - `Synthetic B2B CRM and Marketing`

This is the right next step because it proves:

- a second bounded service
- a second dataset layer
- real cross-service GTM behavior

without jumping too early into scoring or outreach generation.

### Phase 2 first questions

The first enrichment-service questions should stay narrow:

- `Summarize firmographic context for the top 5 at-risk accounts in 2017-Q2.`
- `Find lookalike accounts similar to our top-risk manufacturing accounts.`
- `Which enriched accounts look most similar to our best existing customers?`

These should remain:

- bounded
- explainable
- non-mutating

### Recorded execution sequence

The next concrete implementation order should be:

1. wire `studio_gtm_enrichment` into the GTM Compose stack
2. add the first live enrichment runtime path
3. teach the LLM runtime the second-service capability brief
4. add Phase 2 regression cases for enrichment and cross-service flow
5. only after that, start Phase 3 actor and approval boundaries

This ordering is intentional.

Do not start actor and approval work while the second bounded service is still
only half-live.

Finish the minimum live Phase 2 proof first, then add production-real
organizational boundaries on top of a real multi-service path.

## Phase 3

### Goal

Add production-real organizational boundaries:

- actor-aware permissions
- approval authority
- auditability
- UI surfaces for review and approval

### Deliverables

- `keycloak` integration for actor identity and role mapping
- role-aware capability and data-shape differences
- approval UI for reviewable approval actions
- auditable approval state and governed outcomes
- regression coverage for same-question / different-actor behavior
- Studio validation and exported artifacts that reflect actor-aware policy posture

### Initial Phase 3 scope

The first Phase 3 slice should add:

1. role-based read differences
- same question
- different actor
- different safe output shape

2. approval by role and action type
- some users can prepare work
- some users can approve work
- some users can do neither

3. enrichment permission posture
- some roles can see bounded enrichment
- other roles get denial or reduced result shape

4. audit reviewability
- explain who asked, what capability ran, and why a result differed

### Recorded first live Phase 3 slice

The first live Phase 3 slice is now implemented on the showcase stack with:

- actor profiles flowing through the live LLM runtime
- actor-aware root-principal handling in the generated ANIP services
- service-layer role-aware data shaping
- role-aware denial vs approval boundaries for follow-up preparation
- actor-scoped audit querying through the ANIP audit endpoint

Saved proof artifact:

- [phase3-live-proof.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/phase3-live-proof.md)

### Why This Comes Before Packaging

This is a bigger realism jump than packaging polish.

Once the showcase proves:

- actor-aware visibility
- role-aware approval
- auditable governed outcomes

it starts looking production-real instead of just technically impressive.

## Phase 4

### Goal

Add the bounded prioritization service.

### Deliverables

- `gtm-prioritization-service`
- lead/account scoring business spec
- Studio-side application integration design for a REST backend
- generated ANIP capability scaffold and backend adapter
- regression coverage for scoring, ranking, route recommendation, and approval-gated routing

### Why Prioritization Comes Next

- it adds a third bounded service without collapsing into outreach complexity
- it proves ANIP can sit in front of an existing REST scoring/routing backend
- it lets the showcase demonstrate scoring and routing without turning the runtime into a prompt-owned ranker

### Recorded first live Phase 4 slice

The first live Phase 4 slice is now implemented on the showcase stack with:

- a deterministic REST prioritization backend
- a live ANIP wrapper service in front of that backend
- LLM runtime catalog support for the third service
- approval-gated routing through the prioritization service
- regression coverage for bounded scoring, prioritization, and routing approval

Saved proof artifact:

- [phase4-live-proof.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/phase4-live-proof.md)

## Phase 5

### Goal

Add the bounded outreach service.

### Deliverables

- `gtm-outreach-service`
- outreach business spec
- Studio-side application integration design for an MCP backend
- generated ANIP capability scaffold and backend adapter
- regression coverage for draft generation, clarification, and denial of send/raw-transcript requests

### Why Outreach Comes After Prioritization

- it keeps scoring and drafting separate
- it proves ANIP can front an existing MCP drafting backend without rebuilding it
- it keeps the first outreach cut draft-only

### Recorded first live Phase 5 slice

The first live Phase 5 slice is now implemented on the showcase stack with:

- a deterministic MCP outreach backend
- a live ANIP wrapper service in front of that backend
- LLM runtime catalog support for the fourth service
- regression coverage for draft generation, clarification, send denial,
  raw-transcript denial, and actor-aware objection access
- generic metadata-driven enum/default normalization in the thin runtime

Saved proof artifact:

- [phase5-live-proof.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/phase5-live-proof.md)

## Phase 6

### Goal

Deepen the Maven CRM state layer without weakening the governed-service story.

### Deliverables

- bounded forecast capability over the existing GTM state layer
- bounded bottleneck capability over the existing GTM state layer
- stronger Cube usage for aggregate CRM reads where appropriate
- regression coverage that proves the ANIP contract stayed stable while backend
  execution became more semantic-layer-driven
- one approval-shaped operational preview capability

### Recommended capability order

1. `gtm.pipeline_forecast_summary`
2. `gtm.stage_bottleneck_summary`
3. `gtm.sales_team_performance_summary`
4. `gtm.product_pipeline_summary`
5. `gtm.prepare_reassignment_plan`

### Why This Phase Exists

- the Maven CRM dataset still has meaningful unused business surface
- these capabilities are recurring GTM questions, not database-explorer tricks
- the first two are especially good candidates for Cube-backed aggregate reads
- reassignment planning adds another production-real approval boundary

### Phase 6 discipline

Do not turn this into a generic CRM copilot phase.

Each new capability should:

- map to a recurring business question
- use a stable parameter set
- have a clear governed outcome
- preserve the ANIP contract while backend execution evolves

### Recorded live Phase 6 slices

The live Phase 6 slices are now implemented on the showcase stack with:

- `gtm.pipeline_forecast_summary` added to the generated pipeline service
- `gtm.stage_bottleneck_summary` added to the generated pipeline service
- `gtm.sales_team_performance_summary` added to the generated pipeline service
- `gtm.product_pipeline_summary` added to the generated pipeline service
- `gtm.prepare_reassignment_plan` added to the generated pipeline service
- Cube-backed execution for bounded forecast, bottleneck, team-performance,
  and product-pipeline aggregates
- declared input metadata for:
  - `forecast_mode`
  - `slice_by`
- generic metadata-driven enum continuity across clarification follow-up turns
- thin owner-scope normalization that drops quarter literals from scope fields
  instead of silently narrowing reads to an empty result
- actor-aware masking and restriction behavior on all four Phase 6 pipeline
  analytics paths
- approval-gated reassignment preview over the same actor-aware pipeline scope
- regression coverage for:
  - risk-adjusted forecast
  - best-case regional forecast
  - bottleneck reads by region and by product
  - sales-team performance by manager
  - product-pipeline reads by product
  - reassignment-preview approval path
  - clarification then follow-up resolution
  - masked analyst visibility
  - restricted regional overreach

Saved proof artifact:

- [phase6-live-proof.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/phase6-live-proof.md)

## Phase 7

### Goal

Prove governed scenario composition from one user question across multiple
services and phases.

### Deliverables

- compound read flow across multiple bounded services
- compound flow with one approval boundary
- actor-aware compound flow that still respects denial and masking posture
- regression coverage that asserts service chain, loop bounds, audit, and
  upstream plus downstream data checks
- shareable proof artifact for multi-hop governed execution

### Recorded first live Phase 7 slice

The first live Phase 7 slice is now implemented on the showcase stack with:

- `prioritization -> enrichment -> outreach` read composition
- `forecast -> risk -> follow-up preview` composition with approval stop
- actor-aware compound denial for the same forecast-plus-follow-up ask
- `score -> route` composition with approval stop

Saved proof artifact:

- [phase7-live-proof.md](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/phase7-live-proof.md)

### Why This Matters

This is where the story becomes:

- one question
- multiple governed hops
- still predictable

The point is not to answer long prompts for appearance. The point is to show
that scenario composition stays bounded, auditable, and actor-aware.

## Phase 8

### Goal

Package the showcase as a clean, shareable flagship stack.

### Deliverables

- full Docker Compose setup
- preload script for Studio
- reproducible seed data load
- third agent runtime
- guided demo UI
- operator docs

## Initial Work Breakdown

The immediate next implementation slices should be:

1. create the showcase stack root in the main ANIP repo
2. add a Compose skeleton for:
   - Postgres
   - dbt
   - Cube
   - Studio
   - `gtm-pipeline-service`
   - one agent UI
   - one baseline agent runtime
3. define the first GTM schema and loading path for Maven CRM
4. define the first bounded scenario pack
5. implement the first service end to end before adding more services

## Initial Risks

The biggest risks are:

- trying to do too much in v1
- allowing service boundaries to become fuzzy
- making the agent layer seem more important than the governed service layer
- mixing enrichment, scoring, and drafting too early without clear contracts
- turning the showcase into a generic analytics app instead of a governed agent-capability proof
- making the first release depend on external data or integrations that reduce reproducibility

## Success Criteria

The showcase is successful when a user can see, quickly, that:

- the GTM capability was designed intentionally in Studio
- the service implementation matches that design
- the agent is consuming governed services, not improvising over raw tools
- approval, clarification, restriction, and denial are visible and meaningful
- the stack is reproducible locally
- the same services can be consumed by more than one agent runtime
