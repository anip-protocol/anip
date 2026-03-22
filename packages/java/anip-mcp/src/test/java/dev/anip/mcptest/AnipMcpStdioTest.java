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
                                                new CapabilityInput("destination", "string", true, "Destination airport")
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
