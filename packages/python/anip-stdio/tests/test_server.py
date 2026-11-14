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
        # SPEC.md §6.3 Token Issuance: an unrecognised credential is
        # authentication_required, like no credential at all.
        assert resp["error"]["data"]["type"] == "authentication_required"

    # A delegation token is a valid credential for delegating from a token
    # the caller holds (SPEC.md §6.3), and for nothing else.

    async def _held_token(self, server) -> dict:
        resp = await server.handle_request(_req("anip.tokens.issue", {
            "auth": {"bearer": "test-api-key"},
            "subject": "agent:test-agent", "scope": ["echo"], "capability": "echo",
        }))
        return resp["result"]

    async def test_holder_delegates_using_its_token_as_credential(self, server):
        held = await self._held_token(server)
        resp = await server.handle_request(_req("anip.tokens.issue", {
            "auth": {"bearer": held["token"]},
            "subject": "agent:sub-agent", "scope": ["echo"], "capability": "echo",
            "parent_token": held["token_id"],
        }))
        assert resp["result"]["issued"] is True

    async def test_token_credential_cannot_issue_a_root_token(self, server):
        held = await self._held_token(server)
        resp = await server.handle_request(_req("anip.tokens.issue", {
            "auth": {"bearer": held["token"]},
            "subject": "agent:test-agent", "scope": ["echo", "anything.else"], "capability": "echo",
        }))
        assert "error" in resp, "a delegation token was accepted as credential for root issuance"
        assert "insufficient_authority" in str(resp["error"])


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


class TestParameterValidation:
    """SPEC.md §6.3: the failure is in the JSON-RPC result, like any other."""

    RESOLUTION = {
        "action": "retry_now",
        "recovery_class": "retry_now",
        "requires": "parameters that match the capability's declared inputs",
    }

    async def test_missing_required_input(self, server):
        token_jwt = await _issue_token(server)
        resp = await server.handle_request(_req("anip.invoke", {
            "auth": {"bearer": token_jwt},
            "capability": "echo",
            "parameters": {},
            "client_reference_id": "ref-7",
        }))

        assert "error" not in resp
        result = resp["result"]
        assert result["success"] is False
        assert result["failure"] == {
            "type": "invalid_parameters",
            "detail": "echo is missing required input(s): message",
            "resolution": self.RESOLUTION,
            "retry": False,
        }
        assert result["invocation_id"].startswith("inv-")
        assert result["client_reference_id"] == "ref-7"

    @pytest.mark.parametrize("params", [{"parameters": None}, {}])
    async def test_absent_or_null_parameters(self, server, params):
        token_jwt = await _issue_token(server)
        resp = await server.handle_request(_req("anip.invoke", {
            "auth": {"bearer": token_jwt}, "capability": "echo", **params,
        }))

        assert resp["result"]["failure"]["type"] == "invalid_parameters"
        assert resp["result"]["failure"]["detail"] == "echo is missing required input(s): message"

    async def test_wrong_type_on_a_streaming_invocation(self, server):
        token_jwt = await _issue_token(server)
        resp = await server.handle_request(_req("anip.invoke", {
            "auth": {"bearer": token_jwt},
            "capability": "echo",
            "parameters": {"message": 5},
            "stream": True,
        }))

        assert isinstance(resp, list) and len(resp) == 1
        result = resp[0]["result"]
        assert result["success"] is False
        assert result["failure"] == {
            "type": "invalid_parameters",
            "detail": "echo has invalid input(s): 'message' must be string, got number",
            "resolution": self.RESOLUTION,
            "retry": False,
        }


# --- approval_grant on anip.invoke (SPEC.md §4.8) ---

def _approval_capability() -> Capability:
    from anip_core import GrantPolicy
    from anip_service import ANIPError

    async def handler(ctx: InvocationContext, params: dict) -> dict:
        if params["amount"] > 1000 and ctx.approval_grant is None:
            raise ANIPError(
                "approval_required", "transfers above 1000 need approval",
                approval_required={"preview": {"amount": params["amount"]}},
            )
        return {"transferred": params["amount"]}

    return Capability(
        declaration=CapabilityDeclaration(
            name="transfer",
            description="Transfer funds",
            inputs=[CapabilityInput(name="amount", type="number", required=True)],
            output=CapabilityOutput(type="object", fields=["transferred"]),
            side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
            minimum_scope=["finance.write"],
            response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
            grant_policy=GrantPolicy(
                allowed_grant_types=["one_time"], default_grant_type="one_time",
                expires_in_seconds=900, max_uses=1),
        ),
        handler=handler,
    )


class TestApprovalGrant:
    @pytest.fixture
    def approval_server(self):
        return AnipStdioServer(ANIPService(
            service_id="test-stdio-approvals",
            capabilities=[_approval_capability()],
            storage=":memory:",
            authenticate=lambda bearer: "human:test@example.com" if bearer == "test-api-key" else None,
        ))

    async def _token(self, server) -> str:
        resp = await server.handle_request(_req("anip.tokens.issue", {
            "auth": {"bearer": "test-api-key"}, "subject": "agent:test-agent",
            "scope": ["finance.write"], "capability": "transfer",
        }))
        return resp["result"]["token"]

    async def _invoke(self, server, token, **extra):
        return await server.handle_request(_req("anip.invoke", {
            "auth": {"bearer": token}, "capability": "transfer",
            "parameters": {"amount": 5000}, **extra,
        }))

    async def test_continuation_over_stdio_runs_with_the_grant(self, approval_server):
        token = await self._token(approval_server)
        first = await self._invoke(approval_server, token)
        failure = first["result"]["failure"]
        assert failure["type"] == "approval_required"
        grant = await approval_server._service.issue_approval_grant(
            failure["approval_required"]["approval_request_id"], "one_time",
            {"principal": "human:approver@example.com"})

        resp = await self._invoke(approval_server, token, approval_grant=grant["grant_id"])

        assert resp["result"]["success"] is True, resp
        assert resp["result"]["result"] == {"transferred": 5000}
        again = await self._invoke(approval_server, token, approval_grant=grant["grant_id"])
        assert again["result"]["failure"]["type"] == "grant_consumed"

    @pytest.mark.parametrize("grant", ["", "   ", 7], ids=["empty", "whitespace", "not-a-string"])
    @pytest.mark.parametrize("stream", [False, True], ids=["unary", "streaming"])
    async def test_blank_grant_is_not_found(self, approval_server, grant, stream):
        token = await self._token(approval_server)

        resp = await self._invoke(approval_server, token, approval_grant=grant, stream=stream)

        final = resp[-1] if isinstance(resp, list) else resp
        assert final["result"]["success"] is False, final
        assert final["result"]["failure"]["type"] == "grant_not_found"

    async def test_null_grant_is_no_grant(self, approval_server):
        token = await self._token(approval_server)

        resp = await self._invoke(approval_server, token, approval_grant=None)

        assert resp["result"]["failure"]["type"] == "approval_required"
