# ANIP gRPC Transport Binding — Design Spec

## Purpose

Define a native ANIP-over-gRPC transport binding that carries the full ANIP protocol using protobuf service definitions. This enables internal service-to-service agent communication, enterprise platforms, and high-throughput deployments where gRPC is the standard RPC mechanism.

## Shared Proto

A single canonical protobuf file at `proto/anip/v1/anip.proto` defines the `AnipService`. All runtimes generate stubs from this file. The proto is the wire-level contract — changing it is a versioned, compatibility-sensitive operation.

## Service Definition

11 RPCs mapping to the ANIP protocol operations (invoke split into unary and streaming):

```protobuf
syntax = "proto3";
package anip.v1;

service AnipService {
  // Public (no auth)
  rpc Discovery(DiscoveryRequest) returns (DiscoveryResponse);
  rpc Manifest(ManifestRequest) returns (ManifestResponse);
  rpc Jwks(JwksRequest) returns (JwksResponse);
  rpc ListCheckpoints(ListCheckpointsRequest) returns (ListCheckpointsResponse);
  rpc GetCheckpoint(GetCheckpointRequest) returns (GetCheckpointResponse);

  // Bootstrap or JWT auth (via metadata)
  rpc IssueToken(IssueTokenRequest) returns (IssueTokenResponse);

  // JWT auth (via metadata)
  rpc Permissions(PermissionsRequest) returns (PermissionsResponse);
  rpc Invoke(InvokeRequest) returns (InvokeResponse);
  rpc InvokeStream(InvokeRequest) returns (stream InvokeEvent);
  rpc IssueApprovalGrant(IssueApprovalGrantRequest) returns (IssueApprovalGrantResponse);
  rpc QueryAudit(QueryAuditRequest) returns (QueryAuditResponse);
}
```

## Auth Model

Bearer token via gRPC call metadata:

```
metadata key: "authorization"
metadata value: "Bearer eyJhbGciOiJFUzI1NiIs..."
```

Per-call, not per-channel. Different calls on the same channel can use different tokens.

**Auth boundary (same as HTTP and stdio):**

- `IssueToken` — bearer metadata required. Server tries bootstrap auth first (`authenticate_bearer`), then ANIP JWT resolution (`resolve_bearer_token`) for sub-delegation. Matches current HTTP behavior exactly.
- `Permissions`, `Invoke`, `InvokeStream`, `IssueApprovalGrant`, `QueryAudit` — JWT only via `resolve_bearer_token`
- `Discovery`, `Manifest`, `Jwks`, `ListCheckpoints`, `GetCheckpoint` — no auth required

**Missing auth on a protected RPC:** returns gRPC status `UNAUTHENTICATED` with a message like "Authorization metadata required".

## Error Model — The Critical Boundary

**gRPC status codes are for transport/binding failures only:**

- `UNAUTHENTICATED` — missing or unparseable bearer metadata
- `INTERNAL` — server runtime error (not ANIP protocol failure)
- `UNAVAILABLE` — service not ready

**ANIP failures stay inside response messages:**

All ANIP protocol failures (scope_insufficient, budget_exceeded, unknown_capability, purpose_mismatch, not_found, etc.) are returned as successful gRPC calls with the failure carried inside the response message. This is a gRPC-specific design decision — gRPC status codes represent transport/binding state, not application outcomes. (Note: the stdio binding takes a different approach, mapping ANIP failures to JSON-RPC error codes. The gRPC binding intentionally diverges because gRPC status codes have established semantic meanings that would be misleading if overloaded with ANIP failure types.)

Example: invoking an unknown capability returns gRPC status `OK` with:
```
InvokeResponse {
  success: false
  failure: {
    type: "unknown_capability"
    detail: "Capability 'nonexistent' not found"
  }
}
```

This separation is load-bearing. Without it, the binding blurs transport errors and protocol semantics.

## Message Types

### Request/Response Messages

```protobuf
// --- Discovery ---
message DiscoveryRequest {}
message DiscoveryResponse {
  string json = 1;  // Full discovery document as JSON string
}

// --- Manifest ---
message ManifestRequest {}
message ManifestResponse {
  string manifest_json = 1;  // Full manifest as JSON string
  string signature = 2;      // X-ANIP-Signature equivalent
}

// --- JWKS ---
message JwksRequest {}
message JwksResponse {
  string json = 1;  // Full JWKS document as JSON string
}

// --- Token Issuance ---
message IssueTokenRequest {
  string subject = 1;
  repeated string scope = 2;
  string capability = 3;
  string purpose_parameters_json = 4;  // Optional, JSON string
  string parent_token = 5;             // Optional, stored parent token ID
  int32 ttl_hours = 6;
  string caller_class = 7;
  Budget budget = 8;
}
message IssueTokenResponse {
  bool issued = 1;
  string token_id = 2;
  string token = 3;      // JWT string (when issued)
  string expires = 4;    // ISO 8601 (when issued)
  AnipFailure failure = 5; // When !issued (e.g., scope narrowing failed, insufficient authority)
  Budget budget = 6;
}

// --- Shared budget types ---
message Budget {
  string currency = 1;
  double max_amount = 2;
}
message BudgetContext {
  double budget_max = 1;
  string budget_currency = 2;
  double cost_check_amount = 3;
  string cost_certainty = 4;
  double cost_actual = 5;
  bool within_budget = 6;
}

// --- Permissions ---
message PermissionsRequest {}
message PermissionsResponse {
  bool success = 1;
  string json = 2;            // Full permissions response as JSON string (when success)
  AnipFailure failure = 3;    // When !success
}

// --- Invoke (unary) ---
message InvokeRequest {
  string capability = 1;
  string parameters_json = 2;       // JSON string
  string client_reference_id = 3;
  string task_id = 4;
  string parent_invocation_id = 5;
  string upstream_service = 6;
  string approval_grant = 7;        // ApprovalGrant continuation id
  repeated string requested_effects = 8;
}
message InvokeResponse {
  bool success = 1;
  string invocation_id = 2;
  string client_reference_id = 3;
  string result_json = 4;           // JSON string (when success)
  string cost_actual_json = 5;      // Optional, JSON string
  AnipFailure failure = 6;          // When !success
  string task_id = 7;
  string parent_invocation_id = 8;
  BudgetContext budget_context = 9;
  string upstream_service = 10;
}

// --- Invoke (streaming) ---
message InvokeEvent {
  oneof event {
    ProgressEvent progress = 1;
    CompletedEvent completed = 2;
    FailedEvent failed = 3;
  }
}
message ProgressEvent {
  string invocation_id = 1;
  string payload_json = 2;  // JSON string
}
message CompletedEvent {
  string invocation_id = 1;
  string client_reference_id = 2;
  string result_json = 3;
  string cost_actual_json = 4;
  string task_id = 5;
  string parent_invocation_id = 6;
  BudgetContext budget_context = 7;
  string upstream_service = 8;
}
message FailedEvent {
  string invocation_id = 1;
  string client_reference_id = 2;
  AnipFailure failure = 3;
  string task_id = 4;
  string parent_invocation_id = 5;
  BudgetContext budget_context = 6;
  string upstream_service = 7;
}

// --- Approval Grants ---
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

// --- Shared failure type ---
message AnipFailure {
  string type = 1;
  string detail = 2;
  string resolution_json = 3;  // Optional, JSON string
  bool retry = 4;
  string context_json = 5;     // Optional protocol-specific metadata
}

// --- Audit ---
message QueryAuditRequest {
  string capability = 1;
  string since = 2;
  string invocation_id = 3;
  string client_reference_id = 4;
  string event_class = 5;
  int32 limit = 6;
  string task_id = 7;
  string parent_invocation_id = 8;
}
message QueryAuditResponse {
  bool success = 1;
  string json = 2;            // Full audit response as JSON string (when success)
  AnipFailure failure = 3;    // When !success
}

// --- Checkpoints ---
message ListCheckpointsRequest {
  int32 limit = 1;
}
message ListCheckpointsResponse {
  string json = 1;  // Full checkpoint list as JSON string
}

message GetCheckpointRequest {
  string id = 1;
  bool include_proof = 2;
  int32 leaf_index = 3;
  string consistency_from = 4;
}
message GetCheckpointResponse {
  string json = 1;  // Full checkpoint detail as JSON string
}
```

### Design Decision: JSON strings vs full protobuf typing

Discovery, manifest, JWKS, audit, checkpoints, and permissions responses are returned as JSON strings rather than fully typed protobuf messages. This is intentional:

- These responses have complex, evolving shapes that would be expensive to keep in sync across a proto definition
- The proto contract covers the RPC surface (methods, auth, streaming); the response content follows the ANIP JSON schema
- This matches how gRPC APIs often wrap complex domain objects as JSON or `google.protobuf.Struct`
- Token issuance and invoke are fully typed because they have stable, well-defined shapes

If proto-native typing for all responses proves valuable, it can be added in a future proto version without breaking the JSON-string fields.

## Implementation Shape (Python)

New package: `anip-grpc` at `packages/python/anip-grpc/`.

**Server:**
```python
from anip_grpc import serve_grpc

# Blocking — starts gRPC server on port 50051
serve_grpc(service, port=50051)
```

**Client:**
```python
from anip_grpc import AnipGrpcClient

async with AnipGrpcClient("localhost:50051") as client:
    discovery = await client.discovery()
    token = await client.issue_token(bearer="demo-key", subject="agent:bot", scope=["travel.search"])
    result = await client.invoke(bearer=token.token, capability="search_flights", parameters={...})
```

## What This Spec Does NOT Cover

- Multi-language implementations (Go, Java, C#, TypeScript — later, from the same proto)
- gRPC-Web transport
- Bidirectional streaming (not needed for ANIP's request/response model)
- mTLS configuration (deployment concern, not protocol)
- gRPC health checking protocol (can be added alongside but is not ANIP-specific)
- Framework-specific adapters (Spring gRPC, ASP.NET gRPC — only if needed)

## First Pass

Python + Go. Python for fast iteration on the binding design, Go for validating the real gRPC-native use case (internal platforms, service mesh). Port to Java, C#, TypeScript after the binding is proven.
