---
title: Agent-Authored Contract Quickstart
description: An experimental low-friction path for drafting an ANIP service definition with a coding agent before moving to Studio and Registry.
---

# Agent-Authored Contract Quickstart

This is the fastest experimental path for trying ANIP when you already use a coding agent.

Instead of starting with Studio and Registry, you ask an agent to draft a local `anip-service-definition.json`, validate it with the CLI, and generate a service from it.

Use this path for:

- Learning the contract shape.
- Prototyping a small service.
- Testing whether ANIP fits a product surface.
- Producing a first draft before a Studio review.

Do not treat this path as a production release process. It skips Studio review, Registry signing, package locks, publication receipts, template export, release lineage, and scenario evidence.

## The Three Onboarding Paths

| Path | Best for | Trust posture |
| --- | --- | --- |
| Agent-authored contract | First draft, prototype, learning. | Local only; must be validated and reviewed. |
| Studio -> Registry -> CLI | Team review, public packages, production governance. | Reviewed, signed, packaged, reproducible. |
| Registry -> CLI | Consuming an existing package. | Verifies a published artifact and generates from a lockable package. |

The value of the agent-authored path is speed. The value of Studio and Registry is trust.

## Prerequisites

Install the ANIP CLI first:

```bash
anip --help
anip validate --help
anip generate --help
```

If you are working from the repository checkout before installing the CLI, use:

```bash
cd packages/go
go run ./cmd/anip --help
```

Replace `anip` with `go run ./cmd/anip` in the examples below when using the repo-local CLI entry point.

## Give The Agent Current References

Give your coding agent these references:

- [`SPEC.md`](https://github.com/anip-protocol/anip/blob/main/SPEC.md)
- [Protocol Reference](/docs/protocol/reference)
- [Capabilities](/docs/protocol/capabilities)
- [Authentication](/docs/protocol/authentication)
- [Failures, Cost, Audit](/docs/protocol/failures-cost-audit)
- [CLI Reference](/docs/tooling/cli)
- Example service definitions:
  - [`jira-fronting-showcase-0.2.3-service-definition.json`](https://github.com/anip-protocol/anip/blob/main/examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3-service-definition.json)
  - [`gtm-pipeline-q2-review-0.4.3-service-definition.json`](https://github.com/anip-protocol/anip/blob/main/examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.3-service-definition.json)

Also give it the agent skill file:

```text
skills/anip-contract-drafter.md
```

That file is intentionally agent-facing. It tells the agent what to produce, what not to invent, and how to use the CLI validation loop.

## Copy/Paste Prompt

Use this as the starting prompt for Codex, Claude Code, Cursor, or another coding agent:

```text
You are drafting an experimental ANIP service definition.

Goal:
Create a local anip-service-definition.json for the service described below.

Important:
- This is a prototype contract, not a production release artifact.
- Use ANIP 0.24 semantics.
- Use contract_schema_version: "anip-service-definition/v1".
- Use the current ANIP examples as structural references.
- Do not invent unsupported ANIP fields.
- Do not silently default risky capabilities to read/read.
- Every capability must declare concrete inputs, side-effect posture, required scopes, produced effects, forbidden effects, and failure/approval posture.
- If a required contract decision is unclear, stop and ask questions instead of guessing.
- The output must pass: anip validate --definition ./anip-service-definition.json

References:
- SPEC.md
- website/docs/protocol/reference.md
- website/docs/protocol/capabilities.md
- website/docs/protocol/authentication.md
- website/docs/protocol/failures-cost-audit.md
- examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3-service-definition.json
- examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.3-service-definition.json
- skills/anip-contract-drafter.md

Service description:
<describe the service here>

Users / actors:
<who asks for work, who can approve, who can only read>

Capabilities:
<list the business capabilities, not raw endpoints>

Inputs and entities:
<what inputs each capability needs, which are explicit, derived, defaulted, actor-scoped, or clarification-required>

Policies:
<allowed scopes, approval gates, denied actions, restricted data, raw export rules, mutation rules>

Backend:
<API, database, SaaS system, MCP server, or custom service being wrapped>

Deliverables:
1. Create ./anip-service-definition.json.
2. Run anip validate --definition ./anip-service-definition.json.
3. If validation fails, fix the definition and rerun validation.
4. Stop when validation passes, then summarize remaining review risks.
```

## Validate The Draft

Run:

```bash
anip validate --definition ./anip-service-definition.json
```

If validation fails, give the error output back to the agent and ask it to fix only the contract issue that caused the failure.

Do not bypass validation. Do not publish a definition that only “looks right”.

## Generate A Service

Once the definition validates, generate a service:

```bash
anip generate \
  --definition ./anip-service-definition.json \
  --target python \
  --transport http,stdio \
  --dependency-source registry \
  --output ./generated/my-service \
  --force
```

Targets:

```text
python
typescript
go
java
csharp
```

For TypeScript and Java, you can choose framework variants:

```bash
anip generate \
  --definition ./anip-service-definition.json \
  --target typescript \
  --framework hono \
  --transport http,stdio \
  --output ./generated/my-service-ts \
  --force
```

```bash
anip generate \
  --definition ./anip-service-definition.json \
  --target java \
  --framework spring-boot \
  --transport http,stdio \
  --output ./generated/my-service-java \
  --force
```

## Common Failure Modes

Agent-authored contracts often fail in predictable ways:

- Invented fields that are not part of the current service-definition model.
- Vague capabilities that mirror endpoints instead of governed business actions.
- Missing input-resolution posture.
- Missing produced or forbidden business effects.
- Mutating or approval-gated behavior modeled as simple read behavior.
- Missing approval grant posture for preview/approval flows.
- Raw data export not denied explicitly.
- Composed capabilities without declared composition metadata.
- Backend details leaking into the agent-facing contract as raw operations.

These are exactly the kinds of mistakes Studio is designed to catch with guided review, diagnostics, coverage mapping, and package publication checks.

## When To Move To Studio

Move the draft into Studio when:

- The contract will be shared with a team.
- A PM/business owner needs to review the capability surface.
- Approval, denial, audit, or compliance behavior matters.
- You want a package, template, snapshot, or public Registry artifact.
- You need repeatable package publication and generated-service validation.

The recommended release path remains:

```text
source docs -> Studio Product Design -> Studio Developer Design -> Developer Definition -> Registry package -> CLI generation -> tests
```

The agent-authored path lowers the first step. It does not replace the trust path.

## Optional Local Package

For local experiments, you can build an unsigned local package bundle from the validated definition:

```bash
anip package build-local \
  --definition ./anip-service-definition.json \
  --package-id my-prototype-service \
  --package-version 0.1.0 \
  --output-dir ./registry-packages \
  --write-definition
```

Use that for local iteration only. For public or team consumption, publish through Registry after review.
