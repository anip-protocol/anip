---
title: Observability
description: Integrate ANIP with your logging, metrics, tracing, and health monitoring infrastructure.
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Observability

ANIP provides callback-based hooks for logging, metrics, tracing, and diagnostics. Hooks are optional and zero-overhead when absent — the runtime only calls hooks that are registered. Hook callbacks are isolated from correctness paths: a throwing hook never affects requests or background workers.

## Hook categories

| Category | Hooks | Purpose |
|----------|-------|---------|
| **Logging** | 8 hooks | Structured log events for invocations, delegation, audit, checkpoints |
| **Metrics** | 10 hooks | Counters and durations for monitoring dashboards |
| **Tracing** | 2 hooks | Span lifecycle for distributed tracing (OpenTelemetry, Jaeger, etc.) |
| **Diagnostics** | 1 hook | Background worker error reporting |

## Quick example

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

```python
from anip_service import ANIPService, ANIPHooks, LoggingHooks, MetricsHooks, TracingHooks

hooks = ANIPHooks(
    logging=LoggingHooks(
        on_invocation_start=lambda info: print(
            f"[ANIP] invoke-start  capability={info['capability']}  subject={info.get('subject')}"
        ),
        on_invocation_end=lambda info: print(
            f"[ANIP] invoke-end    capability={info['capability']}  "
            f"success={info['success']}  duration_ms={info.get('duration_ms')}"
        ),
        on_delegation_failure=lambda info: print(
            f"[ANIP] delegation-fail  reason={info.get('reason')}"
        ),
    ),
    metrics=MetricsHooks(
        on_invocation_duration=lambda info: statsd.timing(
            "anip.invoke.duration_ms", info["duration_ms"],
            tags=[f"capability:{info['capability']}", f"success:{info['success']}"],
        ),
        on_delegation_denied=lambda info: statsd.increment(
            "anip.delegation.denied", tags=[f"reason:{info.get('reason')}"],
        ),
    ),
)

service = ANIPService(
    service_id="my-service",
    capabilities=[...],
    hooks=hooks,
    authenticate=...,
)
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

```typescript
import { createANIPService } from "@anip/service";
import type { ANIPHooks } from "@anip/service";

const hooks: ANIPHooks = {
  logging: {
    onInvocationStart: (info) =>
      console.log(`[ANIP] invoke-start  capability=${info.capability}  subject=${info.subject}`),
    onInvocationEnd: (info) =>
      console.log(`[ANIP] invoke-end  capability=${info.capability}  success=${info.success}  duration_ms=${info.durationMs}`),
    onDelegationFailure: (info) =>
      console.log(`[ANIP] delegation-fail  reason=${info.reason}`),
  },
  metrics: {
    onInvocationDuration: (info) =>
      statsd.timing("anip.invoke.duration_ms", info.durationMs, {
        capability: info.capability, success: String(info.success),
      }),
  },
};

const service = createANIPService({
  serviceId: "my-service",
  capabilities: [...],
  hooks,
  authenticate: ...,
});
```

</TabItem>
<TabItem value="go" label="Go">

```go
svc, _ := service.New(service.Config{
    ServiceID:    "my-service",
    Capabilities: capabilities,
    Hooks: &service.ANIPHooks{
        Logging: &service.LoggingHooks{
            OnInvocationStart: func(info map[string]any) {
                log.Printf("[ANIP] invoke-start  capability=%s  subject=%s",
                    info["capability"], info["subject"])
            },
            OnInvocationEnd: func(info map[string]any) {
                log.Printf("[ANIP] invoke-end  capability=%s  success=%v  duration_ms=%v",
                    info["capability"], info["success"], info["duration_ms"])
            },
        },
    },
    Authenticate: authenticate,
})
```

</TabItem>
<TabItem value="java" label="Java">

```java
var hooks = new ANIPHooks()
    .setLogging(new LoggingHooks()
        .setOnInvocationStart(info ->
            logger.info("[ANIP] invoke-start capability={} subject={}",
                info.get("capability"), info.get("subject")))
        .setOnInvocationEnd(info ->
            logger.info("[ANIP] invoke-end capability={} success={} duration_ms={}",
                info.get("capability"), info.get("success"), info.get("duration_ms")))
    );

new ANIPService(new ServiceConfig()
    .setServiceId("my-service")
    .setCapabilities(capabilities)
    .setHooks(hooks)
    .setAuthenticate(authenticate));
```

</TabItem>
<TabItem value="csharp" label="C#">

```csharp
var hooks = new AnipHooks {
    Logging = new LoggingHooks {
        OnInvocationStart = info =>
            logger.LogInformation("[ANIP] invoke-start capability={Capability} subject={Subject}",
                info["capability"], info.GetValueOrDefault("subject")),
        OnInvocationEnd = info =>
            logger.LogInformation("[ANIP] invoke-end capability={Capability} success={Success} duration_ms={Duration}",
                info["capability"], info["success"], info.GetValueOrDefault("duration_ms")),
    }
};

var service = new AnipService(new ServiceConfig {
    ServiceId = "my-service",
    Capabilities = capabilities,
    Hooks = hooks,
    Authenticate = authenticate,
});
```

</TabItem>
</Tabs>

## Logging hooks

All logging hooks receive a `dict`/`map`/`object` with context-specific fields.

| Hook | When it fires | Key fields |
|------|--------------|------------|
| `on_invocation_start` | Before handler runs | `capability`, `subject`, `scope`, `invocation_id` |
| `on_invocation_end` | After handler completes | `capability`, `success`, `duration_ms`, `invocation_id` |
| `on_delegation_failure` | Token validation fails | `reason`, `subject` |
| `on_audit_append` | Audit entry written | `capability`, `event_class`, `invocation_id` |
| `on_checkpoint_created` | Merkle checkpoint built | `checkpoint_id`, `entry_count`, `merkle_root` |
| `on_retention_sweep` | Old entries purged | `deleted_count` |
| `on_aggregation_flush` | Aggregated entries flushed | `flushed_count` |
| `on_streaming_summary` | Streaming invocation completed | `capability`, `chunk_count`, `duration_ms` |

## Metrics hooks

| Hook | When it fires | Key fields |
|------|--------------|------------|
| `on_invocation_duration` | After each invocation | `capability`, `success`, `duration_ms` |
| `on_delegation_denied` | Delegation check fails | `reason` |
| `on_audit_append_duration` | Audit write completes | `duration_ms` |
| `on_checkpoint_created` | Checkpoint built | `entry_count`, `duration_ms` |
| `on_checkpoint_failed` | Checkpoint build fails | `error` |
| `on_proof_generated` | Merkle proof built | `duration_ms` |
| `on_proof_unavailable` | Proof cannot be generated | `reason` |
| `on_retention_deleted` | Entries purged | `deleted_count` |
| `on_aggregation_flushed` | Aggregated entries flushed | `flushed_count` |
| `on_streaming_delivery_failure` | SSE delivery fails | `capability`, `error` |

## Tracing hooks

ANIP defines 8 stable span names for distributed tracing integration:

| Span name | Type | Description |
|-----------|------|-------------|
| `anip.invoke` | Request | Top-level invocation span |
| `anip.delegation.validate` | Request | Token + scope validation |
| `anip.handler.execute` | Request | Capability handler execution |
| `anip.audit.append` | Request | Audit entry write |
| `anip.checkpoint.create` | Background | Merkle checkpoint generation |
| `anip.proof.generate` | Request | Inclusion proof generation |
| `anip.retention.sweep` | Background | Audit retention enforcement |
| `anip.aggregation.flush` | Background | Aggregated entry flush |

Request-path spans nest under `anip.invoke`. Background spans are root spans.

### OpenTelemetry integration

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

```python
from opentelemetry import trace

tracer = trace.get_tracer("anip")

hooks = ANIPHooks(
    tracing=TracingHooks(
        start_span=lambda info: tracer.start_span(
            info["span_name"],
            attributes={k: str(v) for k, v in info.get("attributes", {}).items()},
        ),
        end_span=lambda info: info["span"].end(),
    ),
)
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

```typescript
import { trace } from "@opentelemetry/api";

const tracer = trace.getTracer("anip");

const hooks: ANIPHooks = {
  tracing: {
    startSpan: (info) => tracer.startSpan(info.spanName, {
      attributes: info.attributes,
    }),
    endSpan: (info) => info.span.end(),
  },
};
```

</TabItem>
<TabItem value="go" label="Go">

```go
import "go.opentelemetry.io/otel"

tracer := otel.Tracer("anip")

hooks := &service.ANIPHooks{
    Tracing: &service.TracingHooks{
        StartSpan: func(info map[string]any) any {
            _, span := tracer.Start(context.Background(), info["span_name"].(string))
            return span
        },
        EndSpan: func(info map[string]any) {
            info["span"].(oteltrace.Span).End()
        },
    },
}
```

</TabItem>
<TabItem value="java" label="Java">

```java
var tracer = GlobalOpenTelemetry.getTracer("anip");

var hooks = new ANIPHooks().setTracing(new TracingHooks()
    .setStartSpan(info -> tracer.spanBuilder((String) info.get("span_name")).startSpan())
    .setEndSpan(info -> ((Span) info.get("span")).end())
);
```

</TabItem>
<TabItem value="csharp" label="C#">

```csharp
var tracer = TracerProvider.Default.GetTracer("anip");

var hooks = new AnipHooks {
    Tracing = new TracingHooks {
        StartSpan = info => tracer.StartActiveSpan((string)info["span_name"]),
        EndSpan = info => ((TelemetrySpan)info["span"]).End(),
    }
};
```

</TabItem>
</Tabs>

## Health endpoint

The runtime provides a `getHealth()` method that returns a cached snapshot of storage, checkpoint, retention, and aggregation state. Framework adapters expose this as `GET /-/health`:

```bash
curl http://localhost:9100/-/health
```

```json
{
  "status": "healthy",
  "storage": { "type": "sqlite", "connected": true },
  "checkpoint": { "last_sequence": 42, "last_created_at": "2026-03-28T10:00:00Z" },
  "retention": { "last_sweep_at": "2026-03-28T09:55:00Z", "deleted_count": 0 },
  "aggregation": { "pending_count": 0 }
}
```

Enable the health endpoint when mounting:

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

```python
mount_anip(app, service, health_endpoint=True)
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

```typescript
mountAnip(app, service, { healthEndpoint: true });
```

</TabItem>
<TabItem value="go" label="Go">

```go
httpapi.MountANIP(mux, svc)  // health endpoint included by default
```

</TabItem>
<TabItem value="java" label="Java">

```java
// Spring Boot: health endpoint auto-registered via AnipController
```

</TabItem>
<TabItem value="csharp" label="C#">

```csharp
// ASP.NET Core: health endpoint auto-registered via AddAnip()
```

</TabItem>
</Tabs>

## Diagnostics hook

The diagnostics hook catches errors from background workers (checkpoint scheduler, retention sweeper, aggregation flusher) that would otherwise be silently swallowed:

```python
hooks = ANIPHooks(
    diagnostics=DiagnosticsHooks(
        on_background_error=lambda info: sentry.capture_exception(
            info.get("error"),
            extra={"worker": info.get("worker"), "context": info.get("context")},
        ),
    ),
)
```

## Hook isolation

Hooks are isolated from correctness paths. If a hook callback throws an exception:

- The request or background operation completes normally
- The exception is logged (via diagnostics hook if registered, or stderr)
- No data is lost or corrupted

This means you can safely connect hooks to external systems (Datadog, Sentry, Prometheus, etc.) without risking service stability.

## Next steps

- **[Configuration](/docs/getting-started/configuration)** — Storage, auth, and trust setup
- **[Checkpoints & Trust](/docs/protocol/checkpoints-trust)** — What checkpoints verify
- **[Deployment guide](https://github.com/anip-protocol/anip/blob/main/docs/deployment-guide.md)** — Production deployment patterns
