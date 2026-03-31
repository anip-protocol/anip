"""Tests for manifest builder."""
from anip_core import CapabilityDeclaration, CapabilityOutput, SideEffect, SideEffectType, TrustPosture, ServiceIdentity, PROTOCOL_VERSION
from anip_server.manifest import build_manifest


def test_build_manifest():
    caps = {
        "test_cap": CapabilityDeclaration(
            name="test_cap", description="Test", contract_version="1.0",
            inputs=[], output=CapabilityOutput(type="object", fields=[]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window=None),
            minimum_scope=["test.read"],
        ),
    }
    trust = TrustPosture(level="signed")
    identity = ServiceIdentity(id="test-svc", jwks_uri="/.well-known/jwks.json", issuer_mode="first-party")
    manifest = build_manifest(capabilities=caps, trust=trust, service_identity=identity)
    assert manifest.protocol == PROTOCOL_VERSION
    assert manifest.manifest_metadata is not None
    assert manifest.manifest_metadata.sha256 is not None
    assert "test_cap" in manifest.capabilities
