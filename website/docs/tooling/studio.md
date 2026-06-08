---
title: ANIP Studio
description: Design, review, generate, package, and inspect governed ANIP services.
---

# ANIP Studio

ANIP Studio is the authoring and review environment for governed ANIP services. It helps teams move from source material to product design, developer definition, signed package, generated code, and verification evidence.

Studio is not the protocol authority. The exported ANIP service definition and Registry package are the authority. Studio exists to make those artifacts easier and safer to produce.

This page is the operational reference for Studio. If you are learning Studio as an application, start with the dedicated Studio guide:

- [Studio Overview](/docs/studio/overview)
- [Studio for PM and Business Users](/docs/studio/pm-business)
- [Studio for Developers](/docs/studio/developers)
- [Page-by-Page Guide](/docs/studio/page-by-page)
- [AI Assistant Modes](/docs/studio/ai-assistant-modes)
- [Templates](/docs/studio/templates)
- [Package Publishing](/docs/studio/package-publishing)
- [Fronting in Studio](/docs/studio/fronting)

## Version and spec posture

The current Studio application version is `0.8.0`. The protocol target is `anip/0.24`.

Those versions are intentionally separate:

- Studio version tracks the product and tooling surface.
- ANIP spec version tracks the contract shape emitted by Studio.
- Package and template versions track immutable published artifacts.

Studio should reject starter templates that target a newer ANIP spec than the Studio build supports. For the current release line, Studio should emit strict `anip/0.24` definitions rather than silently preserving legacy shapes.

## What Studio is for

Use Studio to:

- Create ANIP service projects.
- Load source documents.
- Turn product intent into reviewed capabilities and scenarios.
- Map Product Design to Developer Design.
- Generate an ANIP service definition.
- Publish a signed package to Registry.
- Create and import starter templates.
- Review fronting projects for existing APIs.
- Browse showcase projects in read-only hosted mode.

## Core artifacts

| Artifact | Purpose |
| --- | --- |
| Source documents | Human-authored source material: product specs, API notes, security policy, examples. |
| Product Design | Business-level baseline: goals, users, scenarios, risks, and expected behavior. |
| Developer Design | Technical contract draft: capabilities, inputs, side effects, scopes, approvals, resolution, mappings. |
| Developer Definition | Canonical machine-readable contract used by generators and verifiers. |
| Package | Registry-published signed bundle containing the service definition and trusted metadata. |
| Template | Safe starter project structure that can be reused for new Studio projects. |

## Project dashboard

The project dashboard is the operational hub for a Studio project. It should make the next action obvious instead of forcing users to understand every internal page.

Key dashboard actions include:

- Continue with Guided Mode.
- Continue with Autopilot Mode.
- Review product and developer diagnostics.
- Open source documents, Product Design, Developer Design, diagrams, and contract views.
- Export a starter template from a completed project.
- Review package publication state.
- Publish approved packages to Registry.
- Open advanced fronting setup when a project fronts an existing backend.

Deep pages are still useful for inspection and repair, but the dashboard should be the normal entry point.

## Authoring modes

Studio supports two AI-assisted authoring modes. Both are optional; Studio must remain usable without AI.

| Mode | Use when | Behavior |
| --- | --- | --- |
| Guided Mode | You want control over each section. | The assistant helps section by section, but the user makes the key decisions. |
| Autopilot Mode | You want Studio to complete a project draft quickly. | The assistant drafts across the project and stops for review. |

Guided Mode has more user responsibility and more control. Autopilot Mode is faster, but still requires human review before publishing.

The assistant is not the trust boundary. The generated contract, validation diagnostics, approval state, and Registry package are the trust boundary.

## Assistant configuration

Studio can run in deterministic mode or use a configured model provider. For production-quality project authoring, use the stronger Studio assistant model, for example:

```bash
STUDIO_ASSISTANT_PROVIDER=openai
STUDIO_ASSISTANT_MODEL=gpt-5.4
OPENAI_API_KEY=...
```

The simulator and generated-service test harness can use a smaller model independently:

```bash
STUDIO_SIMULATOR_PROVIDER=openai
STUDIO_SIMULATOR_MODEL=gpt-5.4-mini
OPENAI_API_KEY=...
```

That separation matters. Studio authoring is contract design work. The simulator is testing agent-consumption behavior against already-produced contracts.

Studio also supports Anthropic and local/Ollama provider settings, but provider choice does not change the trust boundary. The saved Product Design, Developer Design, diagnostics, approvals, package signature, and verifier output remain the authoritative record.

## Standard project flow

1. Create a workspace and project.
2. Load source documents.
3. Draft Product Design.
4. Lock the Product Design baseline.
5. Draft Developer Design.
6. Complete coverage mapping from Product Design to Developer Definition sections.
7. Resolve diagnostics.
8. Generate or save the Developer Definition.
9. Review and approve release lineage.
10. Publish a package to Registry.
11. Generate code from the package.
12. Verify the running service.

The important rule: generation and verification consume the Developer Definition, not a hidden Studio-only state.

For the full revision model, see [Lifecycle and Revisions](/docs/concepts/lifecycle-and-revisions).

## Fronting express flow

Fronting projects are for existing systems: Jira, GitHub, Slack, GitLab, Notion, Linear, Superset, internal REST APIs, GraphQL APIs, MCP servers, data platforms, or semantic layers.

Fronting should be simpler than a full greenfield project. The goal is not to copy a backend API catalog into ANIP. The goal is to expose a smaller governed capability surface in front of a broader existing system:

1. Start from a fronting template or starter.
2. Identify the backend system and safe integration posture.
3. Define governed business capabilities.
4. Capture backend operation evidence as implementation profile material.
5. Define approvals, denial, restriction, clarification, and audit behavior.
6. Generate the ANIP service definition.
7. Generate backend templates and implementation seams.
8. Publish a package.

Fronting does not mean "wrap every API endpoint." It means exposing a smaller governed ANIP capability surface in front of a broader backend system.

Backend integration metadata is implementation profile material. It can say that a capability maps to Jira REST, Linear GraphQL, Slack Web API, Notion API, Superset REST, or an MCP server, but the public ANIP capability remains the product contract.

## Starter templates

Templates lower project creation cost. They can include:

- Project type.
- ANIP spec version.
- Domain/industry labels.
- Safe Markdown source documents.
- Suggested Product Design structure.
- Suggested Developer Design structure.
- Fronting starter metadata.

Templates can be created from a completed project through the project dashboard. The export flow should be selective: users choose sensitive sections, especially source documents, rather than exporting everything blindly.

Template packages should be safe to share:

- Source documents are exported as Markdown.
- Secrets are never exported.
- Connections carry secret references, not token values.
- Binary payloads, scripts, and post-install hooks are not allowed.
- Document and package digests must verify before import.
- Templates targeting a newer ANIP spec than the Studio build supports are rejected.

Templates can be published to Registry separately from ANIP service packages. This keeps reusable project starters distinct from immutable executable contract packages.

## Package publishing

Studio can publish packages to Registry when release lineage is approved.

The published package should include:

- Package README.
- Source links that are portable and safe.
- Product and developer lineage.
- Service definition.
- Manifest and recommended lock.
- Contract signature.
- Agent consumability metadata.
- Agent consumption readiness metadata.
- Optional implementation-material refs if they are immutable and digest-pinned.

Do not publish machine-local links, secrets, private documents, or runtime-only evidence to public Registry.

If implementation material is added after live testing, publish a new package revision instead of mutating the existing package record.

Publishing should be treated as a release action:

- Product and Developer revisions form the release lineage.
- PM or release approval must match the selected lineage.
- Local package generation can happen before remote publication.
- Remote Registry publication creates the externally consumable package record.
- Package identity, version, manifest digest, definition digest, and contract signature must remain immutable.

## Registry integration

Studio can read Registry packages and starter templates, and it can publish packages/templates when configured with a publish token.

Useful settings:

| Setting | Purpose |
| --- | --- |
| `STUDIO_REGISTRY_URL` | Registry API base URL used by Studio. |
| `STUDIO_REGISTRY_REQUIRED_MODE` | Expected Registry mode, such as `production`. |
| `STUDIO_REGISTRY_TRUSTED_KEY_ID` | Expected signing key id for trusted Registry verification. |
| `STUDIO_REGISTRY_PUBLISH_TOKEN` | Server-side token used by Studio publication APIs. |

In production mode, Studio should require production Registry posture unless explicitly configured otherwise. This prevents a hosted Studio from accidentally publishing against a development registry or trusting the wrong signing key.

## Read-only hosted mode

Public Studio deployments should be read-only:

```bash
STUDIO_READ_ONLY=1 STUDIO_SEED_SHOWCASES=1 docker compose -f studio/docker-compose.yml up
```

Read-only mode should allow:

- Browsing workspaces and projects.
- Viewing source documents.
- Viewing Product Design and Developer Design.
- Viewing contracts, packages, templates, and release evidence.
- Inspecting showcase projects.

Read-only mode should block:

- Project creation.
- Document edits.
- Assistant invocations.
- Package publication.
- Template publication.
- Registry mutation.
- Generation actions that write server-side state.

This makes hosted Studio useful for learning without exposing mutation surfaces.

## Local compose

```bash
cd studio
docker compose up --build
```

Useful environment variables:

| Variable | Purpose |
| --- | --- |
| `STUDIO_SEED_SHOWCASES` | Seed GTM and fronting showcase projects. |
| `STUDIO_READ_ONLY` | Block mutation routes for hosted demo mode. |
| `STUDIO_READ_ONLY_REASON` | Message shown when mutation is blocked. |
| `STUDIO_RUN_MIGRATIONS` | Run database migrations on application startup. |
| `STUDIO_MIGRATE_ONLY` | Run migrations and exit, useful for deployment jobs. |
| `DATABASE_URL` | Studio API database connection string. |
| `STUDIO_ASSISTANT_PROVIDER` | Assistant provider for Studio authoring. |
| `STUDIO_ASSISTANT_MODEL` | Assistant model for Studio authoring. |
| `STUDIO_SIMULATOR_PROVIDER` | Provider for simulator and generated-service tests. |
| `STUDIO_SIMULATOR_MODEL` | Model for simulator and generated-service tests. |
| `STUDIO_REGISTRY_URL` | Registry API used for package publication/verification. |
| `STUDIO_REGISTRY_REQUIRED_MODE` | Expected Registry trust mode. |
| `STUDIO_REGISTRY_TRUSTED_KEY_ID` | Expected Registry signing key. |
| `STUDIO_REGISTRY_PUBLISH_TOKEN` | Publish token used by the Studio API. |

Run the local smoke:

```bash
studio/scripts/smoke-compose.sh
```

## Deployment and operations

Studio is stateless apart from its database. For a production or public read-only deployment, run PostgreSQL as the durable dependency and keep application instances replaceable.

Operational endpoints:

| Endpoint | Purpose |
| --- | --- |
| `/api/health` | Basic process health. |
| `/api/readyz` | Readiness check, including database readiness. |
| `/api/metrics` | Prometheus-compatible metrics. |
| `/api/runtime-status` | Runtime configuration visibility for the UI. |
| `/api/settings` | Server-backed Studio settings. |
| `/api/registry/publications` | Registry package publication proxy. |
| `/api/registry/templates` | Registry template listing/publication proxy. |

For a single-instance demo, startup migrations are acceptable. For a scaled deployment, prefer a migrate-only job:

```bash
STUDIO_MIGRATE_ONLY=1 docker compose -f studio/docker-compose.yml run --rm studio-api
STUDIO_RUN_MIGRATIONS=0 docker compose -f studio/docker-compose.yml up --build
```

Studio emits structured JSON logs and Prometheus metrics for request counts, request latency, readiness checks, and migration state. Self-hosted deployments should scrape `/api/metrics` and retain application logs centrally.

## Showcase seeding

Studio can seed showcase projects for a public demo or local evaluation. Current showcase categories include:

- GTM Agent, the main multi-service scenario-driven execution showcase.
- Jira, GitHub, GitLab, Slack, Notion, Linear, and Superset fronting projects.

Use `STUDIO_SEED_SHOWCASES=1` for demo environments. For private production authoring workspaces, disable showcase seeding unless those projects are intentionally part of the workspace.

## What good Studio output looks like

A good Studio project produces:

- A clear Product Design baseline.
- Developer Design coverage with no orphan Product Design items.
- Capabilities that map to business scenarios.
- Explicit input resolution behavior.
- Approval, denial, restriction, clarification, and audit paths.
- A strict `anip/0.24` Developer Definition.
- A package that verifies from Registry.
- Generated code that preserves the public manifest.
- Runtime tests or scenario validation evidence.

Studio succeeds when a consumer can inspect the package and understand what the service is allowed to do without trusting prompts or hidden local glue.
