---
title: Start With Studio
description: Run ANIP Studio, inspect projects, and understand the authoring flow.
---

# Start With Studio

Studio is the authoring and review product for ANIP projects.

For the detailed application guide, start with [Studio Overview](/docs/studio/overview). This page is the short local-start path.

Use it when you want to:

- Create or inspect an ANIP project.
- Load source documents.
- Draft Product Design and Developer Design.
- Generate a Developer Definition.
- Publish a package to Registry.
- Export or import starter templates.
- Browse showcase projects in read-only mode.

Studio is not the runtime authority. The Developer Definition and Registry package are the artifacts that generators, verifiers, and consumers should trust.

## Run Studio Locally

```bash
git clone https://github.com/anip-protocol/anip.git
cd anip/studio
docker compose up --build
```

Open:

```text
http://127.0.0.1:8080
```

By default, `STUDIO_SEED_SHOWCASES=1`, so Studio starts with seeded projects you can inspect.

For AI-assisted authoring, configure the Studio assistant model before starting:

```bash
export STUDIO_ASSISTANT_PROVIDER=openai
export STUDIO_ASSISTANT_MODEL=gpt-5.4
export OPENAI_API_KEY="sk-..."

docker compose up --build
```

Studio authoring was validated with `gpt-5.4` because authoring is contract-design work. Showcase agents intentionally use `gpt-5.4-mini` after the ANIP contract exists.

## Run Read-Only Demo Mode

Read-only mode is the public demo posture:

```bash
STUDIO_READ_ONLY=1 STUDIO_SEED_SHOWCASES=1 docker compose up --build
```

In read-only mode, Studio allows browsing but blocks mutation:

- Project creation.
- Document edits.
- Assistant runs.
- Package publication.
- Template publication.
- Registry mutation.

When possible, run read-only hosted Studio with a read-only database user as well as `STUDIO_READ_ONLY=1`.

## Install Or Deploy Studio

For hosted deployments, use the release images:

```bash
docker pull anipprotocol/studio-api:VERSION
docker pull anipprotocol/studio-web:VERSION
docker pull anipprotocol/studio:VERSION
```

Use `anipprotocol/studio-api` for the API container and `anipprotocol/studio-web` for the web UI. Configure Postgres as durable storage.

Minimum internal authoring settings:

```text
DATABASE_URL=postgresql://...
STUDIO_ASSISTANT_PROVIDER=openai
STUDIO_ASSISTANT_MODEL=gpt-5.4
STUDIO_ASSISTANT_API_KEY=...
STUDIO_REGISTRY_URL=https://registry.example.com/registry-api/v1
STUDIO_REGISTRY_REQUIRED_MODE=production
STUDIO_REGISTRY_TRUSTED_KEY_ID=...
```

Minimum public demo settings:

```text
STUDIO_READ_ONLY=1
STUDIO_SEED_SHOWCASES=1
STUDIO_READ_ONLY_DATABASE_URL=postgresql://readonly-user@...
```

See [ANIP Studio Reference](/docs/tooling/studio) and [Deployment](/docs/operations/deployment) for migration, metrics, Registry trust, and read-only hardening details.

## The Studio Project Flow

The standard Studio flow is:

```text
source documents
  -> Product Design
  -> locked Product baseline
  -> Developer Design
  -> Developer Definition
  -> Registry package
  -> generated service
  -> verification evidence
```

The important rule: generation and verification consume the Developer Definition or Registry package, not hidden Studio state.

## What To Inspect In A Project

Open a seeded or newly created project and inspect:

- Source documents.
- Product Design.
- Developer Design.
- Developer Definition.
- Diagnostics and coverage status.
- Registry publication status.
- Contract signature.
- Template export/import surfaces.
- Generated handoff artifacts.

Do not treat generated code as the first source of truth. In ANIP, reviewed definitions are the truth and generated code is an implementation of them.

## What Good Looks Like

A release-quality Studio project should have:

- Locked Product Design baseline.
- Developer Design coverage for Product Design items.
- No unresolved diagnostics blocking package generation.
- Clear capability IDs.
- Explicit input-resolution behavior.
- Approval paths for write-adjacent or risky behavior.
- Denial, restriction, clarification, recovery, and audit behavior.
- Package lineage and contract signature.
- Portable source/project links.
- No secrets or machine-local paths in package metadata.

## AI Authoring Modes

Studio has three authoring modes:

| Mode | Use when |
|------|----------|
| Manual Mode | You want deterministic page-by-page editing and exact control. |
| Guided Mode | You want AI help while accepting, rejecting, or revising each section. |
| Autopilot Mode | You want Studio to complete the project draft from reviewed source context. |

The mode changes how the project is authored, not what the release must prove. All modes should converge on the same locked Product baseline, saved Developer Definition, readiness diagnostics, package material, and validation evidence.

Autopilot requires enough source evidence. Product docs are usually enough to draft Product Design. Developer Design needs developer evidence such as input contracts, input-resolution behavior, runtime governance, composition, backend bindings, and verification expectations. If that evidence is missing, Studio should stop or ask questions instead of inventing contract truth.

The assistant is not the trust boundary. The generated contract, validation diagnostics, approval state, and Registry package are the trust boundary.

## Smoke Studio

From the repository root:

```bash
studio/scripts/smoke-compose.sh
```

The smoke resets the database, starts read-only seeded compose, checks API/UI reachability, verifies seeded projects, verifies representative mutation guards, and tears down.

## Next Steps

- For reusable project starters, see [Start With Registry](/docs/getting-started/registry).
- For the full application guide, see [Studio Overview](/docs/studio/overview).
- For operational settings and deployment details, see [ANIP Studio Reference](/docs/tooling/studio).
- For seeded examples, see [Showcases](/docs/getting-started/showcases).
- For revision semantics, see [Lifecycle and Revisions](/docs/concepts/lifecycle-and-revisions).
