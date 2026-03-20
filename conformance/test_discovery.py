"""Conformance tests for ANIP discovery, manifest, and JWKS.

Spec references: §6.1 (discovery), §6.2 (manifest signing), Conformance Category 1.
"""
import re


class TestDiscovery:
    def test_discovery_returns_200(self, client):
        resp = client.get("/.well-known/anip")
        assert resp.status_code == 200

    def test_discovery_required_fields(self, discovery):
        required = ["protocol", "compliance", "base_url", "profile", "auth",
                     "capabilities", "endpoints", "trust_level"]
        for field in required:
            assert field in discovery, f"Missing required field: {field}"

    def test_compliance_value(self, discovery):
        assert discovery["compliance"] in ("anip-compliant", "anip-complete")

    def test_endpoints_required_keys(self, discovery):
        required_endpoints = ["manifest", "invoke", "tokens", "permissions"]
        for ep in required_endpoints:
            assert ep in discovery["endpoints"], f"Missing endpoint: {ep}"

    def test_endpoint_urls_consistent_with_base_url(self, discovery):
        base = discovery["base_url"].rstrip("/")
        for name, url in discovery["endpoints"].items():
            if url.startswith("/"):
                continue  # relative URLs are fine
            assert url.startswith(base), (
                f"Endpoint '{name}' URL '{url}' not consistent with base_url '{base}'"
            )

    def test_capabilities_non_empty(self, discovery):
        assert len(discovery["capabilities"]) > 0

    def test_protocol_version_format(self, discovery):
        assert re.match(r"^anip/\d+\.\d+", discovery["protocol"])


class TestManifest:
    def test_manifest_returns_200(self, client):
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200

    def test_manifest_has_signature(self, client):
        resp = client.get("/anip/manifest")
        assert "x-anip-signature" in resp.headers, "Manifest missing X-ANIP-Signature header"

    def test_manifest_contains_capabilities(self, client, discovery):
        resp = client.get("/anip/manifest")
        data = resp.json()
        # Manifest should declare the same capabilities as discovery
        assert "capabilities" in data


class TestJWKS:
    def test_jwks_returns_200(self, client):
        resp = client.get("/.well-known/jwks.json")
        assert resp.status_code == 200

    def test_jwks_has_keys(self, client):
        resp = client.get("/.well-known/jwks.json")
        data = resp.json()
        assert "keys" in data
        assert len(data["keys"]) > 0

    def test_jwks_keys_are_ec(self, client):
        resp = client.get("/.well-known/jwks.json")
        for key in resp.json()["keys"]:
            assert key.get("kty") == "EC", f"Expected EC key, got {key.get('kty')}"
            assert key.get("crv") == "P-256", f"Expected P-256 curve, got {key.get('crv')}"
