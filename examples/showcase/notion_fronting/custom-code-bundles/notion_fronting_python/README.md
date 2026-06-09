# Notion Fronting Python Custom Bundle

This bundle fills the generated ANIP backend seam for the Notion governed
fronting showcase. The generated service owns ANIP validation, tokens,
approvals, audit, and transports. This bundle maps governed inputs to bounded
Notion API calls.

Required environment for live use:

```bash
NOTION_TOKEN=...
NOTION_WORKSPACE_SCOPE=...
NOTION_PARENT_PAGE_ID=...
```

Optional controls:

```bash
ANIP_NOTION_ALLOWED_WORKSPACES=anip
ANIP_NOTION_ALLOWED_PARENTS=<page-id>
ANIP_NOTION_ALLOW_MUTATION=true
```

Mutations are disabled unless `ANIP_NOTION_ALLOW_MUTATION=true` and the
invocation carries a valid ANIP approval grant.
