---
title: gRPC
description: ANIP over gRPC via a shared proto definition for Python and Go core transport use cases.
---

# gRPC Transport

The gRPC binding carries ANIP over Protocol Buffers and HTTP/2. It is defined by `proto/anip/v1/anip.proto` and currently implemented for Python and Go.

**Current status:** gRPC is functional for the core transport path, but it is not the most complete ANIP 0.24 binding today. Use HTTP or stdio when you need the full release-complete surface across all five generated runtimes, especially approval-grant continuation.

## When to use gRPC

Use gRPC when:

- Your internal platform already standardizes on protobuf, HTTP/2, service mesh, or typed generated clients.
- You are using the Python or Go runtime.
- You need core ANIP discovery, manifest, token, permission, invoke, streaming invoke, audit, and checkpoint operations.

Prefer HTTP or stdio when:

- You need parity across Python, TypeScript, Go, Java, and C#.
- You need the newest approval-grant continuation flow as a first-class transport field.
- You are generating showcase services or public examples.
- You need the strongest current conformance coverage.

## Actual Service Definition

The current proto exposes these RPCs:

```protobuf
service AnipService {
  rpc Discovery(DiscoveryRequest) returns (DiscoveryResponse);
  rpc Manifest(ManifestRequest) returns (ManifestResponse);
  rpc Jwks(JwksRequest) returns (JwksResponse);
  rpc ListCheckpoints(ListCheckpointsRequest) returns (ListCheckpointsResponse);
  rpc GetCheckpoint(GetCheckpointRequest) returns (GetCheckpointResponse);

  rpc IssueToken(IssueTokenRequest) returns (IssueTokenResponse);

  rpc Permissions(PermissionsRequest) returns (PermissionsResponse);
  rpc Invoke(InvokeRequest) returns (InvokeResponse);
  rpc InvokeStream(InvokeRequest) returns (stream InvokeEvent);
  rpc QueryAudit(QueryAuditRequest) returns (QueryAuditResponse);
}
```

There is no ANIP-specific `Health` RPC in the current proto. Health checking should be handled by the platform or by a separate gRPC health service if needed.

## Capability And Manifest Fidelity

`Manifest` returns the signed manifest as JSON:

```protobuf
message ManifestResponse {
  string manifest_json = 1;
  string signature = 2;
}
```

That means newer contract fields such as composed capabilities and v0.24 input-resolution metadata can still flow through gRPC discovery as part of the signed JSON manifest.

The limitation is not manifest discovery. The limitation is typed invocation support for newer runtime workflows.

## Current Parity

| Area | Status |
|------|--------|
| Discovery, manifest, JWKS | Implemented |
| Token issuance | Implemented |
| Permission discovery | Implemented |
| Unary invoke | Implemented |
| Server-streaming invoke | Implemented |
| Audit query | Implemented |
| Checkpoints | Implemented |
| v0.24 input-resolution metadata | Preserved in manifest JSON |
| Approval-grant issuance | Not modeled as a gRPC RPC |
| Approval-grant continuation | Not modeled as an `InvokeRequest` field |
| Structured approval failure metadata | Partially lossy; only generic failure fields and `resolution_json` are first-class |
| Runtime coverage | Python and Go |
| Generator parity | HTTP and stdio are the complete generated paths today |

## Invocation Shape

The current invoke request carries capability, parameters, and lineage hints:

```protobuf
message InvokeRequest {
  string capability = 1;
  string parameters_json = 2;
  string client_reference_id = 3;
  string task_id = 4;
  string parent_invocation_id = 5;
  string upstream_service = 6;
}
```

This is enough for normal bounded invocation, but it does not yet include `approval_grant`. That matters for services that return `approval_required` and expect a later continuation call with a signed grant.

## Error Model

ANIP protocol failures are returned inside response messages instead of as gRPC status codes. gRPC status codes are reserved for transport-level errors such as missing metadata, invalid protobuf input, unavailable service, and deadline exceeded.

```protobuf
message InvokeResponse {
  bool success = 1;
  string invocation_id = 2;
  string client_reference_id = 3;
  string result_json = 4;
  string cost_actual_json = 5;
  AnipFailure failure = 6;
  string task_id = 7;
  string parent_invocation_id = 8;
  BudgetContext budget_context = 9;
  string upstream_service = 10;
}

message AnipFailure {
  string type = 1;
  string detail = 2;
  string resolution_json = 3;
  bool retry = 4;
}
```

This preserves common failure information, but it is not yet a complete typed representation of newer approval-required metadata.

## Authentication

Auth is passed via gRPC metadata:

```text
authorization: Bearer <token>
```

The token model is the same ANIP bearer-token model used by HTTP and stdio. The transport carrier is different; the delegation semantics are not supposed to change.

## Runtime Support

| Runtime | Package | Status |
|---------|---------|--------|
| Python | `anip-grpc` | Core binding implemented |
| Go | `grpcapi` | Core binding implemented |
| TypeScript | n/a | Planned |
| Java | n/a | Planned |
| C# | n/a | Planned |

## What Would Make gRPC Complete

To bring gRPC back to full current ANIP parity, the next implementation pass should:

- Add `approval_grant` to `InvokeRequest`.
- Add a first-class approval-grant issuance RPC or explicitly keep grant issuance HTTP-only and document that as a protocol decision.
- Preserve full structured failure metadata, including `approval_required`.
- Verify Python and Go delegated token issuance behavior is identical.
- Add conformance tests for approval-required, approval continuation, v0.24 input-resolution manifest fidelity, composed capabilities, budget context, lineage, audit, and streaming failure behavior.
- Regenerate Python and Go stubs from the updated proto.

Until then, treat gRPC as a functional core binding, not the default public or generated showcase transport.
