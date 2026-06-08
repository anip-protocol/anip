# GTM Showcase Story

## What This Showcase Is Trying To Prove

This showcase is meant to speak to real GTM teams, not only protocol or
platform engineers.

The claim is not:

- "we built another impressive AI demo"

The claim is:

- GTM agents can be built in a way that is safer, more governable, easier to
  validate, and more realistic to run in-house than the common
  `prompt + raw tools + hidden glue` pattern.

## The Commercial Problem

Most GTM agent implementations break down in one of two ways:

1. they are too shallow
- they answer a few CRM questions
- they do not survive real ambiguity, approval boundaries, or misuse pressure

2. they are too unconstrained
- they hide behavior inside prompts, routing glue, and ad hoc tool policies
- business stakeholders only discover mismatches after implementation

That is expensive, slow, and hard to trust.

## The Better Story

This showcase demonstrates a different operating model:

1. PM/business defines intended behavior up front
2. Studio translates that into bounded ANIP behavior and developer design
3. Studio generates real service scaffolds from that design
4. the running services are validated back against the intended design
5. multiple agents consume the same governed services

That is the real proof.

## The Full Showcase Stack

The full showcase uses a layered GTM data and service model.

### 1. Maven Analytics CRM

Role:

- internal GTM system state

What it supports:

- pipeline analysis
- stalled opportunity review
- account risk review
- follow-up preparation

Service:

- `gtm-pipeline-service`

### 2. Bright Data or Synthetic B2B

Role:

- enrichment layer

What it supports:

- firmographic context
- account enrichment
- lookalike analysis
- buying-committee-style context later if needed

Service:

- `gtm-enrichment-service`

### 3. GTM Lead JSON or Lead Scoring Dataset

Role:

- prioritization layer

What it supports:

- lead scoring
- route-to-sales / nurture / archive recommendations
- prioritization workflows

Service:

- `gtm-prioritization-service`

### 4. Sales Conversations / Outreach Dataset

Role:

- outreach and qualification layer

What it supports:

- draft outreach
- objection-aware follow-up suggestions
- qualification-style conversation assistance

Service:

- `gtm-outreach-service`

## Why This Layering Matters

The point is not to create one giant super-agent with one merged dataset.

The point is to show that:

- one business problem can still be decomposed into bounded governed services
- each service can expose a clean ANIP contract
- each layer can be validated independently
- agents can orchestrate across them without raw, unconstrained access

That is what makes the showcase credible.

## The Recommended Build Order

### Phase 1

- Maven CRM only
- one bounded service
- one serious internal GTM loop

### Phase 2

- add the enrichment service
- prove cross-service ANIP usage
- keep the service boundary tight

### Phase 3

- add permission and actor boundaries
- show that the same question can produce different governed results for different users
- add approval and audit review surfaces

### Phase 4

- add the prioritization service
- keep it bounded to scoring, ranking, and route recommendation
- front an existing REST scoring or routing backend with ANIP

### Phase 5

- add the outreach service
- keep it draft-only in the first cut
- front an existing MCP drafting backend with ANIP

### Phase 6

- deepen the Maven CRM state layer
- add higher-value bounded CRM capabilities over the same governed service surface
- use Cube more heavily for aggregate reads where it makes the architecture cleaner

### Phase 7

- prove governed scenario composition from one user question across multiple
  services

### Phase 8

- package the full stack cleanly for sharing

## Maven CRM Capability Expansion

The Maven CRM dataset still has more business value available than the current
pipeline service exposes.

The next CRM-state additions should stay bounded, business-legible, and
compatible with the current layering:

- dbt owns modeling and joins
- Cube increasingly owns reusable aggregate semantics
- ANIP services keep owning capability contracts, governance, approval posture,
  actor boundaries, and auditability

The recommended next capability order is:

1. `gtm.pipeline_forecast_summary`
2. `gtm.stage_bottleneck_summary`
3. `gtm.sales_team_performance_summary`
4. `gtm.product_pipeline_summary`
5. `gtm.prepare_reassignment_plan`

Why this order:

- it uses the Maven CRM dataset more fully without turning the service into a
  generic analytics copilot
- the first two are strong Cube-backed aggregate-read candidates
- the later capabilities bring sales-team and product visibility forward
- the final capability is an operational preview with a clear approval boundary

These are the intended semantics:

- `gtm.pipeline_forecast_summary`
  - likely revenue, commit vs best-case bands, risk-adjusted forecast, top
    contributors
- `gtm.stage_bottleneck_summary`
  - stage accumulation, average age by stage, and risk concentration by slice
- `gtm.sales_team_performance_summary`
  - win rate, cycle time, stalled-load, and open pipeline by rep or team
- `gtm.product_pipeline_summary`
  - open pipeline, won revenue, loss volume, and risk by product line
- `gtm.prepare_reassignment_plan`
  - preview-only reassignment recommendation that remains approval-gated

The live Phase 6 slices are now:

- `gtm.pipeline_forecast_summary`
- `gtm.stage_bottleneck_summary`
- `gtm.sales_team_performance_summary`
- `gtm.product_pipeline_summary`
- `gtm.prepare_reassignment_plan`

That matters for three reasons:

- it uses Cube more heavily where semantic aggregate execution actually helps
- it proves the ANIP contract can stay stable while the backend execution path
  becomes more semantic-layer-driven
- it shows how BI-shaped exploration can stay governed through declared
  semantic capabilities instead of collapsing into raw query freedom

The live Phase 6 path now proves:

- bounded forecast reads over the Maven CRM layer
- bounded bottleneck reads over one allowlisted slice dimension
- bounded team-performance reads over an allowlisted team slice
- bounded product-pipeline reads over a product rollup surface
- approval-gated reassignment previews over the same pipeline state layer
- clarification on missing quarter
- actor-aware masking for financial visibility
- actor-aware restriction for out-of-scope regional asks
- stable ANIP behavior while aggregate execution moved deeper onto Cube

## Governed Scenario Composition

The next realism jump after the four-service proof and the deeper Maven CRM
layer is not packaging. It is composition.

The important claim is not just:

- ANIP supports many isolated capabilities

The stronger claim is:

- ANIP supports governed scenario composition

That means:

- one compound business question
- multiple bounded service hops
- actor-aware restrictions still hold
- approval boundaries still appear where they should
- the final result is still bounded and auditable

The live Phase 7 slice now proves exactly that:

- `prioritization -> enrichment -> outreach`
- `forecast -> risk -> follow-up preview`
- actor-aware denial on the same compound ask
- `score -> route` with approval stop

A useful line for this stage is:

- the question is compound, the execution is still governed

This should not become:

- a vague "analyze anything in CRM" capability
- raw SQL exposure
- prompt-owned forecasting logic
- approval-free operational mutation

## Why REST And MCP Matter

The next two services should not imply that every system must be rebuilt from
scratch to benefit from ANIP.

The stronger story is:

- warehouse-native GTM state can use the Data Access flow
- an existing REST scoring or routing backend can sit behind ANIP
- an existing MCP drafting backend can sit behind ANIP

That proves ANIP is the governed contract layer, not a demand to replace
existing internal systems.

## The Hero Story For Sales And Marketing Teams

The story should be easy to explain:

1. a GTM user asks which Q2 deals are at risk
2. the system clarifies missing scope instead of guessing
3. the pipeline service returns bounded evidence
4. the enrichment service adds firmographic context for a small approved subset
5. the system prepares follow-up work
6. the workflow stops at approval before any mutation
7. Studio shows that the running services still match the intended design

That is much more compelling than:

- a chatbot that "kind of knows our CRM"

## What This Should Say To Buyers

This showcase should make these things obvious:

- the agent is not improvising over raw tools
- business intent was defined before implementation
- the services are bounded and checkable
- smaller models can still be useful when the governed service boundary is strong
- the same agent experience can still enforce different results for different actors
- governed behavior is reviewable after the fact through auditability

## What We Learned About Prompt Logic

This showcase now has a direct proof point for the ANIP architecture.

We tested a planner-prompt expansion that pushed more boundary policy into the
agent layer. The result was worse behavior: ambiguous but in-scope requests
became less stable, especially around clarification handling.

When that prompt-side policy was removed and the prompt was kept thin again, the
live regression harness returned to green.

That is an important result:

- planner-side policy made the system worse
- governed service behavior made it better
- the prompt should stay lean and descriptive, not become the policy engine

## Why Permissions Matter

This showcase gets more enterprise-real once it proves:

- the same question can return different safe result shapes for different users
- some users can prepare work while others cannot
- some users can approve work while others cannot
- enrichment visibility can vary by role and policy

That is not peripheral behavior. It is one of the main reasons to use bounded
governed services instead of raw agent-tool access.

## Why Auditability Matters

Governance without auditability is incomplete.

This showcase should be able to explain:

- who asked
- under which role or authority boundary
- which capability was selected
- which parameters were normalized and sent
- what governed outcome was returned
- why a request was clarified, denied, restricted, or approval-gated
- why two actors received different answers

That is what makes governed behavior reviewable after the fact.

## What It Should Not Pretend

This showcase should not pretend:

- that one model prompt can safely own GTM behavior
- that every GTM workflow belongs in one service
- that every dataset should be merged into one giant warehouse contract
- that outbound execution should happen without strong approval boundaries

The win is disciplined composition, not magical autonomy.
