import asyncio

from anip_service import Capability, InvocationContext, ANIPError
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SideEffect, SideEffectType, CrossServiceContract, CrossServiceContractEntry, RecoveryTarget, ServiceCapabilityRef, Resolution


def _minimal_declaration(name: str = "test_cap") -> CapabilityDeclaration:
    return CapabilityDeclaration(
        name=name,
        description="A test capability",
        contract_version="1.0",
        inputs=[CapabilityInput(name="x", type="string", required=True, description="input")],
        output=CapabilityOutput(type="object", fields=["result"]),
        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
        minimum_scope=["test.read"],
    )


def test_capability_bundles_declaration_and_handler():
    handler = lambda ctx, params: {"ok": True}
    cap = Capability(declaration=_minimal_declaration(), handler=handler)
    assert cap.declaration.name == "test_cap"
    assert cap.handler is handler
    assert cap.exclusive_lock is False


def test_invocation_context_cost_tracking():
    ctx = InvocationContext(
        token=None,  # type: ignore — simplified for test
        root_principal="human:alice@example.com",
        subject="agent:bot-1",
        scopes=["test.read"],
        delegation_chain=["tok-1"],
    )
    assert ctx._cost_actual is None
    ctx.set_cost_actual({"financial": {"amount": 10.0, "currency": "USD"}})
    assert ctx._cost_actual is not None
    assert ctx._cost_actual["financial"]["amount"] == 10.0


def test_anip_error():
    err = ANIPError("not_found", "Flight does not exist")
    assert err.error_type == "not_found"
    assert err.detail == "Flight does not exist"
    assert "not_found" in str(err)


def test_emit_progress_noop_without_sink():
    """emit_progress is a no-op when no progress sink is attached."""
    ctx = InvocationContext(
        token=None,  # type: ignore
        root_principal="human:alice@example.com",
        subject="agent:bot-1",
        scopes=["test.read"],
        delegation_chain=["tok-1"],
    )
    # Should not raise
    asyncio.run(ctx.emit_progress({"percent": 50}))


def test_emit_progress_calls_sink():
    """emit_progress forwards payload to attached sink."""
    received = []

    async def sink(payload):
        received.append(payload)

    ctx = InvocationContext(
        token=None,  # type: ignore
        root_principal="human:alice@example.com",
        subject="agent:bot-1",
        scopes=["test.read"],
        delegation_chain=["tok-1"],
        _progress_sink=sink,
    )
    asyncio.run(ctx.emit_progress({"percent": 50}))
    assert received == [{"percent": 50}]


# --- Capability with cross_service_contract (Phase 5) ---


def test_capability_with_cross_service_contract():
    """cross_service_contract field is preserved in Capability declaration."""
    ref = ServiceCapabilityRef(service="booking-service", capability="confirm_booking")
    entry = CrossServiceContractEntry(
        target=ref,
        required_for_task_completion=True,
        continuity="same_task",
        completion_mode="downstream_acceptance",
    )
    contract = CrossServiceContract(handoff=[entry])
    decl = _minimal_declaration()
    decl.cross_service_contract = contract
    cap = Capability(declaration=decl, handler=lambda ctx, params: {"ok": True})
    assert cap.declaration.cross_service_contract is not None
    assert len(cap.declaration.cross_service_contract.handoff) == 1
    assert cap.declaration.cross_service_contract.handoff[0].target.service == "booking-service"
    d = cap.declaration.model_dump()
    assert d["cross_service_contract"]["handoff"][0]["required_for_task_completion"] is True


def test_anip_error_with_recovery_target_in_resolution():
    """ANIPError carries recovery_target through its resolution dict."""
    rt = {
        "kind": "refresh",
        "target": {"service": "auth-svc", "capability": "refresh_token"},
        "continuity": "same_task",
        "retry_after_target": True,
    }
    resolution = {
        "action": "refresh_token",
        "recovery_class": "refresh_then_retry",
        "recovery_target": rt,
    }
    err = ANIPError("token_expired", "Token has expired", resolution=resolution, retry=False)
    assert err.resolution is not None
    assert err.resolution["recovery_target"]["kind"] == "refresh"
    assert err.resolution["recovery_target"]["target"]["service"] == "auth-svc"
