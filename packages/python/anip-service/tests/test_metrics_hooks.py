"""Tests for metrics hook wiring in ANIPService.invoke()."""
from __future__ import annotations

import pytest
from anip_service import ANIPService, Capability, InvocationContext, ANIPError
from anip_service.hooks import ANIPHooks, MetricsHooks
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


def _error_cap() -> Capability:
    def handler(ctx: InvocationContext, params: dict) -> dict:
        raise ANIPError("handler_error", "intentional failure")

    return Capability(
        declaration=CapabilityDeclaration(
            name="fail",
            description="Always fails",
            contract_version="1.0",
            inputs=[],
            output=CapabilityOutput(type="object", fields=[]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["fail"],
        ),
        handler=handler,
    )


def _crash_cap() -> Capability:
    def handler(ctx: InvocationContext, params: dict) -> dict:
        raise RuntimeError("unexpected boom")

    return Capability(
        declaration=CapabilityDeclaration(
            name="crash",
            description="Throws unexpected error",
            contract_version="1.0",
            inputs=[],
            output=CapabilityOutput(type="object", fields=[]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["crash"],
        ),
        handler=handler,
    )


def _create_mock_metrics_hooks() -> tuple[dict[str, list], MetricsHooks]:
    """Create mock metrics hooks that record events into lists."""
    events: dict[str, list] = {
        "invocation_duration": [],
        "delegation_denied": [],
        "audit_append_duration": [],
        "checkpoint_created": [],
        "checkpoint_failed": [],
        "proof_generated": [],
        "proof_unavailable": [],
        "retention_deleted": [],
        "aggregation_flushed": [],
        "streaming_delivery_failure": [],
    }

    metrics = MetricsHooks(
        on_invocation_duration=lambda d: events["invocation_duration"].append(d),
        on_delegation_denied=lambda d: events["delegation_denied"].append(d),
        on_audit_append_duration=lambda d: events["audit_append_duration"].append(d),
        on_checkpoint_created=lambda d: events["checkpoint_created"].append(d),
        on_checkpoint_failed=lambda d: events["checkpoint_failed"].append(d),
        on_proof_generated=lambda d: events["proof_generated"].append(d),
        on_proof_unavailable=lambda d: events["proof_unavailable"].append(d),
        on_retention_deleted=lambda d: events["retention_deleted"].append(d),
        on_aggregation_flushed=lambda d: events["aggregation_flushed"].append(d),
        on_streaming_delivery_failure=lambda d: events["streaming_delivery_failure"].append(d),
    )

    return events, metrics


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
# Tests
# ---------------------------------------------------------------------------


class TestInvocationDurationSuccess:
    """on_invocation_duration fires on successful invocation."""

    async def test_fires_with_correct_payload(self):
        events, metrics = _create_mock_metrics_hooks()
        service = _make_service(hooks=ANIPHooks(metrics=metrics))

        token = await _issue_test_token(service)
        result = await service.invoke("greet", token, {"name": "World"})

        assert result["success"] is True

        assert len(events["invocation_duration"]) == 1
        dur = events["invocation_duration"][0]
        assert dur["capability"] == "greet"
        assert dur["success"] is True
        assert isinstance(dur["duration_ms"], int)
        assert dur["duration_ms"] >= 0


class TestInvocationDurationFailure:
    """on_invocation_duration fires on failed invocation."""

    async def test_fires_with_success_false_on_anip_error(self):
        events, metrics = _create_mock_metrics_hooks()
        service = _make_service(
            caps=[_error_cap()],
            hooks=ANIPHooks(metrics=metrics),
        )

        token = await _issue_test_token(service, scope=["fail"], capability="fail")
        result = await service.invoke("fail", token, {})

        assert result["success"] is False

        assert len(events["invocation_duration"]) == 1
        dur = events["invocation_duration"][0]
        assert dur["capability"] == "fail"
        assert dur["success"] is False
        assert isinstance(dur["duration_ms"], int)

    async def test_fires_with_success_false_on_unexpected_error(self):
        events, metrics = _create_mock_metrics_hooks()
        service = _make_service(
            caps=[_crash_cap()],
            hooks=ANIPHooks(metrics=metrics),
        )

        token = await _issue_test_token(service, scope=["crash"], capability="crash")
        result = await service.invoke("crash", token, {})

        assert result["success"] is False

        assert len(events["invocation_duration"]) == 1
        dur = events["invocation_duration"][0]
        assert dur["success"] is False


class TestDelegationDenied:
    """on_delegation_denied fires when delegation validation fails."""

    async def test_fires_on_scope_mismatch(self):
        events, metrics = _create_mock_metrics_hooks()
        service = _make_service(hooks=ANIPHooks(metrics=metrics))

        # Issue token with wrong scope
        token = await _issue_test_token(service, scope=["other"], capability="other")
        result = await service.invoke("greet", token, {"name": "World"})

        assert result["success"] is False

        assert len(events["delegation_denied"]) >= 1
        dd = events["delegation_denied"][0]
        assert isinstance(dd["reason"], str)

        # on_invocation_duration should also fire
        assert len(events["invocation_duration"]) == 1
        dur = events["invocation_duration"][0]
        assert dur["success"] is False


class TestAuditAppendDuration:
    """on_audit_append_duration fires after invocation."""

    async def test_fires_after_successful_invocation(self):
        events, metrics = _create_mock_metrics_hooks()
        service = _make_service(hooks=ANIPHooks(metrics=metrics))

        token = await _issue_test_token(service)
        await service.invoke("greet", token, {"name": "World"})

        assert len(events["audit_append_duration"]) >= 1
        audit = events["audit_append_duration"][0]
        assert isinstance(audit["duration_ms"], int)
        assert audit["duration_ms"] >= 0
        assert audit["success"] is True


class TestNoErrorsWhenMetricsHooksOmitted:
    """Invocation works fine without metrics hooks configured."""

    async def test_invocation_succeeds_without_hooks(self):
        service = _make_service()

        token = await _issue_test_token(service)
        result = await service.invoke("greet", token, {"name": "World"})

        assert result["success"] is True
        assert result["result"]["message"] == "Hello, World!"


class TestInvocationDurationUnknownCapability:
    """on_invocation_duration fires for unknown capability."""

    async def test_fires_with_success_false(self):
        events, metrics = _create_mock_metrics_hooks()
        service = _make_service(hooks=ANIPHooks(metrics=metrics))

        token = await _issue_test_token(service)
        result = await service.invoke("nonexistent", token, {})

        assert result["success"] is False

        assert len(events["invocation_duration"]) == 1
        dur = events["invocation_duration"][0]
        assert dur["capability"] == "nonexistent"
        assert dur["success"] is False
