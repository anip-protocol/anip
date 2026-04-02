"""Tests for upstream_service support in invoke request/response/audit (v0.18)."""
import pytest
from anip_service import ANIPService, Capability, InvocationContext
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    SideEffect, SideEffectType,
)


def _echo_cap():
    return Capability(
        declaration=CapabilityDeclaration(
            name="echo",
            description="Echo input",
            inputs=[CapabilityInput(name="msg", type="string", required=True, description="msg")],
            output=CapabilityOutput(type="object", fields=["msg"]),
            side_effect=SideEffect(type=SideEffectType.READ),
            minimum_scope=["echo"],
        ),
        handler=lambda ctx, params: {"msg": params["msg"]},
    )


@pytest.fixture
def service():
    return ANIPService(
        service_id="test-upstream-service",
        capabilities=[_echo_cap()],
        storage=":memory:",
    )


async def _issue_token(service, scope, capability):
    result = await service._engine.issue_root_token(
        authenticated_principal="human:test@example.com",
        subject="human:test@example.com",
        scope=scope,
        capability=capability,
        ttl_hours=1,
    )
    token, token_id = result
    return token


# --- test_upstream_service_echoed_in_response ---

async def test_upstream_service_echoed_in_response(service):
    """upstream_service passed in request is echoed in response."""
    token = await _issue_token(service, ["echo"], "echo")
    result = await service.invoke(
        "echo", token, {"msg": "hello"},
        upstream_service="billing-service",
    )
    assert result["success"] is True
    assert result["upstream_service"] == "billing-service"


# --- test_upstream_service_in_audit ---

async def test_upstream_service_in_audit(service):
    """upstream_service is recorded in audit entries."""
    token = await _issue_token(service, ["echo"], "echo")
    await service.invoke(
        "echo", token, {"msg": "hello"},
        upstream_service="billing-service",
    )
    result = await service.query_audit(token, {})
    entries = result["entries"]
    assert len(entries) >= 1
    assert entries[0].get("upstream_service") == "billing-service"


# --- test_upstream_service_optional ---

async def test_upstream_service_optional(service):
    """Invoking without upstream_service succeeds and returns None/absent."""
    token = await _issue_token(service, ["echo"], "echo")
    result = await service.invoke(
        "echo", token, {"msg": "world"},
    )
    assert result["success"] is True
    # upstream_service should be absent or None when not provided
    assert result.get("upstream_service") is None
