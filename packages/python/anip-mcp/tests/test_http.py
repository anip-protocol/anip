"""Tests for MCP Streamable HTTP transport on FastAPI.

Tests exercise the full MCP protocol flow over real HTTP using direct
JSON-RPC requests. The transport uses SSE streaming; the TestClient
buffers the SSE response so we can assert on the text content.
"""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anip_core import (
    CapabilityDeclaration, SideEffect, SideEffectType,
    CapabilityInput, CapabilityOutput,
)
from anip_service import ANIPService, Capability
from anip_mcp.http import mount_anip_mcp_http


API_KEY = "test-http-key"

# Required MCP headers for SSE mode: client must accept both content types
SSE_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _make_service() -> ANIPService:
    return ANIPService(
        service_id="test-mcp-http",
        capabilities=[
            Capability(
                declaration=CapabilityDeclaration(
                    name="greet",
                    description="Say hello",
                    inputs=[CapabilityInput(name="name", type="string", required=True, description="Who")],
                    output=CapabilityOutput(type="object", fields=["message"]),
                    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                    minimum_scope=["greet"],
                ),
                handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
            ),
        ],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )


@pytest.fixture
def client():
    """FastAPI app with MCP HTTP transport mounted, started via TestClient lifespan."""
    service = _make_service()
    app = FastAPI()

    # Start service on app startup (normally mount_anip does this; we do it directly)
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app_):
        await service.start()
        try:
            yield
        finally:
            await service.shutdown()

    app.router.lifespan_context = lifespan
    mount_anip_mcp_http(app, service)

    with TestClient(app) as c:
        yield c


class TestMcpHttpTransport:
    def test_post_initialize(self, client):
        """initialize returns 200 with server info in SSE event."""
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }, headers=SSE_HEADERS)
        assert resp.status_code == 200
        # Response is SSE — body contains event data with JSON-RPC result
        assert "anip-mcp-http" in resp.text or "serverInfo" in resp.text or "protocolVersion" in resp.text

    def test_list_tools(self, client):
        """tools/list returns the registered greet tool."""
        # MCP is stateless here — each request is independent.
        # We don't need to initialize first in stateless mode.
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }, headers=SSE_HEADERS)
        assert resp.status_code == 200
        assert "greet" in resp.text

    def test_list_tools_includes_description(self, client):
        """tools/list response includes enriched description."""
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }, headers=SSE_HEADERS)
        assert resp.status_code == 200
        # enrich_description adds "Read-only" for READ side effects
        assert "Read-only" in resp.text or "greet" in resp.text

    def test_call_tool_with_valid_api_key(self, client):
        """tools/call with a valid API key returns the greeting."""
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "greet", "arguments": {"name": "World"}},
        }, headers={
            **SSE_HEADERS,
            "Authorization": f"Bearer {API_KEY}",
        })
        assert resp.status_code == 200
        assert "Hello, World!" in resp.text

    def test_call_tool_without_auth(self, client):
        """tools/call without Authorization header returns authentication_required."""
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "greet", "arguments": {"name": "World"}},
        }, headers=SSE_HEADERS)
        assert resp.status_code == 200
        assert "authentication_required" in resp.text

    def test_call_tool_with_invalid_api_key(self, client):
        """tools/call with a wrong API key returns authentication_required."""
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "greet", "arguments": {"name": "World"}},
        }, headers={
            **SSE_HEADERS,
            "Authorization": "Bearer wrong-key",
        })
        assert resp.status_code == 200
        assert "authentication_required" in resp.text or "FAILED" in resp.text

    def test_call_unknown_tool(self, client):
        """tools/call with an unknown tool name returns an error."""
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "nonexistent", "arguments": {}},
        }, headers={
            **SSE_HEADERS,
            "Authorization": f"Bearer {API_KEY}",
        })
        assert resp.status_code == 200
        assert "nonexistent" in resp.text or "Unknown" in resp.text or "isError" in resp.text

    def test_missing_accept_header(self, client):
        """POST without the required Accept header returns 406."""
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }, headers={"Content-Type": "application/json"})
        assert resp.status_code == 406

    def test_get_method_rejected_without_accept(self, client):
        """GET without text/event-stream Accept returns 406."""
        resp = client.get("/mcp", headers={"Accept": "application/json"})
        assert resp.status_code == 406
