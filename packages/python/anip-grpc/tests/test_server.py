"""Integration tests for the ANIP gRPC server — all 10 RPCs through a real gRPC channel."""
from __future__ import annotations

import json
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

# Ensure generated stubs resolve their internal imports
_generated_dir = str(Path(__file__).resolve().parent.parent / "src" / "anip_grpc" / "generated")
if _generated_dir not in sys.path:
    sys.path.insert(0, _generated_dir)

from anip_grpc.generated.anip.v1 import anip_pb2
from anip_grpc.generated.anip.v1 import anip_pb2_grpc


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
        service_id="test-grpc-service",
        capabilities=[_echo_capability()],
        storage=":memory:",
        authenticate=lambda bearer: "human:test@example.com" if bearer == "test-api-key" else None,
    )


@pytest.fixture(scope="module")
def grpc_channel(grpc_service):
    """Start a gRPC server on a random port and return a channel to it."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    anip_pb2_grpc.add_AnipServiceServicer_to_server(
        AnipGrpcServicer(grpc_service), server,
    )
    port = server.add_insecure_port("[::]:0")
    server.start()
    channel = grpc.insecure_channel(f"localhost:{port}")
    yield channel
    channel.close()
    server.stop(grace=0)


@pytest.fixture(scope="module")
def stub(grpc_channel):
    """Return an AnipServiceStub connected to the test server."""
    return anip_pb2_grpc.AnipServiceStub(grpc_channel)


def _auth_metadata(token: str):
    """Build gRPC metadata with a bearer token."""
    return [("authorization", f"Bearer {token}")]


def _issue_token(stub: anip_pb2_grpc.AnipServiceStub) -> str:
    """Issue a token via gRPC and return the JWT string."""
    resp = stub.IssueToken(
        anip_pb2.IssueTokenRequest(
            subject="agent:test-agent",
            scope=["echo"],
            capability="echo",
            caller_class="internal",
        ),
        metadata=_auth_metadata("test-api-key"),
    )
    assert resp.issued is True, f"Token issuance failed: {resp}"
    assert resp.token != ""
    return resp.token


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDiscovery:
    def test_returns_protocol_version(self, stub):
        resp = stub.Discovery(anip_pb2.DiscoveryRequest())
        data = json.loads(resp.json)
        assert "anip_discovery" in data
        assert "protocol" in data["anip_discovery"]

    def test_contains_capabilities(self, stub):
        resp = stub.Discovery(anip_pb2.DiscoveryRequest())
        data = json.loads(resp.json)
        assert "echo" in data["anip_discovery"]["capabilities"]


class TestManifest:
    def test_returns_manifest_and_signature(self, stub):
        resp = stub.Manifest(anip_pb2.ManifestRequest())
        assert resp.manifest_json != ""
        assert resp.signature != ""
        manifest = json.loads(resp.manifest_json)
        assert isinstance(manifest, dict)


class TestJwks:
    def test_returns_keys(self, stub):
        resp = stub.Jwks(anip_pb2.JwksRequest())
        data = json.loads(resp.json)
        assert "keys" in data
        assert isinstance(data["keys"], list)


class TestIssueToken:
    def test_issue_with_api_key(self, stub):
        resp = stub.IssueToken(
            anip_pb2.IssueTokenRequest(
                subject="agent:test-agent",
                scope=["echo"],
                capability="echo",
            ),
            metadata=_auth_metadata("test-api-key"),
        )
        assert resp.issued is True
        assert resp.token != ""
        assert resp.token_id != ""
        assert resp.expires != ""

    def test_issue_without_auth_returns_unauthenticated(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.IssueToken(anip_pb2.IssueTokenRequest(
                subject="agent:test-agent",
                scope=["echo"],
            ))
        assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED

    def test_issue_with_bad_key_returns_unauthenticated(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.IssueToken(
                anip_pb2.IssueTokenRequest(
                    subject="agent:test-agent",
                    scope=["echo"],
                ),
                metadata=_auth_metadata("wrong-key"),
            )
        assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


class TestInvoke:
    def test_invoke_with_jwt(self, stub):
        token = _issue_token(stub)
        resp = stub.Invoke(
            anip_pb2.InvokeRequest(
                capability="echo",
                parameters_json=json.dumps({"message": "hello"}),
                client_reference_id="ref-001",
            ),
            metadata=_auth_metadata(token),
        )
        assert resp.success is True
        assert resp.invocation_id != ""
        result = json.loads(resp.result_json)
        assert result["echo"] == "hello"

    def test_invoke_without_auth_returns_unauthenticated(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.Invoke(anip_pb2.InvokeRequest(
                capability="echo",
                parameters_json=json.dumps({"message": "hello"}),
            ))
        assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED

    def test_invoke_unknown_capability_returns_failure(self, stub):
        token = _issue_token(stub)
        resp = stub.Invoke(
            anip_pb2.InvokeRequest(
                capability="nonexistent",
                parameters_json=json.dumps({}),
            ),
            metadata=_auth_metadata(token),
        )
        # ANIP failures are returned as successful gRPC responses with failure field
        assert resp.success is False
        assert resp.failure.type != ""


class TestInvokeStream:
    def test_invoke_stream_returns_completed(self, stub):
        token = _issue_token(stub)
        events = list(stub.InvokeStream(
            anip_pb2.InvokeRequest(
                capability="echo",
                parameters_json=json.dumps({"message": "streamed"}),
                client_reference_id="ref-stream",
            ),
            metadata=_auth_metadata(token),
        ))
        # Should have at least a completed event
        assert len(events) >= 1
        last = events[-1]
        assert last.HasField("completed")
        result = json.loads(last.completed.result_json)
        assert result["echo"] == "streamed"

    def test_invoke_stream_without_auth(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            list(stub.InvokeStream(anip_pb2.InvokeRequest(
                capability="echo",
                parameters_json=json.dumps({"message": "hello"}),
            )))
        assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED

    def test_invoke_stream_unknown_capability(self, stub):
        token = _issue_token(stub)
        events = list(stub.InvokeStream(
            anip_pb2.InvokeRequest(
                capability="nonexistent",
                parameters_json=json.dumps({}),
            ),
            metadata=_auth_metadata(token),
        ))
        assert len(events) >= 1
        last = events[-1]
        assert last.HasField("failed")
        assert last.failed.failure.type != ""


class TestPermissions:
    def test_discover_permissions(self, stub):
        token = _issue_token(stub)
        resp = stub.Permissions(
            anip_pb2.PermissionsRequest(),
            metadata=_auth_metadata(token),
        )
        assert resp.success is True
        data = json.loads(resp.json)
        assert "available" in data or "restricted" in data or "denied" in data

    def test_permissions_without_auth(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.Permissions(anip_pb2.PermissionsRequest())
        assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


class TestQueryAudit:
    def test_audit_after_invocation(self, stub):
        token = _issue_token(stub)

        # Invoke something to create audit entries
        stub.Invoke(
            anip_pb2.InvokeRequest(
                capability="echo",
                parameters_json=json.dumps({"message": "audit-test"}),
            ),
            metadata=_auth_metadata(token),
        )

        # Query audit
        resp = stub.QueryAudit(
            anip_pb2.QueryAuditRequest(capability="echo"),
            metadata=_auth_metadata(token),
        )
        assert resp.success is True
        data = json.loads(resp.json)
        assert "entries" in data
        assert "count" in data

    def test_audit_without_auth(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.QueryAudit(anip_pb2.QueryAuditRequest())
        assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


class TestListCheckpoints:
    def test_list_checkpoints(self, stub):
        resp = stub.ListCheckpoints(anip_pb2.ListCheckpointsRequest(limit=5))
        data = json.loads(resp.json)
        assert "checkpoints" in data
        assert isinstance(data["checkpoints"], list)


class TestGetCheckpoint:
    def test_get_missing_checkpoint(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.GetCheckpoint(anip_pb2.GetCheckpointRequest(id="cp-nonexistent"))
        assert exc_info.value.code() == grpc.StatusCode.NOT_FOUND

    def test_get_missing_id(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.GetCheckpoint(anip_pb2.GetCheckpointRequest())
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
