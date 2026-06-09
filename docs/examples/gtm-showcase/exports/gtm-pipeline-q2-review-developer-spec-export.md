# Developer Spec: GTM Pipeline Q2 Review

Generated: 2026-04-12 22:16:23

## Traceability
- Artifact role: Canonical Developer Spec
- Project: GTM Pipeline Q2 Review
- Primary consumer: Both people and agents
- Requirements set: GTM pipeline review requirements
- Scenario: Hero path: at-risk Q2 deals to approval stop
- Service design: GTM pipeline service design
- Evaluation: eval-gtm-pipeline-q2-review (HANDLED)

## Technical Purpose
Turn the PM-owned GTM behavior specification into one bounded ANIP service contract with explicit clarification, denial, approval, metadata, and implementation expectations.

## Translation Chain
- Source business spec: Canonical GTM business spec (docs/examples/gtm-showcase/business-spec.md)
- Translated requirements: GTM pipeline review requirements
- Active scenario: Hero path: at-risk Q2 deals to approval stop
- Proposal: GTM pipeline single-service proposal
- Service design: GTM pipeline service design
- Evaluation status: eval-gtm-pipeline-q2-review (HANDLED)

## Developer Enrichment
- Principle: keep the first release on one reproducible pipeline dataset and one pipeline-focused service
- Principle: encode clarification, denial, and approval_required in the service contract instead of agent glue
- Principle: use Postgres plus dbt plus Cube as implementation internals, not as the external capability surface
- Principle: keep follow-up work at prepare-only until downstream mutation approval exists
- Decision: one GTM Pipeline Service owns all phase 1 pipeline review capabilities
- Decision: all read capabilities require bounded evidence rather than raw row-level export
- Decision: follow-up preparation is exposed as approval-gated work, not automatic execution
- Decision: phase 1 uses denial, not restricted, for raw row-level export requests
- Decision: manifest, discovery, and runtime evidence must be sufficient for Studio conformance validation

## Behavior Placement
Studio should make behavior placement explicit. Important behavior should live in the service contract or an explicit orchestration contract. Remaining runtime glue should stay thin, mechanical, and visible.

### Service-Covered Behavior
- missing quarter or ranking basis yields clarification_required in the service contract
- raw row-level export requests are denied by the bounded pipeline service contract
- actors asking for broader pipeline scope receive explicit restricted outcomes
- actors without follow-up preparation authority are denied at the service boundary
- authorized follow-up preparation returns approval_required with a durable approval request instead of mutating downstream systems
- financially bounded actors receive masked values while keeping the bounded answer shape intact

### Orchestration-Covered Behavior
- the runtime carries actor identity into ANIP token issuance without deciding the actor-specific business outcome itself
- approval review and audit lookup remain explicit runtime surfaces over service-recorded state

### Cross-Service Contract
- No explicit cross-service contract is recorded yet.

### Remaining Runtime Glue
- mechanical quarter normalization still happens in the runtime before invocation
- runtime preflight still denies clearly out-of-scope lead-scoring and outreach requests because those services are not live yet

## Actor, Authority, And Audit Policy
### Actor Model
- Identity source: delegation.root_principal claims carried through ANIP token issuance
- Policy axes:
  - actor role
  - declared business scope
  - financial visibility level
  - follow-up preparation authority
  - follow-up approval authority

### Visibility And Restriction Rules
- Applies when: an actor asks for a pipeline scope broader than the scope encoded in their claims
- Governed outcome: restricted
- Rationale: The service should return the actor-safe scope posture explicitly instead of silently broadening access.
- Applies when: an analytical actor lacks full financial visibility
- Governed outcome: success with masked financial values
- Rationale: The same bounded answer shape can remain available while sensitive values are redacted.

### Approval Authority Rules
- Action: prepare follow-up tasks
- Requester posture: authorized operators may receive approval_required with a durable approval request
- Approver requirement: a separate actor with follow-up approval authority must approve the request before execution can proceed
- Notes:
  - request preparation authority is distinct from approval authority
  - approval requests must remain queryable and auditable after creation

### Audit Review Expectations
- the actor identity used for the invocation must remain visible in the audit trail
- different actor outcomes for the same request must remain reviewable after the fact
- approval state transitions must remain durable and queryable

### Linked Approval Review Surface
- List path: /gtm/approvals
- Approve path template: /gtm/approvals/{approvalRequestId}/approve
- Notes:
  - Studio can review the durable request state through the linked approval surface.
  - The approval surface is service-defined and intentionally separate from the ANIP invoke path.

## Requirements Signals
- Deployment intent: production_single_service
- Business constraint: PM defines behavior families and representative scenarios, not every user utterance
- Business constraint: Raw row-level exports are out of scope for the Phase 1 service
- Business constraint: Follow-up execution must stop until approval exists
- Business constraint: Q2 pipeline review must stay reproducible locally
- Business constraint: High-risk work requires approval review
- Business constraint: Recovery-sensitive behavior must remain reviewable
- Business constraint: Escalate to human review only for unresolved or approval-gated work
- Business constraint: Quarter must be clarified when missing
- Business constraint: Ranking basis must be clarified when missing
- Business constraint: Phase 1 export posture: deny raw row-level export requests
- Auth signal: Delegation Tokens
- Auth signal: Purpose Binding
- Auth signal: Scoped Authority
- Permission signal: Preflight discovery is required
- Permission signal: Grantable requirements are visible
- Permission signal: The permission model distinguishes restricted vs denied; Phase 1 export policy currently uses denied
- Audit signal: Durable
- Audit signal: Searchable

## Active Scenario Contract
- Narrative: A revenue operator asks which deals in the Q2 pipeline are at risk, expects clarification when the scope is underspecified, wants bounded evidence for why the accounts are risky, then asks the system to prepare follow-up tasks and stop before any downstream mutation until approval exists.
- Expected behavior: quarter_and_ranking_basis_are_not_guessed_when_missing
- Expected behavior: risk_evidence_is_bounded_and_explainable
- Expected behavior: row_level_exports_are_denied
- Expected behavior: followup_plan_stops_at_approval_required
- Expected ANIP support: signed_manifest_and_discovery
- Expected ANIP support: purpose_bound_tokens
- Expected ANIP support: bounded_capability_contracts
- Expected ANIP support: service_metadata_validation
- Expected ANIP support: runtime_evidence_and_drift_analysis
- Scenario pack size: 5

## Service Implementation Contract
- Implementation language: python
- Runtime profile: fastapi_anip_service
- Transport profile: http_rest_anip
- Semantic backends: postgres_raw_tables, dbt_modeled_pipeline_views, cube_semantic_queries
- Implementation root: examples/showcase/gtm/services/gtm_pipeline
- Runtime entrypoint: examples/showcase/gtm/services/gtm_pipeline/app.py

## Capability Contracts
### gtm.pipeline_summary
- Purpose: Return a bounded pipeline health summary for a quarter and optional scope.
- Side effect contract: read
- Minimum scope: gtm.pipeline.read
- Clarification required when:
  - quarter is missing
  - scope is underspecified for the requested comparison
- Denied when:
  - the user asks for raw row-level export instead of a bounded summary
- Approval required when:
  - none recorded
- Bounded evidence:
  - stage mix
  - pipeline totals
  - bounded risk indicators
- Implementation notes:
  - read from dbt-modeled pipeline views
  - use Cube measures for bounded aggregations

### gtm.stalled_opportunity_review
- Purpose: Return stalled open opportunities with bounded evidence and explainable stall reasoning.
- Side effect contract: read
- Minimum scope: gtm.pipeline.read
- Clarification required when:
  - stalled-days threshold is missing when the request is ambiguous
- Denied when:
  - the user asks for unconstrained raw pipeline export
- Approval required when:
  - none recorded
- Bounded evidence:
  - days in stage
  - owner
  - account
  - amount bucket
- Implementation notes:
  - derive stall duration from modeled opportunity dates

### gtm.account_risk_summary
- Purpose: Rank at-risk accounts with explicit evidence for why they need attention.
- Side effect contract: read
- Minimum scope: gtm.pipeline.read
- Clarification required when:
  - quarter is missing
  - ranking basis is missing
- Denied when:
  - the request asks for unconstrained export or out-of-scope outreach work
- Approval required when:
  - none recorded
- Bounded evidence:
  - open opportunity count
  - stalled opportunity indicators
  - risk score components
- Implementation notes:
  - risk ranking must stay explainable in the response payload

### gtm.prepare_followup_tasks
- Purpose: Prepare follow-up tasks for high-risk accounts without executing downstream mutations.
- Side effect contract: approval-gated write contract; the Phase 1 runtime returns an approval_required preview until approval exists
- Minimum scope: gtm.pipeline.followup
- Clarification required when:
  - target accounts or quarter are missing
- Denied when:
  - the request asks to execute CRM mutations directly in phase 1
- Approval required when:
  - any downstream task creation or CRM mutation would occur
- Bounded evidence:
  - proposed task preview
  - target account list
  - reason each task was suggested
- Implementation notes:
  - return approval_required with a preview payload instead of mutating downstream systems

## Metadata And Conformance Requirements
- Requirement: Manifest Required
- Requirement: Discovery Required
- Requirement: Signature Required
- Requirement: Jwks Uri Required
- Requirement: Purpose Bound Tokens Required
- Requirement: Audit Evidence Required
- Conformance check: service identity matches the intended GTM pipeline service
- Conformance check: all four bounded capabilities are declared
- Conformance check: approval-gated write posture is visible for gtm.prepare_followup_tasks
- Conformance check: manifest and discovery expose enough metadata for Studio validation

## Generated Implementation Trace
- Studio generation path: business_spec -> business_design -> developer_design -> generated_service_scaffold
- Generated scaffolds: data_access_service.py, data_access_backend_adapter.py
- Showcase runtime files: examples/showcase/gtm/services/gtm_pipeline/app.py, examples/showcase/gtm/services/gtm_pipeline/capabilities.py, examples/showcase/gtm/services/gtm_pipeline/data.py
- Business source artifact: req-gtm-pipeline-business-spec
- Requirements artifact: req-gtm-pipeline-q2-review
- Scenario artifact: scn-gtm-pipeline-q2-review
- Proposal artifact: prop-gtm-pipeline-q2-review
- Shape artifact: shape-gtm-pipeline-q2-review
- Generated code used for showcase: yes
- Running service: anip-gtm-pipeline-showcase
- Validation method: Studio compares intended service design against observed manifest and discovery metadata
- Validation method: Studio uses saved runtime evidence to confirm the hero path stays within the developer contract

## Current Runtime Validation
- Status: HANDLED; runtime metadata captured with open conformance gaps.
- Observed metadata source: inspect_discovery_manifest
- Observed service: anip-gtm-pipeline-showcase
- Protocol declared: anip/0.22
- Manifest signature: missing
- JWKS URI: missing
- Missing intended capabilities: none
- Broader than intended: none
- Runtime gap: the final operator workflow for executing approved follow-up tasks still belongs to the later multi-service phase
- Next change: Add enrichment and outreach services only after the pipeline review loop is proven end to end.
- Next change: Capture signed manifest and JWKS metadata in the live showcase runtime so the developer contract validates without caveats.