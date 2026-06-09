# Notion Governed Fronting Showcase Source Specification

This source document models a realistic fronting use case: Notion API exists downstream, but agents should only see governed workspace capabilities.

## Purpose

Demonstrate that ANIP can govern knowledge-work operations without exposing raw workspace read/write tools directly to agents.

The ANIP contract owns the workspace behavior. The Notion API is the backend for this showcase. Notion MCP may be useful as a comparison point for raw tool exposure, but this package does not use MCP as the ANIP execution interface.

## Service Boundary

- Service ID: `notion-governance-service`
- Service name: Notion Governance Service
- Primary backend: native Notion API adapter
- Deployment posture: centralized ANIP fronting service with workspace/page allowlists, actor-visible scope, approval records, and audit.

## Backend Evidence

Native Notion API supply:

- Workspace search through `/search`.
- Database query through `/databases/{database_id}/query`.
- Page creation through `/pages`.
- Page metadata update through `/pages/{page_id}` and content block append/update through block APIs.
- Comments through `/comments`.

MCP comparison:

- Notion MCP may expose search, database query, page, block, and comment operations.
- This showcase intentionally does not bind ANIP capabilities to Notion MCP tools. The agent-facing surface remains ANIP capabilities backed by bounded Notion API operations.

## Governed Capability Surface

| Capability | User intent | Required inputs | Optional governed inputs | Outcome posture |
| --- | --- | --- | --- | --- |
| `notion.workspace.search_context` | Search bounded pages and databases. | `workspace_scope`, `query` | `limit`, `object_type`, `backend_options` | Read-only. Actor-visible summaries only. |
| `notion.database.query_context` | Query a bounded database view. | `database_id` | `filter`, `sort`, `limit`, `backend_options` | Read-only. Returns summarized context, not raw export. |
| `notion.page.create.prepare` | Prepare a page under an explicit parent. | `parent_id`, `title`, `content_summary` | `template_hint`, `backend_options` | Preview-only. Requires approval before creation. |
| `notion.page.update.prepare` | Prepare a page update. | `page_id`, `change_summary` | `content_patch`, `backend_options` | Preview-only. Requires approval before applying. |
| `notion.comment.prepare` | Prepare a page comment. | `page_id`, `comment_purpose`, `context` | `backend_options` | Preview-only. Requires approval before posting. |

`backend_options` is limited to bounded provider controls such as selected properties, page size, or safe filter fragments. It must not allow arbitrary block mutation, workspace-wide export, parent override, or hidden page access.

## Policy Semantics

- Reads are bounded by actor-visible workspace, page, database, and result limits.
- Missing page, database, parent, or query context returns `clarification_required`.
- Page creation, page updates, and comments are preview/approval flows.
- Private page exfiltration, raw workspace export, workspace admin actions, and unapproved mutations are denied.
- Native API is the execution binding for this package. MCP can be used as a comparison surface, but is not required for ANIP.

## Why ANIP Helps

Notion API access provides powerful workspace operations. ANIP makes the safe boundary explicit: search can be read-only and bounded, while page and comment changes stop at preview or approval.
