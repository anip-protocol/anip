"""Tests for the POST /anip/approval_grants HTTP endpoint (v0.23 §4.9)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anip_core import (
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    GrantPolicy,
    SideEffect,
    SideEffectType,
)
from anip_fastapi import mount_anip
from anip_service import ANIPError, ANIPService, Capability


API_KEY = "test-key-123"


def _approval_required_capability() -> Capability:
    decl = CapabilityDeclaration(
        name="transfer_funds",
        description="High-value transfer",
        inputs=[
            CapabilityInput(name="amount", type="number"),
            CapabilityInput(name="to_account", type="string"),
        ],
        output=CapabilityOutput(type="x", fields=["transfer_id"]),
        side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
        minimum_scope=["finance.write"],
        grant_policy=GrantPolicy(
            allowed_grant_types=["one_time", "session_bound"],
            default_grant_type="one_time",
            expires_in_seconds=900,
            max_uses=1,
        ),
    )

    async def handler(ctx, params):
        if params.get("amount", 0) > 10000:
            raise ANIPError(
                "approval_required",
                "needs approval",
                approval_required={"preview": {"amount": params["amount"]}},
            )
        return {"transfer_id": "tx"}

    return Capability(declaration=decl, handler=handler)


@pytest.fixture
def client(tmp_path):
    import asyncio

    async def authenticate(token: str) -> str | None:
        if token == API_KEY:
            return "human:samir@example.com"
        return None

    svc = ANIPService(
        service_id="test-fin",
        capabilities=[_approval_required_capability()],
        storage=":memory:",
        key_path=str(tmp_path / "keys"),
        authenticate=authenticate,
    )
    app = FastAPI()
    mount_anip(app, svc)

    # Service start is async. Always create a fresh loop — the global loop
    # may be closed/missing if another async test suite ran in the same
    # process.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(svc.start())
    test_client = TestClient(app)
    try:
        yield test_client, svc
    finally:
        loop.run_until_complete(svc.shutdown())
        loop.close()


def _issue_token(client: TestClient, *, scope: list[str], capability: str = "transfer_funds") -> str:
    r = client.post(
        "/anip/tokens",
        json={
            "subject": "human:samir@example.com",
            "scope": scope,
            "capability": capability,
            "ttl_hours": 1,
        },
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _trigger_approval(client: TestClient, token: str) -> str:
    """Invoke transfer_funds with amount > threshold to create a pending request.
    Returns the approval_request_id."""
    r = client.post(
        "/anip/invoke/transfer_funds",
        json={"parameters": {"amount": 50000, "to_account": "x"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    body = r.json()
    return body["failure"]["approval_required"]["approval_request_id"]


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


class TestApprovalGrantsEndpoint:
    def test_happy_path_one_time(self, client):
        c, _svc = client
        token = _issue_token(c, scope=["finance.write"])
        request_id = _trigger_approval(c, token)
        # Approver token with approver:* scope.
        approver_token = _issue_token(
            c, scope=["finance.write", "approver:*"]
        )
        r = c.post(
            "/anip/approval_grants",
            json={"approval_request_id": request_id, "grant_type": "one_time"},
            headers={"Authorization": f"Bearer {approver_token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "grant" in body
        grant = body["grant"]
        assert grant["approval_request_id"] == request_id
        assert grant["grant_type"] == "one_time"
        assert grant["max_uses"] == 1
        assert grant["use_count"] == 0
        assert grant["signature"] != ""

    def test_unauthorized_without_token(self, client):
        c, _ = client
        r = c.post(
            "/anip/approval_grants",
            json={"approval_request_id": "apr_x", "grant_type": "one_time"},
        )
        assert r.status_code == 401

    def test_approval_request_not_found(self, client):
        c, _ = client
        approver_token = _issue_token(c, scope=["finance.write", "approver:*"])
        r = c.post(
            "/anip/approval_grants",
            json={"approval_request_id": "apr_does_not_exist", "grant_type": "one_time"},
            headers={"Authorization": f"Bearer {approver_token}"},
        )
        assert r.status_code == 404
        body = r.json()
        assert body["failure"]["type"] == "approval_request_not_found"

    def test_approver_not_authorized(self, client):
        c, _ = client
        token = _issue_token(c, scope=["finance.write"])
        request_id = _trigger_approval(c, token)
        # Token without any approver: scope.
        non_approver_token = _issue_token(c, scope=["finance.write"])
        r = c.post(
            "/anip/approval_grants",
            json={"approval_request_id": request_id, "grant_type": "one_time"},
            headers={"Authorization": f"Bearer {non_approver_token}"},
        )
        assert r.status_code == 403
        body = r.json()
        assert body["failure"]["type"] == "approver_not_authorized"

    def test_approver_specific_capability_scope(self, client):
        """approver:transfer_funds suffices."""
        c, _ = client
        token = _issue_token(c, scope=["finance.write"])
        request_id = _trigger_approval(c, token)
        approver_token = _issue_token(
            c, scope=["finance.write", "approver:transfer_funds"]
        )
        r = c.post(
            "/anip/approval_grants",
            json={"approval_request_id": request_id, "grant_type": "one_time"},
            headers={"Authorization": f"Bearer {approver_token}"},
        )
        assert r.status_code == 200, r.text

    def test_approval_request_already_decided(self, client):
        c, _ = client
        token = _issue_token(c, scope=["finance.write"])
        request_id = _trigger_approval(c, token)
        approver_token = _issue_token(
            c, scope=["finance.write", "approver:*"]
        )
        # First issuance succeeds.
        c.post(
            "/anip/approval_grants",
            json={"approval_request_id": request_id, "grant_type": "one_time"},
            headers={"Authorization": f"Bearer {approver_token}"},
        )
        # Second fails.
        r = c.post(
            "/anip/approval_grants",
            json={"approval_request_id": request_id, "grant_type": "one_time"},
            headers={"Authorization": f"Bearer {approver_token}"},
        )
        body = r.json()
        assert body["failure"]["type"] == "approval_request_already_decided"

    def test_invalid_body_returns_400(self, client):
        c, _ = client
        approver_token = _issue_token(c, scope=["finance.write", "approver:*"])
        r = c.post(
            "/anip/approval_grants",
            json={"approval_request_id": "apr_x"},  # missing grant_type
            headers={"Authorization": f"Bearer {approver_token}"},
        )
        assert r.status_code == 400
        assert r.json()["failure"]["type"] == "invalid_parameters"

    def test_discovery_advertises_endpoint(self, client):
        c, _ = client
        r = c.get("/.well-known/anip")
        assert r.status_code == 200
        endpoints = r.json()["anip_discovery"]["endpoints"]
        assert "approval_grants" in endpoints
        assert endpoints["approval_grants"] == "/anip/approval_grants"


class TestContinuationViaInvokeEndpoint:
    """End-to-end: approval_grant flows through POST /anip/invoke/{capability}."""

    def test_invoke_with_grant_consumes_grant(self, client):
        c, _svc = client
        token = _issue_token(c, scope=["finance.write"])
        request_id = _trigger_approval(c, token)
        approver_token = _issue_token(
            c, scope=["finance.write", "approver:*"]
        )
        grant_resp = c.post(
            "/anip/approval_grants",
            json={"approval_request_id": request_id, "grant_type": "one_time"},
            headers={"Authorization": f"Bearer {approver_token}"},
        )
        grant_id = grant_resp.json()["grant"]["grant_id"]

        # Resubmit invoke with the grant.
        r = c.post(
            "/anip/invoke/transfer_funds",
            json={
                "parameters": {"amount": 50000, "to_account": "x"},
                "approval_grant": grant_id,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        # The handler still raises approval_required at amount>10k, but the
        # reservation already happened. Verify use_count incremented.
        body = r.json()
        # Second use → grant_consumed.
        r2 = c.post(
            "/anip/invoke/transfer_funds",
            json={
                "parameters": {"amount": 50000, "to_account": "x"},
                "approval_grant": grant_id,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.json()["failure"]["type"] == "grant_consumed"

    def test_invoke_with_unknown_grant_returns_grant_not_found(self, client):
        c, _ = client
        token = _issue_token(c, scope=["finance.write"])
        r = c.post(
            "/anip/invoke/transfer_funds",
            json={
                "parameters": {"amount": 5000, "to_account": "x"},
                "approval_grant": "grant_unknown",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        body = r.json()
        assert body["failure"]["type"] == "grant_not_found"
