"""Tests for the anip-rest package."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anip_rest.translation import generate_routes, generate_openapi_spec, RouteOverride

# Translation tests use the CapabilityDeclaration model directly
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    SideEffect, SideEffectType,
)

GREET_DECL = CapabilityDeclaration(
    name="greet",
    description="Say hello",
    inputs=[CapabilityInput(name="name", type="string", required=True, description="Who")],
    output=CapabilityOutput(type="object", fields=["message"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["greet"],
)

BOOK_DECL = CapabilityDeclaration(
    name="book",
    description="Book something",
    inputs=[CapabilityInput(name="item", type="string", required=True, description="What")],
    output=CapabilityOutput(type="object", fields=["booking_id"]),
    side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
    minimum_scope=["book"],
)


class TestTranslation:
    def test_read_capability_generates_get_route(self):
        routes = generate_routes({"greet": GREET_DECL})
        assert routes[0].method == "GET"
        assert routes[0].path == "/api/greet"

    def test_irreversible_capability_generates_post_route(self):
        routes = generate_routes({"book": BOOK_DECL})
        assert routes[0].method == "POST"
        assert routes[0].path == "/api/book"

    def test_route_override(self):
        overrides = {"greet": RouteOverride(path="/api/hello", method="POST")}
        routes = generate_routes({"greet": GREET_DECL}, overrides)
        assert routes[0].method == "POST"
        assert routes[0].path == "/api/hello"

    def test_openapi_spec_structure(self):
        routes = generate_routes({"greet": GREET_DECL})
        spec = generate_openapi_spec("test-service", routes)
        assert spec["openapi"] == "3.1.0"
        assert "/api/greet" in spec["paths"]


class TestMountIntegration:
    """Integration tests using a real ANIPService + FastAPI TestClient."""

    API_KEY = "test-key"

    @pytest.fixture
    def client(self):
        """Create service, mount ANIP + REST routes, return TestClient.

        mount_anip() wires FastAPI startup/shutdown hooks for service lifecycle.
        TestClient triggers them automatically.
        """
        from anip_service import ANIPService, Capability
        from anip_fastapi import mount_anip
        from anip_rest import mount_anip_rest

        service = ANIPService(
            service_id="test-rest",
            capabilities=[
                Capability(
                    declaration=GREET_DECL,
                    handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
                ),
                Capability(
                    declaration=BOOK_DECL,
                    handler=lambda ctx, params: {"booking_id": "BK-001", "item": params["item"]},
                ),
            ],
            storage=":memory:",
            authenticate=lambda bearer: "test-agent" if bearer == self.API_KEY else None,
        )
        app = FastAPI()
        mount_anip(app, service)       # owns lifecycle via app hooks
        mount_anip_rest(app, service)  # adds REST routes only
        return TestClient(app)

    def test_get_read_capability(self, client):
        resp = client.get("/api/greet", params={"name": "World"},
                          headers={"Authorization": f"Bearer {self.API_KEY}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["result"]["message"] == "Hello, World!"

    def test_post_write_capability(self, client):
        resp = client.post("/api/book",
                           json={"item": "flight"},
                           headers={"Authorization": f"Bearer {self.API_KEY}"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_missing_auth_returns_401(self, client):
        resp = client.get("/api/greet", params={"name": "World"})
        assert resp.status_code == 401
        assert resp.json()["failure"]["type"] == "authentication_required"

    def test_invalid_jwt_returns_structured_error(self, client):
        resp = client.get("/api/greet", params={"name": "World"},
                          headers={"Authorization": "Bearer garbage-not-a-jwt"})
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "invalid_token"

    def test_openapi_spec(self, client):
        resp = client.get("/rest/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert spec["openapi"] == "3.1.0"
        assert "/api/greet" in spec["paths"]

    def test_docs_html(self, client):
        resp = client.get("/rest/docs")
        assert resp.status_code == 200
        assert "swagger-ui" in resp.text
