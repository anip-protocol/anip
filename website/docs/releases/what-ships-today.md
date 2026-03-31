---
title: What Ships Today
description: Current distribution status across all ANIP ecosystems.
---

# What Ships Today

ANIP is not a spec waiting for implementations. Here's what's available now.

## Protocol features through v0.13

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
- **Budget, binding, and control (v0.13)**: Enforceable budget constraints via `token.constraints.budget`; budget narrowing in delegation chains; `requires_binding` on capabilities for execution-time binding; `control_requirements` vocabulary; 6 new failure types; `budget_context` in invoke responses; `unmet_token_requirements` in permission discovery; `FinancialCost` structured type; protocol version `anip/0.13`

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
