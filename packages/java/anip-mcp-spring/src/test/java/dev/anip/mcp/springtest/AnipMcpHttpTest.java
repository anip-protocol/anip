package dev.anip.mcp.springtest;

import com.fasterxml.jackson.databind.JsonNode;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.InputResolution;
import dev.anip.core.ResolutionBehavior;
import dev.anip.core.ResolutionMode;
import dev.anip.core.SideEffect;
import dev.anip.service.ANIPService;
import dev.anip.service.CapabilityDef;
import dev.anip.service.ServiceConfig;
import dev.anip.mcp.spring.AnipMcpHttp;

import io.modelcontextprotocol.server.transport.HttpServletStreamableServerTransportProvider;

import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.boot.web.servlet.ServletRegistrationBean;
import org.springframework.context.annotation.Bean;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The MCP Streamable HTTP transport mounted by {@link AnipMcpHttp}, driven
 * over HTTP: a call that fails parameter validation (SPEC.md §6.3) is a tool
 * error carrying the failure. The Quarkus adapter runs the same cases
 * ({@code dev.anip.mcp.quarkustest.AnipMcpQuarkusTest}).
 */
@SpringBootTest(classes = AnipMcpHttpTest.TestApp.class,
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class AnipMcpHttpTest {

    static final AtomicInteger CALLS = new AtomicInteger();

    @LocalServerPort
    private int port;

    @SpringBootApplication
    static class TestApp {
        @Bean(destroyMethod = "shutdown")
        ANIPService anipService() {
            return testService(CALLS);
        }

        @Bean
        ServletRegistrationBean<HttpServletStreamableServerTransportProvider> mcp(ANIPService service) {
            return AnipMcpHttp.mount(service);
        }
    }

    static ANIPService testService(AtomicInteger calls) {
        ANIPService service = new ANIPService(new ServiceConfig()
                .setServiceId("test-mcp-http-svc")
                .setCapabilities(List.of(new CapabilityDef(
                        new CapabilityDeclaration(
                                "search_flights", "Search for flights", "1.0",
                                List.of(
                                        new CapabilityInput("origin", "string", true, "Origin airport"),
                                        new CapabilityInput("destination", "string", true, "Destination airport"),
                                        new CapabilityInput("passengers", "integer", false, "Passengers"),
                                        // Required, and the declaration says what happens when it is absent.
                                        new CapabilityInput("cabin", "string", true, null,
                                                "Cabin; asked for when absent", null, false, null, null, null,
                                                new InputResolution(ResolutionMode.CLARIFY, null,
                                                        ResolutionBehavior.CLARIFY, null, null))),
                                new CapabilityOutput("object", List.of("flights")),
                                new SideEffect("read", "not_applicable"),
                                List.of("travel"), null, null, List.of("sync")),
                        (ctx, params) -> {
                            calls.incrementAndGet();
                            return Map.of("flights", List.of(Map.of("id", "FL-001")));
                        })))
                .setStorage(":memory:")
                .setAuthenticate(bearer -> "valid-api-key".equals(bearer)
                        ? Optional.of("user@test.com") : Optional.empty())
                .setRetentionIntervalSeconds(-1));
        try {
            service.start();
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
        return service;
    }

    private McpTestClient client(String bearer) throws Exception {
        return new McpTestClient("http://localhost:" + port + "/mcp", bearer).initialize();
    }

    // --- the same cases as the Quarkus adapter's test ---

    private static String text(JsonNode response) {
        return response.get("result").get("content").get(0).get("text").asText();
    }

    private static void assertToolError(JsonNode response) {
        // A tool error carrying the failure: not a success, not a transport error.
        assertNull(response.get("error"), "a JSON-RPC error instead of a tool result: " + response);
        assertNotNull(response.get("result"), String.valueOf(response));
        assertTrue(response.get("result").get("isError").asBoolean(), String.valueOf(response));
    }

    @Test
    void validArgumentsReachTheHandler() throws Exception {
        int before = CALLS.get();
        JsonNode response = client("valid-api-key").callTool("search_flights",
                Map.of("origin", "SEA", "destination", "SFO", "passengers", 2));

        assertNull(response.get("error"), String.valueOf(response));
        assertFalse(response.get("result").path("isError").asBoolean(false), String.valueOf(response));
        assertTrue(text(response).contains("FL-001"), text(response));
        assertEquals(before + 1, CALLS.get());
    }

    @Test
    void missingRequiredInputIsAToolErrorCarryingTheFailure() throws Exception {
        int before = CALLS.get();
        JsonNode response = client("valid-api-key").callTool("search_flights", Map.of("origin", "SEA"));

        assertToolError(response);
        assertEquals("FAILED: invalid_parameters\n"
                + "Detail: search_flights is missing required input(s): destination\n"
                + "Resolution: retry_now\n"
                + "Requires: parameters that match the capability's declared inputs\n"
                + "Retryable: no", text(response));
        assertEquals(before, CALLS.get(), "the handler must not run");
    }

    @Test
    void absentArgumentsAreAToolErrorCarryingTheFailure() throws Exception {
        int before = CALLS.get();
        JsonNode response = client("valid-api-key").callTool("search_flights", null);

        assertToolError(response);
        assertTrue(text(response).startsWith("FAILED: invalid_parameters\n"
                + "Detail: search_flights is missing required input(s): origin, destination\n"),
                text(response));
        assertEquals(before, CALLS.get(), "the handler must not run");
    }

    @Test
    void wrongTypedInputIsAToolErrorCarryingTheFailure() throws Exception {
        int before = CALLS.get();
        JsonNode response = client("valid-api-key").callTool("search_flights",
                Map.of("origin", "SEA", "destination", 7, "passengers", "two", "cabin", true));

        assertToolError(response);
        assertEquals("FAILED: invalid_parameters\n"
                + "Detail: search_flights has invalid input(s): 'destination' must be string, got number; "
                + "'passengers' must be integer, got string; 'cabin' must be string, got boolean\n"
                + "Resolution: retry_now\n"
                + "Requires: parameters that match the capability's declared inputs\n"
                + "Retryable: no", text(response));
        assertEquals(before, CALLS.get(), "the handler must not run");
    }

    @Test
    void toolSchemaDoesNotDemandAnInputThatDeclaresOnMissing() throws Exception {
        JsonNode tools = client("valid-api-key").request("tools/list", Map.of()).get("result").get("tools");
        assertEquals(1, tools.size());
        assertEquals("search_flights", tools.get(0).get("name").asText());
        assertEquals("[\"origin\",\"destination\"]", tools.get(0).get("inputSchema").get("required").toString());
        assertTrue(tools.get(0).get("inputSchema").get("properties").has("cabin"));
    }

    @Test
    void callWithoutCredentialIsAToolError() throws Exception {
        int before = CALLS.get();
        JsonNode response = client(null).callTool("search_flights",
                Map.of("origin", "SEA", "destination", "SFO"));

        assertToolError(response);
        assertTrue(text(response).startsWith("FAILED: authentication_required"), text(response));
        assertEquals(before, CALLS.get());
    }
}
