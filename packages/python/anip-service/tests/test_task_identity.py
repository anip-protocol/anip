"""Tests for task_id and parent_invocation_id support (v0.12)."""
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
        service_id="test-task-identity",
        capabilities=[_echo_cap()],
        storage=":memory:",
    )


async def _issue_token(service, scope, capability):
    """Issue a root token; returns (token, token_purpose_task_id)."""
    result = await service._engine.issue_root_token(
        authenticated_principal="human:test@example.com",
        subject="human:test@example.com",
        scope=scope,
        capability=capability,
        purpose_parameters={"task_id": "test"},
        ttl_hours=1,
    )
    token, token_id = result
    return token


# --- test_invoke_with_task_id ---

async def test_invoke_with_task_id(service):
    """task_id passed in request is echoed in response when it matches token."""
    token = await _issue_token(service, ["echo"], "echo")
    # Use the token's own task_id so there's no mismatch
    token_task_id = token.purpose.task_id
    result = await service.invoke(
        "echo", token, {"msg": "hello"},
        task_id=token_task_id,
    )
    assert result["success"] is True
    assert result["task_id"] == token_task_id


# --- test_invoke_with_parent_invocation_id ---

async def test_invoke_with_parent_invocation_id(service):
    """parent_invocation_id passed in request is echoed in response."""
    token = await _issue_token(service, ["echo"], "echo")
    result = await service.invoke(
        "echo", token, {"msg": "hello"},
        parent_invocation_id="inv-aabbccddeeff",
    )
    assert result["success"] is True
    assert result["parent_invocation_id"] == "inv-aabbccddeeff"


# --- test_task_id_from_token_purpose ---

async def test_task_id_from_token_purpose(service):
    """When request omits task_id, token purpose.task_id is used."""
    token = await _issue_token(service, ["echo"], "echo")
    result = await service.invoke(
        "echo", token, {"msg": "hello"},
    )
    assert result["success"] is True
    # Should use the auto-generated task_id from the token purpose
    assert result["task_id"] == token.purpose.task_id


# --- test_task_id_mismatch_rejected ---

async def test_task_id_mismatch_rejected(service):
    """Mismatched request task_id vs token purpose.task_id returns purpose_mismatch."""
    token = await _issue_token(service, ["echo"], "echo")
    token_task_id = token.purpose.task_id
    result = await service.invoke(
        "echo", token, {"msg": "hello"},
        task_id="completely-different-task",
    )
    assert result["success"] is False
    assert result["failure"]["type"] == "purpose_mismatch"
    assert token_task_id in result["failure"]["detail"]
    assert "completely-different-task" in result["failure"]["detail"]
    assert result["task_id"] == "completely-different-task"


# --- test_audit_query_by_task_id ---

async def test_audit_query_by_task_id(service):
    """Audit entries can be filtered by task_id."""
    token1 = await _issue_token(service, ["echo"], "echo")
    task_id_1 = token1.purpose.task_id
    await service.invoke("echo", token1, {"msg": "a"}, task_id=task_id_1)

    token2 = await _issue_token(service, ["echo"], "echo")
    task_id_2 = token2.purpose.task_id
    await service.invoke("echo", token2, {"msg": "b"}, task_id=task_id_2)

    result = await service.query_audit(token1, {"task_id": task_id_1})
    entries = result["entries"]
    assert len(entries) >= 1
    for e in entries:
        assert e.get("task_id") == task_id_1


# --- test_audit_query_by_parent_invocation_id ---

async def test_audit_query_by_parent_invocation_id(service):
    """Audit entries can be filtered by parent_invocation_id."""
    token = await _issue_token(service, ["echo"], "echo")
    parent_id = "inv-112233445566"
    await service.invoke(
        "echo", token, {"msg": "child"},
        parent_invocation_id=parent_id,
    )
    await service.invoke("echo", token, {"msg": "orphan"})

    result = await service.query_audit(token, {"parent_invocation_id": parent_id})
    entries = result["entries"]
    assert len(entries) >= 1
    for e in entries:
        assert e.get("parent_invocation_id") == parent_id
