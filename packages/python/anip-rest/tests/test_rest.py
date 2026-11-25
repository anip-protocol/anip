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


class TestParameterValidation:
    """SPEC.md §6.3 parameter validation as seen through the REST binding."""

    API_KEY = "test-key"
    RESOLUTION = {
        "action": "retry_now",
        "recovery_class": "retry_now",
        "requires": "parameters that match the capability's declared inputs",
    }

    @pytest.fixture
    def harness(self):
        from anip_service import ANIPService, Capability
        from anip_fastapi import mount_anip
        from anip_rest import mount_anip_rest

        calls: list = []

        def handler(ctx, params):
            calls.append(dict(params))
            return {"ok": True}

        def declaration(name, side_effect):
            return CapabilityDeclaration(
                name=name,
                description="Count things",
                inputs=[
                    CapabilityInput(name="item", type="string", description="What"),
                    CapabilityInput(name="count", type="integer", required=False, description="How many"),
                    CapabilityInput(name="urgent", type="boolean", required=False, description="Urgent"),
                    CapabilityInput(name="weight", type="number", required=False, description="Weight"),
                ],
                output=CapabilityOutput(type="object", fields=["ok"]),
                side_effect=side_effect,
                minimum_scope=["count"],
            )

        service = ANIPService(
            service_id="test-rest-validation",
            capabilities=[
                Capability(
                    declaration=declaration(
                        "count_items",
                        SideEffect(type=SideEffectType.READ, rollback_window="not_applicable")),
                    handler=handler,
                ),
                Capability(
                    declaration=declaration(
                        "order_items",
                        SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none")),
                    handler=handler,
                ),
            ],
            storage=":memory:",
            authenticate=lambda bearer: "test-agent" if bearer == self.API_KEY else None,
        )
        app = FastAPI()
        mount_anip(app, service)
        mount_anip_rest(app, service)
        return TestClient(app), calls

    def _get(self, client, params):
        return client.get("/api/count_items", params=params,
                          headers={"Authorization": f"Bearer {self.API_KEY}"})

    def _post(self, client, body):
        return client.post("/api/order_items", json=body,
                           headers={"Authorization": f"Bearer {self.API_KEY}"})

    def test_get_without_required_input_is_invalid_parameters(self, harness):
        client, calls = harness

        resp = self._get(client, {"count": "2"})
        data = resp.json()

        assert resp.status_code == 400
        assert data["success"] is False
        assert data["failure"] == {
            "type": "invalid_parameters",
            "detail": "count_items is missing required input(s): item",
            "resolution": self.RESOLUTION,
            "retry": False,
        }
        assert data["invocation_id"].startswith("inv-")
        assert calls == []

    def test_post_without_required_input_is_invalid_parameters(self, harness):
        client, calls = harness

        resp = self._post(client, {"count": 2})
        data = resp.json()

        assert resp.status_code == 400
        assert data["failure"] == {
            "type": "invalid_parameters",
            "detail": "order_items is missing required input(s): item",
            "resolution": self.RESOLUTION,
            "retry": False,
        }
        assert calls == []

    def test_post_with_wrong_type_is_invalid_parameters(self, harness):
        client, calls = harness

        resp = self._post(client, {"item": "x", "count": "two"})
        data = resp.json()

        assert resp.status_code == 400
        assert data["failure"]["type"] == "invalid_parameters"
        assert data["failure"]["detail"] == (
            "order_items has invalid input(s): 'count' must be integer, got string")
        assert calls == []

    @pytest.mark.parametrize("name,value,declared", [
        ("count", "two", "integer"),
        ("count", "1.5", "integer"),
        ("urgent", "maybe", "boolean"),
        ("weight", "heavy", "number"),
    ])
    def test_query_value_that_is_not_of_the_declared_type_is_invalid_parameters(
        self, harness, name, value, declared
    ):
        """A query string that cannot be read as the declared type is refused
        by the service, not converted to something else and not a 500."""
        client, calls = harness

        resp = self._get(client, {"item": "x", name: value})
        data = resp.json()

        assert resp.status_code == 400
        assert data["failure"]["type"] == "invalid_parameters"
        received = "number" if value == "1.5" else "string"
        assert data["failure"]["detail"] == (
            f"count_items has invalid input(s): '{name}' must be {declared}, got {received}")
        assert calls == []

    def test_query_values_are_converted_to_the_declared_types(self, harness):
        client, calls = harness

        resp = self._get(client, {
            "item": "x", "count": "3", "urgent": "false", "weight": "1.5"})

        assert resp.json()["success"] is True, resp.text
        assert calls == [{"item": "x", "count": 3, "urgent": False, "weight": 1.5}]

    def test_integral_query_value_with_a_fraction_part_is_an_integer(self, harness):
        client, calls = harness

        resp = self._get(client, {"item": "x", "count": "3.0"})

        assert resp.json()["success"] is True, resp.text
        assert calls[0]["count"] == 3


class TestHttpStatus:
    """SPEC.md §6.3 "HTTP Status Codes": the REST binding answers a failed
    invocation with the status of its failure type, like the protocol binding."""

    API_KEY = "test-key"

    @pytest.fixture
    def client(self):
        from anip_service import ANIPError, ANIPService, Capability
        from anip_fastapi import mount_anip
        from anip_rest import mount_anip_rest

        def fail(ctx, params):
            raise ANIPError(
                params["type"], "provoked",
                resolution={"action": "contact_service_owner", "recovery_class": "terminal"})

        def declaration(name, side_effect):
            return CapabilityDeclaration(
                name=name,
                description="Fail on request",
                inputs=[CapabilityInput(name="type", type="string", description="Failure type")],
                output=CapabilityOutput(type="object", fields=[]),
                side_effect=side_effect,
                minimum_scope=["fail"],
            )

        service = ANIPService(
            service_id="test-rest-status",
            capabilities=[
                Capability(
                    declaration=declaration(
                        "fail_read",
                        SideEffect(type=SideEffectType.READ, rollback_window="not_applicable")),
                    handler=fail,
                ),
                Capability(
                    declaration=declaration(
                        "fail_write",
                        SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none")),
                    handler=fail,
                ),
                Capability(declaration=GREET_DECL, handler=lambda ctx, params: {"message": "hi"}),
            ],
            storage=":memory:",
            authenticate=lambda bearer: "test-agent" if bearer == self.API_KEY else None,
        )
        app = FastAPI()
        mount_anip(app, service)
        mount_anip_rest(app, service)
        return TestClient(app, raise_server_exceptions=False)

    def _headers(self):
        return {"Authorization": f"Bearer {self.API_KEY}"}

    def _types():
        from anip_core import FAILURE_STATUS_CODES
        return sorted(set(FAILURE_STATUS_CODES) - {"approval_required"}) + ["seat_map_unavailable"]

    @pytest.mark.parametrize("failure_type", _types())
    def test_failed_invocation_answers_with_the_status_of_its_type(self, client, failure_type):
        from anip_core import failure_status_code

        get = client.get("/api/fail_read", params={"type": failure_type}, headers=self._headers())
        post = client.post("/api/fail_write", json={"type": failure_type}, headers=self._headers())

        for resp in (get, post):
            assert resp.json()["success"] is False
            assert resp.json()["failure"]["type"] == failure_type
            assert resp.status_code == failure_status_code(failure_type)

    def test_token_without_the_scope_is_403(self, client):
        token = client.post(
            "/anip/tokens", json={"scope": ["fail"], "capability": "greet"},
            headers=self._headers()).json()["token"]

        resp = client.get("/api/greet", params={"name": "World"},
                          headers={"Authorization": f"Bearer {token}"})

        assert resp.json()["failure"]["type"] in ("scope_insufficient", "insufficient_authority")
        assert resp.status_code == 403

    def test_token_for_another_capability_is_403(self, client):
        token = client.post(
            "/anip/tokens", json={"scope": ["fail", "greet"], "capability": "fail_read"},
            headers=self._headers()).json()["token"]

        resp = client.get("/api/greet", params={"name": "World"},
                          headers={"Authorization": f"Bearer {token}"})

        assert resp.json()["failure"]["type"] == "purpose_mismatch"
        assert resp.status_code == 403

    @pytest.mark.parametrize("content", [b'{"type": ', b"", b"not json", b"[1, 2]", b'"text"', b"null"])
    def test_body_that_is_not_a_json_object_is_invalid_parameters(self, client, content):
        resp = client.post(
            "/api/fail_write", content=content,
            headers={**self._headers(), "Content-Type": "application/json"})

        assert resp.status_code == 400, resp.text
        failure = resp.json()["failure"]
        assert resp.json()["success"] is False
        assert failure["type"] == "invalid_parameters"
        assert failure["resolution"]["action"] == "retry_now"
        assert failure["resolution"]["recovery_class"] == "retry_now"
        assert failure["retry"] is False

    def test_credential_is_checked_before_the_body(self, client):
        resp = client.post(
            "/api/fail_write", content=b'{"type": ', headers={"Content-Type": "application/json"})

        assert resp.status_code == 401
        assert resp.json()["failure"]["type"] == "authentication_required"

    def test_binding_has_no_status_table_of_its_own(self):
        import anip_rest.routes as routes
        from anip_core import failure_status_code

        assert not hasattr(routes, "_FAILURE_STATUS")
        assert routes.failure_status_code is failure_status_code
