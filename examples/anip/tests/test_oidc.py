"""Tests for OIDC token validation in the example app."""
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import pytest
import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jwt import algorithms as jwt_algorithms

from anip_flight_demo.oidc import OidcValidator, _map_claims_to_principal


# --- Test key pair ---

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()
_public_jwk = jwt_algorithms.RSAAlgorithm.to_jwk(_public_key, as_dict=True)
_public_jwk["kid"] = "test-key-1"
_public_jwk["alg"] = "RS256"
_public_jwk["use"] = "sig"


# --- Local JWKS server ---

class _JwksHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/.well-known/openid-configuration":
            port = self.server.server_address[1]
            body = json.dumps({
                "issuer": f"http://localhost:{port}",
                "jwks_uri": f"http://localhost:{port}/jwks",
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/jwks":
            body = json.dumps({"keys": [_public_jwk]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # suppress logs


@pytest.fixture(scope="module")
def jwks_server():
    server = HTTPServer(("localhost", 0), _JwksHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{port}"
    server.shutdown()


def _sign_token(issuer: str, audience: str, claims: dict, exp_offset: int = 3600) -> str:
    payload = {
        "iss": issuer,
        "aud": audience,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
        **claims,
    }
    return pyjwt.encode(payload, _private_key, algorithm="RS256", headers={"kid": "test-key-1"})


# --- Claim mapping tests ---

class TestClaimMapping:
    def test_email_claim(self):
        assert _map_claims_to_principal({"email": "samir@example.com"}) == "human:samir@example.com"

    def test_preferred_username(self):
        assert _map_claims_to_principal({"preferred_username": "samir", "sub": "123"}) == "human:samir"

    def test_sub_only(self):
        assert _map_claims_to_principal({"sub": "service-xyz"}) == "oidc:service-xyz"

    def test_no_claims(self):
        assert _map_claims_to_principal({}) is None


# --- Validator tests ---

class TestOidcValidator:
    @pytest.fixture
    def validator(self, jwks_server):
        return OidcValidator(issuer_url=jwks_server, audience="test-service")

    def test_valid_token_with_email(self, validator, jwks_server):
        token = _sign_token(jwks_server, "test-service", {"email": "samir@example.com"})
        result = validator.validate(token)
        assert result == "human:samir@example.com"

    def test_valid_token_with_username(self, validator, jwks_server):
        token = _sign_token(jwks_server, "test-service", {"preferred_username": "samir", "sub": "u1"})
        result = validator.validate(token)
        assert result == "human:samir"

    def test_valid_token_sub_only(self, validator, jwks_server):
        token = _sign_token(jwks_server, "test-service", {"sub": "svc-account"})
        result = validator.validate(token)
        assert result == "oidc:svc-account"

    def test_expired_token(self, validator, jwks_server):
        token = _sign_token(jwks_server, "test-service", {"email": "x@x.com"}, exp_offset=-3600)
        result = validator.validate(token)
        assert result is None

    def test_wrong_issuer(self, jwks_server):
        validator = OidcValidator(issuer_url="https://wrong.example.com", audience="test-service",
                                  jwks_url=f"{jwks_server}/jwks")
        token = _sign_token(jwks_server, "test-service", {"email": "x@x.com"})
        result = validator.validate(token)
        assert result is None

    def test_wrong_audience(self, jwks_server):
        validator = OidcValidator(issuer_url=jwks_server, audience="wrong-aud")
        token = _sign_token(jwks_server, "wrong-aud-not-matching", {"email": "x@x.com"})
        result = validator.validate(token)
        assert result is None

    def test_invalid_signature(self, validator, jwks_server):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        payload = {"iss": jwks_server, "aud": "test-service", "email": "x@x.com",
                   "iat": int(time.time()), "exp": int(time.time()) + 3600}
        token = pyjwt.encode(payload, other_key, algorithm="RS256", headers={"kid": "test-key-1"})
        result = validator.validate(token)
        assert result is None

    def test_jwks_fetch_failure(self):
        validator = OidcValidator(issuer_url="http://localhost:1", audience="x",
                                  jwks_url="http://localhost:1/jwks")
        result = validator.validate("some-token")
        assert result is None

    def test_non_jwt_string(self, validator):
        result = validator.validate("not-a-jwt")
        assert result is None

    def test_explicit_jwks_url(self, jwks_server):
        validator = OidcValidator(issuer_url=jwks_server, audience="test-service",
                                  jwks_url=f"{jwks_server}/jwks")
        token = _sign_token(jwks_server, "test-service", {"email": "direct@example.com"})
        result = validator.validate(token)
        assert result == "human:direct@example.com"
