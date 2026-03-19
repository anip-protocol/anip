# ANIP v0.11: Observability and Runtime Instrumentation — Design

## Goal

Make ANIP operationally observable through callback-based injection points. No hard dependencies on OpenTelemetry, logging frameworks, or metrics backends. Adopters plug in what they need; everything is optional.

## Architecture

A single `hooks` object is passed into service opts with four namespaced sections:

```
hooks: {
  logging:      structured lifecycle events
  metrics:      counters / durations / gauges
  tracing:      span start / end with opaque handles
  diagnostics:  background failure signals
}
```

Plus a `getHealth()` method on the service for pull-based runtime diagnostics.

### Implementation Rule

Missing hooks must be true no-ops. No allocation, no event construction, no branching beyond a single null check at the call site.

## Top-Level Interface

### TypeScript

```typescript
interface ANIPHooks {
  logging?: LoggingHooks;
  metrics?: MetricsHooks;
  tracing?: TracingHooks;
  diagnostics?: DiagnosticsHooks;
}

interface ANIPServiceOpts {
  // ... existing opts ...
  hooks?: ANIPHooks;
}
```

### Python

```python
@dataclass
class ANIPHooks:
    logging: LoggingHooks | None = None
    metrics: MetricsHooks | None = None
    tracing: TracingHooks | None = None
    diagnostics: DiagnosticsHooks | None = None

class ANIPService:
    def __init__(self, *, hooks: ANIPHooks | None = None, ...):
```

Every callback in every hook section is optional. If `hooks` is omitted or a section is `None`, that surface is silent.

## hooks.logging — Structured Logging Hooks

Fire at key lifecycle moments with structured event payloads. Each callback receives a single event object. All return `void` — logging hooks never block the request path.

```typescript
interface LoggingHooks {
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
```

Eight hooks covering: invocation lifecycle, delegation, audit, checkpoints, retention, aggregation, and streaming.

## hooks.metrics — Metrics Hooks

Increment/observe callbacks that adopters wire to their metrics backend. Each takes a small typed event object — not positional arguments — for evolvability and cross-runtime consistency.

```typescript
interface MetricsHooks {
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
```

Ten hooks. Separate from logging — metrics carry just the dimensions and values needed for counters/histograms/gauges. An adopter may use one surface without the other.

## hooks.tracing — Tracing Hooks

Two callbacks model span lifecycle without importing OTEL types. ANIP calls `startSpan` at flow boundaries, receives an opaque handle, and passes it back to `endSpan`.

```typescript
interface TracingHooks {
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
```

### Stable Span Catalog

The initial set of span names (stable contract):

| Span Name | When |
|-----------|------|
| `anip.invoke` | Full invocation lifecycle (root span for a request) |
| `anip.delegation.validate` | Token resolution and validation |
| `anip.handler.execute` | Capability handler execution |
| `anip.audit.append` | Audit entry persistence |
| `anip.checkpoint.create` | Checkpoint generation |
| `anip.proof.generate` | Inclusion proof generation |
| `anip.retention.sweep` | Retention enforcer sweep |
| `anip.aggregation.flush` | Aggregation window flush |

### Nesting Model

Request-path spans nest under `anip.invoke`:

```
anip.invoke
  anip.delegation.validate
  anip.handler.execute
  anip.audit.append
```

Background spans (`anip.checkpoint.create`, `anip.retention.sweep`, `anip.aggregation.flush`) are root spans on their own trace.

## hooks.diagnostics — Background Failure Signals

A single push callback for errors from background workers that are otherwise swallowed silently.

```typescript
interface DiagnosticsHooks {
  onBackgroundError?(event: {
    source: "checkpoint" | "retention" | "aggregation";
    error: string;
    timestamp: string;
  }): void;
}
```

## service.getHealth() — Pull-Based Diagnostics

A synchronous method on the service for runtime health state. Adopters wire it to readiness probes, health endpoints, or dashboards.

```typescript
interface ANIPService {
  // ... existing methods ...
  getHealth(): HealthReport;
}

interface HealthReport {
  status: "healthy" | "degraded" | "unhealthy";
  storage: { type: string; connected: boolean };
  checkpoint: { healthy: boolean; lastRunAt: string | null; lagSeconds: number | null } | null;
  retention: { healthy: boolean; lastRunAt: string | null; lastDeletedCount: number };
  aggregation: { pendingWindows: number } | null;
}
```

`status` is derived: `healthy` if all workers are running as expected, `degraded` if a non-critical worker has failed, `unhealthy` if storage is disconnected or a critical component has failed.

## Framework Bindings

Each framework binding (FastAPI, Hono, Express, Fastify) adds an optional health endpoint:

- **Route**: `GET /.well-known/anip/health`
- **Response**: JSON from `service.getHealth()`
- **Opt-out**: bindings accept a `healthEndpoint: false` option to disable it

No other binding changes. Logging, metrics, and tracing hooks fire from the service layer, not the HTTP layer. Tracing context propagation (e.g., `traceparent` header parsing) is the adopter's responsibility outside ANIP.

## Discovery

No changes to discovery posture. Observability configuration is deployment-internal and not useful to ANIP protocol clients.

## Package Impact

Primary:

- `packages/python/anip-service` — hook types, call sites in service runtime
- `packages/typescript/service` — hook types, call sites in service runtime
- `packages/python/anip-server` — `getHealth()` support from storage/workers
- `packages/typescript/server` — `getHealth()` support from storage/workers

Secondary:

- `packages/python/anip-fastapi` — health endpoint
- `packages/typescript/hono` — health endpoint
- `packages/typescript/express` — health endpoint
- `packages/typescript/fastify` — health endpoint

## Testing Strategy

- **Hook firing tests** — verify each callback fires at the right moment with correct payload shapes, using a mock hooks object that records calls.
- **No-op path tests** — verify omitted hooks take the no-op path: no callbacks fire, no event objects are constructed.
- **`getHealth()` tests** — verify correct reporting for each worker state (running, stopped, failed, no checkpoint configured, etc.).
- **Cross-runtime parity** — same hook events, same payload shapes, same span names in Python and TypeScript.
- **Example apps untouched** — hooks are fully optional; example apps must not need changes.

## What v0.11 Does Not Do

- Force OpenTelemetry as a hard dependency
- Define protocol-level telemetry formats
- Add vendor-specific monitoring assumptions
- Introduce an event-emitter or pub/sub model
- Change discovery or protocol semantics
