"""Tests for anip-core protocol models."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from anip_core import (
    ANIPManifest, CapabilityDeclaration, DelegationToken,
    TrustPosture, AnchoringPolicy, SideEffectType,
    ConcurrentBranches, PermissionResponse,
    ANIPFailure, PROTOCOL_VERSION,
    InvokeRequest, InvokeResponse,
    ResponseMode, StreamSummary,
    AuditPosture, ClientReferenceIdPosture,
    LineagePosture, MetadataPolicy,
    FailureDisclosure, AnchoringPosture,
    DiscoveryPosture,
    EventClass, RetentionTier, DisclosureLevel,
    Purpose, DelegationConstraints, CapabilityOutput,
    SideEffect, Resolution, ProfileVersions,
)


def test_protocol_version():
    # Intentionally hardcoded — this is the one place that verifies the constant value.
    # Update this when bumping the protocol version.
    assert PROTOCOL_VERSION == "anip/0.15"


def test_delegation_token_roundtrip():
    token = DelegationToken(
        token_id="tok-1", issuer="svc", subject="agent",
        scope=["travel.search"],
        purpose=Purpose(capability="search_flights", parameters={}, task_id="t1"),
        parent=None,
        expires=datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        constraints=DelegationConstraints(
            max_delegation_depth=3, concurrent_branches=ConcurrentBranches.ALLOWED,
        ),
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
    assert tp.anchoring is not None
    assert tp.anchoring.max_lag == 100
    assert tp.anchoring.sink == ["witness:example.com"]


def test_response_mode_enum():
    assert ResponseMode.UNARY == "unary"
    assert ResponseMode.STREAMING == "streaming"


def test_capability_declaration_response_modes_default():
    decl = CapabilityDeclaration(
        name="test", description="Test", contract_version="1.0",
        inputs=[], output=CapabilityOutput(type="object", fields=[]),
        side_effect=SideEffect(type=SideEffectType.READ), minimum_scope=["test"],
    )
    assert decl.response_modes == [ResponseMode.UNARY]


def test_capability_declaration_response_modes_streaming():
    decl = CapabilityDeclaration(
        name="test", description="Test", contract_version="1.0",
        inputs=[], output=CapabilityOutput(type="object", fields=[]),
        side_effect=SideEffect(type=SideEffectType.READ), minimum_scope=["test"],
        response_modes=[ResponseMode.STREAMING],
    )
    assert decl.response_modes == [ResponseMode.STREAMING]


def test_capability_declaration_response_modes_both():
    decl = CapabilityDeclaration(
        name="test", description="Test", contract_version="1.0",
        inputs=[], output=CapabilityOutput(type="object", fields=[]),
        side_effect=SideEffect(type=SideEffectType.READ), minimum_scope=["test"],
        response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
    )
    assert len(decl.response_modes) == 2


def test_capability_declaration():
    decl = CapabilityDeclaration(
        name="test", description="A test capability", contract_version="1.0",
        inputs=[], output=CapabilityOutput(type="object", fields=[]),
        side_effect=SideEffect(type=SideEffectType.READ, rollback_window=None),
        minimum_scope=["test.read"],
    )
    assert decl.name == "test"
    assert decl.side_effect.type == SideEffectType.READ


def test_anip_failure():
    failure = ANIPFailure(
        type="scope_insufficient", detail="Missing required scope",
        resolution=Resolution(action="request_broader_scope"), retry=False,
    )
    assert failure.type == "scope_insufficient"
    assert failure.retry is False


def test_manifest_structure():
    manifest = ANIPManifest(protocol=PROTOCOL_VERSION, profile=ProfileVersions(core="1.0"), capabilities={})
    assert manifest.protocol == PROTOCOL_VERSION


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
        InvokeRequest(delegation_token={"token_id": "t"}, parameters={})  # pyright: ignore[reportCallIssue]


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
        InvokeResponse(success=True)  # pyright: ignore[reportCallIssue]
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


# --- Discovery Posture (v0.7) ---


def test_audit_posture_defaults():
    ap = AuditPosture()
    assert ap.enabled is True
    assert ap.signed is True
    assert ap.queryable is True
    assert ap.retention == "P90D"


def test_audit_posture_with_retention():
    ap = AuditPosture(retention="P365D")
    assert ap.retention == "P365D"


def test_client_reference_id_posture_defaults():
    crp = ClientReferenceIdPosture()
    assert crp.supported is True
    assert crp.max_length == 256
    assert crp.opaque is True
    assert crp.propagation == "bounded"


def test_lineage_posture_defaults():
    lp = LineagePosture()
    assert lp.invocation_id is True
    assert lp.client_reference_id is not None
    assert lp.client_reference_id.supported is True


def test_metadata_policy_defaults():
    mp = MetadataPolicy()
    assert mp.bounded_lineage is True
    assert mp.freeform_context is False
    assert mp.downstream_propagation == "minimal"


def test_failure_disclosure_defaults():
    fd = FailureDisclosure()
    assert fd.detail_level == "redacted"


def test_failure_disclosure_full():
    fd = FailureDisclosure(detail_level="full")
    assert fd.detail_level == "full"


def test_anchoring_posture_defaults():
    ap = AnchoringPosture()
    assert ap.enabled is False
    assert ap.cadence is None
    assert ap.max_lag is None
    assert ap.proofs_available is False


def test_anchoring_posture_enabled():
    ap = AnchoringPosture(enabled=True, cadence="PT30S", max_lag=120, proofs_available=True)
    assert ap.enabled is True
    assert ap.cadence == "PT30S"
    assert ap.max_lag == 120
    assert ap.proofs_available is True


def test_discovery_posture_defaults():
    dp = DiscoveryPosture()
    assert dp.audit.enabled is True
    assert dp.lineage.invocation_id is True
    assert dp.metadata_policy.bounded_lineage is True
    assert dp.failure_disclosure.detail_level == "redacted"
    assert dp.anchoring.enabled is False


def test_discovery_posture_roundtrip():
    dp = DiscoveryPosture(
        anchoring=AnchoringPosture(enabled=True, cadence="PT30S", max_lag=120, proofs_available=True),
    )
    d = dp.model_dump()
    assert d["audit"]["enabled"] is True
    assert d["anchoring"]["enabled"] is True
    assert d["anchoring"]["cadence"] == "PT30S"
    restored = DiscoveryPosture.model_validate(d)
    assert restored.anchoring.enabled is True
    assert restored.anchoring.cadence == "PT30S"


# --- v0.8 Security Hardening Enums ---


def test_event_class_enum_values():
    assert EventClass.HIGH_RISK_SUCCESS == "high_risk_success"
    assert EventClass.HIGH_RISK_DENIAL == "high_risk_denial"
    assert EventClass.LOW_RISK_SUCCESS == "low_risk_success"
    assert EventClass.REPEATED_LOW_VALUE_DENIAL == "repeated_low_value_denial"
    assert EventClass.MALFORMED_OR_SPAM == "malformed_or_spam"
    assert len(EventClass) == 5


def test_retention_tier_enum_values():
    assert RetentionTier.LONG == "long"
    assert RetentionTier.MEDIUM == "medium"
    assert RetentionTier.SHORT == "short"
    assert RetentionTier.AGGREGATE_ONLY == "aggregate_only"
    assert len(RetentionTier) == 4


def test_disclosure_level_enum_values():
    assert DisclosureLevel.FULL == "full"
    assert DisclosureLevel.REDUCED == "reduced"
    assert DisclosureLevel.REDACTED == "redacted"
    assert DisclosureLevel.POLICY == "policy"
    assert len(DisclosureLevel) == 4


def test_audit_posture_retention_enforced():
    ap = AuditPosture()
    assert ap.retention_enforced is False
    ap2 = AuditPosture(retention_enforced=True)
    assert ap2.retention_enforced is True


def test_failure_disclosure_accepts_reduced():
    fd = FailureDisclosure(detail_level="reduced")
    assert fd.detail_level == "reduced"


# --- CheckpointDetailResponse (v0.9) ---


def test_checkpoint_detail_response_expires_hint_optional():
    """expires_hint is optional on CheckpointDetailResponse."""
    from anip_core import CheckpointDetailResponse
    resp = CheckpointDetailResponse(
        checkpoint={
            "service_id": "svc-1",
            "checkpoint_id": "ckpt-1",
            "range": {"first_sequence": 1, "last_sequence": 10},
            "merkle_root": "sha256:abc",
            "timestamp": "2026-01-01T00:00:00Z",
            "entry_count": 10,
        },
    )
    assert resp.expires_hint is None


def test_checkpoint_detail_response_expires_hint_set():
    """expires_hint can be set to an ISO 8601 timestamp."""
    from anip_core import CheckpointDetailResponse
    resp = CheckpointDetailResponse(
        checkpoint={
            "service_id": "svc-1",
            "checkpoint_id": "ckpt-1",
            "range": {"first_sequence": 1, "last_sequence": 10},
            "merkle_root": "sha256:abc",
            "timestamp": "2026-01-01T00:00:00Z",
            "entry_count": 10,
        },
        expires_hint="2026-04-01T00:00:00Z",
    )
    assert resp.expires_hint == "2026-04-01T00:00:00Z"
