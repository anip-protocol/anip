---
title: Fronting in Studio
description: How Studio supports governed fronting projects for existing APIs, MCP servers, SaaS systems, and data platforms.
---

# Fronting in Studio

Fronting projects are for existing systems.

The goal is not to copy every backend API, GraphQL operation, MCP tool, or SDK method into ANIP. The goal is to define a smaller governed capability surface that agents can use safely.

## Why Fronting Exists

Existing systems often expose low-level operations:

- `create_issue`
- `transition_issue`
- `chat.postMessage`
- `execute_sql`
- `create_page`
- `update_dashboard`

Those operations may be callable, but an agent still needs to know:

- Which project/channel/workspace/dataset is allowed?
- What inputs require clarification?
- What action is preview-only?
- What requires approval?
- What must be denied?
- What gets audited?
- What happens if the backend would allow something the organization does not?

ANIP fronting puts those answers into a service-owned contract.

## Fronting Design Flow

In Studio, a fronting project should move through:

1. Backend/system identification.
2. Source docs and API evidence.
3. Product scenarios.
4. Governed capability design.
5. Backend operation evidence.
6. Input resolution and policy design.
7. Approval/denial/restriction design.
8. Developer Definition.
9. Package publication.
10. Generated service and live smoke tests.

## Backend Evidence vs Public Contract

Backend evidence can include:

- OpenAPI paths.
- GraphQL operations.
- MCP tools.
- SDK methods.
- REST endpoints.
- Query examples.
- Permission notes.

That evidence helps the implementation. It should not become the public capability surface automatically.

Example:

| Backend operation | Governed ANIP capability |
| --- | --- |
| `chat.postMessage` | `slack.channel_announcement.request` |
| `POST /issue` | `jira.incident_bug.prepare` |
| `execute_sql` | `superset.analytics.answer_question` only if bounded by semantic policy and not raw SQL pass-through |
| `create_page` | `notion.page_create.prepare` |
| Linear GraphQL mutation | `linear.issue_update.request` |

## What Studio Should Capture

For fronting projects, Studio should capture:

- Backend system name.
- Native API/MCP/GraphQL evidence.
- Safe connection references.
- Secret refs, not tokens.
- Allowed workspaces/projects/channels/datasets.
- Capability intent.
- Required inputs.
- `backend_options` or filters when needed, bounded and audited.
- Approval behavior.
- Denial and restriction behavior.
- Audit evidence.
- Implementation notes.

## Fronting Project Diagnostics

Useful diagnostics include:

- Capability looks like a raw backend operation.
- Source docs are missing fronting intent.
- Integration evidence is missing.
- Optional input affects business scope but lacks omission behavior.
- Backend options are unbounded.
- Mutation does not stop at preview or approval.
- Package metadata implies a backend path that implementation does not use.
- Secret value appears in source docs, template, package, or connection metadata.

## Express Mode And Templates

Fronting should usually be easier than a full greenfield project.

Templates can prefill:

- Backend posture.
- Source doc structure.
- Common capability patterns.
- Safe connection-ref conventions.
- Example approval paths.
- Example denial/restriction paths.

But a template should not publish a package automatically. The team still needs to review Product Design, Developer Design, Developer Definition, and package metadata.

## Fronting Checklist

Before publishing a fronting package:

- Capabilities are governed business actions, not raw backend methods.
- Backend integration evidence exists.
- Scope boundaries are explicit.
- Mutations are preview-first or approval-gated.
- Backend options are named, bounded, and audited.
- Secrets are not exported.
- Registry package README explains backend posture honestly.
- Live smoke tests use test resources only.

