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


# --- The service's own check (SPEC.md §6.3) ---------------------------------------


async def test_service_refusal_is_a_tool_error_carrying_the_failure():
    """The schema check above refuses first. A refusal by the service's own
    parameter validation is also a tool error, never a success, and carries
    the failure type, detail and resolution."""
    from anip_mcp.invocation import invoke_with_token, resolve_auth

    calls: list[dict] = []
    service = _service(calls)
    await service.start()
    try:
        token = await resolve_auth(API_KEY, service, "charge")

        result = await invoke_with_token(service, "charge", {"note": "no amount"}, token)
    finally:
        await service.shutdown()

    assert result.is_error is True
    assert result.text.splitlines() == [
        "FAILED: invalid_parameters",
        "Detail: charge is missing required input(s): amount",
        "Resolution: retry_now",
        "Requires: parameters that match the capability's declared inputs",
        "Retryable: no",
    ]
    assert calls == [], "the capability handler must not run"


# --- array and object inputs ------------------------------------------------------


def _structured_service(calls: list[dict]) -> ANIPService:
    def handler(ctx, params):
        calls.append(dict(params))
        return {"ok": True}

    return ANIPService(
        service_id="test-mcp-structured",
        capabilities=[
            Capability(
                declaration=CapabilityDeclaration(
                    name="book",
                    description="Book with a quote",
                    inputs=[
                        CapabilityInput(name="quote", type="object", description="Quote"),
                        CapabilityInput(name="tags", type="array", required=False, description="Tags"),
                    ],
                    output=CapabilityOutput(type="object", fields=["ok"]),
                    side_effect=SideEffect(type=SideEffectType.WRITE, rollback_window="none"),
                    minimum_scope=["book"],
                ),
                handler=handler,
            ),
        ],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )


def test_array_and_object_inputs_are_advertised_as_such():
    from anip_mcp.translation import capability_to_input_schema

    schema = capability_to_input_schema({"inputs": [
        {"name": "quote", "type": "object"},
        {"name": "tags", "type": "array", "required": False},
        {"name": "implicit", "type": "string"},
    ]})

    assert schema["properties"]["quote"]["type"] == "object"
    assert schema["properties"]["tags"]["type"] == "array"
    assert schema["required"] == ["quote", "implicit"]


async def test_object_and_array_arguments_reach_the_capability():
    from mcp import Client
    from mcp.server.lowlevel import Server
    from anip_mcp import mount_anip_mcp, McpCredentials

    calls: list[dict] = []
    server = Server("test-mcp-structured")
    lifecycle = await mount_anip_mcp(
        server, _structured_service(calls),
        credentials=McpCredentials(api_key=API_KEY, scope=["book"], subject="test-agent"),
    )
    try:
        async with Client(server) as client:
            accepted = await client.call_tool("book", {"quote": {"id": "q1"}, "tags": ["a"]})
            refused = await client.call_tool("book", {"quote": "q1"})
    finally:
        await lifecycle.shutdown()

    assert accepted.is_error is False, accepted.content
    assert calls == [{"quote": {"id": "q1"}, "tags": ["a"]}]
    assert refused.is_error is True
    assert "Input validation error" in refused.content[0].text


# --- inputs that declare resolution.on_missing (SPEC.md §4.10) ---------------------


def test_input_with_on_missing_is_not_required_by_the_tool_schema():
    from anip_mcp.translation import capability_to_input_schema

    schema = capability_to_input_schema({"inputs": [
        {"name": "region", "type": "string", "required": True,
         "resolution": {"mode": "clarify", "on_missing": "clarify"}},
        {"name": "mode_only", "type": "string", "required": True,
         "resolution": {"mode": "clarify", "on_missing": None}},
        {"name": "plain", "type": "string", "required": True, "resolution": None},
    ]})

    assert schema["required"] == ["mode_only", "plain"]
    assert schema["properties"]["region"]["type"] == "string"


async def test_missing_on_missing_input_reaches_the_capability():
    from mcp import Client
    from mcp.server.lowlevel import Server
    from anip_mcp import mount_anip_mcp, McpCredentials

    calls: list[dict] = []

    def handler(ctx, params):
        calls.append(dict(params))
        return {"ok": True}

    service = ANIPService(
        service_id="test-mcp-on-missing",
        capabilities=[
            Capability(
                declaration=CapabilityDeclaration(
                    name="report",
                    description="Report for a region",
                    inputs=[
                        CapabilityInput(
                            name="region", type="string", required=True, description="Region",
                            resolution={"mode": "clarify", "on_missing": "clarify"}),
                    ],
                    output=CapabilityOutput(type="object", fields=["ok"]),
                    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                    minimum_scope=["report"],
                ),
                handler=handler,
            ),
        ],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )
    server = Server("test-mcp-on-missing")
    lifecycle = await mount_anip_mcp(
        server, service,
        credentials=McpCredentials(api_key=API_KEY, scope=["report"], subject="test-agent"),
    )
    try:
        async with Client(server) as client:
            absent = await client.call_tool("report", {})
            wrong = await client.call_tool("report", {"region": 5})
    finally:
        await lifecycle.shutdown()

    assert absent.is_error is False, absent.content
    assert calls == [{}]
    assert wrong.is_error is True
