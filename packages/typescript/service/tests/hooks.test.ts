import { describe, it, expect } from "vitest";
import type {
  ANIPHooks,
  LoggingHooks,
  MetricsHooks,
  TracingHooks,
  DiagnosticsHooks,
  HealthReport,
} from "../src/hooks.js";

describe("ANIPHooks type definitions", () => {
  it("accepts a fully populated hooks object", () => {
    const hooks: ANIPHooks = {
      logging: {
        onInvocationStart(event) {
          void event.capability;
          void event.invocationId;
          void event.clientReferenceId;
          void event.rootPrincipal;
          void event.subject;
          void event.timestamp;
        },
        onInvocationEnd(event) {
          void event.capability;
          void event.invocationId;
          void event.success;
          void event.failureType;
          void event.durationMs;
          void event.timestamp;
        },
        onDelegationFailure(event) {
          void event.reason;
          void event.tokenId;
          void event.timestamp;
        },
        onAuditAppend(event) {
          void event.sequenceNumber;
          void event.capability;
          void event.invocationId;
          void event.success;
          void event.timestamp;
        },
        onCheckpointCreated(event) {
          void event.checkpointId;
          void event.entryCount;
          void event.merkleRoot;
          void event.timestamp;
        },
        onRetentionSweep(event) {
          void event.deletedCount;
          void event.durationMs;
          void event.timestamp;
        },
        onAggregationFlush(event) {
          void event.windowCount;
          void event.entriesFlushed;
          void event.timestamp;
        },
        onStreamingSummary(event) {
          void event.invocationId;
          void event.capability;
          void event.eventsEmitted;
          void event.eventsDelivered;
          void event.clientDisconnected;
          void event.durationMs;
          void event.timestamp;
        },
      },
      metrics: {
        onInvocationDuration(event) {
          void event.capability;
          void event.durationMs;
          void event.success;
        },
        onDelegationDenied(event) {
          void event.reason;
        },
        onAuditAppendDuration(event) {
          void event.durationMs;
          void event.success;
        },
        onCheckpointCreated(event) {
          void event.lagSeconds;
        },
        onCheckpointFailed(event) {
          void event.error;
        },
        onProofGenerated(event) {
          void event.durationMs;
        },
        onProofUnavailable(event) {
          void event.reason;
        },
        onRetentionDeleted(event) {
          void event.count;
        },
        onAggregationFlushed(event) {
          void event.windowCount;
        },
        onStreamingDeliveryFailure(event) {
          void event.capability;
        },
      },
      tracing: {
        startSpan(event) {
          void event.name;
          void event.attributes;
          void event.parentSpan;
          return { spanId: "abc" };
        },
        endSpan(event) {
          void event.span;
          void event.status;
          void event.errorType;
          void event.errorMessage;
          void event.attributes;
        },
      },
      diagnostics: {
        onBackgroundError(event) {
          void event.source;
          void event.error;
          void event.timestamp;
        },
      },
    };

    expect(hooks.logging).toBeDefined();
    expect(hooks.metrics).toBeDefined();
    expect(hooks.tracing).toBeDefined();
    expect(hooks.diagnostics).toBeDefined();
  });

  it("accepts an empty hooks object", () => {
    const hooks: ANIPHooks = {};

    expect(hooks.logging).toBeUndefined();
    expect(hooks.metrics).toBeUndefined();
    expect(hooks.tracing).toBeUndefined();
    expect(hooks.diagnostics).toBeUndefined();
  });

  it("accepts partial hooks — only logging with only onInvocationStart", () => {
    const hooks: ANIPHooks = {
      logging: {
        onInvocationStart(event) {
          void event.capability;
        },
      },
    };

    expect(hooks.logging).toBeDefined();
    expect(hooks.logging!.onInvocationStart).toBeDefined();
    expect(hooks.logging!.onInvocationEnd).toBeUndefined();
    expect(hooks.metrics).toBeUndefined();
  });
});

describe("HealthReport type definition", () => {
  it("accepts a fully populated health report", () => {
    const report: HealthReport = {
      status: "healthy",
      storage: { type: "sqlite" },
      checkpoint: {
        healthy: true,
        lastRunAt: "2026-03-18T00:00:00Z",
        lagSeconds: 5,
      },
      retention: {
        healthy: true,
        lastRunAt: "2026-03-18T00:00:00Z",
        lastDeletedCount: 10,
      },
      aggregation: { pendingWindows: 2 },
    };

    expect(report.status).toBe("healthy");
    expect(report.checkpoint).not.toBeNull();
    expect(report.aggregation).not.toBeNull();
  });

  it("accepts nullable checkpoint and aggregation", () => {
    const report: HealthReport = {
      status: "degraded",
      storage: { type: "memory" },
      checkpoint: null,
      retention: {
        healthy: false,
        lastRunAt: null,
        lastDeletedCount: 0,
      },
      aggregation: null,
    };

    expect(report.status).toBe("degraded");
    expect(report.checkpoint).toBeNull();
    expect(report.aggregation).toBeNull();
  });
});
