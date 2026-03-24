#!/usr/bin/env python3
"""Minimal ANIP stdio server for testing the client."""
import asyncio

from anip_service import ANIPService, Capability, InvocationContext
from anip_core import (
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    SideEffect,
    SideEffectType,
)
from anip_stdio import serve_stdio


async def _echo_handler(ctx: InvocationContext, params: dict) -> dict:
    return {"message": params.get("message", "")}


service = ANIPService(
    service_id="test-stdio-client",
    capabilities=[
        Capability(
            declaration=CapabilityDeclaration(
                name="echo",
                description="Echo",
                contract_version="1.0",
                inputs=[CapabilityInput(name="message", type="string", description="msg")],
                output=CapabilityOutput(type="object", fields=["message"]),
                side_effect=SideEffect(type=SideEffectType.READ),
                minimum_scope=["test"],
            ),
            handler=_echo_handler,
        ),
    ],
    storage=":memory:",
    authenticate=lambda bearer: "user@test.com" if bearer == "test-key" else None,
)

asyncio.run(serve_stdio(service))
