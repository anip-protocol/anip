---
title: Notion Fronting
description: Governed Notion fronting showcase for workspace search, database queries, page creation, page updates, and comments.
---

# Notion Fronting

Notion demonstrates governed knowledge-work behavior over a workspace, parent page, database, pages, and comments.

The package is:

```text
notion-fronting-showcase@0.2.0
```

## What It Proves

Notion workspaces often combine documentation, databases, project notes, and operational pages. Raw block/page APIs are too broad as an agent product interface.

The ANIP contract narrows this into governed workspace capabilities:

- Workspace, parent page, page, and database scope are explicit.
- Database queries are bounded.
- Page creation, page updates, and comments are preview or approval flows.
- Parent override, hidden page access, arbitrary block mutation, and workspace-wide export are denied.
- Backend options remain safe provider controls, not raw Notion payload escapes.

## Capability Surface

| Capability | Intent |
| --- | --- |
| `notion.workspace.search_context` | Search bounded workspace context. |
| `notion.database.query_context` | Query an allowed database. |
| `notion.page.create.prepare` | Prepare a page creation preview. |
| `notion.page.update.prepare` | Prepare a page update preview. |
| `notion.comment.prepare` | Prepare a comment preview. |

## Backend Boundary

The backend is Notion API. The agent-facing surface is not a generic Notion block editor. It is a governed contract for allowed workspace actions and outcomes.

## Artifacts

| Artifact | Path |
| --- | --- |
| Source spec | `docs/examples/notion-fronting-showcase/source-spec.md` |
| Package | `examples/showcase/notion_fronting/registry-packages/notion-fronting-showcase-0.2.0.anip-package.json` |
| Service definition | `examples/showcase/notion_fronting/registry-packages/notion-fronting-showcase-0.2.0-service-definition.json` |
| Custom bundles | `examples/showcase/notion_fronting/custom-code-bundles/` |
| Generated services | `examples/showcase/notion_fronting/generated/` |

## Live Validation

Credential file:

```text
/tmp/anip-notion.env
```

The integration must be explicitly connected to the test parent page and database. Mutation requires `ANIP_NOTION_ALLOW_MUTATION=true` and the required approval grant.

