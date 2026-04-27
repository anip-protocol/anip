package dev.anip.mcp;

import dev.anip.core.ANIPError;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.DelegationToken;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.service.ANIPService;
import dev.anip.service.InvokeOpts;

import io.modelcontextprotocol.json.McpJsonDefaults;
import io.modelcontextprotocol.server.McpServer;
import io.modelcontextprotocol.server.McpServerFeatures;
import io.modelcontextprotocol.server.McpSyncServer;
import io.modelcontextprotocol.server.McpSyncServerExchange;
import io.modelcontextprotocol.server.transport.StdioServerTransportProvider;
import io.modelcontextprotocol.spec.McpSchema;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.BiFunction;

/**
 * ANIP MCP stdio transport with mount-time credentials.
 * Each tool call: authenticate -> narrow scope -> synthetic token -> invoke.
 */
public class AnipMcpStdio {

    private AnipMcpStdio() {}

    /**
     * Builds MCP tool specifications for stdio transport with mount-time credentials.
     */
    @SuppressWarnings("unchecked")
    public static List<McpServerFeatures.SyncToolSpecification> buildTools(
            ANIPService service, McpCredentials credentials, boolean enrichDescriptions) {

        Map<String, Object> manifest = (Map<String, Object>) service.getManifest();
        Map<String, Object> capabilities = (Map<String, Object>) manifest.get("capabilities");

        List<McpServerFeatures.SyncToolSpecification> tools = new ArrayList<>();

        for (String name : capabilities.keySet()) {
            CapabilityDeclaration decl = service.getCapabilityDeclaration(name);
            if (decl == null) continue;

            McpSchema.Tool tool = McpToolTranslator.buildTool(name, decl, enrichDescriptions);

            String capName = name;
            BiFunction<McpSyncServerExchange, McpSchema.CallToolRequest, McpSchema.CallToolResult> handler =
                    (exchange, request) -> {
                        Map<String, Object> args = request.arguments();
                        if (args == null) args = Map.of();
                        McpToolTranslator.McpInvokeResult result =
                                invokeWithMountCredentials(service, capName, args, credentials);
                        return McpToolTranslator.buildCallToolResult(result.text(), result.isError());
                    };

            tools.add(new McpServerFeatures.SyncToolSpecification(tool, handler));
        }

        return tools;
    }

    /**
     * Authenticates using mount-time credentials, narrows scope,
     * issues a synthetic token, and invokes the capability.
     */
    public static McpToolTranslator.McpInvokeResult invokeWithMountCredentials(
            ANIPService service, String capName, Map<String, Object> args,
            McpCredentials credentials) {

        // 1. Authenticate the bootstrap credential.
        Optional<String> principal = service.authenticateBearer(credentials.getApiKey());
        if (principal.isEmpty() || principal.get().isEmpty()) {
            return new McpToolTranslator.McpInvokeResult(
                    "FAILED: authentication_required\nDetail: Invalid bootstrap credential\nRetryable: no",
                    true);
        }

        // 2. Narrow scope.
        List<String> capScope = narrowScope(credentials.getScope(),
                service.getCapabilityDeclaration(capName));

        // 3. Issue synthetic token.
        TokenResponse tokenResp;
        try {
            tokenResp = service.issueToken(principal.get(), new TokenRequest(
                    credentials.getSubject(), capScope, capName,
                    Map.of("source", "mcp"), null, 0, null
            ));
        } catch (ANIPError e) {
            return new McpToolTranslator.McpInvokeResult(
                    "FAILED: " + e.getErrorType() + "\nDetail: " + e.getDetail() + "\nRetryable: no",
                    true);
        } catch (Exception e) {
            return new McpToolTranslator.McpInvokeResult(
                    "FAILED: internal_error\nDetail: " + e.getMessage() + "\nRetryable: no",
                    true);
        }

        // 4. Resolve the JWT.
        DelegationToken token;
        try {
            token = service.resolveBearerToken(tokenResp.getToken());
        } catch (Exception e) {
            return new McpToolTranslator.McpInvokeResult(
                    "FAILED: invalid_token\nDetail: " + e.getMessage() + "\nRetryable: no",
                    true);
        }

        // 5. Invoke.
        // v0.23: MCP tool args ARE the capability args (no envelope), so
        // continuation grant rides on a reserved __approval_grant key.
        // Strip it from args before invocation so it doesn't leak into the
        // params digest. session_id is intentionally never read from args
        // — comes from the signed token only.
        InvokeOpts opts = new InvokeOpts();
        Map<String, Object> invokeArgs = args;
        if (args != null && args.get("__approval_grant") instanceof String grant && !grant.isEmpty()) {
            opts.setApprovalGrant(grant);
            invokeArgs = new java.util.LinkedHashMap<>(args);
            invokeArgs.remove("__approval_grant");
        }
        Map<String, Object> result = service.invoke(capName, token, invokeArgs, opts);
        return McpToolTranslator.translateResponse(result);
    }

    /**
     * Narrows scope to what the capability needs.
     */
    public static List<String> narrowScope(List<String> mountScope, CapabilityDeclaration decl) {
        if (decl == null || decl.getMinimumScope() == null || decl.getMinimumScope().isEmpty()) {
            return mountScope;
        }

        java.util.Set<String> needed = new java.util.HashSet<>(decl.getMinimumScope());
        List<String> narrowed = new ArrayList<>();
        for (String s : mountScope) {
            String base = s.contains(":") ? s.substring(0, s.indexOf(':')) : s;
            if (needed.contains(base) || needed.contains(s)) {
                narrowed.add(s);
            }
        }

        return narrowed.isEmpty() ? mountScope : narrowed;
    }

    /**
     * Creates and serves an MCP server over stdio.
     * Blocks until stdin closes or SIGTERM/SIGINT.
     */
    public static void serveStdio(ANIPService service, McpCredentials credentials) throws Exception {
        serveStdio(service, credentials, true);
    }

    public static void serveStdio(ANIPService service, McpCredentials credentials,
                                    boolean enrichDescriptions) throws Exception {
        StdioServerTransportProvider transport = new StdioServerTransportProvider(
                McpJsonDefaults.getMapper());
        List<McpServerFeatures.SyncToolSpecification> tools =
                buildTools(service, credentials, enrichDescriptions);

        McpSyncServer server = McpServer.sync(transport)
                .serverInfo("anip-mcp", "0.11.0")
                .tools(tools)
                .build();

        // Block on transport (reads from stdin).
        transport.getClass(); // Keeps reference alive. Server is started by build().
    }
}
