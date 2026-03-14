"""Tests for KeyManager and key operations."""

import tempfile
from pathlib import Path

from anip_crypto.keys import KeyManager


def test_generate_keys():
    km = KeyManager()
    jwks = km.get_jwks()
    assert len(jwks["keys"]) == 2
    assert jwks["keys"][0]["use"] == "sig"
    assert jwks["keys"][1]["use"] == "audit"


def test_separate_key_ids():
    km = KeyManager()
    jwks = km.get_jwks()
    delegation_kid = jwks["keys"][0]["kid"]
    audit_kid = jwks["keys"][1]["kid"]
    assert delegation_kid != audit_kid


def test_persist_and_load():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    # Remove the empty file so KeyManager generates fresh keys
    Path(path).unlink()
    km1 = KeyManager(key_path=path)
    jwks1 = km1.get_jwks()
    km2 = KeyManager(key_path=path)
    jwks2 = km2.get_jwks()
    assert jwks1["keys"][0]["kid"] == jwks2["keys"][0]["kid"]
    assert jwks1["keys"][1]["kid"] == jwks2["keys"][1]["kid"]
    Path(path).unlink()


def test_kid_property():
    km = KeyManager()
    assert isinstance(km.kid, str)
    assert len(km.kid) == 16


def test_audit_kid_property():
    km = KeyManager()
    assert isinstance(km.audit_kid, str)
    assert km.audit_kid != km.kid
