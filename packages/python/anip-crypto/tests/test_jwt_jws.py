"""Tests for JWT, JWS, JWKS, and verification."""
import json

import pytest

from anip_crypto import (
    KeyManager,
    build_jwks,
    canonicalize,
    sign_jws_detached,
    sign_jws_detached_audit,
    sign_jwt,
    verify_audit_entry_signature,
    verify_jws_detached,
    verify_jws_detached_audit,
    verify_jwt,
    verify_manifest_signature,
)


def test_jwt_sign_verify():
    km = KeyManager()
    token = sign_jwt(km, {"sub": "agent", "aud": "test-svc"})
    claims = verify_jwt(km, token, audience="test-svc")
    assert claims["sub"] == "agent"


def test_jwt_wrong_audience_fails():
    km = KeyManager()
    token = sign_jwt(km, {"sub": "agent", "aud": "svc-a"})
    with pytest.raises(Exception):
        verify_jwt(km, token, audience="svc-b")


def test_jws_detached_delegation():
    km = KeyManager()
    payload = b"manifest-bytes"
    jws = sign_jws_detached(km, payload)
    parts = jws.split(".")
    assert len(parts) == 3
    assert parts[1] == ""
    verify_jws_detached(km, jws, payload)


def test_jws_detached_audit():
    km = KeyManager()
    payload = b"checkpoint-body"
    jws = sign_jws_detached_audit(km, payload)
    verify_jws_detached_audit(km, jws, payload)


def test_jws_delegation_key_cannot_verify_audit_signature():
    km = KeyManager()
    payload = b"data"
    jws = sign_jws_detached_audit(km, payload)
    with pytest.raises(Exception):
        verify_jws_detached(km, jws, payload)


def test_build_jwks():
    km = KeyManager()
    jwks = build_jwks(km)
    assert len(jwks["keys"]) == 2
    assert jwks["keys"][0]["alg"] == "ES256"


def test_canonicalize():
    data = {"b": 2, "a": 1, "signature": "remove-me"}
    canonical = canonicalize(data, exclude={"signature"})
    parsed = json.loads(canonical)
    assert list(parsed.keys()) == ["a", "b"]


def test_verify_audit_entry_signature():
    km = KeyManager()
    entry = {"capability": "test", "timestamp": "2026-01-01T00:00:00Z", "success": True}
    sig = km.sign_audit_entry(entry)
    verify_audit_entry_signature(km, entry, sig)


def test_verify_manifest_signature():
    km = KeyManager()
    manifest_bytes = b'{"protocol":"anip/0.11","capabilities":{}}'
    sig = sign_jws_detached(km, manifest_bytes)
    verify_manifest_signature(km, manifest_bytes, sig)


def test_verify_manifest_signature_wrong_bytes_fails():
    km = KeyManager()
    manifest_bytes = b'{"protocol":"anip/0.11"}'
    sig = sign_jws_detached(km, manifest_bytes)
    with pytest.raises(Exception):
        verify_manifest_signature(km, b"tampered", sig)
