# ANIP Stdio Transport Binding — Design Spec

## Purpose

Define a native ANIP-over-stdio transport binding that carries the full ANIP protocol (discovery, manifest, tokens, invoke, audit, checkpoints) over stdin/stdout using JSON-RPC 2.0. This enables local agents to consume ANIP services as subprocesses without HTTP.

## Framing

- **JSON-RPC 2.0** — newline-delimited on stdin/stdout
- Each message is a single line of JSON followed by `\n`
- Client writes requests to the service's stdin
- Service writes responses to its stdout
- Stderr is reserved for logs/diagnostics (not protocol messages)

## Lifecycle

1. Client spawns the ANIP service process
2. Service initializes (storage, keys, capabilities) and begins reading stdin
3. Client sends JSON-RPC requests, service replies with JSON-RPC responses
4. When stdin closes (client disconnects), the service shuts down gracefully

No handshake or initialization method is required — the first message can be any valid ANIP method.

## Methods

9 core methods mapping to the ANIP protocol operations:

| Method | Auth Required | Description |
|---|---|---|
| `anip.discovery` | No | Get the discovery document |
| `anip.manifest` | No | Get the signed manifest |
| `anip.jwks` | No | Get the JWKS document |
| `anip.tokens.issue` | Bootstrap (API key) | Issue a delegation token |
| `anip.permissions` | JWT | Discover permissions for a token |
| `anip.invoke` | JWT | Invoke a capability |
| `anip.audit.query` | JWT | Query the audit log |
| `anip.checkpoints.list` | No | List checkpoints |
| `anip.checkpoints.get` | No | Get checkpoint detail |

Health is intentionally omitted from the core binding. It is a runtime/operational surface, not a protocol operation. Implementations may optionally support `anip.health` as an extension.

## Auth Model

Protected methods include `params.auth.bearer`:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "anip.invoke",
  "params": {
    "auth": { "bearer": "eyJhbGciOiJFUzI1NiIs..." },
    "capability": "search_flights",
    "parameters": { "origin": "SEA", "destination": "SFO" }
  }
}
```

Auth boundary (same as HTTP):
- `anip.tokens.issue` — bootstrap auth: tries `auth.bearer` as API key first via `authenticate_bearer()`, then as ANIP JWT via `resolve_bearer_token()`. This matches the HTTP token endpoint which accepts both bootstrap keys and existing JWTs for sub-delegation.
- `anip.permissions`, `anip.invoke`, `anip.audit.query` — ANIP JWT only (via `resolve_bearer_token()`)
- All other methods — no auth required

Requests to protected methods without `auth` return a JSON-RPC error.

## Method Specs

### anip.discovery

```json
// Request
{"jsonrpc": "2.0", "id": 1, "method": "anip.discovery", "params": {}}

// Response
{"jsonrpc": "2.0", "id": 1, "result": {"anip_discovery": {...}}}
```

### anip.manifest

```json
// Request
{"jsonrpc": "2.0", "id": 2, "method": "anip.manifest", "params": {}}

// Response — includes signature since there are no HTTP headers
{"jsonrpc": "2.0", "id": 2, "result": {"manifest": {...}, "signature": "eyJ..."}}
```

### anip.jwks

```json
// Request
{"jsonrpc": "2.0", "id": 3, "method": "anip.jwks", "params": {}}

// Response
{"jsonrpc": "2.0", "id": 3, "result": {"keys": [...]}}
```

### anip.tokens.issue

```json
// Request (bootstrap auth — API key)
{
  "jsonrpc": "2.0", "id": 4,
  "method": "anip.tokens.issue",
  "params": {
    "auth": { "bearer": "demo-human-key" },
    "subject": "agent:demo-agent",
    "scope": ["travel.search", "travel.book"],
    "capability": "search_flights",
    "caller_class": "internal"
  }
}

// Response
{"jsonrpc": "2.0", "id": 4, "result": {"issued": true, "token_id": "tok-...", "token": "eyJ...", "expires": "..."}}
```

Optional fields: `purpose_parameters`, `parent_token`, `ttl_hours`, `caller_class`.

### anip.permissions

```json
// Request
{
  "jsonrpc": "2.0", "id": 5,
  "method": "anip.permissions",
  "params": { "auth": { "bearer": "eyJ..." } }
}

// Response
{"jsonrpc": "2.0", "id": 5, "result": {"available": [...], "restricted": [...], "denied": [...]}}
```

### anip.invoke

**Unary mode:**

```json
// Request
{
  "jsonrpc": "2.0", "id": 6,
  "method": "anip.invoke",
  "params": {
    "auth": { "bearer": "eyJ..." },
    "capability": "search_flights",
    "parameters": { "origin": "SEA", "destination": "SFO" },
    "client_reference_id": "ref-001"
  }
}

// Response
{
  "jsonrpc": "2.0", "id": 6,
  "result": {
    "success": true,
    "result": { "flights": [...] },
    "invocation_id": "inv-abc123",
    "client_reference_id": "ref-001",
    "cost_actual": null
  }
}
```

**Streaming mode:**

```json
// Request
{
  "jsonrpc": "2.0", "id": 7,
  "method": "anip.invoke",
  "params": {
    "auth": { "bearer": "eyJ..." },
    "capability": "search_flights",
    "parameters": { "origin": "SEA", "destination": "SFO" },
    "stream": true
  }
}

// Progress notifications (server → client, no id)
{"jsonrpc": "2.0", "method": "anip.invoke.progress", "params": {"invocation_id": "inv-abc123", "payload": {...}}}
{"jsonrpc": "2.0", "method": "anip.invoke.progress", "params": {"invocation_id": "inv-abc123", "payload": {...}}}

// Final response (the single source of truth for the terminal result)
{
  "jsonrpc": "2.0", "id": 7,
  "result": {
    "success": true,
    "result": { "flights": [...] },
    "invocation_id": "inv-abc123",
    "cost_actual": null
  }
}
```

The JSON-RPC response (with `id: 7`) is the canonical terminal result. Progress notifications are informational only. No terminal notification is sent — the response IS the terminal event.

### anip.invoke failure

```json
{
  "jsonrpc": "2.0", "id": 6,
  "result": {
    "success": false,
    "failure": {
      "type": "scope_insufficient",
      "detail": "Token scope does not cover travel.book",
      "resolution": {"action": "request_scope", "grantable_by": "human:samir@example.com"},
      "retry": false
    },
    "invocation_id": "inv-abc123"
  }
}
```

ANIP invocation failures are NOT JSON-RPC errors — they are successful JSON-RPC responses with `success: false` in the result, matching the HTTP model where failures return 200/4xx with a structured body.

### anip.audit.query

```json
// Request — all filter fields supported (all optional)
{
  "jsonrpc": "2.0", "id": 8,
  "method": "anip.audit.query",
  "params": {
    "auth": { "bearer": "eyJ..." },
    "capability": "search_flights",
    "since": "2026-01-01T00:00:00Z",
    "invocation_id": "inv-abc123",
    "client_reference_id": "ref-001",
    "event_class": "high_risk_success",
    "limit": 50
  }
}

// Response
{"jsonrpc": "2.0", "id": 8, "result": {"entries": [...], "count": 3, "root_principal": "human:samir@example.com"}}
```

### anip.checkpoints.list

```json
// Request
{"jsonrpc": "2.0", "id": 9, "method": "anip.checkpoints.list", "params": {"limit": 10}}

// Response
{"jsonrpc": "2.0", "id": 9, "result": {"checkpoints": [...]}}
```

### anip.checkpoints.get

```json
// Request — all fields supported (id required, others optional)
{"jsonrpc": "2.0", "id": 10, "method": "anip.checkpoints.get", "params": {"id": "cp-abc123", "include_proof": true, "leaf_index": 5, "consistency_from": "cp-prev123"}}

// Response
{"jsonrpc": "2.0", "id": 10, "result": {"checkpoint": {...}, "inclusion_proof": {...}, "consistency_proof": {...}}}
```

## Error Handling

Transport-level errors (bad JSON, unknown method, missing auth) use JSON-RPC error responses:

```json
{
  "jsonrpc": "2.0", "id": 1,
  "error": {
    "code": -32001,
    "message": "Authentication required",
    "data": {
      "type": "authentication_required",
      "detail": "This method requires auth.bearer",
      "retry": true
    }
  }
}
```

Error code mapping:
- `-32700` — Parse error (invalid JSON)
- `-32600` — Invalid request (malformed JSON-RPC)
- `-32601` — Method not found
- `-32001` — Authentication required / invalid token / token expired
- `-32002` — Scope insufficient / budget exceeded / purpose mismatch
- `-32004` — Not found (capability, checkpoint)
- `-32603` — Internal error

The `data` field carries the full ANIP failure object when applicable.

## Implementation Shape (Python)

New package: `anip-stdio` at `packages/python/anip-stdio/`.

```python
from anip_stdio import serve_stdio

# Blocking — reads stdin, writes stdout until stdin closes
serve_stdio(service)
```

Also provides a client for agents:

```python
from anip_stdio import AnipStdioClient

# Spawns the service as a subprocess
async with AnipStdioClient("python", "app.py") as client:
    discovery = await client.discovery()
    token = await client.issue_token(bearer="demo-key", subject="agent:bot", scope=["travel.search"])
    result = await client.invoke(bearer=token["token"], capability="search_flights", parameters={...})
```

## What This Spec Does NOT Cover

- gRPC transport binding (future)
- Multi-language implementations (Go, Java, C# — later, from this same spec)
- Session-level auth
- Multiplexed concurrent requests (JSON-RPC supports this via `id`, but the first implementation may be sequential)
- Batch requests (JSON-RPC supports arrays, but not required in the first pass)
