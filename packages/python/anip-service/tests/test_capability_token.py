"""Tests for issue_capability_token and async auth hook fix."""
import asyncio
import pytest

from anip_service import ANIPService, Capability, InvocationContext, ANIPError
from anip_core import (
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    SideEffect,
    SideEffectType,
)


def _test_cap(name: str = "evaluate", scope: list[str] | None = None) -> Capability:
    return Capability(
        declaration=CapabilityDeclaration(
            name=name,
            description="Evaluate a service design",
            contract_version="1.0",
            inputs=[CapabilityInput(name="input", type="string", required=True, description="Input data")],
            output=CapabilityOutput(type="object", fields=["result"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=scope or ["studio.evaluate"],
        ),
        handler=lambda ctx, params: {"result": "ok"},
    )


def _make_service(**kwargs) -> ANIPService:
    defaults = dict(
        service_id="test-service",
        capabilities=[_test_cap()],
        storage=":memory:",
    )
    defaults.update(kwargs)
    return ANIPService(**defaults)


# ---------------------------------------------------------------------------
# Async auth hook bug fix
# ---------------------------------------------------------------------------


class TestAsyncAuthHook:
    @pytest.mark.asyncio
    async def test_async_hook_is_properly_awaited(self):
        """Verify that an async authenticate hook is awaited (not treated as truthy)."""

        async def async_auth(bearer: str) -> str | None:
            return "async-principal" if bearer == "valid" else None

        service = _make_service(authenticate=async_auth)
        result = await service.authenticate_bearer("valid")
        assert result == "async-principal"

    @pytest.mark.asyncio
    async def test_async_hook_returns_none_for_invalid(self):
        async def async_auth(bearer: str) -> str | None:
            return "ok" if bearer == "good" else None

        service = _make_service(authenticate=async_auth)
        result = await service.authenticate_bearer("bad")
        # Should fall through to JWT resolution (which will also fail),
        # resulting in None.
        assert result is None

    @pytest.mark.asyncio
    async def test_sync_hook_still_works(self):
        """Sync hooks must continue to work after the async fix."""

        def sync_auth(bearer: str) -> str | None:
            return "sync-principal" if bearer == "valid" else None

        service = _make_service(authenticate=sync_auth)
        result = await service.authenticate_bearer("valid")
        assert result == "sync-principal"

    @pytest.mark.asyncio
    async def test_sync_hook_returns_none_for_invalid(self):
        def sync_auth(bearer: str) -> str | None:
            return "ok" if bearer == "good" else None

        service = _make_service(authenticate=sync_auth)
        result = await service.authenticate_bearer("bad")
        assert result is None


# ---------------------------------------------------------------------------
# issue_capability_token
# ---------------------------------------------------------------------------


class TestIssueCapabilityToken:
    @pytest.mark.asyncio
    async def test_issues_token_with_capability(self):
        """issue_capability_token should produce a valid token response."""
        service = _make_service()
        resp = await service.issue_capability_token(
            principal="human:alice@example.com",
            capability="evaluate",
            scope=["studio.evaluate"],
        )
        assert resp["issued"] is True
        assert resp["token_id"]
        assert resp["token"]  # JWT string
        assert resp["expires"]

    @pytest.mark.asyncio
    async def test_scope_is_required(self):
        """Scope must be explicitly provided, not derived from capability name."""
        service = _make_service()
        # Providing an explicit scope that differs from the capability name
        resp = await service.issue_capability_token(
            principal="human:bob@example.com",
            capability="evaluate",
            scope=["custom.scope"],
        )
        assert resp["issued"] is True

    @pytest.mark.asyncio
    async def test_optional_parameters(self):
        """purpose_parameters, ttl_hours, and budget should flow through."""
        service = _make_service()
        resp = await service.issue_capability_token(
            principal="human:carol@example.com",
            capability="evaluate",
            scope=["studio.evaluate"],
            purpose_parameters={"task_id": "task-123"},
            ttl_hours=4,
            budget={"currency": "USD", "max_amount": 100},
        )
        assert resp["issued"] is True
        assert resp["token_id"]
        # Budget should be echoed when present
        assert resp.get("budget") is not None

    @pytest.mark.asyncio
    async def test_token_can_be_resolved(self):
        """The JWT from issue_capability_token should be resolvable."""
        service = _make_service()
        resp = await service.issue_capability_token(
            principal="human:dave@example.com",
            capability="evaluate",
            scope=["studio.evaluate"],
        )
        token = await service.resolve_bearer_token(resp["token"])
        assert token.subject == "human:dave@example.com"
        assert token.purpose.capability == "evaluate"


# ---------------------------------------------------------------------------
# issue_delegated_capability_token
# ---------------------------------------------------------------------------


class TestIssueDelegatedCapabilityToken:
    @pytest.mark.asyncio
    async def test_issues_delegated_token(self):
        """issue_delegated_capability_token should produce a valid delegated token."""
        service = _make_service()
        # First issue a root token
        root_resp = await service.issue_capability_token(
            principal="human:alice@example.com",
            capability="evaluate",
            scope=["studio.evaluate"],
        )
        root_token_id = root_resp["token_id"]

        # Now delegate
        resp = await service.issue_delegated_capability_token(
            principal="human:alice@example.com",
            parent_token=root_token_id,
            capability="evaluate",
            scope=["studio.evaluate"],
            subject="agent:helper",
        )
        assert resp["issued"] is True
        assert resp["token_id"]
        assert resp["token"]  # JWT string

        # Resolve and verify delegation
        token = await service.resolve_bearer_token(resp["token"])
        assert token.subject == "agent:helper"
        assert token.purpose.capability == "evaluate"
        assert token.parent == root_token_id

    @pytest.mark.asyncio
    async def test_scope_is_required_and_explicit(self):
        """Scope must be explicitly provided, not inferred from capability."""
        service = _make_service()
        # Root token with broader scope
        root_resp = await service.issue_capability_token(
            principal="human:bob@example.com",
            capability="evaluate",
            scope=["studio.evaluate", "studio.evaluate.read"],
        )
        # Delegate with a subset scope -- scope is explicit, not derived from capability.
        resp = await service.issue_delegated_capability_token(
            principal="human:bob@example.com",
            parent_token=root_resp["token_id"],
            capability="evaluate",
            scope=["studio.evaluate"],
            subject="agent:worker",
        )
        assert resp["issued"] is True

    @pytest.mark.asyncio
    async def test_optional_parameters(self):
        """caller_class, purpose_parameters, ttl_hours, and budget should flow through."""
        service = _make_service()
        root_resp = await service.issue_capability_token(
            principal="human:carol@example.com",
            capability="evaluate",
            scope=["studio.evaluate"],
        )
        resp = await service.issue_delegated_capability_token(
            principal="human:carol@example.com",
            parent_token=root_resp["token_id"],
            capability="evaluate",
            scope=["studio.evaluate"],
            subject="agent:delegate",
            caller_class="automated",
            purpose_parameters={"task_id": "task-456"},
            ttl_hours=1,
            budget={"currency": "USD", "max_amount": 50},
        )
        assert resp["issued"] is True
        assert resp["token_id"]
