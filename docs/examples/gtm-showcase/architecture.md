# GTM Showcase Architecture

## Why This Showcase Exists

This showcase is meant to prove something specific:

- GTM agents are a serious enterprise use case
- they are difficult to build safely with unconstrained agent improvisation
- ANIP can make them more governable, more auditable, and easier to validate

The target is not a toy chatbot.

The target is a real GTM agent stack built the ANIP way:

- `design`
  - Studio holds the business and developer design packet
- `implement`
  - bounded ANIP services expose governed capabilities
- `validate`
  - Studio compares intended behavior against observed implementation metadata and runtime evidence
- `execute`
  - multiple agent runtimes consume the same ANIP services

## Core Principle

This showcase should not pretend there is one magical `GTM super-agent`.

It should demonstrate:

- multiple bounded governed capabilities
- multiple services
- multiple backends
- multiple agent implementations
- one shared ANIP contract model

That is what makes it credible.

## Target Stack

The showcase should be packaged as a `Docker Compose` stack, not a single container.

The stack should include:

- `studio`
  - with preloaded requirements, scenarios, packets, and validation artifacts
- `keycloak`
  - actor identity, role mapping, and token issuance for the showcase
- `postgres`
  - storing the showcase datasets
- `dbt`
  - building modeled GTM datasets and semantic-ready tables/views
- `cube`
  - semantic access layer over the GTM data
- `gtm-pipeline-service`
  - ANIP service for pipeline, risk, and follow-up preparation
- `gtm-enrichment-service`
  - ANIP service for account enrichment and lookalike analysis
- `gtm-prioritization-service`
  - ANIP service for lead/account scoring, ranking, and route recommendation
- `gtm-outreach-service`
  - ANIP service for draft outreach and objection-response assistance
- `agent-ui`
  - simple UI for asking questions and observing governed outcomes
- `approval-ui`
  - simple UI for reviewing and issuing approvals
- `agent-openai`
  - one agent implementation
- `agent-langgraph`
  - a second agent implementation
- `agent-custom`
  - a plain custom tool-calling loop implementation

This is the eventual target stack.

Phase 1 should run a smaller subset:

- Studio
- Postgres
- dbt
- Cube
- `gtm-pipeline-service`
- one baseline agent runtime
- one simple agent UI

Later phases should add:

- `keycloak`
- approval UI
- actor-aware policy behavior
- richer audit review surfaces

## Hero Demo Path

The whole showcase should optimize around one explicit end-to-end path:

1. ask about at-risk Q2 deals
2. trigger clarification when ranking basis, ownership scope, or timeframe is underspecified
3. identify the highest-risk accounts from the bounded pipeline service
4. enrich a small approved subset of those accounts with firmographic context
5. prepare follow-up tasks for the selected accounts
6. stop at approval before any side-effecting downstream execution
7. validate the observed behavior in Studio against the intended design and service metadata

This hero path matters more than raw capability count. The showcase should feel
like one coherent governed experience, not a bag of disconnected demos.

## Actor And Permission Boundaries

The showcase should eventually prove that the same agent-facing question can
produce different governed outcomes depending on who is asking.

Examples:

- sales leader
  - broader regional visibility
  - account values or value bands where allowed
- account manager
  - owned or team-scoped answers only
- rev ops
  - broader operational detail
- lower-privilege role
  - bounded summary only, or denial for sensitive detail

Permissions should shape three things:

- what capability is visible
- what data shape is returned
- what actions are allowed to progress past approval

## Approval And Audit Surfaces

The showcase should eventually include:

- an explicit approval UI
- explicit approver roles
- auditable approval state transitions
- reviewable reasoning for why work stopped at approval

Auditability should capture:

- actor identity
- role / policy posture
- selected capability
- normalized parameters
- governed outcome
- approval state
- bounded evidence basis

This is one of the main things that makes the stack feel deployable instead of
just impressive.

## Dataset Strategy

The showcase should use a layered dataset strategy.

The intended full combination is:

- `Maven Analytics CRM` for internal GTM state
- `Bright Data B2B` or `Synthetic B2B CRM and Marketing` for enrichment
- `Automation Anywhere GTM lead JSON` or a `Lead Scoring Dataset` for prioritization
- a `sales-conversations / outreach dataset` for draft outreach and qualification

Those should be implemented as separate bounded service layers, not merged into
one giant dataset or one giant GTM service.

### 1. Core GTM state

Use:

- `Maven Analytics CRM Sales Opportunities`

Why:

- multi-table
- realistic pipeline structure
- suitable for bounded CRM / RevOps reasoning
- good fit for Postgres + dbt + Cube

This should be the anchor dataset.

For the first release, this is the only required dataset.

### 2. Enrichment layer

Use one of:

- `Bright Data B2B Business Dataset Samples`
- `Synthetic B2B CRM and Marketing Dataset`

Why:

- firmographics
- account context
- lookalike analysis
- enrichment-style workflows

This should remain optional until the core pipeline loop is working cleanly.

### 3. Prioritization layer

Use one of:

- `Lead Scoring Dataset`
- a simpler GTM lead/pipeline scoring dataset

Why:

- gives the showcase a real prioritization step
- helps prove that the agent does more than querying

This should be introduced only after the pipeline and enrichment services are stable.

Implementation posture:

- use the generic Studio `Application Integration` flow
- front an existing REST scoring or routing backend with ANIP

### 4. Drafting layer

Use:

- a sales-conversation / outreach-style dataset

Why:

- enables draft-only personalized outreach
- demonstrates cross-service orchestration without turning the demo into an autonomous outbound system

This should be introduced only after the enrichment and prioritization contracts
are explicit and validated.

Implementation posture:

- use the generic Studio `Application Integration` flow
- front an existing MCP drafting backend with ANIP

## Recommended Full Combination

The strongest full-showcase combination is:

1. `Maven Analytics CRM`
- anchor internal GTM state

2. `Bright Data B2B` or `Synthetic B2B CRM and Marketing`
- enrichment and firmographic context

3. `Automation Anywhere GTM lead JSON` or a `Lead Scoring Dataset`
- prioritization and routing

4. `Sales conversations / outreach dataset`
- draft outreach and qualification support

This is the recommended full-stack story because it shows:

- internal state
- enrichment
- prioritization
- outreach

without pretending those belong in one service contract.

## Service Boundaries

The full showcase should eventually use four bounded ANIP services.

The first serious version should start with one service and expand only after
the first loop is proven.

### 1. GTM Pipeline Service

Primary role:

- governed access to pipeline and opportunity state

Likely backend path:

- Postgres
- dbt models
- Cube semantic layer

Capabilities:

- `gtm.pipeline_summary`
- `gtm.stalled_opportunity_review`
- `gtm.account_risk_summary`
- `gtm.prepare_followup_tasks`

Governed behavior emphasis:

- clarification on ambiguous ranking or scope
- restriction for over-broad raw detail
- approval posture for task preparation or downstream operational actions

### 2. GTM Enrichment Service

Primary role:

- governed access to firmographic and account-context enrichment

Likely backend path:

- Postgres tables over enrichment datasets
- dbt models for normalized account profiles

Capabilities:

- `gtm.account_enrichment_summary`
- `gtm.lookalike_accounts`
- `gtm.buying_committee_summary`

Governed behavior emphasis:

- bounded enrichment views
- clear role-sensitive access posture
- explicit evidence for why an account is considered relevant or similar

### 3. GTM Prioritization Service

Primary role:

- convert bounded cohorts into explainable scoring and route recommendations

Likely backend path:

- existing lead-scoring or routing backend exposed over REST
- ANIP capability layer in front of that backend

Capabilities:

- `gtm.prioritize_leads`
- `gtm.route_leads`
- `gtm.score_leads`

Governed behavior emphasis:

- no raw model-feature export
- bounded ranking and route recommendation
- approval gating for operational routing if it mutates systems

### 4. GTM Outreach Service

Primary role:

- generate bounded, draft-only outreach support

Likely backend path:

- existing content-generation or messaging-assist MCP server
- ANIP capability layer in front of that backend

Capabilities:

- `gtm.draft_outreach_message`
- `gtm.suggest_followup_content`
- `gtm.objection_response_variants`

Governed behavior emphasis:

- no direct sending
- draft-only posture
- denial for raw transcript or training-corpus export

## Questions The Showcase Should Support

The system should eventually support question families like:

- pipeline health and forecast review
- stalled-deal analysis
- account risk review
- lead qualification and prioritization
- account enrichment
- lookalike and segment analysis
- campaign and funnel performance
- competitive and objection analysis
- draft outreach and follow-up recommendations
- RevOps operational review

But this should be staged.

The first implementation should focus on the most credible internal GTM path:

- pipeline analysis
- account risk
- stalled-opportunity review
- approval-gated follow-up preparation

Enrichment, prioritization, and draft outreach should be Phase 2 additions.

## What This Showcase Should Prove

If successful, the showcase should make these things obvious:

- business stakeholders can define bounded capability behavior without enumerating every utterance
- developers can bind that design into real services over real systems
- Studio can validate intended behavior against implementation metadata and runtime evidence
- multiple agent runtimes can consume the same ANIP services
- the system does not require a frontier model to be useful
- the ANIP version is safer, more governable, and easier to validate than a raw agent-tool stack
- the same question can be governed differently for different actors
- governed behavior can be reviewed and explained after the fact

## Non-Goals

This showcase should not try to prove:

- a single unconstrained GTM super-agent
- fully autonomous outbound execution
- every possible GTM workflow in one release
- every dataset integrated on day one
- a dependency on proprietary or hard-to-reproduce external data just to make Phase 1 work

That would weaken the showcase.

The goal is:

- one strong, serious, bounded flagship implementation

## Packaging Goal

The final deliverable should be shareable as a `Docker Compose` stack that gives a user:

- Studio with the GTM design and validation packet preloaded
- the underlying data services and semantic layer
- fully implemented ANIP services
- multiple agent implementations
- a simple UI for interacting with the agents
- configurable model integration via API key

That is the target package.
