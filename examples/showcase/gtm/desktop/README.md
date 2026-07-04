# GTM Agent Desktop Showcase

The GTM Agent Desktop Showcase is the non-Docker path for trying the GTM Agent.

It is intended for PM, business, and evaluation users who want to install an
app, enter an OpenAI-compatible API key, and try governed GTM questions without
learning Docker Compose.

## Scope

- Runs the GTM Agent UI locally.
- Starts embedded local ANIP service sidecars automatically.
- Uses bundled sample GTM data.
- Supports questions, approvals, evidence, and runbook views.
- Uses one canonical generated implementation for the embedded demo.

## Not In Scope

- Running all five language implementations inside the desktop app.
- Bundling Metabase.
- Replacing the Docker Compose full-stack architecture proof.

## Relationship to Docker Compose

The desktop app is the product demo path. Docker Compose remains the technical
verification path for Postgres, dbt, Metabase, and five generated language
stacks.
