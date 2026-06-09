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
