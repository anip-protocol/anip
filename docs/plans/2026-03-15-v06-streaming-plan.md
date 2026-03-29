# ANIP v0.6 Streaming Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add progress-reporting streaming to ANIP via SSE and bump all packages to v0.6.0, allowing capabilities to emit structured progress events during invocation while preserving the existing governance and audit model.

**Architecture:** Streaming extends the existing `/anip/invoke/{capability}` endpoint via a `stream: true` request field. Handlers call `ctx.emit_progress(payload)` (no-op in unary mode). The runtime emits SSE events (`progress`, `completed`, `failed`) and logs a single audit entry with an optional `stream_summary`. No new endpoints, no protocol version change.

**Tech Stack:** Python (Pydantic, FastAPI StreamingResponse), TypeScript (Zod, Node SSE via raw Response/write), SSE (text/event-stream).

---

### Task 1: Python Core Models — ResponseMode Enum and CapabilityDeclaration Update

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/python/anip-core/src/anip_core/__init__.py`
- Test: `packages/python/anip-core/tests/test_models.py`

**Step 1: Write the failing test**

Add to `packages/python/anip-core/tests/test_models.py`:

```python
from anip_core import ResponseMode


def test_response_mode_enum():
    assert ResponseMode.UNARY == "unary"
    assert ResponseMode.STREAMING == "streaming"


def test_capability_declaration_response_modes_default():
    decl = CapabilityDeclaration(
        name="test", description="Test", contract_version="1.0",
        inputs=[], output={"type": "object", "fields": []},
        side_effect={"type": "read"}, minimum_scope=["test"],
    )
    assert decl.response_modes == [ResponseMode.UNARY]


def test_capability_declaration_response_modes_streaming():
    decl = CapabilityDeclaration(
        name="test", description="Test", contract_version="1.0",
        inputs=[], output={"type": "object", "fields": []},
        side_effect={"type": "read"}, minimum_scope=["test"],
        response_modes=["streaming"],
    )
    assert decl.response_modes == [ResponseMode.STREAMING]


def test_capability_declaration_response_modes_both():
    decl = CapabilityDeclaration(
        name="test", description="Test", contract_version="1.0",
        inputs=[], output={"type": "object", "fields": []},
        side_effect={"type": "read"}, minimum_scope=["test"],
        response_modes=["unary", "streaming"],
    )
    assert len(decl.response_modes) == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest packages/python/anip-core/tests/test_models.py -v -k "response_mode"`
Expected: FAIL — `ResponseMode` not found

**Step 3: Write minimal implementation**

In `packages/python/anip-core/src/anip_core/models.py`, add after the `SideEffectType` enum (after line 19):

```python
class ResponseMode(str, Enum):
    UNARY = "unary"
    STREAMING = "streaming"
```

Update `CapabilityDeclaration` (line 131-143) to add after `observability`:

```python
    response_modes: list[ResponseMode] = Field(default_factory=lambda: [ResponseMode.UNARY])
```

In `packages/python/anip-core/src/anip_core/__init__.py`, add `ResponseMode` to the imports from `.models` and to `__all__` (in the Enums section).

**Step 4: Run test to verify it passes**

Run: `pytest packages/python/anip-core/tests/test_models.py -v -k "response_mode"`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add packages/python/anip-core/
git commit -m "feat(core): add ResponseMode enum and response_modes to CapabilityDeclaration"
```

---

### Task 2: Python Core Models — StreamSummary and InvokeRequest.stream

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/python/anip-core/src/anip_core/__init__.py`
- Test: `packages/python/anip-core/tests/test_models.py`

**Step 1: Write the failing test**

Add to `packages/python/anip-core/tests/test_models.py`:

```python
from anip_core import StreamSummary


def test_stream_summary():
    ss = StreamSummary(
        response_mode="streaming",
        events_emitted=5,
        events_delivered=3,
        duration_ms=1200,
        client_disconnected=True,
    )
    assert ss.events_emitted == 5
    assert ss.client_disconnected is True


def test_invoke_request_stream_default_false():
    req = InvokeRequest(
        token="jwt-string",
        parameters={"x": 1},
    )
    assert req.stream is False


def test_invoke_request_stream_true():
    req = InvokeRequest(
        token="jwt-string",
        parameters={"x": 1},
        stream=True,
    )
    assert req.stream is True
```

**Step 2: Run test to verify it fails**

Run: `pytest packages/python/anip-core/tests/test_models.py -v -k "stream"`
Expected: FAIL — `StreamSummary` not found

**Step 3: Write minimal implementation**

In `packages/python/anip-core/src/anip_core/models.py`:

Add `StreamSummary` after `InvokeResponse` (after line 266):

```python
class StreamSummary(BaseModel):
    response_mode: str = "streaming"
    events_emitted: int
    events_delivered: int
    duration_ms: int
    client_disconnected: bool
```

Add `stream_summary` field to `InvokeResponse` (line 258-265), after `session`:

```python
    stream_summary: StreamSummary | None = None
```

Add `stream` field to `InvokeRequest` (line 250-255), after `client_reference_id`:

```python
    stream: bool = False
```

In `__init__.py`, add `StreamSummary` to imports and `__all__`.

**Step 4: Run test to verify it passes**

Run: `pytest packages/python/anip-core/tests/test_models.py -v -k "stream"`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add packages/python/anip-core/
git commit -m "feat(core): add StreamSummary model and stream field on InvokeRequest"
```

---

### Task 3: TypeScript Core Models — ResponseMode, StreamSummary, Updated Schemas

**Files:**
- Modify: `packages/typescript/core/src/models.ts`
- Test: `packages/typescript/core/tests/models.test.ts`

**Step 1: Write the failing test**

Add to `packages/typescript/core/tests/models.test.ts`:

```typescript
import { ResponseMode, StreamSummary } from "../src/models.js";

describe("ResponseMode", () => {
  it("accepts valid values", () => {
    expect(ResponseMode.parse("unary")).toBe("unary");
    expect(ResponseMode.parse("streaming")).toBe("streaming");
  });

  it("rejects invalid values", () => {
    expect(() => ResponseMode.parse("invalid")).toThrow();
  });
});

describe("StreamSummary", () => {
  it("parses a valid stream summary", () => {
    const ss = StreamSummary.parse({
      response_mode: "streaming",
      events_emitted: 5,
      events_delivered: 3,
      duration_ms: 1200,
      client_disconnected: true,
    });
    expect(ss.events_emitted).toBe(5);
    expect(ss.client_disconnected).toBe(true);
  });
});

describe("CapabilityDeclaration with response_modes", () => {
  it("defaults to unary", () => {
    const decl = CapabilityDeclaration.parse({
      name: "test", description: "Test", inputs: [],
      output: { type: "object", fields: [] },
      side_effect: { type: "read" }, minimum_scope: ["test"],
    });
    expect(decl.response_modes).toEqual(["unary"]);
  });

  it("accepts streaming", () => {
    const decl = CapabilityDeclaration.parse({
      name: "test", description: "Test", inputs: [],
      output: { type: "object", fields: [] },
      side_effect: { type: "read" }, minimum_scope: ["test"],
      response_modes: ["unary", "streaming"],
    });
    expect(decl.response_modes).toEqual(["unary", "streaming"]);
  });
});

describe("InvokeRequest with stream", () => {
  it("defaults stream to false", () => {
    const req = InvokeRequest.parse({ token: "jwt" });
    expect(req.stream).toBe(false);
  });

  it("accepts stream true", () => {
    const req = InvokeRequest.parse({ token: "jwt", stream: true });
    expect(req.stream).toBe(true);
  });
});
```

Note: ensure `CapabilityDeclaration` and `InvokeRequest` are imported at the top of the test file alongside the existing imports.

**Step 2: Run test to verify it fails**

Run: `cd packages/typescript && npx vitest run core/tests/models.test.ts -v`
Expected: FAIL — `ResponseMode` not exported

**Step 3: Write minimal implementation**

In `packages/typescript/core/src/models.ts`:

Add after `ObservabilityContract` (after line 128), before `CapabilityDeclaration`:

```typescript
export const ResponseMode = z.enum(["unary", "streaming"]);
export type ResponseMode = z.infer<typeof ResponseMode>;
```

Update `CapabilityDeclaration` (line 130-143) to add after `observability`:

```typescript
  response_modes: z.array(ResponseMode).min(1).default(["unary"]),
```

Add after `InvokeResponse` (after line 284):

```typescript
export const StreamSummary = z.object({
  response_mode: z.literal("streaming"),
  events_emitted: z.number().int(),
  events_delivered: z.number().int(),
  duration_ms: z.number().int(),
  client_disconnected: z.boolean(),
});
export type StreamSummary = z.infer<typeof StreamSummary>;
```

Update `InvokeRequest` (line 267-272) to add after `client_reference_id`:

```typescript
  stream: z.boolean().default(false),
```

Update `InvokeResponse` (line 275-284) to add after `session`:

```typescript
  stream_summary: StreamSummary.nullable().default(null),
```

**Step 4: Run test to verify it passes**

Run: `cd packages/typescript && npx vitest run core/tests/models.test.ts -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/typescript/core/
git commit -m "feat(core): add ResponseMode, StreamSummary, and stream field to TS models"
```

---

### Task 4: Python InvocationContext — emit_progress Method

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/types.py`
- Test: `packages/python/anip-service/tests/test_types.py`

**Step 1: Write the failing test**

Add to `packages/python/anip-service/tests/test_types.py`:

```python
import asyncio


def test_emit_progress_noop_without_sink():
    """emit_progress is a no-op when no progress sink is attached."""
    ctx = InvocationContext(
        token=None,  # type: ignore
        root_principal="human:alice@example.com",
        subject="agent:bot-1",
        scopes=["test.read"],
        delegation_chain=["tok-1"],
    )
    # Should not raise
    asyncio.run(ctx.emit_progress({"percent": 50}))


def test_emit_progress_calls_sink():
    """emit_progress forwards payload to attached sink."""
    received = []

    async def sink(payload):
        received.append(payload)

    ctx = InvocationContext(
        token=None,  # type: ignore
        root_principal="human:alice@example.com",
        subject="agent:bot-1",
        scopes=["test.read"],
        delegation_chain=["tok-1"],
        _progress_sink=sink,
    )
    asyncio.run(ctx.emit_progress({"percent": 50}))
    assert received == [{"percent": 50}]
```

**Step 2: Run test to verify it fails**

Run: `pytest packages/python/anip-service/tests/test_types.py -v -k "emit_progress"`
Expected: FAIL — `emit_progress` not found on InvocationContext

**Step 3: Write minimal implementation**

In `packages/python/anip-service/src/anip_service/types.py`, update `InvocationContext`:

Add import at top:

```python
from typing import Any, Awaitable, Callable
```

Add field after `_cost_actual` (line 20):

```python
    _progress_sink: Callable[[dict[str, Any]], Awaitable[None]] | None = field(default=None, repr=False)
```

Add method after `set_cost_actual` (after line 24):

```python
    async def emit_progress(self, payload: dict[str, Any]) -> None:
        """Emit a progress event. No-op if no sink is attached (unary mode)."""
        if self._progress_sink is not None:
            await self._progress_sink(payload)
```

**Step 4: Run test to verify it passes**

Run: `pytest packages/python/anip-service/tests/test_types.py -v`
Expected: PASS (all tests including new ones)

**Step 5: Commit**

```bash
git add packages/python/anip-service/
git commit -m "feat(service): add emit_progress to InvocationContext"
```

---

### Task 5: TypeScript InvocationContext — emitProgress Method

**Files:**
- Modify: `packages/typescript/service/src/types.ts`
- Test: `packages/typescript/service/tests/types.test.ts` (create)

**Step 1: Write the failing test**

Create `packages/typescript/service/tests/types.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import type { InvocationContext } from "../src/types.js";

describe("InvocationContext.emitProgress", () => {
  it("is a callable method on the interface", () => {
    // Type-level test: ensure emitProgress exists on the interface.
    // We construct a mock context to verify runtime behavior.
    const received: Record<string, unknown>[] = [];
    const ctx: InvocationContext = {
      token: {} as any,
      rootPrincipal: "human:alice",
      subject: "agent:bot",
      scopes: ["test"],
      delegationChain: ["tok-1"],
      invocationId: "inv-000000000000",
      clientReferenceId: null,
      setCostActual(_cost) {},
      async emitProgress(payload) {
        received.push(payload);
      },
    };

    expect(ctx.emitProgress).toBeDefined();
  });

  it("receives payloads when called", async () => {
    const received: Record<string, unknown>[] = [];
    const ctx: InvocationContext = {
      token: {} as any,
      rootPrincipal: "human:alice",
      subject: "agent:bot",
      scopes: ["test"],
      delegationChain: ["tok-1"],
      invocationId: "inv-000000000000",
      clientReferenceId: null,
      setCostActual(_cost) {},
      async emitProgress(payload) {
        received.push(payload);
      },
    };

    await ctx.emitProgress({ percent: 50 });
    expect(received).toEqual([{ percent: 50 }]);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd packages/typescript && npx vitest run service/tests/types.test.ts -v`
Expected: FAIL — `emitProgress` not on InvocationContext interface

**Step 3: Write minimal implementation**

In `packages/typescript/service/src/types.ts`, add to `InvocationContext` interface (after `setCostActual`, line 15):

```typescript
  /** Emit a progress event. No-op in unary mode. */
  emitProgress(payload: Record<string, unknown>): Promise<void>;
```

**Step 4: Run test to verify it passes**

Run: `cd packages/typescript && npx vitest run service/tests/types.test.ts -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/typescript/service/
git commit -m "feat(service): add emitProgress to TS InvocationContext interface"
```

---

### Task 6: Python ANIPService — Streaming Invocation Support

**Architecture note — true streaming, not buffered replay:**

The service layer does NOT buffer progress events and replay them after handler completion.
Instead, `invoke()` accepts an optional `_progress_sink` callable from the HTTP binding.
When the handler calls `ctx.emit_progress(payload)`, the payload flows immediately through
the sink to the SSE transport — the client receives each progress event in real time as
the handler produces it.

For the service-layer unit tests (no HTTP transport), progress events are collected via
a test sink to verify the handler called `emit_progress` correctly.

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Test: `packages/python/anip-service/tests/test_streaming.py` (create)

**Step 1: Write the failing test**

Create `packages/python/anip-service/tests/test_streaming.py`:

```python
import asyncio
import pytest
from anip_service import ANIPService, Capability, InvocationContext
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    SideEffect, SideEffectType, ResponseMode,
)


def _streaming_cap():
    async def handler(ctx: InvocationContext, params):
        await ctx.emit_progress({"step": 1, "message": "Starting"})
        await asyncio.sleep(0.01)  # simulate work
        await ctx.emit_progress({"step": 2, "message": "Processing"})
        return {"result": "done"}

    return Capability(
        declaration=CapabilityDeclaration(
            name="analyze",
            description="Long-running analysis",
            inputs=[CapabilityInput(name="target", type="string", required=True, description="target")],
            output=CapabilityOutput(type="object", fields=["result"]),
            side_effect=SideEffect(type=SideEffectType.READ),
            minimum_scope=["analyze"],
            response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
        ),
        handler=handler,
    )


def _unary_only_cap():
    return Capability(
        declaration=CapabilityDeclaration(
            name="greet",
            description="Say hello",
            inputs=[CapabilityInput(name="name", type="string", required=True, description="name")],
            output=CapabilityOutput(type="object", fields=["message"]),
            side_effect=SideEffect(type=SideEffectType.READ),
            minimum_scope=["greet"],
        ),
        handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
    )


@pytest.fixture
def service():
    return ANIPService(
        service_id="test-service",
        capabilities=[_streaming_cap(), _unary_only_cap()],
        storage=":memory:",
        authenticate=lambda bearer: "agent" if bearer == "key" else None,
    )


async def test_streaming_sink_called_during_handler(service):
    """Progress sink receives events in real time during handler execution."""
    received = []

    async def sink(payload):
        received.append(payload)

    token = await service.issue_token(
        issuer="test-service", subject="agent",
        scope=["analyze"], capability="analyze",
        authenticate_as="human:alice",
    )
    result = await service.invoke(
        "analyze", token, {"target": "x"},
        stream=True,
        _progress_sink=sink,
    )
    assert result["success"] is True
    assert result["result"] == {"result": "done"}
    # Verify sink was called with structured events (not raw payloads)
    assert len(received) == 2
    assert received[0]["payload"] == {"step": 1, "message": "Starting"}
    assert received[0]["invocation_id"].startswith("inv-")
    assert received[0]["client_reference_id"] is None
    assert received[1]["payload"] == {"step": 2, "message": "Processing"}
    # Verify stream_summary
    assert result["stream_summary"]["events_emitted"] == 2
    assert result["stream_summary"]["response_mode"] == "streaming"


async def test_unary_invocation_ignores_progress(service):
    """Unary invocation of a streaming-capable handler should work normally."""
    token = await service.issue_token(
        issuer="test-service", subject="agent",
        scope=["analyze"], capability="analyze",
        authenticate_as="human:alice",
    )
    result = await service.invoke("analyze", token, {"target": "x"})
    assert result["success"] is True
    assert result["result"] == {"result": "done"}
    assert "stream_summary" not in result


async def test_streaming_rejected_for_unary_only(service):
    """Streaming request for a unary-only capability should fail."""
    token = await service.issue_token(
        issuer="test-service", subject="agent",
        scope=["greet"], capability="greet",
        authenticate_as="human:alice",
    )
    result = await service.invoke(
        "greet", token, {"name": "world"},
        stream=True,
    )
    assert result["success"] is False
    assert result["failure"]["type"] == "streaming_not_supported"
```

**Step 2: Run test to verify it fails**

Run: `pytest packages/python/anip-service/tests/test_streaming.py -v`
Expected: FAIL — `invoke()` doesn't accept `stream` kwarg

**Step 3: Write minimal implementation**

In `packages/python/anip-service/src/anip_service/service.py`:

Add import at top (with existing imports):

```python
import time
from typing import Callable, Awaitable
from anip_core import ResponseMode
```

Add a public method for streaming validation by HTTP bindings (avoids reaching
into `_capabilities`). Add after the existing `discover_permissions` method:

```python
    def get_capability_declaration(self, capability_name: str) -> CapabilityDeclaration | None:
        """Return the capability declaration or None. Used by HTTP bindings for pre-validation."""
        cap = self._capabilities.get(capability_name)
        return cap.declaration if cap else None
```

Update `invoke()` signature (line 376-383) to accept `stream` and `_progress_sink`:

```python
    async def invoke(
        self,
        capability_name: str,
        token: DelegationToken,
        params: dict[str, Any],
        *,
        client_reference_id: str | None = None,
        stream: bool = False,
        _progress_sink: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
```

After the capability lookup and before delegation validation (after `decl = cap.declaration`), add streaming validation:

```python
        # Check streaming support
        if stream:
            response_modes = [m.value if hasattr(m, 'value') else m for m in (decl.response_modes or ["unary"])]
            if "streaming" not in response_modes:
                return {
                    "success": False,
                    "failure": {
                        "type": "streaming_not_supported",
                        "detail": f"Capability '{capability_name}' does not support streaming",
                    },
                    "invocation_id": invocation_id,
                    "client_reference_id": client_reference_id,
                }
```

When building the InvocationContext, wire up the progress sink that forwards to the caller's sink in real time:

```python
        # Set up progress tracking for streaming
        events_emitted = 0
        stream_start = time.monotonic() if stream else 0

        async def _internal_progress_sink(payload: dict[str, Any]) -> None:
            nonlocal events_emitted
            events_emitted += 1
            if _progress_sink is not None:
                await _progress_sink({
                    "invocation_id": invocation_id,
                    "client_reference_id": client_reference_id,
                    "payload": payload,
                })

        ctx = InvocationContext(
            token=resolved_token,
            root_principal=await self._engine.get_root_principal(resolved_token),
            subject=resolved_token.subject,
            scopes=resolved_token.scope or [],
            delegation_chain=[t.token_id for t in chain],
            invocation_id=invocation_id,
            client_reference_id=client_reference_id,
            _progress_sink=_internal_progress_sink if stream else None,
        )
```

After building the success response, add stream_summary if streaming:

```python
            if stream:
                response["stream_summary"] = {
                    "response_mode": "streaming",
                    "events_emitted": events_emitted,
                    "events_delivered": events_emitted,
                    "duration_ms": int((time.monotonic() - stream_start) * 1000),
                    "client_disconnected": False,
                }
```

**Step 4: Run test to verify it passes**

Run: `pytest packages/python/anip-service/tests/test_streaming.py -v`
Expected: PASS (3 tests)

**Step 5: Run all existing tests to verify no regressions**

Run: `pytest packages/python/ -x -q`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add packages/python/anip-service/
git commit -m "feat(service): add streaming invocation support to Python ANIPService"
```

---

### Task 7: TypeScript ANIPService — Streaming Invocation Support

**Architecture note — true streaming, not buffered replay:**

Like the Python service (Task 6), the TS service layer accepts an optional `progressSink`
callback from the HTTP binding. When the handler calls `ctx.emitProgress(payload)`, the
service wraps the payload with metadata (invocation_id, client_reference_id) and forwards
the structured event to the sink in real time. The HTTP binding wires its SSE transport
writer as the sink.

**Files:**
- Modify: `packages/typescript/service/src/service.ts`
- Test: `packages/typescript/service/tests/streaming.test.ts` (create)

**Step 1: Write the failing test**

Create `packages/typescript/service/tests/streaming.test.ts`:

```typescript
import { describe, it, expect, beforeAll } from "vitest";
import { createANIPService } from "../src/service.js";
import type { CapabilityDef, InvocationContext } from "../src/types.js";

function streamingCap(): CapabilityDef {
  return {
    declaration: {
      name: "analyze",
      description: "Long-running analysis",
      inputs: [{ name: "target", type: "string", required: true, description: "target" }],
      output: { type: "object", fields: ["result"] },
      side_effect: { type: "read" },
      minimum_scope: ["analyze"],
      response_modes: ["unary", "streaming"],
    } as any,
    async handler(ctx: InvocationContext, params) {
      await ctx.emitProgress({ step: 1, message: "Starting" });
      await ctx.emitProgress({ step: 2, message: "Processing" });
      return { result: "done" };
    },
  };
}

function unaryOnlyCap(): CapabilityDef {
  return {
    declaration: {
      name: "greet",
      description: "Say hello",
      inputs: [{ name: "name", type: "string", required: true, description: "name" }],
      output: { type: "object", fields: ["message"] },
      side_effect: { type: "read" },
      minimum_scope: ["greet"],
    } as any,
    handler(_ctx, params) {
      return { message: `Hello, ${params.name}!` };
    },
  };
}

describe("Streaming invocation", () => {
  let service: ReturnType<typeof createANIPService>;

  beforeAll(async () => {
    service = createANIPService({
      serviceId: "test-service",
      capabilities: [streamingCap(), unaryOnlyCap()],
      storage: ":memory:",
      authenticate: (bearer) => (bearer === "key" ? "agent" : null),
    });
    await service.start();
  });

  it("calls progressSink with structured events in real time", async () => {
    const received: Record<string, unknown>[] = [];
    const token = await service.issueToken({
      issuer: "test-service",
      subject: "agent",
      scope: ["analyze"],
      capability: "analyze",
      authenticateAs: "human:alice",
    });
    const result = await service.invoke("analyze", token, { target: "x" }, {
      stream: true,
      progressSink: async (event) => { received.push(event); },
    });
    expect(result.success).toBe(true);
    expect(result.result).toEqual({ result: "done" });
    // Verify sink received structured events (not raw payloads)
    expect(received).toHaveLength(2);
    expect(received[0].payload).toEqual({ step: 1, message: "Starting" });
    expect((received[0].invocation_id as string).startsWith("inv-")).toBe(true);
    expect(received[1].payload).toEqual({ step: 2, message: "Processing" });
    // Verify stream_summary
    expect(result.stream_summary).toBeDefined();
    expect(result.stream_summary.events_emitted).toBe(2);
    expect(result.stream_summary.response_mode).toBe("streaming");
  });

  it("ignores progress in unary mode", async () => {
    const token = await service.issueToken({
      issuer: "test-service",
      subject: "agent",
      scope: ["analyze"],
      capability: "analyze",
      authenticateAs: "human:alice",
    });
    const result = await service.invoke("analyze", token, { target: "x" });
    expect(result.success).toBe(true);
    expect(result.stream_summary).toBeUndefined();
  });

  it("rejects streaming for unary-only capabilities", async () => {
    const token = await service.issueToken({
      issuer: "test-service",
      subject: "agent",
      scope: ["greet"],
      capability: "greet",
      authenticateAs: "human:alice",
    });
    const result = await service.invoke("greet", token, { name: "world" }, {
      stream: true,
    });
    expect(result.success).toBe(false);
    expect(result.failure.type).toBe("streaming_not_supported");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd packages/typescript && npx vitest run service/tests/streaming.test.ts -v`
Expected: FAIL — `stream` not accepted by invoke opts

**Step 3: Write minimal implementation**

In `packages/typescript/service/src/service.ts`:

First, update the exported `ANIPService` **interface** (line 71-76) so the TS bindings
can pass the new options without a type error:

```typescript
  invoke(
    capabilityName: string,
    token: DelegationToken,
    params: Record<string, unknown>,
    opts?: {
      clientReferenceId?: string | null;
      stream?: boolean;
      progressSink?: (event: Record<string, unknown>) => Promise<void>;
    },
  ): Promise<Record<string, unknown>>;
```

Also add a public method to the interface for streaming validation by bindings:

```typescript
  getCapabilityDeclaration(
    capabilityName: string,
  ): Record<string, unknown> | null;
```

Then update the concrete `invoke()` implementation signature (around line 642-646)
to match the interface:

```typescript
    async invoke(
      capabilityName: string,
      token: DelegationToken,
      params: Record<string, unknown>,
      opts?: {
        clientReferenceId?: string | null;
        stream?: boolean;
        progressSink?: (event: Record<string, unknown>) => Promise<void>;
      },
    ): Promise<Record<string, unknown>> {
```

And add the `getCapabilityDeclaration` implementation (returns the parsed declaration
or null):

```typescript
    getCapabilityDeclaration(capabilityName: string): Record<string, unknown> | null {
      const cap = capabilities.get(capabilityName);
      return cap ? (cap.declaration as Record<string, unknown>) : null;
    },
```

After the capability lookup (after `const decl = cap.declaration;`), add streaming validation:

```typescript
      // Check streaming support
      const stream = opts?.stream ?? false;
      const progressSink = opts?.progressSink ?? null;
      if (stream) {
        const responseModes = decl.response_modes ?? ["unary"];
        if (!responseModes.includes("streaming")) {
          return {
            success: false,
            failure: {
              type: "streaming_not_supported",
              detail: `Capability '${capabilityName}' does not support streaming`,
            },
            invocation_id: invocationId,
            client_reference_id: clientReferenceId,
          };
        }
      }
```

When building the context (around line 703-714), wire up the progress sink that
forwards structured events to the caller's sink in real time:

```typescript
      let eventsEmitted = 0;
      const streamStart = stream ? performance.now() : 0;

      const ctx: InvocationContext = {
        token: resolvedToken,
        rootPrincipal: await engine.getRootPrincipal(resolvedToken),
        subject: resolvedToken.subject,
        scopes: resolvedToken.scope ?? [],
        delegationChain: chain.map((t) => t.token_id),
        invocationId,
        clientReferenceId,
        setCostActual(cost: Record<string, unknown>): void {
          costActual = cost;
        },
        async emitProgress(payload: Record<string, unknown>): Promise<void> {
          if (!stream) return; // no-op in unary mode
          eventsEmitted++;
          if (progressSink) {
            await progressSink({
              invocation_id: invocationId,
              client_reference_id: clientReferenceId,
              payload,
            });
          }
        },
      };
```

After building the success response, add stream_summary if streaming:

```typescript
        if (stream) {
          response.stream_summary = {
            response_mode: "streaming",
            events_emitted: eventsEmitted,
            events_delivered: eventsEmitted,
            duration_ms: Math.round(performance.now() - streamStart),
            client_disconnected: false,
          };
        }
```

**Step 4: Run test to verify it passes**

Run: `cd packages/typescript && npx vitest run service/tests/streaming.test.ts -v`
Expected: PASS (3 tests)

**Step 5: Run all existing TS tests to verify no regressions**

Run: `cd packages/typescript && npx vitest run -v`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
git add packages/typescript/service/
git commit -m "feat(service): add streaming invocation support to TS ANIPService"
```

---

### Task 8: FastAPI SSE Binding — True Real-Time Streaming

**Architecture note — asyncio.Queue bridges handler and SSE transport:**

The FastAPI route wires an `asyncio.Queue` as the bridge between the service layer's
progress sink and the SSE generator. `service.invoke()` runs in a concurrent
`asyncio.Task`. When the handler calls `ctx.emit_progress(payload)`, the service's
internal sink puts a structured event onto the queue. The SSE generator reads from the
queue and yields `event: progress` lines to the client **in real time** — the client
receives each progress event as the handler produces it, not after handler completion.

**Files:**
- Modify: `packages/python/anip-fastapi/src/anip_fastapi/routes.py`
- Test: `packages/python/anip-fastapi/tests/test_routes.py`

**Step 1: Write the failing test**

Add to `packages/python/anip-fastapi/tests/test_routes.py`:

```python
def _streaming_cap():
    async def handler(ctx, params):
        await ctx.emit_progress({"step": 1, "status": "working"})
        return {"answer": 42}

    return Capability(
        declaration=CapabilityDeclaration(
            name="analyze",
            description="Analyze something",
            contract_version="1.0",
            inputs=[CapabilityInput(name="x", type="string", required=True, description="input")],
            output=CapabilityOutput(type="object", fields=["answer"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["analyze"],
            response_modes=["unary", "streaming"],
        ),
        handler=handler,
    )


@pytest.fixture
def streaming_client():
    from anip_core import ResponseMode
    service = ANIPService(
        service_id="test-service",
        capabilities=[_greet_cap(), _streaming_cap()],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )
    app = FastAPI()
    mount_anip(app, service)
    return TestClient(app)


class TestStreamingRoutes:
    def test_streaming_returns_sse(self, streaming_client):
        """POST with stream:true should return text/event-stream."""
        # First issue a token
        resp = streaming_client.post(
            "/anip/tokens",
            json={"subject": "test-agent", "scope": ["analyze"], "capability": "analyze"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert resp.status_code == 200
        jwt_str = resp.json()["token"]

        # Invoke with stream: true
        resp = streaming_client.post(
            "/anip/invoke/analyze",
            json={"parameters": {"x": "test"}, "stream": True},
            headers={"Authorization": f"Bearer {jwt_str}"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        assert "event: progress" in body
        assert "event: completed" in body
        assert '"answer": 42' in body or '"answer":42' in body

    def test_streaming_rejected_for_unary_cap(self, streaming_client):
        """stream:true on a unary-only capability should fail."""
        resp = streaming_client.post(
            "/anip/tokens",
            json={"subject": "test-agent", "scope": ["greet"], "capability": "greet"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        jwt_str = resp.json()["token"]

        resp = streaming_client.post(
            "/anip/invoke/greet",
            json={"parameters": {"name": "world"}, "stream": True},
            headers={"Authorization": f"Bearer {jwt_str}"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["failure"]["type"] == "streaming_not_supported"
```

**Step 2: Run test to verify it fails**

Run: `pytest packages/python/anip-fastapi/tests/test_routes.py -v -k "Streaming"`
Expected: FAIL — streaming route logic not implemented

**Step 3: Write minimal implementation**

In `packages/python/anip-fastapi/src/anip_fastapi/routes.py`:

Add import at top:

```python
import json
from datetime import datetime, timezone
from fastapi.responses import StreamingResponse
```

Replace the invoke route handler (lines 84-102) with:

```python
    @app.post(f"{prefix}/anip/invoke/{{capability}}")
    async def invoke(capability: str, request: Request):
        token = await _resolve_token(request, service)
        if token is None:
            return JSONResponse({"error": "Authentication required"}, status_code=401)

        body = await request.json()
        params = body.get("parameters", body)
        client_reference_id = body.get("client_reference_id")
        stream = body.get("stream", False)

        if not stream:
            # Unary mode — existing behavior
            result = await service.invoke(
                capability, token, params,
                client_reference_id=client_reference_id,
            )
            if not result.get("success"):
                status = _failure_status(result.get("failure", {}).get("type"))
                return JSONResponse(result, status_code=status)
            return result

        # Streaming mode — pre-validate streaming support (return JSON 400, not SSE)
        decl = service.get_capability_declaration(capability)
        if decl is not None:
            modes = [m.value if hasattr(m, 'value') else m
                     for m in (decl.response_modes or ["unary"])]
            if "streaming" not in modes:
                result = await service.invoke(
                    capability, token, params,
                    client_reference_id=client_reference_id,
                    stream=True,
                )
                status = _failure_status(result.get("failure", {}).get("type"))
                return JSONResponse(result, status_code=status)

        # True streaming: asyncio.Queue bridges sink → SSE generator.
        # service.invoke() runs in a concurrent asyncio.Task.  When the
        # handler calls ctx.emit_progress(), the internal sink puts a
        # structured event onto the queue.  The SSE generator reads from
        # the queue and yields SSE lines in real time.
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def progress_sink(event: dict) -> None:
            """Called by service layer with structured events during handler execution."""
            await queue.put({"type": "progress", **event})

        async def run_invoke():
            try:
                result = await service.invoke(
                    capability, token, params,
                    client_reference_id=client_reference_id,
                    stream=True,
                    _progress_sink=progress_sink,
                )
                await queue.put({"type": "terminal", "result": result})
            except Exception as e:
                await queue.put({"type": "error", "detail": str(e)})

        async def sse_generator():
            task = asyncio.create_task(run_invoke())
            try:
                while True:
                    event = await queue.get()
                    ts = datetime.now(timezone.utc).isoformat()

                    if event["type"] == "progress":
                        event_data = {
                            "invocation_id": event["invocation_id"],
                            "client_reference_id": event.get("client_reference_id"),
                            "timestamp": ts,
                            "payload": event["payload"],
                        }
                        yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"

                    elif event["type"] == "terminal":
                        result = event["result"]
                        if result.get("success"):
                            event_data = {
                                "invocation_id": result["invocation_id"],
                                "client_reference_id": result.get("client_reference_id"),
                                "timestamp": ts,
                                "success": True,
                                "result": result.get("result"),
                                "cost_actual": result.get("cost_actual"),
                            }
                            if "stream_summary" in result:
                                event_data["stream_summary"] = result["stream_summary"]
                            yield f"event: completed\ndata: {json.dumps(event_data)}\n\n"
                        else:
                            event_data = {
                                "invocation_id": result.get("invocation_id"),
                                "client_reference_id": result.get("client_reference_id"),
                                "timestamp": ts,
                                "success": False,
                                "failure": result.get("failure"),
                            }
                            if "stream_summary" in result:
                                event_data["stream_summary"] = result["stream_summary"]
                            yield f"event: failed\ndata: {json.dumps(event_data)}\n\n"
                        break

                    elif event["type"] == "error":
                        event_data = {
                            "timestamp": ts,
                            "success": False,
                            "failure": {"type": "internal_error", "detail": event["detail"]},
                        }
                        yield f"event: failed\ndata: {json.dumps(event_data)}\n\n"
                        break
            finally:
                await task

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest packages/python/anip-fastapi/tests/test_routes.py -v`
Expected: PASS (all tests including new streaming ones)

**Step 5: Commit**

```bash
git add packages/python/anip-fastapi/ packages/python/anip-service/
git commit -m "feat(fastapi): add SSE streaming support to invoke route"
```

---

### Task 9: Hono SSE Binding — True Real-Time Streaming

**Architecture note — TransformStream bridges sink → SSE response:**

Hono returns `Response` objects (Web API). To stream SSE events in real time, we create a
`TransformStream`, wire the writable side as the progress sink, and return the readable
side as the response body. `service.invoke()` runs as a floating promise; each
`emitProgress` call writes an SSE line to the stream immediately.

**Files:**
- Modify: `packages/typescript/hono/src/routes.ts`
- Test: `packages/typescript/hono/tests/routes.test.ts`

**Step 1: Write the failing test**

Add to `packages/typescript/hono/tests/routes.test.ts` (follow existing test patterns).
Requires a streaming-capable capability registered in the test service with
`response_modes: ["unary", "streaming"]` and a handler that calls `ctx.emitProgress()`.
Read the existing test file to match its fixture/setup pattern before writing tests for:
- `stream: true` returns `text/event-stream` with progress + completed events
- `stream: true` on unary-only capability returns 400 JSON error

**Step 2: Implement SSE in the Hono invoke route**

In `packages/typescript/hono/src/routes.ts`, update the invoke handler (lines 53-68).

When `body.stream === true`:

```typescript
if (body.stream) {
  // Pre-validate streaming support (return JSON 400, not SSE)
  const decl = service.getCapabilityDeclaration(capability);
  const modes = decl?.response_modes ?? ["unary"];
  if (!modes.includes("streaming")) {
    const result = await service.invoke(capability, token, params, {
      clientReferenceId, stream: true,
    });
    const failure = result.failure as Record<string, unknown>;
    return c.json(result, failureStatus(failure?.type as string));
  }

  // True streaming: TransformStream bridges sink → Response body
  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();
  const encoder = new TextEncoder();

  // Run invoke in background — progress sink writes SSE events in real time
  (async () => {
    try {
      const result = await service.invoke(capability, token, params, {
        clientReferenceId,
        stream: true,
        progressSink: async (event) => {
          const eventData = { ...event, timestamp: new Date().toISOString() };
          await writer.write(
            encoder.encode(`event: progress\ndata: ${JSON.stringify(eventData)}\n\n`),
          );
        },
      });

      // Write terminal event
      const ts = new Date().toISOString();
      const terminalType = result.success ? "completed" : "failed";
      const terminalData = {
        invocation_id: result.invocation_id,
        client_reference_id: result.client_reference_id,
        timestamp: ts,
        success: result.success,
        ...(result.success
          ? { result: result.result, cost_actual: result.cost_actual }
          : { failure: result.failure }),
        ...(result.stream_summary ? { stream_summary: result.stream_summary } : {}),
      };
      await writer.write(
        encoder.encode(`event: ${terminalType}\ndata: ${JSON.stringify(terminalData)}\n\n`),
      );
      await writer.close();
    } catch (err) {
      const errorData = {
        timestamp: new Date().toISOString(),
        success: false,
        failure: { type: "internal_error", detail: String(err) },
      };
      await writer.write(
        encoder.encode(`event: failed\ndata: ${JSON.stringify(errorData)}\n\n`),
      );
      await writer.close();
    }
  })();

  return new Response(readable, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    },
  });
}
```

**Step 3: Run tests**

Run: `cd packages/typescript && npx vitest run hono/tests/routes.test.ts -v`
Expected: PASS

**Step 4: Commit**

```bash
git add packages/typescript/hono/
git commit -m "feat(hono): add true SSE streaming support to invoke route"
```

---

### Task 10: Express SSE Binding — True Real-Time Streaming

**Architecture note — res.write() as the progress sink:**

Express gives us a Node.js `ServerResponse`. We set SSE headers, then pass a
progress sink to `service.invoke()`. Each `emitProgress` call during handler execution
triggers `res.write()` — the client receives the SSE event immediately. After `invoke()`
returns, we write the terminal event and call `res.end()`.

**Files:**
- Modify: `packages/typescript/express/src/routes.ts`
- Test: `packages/typescript/express/tests/routes.test.ts`

**Step 1: Write the failing test**

Add to `packages/typescript/express/tests/routes.test.ts` (follow existing patterns).
Read the existing test file to match its fixture/setup pattern, then add tests for:
- `stream: true` returns `text/event-stream` with progress + completed events
- `stream: true` on unary-only capability returns 400 JSON error

**Step 2: Implement SSE in the Express invoke route**

In `packages/typescript/express/src/routes.ts`, update the invoke handler (lines 58-75).

When `body.stream === true`:

```typescript
if (body.stream) {
  // Pre-validate streaming support (return JSON 400, not SSE)
  const decl = service.getCapabilityDeclaration(req.params.capability);
  const modes = decl?.response_modes ?? ["unary"];
  if (!modes.includes("streaming")) {
    const result = await service.invoke(req.params.capability, token, params, {
      clientReferenceId, stream: true,
    });
    const failure = result.failure as Record<string, unknown>;
    res.status(failureStatus(failure?.type as string)).json(result);
    return;
  }

  // True streaming: res.write() as progress sink
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
  });

  const result = await service.invoke(req.params.capability, token, params, {
    clientReferenceId,
    stream: true,
    progressSink: async (event) => {
      const eventData = { ...event, timestamp: new Date().toISOString() };
      res.write(`event: progress\ndata: ${JSON.stringify(eventData)}\n\n`);
    },
  });

  // Write terminal event
  const ts = new Date().toISOString();
  const terminalType = result.success ? "completed" : "failed";
  const terminalData = {
    invocation_id: result.invocation_id,
    client_reference_id: result.client_reference_id,
    timestamp: ts,
    success: result.success,
    ...(result.success
      ? { result: result.result, cost_actual: result.cost_actual }
      : { failure: result.failure }),
    ...(result.stream_summary ? { stream_summary: result.stream_summary } : {}),
  };
  res.write(`event: ${terminalType}\ndata: ${JSON.stringify(terminalData)}\n\n`);
  res.end();
  return;
}
```

**Step 3: Run tests**

Run: `cd packages/typescript && npx vitest run express/tests/routes.test.ts -v`
Expected: PASS

**Step 4: Commit**

```bash
git add packages/typescript/express/
git commit -m "feat(express): add true SSE streaming support to invoke route"
```

---

### Task 11: Fastify SSE Binding — True Real-Time Streaming

**Architecture note — reply.raw.write() as the progress sink:**

Same pattern as Express but using Fastify's `reply.raw` to access the underlying
Node.js `ServerResponse`. SSE headers are set via `reply.raw.writeHead()`, and
progress events are written via `reply.raw.write()` during handler execution.
After writing the terminal event, call `reply.hijack()` to tell Fastify we've
taken over the response.

**Files:**
- Modify: `packages/typescript/fastify/src/routes.ts`
- Test: `packages/typescript/fastify/tests/routes.test.ts`

**Step 1: Write the failing test**

Add to `packages/typescript/fastify/tests/routes.test.ts` (follow existing patterns).
Read the existing test file to match its fixture/setup pattern, then add tests for:
- `stream: true` returns `text/event-stream` with progress + completed events
- `stream: true` on unary-only capability returns 400 JSON error

**Step 2: Implement SSE in the Fastify invoke route**

In `packages/typescript/fastify/src/routes.ts`, update the invoke handler (lines 50-67).

When `body.stream === true`:

```typescript
if ((body as Record<string, unknown>).stream) {
  // Pre-validate streaming support (return JSON 400, not SSE)
  const decl = service.getCapabilityDeclaration(req.params.capability);
  const modes = decl?.response_modes ?? ["unary"];
  if (!modes.includes("streaming")) {
    const result = await service.invoke(req.params.capability, token, params, {
      clientReferenceId, stream: true,
    });
    const failure = result.failure as Record<string, unknown>;
    return reply.status(failureStatus(failure?.type as string)).send(result);
  }

  // True streaming: reply.raw.write() as progress sink
  reply.raw.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
  });

  const result = await service.invoke(req.params.capability, token, params, {
    clientReferenceId,
    stream: true,
    progressSink: async (event) => {
      const eventData = { ...event, timestamp: new Date().toISOString() };
      reply.raw.write(`event: progress\ndata: ${JSON.stringify(eventData)}\n\n`);
    },
  });

  // Write terminal event
  const ts = new Date().toISOString();
  const terminalType = result.success ? "completed" : "failed";
  const terminalData = {
    invocation_id: result.invocation_id,
    client_reference_id: result.client_reference_id,
    timestamp: ts,
    success: result.success,
    ...(result.success
      ? { result: result.result, cost_actual: result.cost_actual }
      : { failure: result.failure }),
    ...(result.stream_summary ? { stream_summary: result.stream_summary } : {}),
  };
  reply.raw.write(`event: ${terminalType}\ndata: ${JSON.stringify(terminalData)}\n\n`);
  reply.raw.end();
  reply.hijack();  // Tell Fastify we've taken over the response
  return;
}
```

**Step 3: Run tests**

Run: `cd packages/typescript && npx vitest run fastify/tests/routes.test.ts -v`
Expected: PASS

**Step 4: Commit**

```bash
git add packages/typescript/fastify/
git commit -m "feat(fastify): add true SSE streaming support to invoke route"
```

---

### Task 12: Audit & Storage — stream_summary Persistence

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/audit.py`
- Modify: `packages/typescript/server/src/audit.ts`
- Modify: `packages/typescript/server/src/sqlite-worker.ts`
- Modify: `packages/python/anip-service/src/anip_service/service.py` (pass stream_summary to audit)
- Modify: `packages/typescript/service/src/service.ts` (pass stream_summary to audit)
- Test: existing audit test suites

**Step 1: Write the failing test**

Add to the existing audit test files:

Python (`packages/python/anip-server/tests/test_audit.py`):

```python
async def test_audit_entry_includes_stream_summary(audit_log):
    """Audit entries should persist stream_summary when provided."""
    await audit_log.log_entry({
        "capability": "analyze",
        "token_id": "tok-1",
        "root_principal": "human:alice",
        "success": True,
        "invocation_id": "inv-000000000001",
        "stream_summary": {
            "response_mode": "streaming",
            "events_emitted": 5,
            "events_delivered": 3,
            "duration_ms": 1200,
            "client_disconnected": True,
        },
    })
    entries = await audit_log.query_entries()
    assert entries[0]["stream_summary"]["events_emitted"] == 5
    assert entries[0]["stream_summary"]["client_disconnected"] is True
```

TypeScript (`packages/typescript/server/tests/audit.test.ts`):

```typescript
it("persists stream_summary in audit entry", async () => {
  await auditLog.logEntry({
    capability: "analyze",
    tokenId: "tok-1",
    rootPrincipal: "human:alice",
    success: true,
    invocationId: "inv-000000000001",
    streamSummary: {
      response_mode: "streaming",
      events_emitted: 5,
      events_delivered: 3,
      duration_ms: 1200,
      client_disconnected: true,
    },
  });
  const entries = await auditLog.queryEntries();
  expect(entries[0].stream_summary.events_emitted).toBe(5);
  expect(entries[0].stream_summary.client_disconnected).toBe(true);
});
```

**Step 2: Run tests to verify they fail**

```bash
pytest packages/python/anip-server/tests/test_audit.py -v -k "stream_summary"
cd packages/typescript && npx vitest run server/tests/audit.test.ts -v
```

Expected: FAIL — stream_summary not persisted/returned

**Step 3: Implement audit layer changes**

In `packages/python/anip-server/src/anip_server/audit.py`, update `log_entry()` (line 46-63)
to include `stream_summary` in the entry dict:

```python
        "stream_summary": entry_data.get("stream_summary"),
```

In `packages/typescript/server/src/audit.ts`, update the entry construction (line 51-67)
to include `stream_summary`:

```typescript
      stream_summary: entryData.streamSummary ?? null,
```

In `packages/typescript/server/src/sqlite-worker.ts`:

1. Add `"stream_summary"` to `JSON_AUDIT_FIELDS` array (line 19-24):
   ```typescript
   const JSON_AUDIT_FIELDS = [
     "parameters",
     "result_summary",
     "cost_actual",
     "delegation_chain",
     "stream_summary",
   ] as const;
   ```

2. Add `stream_summary TEXT` column to the `audit_log` CREATE TABLE statement.

3. Add `stream_summary` to the INSERT statement in the `storeAuditEntry` handler (lines 146-177).

**Step 4: Wire service layer to pass stream_summary to audit**

In `packages/python/anip-service/src/anip_service/service.py`, update the audit call
after building the success response to include `stream_summary` when streaming:

```python
        audit_data = {
            "success": True,
            "result_summary": self._summarize_result(handler_result),
            "cost_actual": cost_actual,
            "invocation_id": invocation_id,
            "client_reference_id": client_reference_id,
        }
        if stream:
            audit_data["stream_summary"] = response["stream_summary"]
```

In `packages/typescript/service/src/service.ts`, update the `logAudit()` call after
building the success response to include `streamSummary` when streaming:

```typescript
      await logAudit(capabilityName, resolvedToken, {
        success: true,
        resultSummary: summarizeResult(result),
        costActual,
        invocationId,
        clientReferenceId,
        ...(stream ? { streamSummary: response.stream_summary } : {}),
      });
```

**Step 5: Run tests**

```bash
pytest packages/python/anip-server/tests/ -v
cd packages/typescript && npx vitest run server/tests/ -v
```

Expected: PASS (all tests including new stream_summary ones)

**Step 6: Commit**

```bash
git add packages/python/anip-server/ packages/python/anip-service/ packages/typescript/server/ packages/typescript/service/
git commit -m "feat(audit): persist stream_summary in audit entries and storage"
```

---

### Task 13: JSON Schema Updates

**Files:**
- Modify: `schema/anip.schema.json`
- Modify: `schema/types/CapabilityDeclaration.json`
- Modify: `schema/types/InvokeRequest.json`
- Modify: `schema/types/InvokeResponse.json`

**Step 1: Update root schema**

In `schema/anip.schema.json`, add to `$defs`:

```json
"ResponseMode": {
  "enum": ["unary", "streaming"],
  "type": "string"
},
"StreamSummary": {
  "type": "object",
  "properties": {
    "response_mode": { "const": "streaming" },
    "events_emitted": { "type": "integer", "minimum": 0 },
    "events_delivered": { "type": "integer", "minimum": 0 },
    "duration_ms": { "type": "integer", "minimum": 0 },
    "client_disconnected": { "type": "boolean" }
  },
  "required": ["response_mode", "events_emitted", "events_delivered", "duration_ms", "client_disconnected"]
}
```

**Step 2: Update per-type schemas**

In `schema/types/CapabilityDeclaration.json`, add to `properties`:

```json
"response_modes": {
  "type": "array",
  "items": { "$ref": "#/$defs/ResponseMode" },
  "minItems": 1,
  "uniqueItems": true,
  "default": ["unary"]
}
```

And add `ResponseMode` to `$defs` (or reference from root schema).

In `schema/types/InvokeRequest.json`, add to `properties`:

```json
"stream": { "type": "boolean", "default": false }
```

In `schema/types/InvokeResponse.json`, add to `properties`:

```json
"stream_summary": { "$ref": "#/$defs/StreamSummary" }
```

And add `StreamSummary` to `$defs` (or reference from root schema).

**Step 3: Commit**

```bash
git add schema/
git commit -m "feat(schema): add ResponseMode, StreamSummary, stream field to all JSON schemas"
```

---

### Task 14: Version Bump to 0.6.0

**Files (28 version references across 13 files):**

**Python packages — version field:**
- `packages/python/anip-core/pyproject.toml` line 3: `version = "0.5.0"` → `"0.6.0"`
- `packages/python/anip-crypto/pyproject.toml` line 3: `version = "0.5.0"` → `"0.6.0"`
- `packages/python/anip-server/pyproject.toml` line 3: `version = "0.5.0"` → `"0.6.0"`
- `packages/python/anip-service/pyproject.toml` line 3: `version = "0.5.0"` → `"0.6.0"`
- `packages/python/anip-fastapi/pyproject.toml` line 3: `version = "0.5.0"` → `"0.6.0"`

**Python packages — cross-package dependencies:**
- `packages/python/anip-crypto/pyproject.toml` line 7: `anip-core>=0.5.0` → `>=0.6.0`
- `packages/python/anip-server/pyproject.toml` line 7: `anip-core>=0.5.0` → `>=0.6.0`
- `packages/python/anip-server/pyproject.toml` line 8: `anip-crypto>=0.5.0` → `>=0.6.0`
- `packages/python/anip-service/pyproject.toml` line 7: `anip-core>=0.5.0` → `>=0.6.0`
- `packages/python/anip-service/pyproject.toml` line 8: `anip-crypto>=0.5.0` → `>=0.6.0`
- `packages/python/anip-service/pyproject.toml` line 9: `anip-server>=0.5.0` → `>=0.6.0`
- `packages/python/anip-fastapi/pyproject.toml` line 7: `anip-service>=0.5.0` → `>=0.6.0`

**TypeScript packages — version field:**
- `packages/typescript/core/package.json` line 3: `"version": "0.5.0"` → `"0.6.0"`
- `packages/typescript/crypto/package.json` line 3: `"version": "0.5.0"` → `"0.6.0"`
- `packages/typescript/server/package.json` line 3: `"version": "0.5.0"` → `"0.6.0"`
- `packages/typescript/service/package.json` line 3: `"version": "0.5.0"` → `"0.6.0"`
- `packages/typescript/hono/package.json` line 3: `"version": "0.5.0"` → `"0.6.0"`
- `packages/typescript/express/package.json` line 3: `"version": "0.5.0"` → `"0.6.0"`
- `packages/typescript/fastify/package.json` line 3: `"version": "0.5.0"` → `"0.6.0"`

**TypeScript packages — cross-package dependencies:**
- `packages/typescript/crypto/package.json` line 16: `"@anip-dev/core": "0.5.0"` → `"0.6.0"`
- `packages/typescript/server/package.json` line 16: `"@anip-dev/core": "0.5.0"` → `"0.6.0"`
- `packages/typescript/server/package.json` line 17: `"@anip-dev/crypto": "0.5.0"` → `"0.6.0"`
- `packages/typescript/service/package.json` line 16: `"@anip-dev/core": "0.5.0"` → `"0.6.0"`
- `packages/typescript/service/package.json` line 17: `"@anip-dev/crypto": "0.5.0"` → `"0.6.0"`
- `packages/typescript/service/package.json` line 18: `"@anip-dev/server": "0.5.0"` → `"0.6.0"`
- `packages/typescript/express/package.json` line 16: `"@anip-dev/service": "0.5.0"` → `"0.6.0"`
- `packages/typescript/fastify/package.json` line 16: `"@anip-dev/service": "0.5.0"` → `"0.6.0"`
- `packages/typescript/hono/package.json` line 16: `"@anip-dev/service": "0.5.0"` → `"0.6.0"`

**Example app:**
- `examples/anip-ts/package.json` line 3: `"version": "0.5.0"` → `"0.6.0"`

**Step 1: Replace all 0.5.0 version strings**

Use find-and-replace across all files listed above. The simplest approach: replace `0.5.0` → `0.6.0` in each file. Every `0.5.0` in these files is a version reference.

**Step 2: Reinstall TS dependencies**

```bash
cd packages/typescript && npm install
```

This updates the lockfile to reflect the new cross-package versions.

**Step 3: Run all tests**

```bash
pytest packages/python/ -x -q
cd packages/typescript && npx vitest run
```

Expected: All tests pass

**Step 4: Commit**

```bash
git add packages/ examples/
git commit -m "chore: bump all 12 packages to v0.6.0"
```

---

### Task 15: Full Integration Test

**Files:**
- Run all Python tests
- Run all TypeScript tests
- Run example app tests

**Step 1: Run full test suites**

```bash
pytest packages/python/ -x -v
cd packages/typescript && npx vitest run -v
pytest examples/anip/tests/ -v
```

Expected: All pass with no regressions.

**Step 2: Verify streaming works end-to-end**

Review that:
- A capability declaring `response_modes: ["unary", "streaming"]` appears correctly in the manifest
- `stream: true` invocation returns SSE with progress + completed events
- `stream: true` on unary-only capability returns structured error
- Audit log entry for streaming invocation includes `stream_summary`
- Unary invocations are completely unchanged

---

## Task Dependency Graph

```
Task 1 (Py core models) ─────┐
                              ├─→ Task 4 (Py ctx) ─→ Task 6 (Py service) ─→ Task 8 (FastAPI SSE)
Task 2 (Py core StreamSummary)┘

Task 3 (TS core models) ──────→ Task 5 (TS ctx) ─→ Task 7 (TS service) ─┬→ Task 9 (Hono SSE)
                                                                         ├→ Task 10 (Express SSE)
                                                                         └→ Task 11 (Fastify SSE)

Task 6 + Task 7 ──────────→ Task 12 (audit/storage stream_summary)

Task 13 (JSON schema) ── independent
Task 14 (version bump) ── after all other tasks
Task 15 (integration) ── final verification
```

Tasks 1-2 and Task 3 can run in parallel (Python and TypeScript core models are independent).
Tasks 9, 10, 11 can run in parallel (independent HTTP bindings).
Task 12 (audit) depends on Tasks 6 and 7 (needs stream_summary from service layer).
Task 13 (schema) is independent and can run in parallel with Tasks 8-12.
