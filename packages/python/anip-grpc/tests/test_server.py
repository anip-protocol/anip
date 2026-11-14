"""Integration tests for the ANIP gRPC server — all 10 RPCs through a real gRPC channel."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import grpc
from concurrent import futures

from anip_service import ANIPError, ANIPService, Capability, InvocationContext
from anip_core import (
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    GrantPolicy,
    PROTOCOL_VERSION,
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
        return {
            "echo": params.get("message", ""),
            "invocation_id": ctx.invocation_id,
            "requested_effects": ctx.requested_effects,
        }

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


def _approval_required_capability() -> Capability:
    async def handler(ctx: InvocationContext, params: dict) -> dict:
        if params.get("amount", 0) > 10000:
            raise ANIPError(
                "approval_required",
                "needs approval",
                approval_required={"preview": {"amount": params["amount"], "to_account": params["to_account"]}},
            )
        return {"transfer_id": "tx"}

    return Capability(
        declaration=CapabilityDeclaration(
            name="transfer_funds",
            description="High-value transfer",
            inputs=[
                CapabilityInput(name="amount", type="number", required=True, description="amount"),
                CapabilityInput(name="to_account", type="string", required=True, description="destination"),
            ],
            output=CapabilityOutput(type="transfer_confirmation", fields=["transfer_id"]),
            side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
            minimum_scope=["finance.write"],
            response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
            grant_policy=GrantPolicy(
                allowed_grant_types=["one_time", "session_bound"],
                default_grant_type="one_time",
                expires_in_seconds=900,
                max_uses=1,
            ),
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


def _issue_capability_token(stub: anip_pb2_grpc.AnipServiceStub, *, scope: list[str], capability: str) -> str:
    resp = stub.IssueToken(
        anip_pb2.IssueTokenRequest(
            subject="agent:test-agent",
            scope=scope,
            capability=capability,
            caller_class="internal",
        ),
        metadata=_auth_metadata("test-api-key"),
    )
    assert resp.issued is True, f"Token issuance failed: {resp}"
    assert resp.token != ""
    return resp.token


@pytest.fixture
def approval_stub():
    async def authenticate(token: str) -> str | None:
        if token == "test-api-key":
            return "human:test@example.com"
        return None

    service = ANIPService(
        service_id="test-grpc-finance-service",
        capabilities=[_approval_required_capability()],
        storage=":memory:",
        authenticate=authenticate,
    )
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    anip_pb2_grpc.add_AnipServiceServicer_to_server(AnipGrpcServicer(service), server)
    port = server.add_insecure_port("[::]:0")
    server.start()
    channel = grpc.insecure_channel(f"localhost:{port}")
    try:
        yield anip_pb2_grpc.AnipServiceStub(channel)
    finally:
        channel.close()
        server.stop(grace=0)


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

    # A delegation token is a valid credential for delegating from a token
    # the caller holds (SPEC.md §6.3), and for nothing else.

    def _held_token(self, stub):
        resp = stub.IssueToken(
            anip_pb2.IssueTokenRequest(subject="agent:test-agent", scope=["echo"], capability="echo"),
            metadata=_auth_metadata("test-api-key"),
        )
        assert resp.issued is True
        return resp

    def test_holder_delegates_using_its_token_as_credential(self, stub):
        held = self._held_token(stub)
        resp = stub.IssueToken(
            anip_pb2.IssueTokenRequest(subject="agent:sub-agent", scope=["echo"], capability="echo",
                                       parent_token=held.token_id),
            metadata=_auth_metadata(held.token),
        )
        assert resp.issued is True

    def test_token_credential_cannot_issue_a_root_token(self, stub):
        held = self._held_token(stub)
        resp = stub.IssueToken(
            anip_pb2.IssueTokenRequest(subject="agent:test-agent", scope=["echo", "anything.else"],
                                       capability="echo"),
            metadata=_auth_metadata(held.token),
        )
        assert resp.issued is False, "a delegation token was accepted as credential for root issuance"
        assert resp.failure.type == "insufficient_authority"


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

    def test_invoke_carries_requested_effects(self, stub):
        token = _issue_token(stub)
        resp = stub.Invoke(
            anip_pb2.InvokeRequest(
                capability="echo",
                parameters_json=json.dumps({"message": "effects"}),
                requested_effects=["data.read", "content.summary"],
            ),
            metadata=_auth_metadata(token),
        )
        assert resp.success is True
        result = json.loads(resp.result_json)
        assert result["requested_effects"] == ["data.read", "content.summary"]

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

    def test_approval_grant_flow_preserves_failure_context_and_continuation(self, approval_stub):
        requester = _issue_capability_token(
            approval_stub, scope=["finance.write"], capability="transfer_funds",
        )
        first = approval_stub.Invoke(
            anip_pb2.InvokeRequest(
                capability="transfer_funds",
                parameters_json=json.dumps({"amount": 50000, "to_account": "x"}),
            ),
            metadata=_auth_metadata(requester),
        )
        assert first.success is False
        assert first.failure.type == "approval_required"
        context_data = json.loads(first.failure.context_json)
        request_id = context_data["approval_required"]["approval_request_id"]
        assert request_id

        approver = _issue_capability_token(
            approval_stub, scope=["finance.write", "approver:*"], capability="transfer_funds",
        )
        grant_resp = approval_stub.IssueApprovalGrant(
            anip_pb2.IssueApprovalGrantRequest(
                approval_request_id=request_id,
                grant_type="one_time",
            ),
            metadata=_auth_metadata(approver),
        )
        assert grant_resp.success is True
        grant = json.loads(grant_resp.grant_json)
        grant_id = grant["grant_id"]

        second = approval_stub.Invoke(
            anip_pb2.InvokeRequest(
                capability="transfer_funds",
                parameters_json=json.dumps({"amount": 50000, "to_account": "x"}),
                approval_grant=grant_id,
            ),
            metadata=_auth_metadata(requester),
        )
        assert second.success is False

        third = approval_stub.Invoke(
            anip_pb2.InvokeRequest(
                capability="transfer_funds",
                parameters_json=json.dumps({"amount": 50000, "to_account": "x"}),
                approval_grant=grant_id,
            ),
            metadata=_auth_metadata(requester),
        )
        assert third.success is False
        assert third.failure.type == "grant_consumed"

    @pytest.mark.parametrize("grant", ["", "   "], ids=["empty", "whitespace"])
    def test_supplied_blank_grant_is_not_found(self, approval_stub, grant):
        """proto3 ``optional``: an empty approval_grant is present, so it is a
        supplied grant that names none (SPEC.md §4.8), as over HTTP."""
        requester = _issue_capability_token(
            approval_stub, scope=["finance.write"], capability="transfer_funds",
        )
        for amount in (50000, 5):
            request = anip_pb2.InvokeRequest(
                capability="transfer_funds",
                parameters_json=json.dumps({"amount": amount, "to_account": "x"}),
                approval_grant=grant,
            )
            assert request.HasField("approval_grant")
            resp = approval_stub.Invoke(request, metadata=_auth_metadata(requester))
            assert resp.success is False
            assert resp.failure.type == "grant_not_found"

            events = list(approval_stub.InvokeStream(request, metadata=_auth_metadata(requester)))
            assert events[-1].WhichOneof("event") == "failed", events
            assert events[-1].failed.failure.type == "grant_not_found"

    def test_absent_grant_is_no_grant(self, approval_stub):
        requester = _issue_capability_token(
            approval_stub, scope=["finance.write"], capability="transfer_funds",
        )
        request = anip_pb2.InvokeRequest(
            capability="transfer_funds",
            parameters_json=json.dumps({"amount": 50000, "to_account": "x"}),
        )
        assert not request.HasField("approval_grant")
        resp = approval_stub.Invoke(request, metadata=_auth_metadata(requester))
        assert resp.failure.type == "approval_required"

    def test_one_time_grant_request_for_more_than_one_use_is_invalid(self, approval_stub):
        """A one_time grant allows max_uses 1 only; asking for more is
        refused rather than lowered, and the request stays pending."""
        requester = _issue_capability_token(
            approval_stub, scope=["finance.write"], capability="transfer_funds",
        )
        first = approval_stub.Invoke(
            anip_pb2.InvokeRequest(
                capability="transfer_funds",
                parameters_json=json.dumps({"amount": 50000, "to_account": "x"}),
            ),
            metadata=_auth_metadata(requester),
        )
        request_id = json.loads(first.failure.context_json)["approval_required"]["approval_request_id"]
        approver = _issue_capability_token(
            approval_stub, scope=["finance.write", "approver:*"], capability="transfer_funds",
        )

        refused = approval_stub.IssueApprovalGrant(
            anip_pb2.IssueApprovalGrantRequest(
                approval_request_id=request_id, grant_type="one_time", max_uses=2,
            ),
            metadata=_auth_metadata(approver),
        )
        assert refused.success is False
        assert refused.failure.type == "invalid_parameters"

        accepted = approval_stub.IssueApprovalGrant(
            anip_pb2.IssueApprovalGrantRequest(
                approval_request_id=request_id, grant_type="one_time", max_uses=1,
            ),
            metadata=_auth_metadata(approver),
        )
        assert accepted.success is True


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


class TestParameterValidation:
    """SPEC.md §6.3: the failure is in the response message, like any other."""

    RESOLUTION = {
        "action": "retry_now",
        "recovery_class": "retry_now",
        "requires": "parameters that match the capability's declared inputs",
    }

    def test_invoke_missing_required_input(self, stub):
        token = _issue_token(stub)
        resp = stub.Invoke(
            anip_pb2.InvokeRequest(
                capability="echo",
                parameters_json=json.dumps({}),
                client_reference_id="ref-val",
            ),
            metadata=_auth_metadata(token),
        )
        assert resp.success is False
        assert resp.invocation_id.startswith("inv-")
        assert resp.client_reference_id == "ref-val"
        assert resp.result_json == ""
        assert resp.failure.type == "invalid_parameters"
        assert resp.failure.detail == "echo is missing required input(s): message"
        assert json.loads(resp.failure.resolution_json) == self.RESOLUTION
        assert resp.failure.retry is False

    def test_invoke_without_parameters(self, stub):
        token = _issue_token(stub)
        resp = stub.Invoke(
            anip_pb2.InvokeRequest(capability="echo"), metadata=_auth_metadata(token))
        assert resp.success is False
        assert resp.failure.type == "invalid_parameters"
        assert resp.failure.detail == "echo is missing required input(s): message"

    def test_invoke_wrong_type(self, stub):
        token = _issue_token(stub)
        resp = stub.Invoke(
            anip_pb2.InvokeRequest(
                capability="echo", parameters_json=json.dumps({"message": ["a"]})),
            metadata=_auth_metadata(token),
        )
        assert resp.success is False
        assert resp.failure.type == "invalid_parameters"
        assert resp.failure.detail == (
            "echo has invalid input(s): 'message' must be string, got array")
        assert json.loads(resp.failure.resolution_json) == self.RESOLUTION

    def test_invoke_stream_missing_required_input(self, stub):
        token = _issue_token(stub)
        events = list(stub.InvokeStream(
            anip_pb2.InvokeRequest(capability="echo", parameters_json=json.dumps({})),
            metadata=_auth_metadata(token),
        ))
        assert len(events) == 1
        failed = events[0].failed
        assert events[0].HasField("failed")
        assert failed.invocation_id.startswith("inv-")
        assert failed.failure.type == "invalid_parameters"
        assert failed.failure.detail == "echo is missing required input(s): message"
        assert json.loads(failed.failure.resolution_json) == self.RESOLUTION
        assert failed.failure.retry is False

    @pytest.mark.parametrize("parameters_json", ['{"message": ', "[1, 2]", '"text"'])
    def test_parameters_that_are_not_a_json_object(self, stub, parameters_json):
        token = _issue_token(stub)
        request = anip_pb2.InvokeRequest(capability="echo", parameters_json=parameters_json)

        resp = stub.Invoke(request, metadata=_auth_metadata(token))
        assert resp.success is False
        assert resp.failure.type == "invalid_parameters"
        assert json.loads(resp.failure.resolution_json)["action"] == "retry_now"
        assert resp.failure.retry is False

        events = list(stub.InvokeStream(request, metadata=_auth_metadata(token)))
        assert len(events) == 1 and events[0].HasField("failed")
        assert events[0].failed.failure.type == "invalid_parameters"
        assert json.loads(events[0].failed.failure.resolution_json)["action"] == "retry_now"

    def test_malformed_grant_request_carries_the_resolution(self, approval_stub):
        approver = _issue_capability_token(
            approval_stub, scope=["approver:transfer_funds"], capability="transfer_funds",
        )
        resp = approval_stub.IssueApprovalGrant(
            anip_pb2.IssueApprovalGrantRequest(grant_type="one_time"),
            metadata=_auth_metadata(approver),
        )
        assert resp.success is False
        assert resp.failure.type == "invalid_parameters"
        resolution = json.loads(resp.failure.resolution_json)
        assert resolution["action"] == "retry_now"
        assert resolution["recovery_class"] == "retry_now"
        assert resp.failure.retry is False


class TestStreamingPreHandlerChecks:
    """InvokeStream is refused before the handler for the same reasons as Invoke."""

    def _both(self, stub, token, **request):
        unary = stub.Invoke(anip_pb2.InvokeRequest(**request), metadata=_auth_metadata(token))
        events = list(stub.InvokeStream(
            anip_pb2.InvokeRequest(**request), metadata=_auth_metadata(token)))
        assert unary.success is False
        assert len(events) == 1 and events[0].HasField("failed"), events
        streamed = events[0].failed
        assert streamed.failure.type == unary.failure.type
        assert streamed.failure.detail == unary.failure.detail
        assert streamed.failure.resolution_json == unary.failure.resolution_json
        assert streamed.invocation_id.startswith("inv-")
        return unary.failure.type

    def test_unknown_approval_grant(self, stub):
        token = _issue_token(stub)
        assert self._both(
            stub, token, capability="echo",
            parameters_json=json.dumps({"message": "hello"}),
            approval_grant="grant_000000000000",
        ) == "grant_not_found"

    def test_insufficient_scope(self, stub):
        token = _issue_capability_token(stub, scope=["unrelated"], capability="echo")
        assert self._both(
            stub, token, capability="echo", parameters_json=json.dumps({"message": "hello"}),
        ) == "scope_insufficient"

    def test_purpose_mismatch(self, stub):
        token = _issue_capability_token(stub, scope=["echo"], capability="something_else")
        assert self._both(
            stub, token, capability="echo", parameters_json=json.dumps({"message": "hello"}),
        ) == "purpose_mismatch"

    def test_parameter_validation(self, stub):
        token = _issue_token(stub)
        assert self._both(
            stub, token, capability="echo", parameters_json=json.dumps({}),
        ) == "invalid_parameters"


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


class TestServeGrpcLifecycle:
    """Test that serve_grpc properly manages the ANIP service lifecycle."""

    def test_serve_grpc_starts_and_stops(self):
        """serve_grpc should start the ANIP service on a persistent event loop
        and shut it down cleanly when the gRPC server stops."""
        import threading
        import time
        from anip_grpc.server import serve_grpc

        service = ANIPService(
            service_id="test-lifecycle",
            capabilities=[
                Capability(
                    declaration=CapabilityDeclaration(
                        name="echo",
                        description="Echo",
                        contract_version="1.0",
                        inputs=[CapabilityInput(name="msg", type="string", description="m")],
                        output=CapabilityOutput(type="object", fields=["msg"]),
                        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                        minimum_scope=["test"],
                    ),
                    handler=lambda ctx, params: {"msg": params.get("msg", "")},
                ),
            ],
            storage=":memory:",
            authenticate=lambda b: "user@test.com" if b == "k" else None,
        )

        # Run serve_grpc in a thread so we can stop it
        port = 50099
        server_thread = threading.Thread(target=serve_grpc, args=(service, port), daemon=True)
        server_thread.start()
        time.sleep(1)  # Wait for startup

        # Verify the gRPC server is serving
        channel = grpc.insecure_channel(f"localhost:{port}")
        stub = anip_pb2_grpc.AnipServiceStub(channel)
        resp = stub.Discovery(anip_pb2.DiscoveryRequest())
        data = json.loads(resp.json)
        assert data["anip_discovery"]["protocol"] == PROTOCOL_VERSION

        # Verify token issuance works (proves async service is alive)
        tok = stub.IssueToken(
            anip_pb2.IssueTokenRequest(subject="a", scope=["test"], capability="echo"),
            metadata=[("authorization", "Bearer k")],
        )
        assert tok.issued is True

        channel.close()
