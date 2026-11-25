package dev.anip.mcptest;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.SideEffect;
import dev.anip.mcp.AnipMcpStdio;
import dev.anip.mcp.McpCredentials;
import dev.anip.mcp.McpToolTranslator;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.ServiceConfig;

import io.modelcontextprotocol.server.McpServerFeatures;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

class AnipMcpStdioTest {

    private ANIPService service;

    @BeforeEach
    void setUp() throws Exception {
        service = new ANIPService(new ServiceConfig()
                .setServiceId("test-mcp-svc")
                .setCapabilities(List.of(
                        new CapabilityDef(
                                new CapabilityDeclaration(
                                        "search_flights", "Search for flights", "1.0",
                                        List.of(
                                                new CapabilityInput("origin", "string", true, "Origin airport"),
                                                new CapabilityInput("destination", "string", true, "Destination airport"),
                                                new CapabilityInput("cabin", "string", true, null,
                                                        "Cabin; asked for when absent", null, false, null, null, null,
                                                        new dev.anip.core.InputResolution(
                                                                dev.anip.core.ResolutionMode.CLARIFY, null,
                                                                dev.anip.core.ResolutionBehavior.CLARIFY, null, null))
                                        ),
                                        new CapabilityOutput("object", List.of("flights")),
                                        new SideEffect("read", "not_applicable"),
                                        List.of("travel"), null, null,
                                        List.of("sync")
                                ),
                                (ctx, params) -> Map.of("flights", List.of(
                                        Map.of("id", "FL-001", "price", 199.99)
                                ))
                        )
                ))
                .setStorage(":memory:")
                .setAuthenticate(bearer -> {
                    if ("valid-api-key".equals(bearer)) {
                        return Optional.of("user@test.com");
                    }
                    return Optional.empty();
                })
                .setRetentionIntervalSeconds(-1));
        service.start();
    }

    @AfterEach
    void tearDown() {
        if (service != null) {
            service.shutdown();
        }
    }

    @Test
    void testBuildToolsWithCredentials() {
        McpCredentials creds = new McpCredentials("valid-api-key",
                List.of("travel"), "test-agent");

        List<McpServerFeatures.SyncToolSpecification> tools =
                AnipMcpStdio.buildTools(service, creds, true);

        assertFalse(tools.isEmpty());
        assertEquals(1, tools.size());
        assertEquals("search_flights", tools.get(0).tool().name());
    }

    @Test
    void testInvokeWithValidCredentials() {
        McpCredentials creds = new McpCredentials("valid-api-key",
                List.of("travel"), "test-agent");

        McpToolTranslator.McpInvokeResult result = AnipMcpStdio.invokeWithMountCredentials(
                service, "search_flights",
                Map.of("origin", "SFO", "destination", "LAX"), creds);

        assertFalse(result.isError());
        assertTrue(result.text().contains("FL-001"));
    }

    @Test
    void testInvokeWithInvalidCredentials() {
        McpCredentials creds = new McpCredentials("bad-key",
                List.of("travel"), "test-agent");

        McpToolTranslator.McpInvokeResult result = AnipMcpStdio.invokeWithMountCredentials(
                service, "search_flights", Map.of(), creds);

        assertTrue(result.isError());
        assertTrue(result.text().contains("FAILED: authentication_required"));
    }

    // SPEC.md §6.3: a call that fails parameter validation is a tool error
    // carrying the failure, not a success.

    @Test
    void testMissingRequiredInputIsAToolError() {
        McpCredentials creds = new McpCredentials("valid-api-key",
                List.of("travel"), "test-agent");

        McpToolTranslator.McpInvokeResult result = AnipMcpStdio.invokeWithMountCredentials(
                service, "search_flights", Map.of("origin", "SFO"), creds);

        assertTrue(result.isError());
        assertEquals("FAILED: invalid_parameters\n"
                + "Detail: search_flights is missing required input(s): destination\n"
                + "Resolution: retry_now\n"
                + "Requires: parameters that match the capability's declared inputs\n"
                + "Retryable: no", result.text());
    }

    @Test
    void testAbsentArgumentsAreAToolError() {
        McpCredentials creds = new McpCredentials("valid-api-key",
                List.of("travel"), "test-agent");

        McpToolTranslator.McpInvokeResult result = AnipMcpStdio.invokeWithMountCredentials(
                service, "search_flights", null, creds);

        assertTrue(result.isError());
        assertTrue(result.text().startsWith("FAILED: invalid_parameters\n"
                + "Detail: search_flights is missing required input(s): origin, destination\n"),
                result.text());
    }

    @Test
    void testWrongTypedArgumentIsAToolError() {
        McpCredentials creds = new McpCredentials("valid-api-key",
                List.of("travel"), "test-agent");

        McpToolTranslator.McpInvokeResult result = AnipMcpStdio.invokeWithMountCredentials(
                service, "search_flights", Map.of("origin", "SFO", "destination", 7), creds);

        assertTrue(result.isError());
        assertTrue(result.text().contains(
                "Detail: search_flights has invalid input(s): 'destination' must be string, got number"),
                result.text());
        assertTrue(result.text().contains("Resolution: retry_now"), result.text());
    }

    @Test
    void testInputThatDeclaresOnMissingIsNotDemandedOfTheCaller() {
        McpCredentials creds = new McpCredentials("valid-api-key",
                List.of("travel"), "test-agent");

        // 'cabin' is required and declares resolution.on_missing: the tool
        // schema does not require it and the call reaches the handler.
        assertEquals(List.of("origin", "destination"),
                AnipMcpStdio.buildTools(service, creds, true).get(0).tool().inputSchema().required());
        McpToolTranslator.McpInvokeResult result = AnipMcpStdio.invokeWithMountCredentials(
                service, "search_flights", Map.of("origin", "SFO", "destination", "LAX"), creds);
        assertFalse(result.isError(), result.text());

        result = AnipMcpStdio.invokeWithMountCredentials(
                service, "search_flights",
                Map.of("origin", "SFO", "destination", "LAX", "cabin", 3), creds);
        assertTrue(result.isError());
        assertTrue(result.text().contains("'cabin' must be string, got number"), result.text());
    }

    @Test
    void testNarrowScope() {
        CapabilityDeclaration decl = service.getCapabilityDeclaration("search_flights");
        List<String> narrowed = AnipMcpStdio.narrowScope(
                List.of("travel", "finance", "admin"), decl);

        assertEquals(1, narrowed.size());
        assertTrue(narrowed.contains("travel"));
    }

    @Test
    void testNarrowScopePreservesConstraints() {
        CapabilityDeclaration decl = service.getCapabilityDeclaration("search_flights");
        List<String> narrowed = AnipMcpStdio.narrowScope(
                List.of("travel:max_$500", "finance"), decl);

        assertEquals(1, narrowed.size());
        assertEquals("travel:max_$500", narrowed.get(0));
    }
}
