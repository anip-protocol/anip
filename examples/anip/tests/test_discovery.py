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
