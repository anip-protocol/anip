# ANIP Studio: Governed Integration Fronting for Native APIs and MCP

## Purpose

Studio should make it fast to design, generate, and verify ANIP services in front of existing enterprise systems.

The important point is that ANIP does not require MCP. ANIP can govern:

- native REST APIs
- GraphQL APIs
- database-backed services
- MCP servers
- mixed backends

MCP is one integration shape. It is not the trust boundary and it is not a prerequisite for ANIP.

## Positioning

The message should be:

- MCP gives agents access to tools and data.
- ANIP defines the governed way agents may use that access.
- Native APIs can be fronted directly when MCP is unnecessary or undesirable.
- The governed capability contract should stay stable even when the backend integration shape changes.

This lets ANIP support two strong stories:

- **Native API first:** ANIP is the governed service layer from the start.
- **MCP fronting:** ANIP can govern existing MCP investments without exposing raw MCP tools directly to agents.

## Design Principle

Studio must not generate "one ANIP capability per raw MCP tool" or "one ANIP capability per raw API endpoint" by default.

Raw backend operations are discovery input. ANIP capabilities are curated governed output.

The user should define or accept a small capability surface that captures:

- business intent
- required inputs
- allowed actors
- side-effect posture
- approval requirements
- denial and restriction rules
- clarification rules
- audit and lineage expectations
- backend operation mapping

Studio remains deterministic in every project type. AI assistance should be available and encouraged because it can accelerate discovery, mapping, and drafting, but it must stay optional. The same project can be completed manually through deterministic Studio flows.

## Project Model

Studio should introduce an explicit project type or project intent discriminator, but it should not make "MCP project" the top-level concept.

Recommended model:

```json
{
  "project_type": "governed_service_project",
  "integration_profile": {
    "kind": "native_api | mcp | database | hybrid",
    "systems": [
      {
        "system_id": "jira",
        "display_name": "Jira",
        "backend_kind": "native_api | mcp",
        "auth_mode": "user_delegated | service_delegated | external",
        "connection_ref": "connection-id"
      }
    ]
  }
}
```

This keeps ANIP generic:

- A Jira-native project and a Jira-MCP project can generate the same governed capability surface.
- A project can switch backend implementation without changing the business contract.
- Studio can later support GitHub, Slack, Stripe, Linear, Notion, Sentry, or internal systems without adding product-specific project types.

## Connection Model

Connection definitions should be workspace-scoped by default.

Rationale:

- credentials and identity provider bindings are usually organization or workspace concerns
- multiple projects may front the same enterprise system
- project exports should not contain secrets
- cloned projects should keep references explicit instead of copying credentials

Project JSON should store only connection references and non-secret capability mapping metadata.

Recommended workspace connection shape:

```json
{
  "connection_id": "conn-jira-prod",
  "display_name": "Jira Production",
  "backend_kind": "native_api | mcp | database",
  "system_kind": "jira",
  "endpoint_ref": "workspace-secret-or-config-ref",
  "auth_mode": "user_delegated | service_delegated | external",
  "identity_provider_ref": "sso-provider-ref",
  "secret_ref": "vault-or-local-secret-ref",
  "allowed_project_refs": ["project-id"],
  "created_at": "2026-04-21T00:00:00Z",
  "updated_at": "2026-04-21T00:00:00Z"
}
```

### Runtime-Only Fields

These must not be embedded in project JSON, exported Service Definitions, or blueprint manifests:

- raw API tokens
- OAuth refresh tokens
- client secrets
- service account private keys
- local MCP process credentials
- database passwords

Studio should reference them through workspace connection ids and secret references.

Hard rule:

**Developer Definition may describe integration expectations. It must not contain operational secrets, environment-bound credentials, or deploy-time secret material.**

### Importable Design Fields

These may be imported into Developer Design and exported into the ANIP Service Definition:

- backend kind
- system kind
- non-secret endpoint category
- selected raw operations
- raw operation schema summaries
- capability-to-operation mappings
- auth mode expectation
- required identity claims
- required actor scopes
- side-effect posture
- approval, denial, restriction, clarification, audit, and lineage rules

### Auth Modes

`user_delegated` means:

- Studio/ANIP authenticates the user centrally
- ANIP maps user identity to actor policy
- ANIP calls the downstream system with user-scoped delegation when available
- verifier evidence should include the expected delegated identity posture

`service_delegated` means:

- Studio/ANIP authenticates the user centrally
- ANIP enforces user/actor policy before backend access
- ANIP calls the downstream system with controlled service credentials
- verifier evidence must prove per-user policy was enforced before service credential use

`external` means:

- downstream identity and credentials are handled by an external gateway or runtime environment
- Studio records the expectation, but generated runtime must fail closed if the required external identity context is missing

### SSO and Actor Mapping

Workspace connections should support optional identity provider mappings:

- identity provider id
- claim-to-actor mapping
- group-to-scope mapping
- default denied posture when claims are missing
- audit subject claim
- delegated downstream subject claim, when applicable

This makes centralized ANIP the policy and audit boundary even when the backend is native API, MCP, database, or hybrid.

## Integration Profiles

### Native API

Native API fronting should be the primary enterprise architecture story.

Benefits:

- fewer moving parts
- direct control over auth, rate limits, payloads, and error handling
- centralized secrets management
- easier service-side policy enforcement
- cleaner generated adapter customization

Expected generated assets:

- ANIP service scaffold
- native API adapter
- connection configuration template
- policy and approval hooks
- verifier/regression scaffold

### MCP

MCP fronting should be the market bridge story.

Benefits:

- teams can reuse existing MCP servers
- broad MCP tool surfaces can be narrowed into governed capabilities
- ANIP can add policy, approval, audit, and deterministic verification above MCP

Expected generated assets:

- ANIP service scaffold
- MCP client adapter
- selected MCP operation mapping
- policy and approval hooks
- verifier/regression scaffold

### Hybrid

Hybrid projects should allow multiple backend systems behind one governed capability surface.

Example:

- Jira native API for issue write operations
- Confluence MCP for read-only policy lookup
- Slack native API for approval notification

The generated ANIP service remains the exposed agent-facing contract.

## Trust and Identity

Centralized ANIP should be the enterprise default.

It should own:

- enterprise SSO integration
- actor identity mapping
- policy enforcement
- approval state
- audit records
- backend credential handling
- runtime verification boundaries

ANIP should support two downstream auth modes:

- **User-delegated:** ANIP authenticates the user and calls downstream systems with user-scoped delegation when available.
- **Service-delegated:** ANIP authenticates the user centrally, enforces per-user policy, and calls downstream systems with controlled service credentials.

Local MCP remains useful for developer workflows and experimentation, but it should not be the primary enterprise governance story.

## Studio Flow

Studio should add a developer-side integration fronting flow:

1. Choose integration profile
2. Configure connection
3. Discover raw backend surface
4. Select raw operations that are allowed as backend supply
5. Define governed ANIP capabilities
6. Set actor, approval, denial, restriction, clarification, audit, and lineage rules
7. Generate wrapper service
8. Run verification and regression checks

The flow must support manual mode without AI assistance.

AI assistance can optionally propose:

- capability groupings
- dangerous raw operations
- read/write side-effect posture
- input/output contract drafts
- approval and denial rules
- verification scenarios

Assistant output remains proposal-only. The deterministic Studio model applies accepted patches and validates the result.

## Discovery Record Ownership

Raw discovery records should be operational metadata stored separately from the exported Service Definition.

Rationale:

- raw backend surfaces can be noisy, unstable, or environment-specific
- discovery may include operations that should never become agent-facing capabilities
- rediscovery should not mutate the canonical contract until the developer accepts mappings
- only accepted governed capability mappings should flow into Developer Design and the exported ANIP Service Definition

Accepted mappings should preserve enough references to trace a governed capability back to selected raw operations, but the Service Definition should not become a dump of every discovered backend operation.

## First Showcase

The first target should be Jira/Atlassian because the raw tool surface is familiar and the governance value is easy to explain.

Recommended first capability surface:

- `jira.search_team_backlog`
- `jira.prepare_bug_ticket`
- `jira.prepare_story_ticket`
- `jira.request_status_transition`
- `jira.add_incident_comment`
- `jira.prepare_incident_followup`

The demo should show the same governed capability contract over two backend implementations:

- Jira native REST API
- Atlassian MCP

The verifier should run the same regression pack against both.

This proves:

- ANIP does not require MCP.
- MCP can be governed when it already exists.
- backend integration shape is replaceable.
- governed capability semantics remain stable.

## Rovo MCP Outbound Governance Use Case

Atlassian Rovo MCP is a strong public use case because it makes the difference between access and governed use very visible.

Rovo MCP can expose Jira and related Atlassian operations to agents. That is useful, but the raw MCP layer does not, by itself, define the organization's behavior contract:

- which Jira projects agents may touch
- which issue types may be prepared or created
- which transitions may be requested versus executed
- which severity or customer-impact cases require approval
- which sensitive fields must be redacted before leaving the organization
- which requests should be denied, restricted, clarified, or audited
- which outbound payloads are acceptable for a third-party SaaS boundary

The ANIP use case is:

**Put centralized ANIP in front of Rovo MCP so the organization can govern and monitor what agents send to Atlassian.**

This is a stronger demo than simply wrapping Jira operations because it shows a concrete enterprise control gap:

- local skills and local MCP clients scatter behavior across user machines
- prompts cannot reliably enforce organization-wide outbound data policy
- raw MCP access can still send sensitive context to third-party systems if the local agent decides to include it
- centralized ANIP can inspect, redact, deny, require clarification, require approval, and audit before any downstream MCP call

### Demo Narrative

User request:

> Create a Sev-2 Jira bug from this customer incident summary and include the logs.

Raw MCP/skills path:

- the local agent decides which Jira tool to call
- the local agent decides what incident text and logs to send
- safety behavior depends on local skills, prompts, and user setup
- organization-level audit may only see the final Jira issue, not the attempted outbound context

ANIP-fronted path:

- the agent calls `jira.prepare_bug_ticket`
- ANIP classifies the request as write-adjacent and customer-impacting
- ANIP checks actor scope, allowed project, allowed issue type, and severity threshold
- ANIP scans the outbound candidate payload for sensitive fields, secrets, PII, internal-only data, or restricted log excerpts
- ANIP redacts, masks, denies, clarifies, or requires approval before any Rovo MCP call
- ANIP records the decision, redaction summary, approval state, downstream operation ref, and final payload digest

### Governed Capabilities

Initial Rovo MCP capability surface:

- `jira.search_team_backlog`
- `jira.prepare_bug_ticket`
- `jira.prepare_story_ticket`
- `jira.request_status_transition`
- `jira.prepare_incident_followup`
- `jira.add_incident_comment`

The important design choice is that raw Rovo MCP tools are not exposed directly to agents. They are backend supply for governed ANIP capabilities.

### Outbound Control Contract

The ANIP Service Definition should make outbound control explicit:

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

This makes outbound monitoring part of the generated contract, not a hidden skill instruction.

### Evidence ANIP Should Capture

For each governed downstream call, ANIP should emit evidence such as:

- caller identity and mapped actor
- requested capability
- raw backend operation target
- source payload digest
- outbound payload digest
- redaction decisions and counts
- denied fields or blocked categories
- approval decision id, when required
- clarification questions asked and answered
- final downstream operation id or skipped operation reason
- timestamp and policy version

This evidence is the key enterprise value. It lets the organization prove what was inspected, what was sent, what was blocked, and why.

### Behavior Inference Inputs

Since Rovo MCP lacks organization-specific behavior, Studio should infer a proposal from multiple evidence sources:

- Rovo MCP tool names, descriptions, input schemas, and output schemas
- Jira project metadata, issue types, custom fields, priorities, transitions, and workflow rules
- Atlassian API documentation or OpenAPI-like contracts where available
- internal Jira process docs, incident runbooks, release policies, and support escalation docs
- data classification and external-sharing policies
- existing skills, prompts, and runbooks as migration evidence, not runtime truth
- historical Jira examples such as bug tickets, incidents, transition histories, comments, and labels

The assistant should produce proposal bundles:

- candidate governed capabilities
- candidate raw MCP operation mappings
- candidate required inputs and output intent
- candidate approval, denial, restriction, clarification, redaction, and audit rules
- targeted blocking questions only where evidence is missing

The deterministic Studio model still owns acceptance and validation.

### Minimal Clarification Questions

The assistant should not ask PMs to manually design Jira behavior field by field. It should infer first and ask only material questions, such as:

- Which Jira projects may this ANIP service access?
- Should agents ever execute Jira transitions, or only request transition drafts?
- Which severity or customer-impact thresholds require approval?
- Which fields or log categories must never be sent to Atlassian?
- Should comments be prepare-only, approval-gated, or directly allowed for specific actors?
- Which user identity should appear in downstream Jira actions: user-delegated identity or service-delegated ANIP identity?

### Studio Product Implication

For this use case, Source Docs should support these source categories:

- fronting intent
- MCP schema
- API docs
- auth and scopes
- permission matrix
- workflow/status docs
- org policy
- runtime evidence
- existing skills/prompts/runbooks as migration evidence

The AI readiness gate should not require a traditional PM business spec. It should require enough fronting intent plus integration evidence to draft a governed capability proposal.

## Jira Native Example

This example is intentionally concrete so the first implementation slice has a stable target.

### Workspace Connection

```json
{
  "connection_id": "conn-jira-prod",
  "display_name": "Jira Production",
  "backend_kind": "native_api",
  "system_kind": "jira",
  "endpoint_ref": "jira-prod-base-url",
  "auth_mode": "service_delegated",
  "identity_provider_ref": "corp-sso",
  "secret_ref": "vault://anip/jira/service-account",
  "allowed_project_refs": ["proj-jira-governance-demo"]
}
```

The `secret_ref` is runtime-only. Project JSON, Service Definition exports, and blueprint manifests may reference `conn-jira-prod`, but must not include the service account token.

### Raw Discovery Record

```json
{
  "operation_id": "jira.create_issue",
  "connection_ref": "conn-jira-prod",
  "backend_kind": "native_api",
  "method": "POST",
  "path_template": "/rest/api/3/issue",
  "side_effect_level": "write",
  "input_schema_summary": {
    "required": ["project_key", "issue_type", "summary"],
    "optional": ["description", "priority", "labels", "assignee"]
  },
  "risk_notes": [
    "Creates a durable Jira issue.",
    "Must not be exposed directly as an agent-facing operation."
  ]
}
```

### Governed Capability Mapping

```json
{
  "capability_id": "jira.prepare_bug_ticket",
  "title": "Prepare Bug Ticket",
  "intent": "Draft a governed Jira bug ticket from a defect or incident summary.",
  "backend_operations": ["jira.create_issue"],
  "execution_posture": "prepare_only",
  "side_effect_level": "write_adjacent",
  "required_inputs": ["project_key", "summary", "severity", "customer_impact"],
  "allowed_issue_types": ["Bug"],
  "approval_rule_refs": ["approval.sev2_or_customer_impact"],
  "denial_rule_refs": ["deny.unsupported_project"],
  "clarification_rule_refs": ["clarify.missing_reproduction"],
  "audit_required": true
}
```

The governed capability may prepare a ticket payload and request approval. It must not call the raw create-issue operation unless the declared approval and actor policy allow it.

### Service Definition Fragment

```json
{
  "integration_profile": {
    "kind": "native_api",
    "systems": [
      {
        "system_id": "jira",
        "backend_kind": "native_api",
        "connection_ref": "conn-jira-prod",
        "auth_mode": "service_delegated"
      }
    ]
  },
  "capabilities": [
    {
      "id": "jira.prepare_bug_ticket",
      "subject_kind": "jira_issue",
      "context_type": "incident_or_defect_summary",
      "output_intent": "approval_ready_ticket_draft",
      "side_effect_level": "write_adjacent",
      "backend_operation_refs": ["jira.create_issue"]
    }
  ]
}
```

### Generated Adapter Binding Fragment

```json
{
  "service_id": "jira-governance-service",
  "capability_id": "jira.prepare_bug_ticket",
  "adapter_kind": "native_api",
  "connection_ref": "conn-jira-prod",
  "operation_ref": "jira.create_issue",
  "binding_mode": "approval_gated_execution",
  "secret_ref_required": true
}
```

The same capability contract can later bind to an Atlassian MCP operation by changing the adapter binding, not by changing the agent-facing capability semantics.

### Deployment-Time Backend Selection

Hybrid integration profiles may bind one governed capability to multiple backend implementation shapes, such as native API plus MCP. The Service Definition remains the behavior authority, while generated deployment assets declare which backend binding is active in a specific environment.

Studio/generator output should include a `backend-selection.template.json` whenever any capability has more than one backend binding. The template is deployment configuration, not business truth. Local conformance must fail if hybrid bindings exist and no backend-selection template was generated.

```json
{
  "template_kind": "anip_backend_selection_template",
  "selection_scope": "deployment",
  "service_definition_digest": "sha256:...",
  "capabilities": [
    {
      "capability_id": "jira.prepare_bug_ticket",
      "service_id": "jira-governance-service",
      "selection_required": true,
      "active_backend_kind": "",
      "active_connection_ref": "",
      "available_backend_bindings": [
        {
          "backend_kind": "native_api",
          "connection_ref": "conn-jira-prod",
          "raw_operation_refs": ["jira.create_issue"]
        },
        {
          "backend_kind": "mcp",
          "connection_ref": "conn-atlassian-mcp-prod",
          "raw_operation_refs": ["atlassian.create_jira_issue"]
        }
      ]
    }
  ]
}
```

## Guardrails

Studio should explicitly prevent unsafe shortcuts:

- no automatic "expose every MCP tool" mode
- no automatic "expose every REST endpoint" mode
- no raw write operation exposed directly to agents without a governed capability wrapper
- no hidden prompt-only policy
- no assistant-only workflow requirement
- no final truth written by AI without deterministic validation

## Implementation Slices

### Slice 1: Model and UX Foundation

- Add `project_type` and `integration_profile` to Studio project metadata.
- Add a governed integration project creation path.
- Add native API, MCP, database, and hybrid profile options.
- Add workspace-scoped connection metadata stubs without storing secrets in project JSON.
- Add explicit `user_delegated`, `service_delegated`, and `external` auth mode handling.

### Slice 2: Discovery Records

- Add persisted raw backend operation discovery records.
- Support manual operation entry first.
- Add MCP discovery adapter later.
- Add native OpenAPI/import support later.

### Slice 3: Governed Capability Mapping

- Add UI to map selected raw operations to governed capabilities.
- Capture side-effect posture, actor scope, approvals, denials, clarifications, audit, and lineage.
- Store mapping in Developer Design and export it into Developer Definition.

### Slice 4: Generator Support

- Generate ANIP wrapper service with backend adapter interface.
- Generate native API adapter template.
- Generate MCP adapter template.
- Generate deployment backend-selection templates for hybrid backend bindings.
- Keep implementation-specific assets in the implementation-template layer.

### Slice 5: Verification

- Generate regression scenarios for approval, denial, clarification, actor restriction, and compound flows.
- Verify the same governed contract against native and MCP backend implementations.
- Verify outbound payload inspection, redaction, approval gating, denial, and audit evidence before third-party calls.

### Slice 6: Rovo MCP Outbound Governance Demo

- Add Rovo MCP as the first MCP-backed fronting target.
- Import or manually enter Rovo MCP Jira tool schemas as raw operation metadata.
- Add outbound-control metadata to governed capability mappings.
- Add payload inspection and redaction policy proposals.
- Emit outbound evidence records for attempted and completed downstream MCP calls.
- Demonstrate a sensitive incident-to-Jira flow where ANIP blocks or redacts data before Atlassian receives it.

## First Complete Slice

The first vertical slice should prove the full model without requiring public registry or MCP support:

1. Manual raw Jira native operation entry.
2. Governed capability mapping.
3. Service Definition export.
4. Native API wrapper generation.
5. Local conformance report.

AI assistance can propose mappings and policy defaults, but the deterministic manual path must work end to end.

The second vertical slice should prove the Rovo MCP outbound-governance story:

1. Rovo MCP raw Jira operation metadata.
2. Governed `jira.prepare_bug_ticket` mapping.
3. Outbound payload inspection and redaction rules.
4. Approval-gated downstream MCP execution.
5. Evidence record showing what was inspected, redacted, approved, denied, and sent.

## Open Questions

- Should workspace-scoped connections support project-local non-secret overrides such as sandbox endpoint labels or discovery filters?
- How should Studio represent user-delegated downstream auth during local development?
- Should MCP discovery be done by Studio backend directly or by a generated connector probe?
- What is the minimal shared adapter interface needed across native API and MCP backends?
- What repository shape should store operational discovery metadata so it can be refreshed without mutating exported Service Definitions?
