# GTM Revenue Operations Showcase Business Spec

## Purpose

This document is the umbrella business specification for the full GTM ANIP
showcase.

It replaces the narrower Phase 1 framing of the earlier `business-spec.md`
document and is intended to cover the complete GTM system as it exists now:

- pipeline analytics
- enrichment
- prioritization
- outreach drafting
- actor-aware permission boundaries
- approval-gated operational previews
- auditability
- governed multi-service composition

This is the business-facing source artifact that Studio should translate into:

1. PM-readable requirements and scenarios
2. developer design and service boundaries
3. generated code and extension points
4. validation of the running services against intended behavior
5. regression-backed proof that the implementation still matches the design

## Problem

Revenue operations teams increasingly want agent experiences that can:

- answer pipeline and forecast questions quickly
- identify risk and bottlenecks
- enrich account context
- prioritize work
- draft outreach
- prepare operational actions

The default market approach is usually a prompt-heavy agent with broad CRM or
warehouse access. That is hard to review, hard to govern, and difficult to
trust once the workflow becomes multi-step or actor-sensitive.

The showcase exists to prove a different pattern:

- business intent is defined up front
- bounded ANIP capabilities are designed explicitly
- the implementation is generated and completed from that design
- the running services are validated against the intended design
- agent runtimes consume governed services instead of raw tools

## Business Goal

Build a GTM agent system that lets revenue users and GTM operators:

- inspect pipeline health, forecast posture, risk, and bottlenecks
- review team and product performance
- enrich account context and identify lookalikes
- score and prioritize inbound or at-risk work
- draft bounded outreach content
- prepare follow-up and reassignment plans

while preserving:

- bounded service behavior
- actor-aware visibility and masking
- approval-gated operational actions
- explicit clarification instead of guessing
- explicit denial or restriction instead of overreach
- auditable behavior across single-service and multi-service flows

## System Scope

The GTM showcase is a multi-service system composed of four bounded ANIP
services.

The following capability inventory is canonical for this showcase. Studio must
preserve these exact capability IDs in Developer Design, package generation, and
showcase verification. Do not introduce paraphrased replacement IDs for these
business behaviors.

### 1. Pipeline Service

Service:

- `gtm-pipeline-service`

Capabilities:

- `gtm.pipeline_summary`
- `gtm.pipeline_forecast_summary`
- `gtm.stage_bottleneck_summary`
- `gtm.sales_team_performance_summary`
- `gtm.product_pipeline_summary`
- `gtm.stalled_opportunity_review`
- `gtm.account_risk_summary`
- `gtm.prepare_followup_tasks`
- `gtm.prepare_reassignment_plan`
- `gtm.at_risk_followup_preparation`
- `gtm.at_risk_reassignment_preparation`

This service owns the governed CRM-state layer.

### 2. Enrichment Service

Service:

- `gtm-enrichment-service`

Capabilities:

- `gtm.account_enrichment_summary`
- `gtm.lookalike_accounts`
- `gtm.at_risk_account_enrichment_summary`

This service owns bounded external-style context enrichment over the approved
account scope.

### 3. Prioritization Service

Service:

- `gtm-prioritization-service`

Capabilities:

- `gtm.score_leads`
- `gtm.prioritize_accounts`
- `gtm.route_leads`
- `gtm.prioritized_routing_preparation`

This service owns deterministic scoring, ranking, and approval-gated routing.

### 4. Outreach Service

Service:

- `gtm-outreach-service`

Capabilities:

- `gtm.draft_outreach_message`
- `gtm.suggest_followup_content`
- `gtm.objection_response_variants`
- `gtm.prioritized_outreach_draft`
- `gtm.bottleneck_account_outreach_draft`

This service owns bounded draft-only outreach behavior. It does not send
messages.

## Cross-Service Capability Semantics

Some showcase capabilities are intentionally cross-service from a business
perspective, but still have one canonical owning service in the ANIP contract.
They are not hidden agent recipes and they are not generic consumer-side
workflow glue.

- `gtm.at_risk_account_enrichment_summary` is owned by
  `gtm-enrichment-service`. It enriches accounts selected from a bounded
  at-risk account review without exposing raw enrichment data.
- `gtm.at_risk_followup_preparation` is owned by `gtm-pipeline-service`.
  It composes a bounded at-risk account review into follow-up task preparation
  and stops at `approval_required` before any task is created.
- `gtm.at_risk_reassignment_preparation` is owned by `gtm-pipeline-service`.
  It composes a bounded at-risk or overloaded pipeline review into a
  reassignment preview and stops before ownership changes are executed.
- `gtm.prioritized_routing_preparation` is owned by
  `gtm-prioritization-service`. It composes lead scoring/prioritization into a
  routing preview and stops at `approval_required` before downstream routing.
- `gtm.prioritized_outreach_draft` is owned by `gtm-outreach-service`. It
  drafts outreach for an explicitly selected prioritized account or cohort and
  stops before any send behavior.
- `gtm.bottleneck_account_outreach_draft` is owned by `gtm-outreach-service`.
  It drafts outreach for either an explicitly selected account from a
  bottleneck/risk review or a provider-selected bounded top candidate from that
  review, then stops at approval or preview. The service owns this derived
  target selection boundary; the consuming agent must not guess the account in
  app glue.

The consuming agent or app may orchestrate calls across services, but the
public capability IDs above remain service-owned contract surface. Any generated
implementation must preserve these IDs so the regression bank can compare the
same governed behavior across Python, TypeScript, Go, Java, and C#.

## Primary Users And Actors

The showcase must support different governed outcomes for different actors.

Representative actor families:

- `sales_leader`
- `rev_ops_manager`
- `account_manager_east`
- `account_manager_west`
- `sales_analyst`

The business expectation is not simply endpoint access control. The expectation
is that actor identity can change:

- what data is visible
- what fields are masked
- what scope is allowed
- what actions can be prepared
- what actions require approval
- what actions are denied

## Core Business Questions

The system must support recurring GTM questions such as:

- What does the current quarter pipeline look like by stage or region?
- What is the risk-adjusted forecast for a quarter or region?
- Which accounts are most at risk, and why?
- Where are deals bottlenecking?
- Which teams or managers are underperforming?
- How is pipeline distributed by product line?
- What enrichment context explains why these accounts matter?
- Which accounts or leads should be prioritized next?
- What follow-up or reassignment work should be prepared?
- What first-touch or follow-up outreach should be drafted for an approved
  target?

These questions must be supported through bounded capabilities, not through a
generic “query anything in CRM” surface.

## Capability Expectations

Every business capability in this system must satisfy the following conditions:

1. it answers a recurring business question
2. it uses a stable parameter set
3. it has a clear governed outcome
4. it preserves explicit service ownership
5. it is reviewable in Studio and testable in the regression harness

The system should support BI-shaped reads where appropriate, but only through
declared semantic capabilities and allowlisted dimensions, filters, and
measures. It must not expose raw SQL or arbitrary database exploration through
the agent layer.

## Required Governed Behaviors

The system must make these behaviors explicit and reviewable:

### Success

- in-scope bounded read or draft behavior returns a governed result

### Clarification

- the system does not guess missing critical fields such as quarter, account
  reference, ranking basis, or outreach target

### Restriction

- the system may narrow or mask the result when an actor is partially allowed
  to see a bounded slice but not the full requested scope

### Denial

- the system denies raw export, direct-send, or out-of-scope requests instead
  of improvising unsafe behavior

### Approval Required

- the system may prepare operational previews but must stop before routing,
  reassignment, follow-up execution, or any other write-adjacent side effect

## Approval Posture

The showcase must demonstrate that operational preparation and execution are
not the same thing.

Allowed preparation examples:

- follow-up task preview
- reassignment plan preview
- lead routing preview

Required behavior:

- preview can be generated when the actor is allowed to prepare it
- the system returns `approval_required` for the next step
- the approval record is durable and reviewable
- a lower-authority actor can be denied even when the same question is allowed
  for a higher-authority actor

## Auditability Requirements

Every governed call must be reconstructable after the fact.

The system must be able to explain:

- who asked
- which actor identity or role applied
- which capability ran
- which parameters were used after normalization
- whether the outcome was success, clarification, restriction, denial, or
  approval-required
- why two different actors received different results

Audit is a core part of the business trust story, not a technical afterthought.

## Multi-Service Composition Requirements

The system must support compound user questions that require more than one
bounded service hop while preserving the same governed boundaries.

Representative composition families:

- `pipeline/risk -> enrichment`
- `prioritization -> enrichment -> outreach`
- `forecast -> risk -> follow-up preview`
- `score -> route`
- `bottleneck -> risk -> enrichment`

The required business property is:

- the question may be compound
- the execution remains governed

That means:

- service chaining is bounded
- approval stops still apply mid-chain
- denial still applies mid-chain
- clarification still applies at the correct step
- actor-aware boundaries still hold across the chain

## Data And Verification Posture

The showcase uses warehouse-modeled GTM data plus bounded auxiliary layers.

The business expectation is:

- the agent consumes governed ANIP capabilities
- the data layer is modeled and inspectable
- a BI verification surface can validate the same read-oriented business slices
- governance still remains with ANIP services, not the BI tool

The verification surface is allowed to validate:

- pipeline
- forecast
- bottlenecks
- risk
- team performance
- product pipeline
- enrichment slices

It is not expected to replicate:

- actor-aware denial or masking
- approval behavior
- compound orchestration
- outreach generation

## Validation Intent

The showcase is only successful if the full lifecycle is visible and repeatable:

1. business spec exists as a first-class project asset
2. Studio translates that spec into PM-readable requirements and scenarios
3. Studio derives developer design and service shape from those artifacts
4. generated code is actually used in the running implementation
5. explicit extension logic has a declared place and does not hide in
   overwritten generated files
6. Studio can observe and validate the running services against intended
   behavior and ANIP metadata
7. the regression harness passes across single-service and compound flows

## Non-Goals

This showcase is not trying to prove:

- a single unconstrained GTM super-agent
- raw SQL freedom for the agent
- unrestricted CRM export
- direct-send outreach
- write execution without approval
- one giant merged service instead of explicit boundaries
- hidden prompt logic acting as the policy engine

## Success Criteria

The showcase is successful when an informed reviewer can see that:

- the business intent was written first
- the PM and developer views derive from that business intent
- the implementation follows the bounded service design
- extensions are explicit instead of hidden inside regenerated files
- the same services can be consumed by multiple agent runtimes
- permissions, approvals, denial, clarification, and auditability survive
  compound workflows
- the full system can be reproduced locally and validated end to end
