"""Tests for anip-core protocol models."""
import pytest
from anip_core import (
    ANIPManifest, CapabilityDeclaration, DelegationToken,
    TrustPosture, AnchoringPolicy, SideEffectType,
    ConcurrentBranches, PermissionResponse, InvokeResponse,
    ANIPFailure, PROTOCOL_VERSION,
)


def test_protocol_version():
    assert PROTOCOL_VERSION == "anip/0.3"


def test_delegation_token_roundtrip():
    token = DelegationToken(
        token_id="tok-1", issuer="svc", subject="agent",
        scope=["travel.search"],
        purpose={"capability": "search_flights", "parameters": {}, "task_id": "t1"},
        parent=None, expires="2026-12-31T23:59:59Z",
        constraints={"max_delegation_depth": 3, "concurrent_branches": "allowed"},
    )
    d = token.model_dump()
    assert d["token_id"] == "tok-1"
    assert d["scope"] == ["travel.search"]
    restored = DelegationToken.model_validate(d)
    assert restored.token_id == token.token_id


def test_trust_posture_defaults():
    tp = TrustPosture()
    assert tp.level == "signed"
    assert tp.anchoring is None


def test_trust_posture_anchored():
    tp = TrustPosture(
        level="anchored",
        anchoring=AnchoringPolicy(cadence="PT60S", max_lag=100, sink=["witness:example.com"]),
    )
    assert tp.anchoring.max_lag == 100
    assert tp.anchoring.sink == ["witness:example.com"]


def test_capability_declaration():
    decl = CapabilityDeclaration(
        name="test", description="A test capability", contract_version="1.0",
        inputs=[], output={"type": "object", "fields": []},
        side_effect={"type": "read", "rollback_window": None},
        minimum_scope=["test.read"],
    )
    assert decl.name == "test"
    assert decl.side_effect.type == SideEffectType.READ


def test_anip_failure():
    failure = ANIPFailure(
        type="scope_insufficient", detail="Missing required scope",
        resolution={"action": "request_broader_scope"}, retry=False,
    )
    assert failure.type == "scope_insufficient"
    assert failure.retry is False


def test_manifest_structure():
    manifest = ANIPManifest(protocol="anip/0.3", profile={"core": "1.0"}, capabilities={})
    assert manifest.protocol == "anip/0.3"


def test_permission_response():
    resp = PermissionResponse(available=[], restricted=[], denied=[])
    assert len(resp.available) == 0


def test_side_effect_type_enum():
    assert SideEffectType.READ == "read"
    assert SideEffectType.IRREVERSIBLE == "irreversible"


def test_concurrent_branches_enum():
    assert ConcurrentBranches.EXCLUSIVE == "exclusive"
    assert ConcurrentBranches.ALLOWED == "allowed"
