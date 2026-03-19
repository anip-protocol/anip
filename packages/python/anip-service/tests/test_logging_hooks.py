"""Tests for logging hook wiring in ANIPService.invoke()."""
from __future__ import annotations

import pytest
from anip_service import ANIPService, Capability, InvocationContext, ANIPError
from anip_service.hooks import ANIPHooks, LoggingHooks
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


def _create_mock_hooks() -> tuple[dict[str, list], LoggingHooks]:
    """Create mock hooks that record events into lists."""
    events: dict[str, list] = {
        "invocation_start": [],
        "invocation_end": [],
        "delegation_failure": [],
        "audit_append": [],
        "checkpoint_created": [],
        "aggregation_flush": [],
        "streaming_summary": [],
    }

    logging = LoggingHooks(
        on_invocation_start=lambda d: events["invocation_start"].append(d),
        on_invocation_end=lambda d: events["invocation_end"].append(d),
        on_delegation_failure=lambda d: events["delegation_failure"].append(d),
        on_audit_append=lambda d: events["audit_append"].append(d),
        on_checkpoint_created=lambda d: events["checkpoint_created"].append(d),
        on_aggregation_flush=lambda d: events["aggregation_flush"].append(d),
        on_streaming_summary=lambda d: events["streaming_summary"].append(d),
    )

    return events, logging


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


class TestInvocationStartAndEndSuccess:
    """on_invocation_start and on_invocation_end fire on successful invocation."""

    async def test_both_hooks_fire_with_correct_payloads(self):
        events, logging = _create_mock_hooks()
        service = _make_service(hooks=ANIPHooks(logging=logging))

        token = await _issue_test_token(service)
        result = await service.invoke("greet", token, {"name": "World"})

        assert result["success"] is True

        # on_invocation_start
        assert len(events["invocation_start"]) == 1
        start = events["invocation_start"][0]
        assert start["capability"] == "greet"
        assert start["invocation_id"].startswith("inv-")
        assert start["client_reference_id"] is None
        assert start["root_principal"] == "human:test@example.com"
        assert start["subject"] == "human:test@example.com"
        assert isinstance(start["timestamp"], str)

        # on_invocation_end
        assert len(events["invocation_end"]) == 1
        end = events["invocation_end"][0]
        assert end["capability"] == "greet"
        assert end["invocation_id"] == start["invocation_id"]
        assert end["success"] is True
        assert end["failure_type"] is None
        assert isinstance(end["duration_ms"], int)
        assert end["duration_ms"] >= 0
        assert isinstance(end["timestamp"], str)


class TestInvocationEndHandlerError:
    """on_invocation_end fires with success=False on ANIPError."""

    async def test_fires_with_correct_failure_type(self):
        events, logging = _create_mock_hooks()
        service = _make_service(
            caps=[_error_cap()],
            hooks=ANIPHooks(logging=logging),
        )

        token = await _issue_test_token(service, scope=["fail"], capability="fail")
        result = await service.invoke("fail", token, {})

        assert result["success"] is False

        # on_invocation_start should fire (context was built before handler)
        assert len(events["invocation_start"]) == 1

        # on_invocation_end
        assert len(events["invocation_end"]) == 1
        end = events["invocation_end"][0]
        assert end["success"] is False
        assert end["failure_type"] == "handler_error"
        assert isinstance(end["duration_ms"], int)


class TestInvocationEndInternalError:
    """on_invocation_end fires with failure_type=internal_error for non-ANIPError."""

    async def test_fires_with_internal_error(self):
        events, logging = _create_mock_hooks()
        service = _make_service(
            caps=[_crash_cap()],
            hooks=ANIPHooks(logging=logging),
        )

        token = await _issue_test_token(service, scope=["crash"], capability="crash")
        result = await service.invoke("crash", token, {})

        assert result["success"] is False

        assert len(events["invocation_end"]) == 1
        end = events["invocation_end"][0]
        assert end["success"] is False
        assert end["failure_type"] == "internal_error"


class TestNoErrorsWhenHooksOmitted:
    """Invocation works fine without hooks configured."""

    async def test_invocation_succeeds_without_hooks(self):
        service = _make_service()

        token = await _issue_test_token(service)
        result = await service.invoke("greet", token, {"name": "World"})

        assert result["success"] is True
        assert result["result"]["message"] == "Hello, World!"


class TestAuditAppendHook:
    """on_audit_append fires after invocation."""

    async def test_fires_after_successful_invocation(self):
        events, logging = _create_mock_hooks()
        service = _make_service(hooks=ANIPHooks(logging=logging))

        token = await _issue_test_token(service)
        await service.invoke("greet", token, {"name": "World"})

        assert len(events["audit_append"]) >= 1
        audit = events["audit_append"][0]
        assert audit["capability"] == "greet"
        assert audit["success"] is True
        assert isinstance(audit["sequence_number"], int)
        assert isinstance(audit["invocation_id"], str)
        assert isinstance(audit["timestamp"], str)

    async def test_fires_after_failed_invocation(self):
        events, logging = _create_mock_hooks()
        service = _make_service(
            caps=[_error_cap()],
            hooks=ANIPHooks(logging=logging),
        )

        token = await _issue_test_token(service, scope=["fail"], capability="fail")
        await service.invoke("fail", token, {})

        assert len(events["audit_append"]) >= 1
        audit = events["audit_append"][0]
        assert audit["capability"] == "fail"
        assert audit["success"] is False


class TestUnknownCapabilityHook:
    """on_invocation_end fires with failure_type=unknown_capability."""

    async def test_fires_for_unknown_capability(self):
        events, logging = _create_mock_hooks()
        service = _make_service(hooks=ANIPHooks(logging=logging))

        token = await _issue_test_token(service)
        result = await service.invoke("nonexistent", token, {})

        assert result["success"] is False

        # on_invocation_start should NOT fire (no context built)
        assert len(events["invocation_start"]) == 0

        # on_invocation_end should fire
        assert len(events["invocation_end"]) == 1
        end = events["invocation_end"][0]
        assert end["capability"] == "nonexistent"
        assert end["success"] is False
        assert end["failure_type"] == "unknown_capability"


class TestDelegationFailureHook:
    """on_delegation_failure fires when token validation fails."""

    async def test_fires_on_scope_mismatch(self):
        events, logging = _create_mock_hooks()
        service = _make_service(hooks=ANIPHooks(logging=logging))

        # Issue token with wrong scope
        token = await _issue_test_token(service, scope=["other"], capability="other")
        result = await service.invoke("greet", token, {"name": "World"})

        assert result["success"] is False

        assert len(events["delegation_failure"]) >= 1
        df = events["delegation_failure"][0]
        assert isinstance(df["reason"], str)
        assert isinstance(df["timestamp"], str)

        # on_invocation_end should also fire
        assert len(events["invocation_end"]) == 1
        end = events["invocation_end"][0]
        assert end["success"] is False


class TestClientReferenceIdPropagation:
    """client_reference_id is passed through to on_invocation_start."""

    async def test_passes_client_reference_id(self):
        events, logging = _create_mock_hooks()
        service = _make_service(hooks=ANIPHooks(logging=logging))

        token = await _issue_test_token(service)
        await service.invoke(
            "greet", token, {"name": "World"},
            client_reference_id="ref-123",
        )

        start = events["invocation_start"][0]
        assert start["client_reference_id"] == "ref-123"
