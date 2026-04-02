"""Conformance tests for ANIP advisory composition hints (v0.17).

Spec references: refresh_via, verify_via fields on CapabilityDeclaration.

All tests skip gracefully if no capabilities declare these fields.
"""
import pytest


class TestCompositionHints:
    def test_composition_hints_roundtrip_through_manifest(self, client):
        """Capabilities that declare refresh_via or verify_via MUST expose those
        fields in the HTTP response from GET /anip/manifest."""
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200, f"Manifest fetch failed: {resp.status_code}"
        capabilities = resp.json().get("capabilities", {})

        hinted = {
            name: meta
            for name, meta in capabilities.items()
            if meta.get("refresh_via") or meta.get("verify_via")
        }
        if not hinted:
            pytest.skip("No capabilities declare refresh_via or verify_via")

        for name, meta in hinted.items():
            refresh = meta.get("refresh_via")
            verify = meta.get("verify_via")
            assert refresh is not None or verify is not None, (
                f"Capability '{name}' matched the filter but neither field is present "
                f"in the manifest response"
            )

    def test_refresh_via_references_exist_in_manifest(self, client):
        """Every capability name listed in refresh_via MUST exist as a declared
        capability in the same manifest."""
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200, f"Manifest fetch failed: {resp.status_code}"
        capabilities = resp.json().get("capabilities", {})

        found_any = False
        for name, meta in capabilities.items():
            refresh_via = meta.get("refresh_via") or []
            if not refresh_via:
                continue
            found_any = True
            for referenced in refresh_via:
                assert referenced in capabilities, (
                    f"Capability '{name}' declares refresh_via=[..., '{referenced}', ...] "
                    f"but '{referenced}' is not declared in the same manifest"
                )

        if not found_any:
            pytest.skip("No capabilities declare refresh_via")

    def test_verify_via_references_exist_in_manifest(self, client):
        """Every capability name listed in verify_via MUST exist as a declared
        capability in the same manifest."""
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200, f"Manifest fetch failed: {resp.status_code}"
        capabilities = resp.json().get("capabilities", {})

        found_any = False
        for name, meta in capabilities.items():
            verify_via = meta.get("verify_via") or []
            if not verify_via:
                continue
            found_any = True
            for referenced in verify_via:
                assert referenced in capabilities, (
                    f"Capability '{name}' declares verify_via=[..., '{referenced}', ...] "
                    f"but '{referenced}' is not declared in the same manifest"
                )

        if not found_any:
            pytest.skip("No capabilities declare verify_via")

    def test_refresh_via_is_string_array(self, client):
        """refresh_via, when present, MUST be an array of strings (capability names)."""
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200, f"Manifest fetch failed: {resp.status_code}"
        capabilities = resp.json().get("capabilities", {})

        found_any = False
        for name, meta in capabilities.items():
            refresh_via = meta.get("refresh_via")
            if refresh_via is None:
                continue
            found_any = True
            assert isinstance(refresh_via, list), (
                f"Capability '{name}': refresh_via must be an array, "
                f"got {type(refresh_via).__name__}"
            )
            for i, item in enumerate(refresh_via):
                assert isinstance(item, str), (
                    f"Capability '{name}': refresh_via[{i}] must be a string, "
                    f"got {type(item).__name__} ({item!r})"
                )

        if not found_any:
            pytest.skip("No capabilities declare refresh_via")

    def test_verify_via_is_string_array(self, client):
        """verify_via, when present, MUST be an array of strings (capability names)."""
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200, f"Manifest fetch failed: {resp.status_code}"
        capabilities = resp.json().get("capabilities", {})

        found_any = False
        for name, meta in capabilities.items():
            verify_via = meta.get("verify_via")
            if verify_via is None:
                continue
            found_any = True
            assert isinstance(verify_via, list), (
                f"Capability '{name}': verify_via must be an array, "
                f"got {type(verify_via).__name__}"
            )
            for i, item in enumerate(verify_via):
                assert isinstance(item, str), (
                    f"Capability '{name}': verify_via[{i}] must be a string, "
                    f"got {type(item).__name__} ({item!r})"
                )

        if not found_any:
            pytest.skip("No capabilities declare verify_via")
