package dev.anip.mcp.spring;

import dev.anip.core.ANIPError;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.DelegationToken;
import dev.anip.mcp.McpAuthBridge;
import dev.anip.mcp.McpToolTranslator;
import dev.anip.service.ANIPService;
import dev.anip.service.InvokeOpts;

import io.modelcontextprotocol.common.McpTransportContext;
import io.modelcontextprotocol.server.McpServer;
import io.modelcontextprotocol.server.McpServerFeatures;
import io.modelcontextprotocol.server.McpSyncServer;
import io.modelcontextprotocol.server.McpSyncServerExchange;
import io.modelcontextprotocol.server.transport.WebMvcStreamableServerTransportProvider;
import io.modelcontextprotocol.spec.McpSchema;

import org.springframework.web.servlet.function.RouterFunction;
import org.springframework.web.servlet.function.ServerResponse;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.BiFunction;

/**
 * ANIP MCP Streamable HTTP transport with per-request auth
 * from the Authorization: Bearer header.
 */
public class AnipMcpHttp {

    private AnipMcpHttp() {}

    /**
     * Creates the Streamable HTTP transport provider with auth context extraction.
     */
    public static WebMvcStreamableServerTransportProvider createTransport(String endpoint) {
        return new WebMvcStreamableServerTransportProvider.Builder()
                .mcpEndpoint(endpoint)
                .contextExtractor(serverRequest -> {
                    String auth = serverRequest.headers().firstHeader("Authorization");
                    if (auth != null) {
                        return McpTransportContext.create(Map.of("authorization", auth));
                    }
                    return McpTransportContext.EMPTY;
                })
                .build();
    }

    /**
     * Builds MCP tool specifications for HTTP transport with per-request auth.
     */
    @SuppressWarnings("unchecked")
    public static List<McpServerFeatures.SyncToolSpecification> buildTools(
            ANIPService service, boolean enrichDescriptions) {

        Map<String, Object> manifest = (Map<String, Object>) service.getManifest();
        Map<String, Object> capabilities = (Map<String, Object>) manifest.get("capabilities");

        List<McpServerFeatures.SyncToolSpecification> tools = new ArrayList<>();

        for (String name : capabilities.keySet()) {
            CapabilityDeclaration decl = service.getCapabilityDeclaration(name);
            if (decl == null) continue;

            McpSchema.Tool tool = McpToolTranslator.buildTool(name, decl, enrichDescriptions);

            String capName = name;
            BiFunction<McpSyncServerExchange, Map<String, Object>, McpSchema.CallToolResult> handler =
                    (exchange, args) -> {
                        if (args == null) args = Map.of();

                        // Extract bearer from transport context.
                        McpTransportContext ctx = exchange.transportContext();
                        String auth = ctx != null ? (String) ctx.get("authorization") : null;
                        String bearer = extractBearer(auth);

                        if (bearer == null || bearer.isEmpty()) {
                            return new McpSchema.CallToolResult(
                                    "FAILED: authentication_required\nDetail: No Authorization header provided\nRetryable: no",
                                    true);
                        }

                        // Resolve auth: JWT-first, API-key fallback.
                        DelegationToken token;
                        try {
                            token = McpAuthBridge.resolveAuth(bearer, service, capName);
                        } catch (ANIPError e) {
                            return new McpSchema.CallToolResult(
                                    "FAILED: " + e.getErrorType() + "\nDetail: " + e.getDetail() + "\nRetryable: no",
                                    true);
                        } catch (Exception e) {
                            return new McpSchema.CallToolResult(
                                    "FAILED: authentication_failed\nDetail: " + e.getMessage() + "\nRetryable: no",
                                    true);
                        }

                        // Invoke with resolved token.
                        Map<String, Object> result = service.invoke(capName, token, args,
                                new InvokeOpts());
                        McpToolTranslator.McpInvokeResult mcpResult =
                                McpToolTranslator.translateResponse(result);
                        if (mcpResult.isError()) {
                            return new McpSchema.CallToolResult(mcpResult.text(), true);
                        }
                        return new McpSchema.CallToolResult(mcpResult.text(), false);
                    };

            tools.add(new McpServerFeatures.SyncToolSpecification(tool, handler));
        }

        return tools;
    }

    /**
     * Mounts the MCP Streamable HTTP server and returns the router function
     * for Spring MVC integration.
     */
    public static RouterFunction<ServerResponse> mount(ANIPService service, String endpoint,
                                                         boolean enrichDescriptions) {
        WebMvcStreamableServerTransportProvider transport = createTransport(endpoint);
        List<McpServerFeatures.SyncToolSpecification> tools =
                buildTools(service, enrichDescriptions);

        McpSyncServer server = McpServer.sync(transport)
                .serverInfo("anip-mcp", "0.11.0")
                .tools(tools)
                .build();

        return transport.getRouterFunction();
    }

    public static RouterFunction<ServerResponse> mount(ANIPService service) {
        return mount(service, "/mcp", true);
    }

    private static String extractBearer(String authHeader) {
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            return authHeader.substring(7).trim();
        }
        return null;
    }
}
