# ANIP v0.11: Observability and Runtime Instrumentation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add callback-based observability hooks (logging, metrics, tracing, diagnostics) and a `getHealth()` method to both Python and TypeScript ANIP service runtimes, plus optional health endpoints in all four framework bindings.

**Architecture:** A single `hooks` object is accepted in service opts with four namespaced sections (`logging`, `metrics`, `tracing`, `diagnostics`). Each section contains optional callbacks that fire at key lifecycle moments. A `getHealth()` method returns a cached snapshot of runtime state. Framework bindings optionally expose `GET /-/health`.

**Tech Stack:** Python (asyncio, dataclasses), TypeScript (interfaces, closures), vitest (TS tests), pytest (Python tests)

**Design doc:** `docs/plans/2026-03-18-v011-observability-design.md`

---

### Task 1: Hook type definitions — TypeScript

Define the hook interfaces in a new file and export them.

**Files:**
- Create: `packages/typescript/service/src/hooks.ts`
- Modify: `packages/typescript/service/src/index.ts`
- Modify: `packages/typescript/service/src/service.ts` (add `hooks?` to `ANIPServiceOpts`)
- Test: `packages/typescript/service/tests/hooks.test.ts`

**Step 1: Write the test**

```typescript
// packages/typescript/service/tests/hooks.test.ts
import { describe, it, expect } from "vitest";
import type {
  ANIPHooks,
  LoggingHooks,
  MetricsHooks,
  TracingHooks,
  DiagnosticsHooks,
  HealthReport,
} from "../src/hooks.js";

describe("Hook type definitions", () => {
  it("accepts a fully populated hooks object", () => {
    const hooks: ANIPHooks = {
      logging: {
        onInvocationStart: () => {},
        onInvocationEnd: () => {},
        onDelegationFailure: () => {},
        onAuditAppend: () => {},
        onCheckpointCreated: () => {},
        onRetentionSweep: () => {},
        onAggregationFlush: () => {},
        onStreamingSummary: () => {},
      },
      metrics: {
        onInvocationDuration: () => {},
        onDelegationDenied: () => {},
        onAuditAppendDuration: () => {},
        onCheckpointCreated: () => {},
        onCheckpointFailed: () => {},
        onProofGenerated: () => {},
        onProofUnavailable: () => {},
        onRetentionDeleted: () => {},
        onAggregationFlushed: () => {},
        onStreamingDeliveryFailure: () => {},
      },
      tracing: {
        startSpan: () => ({}),
        endSpan: () => {},
      },
      diagnostics: {
        onBackgroundError: () => {},
      },
    };
    expect(hooks).toBeDefined();
  });

  it("accepts an empty hooks object", () => {
    const hooks: ANIPHooks = {};
    expect(hooks).toBeDefined();
  });

  it("accepts partial hooks", () => {
    const hooks: ANIPHooks = {
      logging: { onInvocationStart: () => {} },
    };
    expect(hooks).toBeDefined();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd packages/typescript && npx vitest run service/tests/hooks.test.ts`
Expected: FAIL — cannot resolve `../src/hooks.js`

**Step 3: Create the hooks type file**

```typescript
// packages/typescript/service/src/hooks.ts

// ---------------------------------------------------------------------------
// Logging hooks
// ---------------------------------------------------------------------------

export interface LoggingHooks {
  onInvocationStart?(event: {
    capability: string;
    invocationId: string;
    clientReferenceId: string | null;
    rootPrincipal: string;
    subject: string;
    timestamp: string;
  }): void;

  onInvocationEnd?(event: {
    capability: string;
    invocationId: string;
    success: boolean;
    failureType: string | null;
    durationMs: number;
    timestamp: string;
  }): void;

  onDelegationFailure?(event: {
    reason: string;
    tokenId: string | null;
    timestamp: string;
  }): void;

  onAuditAppend?(event: {
    sequenceNumber: number;
    capability: string;
    invocationId: string;
    success: boolean;
    timestamp: string;
  }): void;

  onCheckpointCreated?(event: {
    checkpointId: string;
    entryCount: number;
    merkleRoot: string;
    timestamp: string;
  }): void;

  onRetentionSweep?(event: {
    deletedCount: number;
    durationMs: number;
    timestamp: string;
  }): void;

  onAggregationFlush?(event: {
    windowCount: number;
    entriesFlushed: number;
    timestamp: string;
  }): void;

  onStreamingSummary?(event: {
    invocationId: string;
    capability: string;
    eventsEmitted: number;
    eventsDelivered: number;
    clientDisconnected: boolean;
    durationMs: number;
    timestamp: string;
  }): void;
}

// ---------------------------------------------------------------------------
// Metrics hooks
// ---------------------------------------------------------------------------

export interface MetricsHooks {
  onInvocationDuration?(event: { capability: string; durationMs: number; success: boolean }): void;
  onDelegationDenied?(event: { reason: string }): void;
  onAuditAppendDuration?(event: { durationMs: number; success: boolean }): void;
  onCheckpointCreated?(event: { lagSeconds: number }): void;
  onCheckpointFailed?(event: { error: string }): void;
  onProofGenerated?(event: { durationMs: number }): void;
  onProofUnavailable?(event: { reason: string }): void;
  onRetentionDeleted?(event: { count: number }): void;
  onAggregationFlushed?(event: { windowCount: number }): void;
  onStreamingDeliveryFailure?(event: { capability: string }): void;
}

// ---------------------------------------------------------------------------
// Tracing hooks
// ---------------------------------------------------------------------------

export interface TracingHooks {
  startSpan?(event: {
    name: string;
    attributes: Record<string, string | number | boolean>;
    parentSpan?: unknown;
  }): unknown;

  endSpan?(event: {
    span: unknown;
    status: "ok" | "error";
    errorType?: string;
    errorMessage?: string;
    attributes?: Record<string, string | number | boolean>;
  }): void;
}

// ---------------------------------------------------------------------------
// Diagnostics hooks
// ---------------------------------------------------------------------------

export interface DiagnosticsHooks {
  onBackgroundError?(event: {
    source: "checkpoint" | "retention" | "aggregation";
    error: string;
    timestamp: string;
  }): void;
}

// ---------------------------------------------------------------------------
// Top-level hooks container
// ---------------------------------------------------------------------------

export interface ANIPHooks {
  logging?: LoggingHooks;
  metrics?: MetricsHooks;
  tracing?: TracingHooks;
  diagnostics?: DiagnosticsHooks;
}

// ---------------------------------------------------------------------------
// Health report
// ---------------------------------------------------------------------------

export interface HealthReport {
  status: "healthy" | "degraded" | "unhealthy";
  storage: { type: string };
  checkpoint: { healthy: boolean; lastRunAt: string | null; lagSeconds: number | null } | null;
  retention: { healthy: boolean; lastRunAt: string | null; lastDeletedCount: number };
  aggregation: { pendingWindows: number } | null;
}
```

**Step 4: Add `hooks?` to `ANIPServiceOpts`**

In `packages/typescript/service/src/service.ts`, add to the `ANIPServiceOpts` interface:

```typescript
import type { ANIPHooks, HealthReport } from "./hooks.js";

// In ANIPServiceOpts:
  hooks?: ANIPHooks;
```

**Step 5: Export from index**

In `packages/typescript/service/src/index.ts`, add:

```typescript
export type {
  ANIPHooks,
  LoggingHooks,
  MetricsHooks,
  TracingHooks,
  DiagnosticsHooks,
  HealthReport,
} from "./hooks.js";
```

**Step 6: Build and run tests**

Run: `cd packages/typescript && ./node_modules/.bin/tsc --build service && npx vitest run service/tests/hooks.test.ts`
Expected: PASS — all 3 type tests pass

**Step 7: Commit**

```bash
git add packages/typescript/service/src/hooks.ts packages/typescript/service/src/index.ts packages/typescript/service/src/service.ts packages/typescript/service/tests/hooks.test.ts
git commit -m "feat(v0.11): add TypeScript hook type definitions"
```

---

### Task 2: Hook type definitions — Python

Define the hook dataclasses in a new file and export them.

**Files:**
- Create: `packages/python/anip-service/src/anip_service/hooks.py`
- Modify: `packages/python/anip-service/src/anip_service/__init__.py`
- Modify: `packages/python/anip-service/src/anip_service/service.py` (add `hooks` param)
- Test: `packages/python/anip-service/tests/test_hooks.py`

**Step 1: Write the test**

```python
# packages/python/anip-service/tests/test_hooks.py
from anip_service.hooks import (
    ANIPHooks,
    LoggingHooks,
    MetricsHooks,
    TracingHooks,
    DiagnosticsHooks,
    HealthReport,
)


def test_fully_populated_hooks():
    hooks = ANIPHooks(
        logging=LoggingHooks(
            on_invocation_start=lambda event: None,
            on_invocation_end=lambda event: None,
            on_delegation_failure=lambda event: None,
            on_audit_append=lambda event: None,
            on_checkpoint_created=lambda event: None,
            on_retention_sweep=lambda event: None,
            on_aggregation_flush=lambda event: None,
            on_streaming_summary=lambda event: None,
        ),
        metrics=MetricsHooks(
            on_invocation_duration=lambda event: None,
            on_delegation_denied=lambda event: None,
            on_audit_append_duration=lambda event: None,
            on_checkpoint_created=lambda event: None,
            on_checkpoint_failed=lambda event: None,
            on_proof_generated=lambda event: None,
            on_proof_unavailable=lambda event: None,
            on_retention_deleted=lambda event: None,
            on_aggregation_flushed=lambda event: None,
            on_streaming_delivery_failure=lambda event: None,
        ),
        tracing=TracingHooks(
            start_span=lambda event: object(),
            end_span=lambda event: None,
        ),
        diagnostics=DiagnosticsHooks(
            on_background_error=lambda event: None,
        ),
    )
    assert hooks.logging is not None
    assert hooks.metrics is not None
    assert hooks.tracing is not None
    assert hooks.diagnostics is not None


def test_empty_hooks():
    hooks = ANIPHooks()
    assert hooks.logging is None
    assert hooks.metrics is None
    assert hooks.tracing is None
    assert hooks.diagnostics is None


def test_partial_hooks():
    hooks = ANIPHooks(
        logging=LoggingHooks(on_invocation_start=lambda event: None),
    )
    assert hooks.logging is not None
    assert hooks.logging.on_invocation_end is None
    assert hooks.metrics is None
```

**Step 2: Run test to verify it fails**

Run: `cd packages/python && python3 -m pytest anip-service/tests/test_hooks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'anip_service.hooks'`

**Step 3: Create the hooks module**

```python
# packages/python/anip-service/src/anip_service/hooks.py
"""Observability hook types for the ANIP service runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class LoggingHooks:
    on_invocation_start: Callable[[dict[str, Any]], None] | None = None
    on_invocation_end: Callable[[dict[str, Any]], None] | None = None
    on_delegation_failure: Callable[[dict[str, Any]], None] | None = None
    on_audit_append: Callable[[dict[str, Any]], None] | None = None
    on_checkpoint_created: Callable[[dict[str, Any]], None] | None = None
    on_retention_sweep: Callable[[dict[str, Any]], None] | None = None
    on_aggregation_flush: Callable[[dict[str, Any]], None] | None = None
    on_streaming_summary: Callable[[dict[str, Any]], None] | None = None


@dataclass
class MetricsHooks:
    on_invocation_duration: Callable[[dict[str, Any]], None] | None = None
    on_delegation_denied: Callable[[dict[str, Any]], None] | None = None
    on_audit_append_duration: Callable[[dict[str, Any]], None] | None = None
    on_checkpoint_created: Callable[[dict[str, Any]], None] | None = None
    on_checkpoint_failed: Callable[[dict[str, Any]], None] | None = None
    on_proof_generated: Callable[[dict[str, Any]], None] | None = None
    on_proof_unavailable: Callable[[dict[str, Any]], None] | None = None
    on_retention_deleted: Callable[[dict[str, Any]], None] | None = None
    on_aggregation_flushed: Callable[[dict[str, Any]], None] | None = None
    on_streaming_delivery_failure: Callable[[dict[str, Any]], None] | None = None


@dataclass
class TracingHooks:
    start_span: Callable[[dict[str, Any]], Any] | None = None
    end_span: Callable[[dict[str, Any]], None] | None = None


@dataclass
class DiagnosticsHooks:
    on_background_error: Callable[[dict[str, Any]], None] | None = None


@dataclass
class ANIPHooks:
    logging: LoggingHooks | None = None
    metrics: MetricsHooks | None = None
    tracing: TracingHooks | None = None
    diagnostics: DiagnosticsHooks | None = None


@dataclass
class HealthReport:
    status: str  # "healthy" | "degraded" | "unhealthy"
    storage: dict[str, Any]
    checkpoint: dict[str, Any] | None
    retention: dict[str, Any]
    aggregation: dict[str, Any] | None
```

**Step 4: Add `hooks` param to `ANIPService.__init__`**

In `packages/python/anip-service/src/anip_service/service.py`, add import and parameter:

```python
from anip_service.hooks import ANIPHooks, HealthReport
```

Add to `__init__` signature:

```python
    hooks: ANIPHooks | None = None,
```

Store it:

```python
    self._hooks = hooks or ANIPHooks()
```

**Step 5: Export from `__init__.py`**

In `packages/python/anip-service/src/anip_service/__init__.py`, add:

```python
from anip_service.hooks import (
    ANIPHooks,
    LoggingHooks,
    MetricsHooks,
    TracingHooks,
    DiagnosticsHooks,
    HealthReport,
)
```

**Step 6: Run tests**

Run: `cd packages/python && python3 -m pytest anip-service/tests/test_hooks.py -v`
Expected: PASS — all 3 tests pass

**Step 7: Commit**

```bash
git add packages/python/anip-service/src/anip_service/hooks.py packages/python/anip-service/src/anip_service/__init__.py packages/python/anip-service/src/anip_service/service.py packages/python/anip-service/tests/test_hooks.py
git commit -m "feat(v0.11): add Python hook type definitions"
```

---

### Task 3: Logging hooks — TypeScript invoke() wiring

Wire the 8 logging hooks into the TypeScript service runtime's `invoke()`, `logAudit()`, checkpoint, retention, and aggregation code paths.

**Files:**
- Modify: `packages/typescript/service/src/service.ts`
- Test: `packages/typescript/service/tests/logging-hooks.test.ts`

**Step 1: Write the test**

```typescript
// packages/typescript/service/tests/logging-hooks.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { createANIPService, defineCapability } from "../src/index.js";
import type { LoggingHooks } from "../src/hooks.js";

function makeTestService(loggingHooks: LoggingHooks) {
  const cap = defineCapability({
    declaration: {
      name: "test_cap",
      description: "Test capability",
      contract_version: "1.0",
      inputs: [],
      output: { type: "object", fields: [] },
      side_effect: { type: "read", rollback_window: "not_applicable" },
      minimum_scope: ["test"],
      cost: { certainty: "fixed", financial: null, determined_by: null, factors: null, compute: null, rate_limit: null },
      requires: [],
      composes_with: [],
      session: { type: "stateless" },
      observability: { logged: true, retention: "P90D", fields_logged: [], audit_accessible_by: [] },
    },
    handler: () => ({ result: "ok" }),
  });

  const service = createANIPService({
    serviceId: "test-hooks",
    capabilities: [cap],
    storage: { type: "memory" },
    authenticate: (bearer: string) => bearer === "valid" ? "human:tester" : null,
    hooks: { logging: loggingHooks },
  });

  return service;
}

describe("Logging hooks", () => {
  it("fires onInvocationStart and onInvocationEnd on successful invoke", async () => {
    const events: Record<string, unknown>[] = [];
    const service = makeTestService({
      onInvocationStart: (e) => events.push({ type: "start", ...e }),
      onInvocationEnd: (e) => events.push({ type: "end", ...e }),
    });
    await service.start();

    const token = await service.issueToken("human:tester", {
      scopes: ["test"],
      subject: "human:tester",
    });
    const resolved = await service.resolveBearerToken(token.token as string);
    await service.invoke("test_cap", resolved, {});

    service.stop();

    const startEvent = events.find((e) => e.type === "start");
    const endEvent = events.find((e) => e.type === "end");
    expect(startEvent).toBeDefined();
    expect(startEvent!.capability).toBe("test_cap");
    expect(startEvent!.invocationId).toBeDefined();
    expect(endEvent).toBeDefined();
    expect(endEvent!.success).toBe(true);
    expect(typeof endEvent!.durationMs).toBe("number");
  });

  it("fires onInvocationEnd with failureType on handler error", async () => {
    const events: Record<string, unknown>[] = [];
    const cap = defineCapability({
      declaration: {
        name: "fail_cap",
        description: "Failing capability",
        contract_version: "1.0",
        inputs: [],
        output: { type: "object", fields: [] },
        side_effect: { type: "read", rollback_window: "not_applicable" },
        minimum_scope: ["test"],
        cost: { certainty: "fixed", financial: null, determined_by: null, factors: null, compute: null, rate_limit: null },
        requires: [],
        composes_with: [],
        session: { type: "stateless" },
        observability: { logged: true, retention: "P90D", fields_logged: [], audit_accessible_by: [] },
      },
      handler: () => { throw new (require("../src/types.js").ANIPError)("invalid_parameters", "bad input"); },
    });

    const service = createANIPService({
      serviceId: "test-hooks-fail",
      capabilities: [cap],
      storage: { type: "memory" },
      authenticate: (b: string) => b === "valid" ? "human:tester" : null,
      hooks: { logging: { onInvocationEnd: (e) => events.push(e) } },
    });
    await service.start();

    const token = await service.issueToken("human:tester", { scopes: ["test"], subject: "human:tester" });
    const resolved = await service.resolveBearerToken(token.token as string);
    await service.invoke("fail_cap", resolved, {});

    service.stop();

    expect(events).toHaveLength(1);
    expect(events[0].success).toBe(false);
    expect(events[0].failureType).toBe("invalid_parameters");
  });

  it("does not throw when hooks are omitted", async () => {
    const service = createANIPService({
      serviceId: "test-no-hooks",
      capabilities: [defineCapability({
        declaration: {
          name: "cap",
          description: "d",
          contract_version: "1.0",
          inputs: [],
          output: { type: "object", fields: [] },
          side_effect: { type: "read", rollback_window: "not_applicable" },
          minimum_scope: ["test"],
          cost: { certainty: "fixed", financial: null, determined_by: null, factors: null, compute: null, rate_limit: null },
          requires: [],
          composes_with: [],
          session: { type: "stateless" },
          observability: { logged: true, retention: "P90D", fields_logged: [], audit_accessible_by: [] },
        },
        handler: () => ({ ok: true }),
      })],
      storage: { type: "memory" },
      authenticate: (b: string) => b === "v" ? "human:t" : null,
    });
    await service.start();

    const token = await service.issueToken("human:t", { scopes: ["test"], subject: "human:t" });
    const resolved = await service.resolveBearerToken(token.token as string);
    await expect(service.invoke("cap", resolved, {})).resolves.toBeDefined();

    service.stop();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd packages/typescript && npx vitest run service/tests/logging-hooks.test.ts`
Expected: FAIL — hooks not wired, onInvocationStart never fires

**Step 3: Wire logging hooks into `createANIPService`**

In `packages/typescript/service/src/service.ts`:

1. At the top of `createANIPService`, extract hooks:

```typescript
const hooks = opts.hooks ?? {};
const logHooks = hooks.logging;
```

2. In `invoke()`, at the very start (after invocationId is generated, before delegation validation):

```typescript
const invokeStartTime = performance.now();
logHooks?.onInvocationStart?.({
  capability: capabilityName,
  invocationId,
  clientReferenceId: clientReferenceId ?? null,
  rootPrincipal: /* resolved after token validation */,
  subject: /* resolved after token validation */,
  timestamp: new Date().toISOString(),
});
```

Note: `rootPrincipal` and `subject` are not available until after token resolution. Move this call to after the `InvocationContext` is built but before the handler runs.

3. At every return point in `invoke()` (success, ANIPError, internal_error, concurrent_lock), fire `onInvocationEnd`:

```typescript
logHooks?.onInvocationEnd?.({
  capability: capabilityName,
  invocationId,
  success: true/false,
  failureType: null/"invalid_parameters"/etc.,
  durationMs: Math.round(performance.now() - invokeStartTime),
  timestamp: new Date().toISOString(),
});
```

4. After `audit.logEntry()` calls, fire `onAuditAppend`:

```typescript
logHooks?.onAuditAppend?.({
  sequenceNumber: /* from storage result */,
  capability: capabilityName,
  invocationId,
  success: auditSuccess,
  timestamp: new Date().toISOString(),
});
```

5. In `leaderCheckpointTick`, after successful checkpoint creation, fire `onCheckpointCreated`.

6. In `flushAggregator`, after flushing, fire `onAggregationFlush`.

7. In streaming code path, after stream completes, fire `onStreamingSummary`.

8. `onRetentionSweep` and `onDelegationFailure` will be wired in later tasks (Task 5 and Task 7 respectively) since they fire from server-layer components that need callback injection.

**Step 4: Run tests**

Run: `cd packages/typescript && ./node_modules/.bin/tsc --build service && npx vitest run service/tests/logging-hooks.test.ts`
Expected: PASS

**Step 5: Run full test suite to verify no regressions**

Run: `cd packages/typescript && npx vitest run`
Expected: All 289+ tests pass

**Step 6: Commit**

```bash
git add packages/typescript/service/src/service.ts packages/typescript/service/tests/logging-hooks.test.ts
git commit -m "feat(v0.11): wire logging hooks into TypeScript invoke()"
```

---

### Task 4: Logging hooks — Python invoke() wiring

Wire the same 8 logging hooks into the Python service runtime.

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Test: `packages/python/anip-service/tests/test_logging_hooks.py`

**Step 1: Write the test**

```python
# packages/python/anip-service/tests/test_logging_hooks.py
import pytest
from anip_service import ANIPService, Capability, ANIPError, InvocationContext
from anip_service.hooks import ANIPHooks, LoggingHooks
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SideEffect, SideEffectType, Cost, CostCertainty, ObservabilityContract, SessionInfo


def _make_cap(name: str = "test_cap", handler=None):
    if handler is None:
        handler = lambda ctx, params: {"result": "ok"}
    return Capability(
        declaration=CapabilityDeclaration(
            name=name,
            description="Test",
            contract_version="1.0",
            inputs=[],
            output=CapabilityOutput(type="object", fields=[]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["test"],
            cost=Cost(certainty=CostCertainty.FIXED),
            session=SessionInfo(),
            observability=ObservabilityContract(logged=True, retention="P90D", fields_logged=[], audit_accessible_by=[]),
        ),
        handler=handler,
    )


@pytest.mark.asyncio
async def test_invocation_start_end_fires():
    events = []
    service = ANIPService(
        service_id="test-hooks",
        capabilities=[_make_cap()],
        storage=":memory:",
        authenticate=lambda b: "human:tester" if b == "valid" else None,
        hooks=ANIPHooks(logging=LoggingHooks(
            on_invocation_start=lambda e: events.append({"type": "start", **e}),
            on_invocation_end=lambda e: events.append({"type": "end", **e}),
        )),
    )
    service.start()

    token_resp = await service.issue_token("human:tester", {"scopes": ["test"], "subject": "human:tester"})
    resolved = await service.resolve_bearer_token(token_resp["token"])
    await service.invoke("test_cap", resolved, {})

    service.stop()

    start_events = [e for e in events if e["type"] == "start"]
    end_events = [e for e in events if e["type"] == "end"]
    assert len(start_events) == 1
    assert start_events[0]["capability"] == "test_cap"
    assert "invocationId" in start_events[0] or "invocation_id" in start_events[0]
    assert len(end_events) == 1
    assert end_events[0]["success"] is True
    assert isinstance(end_events[0]["duration_ms"], (int, float))


@pytest.mark.asyncio
async def test_invocation_end_on_failure():
    events = []
    def failing_handler(ctx, params):
        raise ANIPError("invalid_parameters", "bad input")

    service = ANIPService(
        service_id="test-hooks-fail",
        capabilities=[_make_cap("fail_cap", handler=failing_handler)],
        storage=":memory:",
        authenticate=lambda b: "human:tester" if b == "valid" else None,
        hooks=ANIPHooks(logging=LoggingHooks(
            on_invocation_end=lambda e: events.append(e),
        )),
    )
    service.start()

    token_resp = await service.issue_token("human:tester", {"scopes": ["test"], "subject": "human:tester"})
    resolved = await service.resolve_bearer_token(token_resp["token"])
    await service.invoke("fail_cap", resolved, {})

    service.stop()

    assert len(events) == 1
    assert events[0]["success"] is False
    assert events[0]["failure_type"] == "invalid_parameters"


@pytest.mark.asyncio
async def test_no_hooks_no_error():
    service = ANIPService(
        service_id="test-no-hooks",
        capabilities=[_make_cap()],
        storage=":memory:",
        authenticate=lambda b: "human:t" if b == "v" else None,
    )
    service.start()

    token_resp = await service.issue_token("human:t", {"scopes": ["test"], "subject": "human:t"})
    resolved = await service.resolve_bearer_token(token_resp["token"])
    result = await service.invoke("test_cap", resolved, {})

    service.stop()

    assert result["success"] is True
```

**Step 2: Run test to verify it fails**

Run: `cd packages/python && python3 -m pytest anip-service/tests/test_logging_hooks.py -v`
Expected: FAIL — hooks not wired

**Step 3: Wire logging hooks into `ANIPService.invoke()`**

In `packages/python/anip-service/src/anip_service/service.py`:

1. Extract hooks at init:

```python
self._hooks = hooks or ANIPHooks()
self._log_hooks = self._hooks.logging
```

2. In `invoke()`, after building `InvocationContext` but before handler:

```python
invoke_start = time.monotonic()
if self._log_hooks and self._log_hooks.on_invocation_start:
    self._log_hooks.on_invocation_start({
        "capability": capability_name,
        "invocation_id": invocation_id,
        "client_reference_id": client_reference_id,
        "root_principal": root_principal,
        "subject": subject,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
```

3. At every return point, fire `on_invocation_end` (same pattern as TypeScript).

4. Wire `on_audit_append`, `on_checkpoint_created`, `on_aggregation_flush`, `on_streaming_summary` at their respective call sites.

**Step 4: Run tests**

Run: `cd packages/python && python3 -m pytest anip-service/tests/test_logging_hooks.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `cd packages/python && python3 -m pytest anip-service/tests/ anip-server/tests/ -x -q`
Expected: All 214+ tests pass

**Step 6: Commit**

```bash
git add packages/python/anip-service/src/anip_service/service.py packages/python/anip-service/tests/test_logging_hooks.py
git commit -m "feat(v0.11): wire logging hooks into Python invoke()"
```

---

### Task 5: Metrics hooks — both runtimes

Wire the 10 metrics hooks into both TypeScript and Python service runtimes.

**Files:**
- Modify: `packages/typescript/service/src/service.ts`
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Test: `packages/typescript/service/tests/metrics-hooks.test.ts`
- Test: `packages/python/anip-service/tests/test_metrics_hooks.py`

**Implementation approach:**

Metrics hooks fire at the same lifecycle points as logging hooks but with simpler payloads. Many share call sites — e.g., `onInvocationEnd` fires the logging hook, and the same location fires `onInvocationDuration` for metrics.

The key new metrics with no logging equivalent:
- `onCheckpointFailed` — surfaces currently-swallowed checkpoint errors
- `onProofGenerated` / `onProofUnavailable` — fires from `getCheckpoint()` proof generation path
- `onStreamingDeliveryFailure` — fires when a progress event write to the client fails

For each:
1. Write test that creates a service with `hooks: { metrics: {...} }` and verifies callbacks fire
2. Wire `metricsHooks?.onXxx?.({ ... })` calls at the right locations
3. Verify no regression in full suite

**Commit:**

```bash
git commit -m "feat(v0.11): wire metrics hooks into both runtimes"
```

---

### Task 6: Tracing hooks — both runtimes

Wire `startSpan` / `endSpan` around the 8 stable spans defined in the design.

**Files:**
- Modify: `packages/typescript/service/src/service.ts`
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Test: `packages/typescript/service/tests/tracing-hooks.test.ts`
- Test: `packages/python/anip-service/tests/test_tracing_hooks.py`

**Implementation approach:**

Create a small helper to reduce boilerplate:

TypeScript:
```typescript
function withSpan<T>(
  tracing: TracingHooks | undefined,
  name: string,
  attrs: Record<string, string | number | boolean>,
  parent: unknown | undefined,
  fn: (span: unknown) => T,
): T {
  if (!tracing?.startSpan) return fn(undefined);
  const span = tracing.startSpan({ name, attributes: attrs, parentSpan: parent });
  try {
    const result = fn(span);
    if (result instanceof Promise) {
      return result.then(
        (v) => { tracing.endSpan?.({ span, status: "ok" }); return v; },
        (e) => { tracing.endSpan?.({ span, status: "error", errorType: e?.name, errorMessage: e?.message }); throw e; },
      ) as T;
    }
    tracing.endSpan?.({ span, status: "ok" });
    return result;
  } catch (e: any) {
    tracing.endSpan?.({ span, status: "error", errorType: e?.name, errorMessage: e?.message });
    throw e;
  }
}
```

Python equivalent:
```python
async def _with_span(tracing, name, attrs, parent, fn):
    if not tracing or not tracing.start_span:
        return await fn()
    span = tracing.start_span({"name": name, "attributes": attrs, "parent_span": parent})
    try:
        result = await fn()
        if tracing.end_span:
            tracing.end_span({"span": span, "status": "ok"})
        return result
    except Exception as e:
        if tracing.end_span:
            tracing.end_span({"span": span, "status": "error", "error_type": type(e).__name__, "error_message": str(e)})
        raise
```

Wrap these spans in `invoke()`:
1. `anip.invoke` — root span for the entire invocation
2. `anip.delegation.validate` — around token resolution
3. `anip.handler.execute` — around the handler call
4. `anip.audit.append` — around audit persistence

And in background flows:
5. `anip.checkpoint.create` — around checkpoint creation
6. `anip.proof.generate` — around proof generation in `getCheckpoint()`
7. `anip.retention.sweep` — around retention sweep
8. `anip.aggregation.flush` — around aggregation flush

Tests verify span start/end pairs fire with correct names and nesting.

**Commit:**

```bash
git commit -m "feat(v0.11): wire tracing hooks into both runtimes"
```

---

### Task 7: Diagnostics hook + retention/checkpoint callback injection

Wire `onBackgroundError` by injecting error callbacks into `CheckpointScheduler` and `RetentionEnforcer`. Also wire `onRetentionSweep` and `onDelegationFailure` logging hooks which fire from server-layer components.

**Files:**
- Modify: `packages/typescript/server/src/retention-enforcer.ts`
- Modify: `packages/typescript/server/src/checkpoint.ts`
- Modify: `packages/python/anip-server/src/anip_server/retention_enforcer.py`
- Modify: `packages/python/anip-server/src/anip_server/checkpoint.py`
- Modify: `packages/typescript/service/src/service.ts` (pass callbacks to server components)
- Modify: `packages/python/anip-service/src/anip_service/service.py` (pass callbacks to server components)
- Test: `packages/typescript/service/tests/diagnostics-hooks.test.ts`
- Test: `packages/python/anip-service/tests/test_diagnostics_hooks.py`

**Implementation approach:**

Add optional `onError` and `onSweep` callback parameters to `RetentionEnforcer` and `CheckpointScheduler`:

TypeScript RetentionEnforcer:
```typescript
constructor(
  storage: StorageBackend,
  intervalSeconds = 60,
  opts?: {
    skipAuditRetention?: boolean;
    onSweep?: (deletedCount: number, durationMs: number) => void;
    onError?: (error: string) => void;
  },
)
```

Then in the sweep loop, call `onSweep` after a successful sweep and `onError` when an exception is caught.

The service layer passes lambdas that fire the hooks:

```typescript
const retentionEnforcer = new RetentionEnforcer(storage, 60, {
  skipAuditRetention: isPostgresBackend,
  onSweep: (deletedCount, durationMs) => {
    logHooks?.onRetentionSweep?.({ deletedCount, durationMs, timestamp: new Date().toISOString() });
    metricsHooks?.onRetentionDeleted?.({ count: deletedCount });
  },
  onError: (error) => {
    hooks.diagnostics?.onBackgroundError?.({ source: "retention", error, timestamp: new Date().toISOString() });
  },
});
```

Same pattern for CheckpointScheduler and aggregation flush errors.

Tests verify `onBackgroundError` fires when a background worker encounters an error (use a storage mock that throws).

**Commit:**

```bash
git commit -m "feat(v0.11): wire diagnostics and background hooks"
```

---

### Task 8: `getHealth()` — both runtimes

Add `getHealth()` method to both service runtimes that returns a cached snapshot of runtime state.

**Files:**
- Modify: `packages/typescript/service/src/service.ts`
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/typescript/server/src/retention-enforcer.ts` (add state tracking)
- Modify: `packages/python/anip-server/src/anip_server/retention_enforcer.py` (add state tracking)
- Test: `packages/typescript/service/tests/health.test.ts`
- Test: `packages/python/anip-service/tests/test_health.py`

**Implementation approach:**

Add state tracking to server components:
- `RetentionEnforcer`: track `lastRunAt`, `lastDeletedCount`, `lastError`
- `CheckpointScheduler`: track `lastRunAt`, `lastError`

These are updated as side effects of normal ticks — no live probes.

TypeScript `getHealth()`:
```typescript
getHealth(): HealthReport {
  const checkpointHealth = scheduler ? {
    healthy: /* lastError is null */,
    lastRunAt: /* from scheduler state */,
    lagSeconds: /* compute from last checkpoint time vs now */,
  } : null;

  const retentionHealth = {
    healthy: retentionEnforcer.isRunning(),
    lastRunAt: retentionEnforcer.getLastRunAt(),
    lastDeletedCount: retentionEnforcer.getLastDeletedCount(),
  };

  const aggregationHealth = aggregator ? {
    pendingWindows: aggregator.getPendingCount(),
  } : null;

  const storageType = isPostgresBackend ? "postgres"
    : storage instanceof SQLiteStorage ? "sqlite"
    : "memory";

  const status = /* derive from component health */;

  return { status, storage: { type: storageType }, checkpoint: checkpointHealth, retention: retentionHealth, aggregation: aggregationHealth };
}
```

Python equivalent follows the same pattern.

Tests:
- Verify health report shape after `start()`
- Verify `status` is `"healthy"` under normal conditions
- Verify `checkpoint` is `null` when no checkpoint policy configured
- Verify `aggregation` is `null` when no aggregation window configured

**Commit:**

```bash
git commit -m "feat(v0.11): add getHealth() to both runtimes"
```

---

### Task 9: Framework binding health endpoints

Add optional `GET /-/health` endpoint to all four framework bindings.

**Files:**
- Modify: `packages/python/anip-fastapi/src/anip_fastapi/routes.py`
- Modify: `packages/typescript/hono/src/routes.ts`
- Modify: `packages/typescript/express/src/routes.ts`
- Modify: `packages/typescript/fastify/src/routes.ts`
- Test: `packages/python/anip-fastapi/tests/test_health.py` (or add to existing test)
- Test: `packages/typescript/hono/tests/health.test.ts` (or add to existing test)
- Test: `packages/typescript/express/tests/health.test.ts` (or add to existing test)
- Test: `packages/typescript/fastify/tests/health.test.ts` (or add to existing test)

**Implementation approach:**

Each binding adds a `healthEndpoint` option (default: `false`). When enabled, register `GET /-/health` that calls `service.getHealth()` and returns JSON.

FastAPI:
```python
def mount_anip(app: FastAPI, service: ANIPService, prefix: str = "", *, health_endpoint: bool = False):
    # ... existing routes ...
    if health_endpoint:
        @app.get("/-/health")
        def health():
            return service.get_health()
```

Hono:
```typescript
function mountAnip(app: Hono, service: ANIPService, opts?: { prefix?: string; healthEndpoint?: boolean }) {
  // ... existing routes ...
  if (opts?.healthEndpoint) {
    app.get("/-/health", (c) => c.json(service.getHealth()));
  }
}
```

Same pattern for Express and Fastify.

Tests verify:
- Health endpoint not registered by default
- Health endpoint responds with 200 and correct shape when enabled
- Health endpoint returns valid JSON with `status`, `storage`, `retention` fields

**Commit:**

```bash
git commit -m "feat(v0.11): add optional health endpoint to framework bindings"
```

---

### Task 10: Update PROTOCOL_VERSION and final verification

Bump the protocol version to `anip/0.11` and run all tests across both runtimes.

**Files:**
- Modify: `packages/typescript/core/src/index.ts` (PROTOCOL_VERSION)
- Modify: `packages/python/anip-core/src/anip_core/__init__.py` (PROTOCOL_VERSION)
- Modify: any version tests that assert `anip/0.10`

**Step 1: Update version constants**

TypeScript:
```typescript
export const PROTOCOL_VERSION = "anip/0.11";
```

Python:
```python
PROTOCOL_VERSION = "anip/0.11"
```

**Step 2: Update version tests**

Find and update any test assertions that check for `anip/0.10`.

**Step 3: Rebuild and run all tests**

Run:
```bash
cd packages/typescript && ./node_modules/.bin/tsc --build core crypto server service && npx vitest run
cd ../python && python3 -m pytest anip-service/tests/ anip-server/tests/ -x -q
```

Expected: All tests pass with updated version

**Step 4: Verify example apps still work without changes**

Run:
```bash
cd packages/typescript && npx vitest run ../examples/anip-ts/tests/
cd ../python && python3 -m pytest ../../examples/anip/tests/ -x -q
```

Expected: Example apps pass without modification — hooks are fully optional

**Step 5: Commit**

```bash
git commit -m "feat(v0.11): bump protocol version to anip/0.11"
```

---

## Task Summary

| Task | Description | Primary Packages |
|------|-------------|-----------------|
| 1 | Hook type definitions — TypeScript | service (TS) |
| 2 | Hook type definitions — Python | anip-service (Py) |
| 3 | Logging hooks — TypeScript invoke() | service (TS) |
| 4 | Logging hooks — Python invoke() | anip-service (Py) |
| 5 | Metrics hooks — both runtimes | service (TS), anip-service (Py) |
| 6 | Tracing hooks — both runtimes | service (TS), anip-service (Py) |
| 7 | Diagnostics + server component callbacks | server (TS/Py), service (TS/Py) |
| 8 | `getHealth()` — both runtimes | server (TS/Py), service (TS/Py) |
| 9 | Framework binding health endpoints | fastapi, hono, express, fastify |
| 10 | Version bump + final verification | core (TS/Py), all tests |
