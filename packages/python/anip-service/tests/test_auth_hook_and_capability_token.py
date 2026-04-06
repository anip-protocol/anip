"""Tests for async auth hook support and issue_capability_token helper."""
import pytest
from anip_service import ANIPService, Capability
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SideEffect, SideEffectType


def _test_cap(name: str = "greet", scope: list[str] | None = None) -> Capability:
    return Capability(
        declaration=CapabilityDeclaration(
            name=name,
            description="Say hello",
            contract_version="1.0",
            inputs=[CapabilityInput(name="name", type="string", required=True, description="Who to greet")],
            output=CapabilityOutput(type="object", fields=["message"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=scope or [name],
        ),
        handler=lambda ctx, params: {"message": f"Hello, {params.get('name', 'world')}!"},
    )


def _make_service(authenticate=None) -> ANIPService:
    return ANIPService(
        service_id="test-service",
        capabilities=[_test_cap()],
        storage=":memory:",
        authenticate=authenticate,
    )


# ---------------------------------------------------------------------------
# Auth hook tests
# ---------------------------------------------------------------------------

class TestAuthHook:
    async def test_sync_hook_returns_principal(self):
        """A sync auth hook that returns a principal string works as expected."""
        def sync_auth(token: str) -> str | None:
            if token == "valid-key":
                return "human:alice@example.com"
            return None

        service = _make_service(authenticate=sync_auth)
        principal = await service.authenticate_bearer("valid-key")
        assert principal == "human:alice@example.com"

    async def test_sync_hook_returns_none_falls_through(self):
        """A sync auth hook that returns None falls through to JWT verification."""
        def sync_auth(token: str) -> str | None:
            return None

        service = _make_service(authenticate=sync_auth)
        # No valid JWT either, so overall result is None
        principal = await service.authenticate_bearer("not-a-jwt")
        assert principal is None

    async def test_async_hook_is_properly_awaited(self):
        """An async auth hook is awaited — its return value becomes the principal,
        not the truthy coroutine object."""
        async def async_auth(token: str) -> str | None:
            if token == "async-valid-key":
                return "human:bob@example.com"
            return None

        service = _make_service(authenticate=async_auth)
        principal = await service.authenticate_bearer("async-valid-key")
        assert principal == "human:bob@example.com"
        # Ensure we actually got the string, not a coroutine
        assert isinstance(principal, str)

    async def test_async_hook_returning_none_falls_through(self):
        """An async auth hook that returns None does not short-circuit as truthy."""
        async def async_auth(token: str) -> str | None:
            return None

        service = _make_service(authenticate=async_auth)
        principal = await service.authenticate_bearer("some-token")
        assert principal is None

    async def test_no_hook_falls_through_to_jwt(self):
        """With no auth hook, an invalid bearer returns None."""
        service = _make_service(authenticate=None)
        principal = await service.authenticate_bearer("not-a-jwt")
        assert principal is None


# ---------------------------------------------------------------------------
# issue_capability_token tests
# ---------------------------------------------------------------------------

class TestIssueCapabilityToken:
    async def test_returns_token_with_correct_capability(self):
        """issue_capability_token produces a JWT and token_id for the capability."""
        service = _make_service()
        result = await service.issue_capability_token(
            principal="human:alice@example.com",
            capability="greet",
            scope=["greet"],
        )
        assert result["issued"] is True
        assert "token" in result
        assert "token_id" in result
        assert "expires" in result

    async def test_token_capability_claim_matches(self):
        """The issued JWT carries the expected capability claim."""
        import base64, json as _json

        service = _make_service()
        result = await service.issue_capability_token(
            principal="human:alice@example.com",
            capability="greet",
            scope=["greet"],
        )
        # Decode JWT payload (no signature verification needed for claim inspection)
        parts = result["token"].split(".")
        # Add padding
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
        assert payload.get("capability") == "greet"
        assert payload.get("scope") == ["greet"]

    async def test_scope_is_required_and_not_defaulted(self):
        """scope must be provided explicitly; the helper passes it through."""
        service = _make_service()
        result = await service.issue_capability_token(
            principal="human:alice@example.com",
            capability="greet",
            scope=["greet", "extra.read"],
        )
        import base64, json as _json
        parts = result["token"].split(".")
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
        assert "extra.read" in payload["scope"]

    async def test_purpose_parameters_passed_through(self):
        """purpose_parameters are forwarded to issue_token."""
        service = _make_service()
        result = await service.issue_capability_token(
            principal="human:alice@example.com",
            capability="greet",
            scope=["greet"],
            purpose_parameters={"context": "test-context"},
        )
        assert result["issued"] is True

    async def test_budget_passed_through(self):
        """budget kwarg is forwarded and echoed in response when set."""
        service = _make_service()
        result = await service.issue_capability_token(
            principal="human:alice@example.com",
            capability="greet",
            scope=["greet"],
            budget={"currency": "USD", "max_amount": 10.0},
        )
        assert result["issued"] is True
        assert "budget" in result

    async def test_custom_ttl_hours(self):
        """ttl_hours is respected in the issued token's expiry."""
        from datetime import datetime, timezone
        service = _make_service()
        result = await service.issue_capability_token(
            principal="human:alice@example.com",
            capability="greet",
            scope=["greet"],
            ttl_hours=8,
        )
        expires = datetime.fromisoformat(result["expires"])
        now = datetime.now(timezone.utc)
        diff_hours = (expires - now).total_seconds() / 3600
        # Should be approximately 8 hours (within a 1-minute tolerance)
        assert 7.98 < diff_hours < 8.02
