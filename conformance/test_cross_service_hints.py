"""Conformance tests for ANIP cross-service handoff hints (v0.19).

Spec references: v0.19 additions for cross_service field on CapabilityDeclaration.

cross_service is an optional object field on a capability declaration that carries
advisory hints for cross-service coordination:
  - handoff_to   — capabilities on other services this capability naturally leads into
  - refresh_via  — capabilities on other services that can refresh stale artifacts
  - verify_via   — capabilities on other services that can verify side effects
  - followup_via — capabilities on other services useful after this one completes

Each entry in those arrays is a ServiceCapabilityRef: { service, capability } — both
non-empty strings. The showcase MUST declare at least one capability with cross_service.
"""


class TestCrossServiceRoundtrip:
    def test_cross_service_roundtrip_through_manifest(self, client):
        """Capabilities that declare cross_service MUST expose that field in the manifest.

        The showcase is required to have at least one capability with cross_service, so
        this test MUST NOT skip — if no capability declares it, the showcase is broken.
        """
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200, f"Manifest fetch failed: {resp.status_code}"
        capabilities = resp.json().get("capabilities", {})

        assert capabilities, "Manifest has no capabilities"

        cross_service_caps = {
            name: meta
            for name, meta in capabilities.items()
            if meta.get("cross_service") is not None
        }

        assert cross_service_caps, (
            "No capability declares cross_service — the showcase MUST include at least "
            "one capability with cross_service hints (v0.19 requirement). "
            f"Declared capabilities: {list(capabilities.keys())}"
        )

        for name, meta in cross_service_caps.items():
            cs = meta["cross_service"]
            assert isinstance(cs, dict), (
                f"Capability '{name}': cross_service must be an object, "
                f"got {type(cs).__name__}"
            )


class TestServiceCapabilityRefShape:
    def test_service_capability_ref_shape(self, client):
        """Every ServiceCapabilityRef in cross_service arrays must have non-empty
        'service' and 'capability' strings."""
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200, f"Manifest fetch failed: {resp.status_code}"
        capabilities = resp.json().get("capabilities", {})

        found_any = False
        for cap_name, meta in capabilities.items():
            cs = meta.get("cross_service")
            if cs is None:
                continue

            for array_key in ("handoff_to", "refresh_via", "verify_via", "followup_via"):
                refs = cs.get(array_key) or []
                if not refs:
                    continue
                found_any = True
                assert isinstance(refs, list), (
                    f"Capability '{cap_name}': cross_service.{array_key} must be an array, "
                    f"got {type(refs).__name__}"
                )
                for i, ref in enumerate(refs):
                    assert isinstance(ref, dict), (
                        f"Capability '{cap_name}': cross_service.{array_key}[{i}] must be "
                        f"an object, got {type(ref).__name__}"
                    )
                    svc = ref.get("service")
                    cap = ref.get("capability")
                    assert isinstance(svc, str) and svc, (
                        f"Capability '{cap_name}': cross_service.{array_key}[{i}].service "
                        f"must be a non-empty string, got {svc!r}"
                    )
                    assert isinstance(cap, str) and cap, (
                        f"Capability '{cap_name}': cross_service.{array_key}[{i}].capability "
                        f"must be a non-empty string, got {cap!r}"
                    )

        if not found_any:
            # cross_service present but all arrays empty — still valid, just nothing to check
            pass


class TestCrossServiceOptional:
    def test_cross_service_optional(self, client):
        """Capabilities without cross_service are valid — the field is purely optional."""
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200, f"Manifest fetch failed: {resp.status_code}"
        capabilities = resp.json().get("capabilities", {})

        for cap_name, meta in capabilities.items():
            cs = meta.get("cross_service")
            # None (absent) is always valid
            if cs is None:
                continue
            # If present, must be a dict
            assert isinstance(cs, dict), (
                f"Capability '{cap_name}': cross_service, when present, must be an object, "
                f"got {type(cs).__name__}"
            )
