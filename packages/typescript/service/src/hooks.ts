/**
 * ANIP v0.11 — Observability hook type definitions.
 *
 * Callback-based injection points for logging, metrics, tracing, and
 * diagnostics.  Every callback is optional; absent hooks are silent.
 */

// ---------------------------------------------------------------------------
// hooks.logging — Structured Logging Hooks
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
// hooks.metrics — Metrics Hooks
// ---------------------------------------------------------------------------

export interface MetricsHooks {
  onInvocationDuration?(event: {
    capability: string;
    durationMs: number;
    success: boolean;
  }): void;

  onDelegationDenied?(event: { reason: string }): void;

  onAuditAppendDuration?(event: {
    durationMs: number;
    success: boolean;
  }): void;

  onCheckpointCreated?(event: { lagSeconds: number }): void;

  onCheckpointFailed?(event: { error: string }): void;

  onProofGenerated?(event: { durationMs: number }): void;

  onProofUnavailable?(event: { reason: string }): void;

  onRetentionDeleted?(event: { count: number }): void;

  onAggregationFlushed?(event: { windowCount: number }): void;

  onStreamingDeliveryFailure?(event: { capability: string }): void;
}

// ---------------------------------------------------------------------------
// hooks.tracing — Tracing Hooks
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
// hooks.diagnostics — Background Failure Signals
// ---------------------------------------------------------------------------

export interface DiagnosticsHooks {
  onBackgroundError?(event: {
    source: "checkpoint" | "retention" | "aggregation";
    error: string;
    timestamp: string;
  }): void;
}

// ---------------------------------------------------------------------------
// ANIPHooks — Top-level container
// ---------------------------------------------------------------------------

export interface ANIPHooks {
  logging?: LoggingHooks;
  metrics?: MetricsHooks;
  tracing?: TracingHooks;
  diagnostics?: DiagnosticsHooks;
}

// ---------------------------------------------------------------------------
// HealthReport — Pull-based diagnostics
// ---------------------------------------------------------------------------

export interface HealthReport {
  status: "healthy" | "degraded" | "unhealthy";
  storage: { type: string };
  checkpoint: {
    healthy: boolean;
    lastRunAt: string | null;
    lagSeconds: number | null;
  } | null;
  retention: {
    healthy: boolean;
    lastRunAt: string | null;
    lastDeletedCount: number;
  };
  aggregation: { pendingWindows: number } | null;
}
