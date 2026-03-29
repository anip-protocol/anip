/**
 * ANIP MCP Streamable HTTP transport for Fastify.
 *
 * Uses StreamableHTTPServerTransport (Node.js IncomingMessage/ServerResponse wrapper).
 *
 * The SDK's stateless transport requires a fresh transport+server pair per request.
 * We use buildMcpServer() per request, which is cheap as it only registers handlers.
 *
 * Fastify pre-parses the request body, so we pass it as the third argument
 * to handleRequest rather than letting the transport try to re-read the stream.
 */
import type { FastifyInstance } from "fastify";
import type { ANIPService } from "@anip-dev/service";
import { buildMcpServer } from "@anip-dev/mcp";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

export interface McpFastifyOptions {
  /** MCP endpoint path. Default: "/mcp" */
  path?: string;
  /** Enrich tool descriptions with ANIP metadata. Default: true */
  enrichDescriptions?: boolean;
}

export async function mountAnipMcpFastify(
  app: FastifyInstance,
  service: ANIPService,
  opts?: McpFastifyOptions,
): Promise<{ closeTransport: () => Promise<void> }> {
  const mcpPath = opts?.path ?? "/mcp";
  const enrichDescriptions = opts?.enrichDescriptions;

  // Track active transports for cleanup
  const activeTransports = new Set<StreamableHTTPServerTransport>();

  // Forward all requests on the MCP path.
  // Stateless mode requires a fresh transport+server per request.
  app.all(mcpPath, async (request, reply) => {
    const authHeader = request.headers.authorization;
    const token =
      typeof authHeader === "string" && authHeader.startsWith("Bearer ")
        ? authHeader.slice(7).trim()
        : undefined;

    // Attach auth to raw IncomingMessage — the SDK reads req.auth in handleRequest
    if (token) {
      (request.raw as any).auth = { token, clientId: "", scopes: [] };
    }

    // Create fresh server+transport per request (stateless mode requirement)
    const server = buildMcpServer(service, { enrichDescriptions });
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined, // stateless
    });
    activeTransports.add(transport);

    await server.connect(transport);

    // Pass the Fastify-parsed body to avoid double-reading the Node stream.
    // The SDK accepts an optional parsedBody as the third argument.
    await transport.handleRequest(request.raw, reply.raw, request.body);

    activeTransports.delete(transport);
  });

  return {
    closeTransport: async () => {
      await Promise.all(Array.from(activeTransports).map((t) => t.close()));
      activeTransports.clear();
    },
  };
}
