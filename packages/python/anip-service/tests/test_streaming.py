import asyncio
import pytest
from anip_service import ANIPService, Capability, InvocationContext
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    SideEffect, SideEffectType, ResponseMode,
)


def _streaming_cap():
    async def handler(ctx: InvocationContext, params):
        await ctx.emit_progress({"step": 1, "message": "Starting"})
        await asyncio.sleep(0.01)  # simulate work
        await ctx.emit_progress({"step": 2, "message": "Processing"})
        return {"result": "done"}

    return Capability(
        declaration=CapabilityDeclaration(
            name="analyze",
            description="Long-running analysis",
            inputs=[CapabilityInput(name="target", type="string", required=True, description="target")],
            output=CapabilityOutput(type="object", fields=["result"]),
            side_effect=SideEffect(type=SideEffectType.READ),
            minimum_scope=["analyze"],
            response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
        ),
        handler=handler,
    )


def _unary_only_cap():
    return Capability(
        declaration=CapabilityDeclaration(
            name="greet",
            description="Say hello",
            inputs=[CapabilityInput(name="name", type="string", required=True, description="name")],
            output=CapabilityOutput(type="object", fields=["message"]),
            side_effect=SideEffect(type=SideEffectType.READ),
            minimum_scope=["greet"],
        ),
        handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
    )


@pytest.fixture
def service():
    return ANIPService(
        service_id="test-service",
        capabilities=[_streaming_cap(), _unary_only_cap()],
        storage=":memory:",
    )


async def _issue_test_token(service, scope, capability):
    """Helper to issue a root token for testing via the engine directly."""
    result = await service._engine.issue_root_token(
        authenticated_principal="human:test@example.com",
        subject="human:test@example.com",
        scope=scope,
        capability=capability,
        purpose_parameters={"task_id": "test"},
        ttl_hours=1,
    )
    token, token_id = result
    return token


async def test_streaming_sink_called_during_handler(service):
    """Progress sink receives events in real time during handler execution."""
    received = []

    async def sink(payload):
        received.append(payload)

    token = await _issue_test_token(service, scope=["analyze"], capability="analyze")
    result = await service.invoke(
        "analyze", token, {"target": "x"},
        stream=True,
        _progress_sink=sink,
    )
    assert result["success"] is True
    assert result["result"] == {"result": "done"}
    # Verify sink was called with structured events (not raw payloads)
    assert len(received) == 2
    assert received[0]["payload"] == {"step": 1, "message": "Starting"}
    assert received[0]["invocation_id"].startswith("inv-")
    assert received[0]["client_reference_id"] is None
    assert received[1]["payload"] == {"step": 2, "message": "Processing"}
    # Verify stream_summary
    assert result["stream_summary"]["events_emitted"] == 2
    assert result["stream_summary"]["response_mode"] == "streaming"


async def test_unary_invocation_ignores_progress(service):
    """Unary invocation of a streaming-capable handler should work normally."""
    token = await _issue_test_token(service, scope=["analyze"], capability="analyze")
    result = await service.invoke("analyze", token, {"target": "x"})
    assert result["success"] is True
    assert result["result"] == {"result": "done"}
    assert "stream_summary" not in result


async def test_streaming_rejected_for_unary_only(service):
    """Streaming request for a unary-only capability should fail."""
    token = await _issue_test_token(service, scope=["greet"], capability="greet")
    result = await service.invoke(
        "greet", token, {"name": "world"},
        stream=True,
    )
    assert result["success"] is False
    assert result["failure"]["type"] == "streaming_not_supported"
