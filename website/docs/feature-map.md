---
sidebar_position: 3
title: Feature Map
description: Complete inventory of ANIP protocol features, runtimes, transports, and tooling.
---

# Feature Map

This page maps the current ANIP surface area. It is not a version history; it is the practical inventory of what exists across the protocol, tooling, generated services, Registry, Studio, and showcases.

Current protocol target: `anip/0.24`.

## Protocol Contract

| Feature | What it gives agents and organizations | Where to read |
|---------|-------------|-------------|
| Capability declarations | Service-owned action semantics: name, description, inputs, outputs, side-effect posture, cost, controls, outcomes, and scope. | [Capabilities](/docs/protocol/capabilities) |
| Input declarations | Required/optional inputs, validation, allowed values, defaults, semantic type, entity-reference posture, and catalog references. | [Input declarations](/docs/protocol/capabilities#input-declarations) |
| Input resolution | Per-input rules for explicit values, closed values, backend-resolved values, actor-policy scope, app-selected values, and clarification. | [Input resolution](/docs/protocol/capabilities#input-resolution-v024) |
| Side-effect posture | Contract-level `read`, `write`, `transactional`, or `irreversible` behavior tied to permissions, approvals, audit, and verification. | [Side-effect types](/docs/protocol/capabilities#side-effect-types) |
| Cost declaration | Fixed, estimated, or dynamic cost before execution, with actual cost after execution when applicable. | [Cost signaling](/docs/protocol/failures-cost-audit#cost-signaling) |
| Binding requirements | Capability can require a quote, offer, price lock, or other execution-time binding before invocation. | [Binding requirements](/docs/protocol/capabilities#binding-requirements-v014) |
| Control requirements | Declared controls such as `cost_ceiling` and `stronger_delegation_required` that the runtime can enforce. | [Control requirements](/docs/protocol/capabilities#control-requirements-v014) |
| Capability graph | Prerequisites and compensation paths for capabilities that depend on other capabilities. | [Capability graph](/docs/protocol/capabilities#capability-graph) |
| Composition | `atomic` or `composed` capabilities with step graph, input/output mapping, empty-result policy, failure policy, and audit policy. | [Capability composition](/docs/protocol/capabilities#capability-composition-v023) |
| Same-service hints | Advisory `refresh_via`, `verify_via`, and related hints for recovery and verification within a manifest. | [Advisory composition hints](/docs/protocol/capabilities#advisory-composition-hints-v017) |
| Cross-service hints | Service/capability references for handoff, refresh, verify, and follow-up across ANIP services. | [Cross-service handoff hints](/docs/protocol/capabilities#cross-service-handoff-hints-v019) |
| Service/package boundary | Public capability contract remains stable while implementation details, bundles, and downstream APIs stay behind the service boundary. | [Service and package boundary](/docs/protocol/capabilities#service-and-package-boundary) |

## Authority, Failure, and Audit

| Feature | What it gives agents and organizations | Where to read |
|---------|-------------|---------------|
| Delegation | Scoped JWT authority chains with capability, purpose, time, budget, and delegation-depth constraints. | [Delegation](/docs/protocol/delegation-permissions) |
| Permission discovery | Pre-invoke `available`, `restricted`, and `denied` buckets so agents do not guess what they may do. | [Permission discovery](/docs/protocol/delegation-permissions#permission-discovery) |
| Restriction metadata | Machine-readable `reason_type` plus actionable `resolution_hint` for restricted and denied entries. | [Three-bucket model](/docs/protocol/delegation-permissions#three-bucket-model) |
| Budget constraints | Enforceable token budget with currency and max amount. | [Budget constraints](/docs/protocol/delegation-permissions#budget-constraints-in-delegation) |
| Budget narrowing | Child delegation cannot exceed the parent's delegated budget. | [Budget narrowing rule](/docs/protocol/delegation-permissions#budget-narrowing-rule) |
| Approval grants | Signed one-time or session-bound grants for approval-required continuations. | [Approval grants](/docs/protocol/delegation-permissions#approval-grants) |
| Structured failures | Machine-readable failure type, retry posture, canonical resolution action, and optional recovery target. | [Structured failures](/docs/protocol/failures-cost-audit#structured-failures) |
| Recovery actions | Canonical recovery vocabulary including retry, refresh, redelegation, approval, escalation, and service-owner intervention. | [Recovery actions](/docs/protocol/failures-cost-audit#recovery-actions) |
| Budget context | `budget_context` in invocation responses, including success and failure cases. | [Budget enforcement](/docs/protocol/failures-cost-audit#budget-enforcement) |
| Audit logging | Protocol-level execution evidence with event classification, retention tier, lineage, approval, budget, and authority context. | [Audit logging](/docs/protocol/failures-cost-audit#audit-logging) |
| Lineage | `task_id`, `parent_invocation_id`, `client_reference_id`, and `upstream_service` for causal tracing across services. | [Lineage](/docs/protocol/lineage) |
| Checkpoints | Merkle checkpoints and inclusion proofs for tamper-evident audit history. | [Checkpoints and trust](/docs/protocol/checkpoints-trust) |
| Manifest signatures | Signed manifests and JWKS publication so clients can verify what they consume. | [Reference](/docs/protocol/reference#manifest) |

## Studio, Registry, and CLI

| Component | Purpose | Where to read |
|-----------|---------|---------------|
| [Studio](/docs/studio/overview) | Design, review, package, template, and inspect ANIP projects. Includes Guided Mode, Autopilot Mode, fronting flow, and read-only hosted mode. | [Studio guide](/docs/studio/overview) |
| [Registry](/docs/tooling/registry) | Publish, inspect, lock, verify, and browse signed packages and starter templates. | [Registry](/docs/tooling/registry) |
| [CLI](/docs/tooling/cli) | Generate services, validate definitions, verify packages, build/publish packages, attach implementation metadata, and scaffold fronting services. | [CLI](/docs/tooling/cli) |
| Packages | Immutable artifacts containing manifest, service definition, readme, recommended lock, signature metadata, and optional implementation-material refs. | [Package trust loop](/docs/getting-started/package-trust-loop) |
| Templates | Safe project starters for Studio, separated from signed runtime packages and importable by spec-version compatibility. | [Starter templates](/docs/tooling/registry#template-publishing) |
| Locks | Digest-pinned package locks for repeatable generation from Registry or bundle artifacts. | [Lock files](/docs/tooling/registry#lock-files) |
| Custom bundles | Reviewed implementation material overlaid at generation time without changing the signed public capability contract. | [Custom code bundles](/docs/generated-services/custom-code-bundles) |
| Fronting scaffolds | Generate governed ANIP services in front of existing APIs, GraphQL APIs, MCP surfaces, SaaS tools, or data platforms. | [Governed fronting](/docs/patterns/fronting) |
| Agent consumption kit | Generated compact metadata for routing, readiness, app-glue boundaries, prompt briefs, and agent-side consumption. | [Generate service](/docs/getting-started/generate-service) |

## Runtime and Generation Support

| Target | Runtime package | Framework variants | Generated transports |
|--------|-----------------|--------------------|----------------------|
| Python | `anip-service` | FastAPI | HTTP, stdio, gRPC |
| TypeScript | `@anip-dev/service` | Hono, Express, Fastify | HTTP, stdio |
| Go | `github.com/anip-protocol/anip/packages/go` | `net/http`, Gin | HTTP, stdio, gRPC |
| Java | `dev.anip:anip-service` | Spring Boot, Quarkus | HTTP, stdio |
| C# | `Anip.Service` | ASP.NET Core | HTTP, stdio |

Framework selection is a generation-time choice. It should not change the ANIP contract.

## Transports and Interfaces

| Surface | What it is | Runtime support | Where to read |
|---------|------------|-----------------|---------------|
| Native ANIP HTTP | Primary wire protocol for web services, Studio, curl, and service-to-service calls. | All 5 | [HTTP](/docs/transports/http) |
| Native ANIP stdio | JSON-RPC 2.0 over stdin/stdout for local agents and subprocess tools. | All 5 | [stdio](/docs/transports/stdio) |
| Native ANIP gRPC | Protobuf over HTTP/2 for high-performance internal services. | Python, Go | [gRPC](/docs/transports/grpc) |
| REST/OpenAPI interface | Derived interface generated from capabilities. It is not the ANIP governance boundary. | Generated from ANIP | [Interfaces](/docs/generated-services/interfaces) |
| GraphQL interface | Derived GraphQL surface generated from capabilities. | Generated from ANIP | [Interfaces](/docs/generated-services/interfaces) |
| MCP interface | Derived MCP surface exposing governed ANIP capabilities to MCP clients. | Generated from ANIP | [Interfaces](/docs/generated-services/interfaces) |

## Validation and Conformance

| Feature | Purpose | Where to read |
|---------|---------|---------------|
| Service definition validation | Reject malformed definitions before packaging or generation. | [CLI](/docs/tooling/cli#anip-validate-and-anip-verify) |
| Package verification | Verify Registry packages, local bundles, signatures, locks, and digest expectations. | [CLI](/docs/tooling/cli#anip-validate-and-anip-verify) |
| Protocol conformance package | Source-local conformance suite under `conformance/` for running ANIP services: discovery, manifests, tokens, permissions, invocation, audit, checkpoints, lineage, and input resolution. | [Conformance](/docs/testing/conformance-contract-testing#protocol-conformance) |
| Generator conformance package | Source-local generator fixture suite under `packages/go/generator/testdata/` that checks `anip generate` across Python, TypeScript, Go, Java, and C#. | [Generator conformance](/docs/testing/conformance-contract-testing#generator-conformance-and-parity) |
| Runtime parity | Check that generated services expose equivalent public manifests and behavior across languages and framework variants. | [Conformance](/docs/testing/conformance-contract-testing) |
| Contract testing | Exercise scenario packs against running services so implementation behavior matches the signed contract. | [Contract testing](/docs/testing/conformance-contract-testing#contract-testing) |
| Scenario-driven execution design | Business scenarios define capability boundaries, allowed outcomes, approvals, denials, clarification, and recovery behavior. | [Scenario-driven execution](/docs/concepts/scenario-driven-execution) |
| Execution scenario validation | Scenario packs verify that running services honor the contract under realistic requests. | [Execution scenario validation](/docs/concepts/execution-scenario-validation) |

## Showcases

| Showcase | What it demonstrates | Where to read |
|----------|----------------------|---------------|
| GTM Agent | Studio-produced contract, 23 capabilities, Registry package, five generated language implementations, custom bundles, agent UI, approval UI, and 490-question behavioral bank. | [GTM showcase](/docs/showcases/overview#gtm-agent-showcase) |
| Jira fronting | Governed issue triage, search, comment, transition, and mutation approval over Jira REST. | [Fronting showcases](/docs/showcases/fronting) |
| GitHub fronting | Governed repository and issue operations over GitHub APIs. | [Fronting showcases](/docs/showcases/fronting) |
| GitLab fronting | Governed project, issue, merge-request, and repository operations over GitLab APIs. | [Fronting showcases](/docs/showcases/fronting) |
| Slack fronting | Governed channel read/post capabilities with explicit approval for message sends. | [Fronting showcases](/docs/showcases/fronting) |
| Linear fronting | Governed workspace/team/issue operations over Linear GraphQL. | [Fronting showcases](/docs/showcases/fronting) |
| Notion fronting | Governed page, database, search, update, and comment capabilities over Notion API. | [Fronting showcases](/docs/showcases/fronting) |
| Superset fronting | Governed analytics capabilities over Superset REST, avoiding raw `execute_sql` as the agent-facing boundary. | [Superset local stack](/docs/showcases/overview#superset-local-stack) |
| Introductory domain examples | Smaller Travel, Finance, and DevOps examples for learning the protocol shape. | [Showcases](/docs/showcases/overview) |

## Release and Deployment Surface

| Area | Current support | Where to read |
|------|-----------------|---------------|
| CLI distribution | Prebuilt archives for macOS, Linux, and Windows on arm64/amd64; Homebrew tap flow. | [Install](/docs/getting-started/install) |
| Registry deployment | Docker image, local compose, Postgres-backed production mode, health checks, metrics, logging, and migration controls. | [Deployment](/docs/operations/deployment) |
| Studio deployment | Dockerized API/web, local compose, read-only mode, seeded showcases, metrics, and logging. | [Deployment](/docs/operations/deployment) |
| Local platform | Registry + Studio + seeded packages/templates for local evaluation. | [Local platform](/docs/getting-started/local-platform) |
| Observability | Structured logs, health/readiness endpoints, and Prometheus metrics for Registry and Studio. | [Observability](/docs/getting-started/observability) |

## Reading Order

If you are new to ANIP, use this order:

1. [Why ANIP](/docs/why-anip)
2. [ANIP vs MCP](/docs/concepts/anip-vs-mcp)
3. [Architecture](/docs/concepts/architecture)
4. [Capabilities](/docs/protocol/capabilities)
5. [Generate a service](/docs/getting-started/generate-service)
6. [Registry](/docs/getting-started/registry)
7. [Studio](/docs/getting-started/studio)
