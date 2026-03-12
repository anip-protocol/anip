"""Tests for trust mode switching."""

import uuid

from fastapi.testclient import TestClient


def test_default_mode_is_signed():
    """Without env override, server requires JWT tokens."""
    from anip_server.main import get_trust_mode
    assert get_trust_mode() == "signed"


def test_declaration_mode_accepts_old_format(monkeypatch):
    """In trust-on-declaration mode, the old DelegationToken format works."""
    monkeypatch.setenv("ANIP_TRUST_MODE", "declaration")
    from anip_server.main import app, set_trust_mode
    set_trust_mode("declaration")
    client = TestClient(app)
    token_id = f"test-old-style-{uuid.uuid4().hex[:8]}"
    # Old-style token registration
    resp = client.post("/anip/tokens", json={
        "token_id": token_id,
        "issuer": "human:test@example.com",
        "subject": "agent:test",
        "scope": ["travel.search"],
        "purpose": {"capability": "search_flights", "parameters": {}, "task_id": "t1"},
        "parent": None,
        "expires": "2099-01-01T00:00:00Z",
        "constraints": {"max_delegation_depth": 3, "concurrent_branches": "allowed"},
    })
    body = resp.json()
    assert body.get("registered") is True or body.get("issued") is True
    # Old-style permissions query
    resp2 = client.post("/anip/permissions", json={
        "token_id": token_id,
        "issuer": "human:test@example.com",
        "subject": "agent:test",
        "scope": ["travel.search"],
        "purpose": {"capability": "search_flights", "parameters": {}, "task_id": "t1"},
        "parent": None,
        "expires": "2099-01-01T00:00:00Z",
        "constraints": {"max_delegation_depth": 3, "concurrent_branches": "allowed"},
    })
    assert resp2.status_code == 200
    # Clean up
    set_trust_mode("signed")
