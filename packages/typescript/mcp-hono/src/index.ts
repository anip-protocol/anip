/**
 * ANIP MCP Streamable HTTP transport for Hono.
 *
 * Uses WebStandardStreamableHTTPServerTransport (Web Standard APIs).
 *
 * The SDK's stateless transport requires a fresh transport+server pair per request.
 * We use buildMcpServer() per request, which is cheap as it only registers handlers.
 */
import type { Hono } from "hono";
import type { ANIPService } from "@anip-dev/service";
import { buildMcpServer } from "@anip-dev/mcp";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";

export interface McpHonoOptions {
  /** MCP endpoint path. Default: "/mcp" */
  path?: string;
  /** Enrich tool descriptions with ANIP metadata. Default: true */
  enrichDescriptions?: boolean;
}

export async function mountAnipMcpHono(
  app: Hono,
  service: ANIPService,
  opts?: McpHonoOptions,
): Promise<{ closeTransport: () => Promise<void> }> {
  const mcpPath = opts?.path ?? "/mcp";
  const enrichDescriptions = opts?.enrichDescriptions;

  // Track active transports for cleanup
  const activeTransports = new Set<WebStandardStreamableHTTPServerTransport>();

  // Forward all requests on the MCP path.
  // Stateless mode requires a fresh transport+server per request.
  app.all(`${mcpPath}`, async (c) => {
    const authHeader = c.req.header("authorization");
    const token = authHeader?.startsWith("Bearer ") ? authHeader.slice(7).trim() : undefined;

    // Create fresh server+transport per request (stateless mode requirement)
    const server = buildMcpServer(service, { enrichDescriptions });
    const transport = new WebStandardStreamableHTTPServerTransport({
      sessionIdGenerator: undefined, // stateless
    });
    activeTransports.add(transport);

    await server.connect(transport);

    const response = await transport.handleRequest(c.req.raw, {
      authInfo: token ? { token, clientId: "", scopes: [] } : undefined,
    });

    activeTransports.delete(transport);
    return response;
  });

  return {
    closeTransport: async () => {
      await Promise.all(Array.from(activeTransports).map((t) => t.close()));
      activeTransports.clear();
    },
  };
}
