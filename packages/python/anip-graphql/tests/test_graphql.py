"""Tests for the anip-graphql package."""
import pytest

from anip_core.models import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    SideEffect, SideEffectType,
)
from anip_graphql.translation import (
    generate_schema, to_camel_case, to_snake_case, build_graphql_response,
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
    name="book_item",
    description="Book something",
    inputs=[CapabilityInput(name="item_name", type="string", required=True, description="What")],
    output=CapabilityOutput(type="object", fields=["booking_id"]),
    side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
    minimum_scope=["book"],
)


class TestCaseConversion:
    def test_to_camel_case(self):
        assert to_camel_case("search_flights") == "searchFlights"
        assert to_camel_case("book") == "book"

    def test_to_snake_case(self):
        assert to_snake_case("searchFlights") == "search_flights"
        assert to_snake_case("itemName") == "item_name"


class TestSDLGeneration:
    def test_generates_query_for_read(self):
        sdl = generate_schema({"greet": GREET_DECL})
        assert "type Query" in sdl
        assert "greet(name: String!): GreetResult!" in sdl

    def test_generates_mutation_for_irreversible(self):
        sdl = generate_schema({"book_item": BOOK_DECL})
        assert "type Mutation" in sdl
        assert "bookItem(itemName: String!): BookItemResult!" in sdl

    def test_includes_directives(self):
        sdl = generate_schema({"greet": GREET_DECL})
        assert "@anipSideEffect" in sdl
        assert "@anipScope" in sdl

    def test_includes_shared_types(self):
        sdl = generate_schema({"greet": GREET_DECL})
        assert "type ANIPFailure" in sdl
        assert "scalar JSON" in sdl


class TestResponseMapping:
    def test_success_response(self):
        result = build_graphql_response({"success": True, "result": {"message": "Hi"}})
        assert result["success"] is True
        assert result["result"]["message"] == "Hi"

    def test_failure_response(self):
        result = build_graphql_response({
            "success": False,
            "failure": {
                "type": "scope_insufficient",
                "detail": "Missing scope",
                "resolution": {"action": "request_scope", "grantable_by": "admin"},
                "retry": False,
            },
        })
        assert result["success"] is False
        assert result["failure"]["type"] == "scope_insufficient"
        assert result["failure"]["resolution"]["grantableBy"] == "admin"

    def test_cost_actual_mapping(self):
        result = build_graphql_response({
            "success": True,
            "result": {},
            "cost_actual": {
                "financial": {"amount": 100, "currency": "USD"},
                "variance_from_estimate": "-5%",
            },
        })
        assert result["costActual"]["financial"]["amount"] == 100
        assert result["costActual"]["varianceFromEstimate"] == "-5%"


class TestMountIntegration:
    """Integration tests using a real ANIPService + FastAPI TestClient."""

    API_KEY = "test-key"

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from anip_service import ANIPService, Capability
        from anip_fastapi import mount_anip
        from anip_graphql import mount_anip_graphql

        service = ANIPService(
            service_id="test-graphql",
            capabilities=[
                Capability(
                    declaration=GREET_DECL,
                    handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
                ),
                Capability(
                    declaration=BOOK_DECL,
                    handler=lambda ctx, params: {"booking_id": "BK-001"},
                ),
            ],
            authenticate=lambda bearer: "test-agent" if bearer == self.API_KEY else None,
        )
        app = FastAPI()
        mount_anip(app, service)          # owns lifecycle via app hooks
        mount_anip_graphql(app, service)  # adds GraphQL routes only
        return TestClient(app)

    def test_query_read_capability(self, client):
        resp = client.post(
            "/graphql",
            json={"query": '{ greet(name: "World") { success result } }'},
            headers={"Authorization": f"Bearer {self.API_KEY}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["greet"]["success"] is True
        assert data["data"]["greet"]["result"]["message"] == "Hello, World!"

    def test_mutation_write_capability(self, client):
        resp = client.post(
            "/graphql",
            json={"query": 'mutation { bookItem(itemName: "x") { success result } }'},
            headers={"Authorization": f"Bearer {self.API_KEY}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["bookItem"]["success"] is True

    def test_query_with_invalid_jwt_returns_invalid_token(self, client):
        resp = client.post(
            "/graphql",
            json={"query": '{ greet(name: "World") { success failure { type } } }'},
            headers={"Authorization": "Bearer garbage-not-a-jwt"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["greet"]["success"] is False
        assert data["data"]["greet"]["failure"]["type"] == "invalid_token"

    def test_query_without_auth_returns_failure(self, client):
        resp = client.post(
            "/graphql",
            json={"query": '{ greet(name: "World") { success failure { type } } }'},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["greet"]["success"] is False
        assert data["data"]["greet"]["failure"]["type"] == "authentication_required"

    def test_schema_endpoint(self, client):
        resp = client.get("/schema.graphql")
        assert resp.status_code == 200
        assert "type Query" in resp.text
