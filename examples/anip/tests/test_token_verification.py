"""Tests for JWT verification on protected endpoints."""

from tests.conftest import client  # noqa: F401


AUTH = {"Authorization": "Bearer demo-human-key"}


def _issue_token(client, scope, capability, **kwargs):
    """Helper: issue a token and return the JWT string + token_id."""
    resp = client.post("/anip/tokens", json={
        "subject": "agent:test",
        "scope": scope,
        "capability": capability,
        **kwargs,
    }, headers=AUTH)
    body = resp.json()
    return body["token"], body["token_id"]


def test_permissions_with_jwt(client):
    token_jwt, _ = _issue_token(client, ["travel.search"], "search_flights")
    resp = client.post("/anip/permissions", json={"token": token_jwt})
    assert resp.status_code == 200
    body = resp.json()
    available = [c["capability"] for c in body["available"]]
    assert "search_flights" in available


def test_permissions_rejects_invalid_jwt(client):
    resp = client.post("/anip/permissions", json={"token": "invalid.jwt.string"})
    assert resp.status_code == 401


def test_invoke_with_jwt(client):
    token_jwt, _ = _issue_token(client, ["travel.search"], "search_flights")
    resp = client.post("/anip/invoke/search_flights", json={
        "token": token_jwt,
        "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


def test_invoke_rejects_invalid_jwt(client):
    resp = client.post("/anip/invoke/search_flights", json={
        "token": "bad.token.here",
        "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
    })
    assert resp.status_code == 200  # ANIP returns failures in the body, not HTTP codes
    body = resp.json()
    assert body["success"] is False
    assert body["failure"]["type"] == "invalid_token"


def test_invoke_rejects_tampered_store(client):
    """If the stored token's scope is mutated after issuance, invocation is rejected."""
    token_jwt, token_id = _issue_token(client, ["travel.search"], "search_flights")
    # Simulate store tampering: directly modify the stored token's scope
    from anip_flight_demo.data.database import get_connection
    import json
    conn = get_connection()
    conn.execute(
        "UPDATE delegation_tokens SET scope = ? WHERE token_id = ?",
        (json.dumps(["travel.search", "travel.book:max_$999"]), token_id),
    )
    conn.commit()
    # Now try to use the token — should be rejected because JWT scope != stored scope
    resp = client.post("/anip/invoke/search_flights", json={
        "token": token_jwt,
        "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
    })
    body = resp.json()
    assert body["success"] is False
    assert body["failure"]["type"] == "token_integrity_violation"


def test_audit_with_jwt(client):
    token_jwt, _ = _issue_token(client, ["travel.search"], "search_flights")
    # Do an invocation first so there's something in the audit log
    client.post("/anip/invoke/search_flights", json={
        "token": token_jwt,
        "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
    })
    resp = client.post("/anip/audit", json={"token": token_jwt})
    assert resp.status_code == 200
    body = resp.json()
    assert "entries" in body
