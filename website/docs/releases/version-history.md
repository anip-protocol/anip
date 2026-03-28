---
title: Version History
description: ANIP protocol version progression from v0.1 through v0.11.
---

# Version History

ANIP's version line tracks the progression of protocol capabilities. The current version is **v0.11**.

## Version progression

| Version | What it added | Key concepts |
|---------|--------------|--------------|
| **v0.11** | Runtime observability | Logging, metrics, tracing, diagnostics hooks; `getHealth()`; health endpoint |
| **v0.10** | Horizontal scaling | PostgreSQL storage; leader election; exclusive invocation locks; multi-replica support |
| **v0.9** | Audit aggregation | Storage-side redaction; caller-class disclosure; audit entry aggregation for high-volume reads |
| **v0.8** | Security hardening | Event classification; two-layer retention; failure redaction; aggregation flushing |
| **v0.7** | Discovery posture | Trust posture in discovery; anchoring cadence; metadata disclosure control |
| **v0.6** | Streaming invocations | SSE-based streaming responses; `response_modes` declaration; streaming + unary support |
| **v0.5** | Async storage | Non-blocking audit writes; background checkpoint scheduling; retention enforcement |
| **v0.4** | Lineage | `invocation_id` and `client_reference_id` for cross-delegation lineage tracking |
| **v0.3** | Anchored trust | Merkle checkpoints; signed manifests; JWKS; trust levels (declarative → signed → anchored) |
| **v0.2** | Cost and failures | Cost declaration and `cost_actual`; structured failures with resolution guidance |
| **v0.1** | Core protocol | Discovery, manifest, capabilities, delegation, permissions, invoke, audit |

## What's next

- Federated trust — cross-service delegation chains and token exchange
- Studio streaming visualization — watch streaming invocations in real-time
- Studio lineage tracing — trace invocation chains through audit
- gRPC transport expansion — Java, C#, TypeScript bindings from the shared proto

For the full roadmap, see the [SPEC.md](https://github.com/anip-protocol/anip/blob/main/SPEC.md#13-roadmap-v01--v1) in the repo.
