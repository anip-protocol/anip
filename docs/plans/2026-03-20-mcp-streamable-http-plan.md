# MCP Streamable HTTP Transport Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Streamable HTTP transport to the MCP packages so ANIP-backed MCP servers work over the network, not just stdio.

**Architecture:** Extract shared invocation logic from `@anip/mcp` into `invocation.ts`. Add `buildMcpServer` helper. Create three thin framework packages (`@anip/mcp-hono`, `@anip/mcp-express`, `@anip/mcp-fastify`) that mount the SDK's Streamable HTTP transport. Python's `anip-mcp` gains `invocation.py` and `http.py`. Per-request auth from `Authorization: Bearer`, JWT-first, API-key fallback.

**Tech Stack:** TypeScript (`@modelcontextprotocol/sdk` Streamable HTTP, Hono, Express, Fastify), Python (`mcp` StreamableHTTPServerTransport, FastAPI)

**Design doc:** `docs/plans/2026-03-20-mcp-streamable-http-design.md`

---

## Chunk 1: Shared Core Refactor (`@anip/mcp`)

### Task 1: Extract invocation.ts

**Files:**
- Create: `packages/typescript/mcp/src/invocation.ts`
- Modify: `packages/typescript/mcp/src/routes.ts`
- Modify: `packages/typescript/mcp/src/index.ts`

Extract `translateResponse`, add `resolveAuth` and `invokeWithToken` as shared functions. Refactor `routes.ts` to use them. The stdio-specific `invokeWithMountCredentials` stays in `routes.ts`.

- [ ] **Step 1: Create invocation.ts**

```typescript
/**
 * Shared ANIP MCP invocation core.
 *
 * Used by both stdio (routes.ts) and HTTP framework packages.
 */
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";

export interface InvokeResult {
  text: string;
  isError: boolean;
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
```

- [ ] **Step 2: Refactor routes.ts to use invocation.ts**

Replace the inline `invokeCapability` and `translateResponse` with imports. Keep `invokeWithMountCredentials` (renamed from `invokeCapability`) in routes.ts since it's stdio-specific.

The refactored `routes.ts` should:
- Import `invokeWithToken`, `translateResponse`, `InvokeResult` from `./invocation.js`
- Keep the `McpCredentials` type and the `invokeWithMountCredentials` function (which issues a synthetic token from mount-time config then calls `invokeWithToken`)
- Keep the `mountAnipMcp` function unchanged in behavior

- [ ] **Step 3: Add buildMcpServer to invocation.ts**

Add a shared helper that creates an MCP Server with tools registered from an ANIPService. This is used by all framework packages.

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { capabilityToInputSchema, enrichDescription } from "./translation.js";

export interface BuildMcpServerOptions {
  enrichDescriptions?: boolean;
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
    { name: "anip-mcp", version: "0.8.0" },
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
        const authInfo = extra?.authInfo;
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
```

- [ ] **Step 4: Update index.ts exports**

```typescript
export { mountAnipMcp } from "./routes.js";
export type { McpMountOptions, McpCredentials } from "./routes.js";
export { buildMcpServer, resolveAuth, invokeWithToken, translateResponse } from "./invocation.js";
export type { InvokeResult, BuildMcpServerOptions } from "./invocation.js";
```

- [ ] **Step 5: Run existing tests to verify no regression**

Run: `cd packages/typescript/mcp && npx vitest run`
Expected: All 7 existing tests pass

- [ ] **Step 6: Commit**

```bash
git add packages/typescript/mcp/src/
git commit -m "refactor(mcp): extract shared invocation core and buildMcpServer"
```

---

## Chunk 2: @anip/mcp-hono

### Task 2: Scaffold and implement @anip/mcp-hono

**Files:**
- Create: `packages/typescript/mcp-hono/package.json`
- Create: `packages/typescript/mcp-hono/tsconfig.json`
- Create: `packages/typescript/mcp-hono/src/index.ts`
- Create: `packages/typescript/mcp-hono/tests/mcp-hono.test.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@anip/mcp-hono",
  "version": "0.8.0",
  "description": "ANIP MCP Streamable HTTP transport for Hono",
  "type": "module",
  "engines": { "node": ">=20" },
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": { "build": "tsc", "test": "vitest run" },
  "dependencies": {
    "@anip/mcp": "0.8.0",
    "@anip/service": "0.8.0",
    "@modelcontextprotocol/sdk": "^1.12.0",
    "hono": "^4.0.0"
  },
  "devDependencies": {
    "@anip/core": "0.8.0",
    "@anip/server": "0.8.0",
    "@anip/hono": "0.8.0",
    "typescript": "^5.5.0",
    "vitest": "^4.1.0"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

Same as other packages — ES2022, NodeNext, strict.

- [ ] **Step 3: Create src/index.ts**

```typescript
/**
 * ANIP MCP Streamable HTTP transport for Hono.
 *
 * Uses WebStandardStreamableHTTPServerTransport (Web Standard APIs).
 */
import type { Hono } from "hono";
import type { ANIPService } from "@anip/service";
import { buildMcpServer } from "@anip/mcp";
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
): Promise<void> {
  const mcpPath = opts?.path ?? "/mcp";

  // Build MCP Server with tools — HTTP mode (no callToolHandler = uses authInfo)
  const server = buildMcpServer(service, {
    enrichDescriptions: opts?.enrichDescriptions,
  });

  // Create transport once at mount time
  const transport = new WebStandardStreamableHTTPServerTransport({
    sessionIdGenerator: undefined, // stateless
  });
  await server.connect(transport);

  // Forward all requests on the MCP path to the transport
  app.all(`${mcpPath}`, async (c) => {
    const authHeader = c.req.header("authorization");
    const token = authHeader?.startsWith("Bearer ") ? authHeader.slice(7).trim() : undefined;
    return transport.handleRequest(c.req.raw, {
      authInfo: token ? { token, clientId: "", scopes: [] } : undefined,
    });
  });
}
```

- [ ] **Step 4: Add "mcp-hono" to workspaces in packages/typescript/package.json**

- [ ] **Step 5: Install and build**

Run: `cd packages/typescript && npm install && cd mcp-hono && npx tsc`

- [ ] **Step 6: Write tests**

```typescript
import { describe, it, expect } from "vitest";
import { Hono } from "hono";
import { createANIPService, defineCapability } from "@anip/service";
import { InMemoryStorage } from "@anip/server";
import type { CapabilityDeclaration } from "@anip/core";
import { mountAnip } from "@anip/hono";
import { mountAnipMcpHono } from "../src/index.js";

const API_KEY = "test-key-123";

function greetCap() {
  return defineCapability({
    declaration: {
      name: "greet",
      description: "Say hello",
      contract_version: "1.0",
      inputs: [{ name: "name", type: "string", required: true, description: "Who" }],
      output: { type: "object", fields: ["message"] },
      side_effect: { type: "read", rollback_window: "not_applicable" },
      minimum_scope: ["greet"],
      response_modes: ["unary"],
    } as CapabilityDeclaration,
    handler: (_ctx, params) => ({ message: `Hello, ${params.name}!` }),
  });
}

async function makeApp() {
  const service = createANIPService({
    serviceId: "test-mcp-http",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const app = new Hono();
  const { shutdown } = await mountAnip(app, service);
  await mountAnipMcpHono(app, service);
  return { app, shutdown };
}

describe("MCP Streamable HTTP (Hono)", () => {
  it("POST /mcp with initialize returns success", async () => {
    const { app, shutdown } = await makeApp();
    const res = await app.request("/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: {
          protocolVersion: "2024-11-05",
          capabilities: {},
          clientInfo: { name: "test", version: "1.0" },
        },
      }),
    });
    expect(res.status).toBe(200);
    await shutdown();
  });

  it("POST /mcp with tools/list returns tools", async () => {
    const { app, shutdown } = await makeApp();
    // Initialize first
    await app.request("/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0", id: 1, method: "initialize",
        params: { protocolVersion: "2024-11-05", capabilities: {}, clientInfo: { name: "test", version: "1.0" } },
      }),
    });

    const res = await app.request("/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} }),
    });
    expect(res.status).toBe(200);
    // Response may be SSE or JSON depending on transport mode
    const text = await res.text();
    expect(text).toContain("greet");
    await shutdown();
  });

  it("POST /mcp with tools/call and valid API key returns result", async () => {
    const { app, shutdown } = await makeApp();
    // Initialize
    await app.request("/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0", id: 1, method: "initialize",
        params: { protocolVersion: "2024-11-05", capabilities: {}, clientInfo: { name: "test", version: "1.0" } },
      }),
    });

    const res = await app.request("/mcp", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${API_KEY}`,
      },
      body: JSON.stringify({
        jsonrpc: "2.0", id: 3, method: "tools/call",
        params: { name: "greet", arguments: { name: "World" } },
      }),
    });
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toContain("Hello, World!");
    await shutdown();
  });

  it("POST /mcp with tools/call without auth returns error", async () => {
    const { app, shutdown } = await makeApp();
    // Initialize
    await app.request("/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0", id: 1, method: "initialize",
        params: { protocolVersion: "2024-11-05", capabilities: {}, clientInfo: { name: "test", version: "1.0" } },
      }),
    });

    const res = await app.request("/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0", id: 3, method: "tools/call",
        params: { name: "greet", arguments: { name: "World" } },
      }),
    });
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toContain("authentication_required");
    await shutdown();
  });
});
```

**Note:** The exact response format depends on the Streamable HTTP transport — it may return SSE events or JSON. Tests assert on the response text containing the expected content. The implementer should adapt assertions if the transport returns structured JSON-RPC responses differently than expected. Check how `WebStandardStreamableHTTPServerTransport` formats responses and adjust.

- [ ] **Step 7: Run tests**

Run: `cd packages/typescript/mcp-hono && npx vitest run`
Expected: All tests pass. If transport initialization requires specific protocol flow, adapt the tests to match.

- [ ] **Step 8: Commit**

```bash
git add packages/typescript/mcp-hono/ packages/typescript/package.json
git commit -m "feat(mcp-hono): add MCP Streamable HTTP transport for Hono"
```

---

## Chunk 3: @anip/mcp-express and @anip/mcp-fastify

### Task 3: Implement @anip/mcp-express

**Files:**
- Create: `packages/typescript/mcp-express/package.json`
- Create: `packages/typescript/mcp-express/tsconfig.json`
- Create: `packages/typescript/mcp-express/src/index.ts`
- Create: `packages/typescript/mcp-express/tests/mcp-express.test.ts`

Same pattern as mcp-hono but using `StreamableHTTPServerTransport` (Node wrapper). Auth goes on `req.auth` before calling `handleRequest`.

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@anip/mcp-express",
  "version": "0.8.0",
  "description": "ANIP MCP Streamable HTTP transport for Express",
  "type": "module",
  "engines": { "node": ">=20" },
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": { "build": "tsc", "test": "vitest run" },
  "dependencies": {
    "@anip/mcp": "0.8.0",
    "@anip/service": "0.8.0",
    "@modelcontextprotocol/sdk": "^1.12.0"
  },
  "devDependencies": {
    "@anip/core": "0.8.0",
    "@anip/server": "0.8.0",
    "@anip/express": "0.8.0",
    "express": "^4.18.0",
    "@types/express": "^4.17.0",
    "typescript": "^5.5.0",
    "vitest": "^4.1.0",
    "supertest": "^7.0.0",
    "@types/supertest": "^6.0.0"
  }
}
```

- [ ] **Step 2: Create src/index.ts**

```typescript
import type { Express } from "express";
import type { ANIPService } from "@anip/service";
import { buildMcpServer } from "@anip/mcp";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

export interface McpExpressOptions {
  path?: string;
  enrichDescriptions?: boolean;
}

export async function mountAnipMcpExpress(
  app: Express,
  service: ANIPService,
  opts?: McpExpressOptions,
): Promise<void> {
  const mcpPath = opts?.path ?? "/mcp";

  const server = buildMcpServer(service, {
    enrichDescriptions: opts?.enrichDescriptions,
  });

  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  await server.connect(transport);

  app.all(mcpPath, (req, res) => {
    const authHeader = req.headers.authorization;
    const token = authHeader?.startsWith("Bearer ") ? authHeader.slice(7).trim() : undefined;
    if (token) {
      (req as any).auth = { token, clientId: "", scopes: [] };
    }
    transport.handleRequest(req, res);
  });
}
```

- [ ] **Step 3: Write tests using supertest**

Same test cases as Hono but using Express + supertest.

- [ ] **Step 4: Add "mcp-express" to workspaces, install, build, test**

- [ ] **Step 5: Commit**

```bash
git add packages/typescript/mcp-express/ packages/typescript/package.json
git commit -m "feat(mcp-express): add MCP Streamable HTTP transport for Express"
```

---

### Task 4: Implement @anip/mcp-fastify

**Files:**
- Create: `packages/typescript/mcp-fastify/package.json`
- Create: `packages/typescript/mcp-fastify/tsconfig.json`
- Create: `packages/typescript/mcp-fastify/src/index.ts`
- Create: `packages/typescript/mcp-fastify/tests/mcp-fastify.test.ts`

- [ ] **Step 1: Create package.json**

Same as Express but with `fastify` instead of `express`.

- [ ] **Step 2: Create src/index.ts**

```typescript
import type { FastifyInstance } from "fastify";
import type { ANIPService } from "@anip/service";
import { buildMcpServer } from "@anip/mcp";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

export interface McpFastifyOptions {
  path?: string;
  enrichDescriptions?: boolean;
}

export async function mountAnipMcpFastify(
  app: FastifyInstance,
  service: ANIPService,
  opts?: McpFastifyOptions,
): Promise<void> {
  const mcpPath = opts?.path ?? "/mcp";

  const server = buildMcpServer(service, {
    enrichDescriptions: opts?.enrichDescriptions,
  });

  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  await server.connect(transport);

  app.all(mcpPath, (request, reply) => {
    const authHeader = request.headers.authorization;
    const token = typeof authHeader === "string" && authHeader.startsWith("Bearer ")
      ? authHeader.slice(7).trim() : undefined;
    if (token) {
      (request.raw as any).auth = { token, clientId: "", scopes: [] };
    }
    transport.handleRequest(request.raw, reply.raw);
  });
}
```

- [ ] **Step 3: Write tests using Fastify's inject()**

Same test cases as Hono/Express but using Fastify.

- [ ] **Step 4: Add "mcp-fastify" to workspaces, install, build, test**

- [ ] **Step 5: Commit**

```bash
git add packages/typescript/mcp-fastify/ packages/typescript/package.json
git commit -m "feat(mcp-fastify): add MCP Streamable HTTP transport for Fastify"
```

---

## Chunk 4: Python HTTP Transport

### Task 5: Extract Python invocation.py

**Files:**
- Create: `packages/python/anip-mcp/src/anip_mcp/invocation.py`
- Modify: `packages/python/anip-mcp/src/anip_mcp/routes.py`

Extract `_translate_response` into `invocation.py`, add `resolve_auth` and `invoke_with_token`. Refactor `routes.py` to import from it.

- [ ] **Step 1: Create invocation.py**

```python
"""Shared ANIP MCP invocation core.

Used by both stdio (routes.py) and HTTP (http.py).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from anip_service import ANIPService, ANIPError


@dataclass
class InvokeResult:
    text: str
    is_error: bool


async def resolve_auth(
    bearer: str,
    service: ANIPService,
    capability_name: str,
):
    """Resolve auth from a bearer token. JWT-first, API-key fallback."""
    jwt_error = None
    try:
        return await service.resolve_bearer_token(bearer)
    except ANIPError as e:
        jwt_error = e

    principal = await service.authenticate_bearer(bearer)
    if principal:
        cap_decl = service.get_capability_declaration(capability_name)
        min_scope = cap_decl.minimum_scope if cap_decl else []
        token_result = await service.issue_token(principal, {
            "subject": "adapter:anip-mcp",
            "scope": min_scope if min_scope else ["*"],
            "capability": capability_name,
            "purpose_parameters": {"source": "mcp"},
        })
        jwt_str = token_result["token"]
        return await service.resolve_bearer_token(jwt_str)

    if jwt_error:
        raise jwt_error
    raise ANIPError("authentication_required", "No valid bearer credential provided")


async def invoke_with_token(
    service: ANIPService,
    capability_name: str,
    args: dict[str, Any],
    token,
) -> InvokeResult:
    """Invoke a capability with an already-resolved delegation token."""
    try:
        result = await service.invoke(capability_name, token, args)
        return translate_response(result)
    except ANIPError as e:
        return InvokeResult(
            text=f"FAILED: {e.error_type}\nDetail: {e.detail}\nRetryable: no",
            is_error=True,
        )


def translate_response(response: dict[str, Any]) -> InvokeResult:
    """Translate an ANIP invoke response to MCP text format."""
    if response.get("success"):
        result = response.get("result", {})
        parts = [json.dumps(result, indent=2, default=str)]
        cost_actual = response.get("cost_actual")
        if cost_actual:
            financial = cost_actual.get("financial", {})
            amount = financial.get("amount")
            currency = financial.get("currency", "USD")
            if amount is not None:
                parts.append(f"\n[Cost: {currency} {amount}]")
        return InvokeResult(text="".join(parts), is_error=False)

    failure = response.get("failure", {})
    parts = [
        f"FAILED: {failure.get('type', 'unknown')}",
        f"Detail: {failure.get('detail', 'no detail')}",
    ]
    resolution = failure.get("resolution", {})
    if resolution:
        parts.append(f"Resolution: {resolution.get('action', '')}")
        if resolution.get("requires"):
            parts.append(f"Requires: {resolution['requires']}")
    parts.append(f"Retryable: {'yes' if failure.get('retry') else 'no'}")
    return InvokeResult(text="\n".join(parts), is_error=True)
```

- [ ] **Step 2: Refactor routes.py to import from invocation.py**

Replace `_translate_response` and `_invoke_capability` to use the shared functions. Keep `invoke_with_mount_credentials` (renamed from `_invoke_capability`) as the stdio-specific path.

- [ ] **Step 3: Run existing tests**

Run: `pytest packages/python/anip-mcp/tests/ -v`
Expected: All existing tests pass

- [ ] **Step 4: Commit**

```bash
git add packages/python/anip-mcp/src/anip_mcp/
git commit -m "refactor(mcp): extract shared Python invocation core"
```

---

### Task 6: Implement Python HTTP mount

**Files:**
- Create: `packages/python/anip-mcp/src/anip_mcp/http.py`
- Modify: `packages/python/anip-mcp/src/anip_mcp/__init__.py`
- Create: `packages/python/anip-mcp/tests/test_http.py`

- [ ] **Step 1: Create http.py**

```python
"""ANIP MCP Streamable HTTP transport for FastAPI."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import Response

from anip_service import ANIPService
from .invocation import resolve_auth, invoke_with_token, translate_response, InvokeResult

# The implementer should check what the Python mcp library exposes for
# Streamable HTTP transport and adapt this module accordingly.
# Expected: mcp.server.streamable_http.StreamableHTTPServerTransport
# The module should:
# 1. Create an MCP Server with tools from the ANIPService
# 2. Create a StreamableHTTPServerTransport (stateless)
# 3. Connect server to transport once at mount time
# 4. Mount GET/POST/DELETE handlers on the FastAPI app at the given path
# 5. Extract bearer from Authorization header per-request
# 6. Pass auth context to the transport


def mount_anip_mcp_http(
    app: FastAPI,
    service: ANIPService,
    *,
    path: str = "/mcp",
    enrich_descriptions: bool = True,
) -> None:
    """Mount MCP Streamable HTTP transport on a FastAPI app.

    Does not own service lifecycle — mount_anip() handles that.
    """
    # Implementation depends on the Python mcp library's StreamableHTTPServerTransport API.
    # The implementer should:
    # 1. Import from mcp.server.streamable_http
    # 2. Build MCP server with tool handlers that use resolve_auth + invoke_with_token
    # 3. Create transport, connect server
    # 4. Mount request handlers on the FastAPI app
    raise NotImplementedError(
        "Python MCP Streamable HTTP transport — "
        "implement using mcp.server.streamable_http.StreamableHTTPServerTransport"
    )
```

**Note:** The Python `mcp` library's Streamable HTTP API may differ from TypeScript. The implementer should check `mcp.server.streamable_http` for the actual class interface and adapt. The core logic (resolve_auth, invoke_with_token, translate_response) is already extracted and ready to use.

- [ ] **Step 2: Update __init__.py**

Add `mount_anip_mcp_http` to exports.

- [ ] **Step 3: Write tests**

Follow the FastAPI TestClient pattern. Tests should cover:
- POST /mcp with initialize
- tools/list
- tools/call with valid auth
- tools/call without auth

The implementer should adapt test structure to match the actual transport behavior.

- [ ] **Step 4: Commit**

```bash
git add packages/python/anip-mcp/
git commit -m "feat(mcp): add Python MCP Streamable HTTP transport for FastAPI"
```

---

## Chunk 5: CI and Cleanup

### Task 7: Update CI workflows

**Files:**
- Modify: `.github/workflows/ci-typescript.yml`
- Modify: `.github/workflows/ci-python.yml`

- [ ] **Step 1: Add mcp-hono, mcp-express, mcp-fastify to TypeScript CI**

Add build steps (`npx tsc -p mcp-hono/tsconfig.json`, etc.) and test steps (`npm test --workspace=@anip/mcp-hono`, etc.).

- [ ] **Step 2: Python CI already covers anip-mcp — verify http.py tests are picked up**

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/
git commit -m "ci: add MCP HTTP transport packages to CI"
```
