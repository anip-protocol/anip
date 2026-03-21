/**
 * Shared ANIP MCP invocation core.
 *
 * Used by both stdio (routes.ts) and HTTP framework packages.
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";
import { capabilityToInputSchema, enrichDescription } from "./translation.js";

export interface InvokeResult {
  text: string;
  isError: boolean;
}

export interface BuildMcpServerOptions {
  enrichDescriptions?: boolean;
}

/**
 * Resolve auth from a bearer token string.
 * JWT-first, API-key fallback — same pattern as REST/GraphQL.
 *
 * Used by HTTP transports (not stdio — stdio uses mount-time credentials).
 */
export async function resolveAuth(
  bearer: string,
  service: ANIPService,
  capabilityName: string,
): Promise<import("@anip/core").DelegationToken> {
  // Try as JWT first — preserves original delegation chain
  let jwtError: ANIPError | null = null;
  try {
    return await service.resolveBearerToken(bearer);
  } catch (e) {
    if (!(e instanceof ANIPError)) throw e;
    jwtError = e;
  }

  // Try as API key — issue synthetic token scoped to this capability
  const principal = await service.authenticateBearer(bearer);
  if (principal) {
    const capDecl = service.getCapabilityDeclaration(capabilityName);
    const minScope = (capDecl?.minimum_scope as string[]) ?? [];
    const tokenResult = await service.issueToken(principal, {
      subject: "adapter:anip-mcp",
      scope: minScope.length > 0 ? minScope : ["*"],
      capability: capabilityName,
      purpose_parameters: { source: "mcp" },
    });
    const jwt = tokenResult.token as string;
    return await service.resolveBearerToken(jwt);
  }

  // Neither JWT nor API key — surface the original JWT error
  if (jwtError) throw jwtError;
  throw new ANIPError("authentication_required", "No valid bearer credential provided");
}

/**
 * Invoke a capability with an already-resolved delegation token.
 */
export async function invokeWithToken(
  service: ANIPService,
  capabilityName: string,
  args: Record<string, unknown>,
  token: import("@anip/core").DelegationToken,
): Promise<InvokeResult> {
  try {
    const result = await service.invoke(capabilityName, token, args);
    return translateResponse(result);
  } catch (e) {
    if (e instanceof ANIPError) {
      return {
        text: `FAILED: ${e.errorType}\nDetail: ${e.detail}\nRetryable: no`,
        isError: true,
      };
    }
    throw e;
  }
}

/**
 * Translate an ANIP invoke response to MCP text format.
 */
export function translateResponse(response: Record<string, unknown>): InvokeResult {
  if (response.success) {
    const result = response.result as Record<string, unknown>;
    const parts = [JSON.stringify(result, null, 2)];
    const costActual = response.cost_actual as Record<string, unknown> | undefined;
    if (costActual) {
      const financial = costActual.financial as Record<string, unknown>;
      const amount = financial?.amount;
      const currency = (financial?.currency as string) ?? "USD";
      if (amount !== undefined) parts.push(`\n[Cost: ${currency} ${amount}]`);
    }
    return { text: parts.join(""), isError: false };
  }

  const failure = response.failure as Record<string, unknown>;
  const parts = [
    `FAILED: ${failure?.type ?? "unknown"}`,
    `Detail: ${failure?.detail ?? "no detail"}`,
  ];
  const resolution = failure?.resolution as Record<string, unknown> | undefined;
  if (resolution) {
    parts.push(`Resolution: ${resolution.action ?? ""}`);
    if (resolution.requires) parts.push(`Requires: ${resolution.requires}`);
  }
  parts.push(`Retryable: ${(failure?.retry as boolean) ? "yes" : "no"}`);
  return { text: parts.join("\n"), isError: true };
}

/**
 * Build an MCP Server with tools registered from an ANIPService.
 *
 * The returned server has list_tools and call_tool handlers.
 * call_tool reads auth from extra.authInfo.token (for HTTP transport)
 * or falls back to the provided callToolHandler (for stdio).
 */
export function buildMcpServer(
  service: ANIPService,
  opts?: BuildMcpServerOptions & {
    /** Custom call_tool handler — used by stdio to inject mount-time credentials. */
    callToolHandler?: (name: string, args: Record<string, unknown>, extra?: any) => Promise<InvokeResult>;
  },
): Server {
  const enrichDescs = opts?.enrichDescriptions ?? true;

  const manifest = service.getManifest();
  const mcpTools = new Map<string, { name: string; description: string; inputSchema: Record<string, unknown> }>();
  for (const [name, decl] of Object.entries(manifest.capabilities)) {
    const fullDecl = service.getCapabilityDeclaration(name);
    if (!fullDecl) continue;
    const description = enrichDescs
      ? enrichDescription(fullDecl as any)
      : ((decl as any).description as string);
    mcpTools.set(name, {
      name,
      description,
      inputSchema: capabilityToInputSchema(fullDecl as any),
    });
  }

  const server = new Server(
    { name: "anip-mcp", version: "0.11.0" },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return { tools: Array.from(mcpTools.values()) };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request, extra) => {
    const { name, arguments: args } = request.params;

    if (!mcpTools.has(name)) {
      return {
        content: [{ type: "text" as const, text: `Unknown tool: ${name}. Available: ${Array.from(mcpTools.keys()).join(", ")}` }],
        isError: true,
      };
    }

    try {
      let result: InvokeResult;
      if (opts?.callToolHandler) {
        // stdio path — uses mount-time credentials
        result = await opts.callToolHandler(name, (args ?? {}) as Record<string, unknown>, extra);
      } else {
        // HTTP path — resolve auth from extra.authInfo.token
        const authInfo = (extra as any)?.authInfo;
        if (!authInfo?.token) {
          return {
            content: [{ type: "text" as const, text: "FAILED: authentication_required\nDetail: No Authorization header\nRetryable: yes" }],
            isError: true,
          };
        }
        const token = await resolveAuth(authInfo.token, service, name);
        result = await invokeWithToken(service, name, (args ?? {}) as Record<string, unknown>, token);
      }
      return {
        content: [{ type: "text" as const, text: result.text }],
        isError: result.isError,
      };
    } catch (err) {
      if (err instanceof ANIPError) {
        return {
          content: [{ type: "text" as const, text: `FAILED: ${err.errorType}\nDetail: ${err.detail}\nRetryable: no` }],
          isError: true,
        };
      }
      return {
        content: [{ type: "text" as const, text: `ANIP invocation error: ${err instanceof Error ? err.message : String(err)}` }],
        isError: true,
      };
    }
  });

  return server;
}
