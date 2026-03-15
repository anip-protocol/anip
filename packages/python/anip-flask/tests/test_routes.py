import pytest
from flask import Flask
from anip_service import ANIPService, Capability
from anip_flask import mount_anip
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SideEffect, SideEffectType


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
    app = Flask(__name__)
    service = ANIPService(
        service_id="test-service",
        capabilities=[_greet_cap()],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )
    handle = mount_anip(app, service)
    yield app.test_client()
    handle.stop()


class TestDiscoveryRoutes:
    def test_well_known_anip(self, client):
        resp = client.get("/.well-known/anip")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "anip_discovery" in data
        assert "greet" in data["anip_discovery"]["capabilities"]

    def test_jwks(self, client):
        resp = client.get("/.well-known/jwks.json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "keys" in data

    def test_manifest(self, client):
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200
        assert "X-ANIP-Signature" in resp.headers


class TestCheckpointRoutes:
    def test_checkpoints_list(self, client):
        resp = client.get("/anip/checkpoints")
        assert resp.status_code == 200
        assert "checkpoints" in resp.get_json()

    def test_checkpoint_not_found(self, client):
        resp = client.get("/anip/checkpoints/ckpt-nonexistent")
        assert resp.status_code == 404


class TestTokenRoutes:
    def test_token_without_auth(self, client):
        resp = client.post("/anip/tokens", json={"scope": ["greet"]})
        assert resp.status_code == 401


class TestInvokeRoutes:
    def _get_token(self, client):
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["greet"], "capability": "greet"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert resp.status_code == 200
        return resp.get_json()["token"]

    def test_invoke_success(self, client):
        # First get a token
        token = self._get_token(client)

        # Then invoke
        resp = client.post(
            "/anip/invoke/greet",
            json={"parameters": {"name": "World"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["result"]["message"] == "Hello, World!"

    def test_invoke_response_has_invocation_id(self, client):
        """Invoke response should include invocation_id."""
        token = self._get_token(client)
        resp = client.post(
            "/anip/invoke/greet",
            json={"parameters": {"name": "World"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
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
        data = resp.get_json()
        assert data["success"] is True
        assert data["client_reference_id"] == "my-ref-42"


class TestLifecycle:
    def test_stop(self):
        app = Flask(__name__)
        service = ANIPService(
            service_id="test-service",
            capabilities=[_greet_cap()],
            storage=":memory:",
        )
        handle = mount_anip(app, service)
        handle.stop()  # Should not raise
