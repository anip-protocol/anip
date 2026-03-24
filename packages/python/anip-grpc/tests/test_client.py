"""Integration tests for AnipGrpcClient — full round-trip through a real gRPC channel."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import grpc
from concurrent import futures

from anip_service import ANIPService, Capability, InvocationContext
from anip_core import (
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    ResponseMode,
    SideEffect,
    SideEffectType,
)

from anip_grpc.server import AnipGrpcServicer
from anip_grpc.client import AnipGrpcClient

# Ensure generated stubs resolve their internal imports
_generated_dir = str(Path(__file__).resolve().parent.parent / "src" / "anip_grpc" / "generated")
if _generated_dir not in sys.path:
    sys.path.insert(0, _generated_dir)

from anip_grpc.generated.anip.v1 import anip_pb2_grpc  # noqa: E402


# ---------------------------------------------------------------------------
# Test capability: echo
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def grpc_service():
    """Create a shared ANIPService for the module."""
    return ANIPService(
        service_id="test-client-service",
        capabilities=[_echo_capability()],
        storage=":memory:",
        authenticate=lambda bearer: "human:test@example.com" if bearer == "test-api-key" else None,
    )


@pytest.fixture(scope="module")
def grpc_port(grpc_service):
    """Start a gRPC server on a random port and yield the port number."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    anip_pb2_grpc.add_AnipServiceServicer_to_server(
        AnipGrpcServicer(grpc_service), server,
    )
    port = server.add_insecure_port("[::]:0")
    server.start()
    yield port
    server.stop(grace=0)


@pytest.fixture(scope="module")
def client(grpc_port):
    """Return an AnipGrpcClient connected to the test server."""
    c = AnipGrpcClient(f"localhost:{grpc_port}")
    yield c
    c.close()


def _issue_token(client: AnipGrpcClient) -> str:
    """Issue a JWT using the test API key and return the token string."""
    resp = client.issue_token(
        bearer="test-api-key",
        subject="agent:test-agent",
        scope=["echo"],
        capability="echo",
        caller_class="internal",
    )
    assert resp["issued"] is True, f"Token issuance failed: {resp}"
    assert resp.get("token"), "Expected a token string"
    return resp["token"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDiscovery:
    def test_returns_protocol_version(self, client):
        data = client.discovery()
        assert "anip_discovery" in data
        assert "protocol" in data["anip_discovery"]

    def test_contains_capabilities(self, client):
        data = client.discovery()
        assert "echo" in data["anip_discovery"]["capabilities"]


class TestManifest:
    def test_returns_manifest_and_signature(self, client):
        data = client.manifest()
        assert "manifest" in data
        assert "signature" in data
        assert isinstance(data["manifest"], dict)
        assert data["signature"] != ""


class TestJwks:
    def test_returns_keys(self, client):
        data = client.jwks()
        assert "keys" in data
        assert isinstance(data["keys"], list)


class TestIssueToken:
    def test_issue_with_api_key(self, client):
        resp = client.issue_token(
            bearer="test-api-key",
            subject="agent:test-agent",
            scope=["echo"],
            capability="echo",
        )
        assert resp["issued"] is True
        assert resp.get("token")
        assert resp.get("token_id")
        assert resp.get("expires")

    def test_issue_without_auth_raises(self, grpc_port):
        """Calling without a valid bearer raises grpc.RpcError (UNAUTHENTICATED)."""
        with AnipGrpcClient(f"localhost:{grpc_port}") as c:
            with pytest.raises(grpc.RpcError) as exc_info:
                c.issue_token(
                    bearer="wrong-key",
                    subject="agent:test-agent",
                    scope=["echo"],
                    capability="echo",
                )
            assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


class TestInvoke:
    def test_invoke_with_jwt_succeeds(self, client):
        token = _issue_token(client)
        resp = client.invoke(
            bearer=token,
            capability="echo",
            parameters={"message": "hello"},
            client_reference_id="ref-client-001",
        )
        assert resp["success"] is True
        assert resp["invocation_id"] != ""
        assert resp["result"]["echo"] == "hello"

    def test_invoke_without_auth_raises(self, grpc_port):
        """Invoking without a bearer raises grpc.RpcError (UNAUTHENTICATED)."""
        with AnipGrpcClient(f"localhost:{grpc_port}") as c:
            with pytest.raises(grpc.RpcError) as exc_info:
                c.invoke(
                    bearer="not-a-jwt",
                    capability="echo",
                    parameters={"message": "hello"},
                )
            assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED

    def test_invoke_unknown_capability_returns_failure(self, client):
        token = _issue_token(client)
        resp = client.invoke(
            bearer=token,
            capability="nonexistent",
            parameters={},
        )
        assert resp["success"] is False
        assert "failure" in resp
        assert resp["failure"]["type"] != ""


class TestInvokeStream:
    def test_stream_yields_completed_event(self, client):
        token = _issue_token(client)
        events = list(client.invoke_stream(
            bearer=token,
            capability="echo",
            parameters={"message": "streamed"},
            client_reference_id="ref-stream-001",
        ))
        assert len(events) >= 1
        last = events[-1]
        assert last["type"] == "completed"
        assert last["result"]["echo"] == "streamed"

    def test_stream_without_auth_raises(self, grpc_port):
        with AnipGrpcClient(f"localhost:{grpc_port}") as c:
            with pytest.raises(grpc.RpcError) as exc_info:
                list(c.invoke_stream(
                    bearer="not-a-jwt",
                    capability="echo",
                    parameters={"message": "hello"},
                ))
            assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED

    def test_stream_unknown_capability_yields_failed_event(self, client):
        token = _issue_token(client)
        events = list(client.invoke_stream(
            bearer=token,
            capability="nonexistent",
            parameters={},
        ))
        assert len(events) >= 1
        last = events[-1]
        assert last["type"] == "failed"
        assert last["failure"]["type"] != ""


class TestPermissions:
    def test_returns_permissions(self, client):
        token = _issue_token(client)
        resp = client.permissions(bearer=token)
        assert resp["success"] is True
        assert "available" in resp or "restricted" in resp or "denied" in resp

    def test_without_auth_raises(self, grpc_port):
        with AnipGrpcClient(f"localhost:{grpc_port}") as c:
            with pytest.raises(grpc.RpcError) as exc_info:
                c.permissions(bearer="not-a-jwt")
            assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


class TestQueryAudit:
    def test_audit_after_invocation(self, client):
        token = _issue_token(client)

        # Invoke something to create audit entries first
        client.invoke(
            bearer=token,
            capability="echo",
            parameters={"message": "audit-test"},
        )

        resp = client.query_audit(bearer=token, capability="echo")
        assert resp["success"] is True
        assert "entries" in resp
        assert "count" in resp

    def test_audit_without_auth_raises(self, grpc_port):
        with AnipGrpcClient(f"localhost:{grpc_port}") as c:
            with pytest.raises(grpc.RpcError) as exc_info:
                c.query_audit(bearer="not-a-jwt")
            assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


class TestListCheckpoints:
    def test_list_checkpoints(self, client):
        resp = client.list_checkpoints(limit=5)
        assert "checkpoints" in resp
        assert isinstance(resp["checkpoints"], list)


class TestContextManager:
    def test_context_manager_closes_channel(self, grpc_port):
        with AnipGrpcClient(f"localhost:{grpc_port}") as c:
            data = c.discovery()
            assert "anip_discovery" in data
        # After exiting, the channel is closed — further calls should fail
        with pytest.raises(Exception):
            c.discovery()
