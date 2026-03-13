"""Tests for manifest signing with detached JWS."""

import base64

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import (
    EllipticCurvePublicNumbers,
    SECP256R1,
)
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from tests.conftest import client  # noqa: F401


def _pad_b64(s):
    return s + "=" * (4 - len(s) % 4) if len(s) % 4 else s


def test_manifest_has_signature_header(client):
    resp = client.get("/anip/manifest")
    assert resp.status_code == 200
    assert "X-ANIP-Signature" in resp.headers
    sig = resp.headers["X-ANIP-Signature"]
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
    # Get the public key from JWKS
    jwks_resp = client.get("/.well-known/jwks.json")
    jwk = jwks_resp.json()["keys"][0]

    # Reconstruct the EC public key from JWK coordinates
    x = int.from_bytes(base64.urlsafe_b64decode(_pad_b64(jwk["x"])), "big")
    y = int.from_bytes(base64.urlsafe_b64decode(_pad_b64(jwk["y"])), "big")
    pub_key = EllipticCurvePublicNumbers(x, y, SECP256R1()).public_key()

    # Get manifest + detached signature
    manifest_resp = client.get("/anip/manifest")
    sig_header = manifest_resp.headers["X-ANIP-Signature"]
    manifest_bytes = manifest_resp.content  # raw bytes from the response

    # Parse detached JWS: header..signature
    parts = sig_header.split(".")
    assert len(parts) == 3
    assert parts[1] == ""
    header_b64, _, sig_b64 = parts

    # Reconstruct signing input: header_b64 + "." + base64url(manifest_bytes)
    payload_b64 = base64.urlsafe_b64encode(manifest_bytes).rstrip(b"=").decode()
    signing_input = f"{header_b64}.{payload_b64}".encode()

    # Decode signature (ES256 = r || s, 32 bytes each)
    sig_bytes = base64.urlsafe_b64decode(_pad_b64(sig_b64))
    r = int.from_bytes(sig_bytes[:32], "big")
    s = int.from_bytes(sig_bytes[32:], "big")
    der_sig = encode_dss_signature(r, s)

    # Verify — raises if invalid
    pub_key.verify(der_sig, signing_input, ec.ECDSA(hashes.SHA256()))


def test_manifest_protocol_is_v03(client):
    resp = client.get("/anip/manifest")
    body = resp.json()
    assert body["protocol"] == "anip/0.3"
