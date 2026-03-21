/**
 * ANIP MCP Streamable HTTP transport for Express.
 *
 * Uses StreamableHTTPServerTransport (Node.js wrapper around Web Standard transport).
 *
 * The SDK's stateless transport requires a fresh transport+server pair per request.
 * We use buildMcpServer() per request, which is cheap as it only registers handlers.
 */
import type { Express } from "express";
import type { ANIPService } from "@anip/service";
import { buildMcpServer } from "@anip/mcp";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

export interface McpExpressOptions {
  /** MCP endpoint path. Default: "/mcp" */
  path?: string;
  /** Enrich tool descriptions with ANIP metadata. Default: true */
  enrichDescriptions?: boolean;
}

export async function mountAnipMcpExpress(
  app: Express,
  service: ANIPService,
  opts?: McpExpressOptions,
): Promise<{ closeTransport: () => Promise<void> }> {
  const mcpPath = opts?.path ?? "/mcp";
  const enrichDescriptions = opts?.enrichDescriptions;

  // Track active transports for cleanup
  const activeTransports = new Set<StreamableHTTPServerTransport>();

  // Forward all requests on the MCP path.
  // Stateless mode requires a fresh transport+server per request.
  app.all(mcpPath, async (req, res, next) => {
    try {
      const authHeader = req.headers.authorization;
      const token =
        typeof authHeader === "string" && authHeader.startsWith("Bearer ")
          ? authHeader.slice(7).trim()
          : undefined;

      // Create fresh server+transport per request (stateless mode requirement)
      const server = buildMcpServer(service, { enrichDescriptions });
      const transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: undefined, // stateless
      });
      activeTransports.add(transport);

      await server.connect(transport);

      // Set auth on req so the Node wrapper can pass it through to the Web Standard transport
      if (token) {
        (req as any).auth = { token, clientId: "", scopes: [] };
      }

      await transport.handleRequest(req, res);
      activeTransports.delete(transport);
    } catch (err) {
      next(err);
    }
  });

  return {
    closeTransport: async () => {
      await Promise.all(Array.from(activeTransports).map((t) => t.close()));
      activeTransports.clear();
    },
  };
}
