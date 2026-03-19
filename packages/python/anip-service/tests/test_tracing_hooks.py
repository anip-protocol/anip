"""Tests for tracing hook wiring in ANIPService.invoke()."""
from __future__ import annotations

import pytest
from anip_service import ANIPService, Capability, InvocationContext, ANIPError
from anip_service.hooks import ANIPHooks, TracingHooks
from anip_core import (
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    SideEffect,
    SideEffectType,
)
from typing import Any


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


def _create_mock_tracing_hooks() -> tuple[list[dict], list[dict], TracingHooks]:
    """Create mock tracing hooks that record events into lists."""
    started: list[dict] = []
    ended: list[dict] = []
    counter = [0]

    def start_span(event: dict) -> dict:
        counter[0] += 1
        span = {"id": counter[0], "name": event["name"]}
        started.append(event)
        return span

    def end_span(event: dict) -> None:
        ended.append(event)

    tracing = TracingHooks(start_span=start_span, end_span=end_span)
    return started, ended, tracing


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


class TestTracingHooksSuccessfulInvocation:
    """Tracing spans fire on successful invocation."""

    async def test_fires_correct_spans(self):
        started, ended, tracing = _create_mock_tracing_hooks()
        service = _make_service(hooks=ANIPHooks(tracing=tracing))

        token = await _issue_test_token(service)
        result = await service.invoke("greet", token, {"name": "World"})

        assert result["success"] is True

        span_names = [s["name"] for s in started]
        assert "anip.invoke" in span_names
        assert "anip.delegation.validate" in span_names
        assert "anip.handler.execute" in span_names
        assert "anip.audit.append" in span_names

        # All spans should end with status "ok"
        assert len(ended) == len(started)
        for e in ended:
            assert e["status"] == "ok"

        # Check anip.invoke attributes
        invoke_start = next(s for s in started if s["name"] == "anip.invoke")
        assert invoke_start["attributes"]["capability"] == "greet"


class TestTracingHooksHandlerError:
    """endSpan fires with error status on handler failure."""

    async def test_anip_error_handler(self):
        started, ended, tracing = _create_mock_tracing_hooks()
        service = _make_service(
            caps=[_error_cap()],
            hooks=ANIPHooks(tracing=tracing),
        )

        token = await _issue_test_token(service, scope=["fail"], capability="fail")
        result = await service.invoke("fail", token, {})

        assert result["success"] is False

        # anip.handler.execute should have ended with error
        handler_end = next(
            (e for e in ended if e["span"]["name"] == "anip.handler.execute"),
            None,
        )
        assert handler_end is not None
        assert handler_end["status"] == "error"
        assert handler_end["error_type"] == "ANIPError"
        assert "intentional failure" in handler_end["error_message"]

        # anip.invoke root span should still end ok
        invoke_end = next(
            (e for e in ended if e["span"]["name"] == "anip.invoke"),
            None,
        )
        assert invoke_end is not None
        assert invoke_end["status"] == "ok"

    async def test_unexpected_error_handler(self):
        started, ended, tracing = _create_mock_tracing_hooks()
        service = _make_service(
            caps=[_crash_cap()],
            hooks=ANIPHooks(tracing=tracing),
        )

        token = await _issue_test_token(service, scope=["crash"], capability="crash")
        result = await service.invoke("crash", token, {})

        assert result["success"] is False

        handler_end = next(
            (e for e in ended if e["span"]["name"] == "anip.handler.execute"),
            None,
        )
        assert handler_end is not None
        assert handler_end["status"] == "error"
        assert handler_end["error_type"] == "RuntimeError"
        assert handler_end["error_message"] == "unexpected boom"


class TestTracingHooksSpanNesting:
    """Inner spans receive parentSpan from anip.invoke root span."""

    async def test_inner_spans_have_parent(self):
        started, ended, tracing = _create_mock_tracing_hooks()
        service = _make_service(hooks=ANIPHooks(tracing=tracing))

        token = await _issue_test_token(service)
        await service.invoke("greet", token, {"name": "World"})

        # Root span has no parent_span (or None)
        invoke_start = next(s for s in started if s["name"] == "anip.invoke")
        assert invoke_start.get("parent_span") is None

        # Inner spans should have parent_span set to the root span object
        handler_start = next(s for s in started if s["name"] == "anip.handler.execute")
        assert handler_start["parent_span"] is not None
        assert handler_start["parent_span"]["name"] == "anip.invoke"

        audit_start = next(s for s in started if s["name"] == "anip.audit.append")
        assert audit_start["parent_span"] is not None
        assert audit_start["parent_span"]["name"] == "anip.invoke"

        deleg_start = next(s for s in started if s["name"] == "anip.delegation.validate")
        assert deleg_start["parent_span"] is not None
        assert deleg_start["parent_span"]["name"] == "anip.invoke"


class TestTracingHooksOmitted:
    """Invocation works fine without tracing hooks configured."""

    async def test_invocation_succeeds_without_hooks(self):
        service = _make_service()

        token = await _issue_test_token(service)
        result = await service.invoke("greet", token, {"name": "World"})

        assert result["success"] is True
        assert result["result"]["message"] == "Hello, World!"


class TestTracingHooksDelegationFailure:
    """Tracing spans fire on delegation failure."""

    async def test_fires_invoke_and_delegation_spans(self):
        started, ended, tracing = _create_mock_tracing_hooks()
        service = _make_service(hooks=ANIPHooks(tracing=tracing))

        token = await _issue_test_token(service, scope=["other"], capability="other")
        result = await service.invoke("greet", token, {"name": "World"})

        assert result["success"] is False

        span_names = [s["name"] for s in started]
        assert "anip.invoke" in span_names
        assert "anip.delegation.validate" in span_names
        # audit should also be traced
        assert "anip.audit.append" in span_names

        # Root span should end ok
        invoke_end = next(
            (e for e in ended if e["span"]["name"] == "anip.invoke"),
            None,
        )
        assert invoke_end is not None
        assert invoke_end["status"] == "ok"


class TestTracingHooksUnknownCapability:
    """Root span fires for unknown capability."""

    async def test_fires_invoke_span(self):
        started, ended, tracing = _create_mock_tracing_hooks()
        service = _make_service(hooks=ANIPHooks(tracing=tracing))

        token = await _issue_test_token(service)
        result = await service.invoke("nonexistent", token, {})

        assert result["success"] is False

        span_names = [s["name"] for s in started]
        assert "anip.invoke" in span_names

        invoke_end = next(
            (e for e in ended if e["span"]["name"] == "anip.invoke"),
            None,
        )
        assert invoke_end is not None
        assert invoke_end["status"] == "ok"
