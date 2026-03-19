import asyncio

from anip_service import Capability, InvocationContext, ANIPError
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SideEffect, SideEffectType


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
