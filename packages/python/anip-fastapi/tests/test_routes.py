import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from anip_service import ANIPService, Capability, ANIPError
from anip_fastapi import mount_anip
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, ResponseMode, SideEffect, SideEffectType


def _greet_cap():
    return Capability(
        declaration=CapabilityDeclaration(
            name="greet",
            description="Say hello",
            contract_version="1.0",
            inputs=[CapabilityInput(name="name", type="string", required=True, description="Who")],
            output=CapabilityOutput(type="object", fields=["message"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["greet"],
        ),
        handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
    )


API_KEY = "test-key-123"


@pytest.fixture
def client():
    service = ANIPService(
        service_id="test-service",
        capabilities=[_greet_cap()],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )
    app = FastAPI()
    mount_anip(app, service)
    return TestClient(app)


class TestDiscoveryRoutes:
    def test_well_known_anip(self, client):
        resp = client.get("/.well-known/anip")
        assert resp.status_code == 200
        data = resp.json()
        assert "anip_discovery" in data
        assert "greet" in data["anip_discovery"]["capabilities"]

    def test_jwks(self, client):
        resp = client.get("/.well-known/jwks.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data

    def test_manifest(self, client):
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200
        assert "X-ANIP-Signature" in resp.headers

    def test_checkpoints_list(self, client):
        resp = client.get("/anip/checkpoints")
        assert resp.status_code == 200
        assert "checkpoints" in resp.json()

    def test_checkpoint_not_found(self, client):
        resp = client.get("/anip/checkpoints/ckpt-nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "not_found"


class TestInvokeRoutes:
    def _get_token(self, client):
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["greet"], "capability": "greet"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert resp.status_code == 200
        return resp.json()["token"]

    def test_invoke_response_has_invocation_id(self, client):
        """Invoke response should include invocation_id."""
        token = self._get_token(client)
        resp = client.post(
            "/anip/invoke/greet",
            json={"parameters": {"name": "World"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["invocation_id"].startswith("inv-")

    def test_invoke_passes_client_reference_id(self, client):
        """Invoke should echo back client_reference_id when provided."""
        token = self._get_token(client)
        resp = client.post(
            "/anip/invoke/greet",
            json={
                "parameters": {"name": "World"},
                "client_reference_id": "my-ref-42",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["client_reference_id"] == "my-ref-42"


class TestPermissionsRoute:
    def _get_token(self, client, scope=None):
        resp = client.post(
            "/anip/tokens",
            json={"scope": scope or ["greet"], "capability": "greet"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert resp.status_code == 200
        return resp.json()["token"]

    def test_permissions_returns_available(self, client):
        token = self._get_token(client)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "restricted" in data
        assert "denied" in data
        cap_names = [c["capability"] for c in data["available"]]
        assert "greet" in cap_names

    def test_permissions_shows_restricted_for_missing_scope(self, client):
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["unrelated"], "capability": "greet"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        restricted_names = [c["capability"] for c in data["restricted"]]
        assert "greet" in restricted_names


class TestAuditRoute:
    def test_audit_returns_entries(self, client):
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["greet"], "capability": "greet"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        token = resp.json()["token"]
        client.post(
            "/anip/invoke/greet",
            json={"parameters": {"name": "World"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.post(
            "/anip/audit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "count" in data
        assert data["count"] >= 1

    def test_audit_with_capability_filter(self, client):
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["greet"], "capability": "greet"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        token = resp.json()["token"]
        client.post(
            "/anip/invoke/greet",
            json={"parameters": {"name": "World"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = client.post(
            "/anip/audit?capability=greet",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability_filter"] == "greet"


def _streaming_cap():
    async def handler(ctx, params):
        await ctx.emit_progress({"step": 1, "status": "working"})
        return {"answer": 42}

    return Capability(
        declaration=CapabilityDeclaration(
            name="analyze",
            description="Analyze something",
            contract_version="1.0",
            inputs=[CapabilityInput(name="x", type="string", required=True, description="input")],
            output=CapabilityOutput(type="object", fields=["answer"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["analyze"],
            response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
        ),
        handler=handler,
    )


@pytest.fixture
def streaming_client():
    service = ANIPService(
        service_id="test-service",
        capabilities=[_greet_cap(), _streaming_cap()],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )
    app = FastAPI()
    mount_anip(app, service)
    return TestClient(app)


class TestStreamingRoutes:
    def test_streaming_returns_sse(self, streaming_client):
        """POST with stream:true should return text/event-stream."""
        resp = streaming_client.post(
            "/anip/tokens",
            json={"subject": "test-agent", "scope": ["analyze"], "capability": "analyze"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert resp.status_code == 200
        jwt_str = resp.json()["token"]

        resp = streaming_client.post(
            "/anip/invoke/analyze",
            json={"parameters": {"x": "test"}, "stream": True},
            headers={"Authorization": f"Bearer {jwt_str}"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        assert "event: progress" in body
        assert "event: completed" in body
        assert '"answer": 42' in body or '"answer":42' in body

    def test_streaming_rejected_for_unary_cap(self, streaming_client):
        """stream:true on a unary-only capability should fail."""
        resp = streaming_client.post(
            "/anip/tokens",
            json={"subject": "test-agent", "scope": ["greet"], "capability": "greet"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        jwt_str = resp.json()["token"]

        resp = streaming_client.post(
            "/anip/invoke/greet",
            json={"parameters": {"name": "world"}, "stream": True},
            headers={"Authorization": f"Bearer {jwt_str}"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["failure"]["type"] == "streaming_not_supported"


# --- Health endpoint tests ---


@pytest.fixture
def health_client():
    service = ANIPService(
        service_id="test-service",
        capabilities=[_greet_cap()],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )
    app = FastAPI()
    mount_anip(app, service, health_endpoint=True)
    return TestClient(app)


class TestAuthErrors:
    def test_token_endpoint_without_auth_returns_anip_failure(self, client):
        resp = client.post("/anip/tokens", json={"scope": ["greet"]})
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"
        assert data["failure"]["resolution"]["action"] == "provide_credentials"
        assert data["failure"]["retry"] is True

    def test_invoke_without_auth_returns_anip_failure(self, client):
        resp = client.post("/anip/invoke/greet", json={"parameters": {"name": "X"}})
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"
        assert data["failure"]["resolution"]["action"] == "request_new_delegation"
        assert data["failure"]["retry"] is True

    def test_permissions_without_auth_returns_anip_failure(self, client):
        resp = client.post("/anip/permissions")
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"
        assert data["failure"]["resolution"]["action"] == "request_new_delegation"

    def test_audit_without_auth_returns_anip_failure(self, client):
        resp = client.post("/anip/audit")
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"
        assert data["failure"]["resolution"]["action"] == "request_new_delegation"

    def test_invoke_with_invalid_token_returns_structured_error(self, client):
        resp = client.post(
            "/anip/invoke/greet",
            json={"parameters": {"name": "X"}},
            headers={"Authorization": "Bearer not-a-valid-jwt"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "invalid_token"

    def test_permissions_with_invalid_token_returns_structured_error(self, client):
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": "Bearer not-a-valid-jwt"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "invalid_token"


class TestHealthEndpoint:
    def test_health_endpoint_disabled_by_default(self, client):
        resp = client.get("/-/health")
        assert resp.status_code in (404, 405)

    def test_health_endpoint_returns_report(self, health_client):
        resp = health_client.get("/-/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "storage" in data
        assert "retention" in data
