"""Tool arguments are validated against the advertised input schema.

A tool's input schema is a promise to the capability: arguments that do not
match it must be refused at the MCP boundary, as a tool error, before the
capability handler runs. The 1.x MCP SDK did this inside its ``call_tool``
decorator. The 2.x SDK does not, so the bindings validate themselves.

Both bindings are covered: the Streamable HTTP transport (real ``tools/call``
requests) and the mount on a caller-supplied ``Server`` (a real MCP client
session against the mounted server).
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


API_KEY = "test-key"

SSE_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}

# Arguments that do not satisfy {"amount": integer, required}.
INVALID_ARGUMENTS = [
    pytest.param({}, id="missing-required"),
    pytest.param({"amount": "not-an-integer"}, id="wrong-type"),
    pytest.param({"amount": None}, id="null"),
    pytest.param({"amount": True}, id="boolean-as-integer"),
    pytest.param({"amount": 1.5}, id="fraction-as-integer"),
]


def _service(calls: list[dict]) -> ANIPService:
    def handler(ctx, params):
        calls.append(dict(params))
        return {"charged": params.get("amount")}

    return ANIPService(
        service_id="test-mcp-validation",
        capabilities=[
            Capability(
                declaration=CapabilityDeclaration(
                    name="charge",
                    description="Charge an amount",
                    inputs=[
                        CapabilityInput(name="amount", type="integer", required=True, description="Amount"),
                        CapabilityInput(name="note", type="string", required=False, description="Note"),
                    ],
                    output=CapabilityOutput(type="object", fields=["charged"]),
                    side_effect=SideEffect(type=SideEffectType.WRITE, rollback_window="none"),
                    minimum_scope=["charge"],
                ),
                handler=handler,
            ),
        ],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )


# --- Streamable HTTP transport -------------------------------------------------


@pytest.fixture
def http_app():
    """(client, calls): the HTTP transport mounted on a FastAPI app."""
    calls: list[dict] = []
    service = _service(calls)
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
        yield client, calls


def _http_call(client: TestClient, arguments: dict) -> dict:
    resp = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {"name": "charge", "arguments": arguments},
    }, headers={**SSE_HEADERS, "Authorization": f"Bearer {API_KEY}"})
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


def test_http_valid_arguments_reach_the_capability(http_app):
    client, calls = http_app

    result = _http_call(client, {"amount": 100})

    assert result.get("isError") is False, result
    assert calls == [{"amount": 100}]


@pytest.mark.parametrize("arguments", INVALID_ARGUMENTS)
def test_http_invalid_arguments_are_refused_before_the_capability_runs(http_app, arguments):
    client, calls = http_app

    result = _http_call(client, arguments)

    assert result.get("isError") is True, result
    assert "Input validation error" in _text(result)
    assert calls == [], "the capability handler must not run"


# --- Mount on a caller-supplied Server ------------------------------------------


@pytest.fixture
async def mounted():
    """(server, calls): the stdio-style mount on a lowlevel MCP Server."""
    from mcp.server.lowlevel import Server
    from anip_mcp import mount_anip_mcp, McpCredentials

    calls: list[dict] = []
    server = Server("test-mcp-validation")
    lifecycle = await mount_anip_mcp(
        server, _service(calls),
        credentials=McpCredentials(api_key=API_KEY, scope=["charge"], subject="test-agent"),
    )
    yield server, calls
    await lifecycle.shutdown()


async def test_mounted_valid_arguments_reach_the_capability(mounted):
    server, calls = mounted
    from mcp import Client

    async with Client(server) as client:
        result = await client.call_tool("charge", {"amount": 100})

    assert result.is_error is False
    assert calls == [{"amount": 100}]


@pytest.mark.parametrize("arguments", INVALID_ARGUMENTS)
async def test_mounted_invalid_arguments_are_refused_before_the_capability_runs(mounted, arguments):
    server, calls = mounted
    from mcp import Client

    async with Client(server) as client:
        result = await client.call_tool("charge", arguments)

    assert result.is_error is True
    assert "Input validation error" in result.content[0].text
    assert calls == [], "the capability handler must not run"
