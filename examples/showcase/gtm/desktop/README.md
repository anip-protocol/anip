# GTM Agent Desktop Showcase

The GTM Agent Desktop Showcase is the non-Docker path for trying the GTM Agent.

It is intended for PM, business, and evaluation users who want to install an
app, enter an OpenAI-compatible API key, and try governed GTM questions without
learning Docker Compose.

## Scope

- Runs the GTM Agent UI locally.
- Starts embedded local ANIP service sidecars automatically.
- Supports an OpenAI-compatible API key through `ANIP_AGENT_API_KEY` or
  `OPENAI_API_KEY`.
- Bundles prebuilt local GTM mart data generated from the Maven CRM source
  files, so mart-backed pipeline and enrichment questions work without Docker.
- Can point the generated GTM services at an external Postgres-compatible GTM
  mart database with `GTM_DESKTOP_DATABASE_URL` or `DATABASE_URL`.
- Supports questions, approvals, evidence, and runbook views.
- Uses one canonical generated implementation for the embedded demo.

## Not In Scope

- Running all five language implementations inside the desktop app.
- Bundling the full JVM Metabase server. The desktop bundle uses local
  prebuilt marts for agent execution; Docker Compose remains the Metabase BI
  verification path.
- Replacing the Docker Compose full-stack architecture proof.

## Relationship to Docker Compose

The desktop app is the product demo path with embedded local data. Docker
Compose remains the technical verification path for Postgres, dbt, Metabase,
and five generated language stacks.
