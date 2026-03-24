"""Integration tests for the ANIP stdio server — all 9 methods through handle_request()."""
from __future__ import annotations

import pytest
from anip_service import ANIPService, Capability, InvocationContext
from anip_core import (
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    ResponseMode,
    SideEffect,
    SideEffectType,
)

from anip_stdio.server import AnipStdioServer


# --- Test capability: echo ---

def _echo_capability() -> Capability:
    async def handler(ctx: InvocationContext, params: dict) -> dict:
        return {"echo": params.get("message", ""), "invocation_id": ctx.invocation_id}

    return Capability(
        declaration=CapabilityDeclaration(
            name="echo",
            description="Echo the input back",
            inputs=[CapabilityInput(name="message", type="string", required=True, description="message")],
            output=CapabilityOutput(type="object", fields=["echo"]),
            side_effect=SideEffect(type=SideEffectType.READ),
            minimum_scope=["echo"],
            response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
        ),
        handler=handler,
    )


# --- Fixtures ---

@pytest.fixture
def service():
    return ANIPService(
        service_id="test-stdio-service",
        capabilities=[_echo_capability()],
        storage=":memory:",
        authenticate=lambda bearer: "human:test@example.com" if bearer == "test-api-key" else None,
    )


@pytest.fixture
def server(service):
    return AnipStdioServer(service)


def _req(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    """Build a JSON-RPC request."""
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


# --- Helper to issue a token via the server ---

async def _issue_token(server: AnipStdioServer) -> str:
    """Issue a token through the server and return the JWT string."""
    resp = await server.handle_request(_req("anip.tokens.issue", {
        "auth": {"bearer": "test-api-key"},
        "subject": "agent:test-agent",
        "scope": ["echo"],
        "capability": "echo",
        "caller_class": "internal",
    }))
    assert "result" in resp, f"Expected result, got: {resp}"
    assert resp["result"]["issued"] is True
    return resp["result"]["token"]


# --- Tests ---

class TestDiscovery:
    async def test_returns_protocol_version(self, server):
        resp = await server.handle_request(_req("anip.discovery"))
        assert "result" in resp
        assert "anip_discovery" in resp["result"]
        assert "protocol" in resp["result"]["anip_discovery"]

    async def test_contains_capabilities(self, server):
        resp = await server.handle_request(_req("anip.discovery"))
        caps = resp["result"]["anip_discovery"]["capabilities"]
        assert "echo" in caps


class TestManifest:
    async def test_returns_manifest_and_signature(self, server):
        resp = await server.handle_request(_req("anip.manifest"))
        assert "result" in resp
        result = resp["result"]
        assert "manifest" in result
        assert "signature" in result
        assert isinstance(result["manifest"], dict)
        assert isinstance(result["signature"], str)


class TestJWKS:
    async def test_returns_keys(self, server):
        resp = await server.handle_request(_req("anip.jwks"))
        assert "result" in resp
        assert "keys" in resp["result"]
        assert isinstance(resp["result"]["keys"], list)


class TestTokensIssue:
    async def test_issue_with_api_key(self, server):
        resp = await server.handle_request(_req("anip.tokens.issue", {
            "auth": {"bearer": "test-api-key"},
            "subject": "agent:test-agent",
            "scope": ["echo"],
            "capability": "echo",
        }))
        assert "result" in resp
        result = resp["result"]
        assert result["issued"] is True
        assert "token" in result
        assert "token_id" in result
        assert "expires" in result

    async def test_issue_without_auth_returns_error(self, server):
        resp = await server.handle_request(_req("anip.tokens.issue", {
            "subject": "agent:test-agent",
            "scope": ["echo"],
        }))
        assert "error" in resp
        assert resp["error"]["code"] == -32001

    async def test_issue_with_bad_key_returns_error(self, server):
        resp = await server.handle_request(_req("anip.tokens.issue", {
            "auth": {"bearer": "wrong-key"},
            "subject": "agent:test-agent",
            "scope": ["echo"],
        }))
        assert "error" in resp
        assert resp["error"]["code"] == -32001


class TestInvoke:
    async def test_invoke_with_jwt(self, server):
        token_jwt = await _issue_token(server)
        resp = await server.handle_request(_req("anip.invoke", {
            "auth": {"bearer": token_jwt},
            "capability": "echo",
            "parameters": {"message": "hello"},
            "client_reference_id": "ref-001",
        }))
        assert "result" in resp
        result = resp["result"]
        assert result["success"] is True
        assert result["result"]["echo"] == "hello"
        assert "invocation_id" in result

    async def test_invoke_without_auth_returns_error(self, server):
        resp = await server.handle_request(_req("anip.invoke", {
            "capability": "echo",
            "parameters": {"message": "hello"},
        }))
        assert "error" in resp
        assert resp["error"]["code"] == -32001

    async def test_invoke_streaming(self, server):
        token_jwt = await _issue_token(server)
        resp = await server.handle_request(_req("anip.invoke", {
            "auth": {"bearer": token_jwt},
            "capability": "echo",
            "parameters": {"message": "streamed"},
            "stream": True,
        }))
        # Streaming returns a list: [notifications..., final_response]
        assert isinstance(resp, list)
        assert len(resp) >= 1
        final = resp[-1]
        assert "result" in final
        assert final["result"]["success"] is True


class TestPermissions:
    async def test_discover_permissions(self, server):
        token_jwt = await _issue_token(server)
        resp = await server.handle_request(_req("anip.permissions", {
            "auth": {"bearer": token_jwt},
        }))
        assert "result" in resp
        # PermissionResponse has available/restricted/denied
        result = resp["result"]
        assert "available" in result or "restricted" in result or "denied" in result

    async def test_permissions_without_auth(self, server):
        resp = await server.handle_request(_req("anip.permissions", {}))
        assert "error" in resp
        assert resp["error"]["code"] == -32001


class TestAuditQuery:
    async def test_audit_after_invocation(self, server):
        token_jwt = await _issue_token(server)

        # Invoke something to create audit entries
        await server.handle_request(_req("anip.invoke", {
            "auth": {"bearer": token_jwt},
            "capability": "echo",
            "parameters": {"message": "audit-test"},
        }))

        # Query audit
        resp = await server.handle_request(_req("anip.audit.query", {
            "auth": {"bearer": token_jwt},
            "capability": "echo",
        }))
        assert "result" in resp
        result = resp["result"]
        assert "entries" in result
        assert "count" in result

    async def test_audit_without_auth(self, server):
        resp = await server.handle_request(_req("anip.audit.query", {}))
        assert "error" in resp
        assert resp["error"]["code"] == -32001


class TestCheckpointsList:
    async def test_list_checkpoints(self, server):
        resp = await server.handle_request(_req("anip.checkpoints.list", {"limit": 5}))
        assert "result" in resp
        result = resp["result"]
        assert "checkpoints" in result
        assert isinstance(result["checkpoints"], list)


class TestCheckpointsGet:
    async def test_get_missing_checkpoint(self, server):
        resp = await server.handle_request(_req("anip.checkpoints.get", {
            "id": "cp-nonexistent",
        }))
        assert "error" in resp
        assert resp["error"]["code"] == -32004

    async def test_get_missing_id(self, server):
        resp = await server.handle_request(_req("anip.checkpoints.get", {}))
        assert "error" in resp
        assert resp["error"]["code"] == -32004


class TestErrorHandling:
    async def test_unknown_method(self, server):
        resp = await server.handle_request(_req("anip.nonexistent"))
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    async def test_invalid_request_missing_jsonrpc(self, server):
        resp = await server.handle_request({"id": 1, "method": "anip.discovery"})
        assert "error" in resp
        assert resp["error"]["code"] == -32600

    async def test_invalid_request_missing_id(self, server):
        resp = await server.handle_request({"jsonrpc": "2.0", "method": "anip.discovery"})
        assert "error" in resp
        assert resp["error"]["code"] == -32600

    async def test_invalid_request_missing_method(self, server):
        resp = await server.handle_request({"jsonrpc": "2.0", "id": 1})
        assert "error" in resp
        assert resp["error"]["code"] == -32600
