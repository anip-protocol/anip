# ANIP v0.2: Cryptographic Trust Foundations — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add signed delegation tokens (JWT/ES256), signed manifests (detached JWS), and signed audit logs (hash chain) to the ANIP reference server, shifting from trust-on-declaration to verifiable trust.

**Architecture:** New `crypto.py` module handles key generation, JWT signing/verification, and JWS operations. The token registration endpoint (`POST /anip/tokens`) becomes a delegation issuance endpoint — callers authenticate and the server constructs+signs the JWT. A `--trust-on-declaration` CLI flag preserves backward compatibility for development. Audit entries gain `sequence_number`, `previous_hash`, and `signature` columns. The TypeScript server mirrors all changes.

**Tech Stack:** Python: PyJWT + cryptography (ES256/ECDSA P-256). TypeScript: jose (ES256). Both: SQLite for persistence, pytest/vitest for tests.

**Scope:** Python server first (Tasks 1-10), TypeScript server second (Task 11), demo/client updates last (Task 12).

---

### Task 1: Crypto Dependencies and Key Management Module

**Context:** The entire cryptographic trust model depends on a key pair. The server generates an ES256 (ECDSA P-256) key pair at startup — or loads an existing one from disk if present. Keys MUST be persisted so that a server restart does not invalidate issued tokens, signed manifests, or audit log signatures. This task creates the foundation everything else builds on.

**Files:**
- Modify: `examples/anip/pyproject.toml`
- Create: `examples/anip/anip_server/primitives/crypto.py`
- Create: `examples/anip/tests/conftest.py`
- Create: `examples/anip/tests/test_crypto.py`

**Step 1: Add dependencies**

Add `PyJWT[crypto]>=2.8` and `pytest>=8.0` to `pyproject.toml`:

```toml
[project]
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "pydantic>=2.0.0",
    "httpx>=0.27.0",
    "PyJWT[crypto]>=2.8",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]
```

**Step 2: Install dependencies**

Run: `cd examples/anip && pip install -e ".[dev]"`
Expected: Success, PyJWT and cryptography installed.

**Step 3: Write the failing tests**

```python
# examples/anip/tests/test_crypto.py
"""Tests for ANIP cryptographic key management."""

import json

import jwt
import pytest

from anip_server.primitives.crypto import KeyManager


class TestKeyManager:
    def test_generates_ec_p256_key(self):
        km = KeyManager()
        assert km.private_key is not None
        assert km.public_key is not None

    def test_jwks_contains_one_key(self):
        km = KeyManager()
        jwks = km.get_jwks()
        assert "keys" in jwks
        assert len(jwks["keys"]) == 1

    def test_jwks_key_has_required_fields(self):
        km = KeyManager()
        key = km.get_jwks()["keys"][0]
        assert key["kty"] == "EC"
        assert key["crv"] == "P-256"
        assert key["alg"] == "ES256"
        assert key["use"] == "sig"
        assert "kid" in key
        assert "x" in key
        assert "y" in key
        # Public key only — no private key material
        assert "d" not in key

    def test_sign_and_verify_roundtrip(self):
        km = KeyManager()
        payload = {"sub": "agent:test", "scope": ["travel.search"]}
        token = km.sign_jwt(payload)
        decoded = km.verify_jwt(token)
        assert decoded["sub"] == "agent:test"
        assert decoded["scope"] == ["travel.search"]

    def test_verify_rejects_tampered_token(self):
        km = KeyManager()
        token = km.sign_jwt({"sub": "agent:test"})
        # Tamper with the payload
        parts = token.split(".")
        parts[1] = parts[1][:-2] + "xx"
        tampered = ".".join(parts)
        with pytest.raises(jwt.exceptions.InvalidSignatureError):
            km.verify_jwt(tampered)

    def test_kid_is_stable_for_same_instance(self):
        km = KeyManager()
        kid1 = km.get_jwks()["keys"][0]["kid"]
        kid2 = km.get_jwks()["keys"][0]["kid"]
        assert kid1 == kid2

    def test_different_instances_have_different_keys(self):
        km1 = KeyManager()
        km2 = KeyManager()
        kid1 = km1.get_jwks()["keys"][0]["kid"]
        kid2 = km2.get_jwks()["keys"][0]["kid"]
        assert kid1 != kid2

    def test_persists_and_loads_keys(self, tmp_path):
        """Keys survive a restart — same kid and verification works across instances."""
        key_file = tmp_path / "anip-keys.json"
        km1 = KeyManager(key_path=str(key_file))
        kid1 = km1.get_jwks()["keys"][0]["kid"]
        token = km1.sign_jwt({"sub": "test"})
        # Simulate restart: new instance loads from same path
        km2 = KeyManager(key_path=str(key_file))
        kid2 = km2.get_jwks()["keys"][0]["kid"]
        assert kid1 == kid2
        # Token signed by km1 is verifiable by km2
        decoded = km2.verify_jwt(token)
        assert decoded["sub"] == "test"

    def test_sign_jws_detached(self):
        km = KeyManager()
        payload = b'{"protocol": "anip/0.2"}'
        signature = km.sign_jws_detached(payload)
        assert isinstance(signature, str)
        # Detached JWS has empty payload: header..signature
        parts = signature.split(".")
        assert len(parts) == 3
        assert parts[1] == ""  # detached = empty payload

    def test_verify_jws_detached(self):
        km = KeyManager()
        payload = b'{"protocol": "anip/0.2"}'
        signature = km.sign_jws_detached(payload)
        assert km.verify_jws_detached(signature, payload) is True

    def test_verify_jws_detached_rejects_modified_payload(self):
        km = KeyManager()
        payload = b'{"protocol": "anip/0.2"}'
        signature = km.sign_jws_detached(payload)
        modified = b'{"protocol": "anip/0.3"}'
        assert km.verify_jws_detached(signature, modified) is False
```

```python
# examples/anip/tests/conftest.py
"""Shared test fixtures for ANIP server tests."""

import pytest
from fastapi.testclient import TestClient

from anip_server.main import app


@pytest.fixture
def client():
    """Test client for the ANIP FastAPI app."""
    return TestClient(app)
```

**Step 4: Run tests to verify they fail**

Run: `cd examples/anip && python -m pytest tests/test_crypto.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'anip_server.primitives.crypto'`

**Step 5: Implement KeyManager**

```python
# examples/anip/anip_server/primitives/crypto.py
"""Cryptographic key management for ANIP v0.2.

Handles ES256 (ECDSA P-256) key generation, JWT signing/verification,
and detached JWS for manifest signing.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


class KeyManager:
    """Manages an ES256 key pair for signing delegation tokens and manifests.

    Keys are persisted to disk so they survive server restarts. If a key file
    exists at the given path, keys are loaded from it. Otherwise, new keys are
    generated and saved. This is critical: ephemeral keys would invalidate all
    issued tokens and signed manifests on restart.
    """

    def __init__(self, key_path: str | None = None) -> None:
        self._key_path = key_path
        if key_path and Path(key_path).exists():
            self._load_keys(key_path)
        else:
            self._generate_keys()
            if key_path:
                self._save_keys(key_path)

    def _generate_keys(self) -> None:
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        self._public_key = self._private_key.public_key()
        pub_bytes = self._public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self._kid = hashlib.sha256(pub_bytes).hexdigest()[:16]

    def _save_keys(self, path: str) -> None:
        """Persist the private key to disk (PEM format, wrapped in JSON with kid)."""
        private_pem = self._private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        data = {"kid": self._kid, "private_key_pem": private_pem}
        Path(path).write_text(json.dumps(data))

    def _load_keys(self, path: str) -> None:
        """Load a previously persisted key pair."""
        data = json.loads(Path(path).read_text())
        self._kid = data["kid"]
        self._private_key = serialization.load_pem_private_key(
            data["private_key_pem"].encode(), password=None
        )
        self._public_key = self._private_key.public_key()

    @property
    def private_key(self) -> ec.EllipticCurvePrivateKey:
        return self._private_key

    @property
    def public_key(self) -> ec.EllipticCurvePublicKey:
        return self._public_key

    def get_jwks(self) -> dict:
        """Return the public key as a JWKS document (no private material)."""
        numbers = self._public_key.public_numbers()
        # Convert coordinates to base64url-encoded big-endian bytes (32 bytes for P-256)
        x_bytes = numbers.x.to_bytes(32, byteorder="big")
        y_bytes = numbers.y.to_bytes(32, byteorder="big")
        return {
            "keys": [
                {
                    "kty": "EC",
                    "crv": "P-256",
                    "alg": "ES256",
                    "use": "sig",
                    "kid": self._kid,
                    "x": base64.urlsafe_b64encode(x_bytes).rstrip(b"=").decode(),
                    "y": base64.urlsafe_b64encode(y_bytes).rstrip(b"=").decode(),
                }
            ]
        }

    def sign_jwt(self, payload: dict, expires_in: int | None = None) -> str:
        """Sign a JWT with the private key."""
        headers = {"kid": self._kid, "alg": "ES256"}
        private_pem = self._private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        return jwt.encode(payload, private_pem, algorithm="ES256", headers=headers)

    def verify_jwt(self, token: str, audience: str = "anip-flight-service") -> dict:
        """Verify and decode a JWT using the public key.

        Validates the audience claim against the expected value. Tokens are
        issued with aud="anip-flight-service", so verification must pass
        the same audience — otherwise PyJWT raises InvalidAudienceError.

        Raises jwt.exceptions.InvalidSignatureError on signature failure.
        Raises jwt.exceptions.InvalidAudienceError on audience mismatch.
        """
        public_pem = self._public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return jwt.decode(
            token, public_pem, algorithms=["ES256"], audience=audience,
        )

    def sign_jws_detached(self, payload: bytes) -> str:
        """Create a detached JWS signature over a payload.

        Returns a JWS with an empty payload section: header..signature
        The original payload is not embedded — the client must supply it for verification.
        """
        # Sign the payload as a normal JWS, then remove the payload part
        private_pem = self._private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        headers = {"kid": self._kid, "alg": "ES256", "b64": False, "crit": ["b64"]}
        # For detached JWS, we sign header.payload but return header..signature
        # Use PyJWT's low-level API: encode the payload as a regular JWT, then detach
        token = jwt.encode(
            {},  # empty claims — we sign raw payload below
            private_pem,
            algorithm="ES256",
            headers={"kid": self._kid},
        )
        # Actually, PyJWT doesn't support detached JWS natively.
        # Build it manually: sign(header_b64 + "." + payload_b64), return header_b64 + ".." + sig_b64
        header_json = json.dumps(
            {"alg": "ES256", "kid": self._kid, "typ": "JWS"},
            separators=(",", ":"),
        ).encode()
        header_b64 = base64.urlsafe_b64encode(header_json).rstrip(b"=").decode()
        payload_b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
        signing_input = f"{header_b64}.{payload_b64}".encode()
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
        from cryptography.hazmat.primitives import hashes
        der_sig = self._private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der_sig)
        # ES256 signature is r || s, each 32 bytes
        sig_bytes = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        sig_b64 = base64.urlsafe_b64encode(sig_bytes).rstrip(b"=").decode()
        return f"{header_b64}..{sig_b64}"

    def verify_jws_detached(self, jws: str, payload: bytes) -> bool:
        """Verify a detached JWS signature against the provided payload.

        Returns True if valid, False if the signature doesn't match.
        """
        try:
            parts = jws.split(".")
            if len(parts) != 3 or parts[1] != "":
                return False
            header_b64, _, sig_b64 = parts
            # Reconstruct the signing input
            payload_b64 = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
            signing_input = f"{header_b64}.{payload_b64}".encode()
            # Decode the signature
            # Add padding back for base64 decode
            sig_padded = sig_b64 + "=" * (4 - len(sig_b64) % 4) if len(sig_b64) % 4 else sig_b64
            sig_bytes = base64.urlsafe_b64decode(sig_padded)
            r = int.from_bytes(sig_bytes[:32], "big")
            s = int.from_bytes(sig_bytes[32:], "big")
            from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
            from cryptography.hazmat.primitives import hashes
            der_sig = encode_dss_signature(r, s)
            self._public_key.verify(der_sig, signing_input, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception:
            return False
```

**Step 6: Run tests to verify they pass**

Run: `cd examples/anip && python -m pytest tests/test_crypto.py -v`
Expected: All 10 tests PASS.

**Step 7: Commit**

```bash
git add examples/anip/pyproject.toml examples/anip/anip_server/primitives/crypto.py examples/anip/tests/
git commit -m "feat(crypto): add KeyManager with ES256 signing, JWKS, and detached JWS"
```

---

### Task 2: JWKS Endpoint and Server Key Initialization

**Context:** The server needs a singleton KeyManager initialized at startup and a `/.well-known/jwks.json` endpoint that serves the public key. Clients use this to verify token signatures locally.

**Files:**
- Modify: `examples/anip/anip_server/main.py:36-43` (add KeyManager init)
- Create: `examples/anip/tests/test_jwks.py`

**Step 1: Write the failing test**

```python
# examples/anip/tests/test_jwks.py
"""Tests for the JWKS endpoint."""

from tests.conftest import client  # noqa: F401


def test_jwks_endpoint_returns_valid_jwks(client):
    resp = client.get("/.well-known/jwks.json")
    assert resp.status_code == 200
    jwks = resp.json()
    assert "keys" in jwks
    assert len(jwks["keys"]) == 1
    key = jwks["keys"][0]
    assert key["kty"] == "EC"
    assert key["crv"] == "P-256"
    assert key["alg"] == "ES256"
    assert "d" not in key  # no private material


def test_jwks_is_stable_across_requests(client):
    resp1 = client.get("/.well-known/jwks.json")
    resp2 = client.get("/.well-known/jwks.json")
    assert resp1.json() == resp2.json()
```

**Step 2: Run test to verify it fails**

Run: `cd examples/anip && python -m pytest tests/test_jwks.py -v`
Expected: FAIL — 404 (endpoint doesn't exist)

**Step 3: Implement JWKS endpoint**

In `main.py`, after the `app = FastAPI(...)` block (line 40), add:

```python
import os
from pathlib import Path
from .primitives.crypto import KeyManager

# Server key pair — persisted to disk so restarts don't invalidate tokens.
# Default path: alongside the SQLite database. Override with ANIP_KEY_PATH env var.
_key_path = os.environ.get(
    "ANIP_KEY_PATH",
    str(Path(__file__).parent / "data" / "anip-keys.json"),
)
_keys = KeyManager(key_path=_key_path)
```

Add the endpoint after the discovery endpoint (after line 127):

```python
@app.get("/.well-known/jwks.json")
def jwks():
    """JSON Web Key Set — public keys for verifying ANIP signatures."""
    return _keys.get_jwks()
```

**Step 4: Run tests to verify they pass**

Run: `cd examples/anip && python -m pytest tests/test_jwks.py -v`
Expected: All 2 tests PASS.

**Step 5: Commit**

```bash
git add examples/anip/anip_server/main.py examples/anip/tests/test_jwks.py
git commit -m "feat: add JWKS endpoint and server key initialization"
```

---

### Task 3: Token Issuance Endpoint (Replace Registration)

**Context:** The biggest change in v0.2. `POST /anip/tokens` currently accepts a full token dict from the client. In v0.2, the client sends a *request* (desired scope, capability, subject) and the server constructs and signs a JWT. The server controls `token_id`, `iss`, `iat`, `exp`. The client cannot forge claims.

**Authentication:** The issuance endpoint MUST require authentication. Without it, any caller can mint arbitrary authority, which defeats the point of signed tokens. The reference implementation uses API key authentication via the `Authorization: Bearer <key>` header. The server maps API keys to identities (the `root_principal`). For the demo, a hardcoded key is acceptable; the mechanism is what matters. Child issuance requires presenting the parent JWT and the server verifies the caller is the parent token's `sub`.

**Important:** The endpoint must remain backward-compatible when `--trust-on-declaration` mode is active (Task 6). For now, implement the new issuance path and update the existing endpoint. The old `DelegationToken` Pydantic model is still used for internal storage; the JWT is the external representation.

**Files:**
- Modify: `examples/anip/anip_server/primitives/models.py` (add `TokenRequest` model)
- Modify: `examples/anip/anip_server/primitives/delegation.py` (add `issue_token()`)
- Modify: `examples/anip/anip_server/main.py:170-193` (rewrite `POST /anip/tokens`)
- Create: `examples/anip/tests/test_token_issuance.py`

**Step 1: Write the failing tests**

```python
# examples/anip/tests/test_token_issuance.py
"""Tests for JWT token issuance."""

import jwt as pyjwt

from tests.conftest import client  # noqa: F401


DEMO_AUTH = {"Authorization": "Bearer demo-human-key"}
AGENT_AUTH = {"Authorization": "Bearer demo-agent-key"}


def test_issue_requires_authentication(client):
    """Issuance without auth header is rejected."""
    resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.search"],
        "capability": "search_flights",
    })
    body = resp.json()
    assert body["issued"] is False
    assert "authentication" in body["error"].lower()


def test_issue_root_token(client):
    """Server issues a signed JWT for an authenticated root delegation request."""
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
    # The token is a valid JWT string
    assert body["token"].count(".") == 2


def test_issued_token_is_verifiable_via_jwks(client):
    """Issued JWT can be verified using the JWKS public key."""
    # Get the public key
    jwks_resp = client.get("/.well-known/jwks.json")
    jwks = jwks_resp.json()
    # Issue a token
    resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.search"],
        "capability": "search_flights",
    }, headers=DEMO_AUTH)
    token_str = resp.json()["token"]
    # Decode header to get kid
    header = pyjwt.get_unverified_header(token_str)
    assert header["alg"] == "ES256"
    assert "kid" in header
    # Verify the JWT has the right claims
    unverified = pyjwt.decode(token_str, options={"verify_signature": False})
    assert unverified["sub"] == "agent:demo-agent"
    assert unverified["scope"] == ["travel.search"]
    assert unverified["capability"] == "search_flights"
    assert unverified["root_principal"] == "human:samir@example.com"
    assert "iss" in unverified
    assert "iat" in unverified
    assert "exp" in unverified
    assert "jti" in unverified


def test_issued_token_has_server_controlled_fields(client):
    """Server sets iss, iat, exp, jti — client cannot control these."""
    resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.book:max_$300"],
        "capability": "book_flight",
    }, headers=DEMO_AUTH)
    token_str = resp.json()["token"]
    claims = pyjwt.decode(token_str, options={"verify_signature": False})
    # Server-controlled
    assert claims["iss"] == "anip-flight-service"
    assert isinstance(claims["iat"], int)
    assert isinstance(claims["exp"], int)
    assert claims["exp"] > claims["iat"]
    # Budget extracted from scope
    assert claims["budget"] == {"max": 300.0, "currency": "USD"}


def test_issue_child_token_with_parent(client):
    """Child token references parent and narrows scope."""
    # Issue parent (human delegates to agent)
    parent_resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.search", "travel.book:max_$500"],
        "capability": "book_flight",
    }, headers=DEMO_AUTH)
    parent_id = parent_resp.json()["token_id"]
    parent_jwt = parent_resp.json()["token"]
    # Issue child (agent sub-delegates) — agent must authenticate as the parent's subject
    child_resp = client.post("/anip/tokens", json={
        "subject": "agent:sub-agent",
        "scope": ["travel.book:max_$300"],
        "capability": "book_flight",
        "parent_token": parent_jwt,
    }, headers=AGENT_AUTH)
    assert child_resp.status_code == 200
    body = child_resp.json()
    assert body["issued"] is True
    child_claims = pyjwt.decode(body["token"], options={"verify_signature": False})
    assert child_claims["parent_token_id"] == parent_id
    # Root principal is inherited from parent chain, not the child caller
    assert child_claims["root_principal"] == "human:samir@example.com"


def test_child_issuance_requires_caller_is_parent_subject(client):
    """Only the parent token's subject can sub-delegate."""
    parent_resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.search"],
        "capability": "search_flights",
    }, headers=DEMO_AUTH)
    parent_jwt = parent_resp.json()["token"]
    # Try to sub-delegate as the human (not the agent who is the subject)
    child_resp = client.post("/anip/tokens", json={
        "subject": "agent:sub-agent",
        "scope": ["travel.search"],
        "capability": "search_flights",
        "parent_token": parent_jwt,
    }, headers=DEMO_AUTH)  # human auth, but parent's subject is agent:demo-agent
    body = child_resp.json()
    assert body["issued"] is False
    assert "subject" in body["error"].lower() or "delegatee" in body["error"].lower()


def test_child_cannot_widen_scope(client):
    """Child token cannot have wider scope than parent."""
    parent_resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.search"],
        "capability": "search_flights",
    }, headers=DEMO_AUTH)
    parent_jwt = parent_resp.json()["token"]
    child_resp = client.post("/anip/tokens", json={
        "subject": "agent:sub-agent",
        "scope": ["travel.search", "travel.book:max_$500"],
        "capability": "book_flight",
        "parent_token": parent_jwt,
    }, headers=AGENT_AUTH)
    body = child_resp.json()
    assert body["issued"] is False
    assert "scope" in body["error"].lower() or "escalation" in body["error"].lower()


def test_child_cannot_widen_budget(client):
    """Child cannot raise parent's budget cap."""
    parent_resp = client.post("/anip/tokens", json={
        "subject": "agent:demo-agent",
        "scope": ["travel.book:max_$300"],
        "capability": "book_flight",
    }, headers=DEMO_AUTH)
    parent_jwt = parent_resp.json()["token"]
    child_resp = client.post("/anip/tokens", json={
        "subject": "agent:sub-agent",
        "scope": ["travel.book:max_$500"],
        "capability": "book_flight",
        "parent_token": parent_jwt,
    }, headers=AGENT_AUTH)
    body = child_resp.json()
    assert body["issued"] is False
```

**Step 2: Run tests to verify they fail**

Run: `cd examples/anip && python -m pytest tests/test_token_issuance.py -v`
Expected: FAIL — current endpoint returns `{"registered": true}` not `{"issued": true}`

**Step 3: Add TokenRequest model**

In `models.py`, after the `DelegationToken` class (after line 54), add:

```python
class TokenRequest(BaseModel):
    """Client request for token issuance. The server controls signing and metadata.

    The caller authenticates via Authorization header. The server derives
    root_principal from the authenticated identity, not from the request body.
    """
    subject: str
    scope: list[str]
    capability: str
    parent_token: str | None = None  # JWT string of parent (for child issuance)
    purpose_parameters: dict[str, Any] = Field(default_factory=dict)
    ttl_hours: int = 2
```

**Step 4: Add issue_token() to delegation.py**

In `delegation.py`, add a new function that creates the internal `DelegationToken` and stores it:

```python
import uuid
from datetime import timedelta


def issue_token(
    request_subject: str,
    request_scope: list[str],
    request_capability: str,
    issuer_id: str,
    parent_token: DelegationToken | None = None,
    purpose_parameters: dict | None = None,
    ttl_hours: int = 2,
    max_delegation_depth: int = 3,
) -> tuple[DelegationToken, str]:
    """Issue a new delegation token.

    Returns (token, token_id). The caller is responsible for JWT signing.
    Validates scope/constraint narrowing against parent if present.
    """
    token_id = f"anip-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=ttl_hours)

    concurrent = ConcurrentBranches.ALLOWED
    if parent_token is not None:
        max_delegation_depth = min(
            max_delegation_depth,
            parent_token.constraints.max_delegation_depth,
        )
        concurrent = parent_token.constraints.concurrent_branches

    token = DelegationToken(
        token_id=token_id,
        issuer=issuer_id,
        subject=request_subject,
        scope=request_scope,
        purpose=Purpose(
            capability=request_capability,
            parameters=purpose_parameters or {},
            task_id=f"task-{token_id}",
        ),
        parent=parent_token.token_id if parent_token else None,
        expires=expires,
        constraints=DelegationConstraints(
            max_delegation_depth=max_delegation_depth,
            concurrent_branches=concurrent,
        ),
    )

    # Validate narrowing if this is a child token
    if parent_token is not None:
        scope_failure = validate_scope_narrowing(token)
        if scope_failure is not None:
            raise ValueError(scope_failure.detail)
        constraint_failure = validate_constraints_narrowing(token)
        if constraint_failure is not None:
            raise ValueError(constraint_failure.detail)

    register_token(token)
    return token, token_id
```

**Step 5: Rewrite POST /anip/tokens in main.py**

Replace the existing `register_delegation_token` function (lines 170-193) with:

First, add an API key registry and authentication helper at module level:

```python
from fastapi import Header

# API key → identity mapping. In production, this would be a database or
# identity provider lookup. For the reference implementation, demo keys are
# hardcoded. The key is what matters — issuance requires authentication.
_api_key_identities: dict[str, str] = {
    "demo-human-key": "human:samir@example.com",
    "demo-agent-key": "agent:demo-agent",
}


def _authenticate_caller(authorization: str | None) -> str | None:
    """Extract identity from Authorization header.

    Returns the caller's identity string, or None if unauthenticated.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    key = authorization.removeprefix("Bearer ").strip()
    return _api_key_identities.get(key)
```

Then the endpoint:

```python
from .primitives.models import TokenRequest


@app.post("/anip/tokens")
def issue_delegation_token(
    request: TokenRequest,
    authorization: str | None = Header(None),
):
    """Issue a signed delegation token.

    v0.2: The server constructs and signs the JWT. The client authenticates
    via Authorization header; the server derives root_principal from the
    authenticated identity, not from the request body.
    """
    from .primitives.delegation import issue_token

    # Authenticate the caller
    caller_identity = _authenticate_caller(authorization)
    if caller_identity is None:
        return {"issued": False, "error": "authentication required — provide Authorization: Bearer <key>"}

    parent_token = None
    root_principal = caller_identity  # Default: caller is the root

    if request.parent_token is not None:
        # Child issuance: verify parent JWT and check caller authorization
        try:
            parent_claims = _keys.verify_jwt(request.parent_token)
        except Exception as e:
            return {"issued": False, "error": f"invalid parent token: {e}"}
        parent_stored = get_token(parent_claims["jti"])
        if parent_stored is None:
            return {"issued": False, "error": "parent token not found in store"}
        # Only the parent token's subject can sub-delegate
        if caller_identity != parent_stored.subject:
            return {
                "issued": False,
                "error": f"caller '{caller_identity}' is not the parent token's subject "
                         f"('{parent_stored.subject}') — only the delegatee can sub-delegate",
            }
        parent_token = parent_stored
        # Root principal comes from the parent chain, not the child caller
        root_principal = get_root_principal(parent_stored)

    try:
        token, token_id = issue_token(
            request_subject=request.subject,
            request_scope=request.scope,
            request_capability=request.capability,
            issuer_id="anip-flight-service",
            parent_token=parent_token,
            purpose_parameters=request.purpose_parameters,
            ttl_hours=request.ttl_hours,
        )
    except ValueError as e:
        return {"issued": False, "error": str(e)}

    # Extract budget from scope for JWT claims
    budget = None
    for s in request.scope:
        if ":max_$" in s:
            budget = {"max": float(s.split(":max_$")[1]), "currency": "USD"}
            break

    # Build JWT claims — these are the cryptographic authority.
    # Every trust-critical field must be signed so _resolve_jwt_token()
    # can detect store tampering.
    claims = {
        "jti": token_id,
        "iss": "anip-flight-service",
        "sub": request.subject,
        "aud": "anip-flight-service",
        "iat": int(token.expires.timestamp()) - (request.ttl_hours * 3600),
        "exp": int(token.expires.timestamp()),
        "scope": request.scope,
        "capability": request.capability,
        "purpose": token.purpose.model_dump(),
        "root_principal": root_principal,
        "constraints": token.constraints.model_dump(),
    }
    if parent_token is not None:
        claims["parent_token_id"] = parent_token.token_id
    if budget is not None:
        claims["budget"] = budget

    jwt_str = _keys.sign_jwt(claims)

    return {
        "issued": True,
        "token_id": token_id,
        "token": jwt_str,
        "expires": token.expires.isoformat(),
    }
```

Also add the import at the top of main.py:

```python
from .primitives.delegation import get_token
```

**Step 6: Run tests to verify they pass**

Run: `cd examples/anip && python -m pytest tests/test_token_issuance.py -v`
Expected: All 6 tests PASS.

**Step 7: Commit**

```bash
git add examples/anip/anip_server/primitives/models.py examples/anip/anip_server/primitives/delegation.py examples/anip/anip_server/main.py examples/anip/tests/test_token_issuance.py
git commit -m "feat: replace token registration with server-side JWT issuance"
```

---

### Task 4: JWT Verification on Protected Endpoints

**Context:** The permissions, invoke, and audit endpoints currently accept a full `DelegationToken` body. In v0.2, clients present their JWT string and the server verifies the signature, decodes claims, and resolves to the stored token. This task updates those endpoints.

**Files:**
- Modify: `examples/anip/anip_server/primitives/models.py` (add `TokenPresentation` model)
- Modify: `examples/anip/anip_server/main.py:199-403` (update permissions, invoke, audit endpoints)
- Create: `examples/anip/tests/test_token_verification.py`

**Step 1: Write the failing tests**

```python
# examples/anip/tests/test_token_verification.py
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
    from anip_server.data.database import get_connection
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
```

**Step 2: Run tests to verify they fail**

Run: `cd examples/anip && python -m pytest tests/test_token_verification.py -v`
Expected: FAIL — endpoints expect `DelegationToken` body, not `{"token": "jwt..."}`

**Step 3: Add TokenPresentation model and update endpoints**

In `models.py`, add:

```python
class TokenPresentation(BaseModel):
    """JWT token presentation for v0.2 protected endpoints."""
    token: str  # JWT string
```

In `models.py`, update `InvokeRequest`:

```python
class InvokeRequestV2(BaseModel):
    """v0.2 invocation request with JWT token."""
    token: str  # JWT string
    parameters: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] | None = None
```

In `main.py`, add a helper function to resolve a JWT to a stored token.

**CRITICAL:** The signed JWT claims are the authority source, not the mutable store.
After loading the stored token, we MUST compare the JWT claims against the stored
values for `sub`, `scope`, `capability`, and `exp`. If they diverge, the store has
been tampered with and the request is rejected. This prevents a DB mutation from
silently widening scope or changing identity after a token was signed.

```python
def _resolve_jwt_token(token_jwt: str) -> DelegationToken | ANIPFailure:
    """Verify JWT signature and resolve to stored token.

    The JWT claims are the cryptographic authority. After loading the stored
    token, we verify that critical fields (sub, scope, capability, exp) match
    the signed claims. If the store has been mutated, the request is rejected.
    """
    try:
        claims = _keys.verify_jwt(token_jwt)
    except Exception as e:
        return ANIPFailure(
            type="invalid_token",
            detail=f"JWT verification failed: {e}",
            resolution=Resolution(action="present_valid_token"),
            retry=False,
        )
    token_id = claims.get("jti")
    if not token_id:
        return ANIPFailure(
            type="invalid_token",
            detail="JWT missing jti claim",
            resolution=Resolution(action="present_valid_token"),
            retry=False,
        )
    stored = get_token(token_id)
    if stored is None:
        return ANIPFailure(
            type="token_not_registered",
            detail=f"token '{token_id}' not found in store",
            resolution=Resolution(action="issue_new_token"),
            retry=True,
        )

    # TRUST BOUNDARY: compare ALL trust-critical signed claims against stored values.
    # The JWT is the authority — if the store diverges, reject.
    # This covers identity, scope, capability, delegation linkage, and constraints.
    mismatches = []
    if claims.get("sub") != stored.subject:
        mismatches.append(f"sub: jwt={claims.get('sub')} store={stored.subject}")
    if sorted(claims.get("scope", [])) != sorted(stored.scope):
        mismatches.append(f"scope: jwt={claims.get('scope')} store={stored.scope}")
    if claims.get("capability") != stored.purpose.capability:
        mismatches.append(f"capability: jwt={claims.get('capability')} store={stored.purpose.capability}")
    # root_principal: controls audit visibility — must match signed claim
    jwt_root = claims.get("root_principal")
    stored_root = get_root_principal(stored)
    if jwt_root is not None and jwt_root != stored_root:
        mismatches.append(f"root_principal: jwt={jwt_root} store={stored_root}")
    # parent linkage: a store mutation could graft the token onto a different chain
    jwt_parent = claims.get("parent_token_id")
    if jwt_parent != stored.parent:
        mismatches.append(f"parent: jwt={jwt_parent} store={stored.parent}")
    # delegation constraints: a store mutation could raise max_delegation_depth
    # or weaken concurrent_branches from exclusive to allowed
    jwt_constraints = claims.get("constraints")
    if jwt_constraints is not None:
        stored_constraints = stored.constraints.model_dump()
        if jwt_constraints != stored_constraints:
            mismatches.append(f"constraints: jwt={jwt_constraints} store={stored_constraints}")
    if mismatches:
        return ANIPFailure(
            type="token_integrity_violation",
            detail=f"Signed JWT claims diverge from stored token: {'; '.join(mismatches)}. "
                   "The stored token may have been tampered with.",
            resolution=Resolution(action="reissue_token"),
            retry=False,
        )

    return stored
```

Update the three protected endpoints to accept `TokenPresentation` / `InvokeRequestV2` and use `_resolve_jwt_token()`. Keep the old `DelegationToken` path as fallback for `--trust-on-declaration` mode (Task 6 will formalize this; for now, the new path is the default).

Update `query_permissions` (line 199):

```python
@app.post("/anip/permissions")
def query_permissions(presentation: TokenPresentation):
    resolved = _resolve_jwt_token(presentation.token)
    if isinstance(resolved, ANIPFailure):
        raise HTTPException(status_code=401, detail=resolved.detail)
    return discover_permissions(resolved, _manifest.capabilities)
```

Update `invoke_capability` (line 214):

```python
@app.post("/anip/invoke/{capability_name}")
def invoke_capability(capability_name: str, request: InvokeRequestV2):
    # Resolve JWT to stored token
    jwt_resolved = _resolve_jwt_token(request.token)
    if isinstance(jwt_resolved, ANIPFailure):
        return InvokeResponse(success=False, failure=jwt_resolved)
    token = jwt_resolved
    # ... rest of invocation logic unchanged, but using resolved token
```

Update `get_audit_log` (line 369):

```python
@app.post("/anip/audit")
def get_audit_log(
    presentation: TokenPresentation,
    capability: str | None = Query(None),
    since: str | None = Query(None),
    limit: int = Query(100, le=1000),
):
    resolved = _resolve_jwt_token(presentation.token)
    if isinstance(resolved, ANIPFailure):
        raise HTTPException(status_code=401, detail=resolved.detail)
    token = resolved
    root_principal = get_root_principal(token)
    entries = query_audit_log(
        capability=capability,
        root_principal=root_principal,
        since=since,
        limit=limit,
    )
    return {
        "entries": entries,
        "count": len(entries),
        "root_principal": root_principal,
        "capability_filter": capability,
        "since_filter": since,
    }
```

**Step 4: Run tests to verify they pass**

Run: `cd examples/anip && python -m pytest tests/test_token_verification.py -v`
Expected: All 5 tests PASS.

**Step 5: Run all tests to check nothing is broken**

Run: `cd examples/anip && python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add examples/anip/anip_server/primitives/models.py examples/anip/anip_server/main.py examples/anip/tests/test_token_verification.py
git commit -m "feat: JWT verification on permissions, invoke, and audit endpoints"
```

---

### Task 5: Trust Mode Flag (--trust-on-declaration)

**Context:** v0.1 behavior must remain available as a dev escape hatch. When `--trust-on-declaration` is passed (or `ANIP_TRUST_MODE=declaration` env var), the server accepts the old unsigned token format. In signed mode (default), only JWTs are accepted. The server logs a warning in trust-on-declaration mode.

**Files:**
- Modify: `examples/anip/anip_server/main.py` (add trust mode config, dual-path endpoints)
- Create: `examples/anip/tests/test_trust_mode.py`

**Step 1: Write the failing tests**

```python
# examples/anip/tests/test_trust_mode.py
"""Tests for trust mode switching."""

import os

import pytest
from fastapi.testclient import TestClient


def test_default_mode_is_signed():
    """Without env override, server requires JWT tokens."""
    # Import fresh to get default config
    from anip_server.main import get_trust_mode
    assert get_trust_mode() == "signed"


def test_declaration_mode_accepts_old_format(monkeypatch):
    """In trust-on-declaration mode, the old DelegationToken format works."""
    monkeypatch.setenv("ANIP_TRUST_MODE", "declaration")
    # Need to reimport to pick up env change
    from anip_server.main import app, set_trust_mode
    set_trust_mode("declaration")
    client = TestClient(app)
    # Old-style token registration
    resp = client.post("/anip/tokens", json={
        "token_id": "test-old-style",
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
        "token_id": "test-old-style",
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
```

**Step 2: Run tests to verify they fail**

Run: `cd examples/anip && python -m pytest tests/test_trust_mode.py -v`
Expected: FAIL — `get_trust_mode` and `set_trust_mode` don't exist

**Step 3: Implement trust mode**

In `main.py`, add at the top (after imports):

```python
import logging
import os

logger = logging.getLogger("anip")

_trust_mode = os.environ.get("ANIP_TRUST_MODE", "signed")

def get_trust_mode() -> str:
    return _trust_mode

def set_trust_mode(mode: str) -> None:
    global _trust_mode
    _trust_mode = mode
    if mode == "declaration":
        logger.warning(
            "ANIP server running in trust-on-declaration mode. "
            "Tokens are NOT cryptographically verified. "
            "Do NOT use this in production."
        )
```

Update `POST /anip/tokens` to accept both formats based on trust mode:

```python
from fastapi import Body

@app.post("/anip/tokens")
def issue_or_register_token(request: dict = Body(...)):
    """Issue a signed delegation token (v0.2) or register unsigned (v0.1 compat).

    In signed mode (default): expects TokenRequest fields, returns JWT.
    In declaration mode: accepts DelegationToken fields, registers as-is.
    """
    if _trust_mode == "declaration":
        # v0.1 path: accept full DelegationToken
        try:
            token = DelegationToken(**request)
        except Exception as e:
            return {"registered": False, "error": str(e)}
        parent_failure = validate_parent_exists(token)
        if parent_failure is not None:
            return {"registered": False, "error": parent_failure.detail}
        scope_failure = validate_scope_narrowing(token)
        if scope_failure is not None:
            return {"registered": False, "error": scope_failure.detail}
        constraint_failure = validate_constraints_narrowing(token)
        if constraint_failure is not None:
            return {"registered": False, "error": constraint_failure.detail}
        register_token(token)
        return {"registered": True, "token_id": token.token_id}
    else:
        # v0.2 path: server-side issuance
        # ... (existing issuance code from Task 3)
```

Similarly, update permissions, invoke, and audit endpoints to accept both formats:

```python
@app.post("/anip/permissions")
def query_permissions(request: dict = Body(...)):
    if _trust_mode == "declaration" and "token_id" in request:
        # v0.1 path
        token = DelegationToken(**request)
        resolved = resolve_registered_token(token)
        if isinstance(resolved, ANIPFailure):
            raise HTTPException(status_code=401, detail=resolved.detail)
        return discover_permissions(resolved, _manifest.capabilities)
    else:
        # v0.2 path
        token_jwt = request.get("token", "")
        resolved = _resolve_jwt_token(token_jwt)
        if isinstance(resolved, ANIPFailure):
            raise HTTPException(status_code=401, detail=resolved.detail)
        return discover_permissions(resolved, _manifest.capabilities)
```

Apply the same pattern to invoke and audit endpoints.

**Step 4: Run tests to verify they pass**

Run: `cd examples/anip && python -m pytest tests/test_trust_mode.py -v`
Expected: All tests PASS.

**Step 5: Run all tests**

Run: `cd examples/anip && python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add examples/anip/anip_server/main.py examples/anip/tests/test_trust_mode.py
git commit -m "feat: add trust mode flag with v0.1 backward compatibility"
```

---

### Task 6: Manifest Signing (Detached JWS)

**Context:** Phase 2. The manifest is signed once at startup. The signature is returned as an `X-ANIP-Signature` response header on `GET /anip/manifest`. Adds `manifest_metadata` and `service_identity` sections to the manifest.

**Files:**
- Modify: `examples/anip/anip_server/primitives/models.py` (add `ManifestMetadata`, `ServiceIdentity`)
- Modify: `examples/anip/anip_server/primitives/manifest.py` (add metadata + identity to manifest)
- Modify: `examples/anip/anip_server/main.py:133-136` (sign manifest, add header)
- Create: `examples/anip/tests/test_manifest_signing.py`

**Step 1: Write the failing tests**

```python
# examples/anip/tests/test_manifest_signing.py
"""Tests for manifest signing with detached JWS."""

import json

from tests.conftest import client  # noqa: F401


def test_manifest_has_signature_header(client):
    resp = client.get("/anip/manifest")
    assert resp.status_code == 200
    assert "X-ANIP-Signature" in resp.headers
    sig = resp.headers["X-ANIP-Signature"]
    # Detached JWS: header..signature (empty payload)
    parts = sig.split(".")
    assert len(parts) == 3
    assert parts[1] == ""


def test_manifest_has_metadata(client):
    resp = client.get("/anip/manifest")
    body = resp.json()
    assert "manifest_metadata" in body
    meta = body["manifest_metadata"]
    assert "version" in meta
    assert "sha256" in meta
    assert "issued_at" in meta
    assert "expires_at" in meta


def test_manifest_has_service_identity(client):
    resp = client.get("/anip/manifest")
    body = resp.json()
    assert "service_identity" in body
    identity = body["service_identity"]
    assert "id" in identity
    assert "jwks_uri" in identity
    assert identity["issuer_mode"] == "first-party"


def test_manifest_signature_verifies_cryptographically(client):
    """Detached JWS signature must cryptographically verify against the manifest body."""
    import base64
    import json as json_mod
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    from cryptography.hazmat.primitives import hashes

    # Get the public key from JWKS
    jwks_resp = client.get("/.well-known/jwks.json")
    jwk = jwks_resp.json()["keys"][0]  # delegation key (use=sig)

    # Reconstruct the EC public key from JWK coordinates
    def _pad_b64(s):
        return s + "=" * (4 - len(s) % 4) if len(s) % 4 else s

    x = int.from_bytes(base64.urlsafe_b64decode(_pad_b64(jwk["x"])), "big")
    y = int.from_bytes(base64.urlsafe_b64decode(_pad_b64(jwk["y"])), "big")
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicNumbers, SECP256R1
    pub_key = EllipticCurvePublicNumbers(x, y, SECP256R1()).public_key()

    # Get manifest + detached signature
    manifest_resp = client.get("/anip/manifest")
    sig_header = manifest_resp.headers["X-ANIP-Signature"]
    # The manifest body as the server serialized it
    manifest_bytes = manifest_resp.content

    # Parse detached JWS: header..signature
    parts = sig_header.split(".")
    assert len(parts) == 3
    assert parts[1] == ""  # detached = empty payload
    header_b64, _, sig_b64 = parts

    # Reconstruct signing input: header_b64 + "." + base64url(manifest_bytes)
    payload_b64 = base64.urlsafe_b64encode(manifest_bytes).rstrip(b"=").decode()
    signing_input = f"{header_b64}.{payload_b64}".encode()

    # Decode signature (ES256 = r || s, 32 bytes each)
    sig_bytes = base64.urlsafe_b64decode(_pad_b64(sig_b64))
    r = int.from_bytes(sig_bytes[:32], "big")
    s = int.from_bytes(sig_bytes[32:], "big")
    der_sig = encode_dss_signature(r, s)

    # Verify — this will raise if the signature is invalid
    pub_key.verify(der_sig, signing_input, ec.ECDSA(hashes.SHA256()))
    # If we reach here, the signature is valid


def test_manifest_protocol_is_v02(client):
    resp = client.get("/anip/manifest")
    body = resp.json()
    assert body["protocol"] == "anip/0.2"
```

**Step 2: Run tests to verify they fail**

Run: `cd examples/anip && python -m pytest tests/test_manifest_signing.py -v`
Expected: FAIL — no `X-ANIP-Signature` header, no `manifest_metadata`, protocol is `anip/1.0`

**Step 3: Add ManifestMetadata and ServiceIdentity models**

In `models.py`, add before `ANIPManifest`:

```python
class ManifestMetadata(BaseModel):
    version: str = "0.2.0"
    sha256: str = ""  # Set at build time
    issued_at: str = ""  # Set at build time
    expires_at: str = ""  # Set at build time


class ServiceIdentity(BaseModel):
    id: str = "anip-flight-service"
    jwks_uri: str = "/.well-known/jwks.json"
    issuer_mode: str = "first-party"
```

Update `ANIPManifest`:

```python
class ANIPManifest(BaseModel):
    protocol: str = "anip/0.2"
    profile: ProfileVersions
    capabilities: dict[str, CapabilityDeclaration]
    manifest_metadata: ManifestMetadata | None = None
    service_identity: ServiceIdentity | None = None
```

**Step 4: Update manifest building and serving**

In `manifest.py`, update `build_manifest()` to include metadata and identity:

```python
import hashlib
import json
from datetime import datetime, timedelta, timezone


def build_manifest():
    # ... existing capability assembly ...
    manifest = ANIPManifest(
        protocol="anip/0.2",
        profile=ProfileVersions(...),
        capabilities=capabilities,
        service_identity=ServiceIdentity(),
    )
    # Compute sha256 over capabilities (excluding metadata itself)
    caps_json = json.dumps(
        {k: v.model_dump() for k, v in capabilities.items()},
        sort_keys=True,
    ).encode()
    now = datetime.now(timezone.utc)
    manifest.manifest_metadata = ManifestMetadata(
        sha256=hashlib.sha256(caps_json).hexdigest(),
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(days=30)).isoformat(),
    )
    return manifest
```

In `main.py`, update the manifest endpoint:

```python
from fastapi.responses import JSONResponse

@app.get("/anip/manifest")
def get_manifest():
    """Full ANIP manifest with detached JWS signature."""
    manifest_dict = _manifest.model_dump()
    manifest_bytes = json.dumps(manifest_dict, separators=(",", ":"), sort_keys=True).encode()
    signature = _keys.sign_jws_detached(manifest_bytes)
    return JSONResponse(
        content=manifest_dict,
        headers={"X-ANIP-Signature": signature},
    )
```

Add `import json` at the top of main.py if not already present.

**Step 5: Run tests to verify they pass**

Run: `cd examples/anip && python -m pytest tests/test_manifest_signing.py -v`
Expected: All 5 tests PASS.

**Step 6: Commit**

```bash
git add examples/anip/anip_server/primitives/models.py examples/anip/anip_server/primitives/manifest.py examples/anip/anip_server/main.py examples/anip/tests/test_manifest_signing.py
git commit -m "feat: signed manifests with detached JWS and manifest metadata"
```

---

### Task 7: Discovery Endpoint Updates

**Context:** The discovery endpoint needs to advertise `jwks_uri`, update the protocol version to `0.2`, and reflect the new auth model.

**Files:**
- Modify: `examples/anip/anip_server/main.py:55-127` (discovery endpoint)
- Create: `examples/anip/tests/test_discovery.py`

**Step 1: Write the failing tests**

```python
# examples/anip/tests/test_discovery.py
"""Tests for the v0.2 discovery endpoint."""

from tests.conftest import client  # noqa: F401


def test_discovery_protocol_version(client):
    resp = client.get("/.well-known/anip")
    disco = resp.json()["anip_discovery"]
    assert disco["protocol"] == "anip/0.2"


def test_discovery_has_jwks_uri(client):
    resp = client.get("/.well-known/anip")
    disco = resp.json()["anip_discovery"]
    assert "jwks_uri" in disco
    assert disco["jwks_uri"].endswith("/.well-known/jwks.json")


def test_discovery_auth_format_includes_jwt(client):
    resp = client.get("/.well-known/anip")
    auth = resp.json()["anip_discovery"]["auth"]
    assert "jwt-es256" in auth["supported_formats"]


def test_discovery_endpoints_include_jwks(client):
    resp = client.get("/.well-known/anip")
    endpoints = resp.json()["anip_discovery"]["endpoints"]
    assert "jwks" in endpoints
    assert endpoints["jwks"] == "/.well-known/jwks.json"
```

**Step 2: Run tests to verify they fail**

Run: `cd examples/anip && python -m pytest tests/test_discovery.py -v`
Expected: FAIL — protocol is `anip/1.0`, no `jwks_uri`

**Step 3: Update discovery endpoint**

In `main.py`, update the discovery function:

- Change `_manifest.protocol` reference or hardcode `"anip/0.2"` in the discovery response
- Add `"jwks_uri": f"{base_url}/.well-known/jwks.json"` to the top-level discovery object
- Update `auth.supported_formats` to `["jwt-es256", "anip-v1"]`
- Add `"jwks": "/.well-known/jwks.json"` to endpoints dict

**Step 4: Run tests to verify they pass**

Run: `cd examples/anip && python -m pytest tests/test_discovery.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add examples/anip/anip_server/main.py examples/anip/tests/test_discovery.py
git commit -m "feat: update discovery endpoint for v0.2 with JWKS and JWT auth"
```

---

### Task 8: Audit Log Schema Migration (Hash Chain + Signature)

**Context:** Phase 3 starts here. Audit entries need three new columns: `sequence_number` (global monotonic), `previous_hash` (SHA-256 of prior entry), and `signature` (ES256 over canonical entry). This task migrates the schema and updates the write/read functions.

**Files:**
- Modify: `examples/anip/anip_server/data/database.py:46-104` (schema), `251-285` (log_invocation), `288-325` (query_audit_log)
- Create: `examples/anip/tests/test_audit_schema.py`

**Step 1: Write the failing tests**

```python
# examples/anip/tests/test_audit_schema.py
"""Tests for v0.2 audit log schema with hash chain."""

import sqlite3

from anip_server.data.database import get_connection, log_invocation, query_audit_log


def test_audit_table_has_new_columns():
    conn = get_connection()
    cursor = conn.execute("PRAGMA table_info(audit_log)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "sequence_number" in columns
    assert "previous_hash" in columns
    assert "signature" in columns


def test_first_audit_entry_has_sentinel_previous_hash():
    log_invocation(
        capability="test_cap",
        token_id="test-001",
        issuer="human:test@example.com",
        subject="agent:test",
        root_principal="human:test@example.com",
        parameters={"key": "value"},
        success=True,
    )
    entries = query_audit_log(root_principal="human:test@example.com")
    assert len(entries) >= 1
    entry = entries[-1]  # most recent (ordered DESC)
    assert "previous_hash" in entry
    # First entry uses sentinel
    assert entry["sequence_number"] >= 1


def test_sequential_entries_form_hash_chain():
    log_invocation(
        capability="test_chain_1",
        token_id="test-chain-1",
        issuer="human:chain@example.com",
        subject="agent:test",
        root_principal="human:chain@example.com",
        parameters={},
        success=True,
    )
    log_invocation(
        capability="test_chain_2",
        token_id="test-chain-2",
        issuer="human:chain@example.com",
        subject="agent:test",
        root_principal="human:chain@example.com",
        parameters={},
        success=True,
    )
    entries = query_audit_log(root_principal="human:chain@example.com")
    # Entries are DESC, so [0] is newest, [1] is older
    if len(entries) >= 2:
        newer = entries[0]
        older = entries[1]
        # Newer entry's previous_hash should reference the older entry
        assert newer["previous_hash"] != older["previous_hash"]
        assert newer["sequence_number"] > older["sequence_number"]
```

**Step 2: Run tests to verify they fail**

Run: `cd examples/anip && python -m pytest tests/test_audit_schema.py -v`
Expected: FAIL — columns don't exist

**Step 3: Update schema and functions**

Update `_init_schema()` in `database.py` — add columns to `audit_log`:

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_number INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    capability TEXT NOT NULL,
    token_id TEXT,
    issuer TEXT,
    subject TEXT,
    root_principal TEXT,
    parameters TEXT,
    success INTEGER NOT NULL,
    result_summary TEXT,
    failure_type TEXT,
    cost_actual TEXT,
    delegation_chain TEXT,
    previous_hash TEXT NOT NULL,
    signature TEXT
);
```

Add a helper to compute the hash of an entry:

```python
import hashlib

def _compute_entry_hash(entry: dict[str, Any]) -> str:
    """Compute SHA-256 hash of an audit entry for the hash chain."""
    # Canonical form: sorted keys, compact JSON
    canonical = json.dumps(
        {k: v for k, v in sorted(entry.items()) if k not in ("signature", "id")},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"
```

Update `log_invocation()` to:
1. Query the last entry's hash (or use sentinel `"sha256:0"` for first entry)
2. Assign `sequence_number = last_sequence + 1`
3. Compute `previous_hash` from the last entry
4. Store the new columns

Update `query_audit_log()` to include the new fields in results.

**Step 4: Run tests to verify they pass**

Run: `cd examples/anip && python -m pytest tests/test_audit_schema.py -v`
Expected: All 3 tests PASS.

**Step 5: Delete the old database file to reset schema**

Run: `rm -f examples/anip/anip_server/data/anip.db`

**Step 6: Run all tests**

Run: `cd examples/anip && python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 7: Commit**

```bash
git add examples/anip/anip_server/data/database.py examples/anip/tests/test_audit_schema.py
git commit -m "feat: audit log hash chain with sequence numbers and previous_hash"
```

---

### Task 9: Audit Entry Signing

**Context:** Each audit entry is signed with a dedicated audit key (separate from the delegation signing key, per design doc). The signature covers all entry fields except `signature` itself. The KeyManager gets a second key pair for audit.

**Files:**
- Modify: `examples/anip/anip_server/primitives/crypto.py` (add audit key)
- Modify: `examples/anip/anip_server/data/database.py` (sign entries at write time)
- Modify: `examples/anip/anip_server/main.py` (pass audit key to database layer)
- Create: `examples/anip/tests/test_audit_signing.py`

**Step 1: Write the failing tests**

```python
# examples/anip/tests/test_audit_signing.py
"""Tests for audit entry signing."""

from anip_server.data.database import log_invocation, query_audit_log
from anip_server.primitives.crypto import KeyManager


def test_audit_entries_have_signatures():
    log_invocation(
        capability="test_signed",
        token_id="test-sig-001",
        issuer="human:sig@example.com",
        subject="agent:test",
        root_principal="human:sig@example.com",
        parameters={"action": "test"},
        success=True,
    )
    entries = query_audit_log(root_principal="human:sig@example.com")
    signed_entries = [e for e in entries if e["capability"] == "test_signed"]
    assert len(signed_entries) >= 1
    assert signed_entries[0]["signature"] is not None
    assert len(signed_entries[0]["signature"]) > 0
```

**Step 2: Run tests to verify they fail**

Run: `cd examples/anip && python -m pytest tests/test_audit_signing.py -v`
Expected: FAIL — signature is None

**Step 3: Add audit key to KeyManager**

In `crypto.py`, add a second key pair:

```python
class KeyManager:
    def __init__(self) -> None:
        # Delegation signing key
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        self._public_key = self._private_key.public_key()
        pub_bytes = self._public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self._kid = hashlib.sha256(pub_bytes).hexdigest()[:16]

        # Audit signing key (separate from delegation key)
        self._audit_private_key = ec.generate_private_key(ec.SECP256R1())
        self._audit_public_key = self._audit_private_key.public_key()
        audit_pub_bytes = self._audit_public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self._audit_kid = hashlib.sha256(audit_pub_bytes).hexdigest()[:16]

    def sign_audit_entry(self, entry_data: dict) -> str:
        """Sign an audit entry with the dedicated audit key."""
        canonical = json.dumps(
            {k: v for k, v in sorted(entry_data.items()) if k != "signature"},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        private_pem = self._audit_private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        return jwt.encode(
            {"audit_hash": hashlib.sha256(canonical).hexdigest()},
            private_pem,
            algorithm="ES256",
            headers={"kid": self._audit_kid},
        )

    def get_jwks(self) -> dict:
        """Return both delegation and audit public keys."""
        # ... existing delegation key ...
        # Add audit key with use="audit"
```

Update the JWKS to include both keys (delegation key with `use: "sig"`, audit key with `use: "audit"`).

**Step 4: Wire audit signing into log_invocation**

The `log_invocation` function in `database.py` needs access to the KeyManager. Add a module-level setter or pass it as a parameter. The simplest approach: add a module-level `_audit_signer` that `main.py` sets at startup.

In `database.py`:

```python
_audit_signer = None

def set_audit_signer(signer):
    global _audit_signer
    _audit_signer = signer
```

In `log_invocation()`, after building the entry dict, call `_audit_signer.sign_audit_entry(entry)` and store the result in the `signature` column.

In `main.py` at startup:

```python
from .data.database import set_audit_signer
set_audit_signer(_keys)
```

**Step 5: Run tests to verify they pass**

Run: `cd examples/anip && python -m pytest tests/test_audit_signing.py -v`
Expected: PASS.

**Step 6: Run all tests**

Run: `cd examples/anip && python -m pytest tests/ -v`
Expected: All tests PASS.

**Step 7: Commit**

```bash
git add examples/anip/anip_server/primitives/crypto.py examples/anip/anip_server/data/database.py examples/anip/anip_server/main.py examples/anip/tests/test_audit_signing.py
git commit -m "feat: signed audit entries with dedicated audit key"
```

---

### Task 10: Conformance Test Suite

**Context:** A test suite that validates ANIP service behavior against its declarations. Tests side-effect accuracy, cost accuracy (model-aware), scope enforcement, budget enforcement, and failure semantics.

**Portability:** The suite MUST be runnable against any ANIP service URL, not just the bundled app. It accepts a `--anip-url` pytest flag (defaulting to in-process TestClient for convenience). This makes it a genuine portable verifier, not just regression coverage.

**Files:**
- Create: `examples/anip/tests/test_conformance.py`
- Modify: `examples/anip/tests/conftest.py` (add `--anip-url` flag and `service` fixture)

**Step 0: Update conftest.py**

Add the `--anip-url` flag and a `service` fixture that works against either a live URL or the in-process app:

```python
# Add to examples/anip/tests/conftest.py

import httpx


def pytest_addoption(parser):
    parser.addoption(
        "--anip-url", default=None,
        help="ANIP service URL for conformance tests (default: in-process TestClient)",
    )
    parser.addoption(
        "--anip-api-key", default="demo-human-key",
        help="API key for authenticated ANIP requests",
    )


class LiveServiceClient:
    """Thin wrapper around httpx that matches TestClient interface for conformance tests."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def get(self, path, **kwargs):
        return httpx.get(f"{self.base_url}{path}", **kwargs)

    def post(self, path, json=None, headers=None, **kwargs):
        headers = dict(headers or {})
        return httpx.post(f"{self.base_url}{path}", json=json, headers=headers, **kwargs)


@pytest.fixture
def service(request):
    """Service client — in-process TestClient or live HTTP client."""
    url = request.config.getoption("--anip-url")
    if url:
        api_key = request.config.getoption("--anip-api-key")
        return LiveServiceClient(url, api_key)
    return TestClient(app)


@pytest.fixture
def auth_headers(request):
    api_key = request.config.getoption("--anip-api-key", default="demo-human-key")
    return {"Authorization": f"Bearer {api_key}"}
```

**Step 1: Write the conformance tests**

```python
# examples/anip/tests/test_conformance.py
"""ANIP v0.2 Conformance Test Suite.

Validates that an ANIP service behaves according to its manifest declarations.
Portable: run against any ANIP service URL with --anip-url, or against the
bundled app in-process (default).

Usage:
    # Against bundled app (default)
    pytest tests/test_conformance.py -v

    # Against a live server
    pytest tests/test_conformance.py -v --anip-url http://localhost:8000 --anip-api-key my-key
"""

import pytest


def _issue(service, scope, capability, auth_headers):
    resp = service.post("/anip/tokens", json={
        "subject": "agent:conformance-tester",
        "scope": scope,
        "capability": capability,
    }, headers=auth_headers)
    return resp.json()["token"]


class TestSideEffectAccuracy:
    """Verify side_effect declarations match actual behavior."""

    def test_read_capability_does_not_mutate_state(self, service, auth_headers):
        """search_flights is declared as 'read' — calling it should not change state."""
        token = _issue(service, ["travel.search"], "search_flights", auth_headers)
        # Call twice with same params
        params = {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}
        r1 = service.post("/anip/invoke/search_flights", json={"token": token, "parameters": params})
        r2 = service.post("/anip/invoke/search_flights", json={"token": token, "parameters": params})
        assert r1.json()["result"] == r2.json()["result"]


class TestScopeEnforcement:
    """Verify scope constraints are enforced."""

    def test_wrong_capability_scope_is_rejected(self, service, auth_headers):
        """Token scoped for search should not allow booking."""
        token = _issue(service, ["travel.search"], "search_flights", auth_headers)
        resp = service.post("/anip/invoke/book_flight", json={
            "token": token,
            "parameters": {"flight_number": "AA100", "date": "2026-03-10", "passengers": 1},
        })
        body = resp.json()
        assert body["success"] is False
        assert body["failure"]["type"] in ("purpose_mismatch", "insufficient_authority")


class TestBudgetEnforcement:
    """Verify budget constraints from scope are enforced."""

    def test_over_budget_invocation_is_rejected(self, service, auth_headers):
        """Booking a flight that costs more than the budget should fail with budget_exceeded."""
        # First search to know prices
        search_token = _issue(service, ["travel.search"], "search_flights", auth_headers)
        search_resp = service.post("/anip/invoke/search_flights", json={
            "token": search_token,
            "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
        })
        flights = search_resp.json()["result"]["flights"]
        expensive = max(flights, key=lambda f: f["price"])

        # Try to book with a budget lower than the expensive flight
        book_token = _issue(service, ["travel.book:max_$100"], "book_flight", auth_headers)
        resp = service.post("/anip/invoke/book_flight", json={
            "token": book_token,
            "parameters": {
                "flight_number": expensive["flight_number"],
                "date": "2026-03-10",
                "passengers": 1,
            },
        })
        body = resp.json()
        assert body["success"] is False
        assert body["failure"]["type"] == "budget_exceeded"


class TestFailureSemantics:
    """Verify failures include structured resolution guidance."""

    def test_failure_has_type_detail_resolution(self, service, auth_headers):
        """Every ANIP failure must have type, detail, and resolution."""
        token = _issue(service, ["travel.book:max_$1"], "book_flight", auth_headers)
        resp = service.post("/anip/invoke/book_flight", json={
            "token": token,
            "parameters": {"flight_number": "AA100", "date": "2026-03-10", "passengers": 1},
        })
        body = resp.json()
        assert body["success"] is False
        failure = body["failure"]
        assert "type" in failure
        assert "detail" in failure
        assert "resolution" in failure
        assert "action" in failure["resolution"]

    def test_budget_exceeded_resolution_is_actionable(self, service, auth_headers):
        """Budget exceeded should tell the agent who can grant more budget."""
        token = _issue(service, ["travel.book:max_$1"], "book_flight", auth_headers)
        resp = service.post("/anip/invoke/book_flight", json={
            "token": token,
            "parameters": {"flight_number": "AA100", "date": "2026-03-10", "passengers": 1},
        })
        failure = resp.json()["failure"]
        assert failure["type"] == "budget_exceeded"
        assert failure["resolution"]["action"] == "request_budget_increase"
        assert "grantable_by" in failure["resolution"]


class TestCostAccuracy:
    """Verify actual costs fall within declared ranges."""

    def test_booking_cost_within_declared_range(self, service, auth_headers):
        """Actual booking cost should fall within manifest-declared cost range."""
        # Get manifest to know declared range
        manifest = service.get("/anip/manifest").json()
        book_cost = manifest["capabilities"]["book_flight"]["cost"]["financial"]
        range_min = book_cost["range_min"]
        range_max = book_cost["range_max"]

        # Search for cheapest flight
        search_token = _issue(service, ["travel.search"], "search_flights", auth_headers)
        flights = service.post("/anip/invoke/search_flights", json={
            "token": search_token,
            "parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
        }).json()["result"]["flights"]
        cheapest = min(flights, key=lambda f: f["price"])

        # Book it
        book_token = _issue(service, [f"travel.book:max_${int(cheapest['price']) + 100}"], "book_flight", auth_headers)
        resp = service.post("/anip/invoke/book_flight", json={
            "token": book_token,
            "parameters": {
                "flight_number": cheapest["flight_number"],
                "date": "2026-03-10",
                "passengers": 1,
            },
        })
        body = resp.json()
        assert body["success"] is True
        actual_cost = body["cost_actual"]["financial"]["amount"]
        assert range_min <= actual_cost <= range_max, (
            f"Actual cost ${actual_cost} outside declared range ${range_min}-${range_max}"
        )
```

**Step 2: Run conformance tests**

Run: `cd examples/anip && python -m pytest tests/test_conformance.py -v`
Expected: All tests PASS (if they fail, fix the server to match its declarations).

**Step 3: Commit**

```bash
git add examples/anip/tests/test_conformance.py
git commit -m "feat: ANIP v0.2 conformance test suite"
```

---

### Task 11: TypeScript Server — All Phases

**Context:** The TypeScript server at `examples/anip-ts/` mirrors the Python server. It needs the same v0.2 changes: JWT issuance, JWKS endpoint, manifest signing, audit hash chain. The TypeScript server uses Hono + Zod and stores everything in memory.

**Files:**
- Modify: `examples/anip-ts/package.json` (add `jose` dependency)
- Create: `examples/anip-ts/src/crypto.ts` (KeyManager equivalent)
- Modify: `examples/anip-ts/src/server.ts` (JWKS endpoint, token issuance, manifest signing, audit chain)
- Modify: `examples/anip-ts/src/types.ts` (add TokenRequest, ManifestMetadata, etc.)
- Modify: `examples/anip-ts/src/primitives/delegation.ts` (add issue_token)

**Step 1: Add jose dependency**

Run: `cd examples/anip-ts && npm install jose`

**Step 2: Create crypto.ts**

```typescript
// examples/anip-ts/src/crypto.ts
import * as jose from "jose";
import { readFileSync, writeFileSync, existsSync } from "fs";

interface PersistedKeys {
  delegationJwk: jose.JWK;
  delegationKid: string;
  auditJwk: jose.JWK;
  auditKid: string;
}

export class KeyManager {
  private privateKey!: CryptoKey;
  private publicKey!: CryptoKey;
  private kid!: string;
  private auditPrivateKey!: CryptoKey;
  private auditPublicKey!: CryptoKey;
  private auditKid!: string;
  private _ready: Promise<void>;
  private keyPath: string | undefined;

  constructor(keyPath?: string) {
    this.keyPath = keyPath;
    this._ready = this.init();
  }

  private async init() {
    // Try to load persisted keys first (same as Python: restart must not
    // invalidate issued tokens, signed manifests, or audit signatures)
    if (this.keyPath && existsSync(this.keyPath)) {
      await this.loadKeys(this.keyPath);
      return;
    }

    // Generate fresh keys
    const { publicKey, privateKey } = await jose.generateKeyPair("ES256");
    this.privateKey = privateKey as CryptoKey;
    this.publicKey = publicKey as CryptoKey;
    const jwk = await jose.exportJWK(this.publicKey);
    this.kid = await this.computeKid(jwk);

    // Audit key (separate from delegation key)
    const audit = await jose.generateKeyPair("ES256");
    this.auditPrivateKey = audit.privateKey as CryptoKey;
    this.auditPublicKey = audit.publicKey as CryptoKey;
    const auditJwk = await jose.exportJWK(this.auditPublicKey);
    this.auditKid = await this.computeKid(auditJwk);

    // Persist for next restart
    if (this.keyPath) {
      await this.saveKeys(this.keyPath);
    }
  }

  private async saveKeys(path: string): Promise<void> {
    const delegationJwk = await jose.exportJWK(this.privateKey);
    const auditJwk = await jose.exportJWK(this.auditPrivateKey);
    const data: PersistedKeys = {
      delegationJwk,
      delegationKid: this.kid,
      auditJwk,
      auditKid: this.auditKid,
    };
    writeFileSync(path, JSON.stringify(data), "utf-8");
  }

  private async loadKeys(path: string): Promise<void> {
    const data: PersistedKeys = JSON.parse(readFileSync(path, "utf-8"));
    this.kid = data.delegationKid;
    this.privateKey = (await jose.importJWK(data.delegationJwk, "ES256")) as CryptoKey;
    this.publicKey = (await jose.importJWK(
      { ...data.delegationJwk, d: undefined }, "ES256"
    )) as CryptoKey;
    this.auditKid = data.auditKid;
    this.auditPrivateKey = (await jose.importJWK(data.auditJwk, "ES256")) as CryptoKey;
    this.auditPublicKey = (await jose.importJWK(
      { ...data.auditJwk, d: undefined }, "ES256"
    )) as CryptoKey;
  }

  private async computeKid(jwk: jose.JWK): Promise<string> {
    const thumbprint = await jose.calculateJwkThumbprint(jwk);
    return thumbprint.slice(0, 16);
  }

  async ready(): Promise<void> {
    return this._ready;
  }

  async getJWKS(): Promise<{ keys: jose.JWK[] }> {
    await this._ready;
    const delegationJwk = await jose.exportJWK(this.publicKey);
    const auditJwk = await jose.exportJWK(this.auditPublicKey);
    return {
      keys: [
        { ...delegationJwk, kid: this.kid, alg: "ES256", use: "sig" },
        { ...auditJwk, kid: this.auditKid, alg: "ES256", use: "audit" },
      ],
    };
  }

  async signJWT(payload: jose.JWTPayload): Promise<string> {
    await this._ready;
    return new jose.SignJWT(payload)
      .setProtectedHeader({ alg: "ES256", kid: this.kid })
      .sign(this.privateKey);
  }

  async verifyJWT(token: string): Promise<jose.JWTPayload> {
    await this._ready;
    const { payload } = await jose.jwtVerify(token, this.publicKey);
    return payload;
  }

  async signJWSDetached(payload: Uint8Array): Promise<string> {
    await this._ready;
    const jws = await new jose.CompactSign(payload)
      .setProtectedHeader({ alg: "ES256", kid: this.kid })
      .sign(this.privateKey);
    // Detach: replace payload with empty
    const [header, , signature] = jws.split(".");
    return `${header}..${signature}`;
  }
}
```

**Step 3: Add JWKS endpoint and update server**

In `server.ts`, add:

```typescript
import { KeyManager } from "./crypto";
import { resolve } from "path";

// Persist keys alongside the server source — override with ANIP_KEY_PATH env var
const keyPath = process.env.ANIP_KEY_PATH ?? resolve(__dirname, "../anip-keys.json");
const keys = new KeyManager(keyPath);

app.get("/.well-known/jwks.json", async (c) => {
  const jwks = await keys.getJWKS();
  return c.json(jwks);
});
```

Update `POST /anip/tokens` to issue JWTs (same pattern as Python).
Update `GET /anip/manifest` to add `X-ANIP-Signature` header.
Update protected endpoints to accept `{ token: "jwt..." }` format.
Add trust mode via `ANIP_TRUST_MODE` env var.

**Step 4: Update types.ts**

Add `TokenRequest`, `ManifestMetadata`, `ServiceIdentity` Zod schemas.
Update protocol version to `"anip/0.2"`.

**Step 5: Add audit hash chain with persistence**

The TypeScript server currently keeps audit logs only in memory. For Phase 3's "append-only integrity" claim to hold, signed audit entries must survive a restart. Two options:

- **Option A (recommended for reference parity):** Add a `better-sqlite3` dependency and persist audit entries to SQLite, mirroring the Python server's approach. The audit table schema matches the Python version with `sequence_number`, `previous_hash`, and `signature` columns.
- **Option B (minimal):** Keep in-memory storage but document explicitly that the TS server's audit chain does NOT survive restarts and is therefore unsuitable for production audit integrity. Add a prominent comment and a startup log warning.

Choose Option A for the reference implementation. Add `better-sqlite3` to dependencies:

```bash
cd examples/anip-ts && npm install better-sqlite3 && npm install -D @types/better-sqlite3
```

Create a minimal `src/data/database.ts` with the audit table schema matching the Python version. Update the audit log functions to write to and read from SQLite instead of the in-memory array.

**Step 6: Build and verify**

Run: `cd examples/anip-ts && npm run build`
Expected: No type errors.

Run: `cd examples/anip-ts && npm run dev` (in background)
Then: `curl http://localhost:8000/.well-known/jwks.json`
Expected: Valid JWKS response with 2 keys.

**Step 7: Commit**

```bash
git add examples/anip-ts/
git commit -m "feat(ts): TypeScript server v0.2 — JWT tokens, signed manifests, audit chain"
```

---

### Task 12: Client Library and Demo Updates

**Context:** The `anip_client.py` library and the demo scripts (`agent_demo.py`, `agent_loop.py`) need to work with v0.2's JWT-based tokens. The client's `make_token()` function is replaced by calling `POST /anip/tokens` and receiving a JWT. The agent loop's tool dispatch needs to pass JWT strings instead of token dicts.

**Files:**
- Modify: `examples/agent/anip_client.py` (update for JWT flow)
- Modify: `examples/agent/agent_demo.py` (update for JWT flow)
- Modify: `examples/agent/agent_loop.py` (update for JWT flow)

**Step 1: Update ANIPClient**

The client now stores JWT strings instead of token dicts. Update methods:

```python
class ANIPClient:
    def request_token(
        self, subject: str, scope: list[str], capability: str,
        parent_token: str | None = None, ttl_hours: int = 2,
    ) -> dict[str, Any]:
        """Request a delegation token from the service (v0.2)."""
        body: dict[str, Any] = {
            "subject": subject,
            "scope": scope,
            "capability": capability,
            "ttl_hours": ttl_hours,
        }
        if parent_token is not None:
            body["parent_token"] = parent_token
        return self._post("/anip/tokens", body)

    def check_permissions(self, token_jwt: str) -> dict[str, Any]:
        """Query permissions using a JWT token."""
        return self._post("/anip/permissions", {"token": token_jwt})

    def invoke(self, capability: str, token_jwt: str, parameters: dict[str, Any]) -> dict[str, Any]:
        """Invoke a capability using a JWT token."""
        return self._post(f"/anip/invoke/{capability}", {"token": token_jwt, "parameters": parameters})

    def query_audit(self, token_jwt: str, capability: str | None = None) -> dict[str, Any]:
        """Query audit log using a JWT token."""
        params = f"?capability={capability}" if capability else ""
        return self._post(f"/anip/audit{params}", {"token": token_jwt})
```

Keep `make_token()` for `--trust-on-declaration` mode only, with a deprecation comment.

**Step 2: Update agent_demo.py**

Replace `make_token()` calls with `client.request_token()`. Store JWT strings in state instead of token dicts. Update all invocation calls to pass JWT strings.

**Step 3: Update agent_loop.py**

The token inventory (`token_inventory`) currently stores dicts. Update to store JWT strings. Update `dispatch_tool()` to pass JWT strings to `client.invoke()`, `client.check_permissions()`, `client.query_audit()`.

Update `_handle_budget_request()` to call `client.request_token()` instead of `client.register_token(make_token(...))`.

**Step 4: Test end-to-end**

Start the server:
Run: `cd examples/anip && rm -f anip_server/data/anip.db && uvicorn anip_server.main:app`

In a separate terminal, test simulated mode:
Run: `cd examples/agent && python agent_demo.py`
Expected: All 8 steps complete successfully.

Test agent mode:
Run: `cd examples/agent && ANTHROPIC_API_KEY=sk-... python agent_demo.py --agent`
Expected: Agent completes the flight booking flow.

**Step 5: Commit**

```bash
git add examples/agent/
git commit -m "feat: update client and demos for v0.2 JWT token flow"
```

---

## Post-Implementation Checklist

After all tasks are complete:

1. **Delete old database**: `rm -f examples/anip/anip_server/data/anip.db` — schema has changed
2. **Run full test suite**: `cd examples/anip && python -m pytest tests/ -v`
3. **Run conformance tests**: `cd examples/anip && python -m pytest tests/test_conformance.py -v`
4. **Test end-to-end**: Start server, run `agent_demo.py` in all three modes
5. **Build TypeScript**: `cd examples/anip-ts && npm run build`
6. **Update SPEC.md**: Change protocol version references from v0.1 to v0.2, add JWT/JWKS sections
7. **Update README.md**: Update status section to reflect v0.2
