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


class TestMountIntegration:
    """Integration tests exercising mount_anip_mcp on a real MCP Server."""

    API_KEY = "test-key"

    @pytest.fixture
    async def mounted(self):
        from anip_core import (
            CapabilityDeclaration, SideEffect, SideEffectType,
            CapabilityInput, CapabilityOutput,
        )
        from anip_service import ANIPService, Capability
        from mcp.server.lowlevel import Server
        from anip_mcp import mount_anip_mcp, McpCredentials

        svc = ANIPService(
            service_id="test-mcp-mount",
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
        server = Server("test-mcp-server")
        creds = McpCredentials(api_key=self.API_KEY, scope=["greet"], subject="test-agent")
        lifecycle = await mount_anip_mcp(server, svc, credentials=creds)
        yield server, lifecycle
        await lifecycle.shutdown()

    async def test_list_tools_returns_the_capabilities(self, mounted):
        """The handler mounted for tools/list returns the service's capabilities."""
        server, _ = mounted
        from mcp.types import PaginatedRequestParams
        entry = server.get_request_handler("tools/list")
        assert entry is not None, "no tools/list handler was mounted"

        result = await entry.handler(None, PaginatedRequestParams())

        assert [tool.name for tool in result.tools] == ["greet"]

    async def test_call_tool_invokes_the_capability(self, mounted):
        """The handler mounted for tools/call invokes with the mount credentials."""
        server, _ = mounted
        from mcp.types import CallToolRequestParams
        entry = server.get_request_handler("tools/call")
        assert entry is not None, "no tools/call handler was mounted"

        result = await entry.handler(None, CallToolRequestParams(name="greet", arguments={"name": "World"}))

        assert result.is_error is False
        assert "Hello, World!" in result.content[0].text

    async def test_call_unknown_tool_is_a_tool_error(self, mounted):
        server, _ = mounted
        from mcp.types import CallToolRequestParams
        entry = server.get_request_handler("tools/call")

        result = await entry.handler(None, CallToolRequestParams(name="nonexistent", arguments={}))

        assert result.is_error is True
        assert "Unknown tool: nonexistent" in result.content[0].text

    async def test_a_real_client_lists_and_calls_tools(self, mounted):
        """Full protocol round trip: an MCP client connected to the mounted
        server performs the handshake, sees the tools, and calls one."""
        server, _ = mounted
        from mcp import Client

        async with Client(server) as client:
            tools = await client.list_tools()
            assert [tool.name for tool in tools.tools] == ["greet"]

            result = await client.call_tool("greet", {"name": "World"})
            assert result.is_error is False
            assert "Hello, World!" in result.content[0].text

            unknown = await client.call_tool("nonexistent", {})
            assert unknown.is_error is True
            assert "Unknown tool: nonexistent" in unknown.content[0].text

    async def test_mount_returns_lifecycle(self, mounted):
        """Verify mount returns working lifecycle handle."""
        _, lifecycle = mounted
        assert hasattr(lifecycle, "stop")
        assert hasattr(lifecycle, "shutdown")
