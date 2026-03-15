import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from anip_service import ANIPService, Capability, ANIPError
from anip_fastapi import mount_anip
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


@pytest.fixture
def client():
    service = ANIPService(
        service_id="test-service",
        capabilities=[_greet_cap()],
        storage=":memory:",
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
