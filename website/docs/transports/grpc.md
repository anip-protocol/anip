---
title: gRPC
description: ANIP over gRPC via shared proto definition for high-performance environments.
---

# gRPC Transport

The gRPC binding carries ANIP over Protocol Buffers and HTTP/2. It's defined by a shared proto file at `proto/anip/v1/anip.proto` and currently implemented in Python and Go.

## When to use gRPC

- Internal platform environments that already use protobuf and service mesh
- Performance-sensitive scenarios where protobuf serialization and HTTP/2 multiplexing matter
- Polyglot environments generating typed clients from the proto

## Service definition

The proto defines 10 RPCs mapping to ANIP's protocol operations:

```protobuf
service AnipService {
  rpc Discovery(DiscoveryRequest)     returns (DiscoveryResponse);
  rpc Manifest(ManifestRequest)       returns (ManifestResponse);
  rpc Jwks(JwksRequest)               returns (JwksResponse);
  rpc IssueToken(IssueTokenRequest)   returns (IssueTokenResponse);
  rpc Permissions(PermissionsRequest) returns (PermissionsResponse);
  rpc Invoke(InvokeRequest)           returns (InvokeResponse);
  rpc Audit(AuditRequest)             returns (AuditResponse);
  rpc Checkpoints(CheckpointsRequest) returns (CheckpointsResponse);
  rpc CheckpointDetail(CheckpointDetailRequest) returns (CheckpointDetailResponse);
  rpc Health(HealthRequest)           returns (HealthResponse);
}
```

## Error model

ANIP failures are returned in the response body, not as gRPC status codes. This preserves the structured failure model (type, detail, resolution) that agents depend on:

```protobuf
message InvokeResponse {
  bool success = 1;
  string invocation_id = 2;
  google.protobuf.Struct result = 3;
  AnipFailure failure = 4;
}

message AnipFailure {
  string type = 1;
  string detail = 2;
  bool retry = 3;
  Resolution resolution = 4;
}
```

gRPC status codes are reserved for transport-level errors (unavailable, deadline exceeded, etc.).

## Authentication

Auth is passed via gRPC metadata:

```
authorization: Bearer <token>
```

## Runtime support

| Runtime | Package |
|---------|---------|
| Python | `anip-grpc` |
| Go | `grpcapi` |
| Java, C#, TypeScript | Planned (generate from shared proto) |
