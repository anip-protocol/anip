# Governed Integration Fronting Studio Plan

## Purpose

Studio should make it easy to create an ANIP service in front of an existing API, MCP server, database-backed system, or hybrid backend.

The product value is not "connect another tool." The value is turning broad backend access into a small, governed, reviewable, generated, and verifiable service contract.

The core message:

- MCP exposes tools.
- Native APIs expose endpoints.
- ANIP exposes the allowed way an agent may use them.

This is the practical answer to organizations that are being pushed toward "skills for everything" and "MCP for everything." Skills and MCP are useful, but they are not the governance layer.

## Positioning

ANIP fronting should support two equally important stories.

### Native API First

Use ANIP directly in front of REST, GraphQL, database, or internal service APIs.

This is the cleaner enterprise default when an organization controls the integration:

- fewer moving parts than MCP
- direct control over auth, payloads, rate limits, and error handling
- centralized SSO, policy, approvals, and audit
- no need to build an MCP server first

### MCP Governance Bridge

Use ANIP in front of existing MCP servers.

This is the market-bridge story:

- teams can keep existing MCP investments
- raw MCP tools become backend supply, not the agent-facing contract
- ANIP centralizes policy, approval, denial, clarification, redaction, and audit
- organizations do not need every team to maintain local skill files that teach agents how to use broad MCP tools safely

## Current State

The repository already has the right foundation:

- `governed_service_project` exists as a Studio project type.
- Projects can declare integration profiles: `native_api`, `mcp`, `database`, or `hybrid`.
- Workspace connections are separate from project JSON and can reference endpoint, identity provider, and secret refs.
- Raw backend operation discovery records are stored separately from the exported Service Definition.
- Governed capability mappings can point to selected raw operations.
- Developer Definition exports `integration_fronting.capability_mappings`.
- Generator metadata includes backend bindings, backend input modes, governance refs, and outbound controls.
- Hybrid mappings can bind one governed capability to multiple backend realizations.
- A seeded issue-tracker fronting showcase already exists as a conceptual proof.

This is directionally correct. The missing piece is product quality: the flow still feels like entering backend metadata, not like creating a governed ANIP front door for an enterprise system.

## Product Principle

Studio must not generate one ANIP capability per raw tool or endpoint by default.

Raw backend operations are discovery input.
Governed ANIP capabilities are curated output.

The user should be guided toward a small capability surface such as:

- `jira.search_team_backlog`
- `jira.prepare_bug_ticket`
- `jira.prepare_story_ticket`
- `jira.request_status_transition`
- `jira.add_incident_comment`
- `jira.prepare_incident_followup`

The raw backend may be:

- Jira REST API
- Atlassian/Rovo MCP
- both

The agent-facing behavior should remain stable.

## Target Studio Experience

The fronting flow should be a first-class Studio lane, not a generic metadata page.

Recommended create-project option:

> Govern an existing API or MCP server

Recommended guided flow:

1. Choose backend shape
2. Configure workspace connection refs
3. Discover or enter raw backend operations
4. Select operations that are allowed as backend supply
5. Propose governed ANIP capabilities
6. Review actor access, approvals, denials, clarification, redaction, and audit
7. Generate ANIP wrapper service
8. Run verifier/regression checks
9. Package and publish

The deterministic path must work manually. The assistant should make the workflow dramatically easier, but assistant output must remain proposal-only until accepted into the deterministic Studio model.

## Fronting Assistant Behavior

The current backend-binding assistant is too generic. Governed fronting needs a dedicated assistant workflow.

The assistant should infer first and ask only material questions.

Inputs:

- project/fronting intent
- API docs or OpenAPI-like schemas
- MCP tool names, descriptions, input schemas, and output schemas
- auth and scope docs
- workflow/status docs
- org policy and data classification docs
- existing prompts, skills, and runbooks as migration evidence
- historical tickets, comments, actions, or audit examples when available

Outputs:

- candidate governed capabilities
- candidate raw backend operation mappings
- candidate semantic inputs
- candidate backend bindings
- candidate side-effect posture
- candidate approval rules
- candidate denial/restriction rules
- candidate clarification prompts
- candidate outbound redaction controls
- candidate verification scenarios

Material questions should be narrow, for example:

- Which projects/workspaces may this service access?
- Should agents execute writes or only prepare/preview them?
- Which severity, customer-impact, money, or workflow thresholds require approval?
- Which fields or payload categories must never leave the organization?
- Should downstream calls use user-delegated identity or service-delegated identity?

## First Showcase

The first polished showcase should be issue tracker fronting.

Use Jira-like semantics because the value is immediately understandable:

- search backlog
- prepare bug/story tickets
- add incident comments
- request status transitions
- require approval for high-risk writes
- deny unsupported projects
- clarify missing required fields
- redact sensitive incident payloads before outbound calls
- audit attempted and completed downstream calls

The strongest demo compares the same ANIP capability contract over two backend realizations:

- Jira native REST API
- Atlassian/Rovo MCP

This proves:

- ANIP does not require MCP.
- MCP can be governed when it already exists.
- Backend integration shape is replaceable.
- The governed capability contract remains the stable system behavior.

## Outbound Governance

Outbound governance must become first-class in the fronting model.

For third-party SaaS boundaries, ANIP should be able to inspect and decide before data leaves the organization.

The contract should express:

- third-party boundary
- payload inspection requirement
- redaction policy refs
- deny policy refs
- approval policy refs
- clarification policy refs
- audit evidence requirement

Example:

```json
{
  "capability_id": "jira.prepare_bug_ticket",
  "backend_operation_refs": ["rovo_mcp.jira.create_issue"],
  "execution_posture": "prepare_only",
  "side_effect_level": "write_adjacent",
  "outbound_controls": {
    "third_party_boundary": "atlassian",
    "payload_inspection_required": true,
    "redaction_policy_refs": ["redact.customer_pii", "redact.secrets", "redact.internal_logs"],
    "approval_policy_refs": ["approval.sev2_or_customer_impact"],
    "deny_policy_refs": ["deny.unsupported_project", "deny.raw_secret_detected"],
    "clarification_policy_refs": ["clarify.missing_reproduction", "clarify.customer_impact"],
    "audit_required": true
  }
}
```

Evidence should include:

- caller identity and mapped actor
- requested capability
- selected backend binding
- source payload digest
- outbound payload digest
- redaction decisions
- blocked categories
- approval decision id
- clarification questions and answers
- final downstream operation id or skipped-operation reason
- policy version

## Generator Expectations

Generated fronting services should include:

- ANIP service scaffold
- backend adapter interface
- native API adapter template
- MCP adapter template
- backend selection template for hybrid bindings
- policy hook stubs
- outbound inspection/redaction extension points
- audit evidence emitter hooks
- verifier/regression pack scaffold

The generated adapter should make customization obvious. It should not pretend generic code can safely understand every enterprise API or MCP server.

Generated behavior should be explicit:

- semantic capability contract is stable
- backend binding is replaceable
- backend-specific request building lives in adapter extension points
- substrate files should remain generated
- custom code should fill declared extension points only

## UX Gaps To Fix

The current `IntegrationFrontingView` is a foundation, but it needs a product pass.

Priority UX changes:

- Rename the lane to something user-facing, such as `Govern Existing API / MCP`.
- Add an obvious create-project path for fronting.
- Replace generic metadata cards with a guided fronting workflow.
- Add import/discovery affordances for MCP schemas and API docs.
- Add a curated capability proposal/review screen.
- Add first-class outbound controls instead of raw text fields.
- Add a clear "raw operation supply" versus "governed capability contract" visual.
- Add explicit native API vs MCP vs hybrid backend comparison.
- Add a "generate wrapper service" call to action only after mappings are coherent.
- Add fronting-specific assistant actions instead of generic backend-binding proposals.

## Implementation Plan

### Slice 1: Productize The Existing Lane

- Rename and reposition the current Integration Fronting page.
- Add clearer copy around "raw backend operations are not agent-facing."
- Add a workflow overview that matches the target flow.
- Add fronting-specific empty states and examples.
- Add direct navigation from governed fronting project creation to the fronting lane.

### Slice 2: Dedicated Fronting Assistant

- Add assistant capability: `propose_governed_fronting_capabilities`.
- Feed it project docs, raw operation records, connection profile, and existing skills/prompts/runbooks.
- Return candidate capability mappings, outbound controls, and verification scenarios.
- Keep accepted output as deterministic Studio artifacts.

### Slice 3: Outbound Controls As First-Class Data

- Replace loose outbound-control arrays/objects with typed Studio fields.
- Support third-party boundary, redaction refs, approval refs, denial refs, clarification refs, and audit evidence expectations.
- Export the structured data into Developer Definition and package metadata.

### Slice 4: Discovery Import

- Add manual import for MCP tool schema JSON.
- Add manual import for OpenAPI fragments.
- Normalize imported operations into discovery records.
- Do not mutate governed mappings on rediscovery without user acceptance.

### Slice 5: Generator And Verifier Polish

- Emit backend-selection templates for hybrid fronting.
- Emit adapter extension points for native API and MCP backends.
- Emit outbound inspection/redaction hooks.
- Emit fronting regression scenarios.
- Verify clarification, denial, approval, redaction, backend selection, and audit evidence.

### Slice 6: Polished Jira/Rovo Showcase

- Build a complete fronting project from source docs.
- Generate contract, package, and wrapper code.
- Run the same regression pack against native and MCP bindings where feasible.
- Document the demo as "MCP gives access; ANIP governs use."

## Acceptance Criteria

The fronting feature is working when a user can:

- Create a governed fronting project without knowing ANIP internals.
- Import or enter raw MCP/API operations.
- Get a small proposed governed capability surface.
- Review only the meaningful governance decisions.
- Generate an ANIP wrapper service.
- See where backend-specific customization belongs.
- Verify approvals, denials, clarifications, redaction, and audit behavior.
- Package/publish the service without leaking secrets.

The feature is compelling when the Jira/Rovo demo clearly shows:

- raw MCP tools are not exposed directly
- skills are not the governance layer
- centralized ANIP decides what is allowed
- sensitive outbound payloads can be inspected before downstream calls
- native API and MCP bindings can share the same governed contract

## Non-Goals

- Do not make MCP a prerequisite for ANIP.
- Do not expose every MCP tool or API endpoint by default.
- Do not store secrets in project exports or package manifests.
- Do not rely on prompt text or skill files for authority boundaries.
- Do not hide backend-specific behavior inside generated substrate files.
- Do not require AI for deterministic completion.

## Near-Term Recommendation

Build this next as a product-quality vertical slice:

1. Productize the existing Integration Fronting lane.
2. Add the dedicated fronting assistant action.
3. Make outbound controls first-class.
4. Generate a complete issue-tracker fronting package.

This is one of the clearest enterprise-value demonstrations for ANIP because it reframes MCP correctly:

MCP is access.
ANIP is governed use.
