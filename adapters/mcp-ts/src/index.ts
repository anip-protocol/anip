#!/usr/bin/env node
/**
 * ANIP-MCP Bridge (TypeScript)
 *
 * A generic bridge that discovers any ANIP-compliant service and
 * exposes its capabilities as MCP tools. Point it at any ANIP service
 * URL — zero per-service code required.
 *
 * Usage:
 *   ANIP_SERVICE_URL=http://localhost:8000 npx tsx src/index.ts
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

import { loadConfig } from "./config.js";
import { discoverService } from "./discovery.js";
import type { ANIPService } from "./discovery.js";
import { ANIPInvoker } from "./invocation.js";
import {
  capabilityToInputSchema,
  enrichDescription,
} from "./translation.js";

interface MCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

async function main() {
  const config = loadConfig();

  console.error(`[anip-mcp-bridge] Discovering ANIP service at ${config.anipServiceUrl}`);

  // Step 1: Discover the ANIP service
  let service: ANIPService;
  try {
    service = await discoverService(config.anipServiceUrl);
  } catch (err) {
    console.error(`[anip-mcp-bridge] Discovery failed:`, err);
    process.exit(1);
  }

  console.error(
    `[anip-mcp-bridge] Discovered ${service.baseUrl} (${service.compliance}) with ${service.capabilities.size} capabilities`
  );
  for (const [name, cap] of service.capabilities) {
    console.error(
      `[anip-mcp-bridge]   ${name}: ${cap.sideEffect} [${cap.contractVersion}]${cap.financial ? " (financial)" : ""}`
    );
  }

  // Step 2: Set up the invoker with delegation tokens
  const invoker = new ANIPInvoker(service, {
    scope: config.scope,
    apiKey: config.apiKey,
  });
  console.error("[anip-mcp-bridge] Invoker ready");

  // Step 3: Build MCP tools from ANIP capabilities
  const mcpTools: Map<string, MCPTool> = new Map();
  for (const [name, capability] of service.capabilities) {
    const description = config.enrichDescriptions
      ? enrichDescription(capability)
      : capability.description;

    mcpTools.set(name, {
      name,
      description,
      inputSchema: capabilityToInputSchema(capability),
    });
  }

  // Step 4: Create MCP server
  const server = new Server(
    { name: "anip-mcp-bridge", version: "0.2.0" },
    { capabilities: { tools: {} } }
  );

  // List tools handler
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return { tools: Array.from(mcpTools.values()) };
  });

  // Call tool handler
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    if (!mcpTools.has(name)) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Unknown tool: ${name}. Available: ${Array.from(mcpTools.keys()).join(", ")}`,
          },
        ],
        isError: true,
      };
    }

    try {
      const result = await invoker.invoke(name, (args ?? {}) as Record<string, unknown>);
      return {
        content: [{ type: "text" as const, text: result }],
      };
    } catch (err) {
      console.error(`[anip-mcp-bridge] Invocation failed for ${name}:`, err);
      return {
        content: [
          {
            type: "text" as const,
            text: `ANIP invocation error: ${err instanceof Error ? err.message : String(err)}`,
          },
        ],
        isError: true,
      };
    }
  });

  // Step 5: Connect via stdio
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("[anip-mcp-bridge] MCP server running on stdio");
}

main().catch((err) => {
  console.error("[anip-mcp-bridge] Fatal:", err);
  process.exit(1);
});
