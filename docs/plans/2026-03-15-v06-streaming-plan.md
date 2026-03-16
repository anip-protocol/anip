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

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Test: `packages/python/anip-service/tests/test_streaming.py` (create)

**Step 1: Write the failing test**

Create `packages/python/anip-service/tests/test_streaming.py`:

```python
import pytest
from anip_service import ANIPService, Capability, InvocationContext
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    SideEffect, SideEffectType, ResponseMode,
)


def _streaming_cap():
    async def handler(ctx: InvocationContext, params):
        await ctx.emit_progress({"step": 1, "message": "Starting"})
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


async def test_streaming_invocation_collects_progress(service):
    """Streaming invocation should collect progress events and return them."""
    token = await service.issue_token(
        issuer="test-service", subject="agent",
        scope=["analyze"], capability="analyze",
        authenticate_as="human:alice",
    )
    result = await service.invoke(
        "analyze", token, {"target": "x"},
        stream=True,
    )
    assert result["success"] is True
    assert result["result"] == {"result": "done"}
    assert result["stream_summary"] is not None
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
from anip_core import ResponseMode
```

Update `invoke()` signature (line 376-383) to accept `stream`:

```python
    async def invoke(
        self,
        capability_name: str,
        token: DelegationToken,
        params: dict[str, Any],
        *,
        client_reference_id: str | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
```

After the capability lookup and before delegation validation (after line 409, after `decl = cap.declaration`), add streaming validation:

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

When building the InvocationContext (around line 442-450), wire up the progress sink:

```python
        # Set up progress sink for streaming
        progress_events: list[dict[str, Any]] = []
        stream_start = time.monotonic()

        async def _progress_sink(payload: dict[str, Any]) -> None:
            progress_events.append(payload)

        ctx = InvocationContext(
            token=resolved_token,
            root_principal=await self._engine.get_root_principal(resolved_token),
            subject=resolved_token.subject,
            scopes=resolved_token.scope or [],
            delegation_chain=[t.token_id for t in chain],
            invocation_id=invocation_id,
            client_reference_id=client_reference_id,
            _progress_sink=_progress_sink if stream else None,
        )
```

After building the success response (around line 519-529), add stream_summary if streaming:

```python
            if stream:
                response["stream_summary"] = {
                    "response_mode": "streaming",
                    "events_emitted": len(progress_events),
                    "events_delivered": len(progress_events),
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

  it("collects progress events and returns stream_summary", async () => {
    const token = await service.issueToken({
      issuer: "test-service",
      subject: "agent",
      scope: ["analyze"],
      capability: "analyze",
      authenticateAs: "human:alice",
    });
    const result = await service.invoke("analyze", token, { target: "x" }, {
      stream: true,
    });
    expect(result.success).toBe(true);
    expect(result.result).toEqual({ result: "done" });
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

Update the `invoke()` method signature (around line 642-646) to accept `stream`:

```typescript
    async invoke(
      capabilityName: string,
      token: DelegationToken,
      params: Record<string, unknown>,
      opts?: { clientReferenceId?: string | null; stream?: boolean },
    ): Promise<Record<string, unknown>> {
```

After the capability lookup (after line 665), add streaming validation:

```typescript
      // Check streaming support
      const stream = opts?.stream ?? false;
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

When building the context (around line 703-714), wire up progress:

```typescript
      const progressEvents: Record<string, unknown>[] = [];
      const streamStart = performance.now();

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
          if (stream) {
            progressEvents.push(payload);
          }
        },
      };
```

After building the success response (around line 730-740), add stream_summary:

```typescript
        if (stream) {
          response.stream_summary = {
            response_mode: "streaming",
            events_emitted: progressEvents.length,
            events_delivered: progressEvents.length,
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

### Task 8: FastAPI SSE Binding

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

        # Streaming mode — SSE response
        # First check if streaming is even valid (non-streaming invocation to get error)
        # We use stream=True to get stream_summary or streaming_not_supported error
        invocation_id = None
        progress_events: list[dict] = []

        async def sse_generator():
            nonlocal invocation_id

            # Wire a real progress sink that yields SSE events
            collected_progress: list[dict] = []

            result = await service.invoke(
                capability, token, params,
                client_reference_id=client_reference_id,
                stream=True,
                _progress_callback=lambda payload: collected_progress.append(payload),
            )

            invocation_id = result.get("invocation_id")

            # If the invocation failed before streaming started (e.g. streaming_not_supported),
            # emit a single failed event
            if not result.get("success"):
                event_data = {
                    "invocation_id": result.get("invocation_id"),
                    "client_reference_id": client_reference_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "success": False,
                    "failure": result["failure"],
                }
                if "stream_summary" in result:
                    event_data["stream_summary"] = result["stream_summary"]
                yield f"event: failed\ndata: {json.dumps(event_data)}\n\n"
                return

            # Emit collected progress events
            for payload in collected_progress:
                event_data = {
                    "invocation_id": result["invocation_id"],
                    "client_reference_id": client_reference_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": payload,
                }
                yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"

            # Emit completed event
            event_data = {
                "invocation_id": result["invocation_id"],
                "client_reference_id": client_reference_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": True,
                "result": result.get("result"),
                "cost_actual": result.get("cost_actual"),
            }
            if "stream_summary" in result:
                event_data["stream_summary"] = result["stream_summary"]
            yield f"event: completed\ndata: {json.dumps(event_data)}\n\n"

        # For streaming_not_supported, we need to detect and return JSON instead
        # Quick validation: check capability's response_modes before starting SSE
        if capability in service._capabilities:
            cap = service._capabilities[capability]
            modes = [m.value if hasattr(m, 'value') else m for m in (cap.declaration.response_modes or ["unary"])]
            if "streaming" not in modes:
                result = await service.invoke(
                    capability, token, params,
                    client_reference_id=client_reference_id,
                    stream=True,
                )
                status = _failure_status(result.get("failure", {}).get("type"))
                return JSONResponse(result, status_code=status)

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
```

Also update `service.invoke()` in `service.py` to accept an optional `_progress_callback` parameter. Add to the invoke signature:

```python
        _progress_callback: Callable[[dict[str, Any]], None] | None = None,
```

And wire it into the progress sink:

```python
        async def _progress_sink(payload: dict[str, Any]) -> None:
            progress_events.append(payload)
            if _progress_callback is not None:
                _progress_callback(payload)
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

### Task 9: Hono SSE Binding

**Files:**
- Modify: `packages/typescript/hono/src/routes.ts`
- Test: `packages/typescript/hono/tests/routes.test.ts`

**Step 1: Write the failing test**

Add to `packages/typescript/hono/tests/routes.test.ts` (follow existing test patterns in the file):

```typescript
describe("Streaming", () => {
  it("returns SSE for stream:true on streaming-capable capability", async () => {
    // Issue a token, then invoke with stream: true
    // Assert content-type is text/event-stream
    // Assert body contains "event: progress" and "event: completed"
  });
});
```

The exact test implementation depends on the existing test setup pattern in the file. Read the existing test file to match its fixture/setup pattern, then add tests for:
- `stream: true` returns `text/event-stream` with progress + completed events
- `stream: true` on unary-only capability returns 400 JSON error

**Step 2: Implement SSE in the Hono invoke route**

In `packages/typescript/hono/src/routes.ts`, update the invoke handler (lines 53-68):

When `body.stream === true`:
1. Validate streaming support (return JSON 400 error if not supported)
2. Call `service.invoke()` with `{ stream: true }` to get result + stream_summary
3. Build SSE event strings for collected progress and terminal event
4. Return `new Response(ReadableStream, { headers: { "Content-Type": "text/event-stream", ... } })`

The pattern for the SSE response in Hono:

```typescript
const encoder = new TextEncoder();
const stream = new ReadableStream({
  async start(controller) {
    // Emit progress events
    for (const payload of progressEvents) {
      const eventData = { invocation_id: result.invocation_id, ... , payload };
      controller.enqueue(encoder.encode(`event: progress\ndata: ${JSON.stringify(eventData)}\n\n`));
    }
    // Emit terminal event
    const terminalData = { invocation_id: result.invocation_id, ..., result: result.result, stream_summary: result.stream_summary };
    controller.enqueue(encoder.encode(`event: completed\ndata: ${JSON.stringify(terminalData)}\n\n`));
    controller.close();
  },
});
return new Response(stream, {
  headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive" },
});
```

**Step 3: Run tests**

Run: `cd packages/typescript && npx vitest run hono/tests/routes.test.ts -v`
Expected: PASS

**Step 4: Commit**

```bash
git add packages/typescript/hono/
git commit -m "feat(hono): add SSE streaming support to invoke route"
```

---

### Task 10: Express SSE Binding

**Files:**
- Modify: `packages/typescript/express/src/routes.ts`
- Test: `packages/typescript/express/tests/routes.test.ts`

**Step 1: Implement SSE in the Express invoke route**

In `packages/typescript/express/src/routes.ts`, update the invoke handler (lines 58-75):

When `body.stream === true`:
1. Validate streaming support (return JSON 400 if not)
2. Call `service.invoke()` with `{ stream: true }`
3. Write SSE events via `res.writeHead(200, { "Content-Type": "text/event-stream", ... })` + `res.write()` + `res.end()`

Pattern:

```typescript
res.writeHead(200, {
  "Content-Type": "text/event-stream",
  "Cache-Control": "no-cache",
  "Connection": "keep-alive",
});
// ... write progress events and terminal event ...
res.end();
```

**Step 2: Run tests**

Run: `cd packages/typescript && npx vitest run express/tests/routes.test.ts -v`
Expected: PASS

**Step 3: Commit**

```bash
git add packages/typescript/express/
git commit -m "feat(express): add SSE streaming support to invoke route"
```

---

### Task 11: Fastify SSE Binding

**Files:**
- Modify: `packages/typescript/fastify/src/routes.ts`
- Test: `packages/typescript/fastify/tests/routes.test.ts`

**Step 1: Implement SSE in the Fastify invoke route**

In `packages/typescript/fastify/src/routes.ts`, update the invoke handler (lines 50-67):

When `body.stream === true`:
1. Validate streaming support (return JSON 400 if not)
2. Call `service.invoke()` with `{ stream: true }`
3. Write SSE events via `reply.raw.writeHead(200, { ... })` + `reply.raw.write()` + `reply.raw.end()`

**Step 2: Run tests**

Run: `cd packages/typescript && npx vitest run fastify/tests/routes.test.ts -v`
Expected: PASS

**Step 3: Commit**

```bash
git add packages/typescript/fastify/
git commit -m "feat(fastify): add SSE streaming support to invoke route"
```

---

### Task 12: JSON Schema Updates

**Files:**
- Modify: `schema/anip.schema.json`
- Modify: `schema/types/CapabilityDeclaration.json`

**Step 1: Update schemas**

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

Update `CapabilityDeclaration` in the schema to add:

```json
"response_modes": {
  "type": "array",
  "items": { "$ref": "#/$defs/ResponseMode" },
  "minItems": 1,
  "uniqueItems": true,
  "default": ["unary"]
}
```

Update `InvokeRequest` to add:

```json
"stream": { "type": "boolean", "default": false }
```

**Step 2: Commit**

```bash
git add schema/
git commit -m "feat(schema): add ResponseMode, StreamSummary, and stream field to JSON schemas"
```

---

### Task 13: Version Bump to 0.6.0

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
- `packages/typescript/crypto/package.json` line 16: `"@anip/core": "0.5.0"` → `"0.6.0"`
- `packages/typescript/server/package.json` line 16: `"@anip/core": "0.5.0"` → `"0.6.0"`
- `packages/typescript/server/package.json` line 17: `"@anip/crypto": "0.5.0"` → `"0.6.0"`
- `packages/typescript/service/package.json` line 16: `"@anip/core": "0.5.0"` → `"0.6.0"`
- `packages/typescript/service/package.json` line 17: `"@anip/crypto": "0.5.0"` → `"0.6.0"`
- `packages/typescript/service/package.json` line 18: `"@anip/server": "0.5.0"` → `"0.6.0"`
- `packages/typescript/express/package.json` line 16: `"@anip/service": "0.5.0"` → `"0.6.0"`
- `packages/typescript/fastify/package.json` line 16: `"@anip/service": "0.5.0"` → `"0.6.0"`
- `packages/typescript/hono/package.json` line 16: `"@anip/service": "0.5.0"` → `"0.6.0"`

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

### Task 14: Full Integration Test

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

Task 12 (JSON schema) ── independent
Task 13 (version bump) ── after all other tasks
Task 14 (integration) ── final verification
```

Tasks 1-2 and Task 3 can run in parallel (Python and TypeScript core models are independent).
Tasks 9, 10, 11 can run in parallel (independent HTTP bindings).
