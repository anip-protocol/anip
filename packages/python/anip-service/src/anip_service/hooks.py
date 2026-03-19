"""Observability hook types for the ANIP service runtime."""
from __future__ import annotations

from dataclasses import dataclass
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
