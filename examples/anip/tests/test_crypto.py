import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from anip_server.primitives.crypto import KeyManager


def test_generates_ec_p256_key():
    km = KeyManager()
    assert isinstance(km.private_key, ec.EllipticCurvePrivateKey)
    assert isinstance(km.public_key, ec.EllipticCurvePublicKey)


def test_jwks_contains_two_keys():
    km = KeyManager()
    jwks = km.get_jwks()
    assert "keys" in jwks
    assert len(jwks["keys"]) == 2


def test_jwks_key_has_required_fields():
    km = KeyManager()
    jwks = km.get_jwks()
    key = jwks["keys"][0]
    assert key["kty"] == "EC"
    assert key["crv"] == "P-256"
    assert key["alg"] == "ES256"
    assert key["use"] == "sig"
    assert "kid" in key
    assert "x" in key
    assert "y" in key
    assert "d" not in key


def test_sign_and_verify_roundtrip():
    km = KeyManager()
    payload = {"sub": "agent-1", "aud": "anip-flight-service"}
    token = km.sign_jwt(payload)
    decoded = km.verify_jwt(token)
    assert decoded["sub"] == "agent-1"


def test_verify_rejects_tampered_token():
    km = KeyManager()
    payload = {"sub": "agent-1", "aud": "anip-flight-service"}
    token = km.sign_jwt(payload)
    # Tamper with the signature
    parts = token.split(".")
    sig = parts[2]
    tampered_sig = sig[:-4] + ("AAAA" if not sig.endswith("AAAA") else "BBBB")
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"
    with pytest.raises(jwt.exceptions.InvalidSignatureError):
        km.verify_jwt(tampered_token)


def test_kid_is_stable_for_same_instance():
    km = KeyManager()
    jwks1 = km.get_jwks()
    jwks2 = km.get_jwks()
    assert jwks1["keys"][0]["kid"] == jwks2["keys"][0]["kid"]


def test_different_instances_have_different_keys():
    km1 = KeyManager()
    km2 = KeyManager()
    assert km1.get_jwks()["keys"][0]["kid"] != km2.get_jwks()["keys"][0]["kid"]


def test_persists_and_loads_keys(tmp_path):
    key_file = str(tmp_path / "server_key.json")
    km1 = KeyManager(key_path=key_file)
    token = km1.sign_jwt({"sub": "test", "aud": "anip-flight-service"})
    kid1 = km1.get_jwks()["keys"][0]["kid"]

    km2 = KeyManager(key_path=key_file)
    kid2 = km2.get_jwks()["keys"][0]["kid"]
    assert kid1 == kid2

    # Token from km1 should verify with km2
    decoded = km2.verify_jwt(token)
    assert decoded["sub"] == "test"


def test_sign_jws_detached():
    km = KeyManager()
    payload = b'{"hello": "world"}'
    jws = km.sign_jws_detached(payload)
    parts = jws.split(".")
    assert len(parts) == 3
    assert parts[1] == ""  # empty payload section


def test_verify_jws_detached():
    km = KeyManager()
    payload = b'{"hello": "world"}'
    jws = km.sign_jws_detached(payload)
    # Should not raise
    km.verify_jws_detached(jws, payload)


def test_verify_jws_detached_rejects_modified_payload():
    km = KeyManager()
    payload = b'{"hello": "world"}'
    jws = km.sign_jws_detached(payload)
    modified_payload = b'{"hello": "TAMPERED"}'
    with pytest.raises(Exception):
        km.verify_jws_detached(jws, modified_payload)
