"""Tests for observability hook type definitions."""
from __future__ import annotations

from anip_service.hooks import (
    ANIPHooks,
    DiagnosticsHooks,
    HealthReport,
    LoggingHooks,
    MetricsHooks,
    TracingHooks,
)


def test_fully_populated_hooks() -> None:
    """All hook slots filled with no-op callbacks."""
    logging = LoggingHooks(
        on_invocation_start=lambda d: None,
        on_invocation_end=lambda d: None,
        on_delegation_failure=lambda d: None,
        on_audit_append=lambda d: None,
        on_checkpoint_created=lambda d: None,
        on_retention_sweep=lambda d: None,
        on_aggregation_flush=lambda d: None,
        on_streaming_summary=lambda d: None,
    )
    metrics = MetricsHooks(
        on_invocation_duration=lambda d: None,
        on_delegation_denied=lambda d: None,
        on_audit_append_duration=lambda d: None,
        on_checkpoint_created=lambda d: None,
        on_checkpoint_failed=lambda d: None,
        on_proof_generated=lambda d: None,
        on_proof_unavailable=lambda d: None,
        on_retention_deleted=lambda d: None,
        on_aggregation_flushed=lambda d: None,
        on_streaming_delivery_failure=lambda d: None,
    )
    tracing = TracingHooks(
        start_span=lambda d: {"span_id": "abc"},
        end_span=lambda d: None,
    )
    diagnostics = DiagnosticsHooks(
        on_background_error=lambda d: None,
    )

    hooks = ANIPHooks(
        logging=logging,
        metrics=metrics,
        tracing=tracing,
        diagnostics=diagnostics,
    )

    assert hooks.logging is logging
    assert hooks.metrics is metrics
    assert hooks.tracing is tracing
    assert hooks.diagnostics is diagnostics

    # Verify callbacks are callable
    assert hooks.logging is not None
    assert hooks.logging.on_invocation_start is not None
    hooks.logging.on_invocation_start({"test": True})

    assert hooks.tracing is not None
    assert hooks.tracing.start_span is not None
    result = hooks.tracing.start_span({"name": "test"})
    assert result == {"span_id": "abc"}


def test_empty_hooks() -> None:
    """Default-constructed hooks have all slots as None."""
    hooks = ANIPHooks()

    assert hooks.logging is None
    assert hooks.metrics is None
    assert hooks.tracing is None
    assert hooks.diagnostics is None

    logging = LoggingHooks()
    assert logging.on_invocation_start is None
    assert logging.on_invocation_end is None
    assert logging.on_delegation_failure is None
    assert logging.on_audit_append is None
    assert logging.on_checkpoint_created is None
    assert logging.on_retention_sweep is None
    assert logging.on_aggregation_flush is None
    assert logging.on_streaming_summary is None

    metrics = MetricsHooks()
    assert metrics.on_invocation_duration is None
    assert metrics.on_delegation_denied is None
    assert metrics.on_audit_append_duration is None
    assert metrics.on_checkpoint_created is None
    assert metrics.on_checkpoint_failed is None
    assert metrics.on_proof_generated is None
    assert metrics.on_proof_unavailable is None
    assert metrics.on_retention_deleted is None
    assert metrics.on_aggregation_flushed is None
    assert metrics.on_streaming_delivery_failure is None

    tracing = TracingHooks()
    assert tracing.start_span is None
    assert tracing.end_span is None

    diagnostics = DiagnosticsHooks()
    assert diagnostics.on_background_error is None


def test_partial_hooks_logging_only() -> None:
    """Hooks with only a logging sub-object and a single callback."""
    calls: list[dict] = []

    hooks = ANIPHooks(
        logging=LoggingHooks(
            on_invocation_start=lambda d: calls.append(d),
        ),
    )

    assert hooks.logging is not None
    assert hooks.metrics is None
    assert hooks.tracing is None
    assert hooks.diagnostics is None

    assert hooks.logging.on_invocation_start is not None
    assert hooks.logging.on_invocation_end is None

    hooks.logging.on_invocation_start({"capability": "summarize", "caller": "alice"})
    assert len(calls) == 1
    assert calls[0]["capability"] == "summarize"


def test_health_report() -> None:
    """HealthReport can be constructed with required fields."""
    report = HealthReport(
        status="healthy",
        storage={"ok": True},
        checkpoint=None,
        retention={"ok": True},
        aggregation=None,
    )

    assert report.status == "healthy"
    assert report.storage == {"ok": True}
    assert report.checkpoint is None
    assert report.retention == {"ok": True}
    assert report.aggregation is None

    degraded = HealthReport(
        status="degraded",
        storage={"ok": True, "latency_ms": 500},
        checkpoint={"last": "2025-01-01T00:00:00Z"},
        retention={"ok": True},
        aggregation={"pending": 42},
    )

    assert degraded.status == "degraded"
    assert degraded.checkpoint is not None
    assert degraded.aggregation is not None
    assert degraded.aggregation["pending"] == 42
