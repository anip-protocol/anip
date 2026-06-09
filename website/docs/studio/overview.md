---
title: Studio Overview
description: What ANIP Studio is, who it is for, and how it turns product intent into published ANIP packages.
---

# Studio Overview

ANIP Studio is the authoring and review application for governed agent-facing services.

It exists because an ANIP contract should not be invented directly in JSON. A good contract has product intent, business scenarios, approval boundaries, developer mappings, implementation seams, diagnostics, lineage, and release approval. Studio gives PM/business users and developers a shared workspace for producing that contract.

Studio is not the runtime authority. The exported Developer Definition and the signed Registry package are the authority. Studio is the place where teams create, review, diagnose, package, and publish those artifacts.

## Why Studio Exists

Most agent integrations fail because the real product behavior lives in scattered places:

- Product docs.
- UI flows.
- API docs.
- Prompt instructions.
- Skill files.
- Workflow graphs.
- Team-specific conventions.
- Backend implementation knowledge.

Studio pulls those inputs into a governed design workflow:

```text
source material
  -> Product Design
  -> locked Product baseline
  -> Developer Design
  -> Developer Definition
  -> Registry package
  -> generated service
  -> scenario validation evidence
```

The goal is not to make Studio another prompt editor. The goal is to make the agent-facing service contract reviewable before code generation and enforceable after deployment.

## Authoring Model

Studio supports three authoring paths:

| Mode | Use it when | Important boundary |
| --- | --- | --- |
| Manual Mode | You want direct deterministic editing of each Product Design and Developer Design surface. | The user is responsible for filling the contract surfaces explicitly. Diagnostics still decide whether the project is ready. |
| Guided Mode | You want AI assistance one section at a time while retaining review control. | Assistant output is proposed content until accepted and saved into the project artifacts. |
| Autopilot Mode | You want Studio to draft the project quickly from available source context. | Autopilot can draft only from evidence it has. It should stop or ask when source material is incomplete instead of inventing release-grade contract truth. |

These modes change the authoring experience, not the authority model. A release-quality project should converge on the same locked Product baseline, saved Developer Definition, package readiness, and validation evidence regardless of which authoring mode produced it.

## Model Boundary: Authoring vs Consumption

Studio authoring and agent consumption are different jobs.

For release-quality Studio authoring, ANIP has been tested with a stronger authoring model such as `gpt-5.4`. That model is doing contract-design work: reading source material, drafting Product Design, completing Developer Design, resolving diagnostics, and producing reviewable package material.

The showcase agents deliberately use `gpt-5.4-mini` where an LLM agent is part of the demo. That includes the GTM Agent validation bank and the showcase agent-consumption path. This is not an accident or a cost-cutting footnote. It is one of the reasons ANIP exists.

With ANIP, the consuming agent does not need to reconstruct policy from a giant prompt, hidden skill file, or consumer-side workflow. The service publishes the governed capability contract, input-resolution rules, approval boundaries, denial posture, audit expectations, and package trust metadata. That smaller, bounded action space lets a smaller model consume the service reliably while the service still owns enforcement.

Use the stronger model where teams are authoring and reviewing contracts. Use the smaller model where an agent is consuming already-governed ANIP services.

## Who Studio Is For

Studio has two primary audiences.

| Audience | Primary responsibility |
| --- | --- |
| PM / business / product owner | Define what the service should allow, stop, clarify, approve, deny, restrict, and audit. |
| Developer / architect / platform owner | Turn that product intent into capabilities, inputs, resolution behavior, mappings, generated code, package metadata, and validation evidence. |

The important collaboration point is the handoff from Product Design to Developer Design. Studio should make it visible when product intent has not been mapped into the generated contract.

## Source Evidence Expectations

Product Design and Developer Design need different evidence.

Product Design can usually start from business-facing source material:

- Product requirements.
- Business process notes.
- Policy expectations.
- User stories and real situations.
- Approval, denial, restriction, and audit expectations.

Developer Design needs implementation-grade evidence before generation-quality contracts are safe:

- Capability input contracts.
- Input-resolution behavior.
- Runtime governance and side-effect posture.
- Approval and denial policy.
- Composition and service ownership.
- Backend bindings or adapter evidence.
- Verification expectations.

Studio should not ask PMs to write runtime schemas. It should also not ask Autopilot to invent implementation contracts from business prose alone. If Developer evidence is missing or partial, the right behavior is to stop, show diagnostics, ask targeted questions, or let developers complete the missing surfaces manually or in Guided Mode.

## What Studio Produces

Studio produces or manages these artifacts:

| Artifact | Purpose |
| --- | --- |
| Source documents | Product specs, policies, API notes, examples, scenario descriptions, and other source material. |
| Product Design | Business-level baseline: goals, actors, scenarios, risks, non-goals, approval expectations, and expected outcomes. |
| Developer Design | Technical contract design: capabilities, inputs, resolution, side effects, scopes, approvals, failures, mappings, and diagnostics. |
| Developer Definition | Canonical ANIP service definition consumed by generators and verifiers. |
| Package | Signed Registry-published behavior contract with lineage, manifest, definition digest, README, readiness, and recommended lock. |
| Template | Safe reusable starter for future Studio projects. |
| Evidence | Diagnostics, coverage, release approval state, verification output, and scenario validation notes. |

## What Studio Is Not

Studio is not:

- The runtime execution boundary.
- A substitute for service enforcement.
- A place to hide implementation shortcuts.
- A place to store real tokens in exported packages.
- The final authority after a package is published.

Once a package is published, consumers should trust the package, signatures, locks, generated service behavior, and validation evidence. They should not need hidden Studio state.

## Main Workflows

Studio supports several workflows:

| Workflow | Use it when |
| --- | --- |
| Empty project | You are designing a new ANIP service from scratch. |
| Create from template | You want to start from reusable project structure, source docs, and suggested capability shape. |
| Fronting project | You are putting ANIP in front of Jira, Slack, GitHub, Superset, Linear, Notion, an internal API, MCP server, or another existing backend. |
| Showcase browsing | You want to inspect seeded examples in read-only mode. |
| Package publication | You have a reviewed Developer Definition and want to publish a signed Registry package. |
| Template export | You want to turn a completed project into a safe reusable starter. |

## Run Studio Locally

Clone the repository and start Studio with Docker Compose:

```bash
git clone https://github.com/anip-protocol/anip.git
cd anip/studio
docker compose up --build
```

Open:

```text
http://127.0.0.1:8080
```

By default, local Studio restores showcase snapshots when `STUDIO_SEED_SHOWCASES=1`. If `STUDIO_READ_ONLY=0`, those projects are editable locally.

For a local authoring environment with AI assistance:

```bash
export STUDIO_ASSISTANT_PROVIDER=openai
export STUDIO_ASSISTANT_MODEL=gpt-5.4
export OPENAI_API_KEY="sk-..."

docker compose up --build
```

For a local read-only showcase browser:

```bash
STUDIO_READ_ONLY=1 STUDIO_SEED_SHOWCASES=1 docker compose up --build
```

## Deploy Or Install Studio

Studio is distributed as Docker images and can also be run from source.

For container deployments, use the release image tags:

```bash
docker pull anipprotocol/studio-api:VERSION
docker pull anipprotocol/studio-web:VERSION
docker pull anipprotocol/studio:VERSION
```

Deploy Studio with Postgres as the durable dependency. The API and web containers should be replaceable; project state lives in the database.

Recommended public demo posture:

```text
STUDIO_READ_ONLY=1
STUDIO_SEED_SHOWCASES=1
STUDIO_READ_ONLY_DATABASE_URL=postgresql://readonly-user@...
```

Recommended internal authoring posture:

```text
DATABASE_URL=postgresql://...
STUDIO_ASSISTANT_PROVIDER=openai
STUDIO_ASSISTANT_MODEL=gpt-5.4
STUDIO_ASSISTANT_API_KEY=...
STUDIO_REGISTRY_URL=https://registry.example.com/registry-api/v1
STUDIO_REGISTRY_REQUIRED_MODE=production
STUDIO_REGISTRY_TRUSTED_KEY_ID=...
STUDIO_REGISTRY_PUBLISH_TOKEN=...
```

For single-instance deployments, startup migrations are acceptable. For scaled deployments, run migrations as a job with `STUDIO_MIGRATE_ONLY=1`, then start replicas with `STUDIO_RUN_MIGRATIONS=0`.

See [ANIP Studio Reference](/docs/tooling/studio) and [Deployment](/docs/operations/deployment) for the full operational checklist.

## The Trust Boundary

Studio can use AI assistance, but the assistant is not the trust boundary.

The trust boundary is:

- Product baseline review.
- Developer Design coverage.
- Diagnostics.
- Release lineage.
- Approval state.
- Developer Definition.
- Registry package signature and receipt.
- Package lock.
- Generated service conformance and scenario validation.

Use Studio to get to those artifacts. Do not ask consumers to trust the Studio UI by itself.

## Where To Go Next

- [Studio for PM and Business Users](/docs/studio/pm-business)
- [Studio for Developers](/docs/studio/developers)
- [Project Types](/docs/studio/project-types)
- [Page-by-Page Guide](/docs/studio/page-by-page)
- [AI Assistant Modes](/docs/studio/ai-assistant-modes)
- [Templates](/docs/studio/templates)
- [Package Publishing](/docs/studio/package-publishing)
- [Fronting in Studio](/docs/studio/fronting)
- [Scenario-Driven Execution Design](/docs/concepts/scenario-driven-execution)
- [Execution Scenario Validation](/docs/concepts/execution-scenario-validation)
