"""MCP Streamable HTTP transport: calling tools with a delegation token.

These tests send real MCP ``tools/call`` requests over HTTP with a delegation
token as the bearer, the way an agent holding a token would. They pin the
authorization behaviour of the binding independently of the MCP SDK version:

- a token invokes the capability it was issued for;
- a token issued for another capability is refused (purpose binding);
- a token whose scope does not cover the capability is refused.

A refusal must reach the client as an MCP tool error carrying the ANIP failure
type, and the capability handler must not run.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anip_core import (
    CapabilityDeclaration, SideEffect, SideEffectType,
    CapabilityInput, CapabilityOutput,
)
from anip_service import ANIPService, Capability
from anip_mcp.http import mount_anip_mcp_http


HUMAN = "human:test@example.com"

SSE_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _capability(name: str, scope: list[str], calls: list[str]) -> Capability:
    def handler(ctx, params):
        calls.append(name)
        return {"message": f"{name}: {params.get('name', '')}"}

    return Capability(
        declaration=CapabilityDeclaration(
            name=name,
            description=name,
            inputs=[CapabilityInput(name="name", type="string", required=False, description="Who")],
            output=CapabilityOutput(type="object", fields=["message"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=scope,
        ),
        handler=handler,
    )


@pytest.fixture
def mcp_app():
    """(client, service, calls): an MCP HTTP app with two capabilities."""
    calls: list[str] = []
    service = ANIPService(
        service_id="test-mcp-http-tokens",
        capabilities=[
            _capability("greet", ["greet"], calls),
            _capability("farewell", ["farewell"], calls),
        ],
        storage=":memory:",
        authenticate=lambda bearer: HUMAN if bearer == "test-key" else None,
    )
    app = FastAPI()

    @asynccontextmanager
    async def lifespan(app_):
        await service.start()
        try:
            yield
        finally:
            await service.shutdown()

    app.router.lifespan_context = lifespan
    mount_anip_mcp_http(app, service)

    with TestClient(app) as client:
        yield client, service, calls


def _issue_token(client: TestClient, service: ANIPService, *, capability: str, scope: list[str]) -> str:
    """Issue a delegation token on the app's event loop and return the JWT."""
    issued = client.portal.call(service.issue_token, HUMAN, {
        "subject": "agent:test-agent",
        "scope": scope,
        "capability": capability,
    })
    return issued["token"]


def _call_tool(client: TestClient, bearer: str, tool: str) -> dict:
    """Send tools/call and return the JSON-RPC ``result`` object."""
    resp = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": tool, "arguments": {"name": "World"}},
    }, headers={**SSE_HEADERS, "Authorization": f"Bearer {bearer}"})
    assert resp.status_code == 200, resp.text
    payloads = [
        json.loads(line[len("data:"):].strip())
        for line in resp.text.splitlines()
        if line.startswith("data:")
    ]
    assert payloads, f"no SSE data event in response: {resp.text!r}"
    message = payloads[-1]
    assert "result" in message, f"expected a tool result, got {message}"
    return message["result"]


def _text(result: dict) -> str:
    return "\n".join(item.get("text", "") for item in result.get("content", []))


def test_call_tool_with_a_delegation_token(mcp_app):
    client, service, calls = mcp_app
    token = _issue_token(client, service, capability="greet", scope=["greet"])

    result = _call_tool(client, token, "greet")

    assert result.get("isError") is False, result
    assert "greet: World" in _text(result)
    assert calls == ["greet"]


def test_token_issued_for_another_capability_is_refused(mcp_app):
    client, service, calls = mcp_app
    # Scope covers both capabilities; the token is bound to "farewell".
    token = _issue_token(client, service, capability="farewell", scope=["greet", "farewell"])

    result = _call_tool(client, token, "greet")

    assert result.get("isError") is True, result
    assert "purpose_mismatch" in _text(result)
    assert calls == [], "the capability handler must not run"


def test_token_with_insufficient_scope_is_refused(mcp_app):
    client, service, calls = mcp_app
    # Bound to "greet", but the scope does not cover it.
    token = _issue_token(client, service, capability="greet", scope=["farewell"])

    result = _call_tool(client, token, "greet")

    assert result.get("isError") is True, result
    assert "scope_insufficient" in _text(result)
    assert calls == [], "the capability handler must not run"
