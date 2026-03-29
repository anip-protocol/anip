---
sidebar_position: 3
title: Feature Map
description: Complete inventory of ANIP protocol features, runtimes, transports, and tooling.
---

# Feature Map

A complete inventory of what ANIP includes today, organized by layer.

## Protocol primitives

| Feature | Description | Spec section |
|---------|-------------|-------------|
| Capability declaration | Name, description, inputs, outputs, side-effect type, scope, cost | [Capabilities](/docs/protocol/capabilities) |
| Side-effect typing | `read`, `write`, `transactional`, `irreversible` | [Capabilities](/docs/protocol/capabilities#side-effect-types) |
| Delegation | Scoped JWT authority chains with budget and purpose constraints | [Delegation](/docs/protocol/delegation-permissions) |
| Permission discovery | Pre-invoke check: available / restricted / denied | [Permissions](/docs/protocol/delegation-permissions#permission-discovery) |
| Structured failures | Type, detail, resolution action, grantable_by, retry | [Failures](/docs/protocol/failures-cost-audit) |
| Cost signaling | Declared range before invoke, actual cost after | [Cost](/docs/protocol/failures-cost-audit#cost-signaling) |
| Capability graph | Prerequisites and compensation path declarations | [Capabilities](/docs/protocol/capabilities#capability-graph) |

## Trust and verification

| Feature | Description |
|---------|-------------|
| Signed manifests | Cryptographic signature via `X-ANIP-Signature` header |
| JWKS | Standard JSON Web Key Set for signature verification |
| Audit logging | Protocol-level logging with event classification, retention policy |
| Merkle checkpoints | Tamper-evident audit history with inclusion proofs |
| Trust posture | Service-declared trust level: declarative → signed → anchored |

## Runtimes

| Runtime | Service package | Framework adapters |
|---------|----------------|-------------------|
| TypeScript | `@anip-dev/service` | Hono, Express, Fastify |
| Python | `anip-service` | FastAPI |
| Java | `anip-service` | Spring Boot, Quarkus |
| Go | `service` | net/http, Gin |
| C# | `Anip.Service` | ASP.NET Core |

## Transports

| Transport | Wire format | Runtimes |
|-----------|------------|----------|
| [HTTP](/docs/transports/http) | REST-like endpoints | All 5 |
| [stdio](/docs/transports/stdio) | JSON-RPC 2.0 | All 5 |
| [gRPC](/docs/transports/grpc) | Protobuf / HTTP/2 | Python, Go |

## Interface adapters

| Adapter | Generated from | Endpoint |
|---------|---------------|----------|
| REST | Capability declarations | `/api/*` (OpenAPI + Swagger UI) |
| GraphQL | Capability declarations | `/graphql` (SDL + directives) |
| MCP | Capability declarations | `/mcp` (Streamable HTTP) |

## Tooling

| Tool | Purpose | How to use |
|------|---------|-----------|
| [Studio](/docs/tooling/studio) | Inspection + invocation UI | Embedded at `/studio` or standalone Docker |
| [Conformance](/docs/tooling/conformance-contract-testing) | Protocol compliance testing | `pytest conformance/` against any HTTP service |
| [Contract testing](/docs/tooling/conformance-contract-testing#contract-testing) | Behavioral truthfulness verification | `anip-contract-tests` with test packs |
| Showcase apps | Reference implementations | Travel, finance, DevOps — full protocol surface |
