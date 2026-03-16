"""Tests for anip-core protocol models."""
import pytest
from pydantic import ValidationError

from anip_core import (
    ANIPManifest, CapabilityDeclaration, DelegationToken,
    TrustPosture, AnchoringPolicy, SideEffectType,
    ConcurrentBranches, PermissionResponse,
    ANIPFailure, PROTOCOL_VERSION,
    InvokeRequest, InvokeResponse,
    ResponseMode, StreamSummary,
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


def test_response_mode_enum():
    assert ResponseMode.UNARY == "unary"
    assert ResponseMode.STREAMING == "streaming"


def test_capability_declaration_response_modes_default():
    decl = CapabilityDeclaration(
        name="test", description="Test", contract_version="1.0",
        inputs=[], output={"type": "object", "fields": []},
        side_effect={"type": "read"}, minimum_scope=["test"],
    )
    assert decl.response_modes == [ResponseMode.UNARY]


def test_capability_declaration_response_modes_streaming():
    decl = CapabilityDeclaration(
        name="test", description="Test", contract_version="1.0",
        inputs=[], output={"type": "object", "fields": []},
        side_effect={"type": "read"}, minimum_scope=["test"],
        response_modes=["streaming"],
    )
    assert decl.response_modes == [ResponseMode.STREAMING]


def test_capability_declaration_response_modes_both():
    decl = CapabilityDeclaration(
        name="test", description="Test", contract_version="1.0",
        inputs=[], output={"type": "object", "fields": []},
        side_effect={"type": "read"}, minimum_scope=["test"],
        response_modes=["unary", "streaming"],
    )
    assert len(decl.response_modes) == 2


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


# --- InvokeRequest (collapsed from InvokeRequestV2) ---


def test_invoke_request_has_token_field():
    """InvokeRequest uses JWT `token` field, not `delegation_token`."""
    req = InvokeRequest(token="eyJhbGciOi...", parameters={"origin": "JFK"})
    assert req.token == "eyJhbGciOi..."
    assert req.parameters == {"origin": "JFK"}
    assert req.budget is None
    assert req.client_reference_id is None


def test_invoke_request_no_delegation_token_field():
    """InvokeRequest no longer accepts delegation_token."""
    assert "delegation_token" not in InvokeRequest.model_fields
    with pytest.raises(ValidationError):
        InvokeRequest(delegation_token={"token_id": "t"}, parameters={})


def test_invoke_request_client_reference_id_valid():
    """client_reference_id up to 256 chars is accepted."""
    ref_id = "a" * 256
    req = InvokeRequest(token="jwt.token.here", client_reference_id=ref_id)
    assert req.client_reference_id == ref_id


def test_invoke_request_client_reference_id_too_long():
    """client_reference_id over 256 chars is rejected."""
    ref_id = "a" * 257
    with pytest.raises(ValidationError) as exc_info:
        InvokeRequest(token="jwt.token.here", client_reference_id=ref_id)
    assert "client_reference_id" in str(exc_info.value)


def test_invoke_request_client_reference_id_none_by_default():
    """client_reference_id defaults to None."""
    req = InvokeRequest(token="jwt.token.here")
    assert req.client_reference_id is None


# --- InvokeResponse lineage fields ---


def test_invoke_response_invocation_id_required():
    """invocation_id is required on InvokeResponse."""
    with pytest.raises(ValidationError) as exc_info:
        InvokeResponse(success=True)
    assert "invocation_id" in str(exc_info.value)


def test_invoke_response_invocation_id_valid_pattern():
    """invocation_id must match ^inv-[0-9a-f]{12}$."""
    resp = InvokeResponse(success=True, invocation_id="inv-0123456789ab")
    assert resp.invocation_id == "inv-0123456789ab"


def test_invoke_response_invocation_id_invalid_pattern():
    """invocation_id rejects values not matching the pattern."""
    with pytest.raises(ValidationError) as exc_info:
        InvokeResponse(success=True, invocation_id="bad-id")
    assert "invocation_id" in str(exc_info.value)


def test_invoke_response_invocation_id_rejects_uppercase():
    """invocation_id hex must be lowercase."""
    with pytest.raises(ValidationError):
        InvokeResponse(success=True, invocation_id="inv-0123456789AB")


def test_invoke_response_invocation_id_wrong_length():
    """invocation_id rejects wrong hex length."""
    with pytest.raises(ValidationError):
        InvokeResponse(success=True, invocation_id="inv-0123456789abc")


def test_invoke_response_client_reference_id_echoed():
    """client_reference_id can be set on response."""
    resp = InvokeResponse(
        success=True,
        invocation_id="inv-aabbccddeeff",
        client_reference_id="my-req-123",
    )
    assert resp.client_reference_id == "my-req-123"


def test_invoke_response_client_reference_id_default_none():
    """client_reference_id defaults to None on response."""
    resp = InvokeResponse(success=True, invocation_id="inv-aabbccddeeff")
    assert resp.client_reference_id is None


def test_invoke_response_roundtrip():
    """Full roundtrip serialization of InvokeResponse with lineage fields."""
    resp = InvokeResponse(
        success=True,
        invocation_id="inv-000000000000",
        client_reference_id="ref-42",
        result={"data": "value"},
    )
    d = resp.model_dump()
    assert d["invocation_id"] == "inv-000000000000"
    assert d["client_reference_id"] == "ref-42"
    restored = InvokeResponse.model_validate(d)
    assert restored.invocation_id == resp.invocation_id
    assert restored.client_reference_id == resp.client_reference_id


# --- Streaming ---


def test_stream_summary():
    ss = StreamSummary(
        response_mode="streaming",
        events_emitted=5,
        events_delivered=3,
        duration_ms=1200,
        client_disconnected=True,
    )
    assert ss.events_emitted == 5
    assert ss.client_disconnected is True


def test_invoke_request_stream_default_false():
    req = InvokeRequest(
        token="jwt-string",
        parameters={"x": 1},
    )
    assert req.stream is False


def test_invoke_request_stream_true():
    req = InvokeRequest(
        token="jwt-string",
        parameters={"x": 1},
        stream=True,
    )
    assert req.stream is True
