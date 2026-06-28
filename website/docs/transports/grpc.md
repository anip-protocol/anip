---
title: gRPC
description: ANIP over gRPC via a shared proto definition for Python and Go core transport use cases.
---

# gRPC Transport

The gRPC binding carries ANIP over Protocol Buffers and HTTP/2. It is defined by `proto/anip/v1/anip.proto` and currently implemented for Python and Go.

**Current status:** gRPC supports the `anip/0.24` core service surface for Python and Go: discovery, signed manifest, JWKS, token issuance, permissions, unary invoke, streaming invoke, approval-grant issuance, audit query, and checkpoints. HTTP and stdio remain the default public/generated paths because they have broader runtime coverage across the full five-language generator surface.

## When To Use gRPC

Use gRPC when:

- Your internal platform already standardizes on protobuf, HTTP/2, service mesh, or typed generated clients.
- You are building with the Python or Go runtime.
- You need typed transport operations while preserving ANIP JSON manifest, discovery, audit, and checkpoint payloads.
- You need approval-required continuation over gRPC without falling back to HTTP.

Prefer HTTP or stdio when:

- You need generated service parity across Python, TypeScript, Go, Java, and C#.
- You are publishing public showcase services where HTTP or stdio is the documented path.
- You need client SDK coverage beyond Python and Go.

## Service Definition

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
  rpc IssueApprovalGrant(IssueApprovalGrantRequest) returns (IssueApprovalGrantResponse);
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

This is intentional. Discovery, manifest, permissions, audit, checkpoints, and JWKS have evolving ANIP JSON shapes. gRPC defines the transport envelope, while the payload follows the same ANIP JSON contract used by HTTP and stdio.

## Current Parity

| Area | Status |
|------|--------|
| Discovery, manifest, JWKS | Implemented |
| Token issuance | Implemented |
| Permission discovery | Implemented |
| Unary invoke | Implemented |
| Server-streaming invoke | Implemented |
| Approval-grant issuance | Implemented |
| Approval-grant continuation | Implemented through `InvokeRequest.approval_grant` |
| Requested effects | Implemented through `InvokeRequest.requested_effects` |
| Structured failure metadata | Preserved through `AnipFailure.context_json` |
| Audit query | Implemented |
| Checkpoints | Implemented |
| v0.24 input-resolution metadata | Preserved in manifest/discovery JSON |
| Runtime coverage | Python and Go |
| Generator parity | HTTP and stdio remain the five-language generated paths |

## Invocation Shape

The invoke request carries capability, parameters, lineage hints, approval continuation, and requested business effects:

```protobuf
message InvokeRequest {
  string capability = 1;
  string parameters_json = 2;
  string client_reference_id = 3;
  string task_id = 4;
  string parent_invocation_id = 5;
  string upstream_service = 6;
  string approval_grant = 7;
  repeated string requested_effects = 8;
}
```

`approval_grant` is the signed grant ID returned by `IssueApprovalGrant`. `requested_effects` carries the caller-requested canonical business effect IDs into the runtime so the service can enforce effect compatibility instead of relying on prose.

## Approval Grants

Approval-required flows use two gRPC operations:

```protobuf
rpc Invoke(InvokeRequest) returns (InvokeResponse);
rpc IssueApprovalGrant(IssueApprovalGrantRequest) returns (IssueApprovalGrantResponse);
```

An approval-required invoke returns `success=false`, `failure.type="approval_required"`, and structured approval metadata in `failure.context_json`. The caller then requests a signed grant with `IssueApprovalGrant` using an approver-scoped token, and retries `Invoke` with `approval_grant`.

```protobuf
message IssueApprovalGrantRequest {
  string approval_request_id = 1;
  string grant_type = 2;
  string session_id = 3;
  optional int32 expires_in_seconds = 4;
  optional int32 max_uses = 5;
}

message IssueApprovalGrantResponse {
  bool success = 1;
  string grant_json = 2;
  AnipFailure failure = 3;
}
```

The optional numeric fields intentionally preserve the difference between “not supplied” and “supplied as zero,” matching the HTTP schema invariants.

## Error Model

ANIP protocol failures are returned inside response messages instead of as gRPC status codes. gRPC status codes are reserved for transport-level errors such as missing metadata, invalid protobuf input, unavailable service, and deadline exceeded.

```protobuf
message AnipFailure {
  string type = 1;
  string detail = 2;
  string resolution_json = 3;
  bool retry = 4;
  string context_json = 5;
}
```

`context_json` is a JSON object containing protocol-specific metadata that does not belong in the generic failure fields. For example, `approval_required` metadata is preserved there so gRPC clients can issue and redeem approval grants without using HTTP.

## Authentication

Auth is passed via gRPC metadata:

```text
authorization: Bearer <token>
```

The token model is the same ANIP bearer-token model used by HTTP and stdio. The transport carrier is different; delegation semantics do not change.

## Runtime Support

| Runtime | Package | Status |
|---------|---------|--------|
| Python | `anip-grpc` | Implemented and covered by transport tests |
| Go | `grpcapi` | Implemented and covered by transport tests |
| TypeScript | n/a | Planned |
| Java | n/a | Planned |
| C# | n/a | Planned |

## Remaining Limits

- gRPC is currently implemented only for Python and Go.
- Generated showcase services still use HTTP and stdio as the default documented transports.
- The standalone capability graph endpoint is not exposed as a dedicated gRPC RPC; graph data remains available through manifest/discovery JSON.
- Cross-language gRPC clients for TypeScript, Java, and C# are not packaged yet.

Treat gRPC as a verified Python/Go transport, not yet as the default five-language public showcase transport.
