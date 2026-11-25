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
        assert to_camel_case("gtm.pipeline_summary") == "gtmPipelineSummary"

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

    def test_sanitizes_dotted_capability_names(self):
        dotted_decl = CapabilityDeclaration(
            name="gtm.pipeline_summary",
            description="Pipeline summary",
            inputs=[CapabilityInput(name="quarter", type="string", required=True, description="Quarter")],
            output=CapabilityOutput(type="object", fields=["summary"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["gtm.pipeline.summary"],
        )
        sdl = generate_schema({"gtm.pipeline_summary": dotted_decl})
        assert "gtmPipelineSummary(quarter: String!): GtmPipelineSummaryResult!" in sdl
        assert "type GtmPipelineSummaryResult" in sdl

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


class TestParameterValidation:
    """SPEC.md §6.3 parameter validation as seen through the GraphQL binding."""

    API_KEY = "test-key"

    @pytest.fixture
    def harness(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from anip_service import ANIPService, Capability
        from anip_fastapi import mount_anip
        from anip_graphql import mount_anip_graphql

        calls: list = []

        def handler(ctx, params):
            calls.append(dict(params))
            return {"ok": True}

        declaration = CapabilityDeclaration(
            name="price_order",
            description="Price an order",
            inputs=[
                CapabilityInput(name="item_name", type="string", description="What"),
                CapabilityInput(name="quote", type="object", required=False, description="Quote"),
                CapabilityInput(name="when", type="date", required=False, description="Day"),
            ],
            output=CapabilityOutput(type="object", fields=["ok"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["price"],
        )
        service = ANIPService(
            service_id="test-graphql-validation",
            capabilities=[
                Capability(declaration=declaration, handler=handler),
                # The binding needs at least one mutation to build its schema.
                Capability(declaration=BOOK_DECL, handler=lambda ctx, params: {"booking_id": "BK-001"}),
            ],
            authenticate=lambda bearer: "test-agent" if bearer == self.API_KEY else None,
        )
        app = FastAPI()
        mount_anip(app, service)
        mount_anip_graphql(app, service)
        return TestClient(app), calls

    FIELDS = "success result failure { type detail retry resolution { action recoveryClass requires } }"

    def _query(self, client, arguments: str):
        return client.post(
            "/graphql",
            json={"query": "{ priceOrder%s { %s } }" % (arguments, self.FIELDS)},
            headers={"Authorization": f"Bearer {self.API_KEY}"},
        )

    def test_valid_call_reaches_the_capability(self, harness):
        client, calls = harness

        data = self._query(client, '(itemName: "x", quote: {id: "q1"})').json()

        assert data["data"]["priceOrder"]["success"] is True, data
        assert calls == [{"item_name": "x", "quote": {"id": "q1"}}]

    def test_wrong_type_is_an_invalid_parameters_failure(self, harness):
        """``object`` is the JSON scalar in the schema, so GraphQL lets any
        value through and the service refuses it."""
        client, calls = harness

        resp = self._query(client, '(itemName: "x", quote: "q1")')

        assert resp.status_code == 200
        result = resp.json()["data"]["priceOrder"]
        assert result["success"] is False
        assert result["result"] is None
        assert result["failure"] == {
            "type": "invalid_parameters",
            "detail": "price_order has invalid input(s): 'quote' must be object, got string",
            "retry": False,
            "resolution": {
                "action": "retry_now",
                "recoveryClass": "retry_now",
                "requires": "parameters that match the capability's declared inputs",
            },
        }
        assert calls == []

    @pytest.mark.parametrize("arguments", ['(quote: {id: "q1"})', "(itemName: null)", ""])
    def test_missing_required_input_is_refused_by_the_schema(self, harness, arguments):
        """A required input is a non-null argument (``String!``): GraphQL
        refuses the document before the resolver, as a GraphQL error."""
        client, calls = harness

        resp = self._query(client, arguments)

        body = resp.json()
        assert resp.status_code == 400
        assert body.get("data") is None
        message = body["errors"][0]["message"]
        assert "itemName" in message or "String!" in message
        assert calls == []


class TestOnMissingInputs:
    """SPEC.md §4.10: an input that declares ``resolution.on_missing`` is left
    to the service when absent, so the schema does not make it non-null."""

    API_KEY = "test-key"

    DECL = CapabilityDeclaration(
        name="region_report",
        description="Report for a region",
        inputs=[
            CapabilityInput(
                name="region", type="string", required=True, description="Region",
                resolution={"mode": "clarify", "on_missing": "clarify"}),
            CapabilityInput(
                name="quarter", type="string", required=True, description="Quarter",
                resolution={"mode": "clarify"}),
        ],
        output=CapabilityOutput(type="object", fields=["ok"]),
        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
        minimum_scope=["report"],
    )

    def test_schema_argument_is_nullable_only_with_on_missing(self):
        sdl = generate_schema({"region_report": self.DECL})
        assert "regionReport(region: String, quarter: String!)" in sdl

    def test_missing_on_missing_input_reaches_the_capability(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from anip_service import ANIPService, Capability
        from anip_fastapi import mount_anip
        from anip_graphql import mount_anip_graphql

        calls: list = []

        def handler(ctx, params):
            calls.append(dict(params))
            return {"ok": True}

        service = ANIPService(
            service_id="test-graphql-on-missing",
            capabilities=[
                Capability(declaration=self.DECL, handler=handler),
                Capability(declaration=BOOK_DECL, handler=lambda ctx, params: {"booking_id": "BK-001"}),
            ],
            authenticate=lambda bearer: "test-agent" if bearer == self.API_KEY else None,
        )
        app = FastAPI()
        mount_anip(app, service)
        mount_anip_graphql(app, service)
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {self.API_KEY}"}

        resp = client.post(
            "/graphql",
            json={"query": '{ regionReport(quarter: "Q1") { success failure { type detail } } }'},
            headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["regionReport"]["success"] is True, resp.text
        assert calls == [{"quarter": "Q1"}]

        refused = client.post(
            "/graphql",
            json={"query": '{ regionReport(region: "eu") { success } }'},
            headers=headers)
        assert refused.status_code == 400
        assert "quarter" in refused.json()["errors"][0]["message"]
