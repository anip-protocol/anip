---
sidebar_position: 1
title: Introduction
description: What ANIP is, why it exists, and what it changes for agent execution.
---

# ANIP — Agent-Native Interface Protocol

ANIP is an open protocol and ecosystem for exposing **service-owned governed capabilities** to AI agents.

It started as a protocol. It has grown into a complete system of tools and processes for authoring, reviewing, packaging, publishing, generating, testing, and verifying agent-facing services.

The core idea is simple:

```text
Agents should not learn execution policy from prompts, recipes, or trial-and-error.
The service should publish the governed contract for what may happen.
```

ANIP makes permissions, side effects, input resolution, approvals, denial, cost, recovery, audit, lineage, and verification part of the interface contract before execution happens.

## The short version

APIs tell software how to call a system. MCP helps agents discover and invoke tools. Skills and workflows can help an agent use those tools.

ANIP answers the missing execution question:

> What governed action is this agent allowed to perform, for this actor, with these inputs, under these constraints, and with what evidence?

That is why ANIP is not just another API description format. It is the service-side contract between reasoning and execution.

For the deeper argument about UIs, MCP, skills, recipes, workflows, and model cost, read [Why ANIP](/docs/why-anip). This introduction focuses on what ANIP is and how the pieces fit together.

## What ANIP gives agents and organizations

| Need | What ANIP provides |
| --- | --- |
| Discoverable actions | Capability declarations with inputs, outcomes, scopes, side effects, and trust metadata. |
| Safe input handling | `anip/0.24` input-resolution rules: clarify, use defaults, use actor scope, resolve in backend, or stop. |
| Permission awareness | Pre-invoke permission discovery with available, restricted, denied, and approval/grantable paths. |
| Approval boundaries | Structured `approval_required` outcomes and approval grants, not loose string flags. |
| Consequence awareness | Read/write/transactional/irreversible side-effect posture tied to policy, audit, and verification. |
| Failure recovery | Structured failures with retry posture, resolution actions, and recovery hints. |
| Verifiable trust | Signed manifests, packages, locks, Registry receipts, and checkpointed audit evidence. |
| Implementation portability | Generated services across Python, TypeScript, Go, Java, and C# from the same contract. |

## The runtime shape

An ANIP service sits between agent reasoning and backend execution:

```text
agent / app / MCP client
        |
        v
ANIP governed capability service
        |
        v
backend API, database, SaaS system, MCP server, workflow engine, or internal service
```

The backend integration can be REST, GraphQL, SQL, SDK, MCP, or custom code. That is an implementation detail. The agent-facing contract is the governed ANIP capability surface.

## From protocol to ecosystem

The protocol is the foundation, but the adoption problem is larger than endpoint shape.

Teams need a way to:

- Design capabilities with product and business owners.
- Map those capabilities into developer-owned contracts.
- Package and sign the reviewed contract.
- Generate services in the languages teams actually use.
- Publish reusable packages and starter templates.
- Verify package identity, locks, receipts, audit, and checkpoints.
- Validate that running services behave like the reviewed scenarios.

That is why ANIP now includes the protocol, Studio, Registry, CLI, generated runtimes, conformance suites, templates, custom-code bundle support, showcase apps, and operating guidance. The goal is not only to define an interface. The goal is to make governed agent execution repeatable.

If you are evaluating ANIP and want to discuss a use case, join the [ANIP Discord](https://discord.gg/5Kx7tWUF) or open a [GitHub issue](https://github.com/anip-protocol/anip/issues).

## Studio and Registry are part of the system

ANIP is not only a protocol and a generator. The hard part is producing contracts that business owners, developers, and consumers can trust.

Studio and Registry are the two product surfaces that make that practical:

| Surface | Role |
| --- | --- |
| [Studio](/docs/studio/overview) | The authoring and review workspace where teams turn source material into Product Design, Developer Design, strict Developer Definition, package material, templates, approval lineage, and validation evidence. |
| [Registry](/docs/getting-started/registry) | The distribution and verification layer where signed packages and starter templates are published, inspected, locked, downloaded, and verified. |

That distinction matters:

- Studio is where a team decides what the service should mean.
- Registry is where consumers verify what was published.
- Generated services are where the reviewed contract is executed.

This is why Studio is more than a form UI around JSON. It is the place where scenario-driven execution design, fronting design, approval boundaries, input-resolution rules, diagnostics, release lineage, and package publication become a repeatable workflow.

## Why this can lower agent-model pressure

ANIP separates contract authoring from contract consumption.

Studio authoring is high-context design work. The Studio AI assistant was tested with `gpt-5.4` for producing reviewable Product Design, Developer Design, package material, and diagnostics.

The showcase agents intentionally use `gpt-5.4-mini` where an LLM is used to consume ANIP services. That is possible because the consuming agent is not expected to carry all policy, approval logic, side-effect posture, and recovery behavior in its prompt. The package and service manifest publish that structure, and the service enforces it.

This is one of the practical advantages of ANIP: teams can use stronger models where they are designing governed contracts, then let smaller agents consume those contracts through bounded, verifiable service-owned capabilities.

## The protocol surface

An ANIP service exposes standard protocol operations:

```text
/.well-known/anip          discovery document
/.well-known/jwks.json     public signing keys
/anip/manifest             signed capability manifest
/anip/tokens               purpose-bound delegation tokens
/anip/permissions          available / restricted / denied checks
/anip/invoke/{capability}  governed invocation
/anip/audit                execution evidence
/anip/checkpoints          tamper-evident checkpoint evidence
```

The endpoint list is not the important part by itself. The important part is the contract behind it: service-owned capabilities, authority, input resolution, side effects, approvals, denial posture, cost, recovery, audit, and package verification.

## The execution flow

The normal agent flow is:

1. **Discover** the service contract and signed capability manifest.
2. **Select** a governed capability rather than a raw backend operation.
3. **Resolve inputs** according to declared rules: clarify, default, actor policy, backend resolver, or app-selected value.
4. **Check authority** before execution using permission discovery and purpose-bound delegation.
5. **Stop for approval** when the service says the action is consequential.
6. **Invoke** with structured success or failure semantics.
7. **Record and verify** lineage, audit, checkpoints, package digests, and receipts.

This flow is what lets agents act without turning every client app into a pile of hidden policy prompts.

## A concrete example

Here is a simplified travel capability contract:

```json
// 1. Agent fetches manifest and sees:
{
  "capabilities": {
    "search_flights": {
      "side_effect": { "type": "read" },
      "minimum_scope": ["travel.search"],
      "cost": { "certainty": "fixed", "financial": null }
    },
    "book_flight": {
      "side_effect": { "type": "irreversible" },
      "minimum_scope": ["travel.book"],
      "cost": {
        "certainty": "estimated",
        "financial": { "currency": "USD", "range_min": 200, "range_max": 800 }
      }
    }
  }
}
```

```json
// 2. Agent checks permissions:
{
  "available": [
    { "capability": "search_flights", "scope_match": "travel.search" }
  ],
  "restricted": [
    { "capability": "book_flight", "reason": "missing scope", "grantable_by": "human:admin@company.com" }
  ]
}
```

The agent now knows it can search flights, but booking requires additional authority from a specific human. It can report that boundary, ask for approval, or stop instead of guessing, failing with an opaque `403`, or attempting an irreversible action with the wrong authority.

## What ANIP is not

- **Not a replacement for MCP.** MCP is valuable for client/tool interoperability. ANIP can expose derived MCP surfaces, but the ANIP contract remains the governed behavior authority.
- **Not a replacement for native APIs.** Native APIs, SDKs, SQL engines, and internal systems are often the right backend implementation path.
- **Not a skill file.** Skills can help with task UX, but authority, approval, denial, audit, and side-effect policy should not live only in consumer-side prompts.
- **Not GUI automation.** Browser and computer-use systems can be useful bridges, but ANIP is a stable, typed, verifiable service interface for agents.
- **Not just OpenAPI with extra fields.** OpenAPI describes endpoints. ANIP defines governed capabilities, execution outcomes, trust, and verification.

## What ships today

ANIP is not a spec waiting for implementations. It ships a working protocol, generation toolchain, Registry, Studio, conformance suites, and showcase applications.

| Category | What's available |
|----------|-----------------|
| **Protocol target** | `anip/0.24` with capability declarations, input resolution, approval grants, delegation, audit, lineage, and checkpoints. |
| **Runtimes** | Python, TypeScript, Go, Java, and C#. |
| **Generated transports** | HTTP and stdio across all five runtimes; gRPC for Python and Go core binding. |
| **Derived interfaces** | REST/OpenAPI, GraphQL, and MCP surfaces generated from the same governed capabilities where enabled. |
| **CLI** | Validate, verify, package, generate, scaffold fronting services, attach implementation metadata, and build release artifacts. |
| **Registry** | Signed package and template publication, browsing, locks, receipts, download metadata, and public verification. |
| **Studio** | Product/developer workspace for scenario-driven design, fronting projects, Guided and Autopilot authoring, diagnostics, release approval, package publishing, template import/export, and read-only showcase browsing. |
| **Testing** | Protocol conformance package, generator conformance package across all five languages, contract testing, scenario validation, and showcase question banks. |
| **Showcases** | GTM Agent language parity plus governed Jira, GitHub, GitLab, Slack, Linear, Notion, and Superset fronting packages. |

## How to start

Use the entry point that matches what you want to evaluate:

| Goal | Start here |
| --- | --- |
| Understand the concept | [ANIP for Everyone](/docs/anip-for-everyone) |
| Build or inspect a service | [First 10 Minutes](/docs/getting-started/first-10-minutes) |
| Generate from trusted packages | [Start With Registry](/docs/getting-started/registry) |
| Author a project | [Start With Studio](/docs/getting-started/studio) |
| Compare with MCP, skills, and native APIs | [ANIP vs MCP](/docs/concepts/anip-vs-mcp) |
| Understand runtime architecture | [Architecture](/docs/concepts/architecture) |
| Validate implementation behavior | [Conformance, Contract, and Scenario Testing](/docs/testing/conformance-contract-testing) |

## Next steps

- **[ANIP for Everyone](/docs/anip-for-everyone)** — Plain-English explanation for non-technical readers
- **[ANIP for Developers](/docs/anip-for-developers)** — Technical mental model before reading the full protocol
- **[First 10 Minutes](/docs/getting-started/first-10-minutes)** — Fastest path through the protocol, platform, and trust loop
- **[Start With Registry](/docs/getting-started/registry)** — Browse packages/templates, verify, lock, and generate
- **[Start With Studio](/docs/getting-started/studio)** — Create a project from scratch or from a starter template
- **[Generate a Service](/docs/getting-started/generate-service)** — Generate code from a package or service definition
- **[Architecture](/docs/concepts/architecture)** — Runtime shape from agents to governed services to downstream systems
- **[Ecosystem](/docs/concepts/ecosystem)** — How Studio, Registry, packages, generators, templates, and verifiers fit together
- **[ANIP vs MCP](/docs/concepts/anip-vs-mcp)** — Where MCP, skills, native APIs, and ANIP each belong
- **[Why ANIP](/docs/why-anip)** — The deeper framing on why agents need a different interface paradigm
- **[Install](/docs/getting-started/install)** — Package install commands for all five runtimes
- **[Protocol: Capabilities](/docs/protocol/capabilities)** — How capability declarations work
