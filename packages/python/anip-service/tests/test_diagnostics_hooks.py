"""Tests for diagnostics hooks and background callback wiring."""
from __future__ import annotations

import asyncio

import pytest
from anip_server import InMemoryStorage, RetentionEnforcer
from anip_service import ANIPService, Capability, InvocationContext
from anip_service.hooks import ANIPHooks, DiagnosticsHooks, LoggingHooks, MetricsHooks
from anip_core import (
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    SideEffect,
    SideEffectType,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _test_cap(name: str = "greet", scope: list[str] | None = None) -> Capability:
    return Capability(
        declaration=CapabilityDeclaration(
            name=name,
            description="Say hello",
            contract_version="1.0",
            inputs=[CapabilityInput(name="name", type="string", required=True, description="Who to greet")],
            output=CapabilityOutput(type="object", fields=["message"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=scope or ["greet"],
        ),
        handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
    )


def _make_service(
    caps: list[Capability] | None = None,
    hooks: ANIPHooks | None = None,
) -> ANIPService:
    return ANIPService(
        service_id="test-service",
        capabilities=caps or [_test_cap()],
        storage=":memory:",
        hooks=hooks,
    )


async def _issue_test_token(service: ANIPService, scope: list[str] | None = None, capability: str | None = None):
    """Helper to issue a root token for testing."""
    cap = capability or "greet"
    result = await service._engine.issue_root_token(
        authenticated_principal="human:test@example.com",
        subject="human:test@example.com",
        scope=scope or ["greet"],
        capability=cap,
        purpose_parameters={"task_id": "test"},
        ttl_hours=1,
    )
    token, _ = result
    return token


# ---------------------------------------------------------------------------
# Part 1: RetentionEnforcer unit-level tests
# ---------------------------------------------------------------------------


class TestRetentionEnforcerOnSweep:
    """on_sweep callback fires on successful sweep."""

    async def test_fires_with_count_and_duration(self):
        storage = InMemoryStorage()
        sweep_results: list[tuple[int, float]] = []

        enforcer = RetentionEnforcer(
            storage,
            interval_seconds=1,
            on_sweep=lambda count, dur: sweep_results.append((count, dur)),
        )

        # Direct sweep doesn't fire the callback (only _run loop does)
        count = await enforcer.sweep()
        assert count == 0

        # Use a very short interval for background loop testing
        enforcer2 = RetentionEnforcer(
            storage,
            interval_seconds=0,  # will sleep 0
            on_sweep=lambda count, dur: sweep_results.append((count, dur)),
        )

        enforcer2.start()
        await asyncio.sleep(0.05)
        enforcer2.stop()

        assert len(sweep_results) >= 1
        deleted_count, duration_ms = sweep_results[0]
        assert deleted_count == 0
        assert isinstance(duration_ms, float)
        assert duration_ms >= 0


class TestRetentionEnforcerOnError:
    """on_error callback fires when sweep throws."""

    async def test_fires_on_storage_error(self):
        error_messages: list[str] = []
        storage = InMemoryStorage()

        # Monkey-patch to make sweep fail
        async def _bad_delete(now: str) -> int:
            raise RuntimeError("storage failure")

        storage.delete_expired_audit_entries = _bad_delete  # type: ignore[assignment]

        enforcer = RetentionEnforcer(
            storage,
            interval_seconds=0,
            on_error=lambda err: error_messages.append(err),
        )

        enforcer.start()
        await asyncio.sleep(0.05)
        enforcer.stop()

        assert len(error_messages) >= 1
        assert "storage failure" in error_messages[0]


# ---------------------------------------------------------------------------
# Part 2: Service-level hook wiring tests
# ---------------------------------------------------------------------------


class TestDiagnosticsBackgroundErrorRetention:
    """on_background_error fires with source=retention on retention errors."""

    async def test_fires_via_enforcer_wiring(self):
        errors: list[dict] = []

        # We test the callback wiring by constructing a RetentionEnforcer
        # directly with the same pattern the service uses.
        storage = InMemoryStorage()

        async def _bad_delete(now: str) -> int:
            raise RuntimeError("retention boom")

        storage.delete_expired_audit_entries = _bad_delete  # type: ignore[assignment]

        enforcer = RetentionEnforcer(
            storage,
            interval_seconds=0,
            on_error=lambda err: errors.append({"source": "retention", "error": err}),
        )

        enforcer.start()
        await asyncio.sleep(0.05)
        enforcer.stop()

        assert len(errors) >= 1
        assert errors[0]["source"] == "retention"
        assert "retention boom" in errors[0]["error"]


class TestLoggingRetentionSweep:
    """on_retention_sweep logging hook fires on successful sweep."""

    async def test_fires_via_enforcer_on_sweep(self):
        sweep_events: list[dict] = []
        storage = InMemoryStorage()

        enforcer = RetentionEnforcer(
            storage,
            interval_seconds=0,
            on_sweep=lambda count, dur: sweep_events.append({
                "deleted_count": count,
                "duration_ms": dur,
            }),
        )

        enforcer.start()
        await asyncio.sleep(0.05)
        enforcer.stop()

        assert len(sweep_events) >= 1
        evt = sweep_events[0]
        assert isinstance(evt["deleted_count"], int)
        assert isinstance(evt["duration_ms"], float)


class TestMetricsRetentionDeleted:
    """on_retention_deleted metrics hook fires on successful sweep."""

    async def test_fires_via_enforcer_on_sweep(self):
        metric_events: list[dict] = []
        storage = InMemoryStorage()

        enforcer = RetentionEnforcer(
            storage,
            interval_seconds=0,
            on_sweep=lambda count, dur: metric_events.append({"count": count}),
        )

        enforcer.start()
        await asyncio.sleep(0.05)
        enforcer.stop()

        assert len(metric_events) >= 1
        assert isinstance(metric_events[0]["count"], int)


class TestDiagnosticsNoErrorsWhenOmitted:
    """Service works fine without diagnostics hooks configured."""

    async def test_invocation_succeeds_without_hooks(self):
        service = _make_service()

        token = await _issue_test_token(service)
        result = await service.invoke("greet", token, {"name": "World"})

        assert result["success"] is True
        assert result["result"]["message"] == "Hello, World!"


class TestServiceRetentionHookWiring:
    """Service layer correctly wires retention hooks to RetentionEnforcer."""

    async def test_on_retention_sweep_method_calls_logging_and_metrics(self):
        log_events: list[dict] = []
        metric_events: list[dict] = []

        hooks = ANIPHooks(
            logging=LoggingHooks(
                on_retention_sweep=lambda d: log_events.append(d),
            ),
            metrics=MetricsHooks(
                on_retention_deleted=lambda d: metric_events.append(d),
            ),
        )

        service = _make_service(hooks=hooks)

        # Call the helper method directly to verify wiring
        service._on_retention_sweep(5, 12.3)

        assert len(log_events) == 1
        assert log_events[0]["deleted_count"] == 5
        assert log_events[0]["duration_ms"] == 12.3
        assert "timestamp" in log_events[0]

        assert len(metric_events) == 1
        assert metric_events[0]["count"] == 5

    async def test_on_retention_error_method_calls_diagnostics(self):
        errors: list[dict] = []

        hooks = ANIPHooks(
            diagnostics=DiagnosticsHooks(
                on_background_error=lambda d: errors.append(d),
            ),
        )

        service = _make_service(hooks=hooks)

        # Call the helper method directly
        service._on_retention_error("test error")

        assert len(errors) == 1
        assert errors[0]["source"] == "retention"
        assert errors[0]["error"] == "test error"
        assert "timestamp" in errors[0]

    async def test_on_checkpoint_error_method_calls_diagnostics(self):
        errors: list[dict] = []

        hooks = ANIPHooks(
            diagnostics=DiagnosticsHooks(
                on_background_error=lambda d: errors.append(d),
            ),
        )

        service = _make_service(hooks=hooks)

        # Call the helper method directly
        service._on_checkpoint_error("checkpoint failed")

        assert len(errors) == 1
        assert errors[0]["source"] == "checkpoint"
        assert errors[0]["error"] == "checkpoint failed"
        assert "timestamp" in errors[0]
