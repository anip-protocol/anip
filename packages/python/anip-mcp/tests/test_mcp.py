"""Tests for the anip-mcp package."""
import pytest

from anip_mcp.translation import capability_to_input_schema, enrich_description
from anip_mcp.routes import _invoke_capability, _translate_response, McpCredentials


GREET_DECLARATION = {
    "name": "greet",
    "description": "Say hello",
    "contract_version": "1.0",
    "inputs": [
        {"name": "name", "type": "string", "required": True, "description": "Who"},
    ],
    "output": {"type": "object", "fields": ["message"]},
    "side_effect": {"type": "read", "rollback_window": "not_applicable"},
    "minimum_scope": ["greet"],
    "response_modes": ["unary"],
}


class TestTranslation:
    def test_input_schema_properties(self):
        schema = capability_to_input_schema(GREET_DECLARATION)
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert schema["properties"]["name"]["type"] == "string"

    def test_input_schema_required(self):
        schema = capability_to_input_schema(GREET_DECLARATION)
        assert "name" in schema["required"]

    def test_enrich_description_read(self):
        desc = enrich_description(GREET_DECLARATION)
        assert "Read-only" in desc
        assert "Delegation scope: greet" in desc

    def test_enrich_description_irreversible(self):
        decl = {
            **GREET_DECLARATION,
            "side_effect": {"type": "irreversible", "rollback_window": "none"},
        }
        desc = enrich_description(decl)
        assert "IRREVERSIBLE" in desc
        assert "No rollback window" in desc


class TestTranslateResponse:
    def test_success_response(self):
        resp = {"success": True, "result": {"message": "Hello!"}}
        text = _translate_response(resp)
        assert "Hello!" in text

    def test_failure_response(self):
        resp = {
            "success": False,
            "failure": {
                "type": "scope_insufficient",
                "detail": "Missing travel.book",
                "resolution": {"action": "request_broader_scope"},
                "retry": False,
            },
        }
        text = _translate_response(resp)
        assert "FAILED: scope_insufficient" in text
        assert "Missing travel.book" in text
        assert "Retryable: no" in text


class TestInvokeCapability:
    """Integration tests using a real ANIPService instance."""

    API_KEY = "test-key"

    @pytest.fixture
    async def service(self):
        """Create and start a test service with a greet capability."""
        from anip_core import (
            CapabilityDeclaration, SideEffect, SideEffectType,
            CapabilityInput, CapabilityOutput,
        )
        from anip_service import ANIPService, Capability

        svc = ANIPService(
            service_id="test-mcp",
            capabilities=[
                Capability(
                    declaration=CapabilityDeclaration(
                        name="greet",
                        description="Say hello",
                        inputs=[CapabilityInput(name="name", type="string", required=True, description="Who")],
                        output=CapabilityOutput(type="object", fields=["message"]),
                        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                        minimum_scope=["greet"],
                    ),
                    handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
                ),
            ],
            storage=":memory:",
            authenticate=lambda bearer: "test-agent" if bearer == self.API_KEY else None,
        )
        await svc.start()
        yield svc
        await svc.shutdown()

    async def test_invoke_with_valid_credentials(self, service):
        creds = McpCredentials(api_key=self.API_KEY, scope=["greet"], subject="test-agent")
        result = await _invoke_capability(service, "greet", {"name": "World"}, creds)
        assert "Hello, World!" in result

    async def test_invoke_with_invalid_credentials(self, service):
        creds = McpCredentials(api_key="wrong-key", scope=["greet"], subject="test")
        result = await _invoke_capability(service, "greet", {"name": "World"}, creds)
        assert "FAILED" in result
        assert "authentication_required" in result
