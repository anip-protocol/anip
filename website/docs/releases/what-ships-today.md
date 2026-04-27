---
title: What Ships Today
description: Current distribution status across all ANIP ecosystems.
---

# What Ships Today

ANIP is not a spec waiting for implementations. Here's what's available now.

## Protocol features through v0.23

Everything below is implemented in the runtimes and exercised by the conformance suite:

- **Core protocol (v0.1)**: Discovery, manifest, capabilities, delegation, permissions, invoke, audit
- **Cost and failures (v0.2)**: Cost declaration, `cost_actual`, structured failures with resolution guidance
- **Anchored trust (v0.3)**: Merkle checkpoints, signed manifests, JWKS, trust levels
- **Lineage (v0.4)**: `invocation_id` and `client_reference_id` for cross-delegation lineage
- **Async storage (v0.5)**: Non-blocking audit writes, background checkpoint scheduling
- **Streaming (v0.6)**: SSE-based streaming responses, `response_modes` declaration
- **Discovery posture (v0.7)**: Trust posture in discovery, anchoring cadence, metadata disclosure
- **Security hardening (v0.8)**: Event classification, two-layer retention, failure redaction
- **Audit aggregation (v0.9)**: Storage-side redaction, caller-class disclosure, aggregation
- **Horizontal scaling (v0.10)**: PostgreSQL storage, leader election, exclusive invocation locks
- **Observability (v0.11)**: Logging, metrics, tracing, diagnostics hooks, `getHealth()`
- **Task identity and invocation lineage (v0.12)**: `task_id` groups related invocations under a single task/workflow; `parent_invocation_id` forms invocation trees for causal tracing; token purpose binding (`purpose.task_id` authoritative, request must match); audit queries filterable by `task_id` and `parent_invocation_id`
- **Budget, binding, and control (v0.13)**: Enforceable budget constraints via `token.constraints.budget`; budget narrowing in delegation chains; `requires_binding` on capabilities for execution-time binding; `control_requirements` vocabulary; 6 new failure types; `budget_context` in invoke responses; `unmet_token_requirements` in permission discovery; `FinancialCost` structured type
- **Binding/control simplification (v0.14)**: Removed `bound_reference`/`freshness_window` overlap from `control_requirements`; protocol version `anip/0.14`
- **Authority and blocked-action clarity (v0.15)**: `reason_type` on restricted/denied capabilities (5 values); `resolution_hint` on restricted; `non_delegable_action` failure type; canonical authority actions (`request_broader_scope`, `request_capability_binding`); deprecated `request_scope_grant`
- **Recovery posture (v0.16)**: `recovery_class` on resolution (6 values: `retry_now`, `wait_then_retry`, `refresh_then_retry`, `redelegation_then_retry`, `revalidate_then_retry`, `terminal`); 5 new canonical actions (`retry_now`, `revalidate_state`, `provide_credentials`, `check_manifest`, `contact_service_owner`); all transport-layer actions canonicalized
- **Advisory composition hints (v0.17)**: `refresh_via` and `verify_via` on capability declarations; same-manifest advisory hints for refresh paths and post-action verification
- **Cross-service continuity (v0.18)**: `upstream_service` optional field on invoke request, response, and audit — identifies the originating ANIP service in cross-service workflows; echoed in response and recorded in audit; services MUST NOT reject foreign `parent_invocation_id` or `task_id` values
- **Cross-service handoff hints (v0.19)**: `cross_service` optional object on capability declarations — four advisory arrays (`handoff_to`, `refresh_via`, `verify_via`, `followup_via`) of `ServiceCapabilityRef` objects (`service` + `capability` strings) that guide agents across multi-service workflows without encoding hard protocol constraints
- **Bootstrap auth and capability-targeted issuance (v0.20)**: Explicit bootstrap auth hook contract (sync MUST, async MAY); `issueCapabilityToken()` root-only helper in all 5 runtimes — pre-binds capability, requires explicit scope, prevents `purpose_mismatch` errors
- **Cross-service contracts and recovery targets (v0.21)**: `cross_service_contract` with structured handoff/followup/verification entries carrying task-local continuity and completion modes; `recovery_target` in resolution objects with kind/target/continuity/retry_after_target — stronger than advisory hints, not a workflow engine
- **Delegated issuance ergonomics (v0.22)**: Canonical `parent_token` semantics (token ID string, not JWT) aligned across all runtimes; `issueDelegatedCapabilityToken()` helper in all 5 runtimes; token issuance responses echo `task_id` for consumer-side task continuity
- **Capability composition + approval grants (v0.23)**: Capabilities declare a `kind` (`atomic` or `composed`); composed capabilities expose a declarative `composition` step graph (steps, input/output mapping, empty-result policy, failure policy, audit policy) as protocol-visible metadata, so agents pick one bounded business capability and the runtime owns step orchestration. The `approval_required` failure persists an `ApprovalRequest`; approvers issue a signed `ApprovalGrant` (`one_time` or `session_bound`) via `POST /anip/approval_grants` that the requester redeems on a follow-up invoke (Phase A read-side validation + Phase B atomic reservation). Session identity is bound into the signed delegation token (`anip:session_id`), so session-bound continuations can't be forged from request bodies. Detached JWS over canonical-sorted JSON gives cross-runtime grant signature compatibility — a grant signed by one runtime verifies in any other.

## Published to package registries

| Ecosystem | Registry | Packages | Install |
|-----------|----------|----------|---------|
| TypeScript | npm | 14 packages (`@anip-dev/core` through `@anip-dev/stdio`) | `npm install @anip-dev/service @anip-dev/hono` |
| Python | PyPI | 11 packages (`anip-core` through `anip-grpc`) | `pip install anip-service anip-fastapi` |
| Java | Maven Central | 16 modules under `dev.anip` | See [Install](/docs/getting-started/install) |
| Go | Module tags | 1 module with 12 packages | `go get github.com/anip-protocol/anip/packages/go` |

## Available in-repo

| Artifact | Status |
|----------|--------|
| C# runtime + adapters (12 projects) | Source available, NuGet publishing not yet configured |
| Conformance suite | `pip install -e ./conformance` |
| Contract testing harness | `pip install -e ./contract-tests` |
| Studio standalone Docker | `docker build -t anip-studio studio/` |
| Showcase apps (travel, finance, DevOps) | Runnable from repo, not packaged as standalone artifacts |

## Not yet published

- C# NuGet packages
- Studio Docker image to GHCR
- Conformance suite to PyPI
- Contract testing harness to PyPI

For detailed package lists per ecosystem, see the [distribution page](https://github.com/anip-protocol/anip/blob/main/docs/distribution.md) in the repo.
