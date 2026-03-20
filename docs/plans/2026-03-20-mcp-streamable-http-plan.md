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

The tests should use the real MCP Client SDK (`StreamableHTTPClientTransport` or `SSEClientTransport`) for faithful Streamable HTTP protocol flow. Since Hono's `app.request()` is a local test helper (not a real HTTP server), the implementer should either:

1. **Start a real HTTP server** using `@hono/node-server`'s `serve()`, connect the MCP Client SDK to it, run the protocol flow, then shut down.
2. If the MCP SDK exposes an in-memory transport for testing (like `InMemoryTransport` used in stdio tests), use that.

The implementer should check the MCP SDK for `StreamableHTTPClientTransport` or equivalent, start a local Hono server on a random port, and connect the MCP Client through the real transport.

**Test cases to implement:**

```typescript
// Pseudocode — adapt to actual MCP Client SDK API

describe("MCP Streamable HTTP (Hono)", () => {
  // Start real HTTP server, connect MCP Client, run protocol

  it("listTools returns registered tools", async () => {
    // client.listTools() → expect tools.length === 1, tools[0].name === "greet"
  });

  it("callTool with valid API key returns result", async () => {
    // Set Authorization header on client transport
    // client.callTool({ name: "greet", arguments: { name: "World" } })
    // → expect result contains "Hello, World!"
  });

  it("callTool without auth returns authentication_required", async () => {
    // No Authorization header
    // client.callTool(...) → expect isError + "authentication_required"
  });

  it("callTool with unknown tool returns error", async () => {
    // client.callTool({ name: "nonexistent", ... }) → expect isError
  });

  it("cleanup: server shuts down cleanly", async () => {
    // Close client, stop server, verify no errors
  });
});
```

The implementer MUST check the MCP SDK for the correct client transport class and adapt. The key requirement is that tests exercise the real Streamable HTTP protocol flow, not hand-crafted JSON-RPC.

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

  app.all(mcpPath, async (req, res, next) => {
    try {
      const authHeader = req.headers.authorization;
      const token = authHeader?.startsWith("Bearer ") ? authHeader.slice(7).trim() : undefined;
      if (token) {
        (req as any).auth = { token, clientId: "", scopes: [] };
      }
      await transport.handleRequest(req, res);
    } catch (err) {
      next(err);
    }
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

  app.all(mcpPath, async (request, reply) => {
    const authHeader = request.headers.authorization;
    const token = typeof authHeader === "string" && authHeader.startsWith("Bearer ")
      ? authHeader.slice(7).trim() : undefined;
    if (token) {
      (request.raw as any).auth = { token, clientId: "", scopes: [] };
    }
    await transport.handleRequest(request.raw, reply.raw);
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

The Python `mcp` library (v1.26+) provides `StreamableHTTPServerTransport` as an ASGI app. Key API:
- Constructor: `StreamableHTTPServerTransport(mcp_session_id=None)` — `None` for stateless mode
- `handle_request(scope, receive, send)` — ASGI entry point, handles GET/POST/DELETE
- `connect()` — async context manager yielding `(read_stream, write_stream)` for bidirectional message passing
- Auth context: `session_message.metadata.request_context` contains the Starlette `Request` object with headers

The transport is ASGI-native, so it mounts on FastAPI via `app.mount()`. The MCP Server runs in a background task, reading from the transport's message streams.

```python
"""ANIP MCP Streamable HTTP transport for FastAPI."""
from __future__ import annotations

import asyncio
from typing import Any

import mcp.types as mcp_types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http import StreamableHTTPServerTransport

from fastapi import FastAPI

from anip_service import ANIPService, ANIPError
from .invocation import resolve_auth, invoke_with_token, InvokeResult
from .translation import capability_to_input_schema, enrich_description


def mount_anip_mcp_http(
    app: FastAPI,
    service: ANIPService,
    *,
    path: str = "/mcp",
    enrich_descriptions: bool = True,
) -> None:
    """Mount MCP Streamable HTTP transport on a FastAPI app.

    Does not own service lifecycle — mount_anip() handles that.

    Creates an MCP Server with tools registered from the ANIPService,
    connects it to a StreamableHTTPServerTransport (stateless, ASGI),
    and mounts the transport on the FastAPI app at the given path.

    Auth is per-request: the tool call handler extracts Authorization
    from the Starlette Request in session_message.metadata.request_context,
    then resolves via resolve_auth (JWT-first, API-key fallback).
    """
    # Build tool map from service
    manifest = service.get_manifest()
    mcp_tools: dict[str, mcp_types.Tool] = {}
    tool_declarations: dict[str, Any] = {}

    for name in manifest.capabilities:
        decl = service.get_capability_declaration(name)
        if not decl:
            continue
        decl_dict = decl.model_dump()
        description = enrich_description(decl_dict) if enrich_descriptions else decl.description
        mcp_tools[name] = mcp_types.Tool(
            name=name,
            description=description,
            inputSchema=capability_to_input_schema(decl_dict),
        )

    # Create MCP Server with tool handlers
    mcp_server = Server("anip-mcp-http")

    @mcp_server.list_tools()
    async def handle_list_tools() -> list[mcp_types.Tool]:
        return list(mcp_tools.values())

    @mcp_server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict,
    ) -> list[mcp_types.TextContent]:
        if name not in mcp_tools:
            return [mcp_types.TextContent(
                type="text",
                text=f"Unknown tool: {name}. Available: {list(mcp_tools.keys())}",
            )]

        # Auth is resolved per-request from the HTTP context
        # The request_context is injected by the transport via
        # session_message.metadata — but for call_tool handlers registered
        # via decorators, the mcp library passes it through the server's
        # request_context. Check server.request_context for the Starlette Request.
        bearer = None
        ctx = mcp_server.request_context
        if ctx and hasattr(ctx, "request_context") and ctx.request_context:
            request = ctx.request_context
            auth_header = getattr(request, "headers", {}).get("authorization", "")
            if auth_header.startswith("Bearer "):
                bearer = auth_header[7:].strip()

        if not bearer:
            return [mcp_types.TextContent(
                type="text",
                text="FAILED: authentication_required\nDetail: No Authorization header\nRetryable: yes",
            )]

        try:
            token = await resolve_auth(bearer, service, name)
            result = await invoke_with_token(service, name, arguments or {}, token)
            return [mcp_types.TextContent(type="text", text=result.text)]
        except ANIPError as e:
            return [mcp_types.TextContent(
                type="text",
                text=f"FAILED: {e.error_type}\nDetail: {e.detail}\nRetryable: no",
            )]
        except Exception as e:
            return [mcp_types.TextContent(
                type="text",
                text=f"ANIP invocation error: {e}",
            )]

    # Create transport (stateless — no session ID)
    transport = StreamableHTTPServerTransport(mcp_session_id=None)

    # Start the MCP server message loop in a background task on app startup
    @app.on_event("startup")
    async def start_mcp():
        async def run_server():
            async with transport.connect() as (read_stream, write_stream):
                await mcp_server.run(
                    read_stream, write_stream,
                    mcp_server.create_initialization_options(),
                )
        asyncio.create_task(run_server())

    # Mount the ASGI transport on the FastAPI app
    app.mount(path, transport.handle_request)
```

**Note:** The exact way the `mcp` library's `Server` passes `request_context` to decorated handlers may vary. The implementer should verify how `server.request_context` works in the `mcp` library version installed (1.26+). If the server doesn't expose request context on `server.request_context`, check `mcp.server.lowlevel.Server` for the actual mechanism and adapt the bearer extraction accordingly.

- [ ] **Step 2: Update __init__.py**

```python
"""ANIP MCP bindings — expose ANIPService capabilities as MCP tools."""
from .routes import mount_anip_mcp, McpCredentials, McpLifecycle
from .http import mount_anip_mcp_http

__all__ = ["mount_anip_mcp", "McpCredentials", "McpLifecycle", "mount_anip_mcp_http"]
```

- [ ] **Step 3: Add pyproject.toml dependency**

Add `sse-starlette>=2.0` to dependencies (required by the mcp transport for SSE responses).

- [ ] **Step 4: Write tests**

```python
"""Tests for MCP Streamable HTTP transport on FastAPI."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anip_core import (
    CapabilityDeclaration, SideEffect, SideEffectType,
    CapabilityInput, CapabilityOutput,
)
from anip_service import ANIPService, Capability
from anip_fastapi import mount_anip
from anip_mcp.http import mount_anip_mcp_http

API_KEY = "test-key"


@pytest.fixture
def client():
    service = ANIPService(
        service_id="test-mcp-http",
        capabilities=[
            Capability(
                declaration=CapabilityDeclaration(
                    name="greet",
                    description="Say hello",
                    inputs=[CapabilityInput(name="name", type="string", required=True, description="Who")],
                    output=CapabilityOutput(type="object", fields=["message"]),
                    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                    minimum_scope=["greet"],
                ),
                handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
            ),
        ],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )
    app = FastAPI()
    mount_anip(app, service)
    mount_anip_mcp_http(app, service)
    return TestClient(app)


class TestMcpHttpTransport:
    def test_post_initialize(self, client):
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }, headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        })
        assert resp.status_code == 200

    def test_list_tools(self, client):
        # Initialize first
        client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}},
        }, headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"})

        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
        }, headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"})
        assert resp.status_code == 200
        assert "greet" in resp.text

    def test_call_tool_with_auth(self, client):
        # Initialize
        client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}},
        }, headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"})

        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "greet", "arguments": {"name": "World"}},
        }, headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        })
        assert resp.status_code == 200
        assert "Hello, World!" in resp.text

    def test_call_tool_without_auth(self, client):
        # Initialize
        client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}},
        }, headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"})

        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "greet", "arguments": {"name": "World"}},
        }, headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"})
        assert resp.status_code == 200
        assert "authentication_required" in resp.text
```

**Note:** The Python tests use direct JSON-RPC HTTP requests because the Python MCP Client SDK may not expose a Streamable HTTP client transport suitable for TestClient. The implementer should check if the `mcp` library has a client-side HTTP transport and use it if available. The important thing is that the protocol flow (initialize → list → call) is exercised through real HTTP.

- [ ] **Step 5: Run tests**

Run: `pytest packages/python/anip-mcp/tests/test_http.py -v`

- [ ] **Step 6: Commit**

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
