"""Tests for authenticated token issuance (v0.2)."""

import jwt

DEMO_AUTH = {"Authorization": "Bearer demo-human-key"}
AGENT_AUTH = {"Authorization": "Bearer demo-agent-key"}


def test_issue_requires_authentication(client):
    """No auth header → issuance refused."""
    resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.search"],
        "capability": "search_flights",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["issued"] is False
    assert "authentication required" in body["error"]


def test_issue_root_token(client):
    """Authenticated caller can issue a root token."""
    resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.search"],
        "capability": "search_flights",
    }, headers=DEMO_AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["issued"] is True
    assert "token" in body
    assert "token_id" in body
    assert body["token_id"].startswith("anip-")


def test_issued_token_is_verifiable_via_jwks(client):
    """The issued JWT is verifiable and contains expected claims."""
    # Get the JWKS
    jwks_resp = client.get("/.well-known/jwks.json")
    jwks = jwks_resp.json()
    assert len(jwks["keys"]) > 0

    # Issue a token
    resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.search"],
        "capability": "search_flights",
    }, headers=DEMO_AUTH)
    body = resp.json()
    assert body["issued"] is True
    jwt_str = body["token"]

    # Decode and verify claims (using PyJWT with the JWKS)
    from cryptography.hazmat.primitives.asymmetric import ec
    from anip_flight_demo.main import _keys

    claims = _keys.verify_jwt(jwt_str, audience="anip-flight-service")
    assert claims["sub"] == "agent:demo-agent"
    assert claims["scope"] == ["travel.search"]
    assert claims["capability"] == "search_flights"
    assert claims["root_principal"] == "human:samir@example.com"
    assert claims["iss"] == "anip-flight-service"
    assert claims["aud"] == "anip-flight-service"
    assert "iat" in claims
    assert "exp" in claims
    assert "jti" in claims


def test_issued_token_has_server_controlled_fields(client):
    """Server sets iss, iat, exp, and extracts budget from scope."""
    resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.book:max_$500"],
        "capability": "book_flight",
        "ttl_hours": 4,
    }, headers=DEMO_AUTH)
    body = resp.json()
    assert body["issued"] is True

    from anip_flight_demo.main import _keys
    claims = _keys.verify_jwt(body["token"], audience="anip-flight-service")

    assert claims["iss"] == "anip-flight-service"
    assert claims["exp"] - claims["iat"] == 4 * 3600
    assert claims["budget"] == {"max": 500.0, "currency": "USD"}
    assert "constraints" in claims


def test_issue_child_token_with_parent(client):
    """Agent can issue a child token using its parent JWT."""
    # Human issues root token to agent
    parent_resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.search", "travel.book:max_$500"],
        "capability": "search_flights",
    }, headers=DEMO_AUTH)
    parent_body = parent_resp.json()
    assert parent_body["issued"] is True
    parent_jwt = parent_body["token"]

    # Agent issues child token using parent JWT
    child_resp = client.post("/anip/tokens", json={
        "subject": "agent:sub-agent",
        "scope": ["travel.search"],
        "capability": "search_flights",
        "parent_token": parent_jwt,
    }, headers=AGENT_AUTH)
    child_body = child_resp.json()
    assert child_body["issued"] is True
    assert "token" in child_body

    # Verify child claims include parent_token_id
    from anip_flight_demo.main import _keys
    child_claims = _keys.verify_jwt(child_body["token"], audience="anip-flight-service")
    assert child_claims["parent_token_id"] == parent_body["token_id"]
    # Root principal should trace back to the human
    assert child_claims["root_principal"] == "human:samir@example.com"


def test_child_issuance_requires_caller_is_parent_subject(client):
    """Only the parent token's subject can sub-delegate."""
    # Human issues root token to agent
    parent_resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.search"],
        "capability": "search_flights",
    }, headers=DEMO_AUTH)
    parent_body = parent_resp.json()
    assert parent_body["issued"] is True
    parent_jwt = parent_body["token"]

    # Human (not the agent subject) tries to sub-delegate → should fail
    child_resp = client.post("/anip/tokens", json={
        "subject": "agent:sub-agent",
        "scope": ["travel.search"],
        "capability": "search_flights",
        "parent_token": parent_jwt,
    }, headers=DEMO_AUTH)
    child_body = child_resp.json()
    assert child_body["issued"] is False
    assert "not the parent token's subject" in child_body["error"]


def test_child_cannot_widen_scope(client):
    """Child token with wider scope than parent is rejected."""
    # Human issues root token with narrow scope
    parent_resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.search"],
        "capability": "search_flights",
    }, headers=DEMO_AUTH)
    parent_body = parent_resp.json()
    assert parent_body["issued"] is True
    parent_jwt = parent_body["token"]

    # Agent tries to issue child with wider scope
    child_resp = client.post("/anip/tokens", json={
        "subject": "agent:sub-agent",
        "scope": ["travel.search", "travel.book"],
        "capability": "search_flights",
        "parent_token": parent_jwt,
    }, headers=AGENT_AUTH)
    child_body = child_resp.json()
    assert child_body["issued"] is False


def test_child_cannot_widen_budget(client):
    """Child token with higher budget than parent is rejected."""
    # Human issues root token with $500 budget
    parent_resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.book:max_$500"],
        "capability": "book_flight",
    }, headers=DEMO_AUTH)
    parent_body = parent_resp.json()
    assert parent_body["issued"] is True
    parent_jwt = parent_body["token"]

    # Agent tries to issue child with $1000 budget
    child_resp = client.post("/anip/tokens", json={
        "subject": "agent:sub-agent",
        "scope": ["travel.book:max_$1000"],
        "capability": "book_flight",
        "parent_token": parent_jwt,
    }, headers=AGENT_AUTH)
    child_body = child_resp.json()
    assert child_body["issued"] is False
