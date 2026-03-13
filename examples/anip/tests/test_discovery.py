"""Tests for the v0.3 discovery endpoint."""

from tests.conftest import client  # noqa: F401


def test_discovery_protocol_version(client):
    resp = client.get("/.well-known/anip")
    disco = resp.json()["anip_discovery"]
    assert disco["protocol"] == "anip/0.3"


def test_discovery_has_trust_level(client):
    """Discovery should include a trust_level field."""
    resp = client.get("/.well-known/anip")
    data = resp.json()["anip_discovery"]
    assert "trust_level" in data
    assert data["trust_level"] in ("signed", "anchored", "attested")


def test_manifest_has_trust_posture(client):
    """Manifest should include full trust posture declaration."""
    resp = client.get("/anip/manifest")
    manifest = resp.json()
    assert "trust" in manifest
    assert manifest["trust"]["level"] in ("signed", "anchored", "attested")


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
