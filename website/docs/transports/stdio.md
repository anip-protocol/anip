---
title: stdio
description: ANIP over JSON-RPC 2.0 on stdin/stdout for local agent communication.
---

# stdio Transport

The stdio binding carries native ANIP over JSON-RPC 2.0 on stdin/stdout. An agent, IDE, CLI, or local tool launches the ANIP service as a subprocess and communicates without opening a network port.

The capability contract is the same contract used by HTTP: signed manifest, scoped delegation, permission discovery, structured failures, approval continuation, lineage, audit, and checkpoints. Only the message framing changes.

## When to use stdio

- A local agent should spawn a service as a subprocess.
- A sandbox or developer machine should avoid opening a network port.
- An IDE or CLI manages the service lifecycle.
- You want local ANIP capabilities available to agent clients without Docker or service discovery.

Use HTTP for deployed services and Studio/browser integration. Use stdio for local process integration.

## Wire format

Messages are newline-delimited JSON-RPC 2.0 objects:

- Client to server: stdin.
- Server to client: stdout.
- Logs should go to stderr, not stdout.
- Requests require an `id`; request-style JSON-RPC notifications are not accepted.

```json
{"jsonrpc": "2.0", "id": 1, "method": "anip.discovery", "params": {}}
```

```json
{"jsonrpc": "2.0", "id": 1, "result": {"anip_discovery": {"version": "0.24.4", ...}}}
```

Generated runtimes use line-delimited JSON rather than `Content-Length` framing.

## Method mapping

Each ANIP operation maps to a JSON-RPC method:

| ANIP operation | JSON-RPC method | Notes |
|----------------|-----------------|-------|
| Discovery | `anip.discovery` | No auth required |
| Manifest | `anip.manifest` | Returns manifest plus signature |
| JWKS | `anip.jwks` | No auth required |
| Issue token | `anip.tokens.issue` | Requires `auth.bearer` |
| Permissions | `anip.permissions` | Requires ANIP delegation token |
| Invoke | `anip.invoke` | Requires ANIP delegation token |
| Audit query | `anip.audit.query` | Requires ANIP delegation token |
| Checkpoints list | `anip.checkpoints.list` | No auth required |
| Checkpoint detail | `anip.checkpoints.get` | No auth required |

Some runtimes also expose `anip.graph` for capability graph inspection. Treat it as optional and discoverable runtime functionality, not a required base method.

## Authentication

Since there's no HTTP header in stdio, auth is passed in the request params:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "anip.invoke",
  "params": {
    "capability": "search_flights",
    "parameters": {"origin": "SEA", "destination": "SFO"},
    "auth": {"bearer": "demo-key"}
  }
}
```

The bearer can be:

- A bootstrap API key or OIDC token for `anip.tokens.issue`.
- An ANIP delegation token for permission discovery, invoke, and audit.

The token semantics are identical to HTTP. The carrier is different because stdio has no headers.

## Token issuance

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "anip.tokens.issue",
  "params": {
    "auth": {"bearer": "demo-key"},
    "subject": "agent-007",
    "scope": ["travel.search"],
    "capability": "search_flights",
    "purpose_parameters": {"task_id": "planning-trip"},
    "ttl_hours": 2
  }
}
```

Typical response:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "issued": true,
    "token_id": "tok_root_001",
    "token": "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9...",
    "scope": ["travel.search"],
    "capability": "search_flights",
    "task_id": "planning-trip"
  }
}
```

## Invocation

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "anip.invoke",
  "params": {
    "auth": {"bearer": "<delegation-token>"},
    "capability": "search_flights",
    "parameters": {
      "origin": "SEA",
      "destination": "SFO"
    },
    "client_reference_id": "task:abc/step-3",
    "task_id": "planning-trip"
  }
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "success": true,
    "invocation_id": "inv-7f3a2b4c5d6e",
    "client_reference_id": "task:abc/step-3",
    "task_id": "planning-trip",
    "result": {
      "flights": [
        {"flight_number": "AA100", "price": 420}
      ]
    }
  }
}
```

Continuation after an approval grant uses the same `anip.invoke` method with `approval_grant`:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "anip.invoke",
  "params": {
    "auth": {"bearer": "<delegation-token>"},
    "capability": "slack.message.prepare",
    "approval_grant": "grant_456",
    "parameters": {
      "channel_id": "C0123456789",
      "text": "Approved incident update"
    }
  }
}
```

Grant issuance itself is currently handled through the HTTP approval endpoint or runtime/helper APIs. The stdio invocation path accepts the resulting grant ID.

## Streaming

Set `stream: true` on `anip.invoke` to request progress notifications before the final response:

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "anip.invoke",
  "params": {
    "auth": {"bearer": "<delegation-token>"},
    "capability": "long_running_report",
    "parameters": {"quarter": "2026-Q2"},
    "stream": true
  }
}
```

Progress events are JSON-RPC notifications:

```json
{"jsonrpc":"2.0","method":"anip.invoke.progress","params":{"message":"Loading source data"}}
```

The final message is the normal JSON-RPC response with the original `id`.

For simple clients, serialize requests on one process. If a client overlaps calls, it must correctly demultiplex progress notifications and final responses by request lifecycle.

## Errors

Invalid JSON-RPC envelopes return standard JSON-RPC errors:

| Code | Meaning |
|------|---------|
| `-32700` | Parse error |
| `-32600` | Invalid request |
| `-32601` | Method not found |
| `-32603` | Internal error |

ANIP failures are carried in JSON-RPC error `data` where the runtime maps protocol failure categories to transport error codes:

```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "error": {
    "code": -32002,
    "message": "Capability cost $487 exceeds delegated budget of $200",
    "data": {
      "type": "budget_exceeded",
      "detail": "Capability cost $487 exceeds delegated budget of $200",
      "retry": false
    }
  }
}
```

Transport errors do not replace ANIP structured failures; they are the JSON-RPC carrier for them.

## Generate a stdio runner

The generator can emit stdio runners for all five supported targets:

```bash
anip generate \
  --package my-service@0.2.0 \
  --target python \
  --transport http,stdio \
  --output ./generated/my-service
```

Typical generated entry points:

| Target | Command |
|--------|---------|
| Python | `python -m <service_module>.stdio_app` |
| TypeScript | `npm run stdio` |
| Go | `go run . --stdio` |
| Java | Generated stdio main class using `anip-stdio` |
| C# | `dotnet run --project ./<Service>.csproj -- --stdio` |

## Runtime Support

Available in all five runtimes: TypeScript (`@anip-dev/stdio`), Python (`anip-stdio`), Java (`anip-stdio`), Go (`stdioapi`), C# (`Anip.Stdio`).

## Relationship to MCP stdio

ANIP stdio and MCP stdio are both subprocess transports, but they are not the same protocol.

| Surface | Purpose |
|---------|---------|
| ANIP stdio | Native ANIP protocol over JSON-RPC: governed capabilities, delegation, permission discovery, invoke, audit, checkpoints. |
| MCP stdio | MCP tool discovery/invocation over stdio for MCP clients. |

If an MCP client needs to consume an ANIP service, expose a generated MCP interface adapter. If a local agent or tool can speak ANIP directly, use native ANIP stdio.

## Next steps

- [Transport overview](/docs/transports/overview)
- [HTTP transport](/docs/transports/http)
- [gRPC transport](/docs/transports/grpc)
- [Generated interfaces](/docs/generated-services/interfaces)
