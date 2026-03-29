/**
 * ANIP MCP bindings — mount ANIPService capabilities as MCP tools.
 *
 * Supports stdio transport via MCP Server.
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import type { ANIPService } from "@anip-dev/service";
import { ANIPError } from "@anip-dev/service";
import { invokeWithToken } from "./invocation.js";
import type { InvokeResult } from "./invocation.js";
import { capabilityToInputSchema, enrichDescription } from "./translation.js";

export interface McpCredentials {
  apiKey: string;
  scope: string[];
  subject: string;
}

export interface McpMountOptions {
  /** Mount-time credentials for stdio transport (no per-request auth). */
  credentials?: McpCredentials;
  /** Enrich MCP tool descriptions with ANIP metadata. Default: true. */
  enrichDescriptions?: boolean;
}

interface MCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

/**
 * Invoke an ANIP capability using mount-time credentials.
 * Issues a synthetic token per call then delegates to invokeWithToken.
 */
async function invokeWithMountCredentials(
  service: ANIPService,
  capabilityName: string,
  args: Record<string, unknown>,
  credentials: McpCredentials,
): Promise<InvokeResult> {
  // Authenticate the bootstrap credential
  const principal = await service.authenticateBearer(credentials.apiKey);
  if (!principal) {
    return {
      text: "FAILED: authentication_required\nDetail: Invalid bootstrap credential\nRetryable: no",
      isError: true,
    };
  }

  // Narrow scope to what the capability needs
  const capDecl = service.getCapabilityDeclaration(capabilityName);
  const minScope = (capDecl?.minimum_scope as string[]) ?? [];
  let capScope = credentials.scope;
  if (minScope.length > 0) {
    const needed = new Set(minScope);
    const narrowed = credentials.scope.filter((s) => {
      const base = s.split(":")[0];
      return needed.has(base) || needed.has(s);
    });
    if (narrowed.length > 0) capScope = narrowed;
  }

  // Issue a synthetic token
  let tokenResult: Record<string, unknown>;
  try {
    tokenResult = await service.issueToken(principal, {
      subject: credentials.subject,
      scope: capScope,
      capability: capabilityName,
      purpose_parameters: { source: "mcp" },
    });
  } catch (e) {
    if (e instanceof ANIPError) {
      return {
        text: `FAILED: ${e.errorType}\nDetail: ${e.detail}\nRetryable: no`,
        isError: true,
      };
    }
    throw e;
  }

  const jwt = tokenResult.token as string;
  const token = await service.resolveBearerToken(jwt);

  return invokeWithToken(service, capabilityName, args, token);
}

/**
 * Mount ANIP capabilities as MCP tools on an MCP Server (stdio transport).
 */
export async function mountAnipMcp(
  target: Server,
  service: ANIPService,
  opts?: McpMountOptions,
): Promise<{ stop: () => void; shutdown: () => Promise<void> }> {
  const enrichDescs = opts?.enrichDescriptions ?? true;
  const credentials = opts?.credentials;

  if (!credentials) {
    throw new Error(
      "mountAnipMcp on MCP Server requires credentials for stdio transport. " +
      "Provide { credentials: { apiKey, scope, subject } } in options.",
    );
  }

  await service.start();

  // Build tool map from service capabilities
  const manifest = service.getManifest();
  const mcpTools = new Map<string, MCPTool>();
  for (const [name, decl] of Object.entries(manifest.capabilities)) {
    const declaration = decl as Record<string, unknown>;
    const fullDecl = service.getCapabilityDeclaration(name);
    if (!fullDecl) continue;
    const description = enrichDescs
      ? enrichDescription(fullDecl as any)
      : (declaration.description as string);
    mcpTools.set(name, {
      name,
      description,
      inputSchema: capabilityToInputSchema(fullDecl as any),
    });
  }

  // Register MCP handlers
  target.setRequestHandler(ListToolsRequestSchema, async () => {
    return { tools: Array.from(mcpTools.values()) };
  });

  target.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    if (!mcpTools.has(name)) {
      return {
        content: [{
          type: "text" as const,
          text: `Unknown tool: ${name}. Available: ${Array.from(mcpTools.keys()).join(", ")}`,
        }],
        isError: true,
      };
    }

    try {
      const result = await invokeWithMountCredentials(
        service, name, (args ?? {}) as Record<string, unknown>, credentials,
      );
      return {
        content: [{ type: "text" as const, text: result.text }],
        isError: result.isError,
      };
    } catch (err) {
      return {
        content: [{
          type: "text" as const,
          text: `ANIP invocation error: ${err instanceof Error ? err.message : String(err)}`,
        }],
        isError: true,
      };
    }
  });

  return {
    stop: () => {
      service.stop();
    },
    shutdown: async () => {
      service.stop();
      await service.shutdown();
    },
  };
}
