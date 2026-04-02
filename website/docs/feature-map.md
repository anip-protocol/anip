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
| Task identity | `task_id` groups related invocations under a single task/workflow | [Delegation](/docs/protocol/delegation-permissions) |
| Invocation lineage | `parent_invocation_id` forms invocation trees for causal tracing | [Delegation](/docs/protocol/delegation-permissions) |
| Token purpose binding | `purpose.task_id` is authoritative; request must match | [Delegation](/docs/protocol/delegation-permissions) |
| Budget constraints | Enforceable `token.constraints.budget` with currency and max amount | [Delegation](/docs/protocol/delegation-permissions#budget-constraints-in-delegation) |
| Budget narrowing | Child delegation budget must be ≤ parent budget | [Delegation](/docs/protocol/delegation-permissions#budget-constraints-in-delegation) |
| Requires binding | `requires_binding` on capabilities for execution-time binding (quote, offer, price lock) | [Capabilities](/docs/protocol/capabilities) |
| Control requirements | Vocabulary: `cost_ceiling`, `stronger_delegation_required` | [Failures](/docs/protocol/failures-cost-audit) |
| Budget context | `budget_context` in invoke responses (success and failure) | [Failures](/docs/protocol/failures-cost-audit#budget-context) |
| `FinancialCost` type | Structured type replacing untyped cost dictionaries | [Cost](/docs/protocol/failures-cost-audit#cost-signaling) |
| `reason_type` on permissions | Machine-readable restriction/denial category on `restricted` and `denied` entries | [Permissions](/docs/protocol/delegation-permissions#reason_type-vocabulary-v015) |
| `resolution_hint` on permissions | Actionable suggestion string on `restricted` entries | [Permissions](/docs/protocol/delegation-permissions#resolution_hint-field-v015) |
| `non_delegable_action` failure | Capability declares it requires direct (root) principal invocation | [Failures](/docs/protocol/failures-cost-audit#v015-failure-types) |
| Canonical `request_broader_scope` | Replaces deprecated `request_scope_grant` resolution action | [Failures](/docs/protocol/failures-cost-audit#canonical-authority-resolution-actions-v015) |
| `recovery_class` on resolution | Coarse recovery strategy on every `resolution` object: 6-value vocabulary (`retry_now`, `wait_then_retry`, `refresh_then_retry`, `redelegation_then_retry`, `revalidate_then_retry`, `terminal`) | [Failures](/docs/protocol/failures-cost-audit#v016-recovery_class--coarse-recovery-strategy) |
| 5 new canonical `resolution.action` values | `retry_now`, `provide_credentials`, `wait_and_retry`, `revalidate_state`, `check_manifest` — completes the canonical action vocabulary | [Reference](/docs/protocol/reference#canonical-resolution-actions-v016) |
| `refresh_via` composition hint | Advisory array of capability names to re-invoke when a stale artifact causes failure (e.g., `binding_stale`) | [Capabilities](/docs/protocol/capabilities#advisory-composition-hints-v017) |
| `verify_via` composition hint | Advisory array of capability names to invoke to verify side effects after executing an irreversible action | [Capabilities](/docs/protocol/capabilities#advisory-composition-hints-v017) |
| Cross-service continuity | `upstream_service` on invoke request/response/audit — identifies the calling ANIP service in cross-service workflows; services MUST echo and record it, MUST NOT reject foreign `parent_invocation_id` or `task_id` values | [Lineage](/docs/protocol/lineage#cross-service-continuity-v018) |
| Cross-service handoff hints | `cross_service` on capability declarations with four advisory arrays (`handoff_to`, `refresh_via`, `verify_via`, `followup_via`), each containing `ServiceCapabilityRef` objects (`service` + `capability` strings) for cross-service workflow guidance | [Capabilities](/docs/protocol/capabilities#cross-service-handoff-hints-v019) |

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
