# Notion Governed Fronting Showcase

This example demonstrates ANIP in front of the Notion API. Agents see governed workspace capabilities, not raw page/database operations.

## Source

- Source spec: `docs/examples/notion-fronting-showcase/source-spec.md`
- CLI starter: `docs/examples/notion-fronting-showcase/anip-fronting-starter.json`
- Package bundle: `registry-packages/notion-fronting-showcase-0.2.0.anip-package.json`

## Generate From Starter

```bash
cd packages/go
go run ./cmd/anip fronting scaffold \
  --starter ../../docs/examples/notion-fronting-showcase/anip-fronting-starter.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/notion_fronting/custom-code-bundles/notion_fronting_python \
  --transport http,stdio \
  --output ../../examples/showcase/notion_fronting/generated/studio_notion_fronting \
  --force
```

## Generate From Package

```bash
cd packages/go
go run ./cmd/anip-generate \
  --package-bundle ../../examples/showcase/notion_fronting/registry-packages/notion-fronting-showcase-0.2.0.anip-package.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/notion_fronting/custom-code-bundles/notion_fronting_python \
  --transport http,stdio \
  --output ../../examples/showcase/notion_fronting/generated/studio_notion_fronting \
  --force
```

## Live Notion Tests

```bash
export NOTION_TOKEN="ntn_..."
export NOTION_WORKSPACE_SCOPE="<stable-workspace-policy-label>"
export NOTION_PARENT_PAGE_ID="<page-id-shared-with-the-integration>"
export NOTION_DATABASE_ID="<database-id-shared-with-the-integration>"
export ANIP_NOTION_ALLOWED_WORKSPACES="<same-workspace-policy-label>"
export ANIP_NOTION_ALLOWED_PARENTS="<same-parent-page-id>"
export ANIP_NOTION_ALLOWED_PAGES="<same-parent-page-id>"
export ANIP_NOTION_ALLOWED_DATABASES="<same-database-id>"
PYTHONPATH="<repo python packages>:<generated src>" \
  python examples/showcase/notion_fronting/scripts/live_smoke.py
```

`NOTION_WORKSPACE_SCOPE` is the ANIP policy label used by the showcase
adapter. It can match the Notion workspace display name, but the important
property is that it also appears in `ANIP_NOTION_ALLOWED_WORKSPACES`.

Run the page-creation smoke only against a disposable parent page:

```bash
export ANIP_NOTION_ALLOW_MUTATION=true
PYTHONPATH="<repo python packages>:<generated src>" \
  python examples/showcase/notion_fronting/scripts/approved_page_smoke.py
```

The approved page smoke confirms `notion.page.create.prepare` stops at preview
first, then creates a pending ANIP approval request, issues a one-time grant,
and resubmits the same parameters with `approval_grant`.

## Design Point

The backend is the Notion API for this showcase. The ANIP contract owns workspace scope, page/database allowlists, approval posture, bounded `backend_options`, denial rules, and audit.
