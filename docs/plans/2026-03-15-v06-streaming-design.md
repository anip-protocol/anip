# ANIP Streaming Design

## Goal

Add progress-reporting streaming to ANIP as the first streaming primitive. Capabilities can emit structured progress events over SSE during invocation, while preserving ANIP's governance, audit, and trust model unchanged.

## Scope

- **In scope:** server-to-client progress streaming via SSE, capability declaration of streaming support, handler ergonomics, audit integration, all HTTP bindings (FastAPI, Hono, Express, Fastify).
- **Out of scope:** bidirectional streaming, explicit cancellation protocol, per-event audit entries, formalized progress payload schemas, non-HTTP transports.

## Architecture

Streaming extends ANIP's existing invocation model rather than introducing a parallel one. The same endpoint, auth flow, delegation checks, and audit logging apply. The only differences are the response format (SSE instead of JSON) and the handler's ability to emit progress events before returning a final result.

## Design Decisions

### 1. Capability Declaration

`CapabilityDeclaration` gets a new optional field:

```
response_modes: list[ResponseMode]   # default: ["unary"]
```

Where `ResponseMode` is a typed enum:

```
ResponseMode = "unary" | "streaming"
```

Constraints:
- Non-empty list
- Unique values
- Validated at registration time

A capability that supports both modes declares `["unary", "streaming"]`. Omitting the field or setting `["unary"]` preserves current behavior. The field appears in the manifest, making streaming support discoverable before invocation.

The existing `output` field describes the shape of the **final result** only. Progress event payloads are unconstrained for the first version.

### 2. Invoke Request

The invoke request body gets a new optional field:

```
stream: bool   # default: false
```

On `POST /anip/invoke/{capability}`:

1. If `stream: true`, the runtime validates against the capability's `response_modes`. If streaming is not declared, return `{ success: false, failure: { type: "streaming_not_supported" } }` (400).
2. Auth, delegation, scope, and purpose checks are identical to unary mode.
3. Response content type is `text/event-stream` instead of `application/json`.
4. No new endpoint. Streaming goes through the existing invoke route.

`stream` is part of the formal invoke request model, not ad-hoc route logic. `streaming_not_supported` is a first-class failure type in ANIP's failure taxonomy.

### 3. SSE Event Schema

Three event types:

**`progress`** — zero or more, emitted by handler:

```
event: progress
data: {
  "invocation_id": "inv-abc123",
  "client_reference_id": "ref-xyz",
  "timestamp": "2026-03-15T12:00:01Z",
  "payload": { "percent": 25, "message": "Scanning..." }
}
```

**`completed`** — exactly one, emitted by runtime when handler returns successfully:

```
event: completed
data: {
  "invocation_id": "inv-abc123",
  "client_reference_id": "ref-xyz",
  "timestamp": "2026-03-15T12:00:05Z",
  "success": true,
  "result": { "findings": [...] },
  "cost_actual": null,
  "stream_summary": {
    "response_mode": "streaming",
    "events_emitted": 3,
    "events_delivered": 3,
    "duration_ms": 4200,
    "client_disconnected": false
  }
}
```

**`failed`** — exactly one (replaces `completed`), emitted if handler raises:

```
event: failed
data: {
  "invocation_id": "inv-abc123",
  "client_reference_id": "ref-xyz",
  "timestamp": "2026-03-15T12:00:03Z",
  "success": false,
  "failure": { "type": "internal_error", "detail": "..." },
  "stream_summary": {
    "response_mode": "streaming",
    "events_emitted": 2,
    "events_delivered": 2,
    "duration_ms": 1800,
    "client_disconnected": false
  }
}
```

Design points:

- Every event carries `invocation_id`, `client_reference_id` (if provided), and `timestamp`.
- `progress.payload` is free-form (`Record<string, unknown>`). No schema enforcement for the first version.
- Terminal events (`completed`, `failed`) mirror the shape of unary invoke responses for consistency.
- `stream_summary` is runtime-managed, never handler-controlled.
- The stream terminates with exactly one of `completed` or `failed`, then the connection closes.

### 4. Handler Ergonomics

The handler signature is unchanged:

```python
# Python
async def my_handler(ctx: InvocationContext, params: dict) -> dict:
    ...
```

```typescript
// TypeScript
async function myHandler(ctx: InvocationContext, params: Record<string, unknown>): Promise<Record<string, unknown>> {
    ...
}
```

`InvocationContext` gets one new method:

```python
async def emit_progress(self, payload: dict) -> None
```

Behavior:
- **Streaming mode:** serializes `payload` as an SSE `progress` event and flushes to the client. Returns once the event is written to the transport buffer.
- **Unary mode:** no-op. Returns immediately, payload discarded.
- The runtime attaches `invocation_id`, `client_reference_id`, and `timestamp` automatically. The handler only provides the `payload` dict.

Implementation: `InvocationContext` receives an internal `_progress_sink` callable at construction. In streaming mode, this is wired to the SSE transport writer. In unary mode, it is a no-op.

Dual-mode capability example:

```python
async def analyze(ctx, params):
    for i, chunk in enumerate(scan(params["target"])):
        await ctx.emit_progress({"step": i + 1, "status": f"Scanning {chunk}..."})
    return {"findings": results}
```

This handler works identically in both modes. Unary callers get the final result. Streaming callers also see progress events.

Sync handlers remain valid for streaming-declared capabilities. The constraint is practical: calling `emit_progress` requires an async handler. Sync handlers that never call `emit_progress` work fine.

### 5. HTTP Bindings

Each binding adds streaming support to the existing invoke route:

1. Parse `stream` from request body.
2. If `stream: true`, validate against capability's `response_modes`.
3. Auth, delegation, lock logic — unchanged.
4. If streaming: set response headers (`Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`), wire a progress sink to the SSE writer, invoke handler, emit terminal event, close stream.
5. If unary: existing behavior unchanged.

Framework-specific SSE mechanisms:

| Framework | SSE pattern |
|-----------|------------|
| FastAPI | `StreamingResponse(media_type="text/event-stream")` with async generator |
| Express | `res.writeHead(200, headers)` + `res.write()` + `res.end()` |
| Hono | `new Response(ReadableStream, { headers })` |
| Fastify | `reply.raw.writeHead()` + `reply.raw.write()` + `reply.raw.end()` |

**Client disconnect handling:**

Transport disconnects and invocation outcomes are separate concerns:

- The handler is not forcibly killed on client disconnect. It runs to completion or until it next calls `emit_progress` and the sink detects the disconnect.
- The audit entry reflects the **handler's outcome**, not the transport state. If the handler completes successfully after a client disconnect, the audit records `success: true`.
- `stream_summary.client_disconnected` captures whether the client closed the connection early.
- `stream_summary.events_delivered` vs `events_emitted` reveals how many events the client actually received.

No explicit cancellation protocol in this version. Connection close is sufficient for SSE progress streaming.

### 6. Audit Integration

One invocation = one audit entry, unchanged. Streaming adds optional fields:

```
stream_summary: {
    response_mode: "streaming",
    events_emitted: int,
    events_delivered: int,
    duration_ms: int,
    client_disconnected: bool
}
```

Rules:

- `success` and `failure_type` reflect the handler's outcome, not the transport state.
- `result_summary` captures the final result (same truncation rules as unary).
- `stream_summary` is runtime-managed. Handlers do not set it.
- For unary invocations, `stream_summary` is absent (not null).
- Hash chain, Merkle tree, and signing are unchanged. The audit entry has additional optional fields to hash over.

## Version

This is a v0.6 feature. `PROTOCOL_VERSION` remains `anip/0.3` — the wire protocol is unchanged. Streaming is a runtime capability, not a protocol-level change.

## Future Extensions

These are explicitly deferred:

- **Explicit cancellation protocol** — `POST /anip/streams/{id}/cancel` with auditable cancel events.
- **Progress payload schemas** — formalized event shapes declared in capability contracts.
- **Result chunking** — `result_chunk` event type for incremental result delivery.
- **LLM token streaming** — `delta` event type for incremental text generation.
- **Event digest** — Merkle root over all emitted events for tamper-evidence of the stream itself.
- **Bidirectional streaming** — client-to-server events during an invocation.
