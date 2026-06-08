---
title: Governed Fronting
description: Use ANIP to put a governed capability surface in front of existing APIs, GraphQL services, MCP servers, databases, and analytics systems.
---

# Governed Fronting

Governed fronting is the pattern of placing an ANIP service in front of an existing system. The existing system may expose REST, GraphQL, MCP, SQL, SDKs, dbt, Cube, Databricks, Snowflake, Jira, Slack, GitHub, Superset, or something internal. ANIP exposes the governed capability surface.

The central rule:

```text
Backend APIs are implementation material.
ANIP capabilities are the agent-facing behavior contract.
```

Fronting is not a transport choice. It is a boundary choice.

```text
agent/client
  -> governed ANIP capability contract
  -> service-side policy, approval, denial, audit, and implementation seam
  -> existing backend system
```

The backend can change from REST to GraphQL, MCP, SQL, dbt, Cube, Snowflake, Databricks, or an internal gateway without changing the ANIP contract, as long as the governed behavior does not change.

## Why front an existing system?

MCP and APIs often expose broad operational surfaces:

- Search.
- Create.
- Update.
- Delete.
- Transition.
- Run query.
- Generate chart.
- Send message.

Agents can call those tools, but the organization still needs to define:

- Which operations are allowed?
- Which projects, channels, repos, datasets, or workspaces are in scope?
- What requires approval?
- What must be denied?
- What should be clarified?
- What should be preview-only?
- What should be audited?

ANIP fronting puts those rules on the service side.

## What fronting is not

Fronting is not:

- Renaming every backend endpoint as an ANIP capability.
- Publishing one capability per MCP tool.
- Giving the agent `execute_sql`, `post_message`, `create_issue`, or `dispatch_workflow` with better descriptions.
- Moving unsafe behavior into a skill file, prompt, or client-side workflow.
- Treating backend auth as enough business governance.

Backend RBAC and OAuth still matter, but they answer a different question: can this credential call the backend? ANIP answers the agent-facing execution question: should this actor be allowed to perform this governed business action now, with these inputs, under this approval and audit posture?

## Native API vs MCP

ANIP does not require MCP. In many production cases, native APIs are the cleaner backend:

- Fewer layers.
- Better observability.
- More direct auth and policy integration.
- Stronger control over payload shaping.
- Easier testing.

MCP is still useful:

- As a comparison surface.
- As an existing integration source.
- As an ingress compatibility layer when clients already speak MCP.
- As an optional backend implementation binding if the MCP server provides useful orchestration.

The first release showcase packages intentionally use native APIs as the execution binding for Jira, GitHub, Slack, GitLab, Linear, Notion, and Superset. MCP is documented as a comparison surface, not as the hidden behavior contract.

For the detailed positioning, see [ANIP vs MCP](/docs/concepts/anip-vs-mcp).

For the concrete showcase set, see [Fronting Showcases](/docs/showcases/fronting).

## Release-grade flow

The release-grade fronting flow should go through Studio, Registry, and generated code:

1. Collect source evidence: API docs, OpenAPI/GraphQL schema, MCP tool list, product rules, security policy, examples, and live smoke notes.
2. Create or import a fronting starter/template in Studio.
3. Define Product Design in business terms: actors, use cases, allowed outcomes, unsafe outcomes, and approval posture.
4. Define Developer Design as governed capabilities, not raw backend operations.
5. Capture backend operation evidence as implementation profile metadata.
6. Generate a strict `anip/0.24` Developer Definition.
7. Resolve diagnostics and approve the release lineage.
8. Publish the package to Registry.
9. Generate the service from the Registry package or package bundle.
10. Add custom implementation material for the backend seam.
11. Run read, preview, approval, denial, and live smoke tests.

The signed Registry package is the public behavior contract. The backend API mapping is implementation material unless it changes the governed behavior.

## What belongs in the contract

The fronting contract should define:

- Capability IDs and descriptions in business language.
- Required and optional inputs.
- Input-resolution behavior for missing, ambiguous, unresolved, and actor-policy-derived values.
- Side-effect posture: read, prepare, request, write, transactional, or irreversible.
- Minimum scopes and permission posture.
- Approval, denial, restriction, clarification, and recovery behavior.
- Bounded backend options when provider-specific controls are allowed.
- Audit expectations and scenario validation evidence.

It should not require every backend parameter to be listed unless that parameter changes governed behavior. Backend-specific controls can be exposed as named governed inputs such as `backend_options`, `filters`, or `fields`, but those inputs must be bounded and audited.

## What belongs in implementation material

Implementation material can include:

- REST, GraphQL, MCP, SQL, SDK, dbt, Cube, Databricks, Snowflake, or internal gateway clients.
- Backend endpoint or tool mappings.
- Tenant, workspace, project, channel, dataset, and repository lookup code.
- Catalog resolvers and policy hooks.
- Payload shaping, redaction, and backend error normalization.
- Live smoke scripts that prove the implementation honors the package.

Changing from one backend binding to another should normally be a code/bundle change, not a contract change. Change the contract when the capability behavior, inputs, side effects, approval posture, denial behavior, audit semantics, or actor-visible result changes.

## Good capability boundaries

Bad fronting design:

```text
github.create_issue
github.update_issue
github.dispatch_workflow
slack.post_message
superset.execute_sql
```

Better fronting design:

```text
github.issue.prepare
github.workflow.dispatch.request
slack.incident_update.prepare
slack.announcement.request
superset.chart.preview.create
superset.dataset.draft.prepare
```

The better capabilities encode business posture:

- Preview before mutation.
- Approval before side effects.
- Scope restrictions.
- Clarification when input is missing.
- Denial for unsafe operations.
- Audit linkage.

## Example mappings

| Backend operation | Better ANIP capability |
| --- | --- |
| Jira `POST /issue` | `jira.issue.prepare` then approved creation |
| Jira transition endpoint | `jira.workflow_transition.request` |
| Slack `chat.postMessage` | `slack.message.prepare` then approved send |
| GitHub issue mutation | `github.issue.prepare` then approved creation/update |
| Linear GraphQL issue mutation | `linear.issue.prepare` then approved creation/update |
| Notion page/database update | `notion.page_update.prepare` then approved update |
| Superset chart generation | `superset.chart.preview.create` |
| Superset SQL execution | Prefer governed semantic/query capability; do not expose raw SQL as the public contract |

## Superset example

Raw Superset tool access might expose `execute_sql`, chart generation, dataset creation, dashboard updates, and database metadata.

ANIP should not expose raw SQL as the agent-facing operation. A safer surface is:

```text
superset.analytics.discover_context
superset.analytics.answer_question
superset.chart.preview.create
superset.chart.publish.request
superset.dashboard.draft.prepare
superset.dataset.draft.prepare
```

The contract can state:

- Raw SQL is not accepted from agents.
- Provider-owned semantic execution may use bounded native APIs.
- Chart creation defaults to preview.
- Publishing requires approval.
- Dataset drafts are approval-gated.
- `backend_options` cannot bypass dataset, metric, grain, or export restrictions.

That is the ANIP value. The agent sees a governed analytics interface, not a database control panel.

## Starter and scaffold flow

A reviewed starter file can capture implementation intent before a full Studio project or Registry package exists:

```bash
anip fronting scaffold \
  --starter ./docs/examples/jira-fronting-showcase/anip-fronting-starter.json \
  --target python \
  --transport http,stdio \
  --output ./generated/jira-fronting \
  --force
```

The generated service contains:

- `anip-service-definition.json`
- `integration-fronting/adapter-bindings.json`
- `integration-fronting/backend-profile.example.json`
- `integration-fronting/backend-selection.example.json`
- `integration-fronting/backend-templates/*`
- `integration-fronting/conformance.json`

The starter is not the final authority. For release-quality packages, prefer the Studio and Registry flow. The service definition and signed package are the contract.

## Backend templates

Generated backend templates are guidance, not shared adapter dependencies. They tell implementers where to wire:

- REST clients.
- GraphQL clients.
- MCP clients.
- dbt/Cube semantic layers.
- Databricks/Snowflake clients.
- Internal gateways.
- Policy and catalog resolvers.

Teams should replace template code with their normal production integration approach. ANIP only requires that the exposed behavior still matches the contract.

## Sensitive options

If callers need provider-specific controls, model them explicitly as a governed input such as:

```text
backend_options
filters
fields
```

Those inputs must be bounded, documented, and audited. They must not become an invisible escape hatch for arbitrary backend calls.

Rules for these inputs:

- Define allowed keys or allowed key families.
- Define defaults and omission behavior.
- Redact or hash sensitive values in audit logs when needed.
- Reject options that change actor scope, data grain, export posture, or mutation behavior unless the capability explicitly allows that.
- Do not pass unknown options blindly to the backend.

## Fronting release checklist

Before publishing a fronting package:

- Capability IDs are business-level, not raw tool names.
- Raw backend operation refs are implementation metadata only.
- Source links are portable, not machine-local.
- No secrets are present.
- `backend_options` is bounded.
- Approval-gated capabilities stop at preview.
- Denied operations are explicit.
- Package metadata matches the real implementation path.
- Generated service tests pass.
- Live smoke tests prove read/preview behavior.
- Approved mutation smokes use real ANIP approval grants.

Fronting is valuable only if it makes the system safer and clearer than giving the agent raw tools.
