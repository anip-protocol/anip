"""Conformance tests for ANIP token issuance and delegation.

Spec references: §4.3 (delegation chain), Conformance Category 4.
"""
from datetime import datetime, timezone

import jwt as pyjwt


class TestTokenIssuance:
    def test_issue_token_success(self, client, bootstrap_bearer, read_capability):
        cap_name, cap_scope = read_capability
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {bootstrap_bearer}"},
            json={
                "scope": cap_scope,
                "capability": cap_name,
                "purpose_parameters": {"task_id": "conformance"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["issued"] is True
        assert "token" in data
        assert "token_id" in data
        assert "expires" in data

    def test_token_expires_in_future(self, client, bootstrap_bearer, read_capability):
        cap_name, cap_scope = read_capability
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {bootstrap_bearer}"},
            json={
                "scope": cap_scope,
                "capability": cap_name,
                "purpose_parameters": {"task_id": "conformance"},
            },
        )
        data = resp.json()
        expires = datetime.fromisoformat(data["expires"].replace("Z", "+00:00"))
        assert expires > datetime.now(timezone.utc)

    def test_token_verifiable_against_jwks(self, client, bootstrap_bearer, read_capability):
        cap_name, cap_scope = read_capability
        # Get JWKS
        jwks_resp = client.get("/.well-known/jwks.json")
        jwks_data = jwks_resp.json()

        # Issue token
        token_resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {bootstrap_bearer}"},
            json={
                "scope": cap_scope,
                "capability": cap_name,
                "purpose_parameters": {"task_id": "conformance"},
            },
        )
        token_str = token_resp.json()["token"]

        # Verify — resolve the matching key by kid from the JWT header
        from jwt import PyJWKSet, get_unverified_header
        header = get_unverified_header(token_str)
        keyset = PyJWKSet.from_dict(jwks_data)
        kid = header.get("kid")
        signing_key = None
        for jwk in keyset.keys:
            if jwk.key_id == kid:
                signing_key = jwk.key
                break
        if signing_key is None:
            # Fall back to first key if no kid match (single-key services)
            signing_key = keyset.keys[0].key
        # Should not raise
        decoded = pyjwt.decode(
            token_str,
            signing_key,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )
        assert decoded is not None


class TestTokenDenial:
    def test_unauthenticated_returns_401(self, client):
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["anything"]},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"
        assert "resolution" in data["failure"]
        assert "retry" in data["failure"]

    def test_unauthenticated_failure_has_required_fields(self, client):
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["anything"]},
        )
        failure = resp.json()["failure"]
        assert "type" in failure
        assert "detail" in failure
        assert "resolution" in failure
        assert "retry" in failure
        assert isinstance(failure["retry"], bool)
