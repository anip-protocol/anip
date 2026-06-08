# Developer Spec: GTM Account Enrichment

Generated: 2026-04-12 22:16:23

## Traceability
- Artifact role: Canonical Developer Spec
- Project: GTM Account Enrichment
- Primary consumer: Both people and agents
- Requirements set: GTM account enrichment requirements
- Scenario: Hero path: enrich selected accounts after pipeline review
- Service design: GTM enrichment service design
- Evaluation: eval-gtm-account-enrichment (HANDLED)

## Technical Purpose
Turn the PM-owned enrichment behavior specification into one bounded ANIP service contract with explicit clarification, denial, metadata, and implementation expectations.

## Translation Chain
- Source business spec: Canonical GTM enrichment business spec (docs/examples/gtm-showcase/enrichment-business-spec.md)
- Translated requirements: GTM account enrichment requirements
- Active scenario: Hero path: enrich selected accounts after pipeline review
- Proposal: GTM enrichment single-service proposal
- Service design: GTM enrichment service design
- Evaluation status: eval-gtm-account-enrichment (HANDLED)

## Developer Enrichment
- Principle: keep the service read-only in this phase
- Principle: encode account-scope clarification and export denial in the service contract instead of agent glue
- Principle: use Postgres plus dbt modeled enrichment views as implementation internals, not the external capability surface
- Decision: one GTM Enrichment Service owns phase 2 enrichment and lookalike capabilities
- Decision: all capabilities return bounded evidence instead of raw enrichment export
- Decision: manifest, discovery, and runtime evidence must be sufficient for Studio conformance validation

## Behavior Placement
Studio should make behavior placement explicit. Important behavior should live in the service contract or an explicit orchestration contract. Remaining runtime glue should stay thin, mechanical, and visible.

### Service-Covered Behavior
- missing account scope yields clarification_required in gtm.account_enrichment_summary
- missing reference account yields clarification_required in gtm.lookalike_accounts
- raw unconstrained enrichment export is denied by the bounded enrichment service contract
- lookalike analysis returns explainable bounded similarity output instead of a raw model dump

### Orchestration-Covered Behavior
- the runtime may resolve top at-risk accounts from the pipeline service before calling the enrichment service
- only bounded account identifiers may cross the pipeline-to-enrichment handoff
- cross-service flow must record prior service calls so Studio can review the handoff path

### Cross-Service Contract
#### Handoff
- Target service: gtm-enrichment-service
- Target capability: gtm.account_enrichment_summary
- Continuity: same_task
- Completion mode: downstream_acceptance
- Required for task completion: no
- Carry fields:
  - account_name
- Rationale: A bounded pipeline risk result may hand off selected account identifiers into enrichment when the user explicitly asks for enrichment context.

### Remaining Runtime Glue
- mechanical account-name normalization still happens in the runtime before enrichment invocation
- generic phrases like 'our best customer' still normalize to clarification triggers before service invocation
- lead-scoring and outreach prompts still deny at runtime because those services are not live yet

## Actor, Authority, And Audit Policy
### Actor Model
- Identity source: delegation.root_principal claims carried through ANIP token issuance
- Policy axes:
  - actor role
  - enrichment visibility level
  - lookalike-analysis authority

### Visibility And Restriction Rules
- Applies when: an actor has bounded enrichment visibility
- Governed outcome: success with bounded enrichment fields only
- Rationale: The service should redact sensitive enrichment fields without inventing a separate workflow.
- Applies when: an actor lacks lookalike-analysis authority
- Governed outcome: denied
- Rationale: Similarity analysis remains a governed capability, not a fallback side effect of enrichment summary.

### Audit Review Expectations
- bounded enrichment responses should remain auditable per actor
- lookalike denial and success paths should remain distinguishable in audit review
- cross-service handoff into enrichment should preserve actor and task continuity

## Requirements Signals
- Deployment intent: production_single_service
- Business constraint: PM defines behavior families and representative scenarios, not every user utterance
- Business constraint: Blocked failure posture: clean_denial_or_clarification_before_human_review
- Auth signal: Delegation Tokens
- Auth signal: Purpose Binding
- Auth signal: Scoped Authority
- Auth signal: Service To Service Handoffs
- Permission signal: Preflight discovery is required
- Permission signal: Grantable requirements are visible
- Permission signal: The permission model distinguishes restricted vs denied outcomes
- Audit signal: Durable
- Audit signal: Searchable

## Active Scenario Contract
- Narrative: A GTM user has already identified a small set of risky accounts from the pipeline service and now asks for bounded firmographic context plus explainable lookalike accounts.
- Expected behavior: account_scope_is_not_guessed_when_missing
- Expected behavior: enrichment_evidence_is_bounded_and_explainable
- Expected behavior: lookalikes_use_bounded_similarity_logic
- Expected behavior: raw_enrichment_exports_are_denied
- Expected ANIP support: signed_manifest_and_discovery
- Expected ANIP support: purpose_bound_tokens
- Expected ANIP support: bounded_capability_contracts
- Expected ANIP support: service_metadata_validation
- Scenario pack size: 1

## Service Implementation Contract
- Implementation language: python
- Runtime profile: fastapi_anip_service
- Transport profile: http_rest_anip
- Semantic backends: postgres_modeled_enrichment_views, curated_sql_account_enrichment_views
- Implementation root: not recorded
- Runtime entrypoint: not recorded

## Capability Contracts
### gtm.account_enrichment_summary
- Purpose: Return bounded firmographic context and fit signals for selected accounts.
- Side effect contract: read
- Minimum scope: gtm.enrichment.read
- Clarification required when:
  - account scope is missing
- Denied when:
  - the request asks for raw unconstrained enrichment export
- Approval required when:
  - none recorded
- Bounded evidence:
  - sector
  - region
  - revenue band
  - employee band
  - fit signal
  - intent signal
- Implementation notes:
  - return only bounded fields from the modeled enrichment view

### gtm.lookalike_accounts
- Purpose: Return bounded lookalike accounts using explainable similarity logic.
- Side effect contract: read
- Minimum scope: gtm.enrichment.read
- Clarification required when:
  - reference account is missing
- Denied when:
  - the request asks for unconstrained similarity export or scoring workflow
- Approval required when:
  - none recorded
- Bounded evidence:
  - reference profile
  - shared segment signals
  - bounded lookalike list
- Implementation notes:
  - similarity must remain explainable from modeled account attributes

## Metadata And Conformance Requirements
- Requirement: Manifest Required
- Requirement: Discovery Required
- Requirement: Signature Required
- Requirement: Jwks Uri Required
- Requirement: Purpose Bound Tokens Required
- Requirement: Audit Evidence Required
- Conformance check: service identity matches the intended GTM enrichment service
- Conformance check: both bounded enrichment capabilities are declared
- Conformance check: the service remains read-only
- Conformance check: manifest and discovery expose enough metadata for Studio validation

## Generated Implementation Trace
- Studio generation path: not recorded
- Generated scaffolds: not recorded
- Showcase runtime files: not recorded
- Business source artifact: req-gtm-enrichment-business-spec
- Requirements artifact: req-gtm-account-enrichment
- Scenario artifact: scn-gtm-account-enrichment
- Proposal artifact: prop-gtm-account-enrichment
- Shape artifact: shape-gtm-account-enrichment
- Generated code used for showcase: yes
- Running service: anip-gtm-enrichment-showcase

## Current Runtime Validation
- Status: HANDLED; runtime metadata captured with open conformance gaps.
- Observed metadata source: inspect_discovery_manifest
- Observed service: unknown
- Protocol declared: missing
- Manifest signature: not inspected
- JWKS URI: not inspected
- Missing intended capabilities: gtm.account_enrichment_summary, gtm.lookalike_accounts
- Broader than intended: none
- Runtime gap: the cross-service orchestration from risk review into enrichment selection still belongs to the agent/runtime layer
- Next change: Add the real external enrichment dataset after the bounded local enrichment loop is proven end to end.