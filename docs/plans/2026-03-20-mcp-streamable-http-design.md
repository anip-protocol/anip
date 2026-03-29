# MCP Streamable HTTP Transport Design

**Goal:** Add HTTP transport support to the MCP packages so ANIP-backed MCP servers are usable over the network, not just stdio.

**Architecture:** The existing `@anip-dev/mcp` package gains a shared invocation core. Three new thin framework packages (`@anip-dev/mcp-hono`, `@anip-dev/mcp-express`, `@anip-dev/mcp-fastify`) mount the MCP SDK's Streamable HTTP transport on their respective framework apps. Python's `anip-mcp` gains an `http.py` module for FastAPI. Auth is per-request from `Authorization: Bearer` headers — same JWT-first, API-key-fallback pattern as REST and GraphQL.

**Tech Stack:** TypeScript (`@modelcontextprotocol/sdk` Streamable HTTP transports, `@anip-dev/service`, Hono/Express/Fastify), Python (`mcp` StreamableHTTPServerTransport, `anip-service`, FastAPI)

---

## Transport Choice

MCP Streamable HTTP, not legacy SSE. The MCP SDK deprecated standalone SSE (`SSEServerTransport`) as of protocol version 2024-11-05. Streamable HTTP is the recommended transport for remote MCP servers — it still uses SSE under the hood for streaming but adds proper session management, resumability, and protocol version negotiation.

## Package Structure

### TypeScript

| Package | Purpose | Depends On |
|---------|---------|------------|
| `@anip-dev/mcp` | Shared core: translation, invocation/auth bridge, stdio mount | `@anip-dev/service`, `@modelcontextprotocol/sdk` |
| `@anip-dev/mcp-hono` | Hono Streamable HTTP mount (`WebStandardStreamableHTTPServerTransport`) | `@anip-dev/mcp`, `hono` |
| `@anip-dev/mcp-express` | Express Streamable HTTP mount (`StreamableHTTPServerTransport`) | `@anip-dev/mcp`, `express` |
| `@anip-dev/mcp-fastify` | Fastify Streamable HTTP mount (`StreamableHTTPServerTransport`) | `@anip-dev/mcp`, `fastify` |

```
packages/typescript/mcp/src/
├── index.ts              # re-exports: mountAnipMcp (stdio), shared types, buildMcpServer
├── translation.ts        # unchanged — capability → tool schema
├── invocation.ts         # NEW — shared resolveAuth, invokeWithToken, translateResponse
└── routes.ts             # stdio mount (refactored to use invocation.ts)

packages/typescript/mcp-hono/src/
└── index.ts              # mountAnipMcpHono(app, service, opts?) — Web Standard transport

packages/typescript/mcp-express/src/
└── index.ts              # mountAnipMcpExpress(app, service, opts?) — Node wrapper transport

packages/typescript/mcp-fastify/src/
└── index.ts              # mountAnipMcpFastify(app, service, opts?) — Node wrapper transport
```

Hono uses `WebStandardStreamableHTTPServerTransport` (Web Standard APIs — native fit, zero adapter overhead). Express and Fastify use `StreamableHTTPServerTransport` (Node.js wrapper around the same core).

### Python

Single package — Python has no multi-framework split in this repo.

```
packages/python/anip-mcp/src/anip_mcp/
├── __init__.py           # adds mount_anip_mcp_http export
├── translation.py        # unchanged
├── invocation.py         # NEW — shared resolveAuth, invokeWithToken, translateResponse
├── routes.py             # stdio mount (refactored to use invocation.py)
└── http.py               # NEW — mount_anip_mcp_http(app, service) for FastAPI
```

## Public API

### TypeScript

```typescript
// Hono — all interfaces on one server
import { mountAnip } from "@anip-dev/hono";
import { mountAnipMcpHono } from "@anip-dev/mcp-hono";

const app = new Hono();
await mountAnip(app, service);              // ANIP protocol (owns lifecycle)
await mountAnipMcpHono(app, service);       // MCP Streamable HTTP at /mcp
```

```typescript
// Express
import { mountAnipMcpExpress } from "@anip-dev/mcp-express";
await mountAnipMcpExpress(app, service);    // MCP Streamable HTTP at /mcp
```

```typescript
// Fastify
import { mountAnipMcpFastify } from "@anip-dev/mcp-fastify";
await mountAnipMcpFastify(app, service);    // MCP Streamable HTTP at /mcp
```

**Mount signature (all three):**
```typescript
async function mountAnipMcp*(
  app: Hono | Express | FastifyInstance,
  service: ANIPService,
  opts?: { path?: string },  // default: "/mcp"
): Promise<void>;
```

No lifecycle return — these don't own service lifecycle (same as `mountAnipRest`, `mountAnipGraphQL`).

### Python

```python
from anip_mcp.http import mount_anip_mcp_http

app = FastAPI()
mount_anip(app, service)              # ANIP protocol (owns lifecycle)
mount_anip_mcp_http(app, service)     # MCP Streamable HTTP at /mcp
```

## Shared Invocation Core

Extracted from the current `routes.ts` into `invocation.ts` / `invocation.py`.

### Shared functions (used by both stdio and HTTP):

- **`invokeWithToken(service, capabilityName, args, token)`** → `InvokeResult` — invoke capability with an already-resolved delegation token, translate response
- **`translateResponse(response)`** → `{ text: string, isError: boolean }` — ANIP response → MCP text with error flag

### HTTP-only:

- **`resolveAuth(bearer, service, capabilityName)`** → `DelegationToken` — JWT-first, API-key fallback. Same pattern as REST/GraphQL: try `resolveBearerToken` first, stash `ANIPError`, fall back to `authenticateBearer` + synthetic token, re-throw JWT error if API key also fails. Only catches `ANIPError`, rethrows unexpected errors.

### stdio-only (stays in `routes.ts`):

- **`invokeWithMountCredentials(service, capabilityName, args, credentials)`** → `InvokeResult` — issues synthetic token from mount-time config, then calls `invokeWithToken`

### Call paths:

```
HTTP:   request → extract Bearer → resolveAuth() → invokeWithToken() → MCP response
stdio:  tool call → invokeWithMountCredentials(credentials) → invokeWithToken() → MCP response
```

Both converge at `invokeWithToken`. The auth boundary is explicit.

## Credential Model

**HTTP mode:** per-request from `Authorization: Bearer` header. Stateless — no session tracking. Each tool call authenticates independently.

- JWT bearer → `resolveBearerToken()` → `DelegationToken` (preserves delegation chain)
- API key bearer → `authenticateBearer()` → synthetic token scoped to the capability (subject: `"adapter:anip-mcp"`, scope from `minimum_scope`, purpose: `{ source: "mcp" }`)

**stdio mode:** unchanged — mount-time credentials, synthetic token per call.

## Transport Wiring

Transport and MCP Server are created **once at mount time**, not per-request.

### How auth context reaches tool handlers

The MCP SDK's `handleRequest(req, options?)` accepts `HandleRequestOptions` which includes `authInfo?: AuthInfo`. The SDK passes this through to tool call handlers via the `extra.authInfo` parameter on `setRequestHandler` callbacks.

The flow:
1. Framework route handler extracts `Authorization: Bearer` from the HTTP request
2. Passes `{ authInfo: { token: bearerValue, clientId: "", scopes: [] } }` to `transport.handleRequest(req, { authInfo })`
3. Transport forwards `authInfo` to the MCP Server's `CallToolRequest` handler via `extra.authInfo`
4. Tool handler reads `extra.authInfo.token` and calls `resolveAuth(bearer, service, capabilityName)` to get a `DelegationToken`

This means `buildMcpServer` registers tool handlers that accept `(request, extra)` and resolve auth from `extra.authInfo.token`. The framework packages only need to extract the bearer and pass it as `authInfo` — they don't resolve ANIP auth themselves.

### Hono (Web Standard transport):

```typescript
export async function mountAnipMcpHono(
  app: Hono, service: ANIPService, opts?: { path?: string }
): Promise<void> {
  const mcpPath = opts?.path ?? "/mcp";

  // Mount time — once
  const server = buildMcpServer(service);  // shared: creates MCP Server, registers tools with auth-aware handlers
  const transport = new WebStandardStreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  await server.connect(transport);

  // Request time — extract bearer, forward to transport with authInfo
  app.all(`${mcpPath}`, async (c) => {
    const authHeader = c.req.header("authorization");
    const token = authHeader?.startsWith("Bearer ") ? authHeader.slice(7).trim() : undefined;
    return transport.handleRequest(c.req.raw, {
      authInfo: token ? { token, clientId: "", scopes: [] } : undefined,
    });
  });
}
```

### Express (Node.js wrapper):

Uses `StreamableHTTPServerTransport` which wraps the Web Standard transport for Node.js `IncomingMessage`/`ServerResponse`. The SDK also ships `createMcpExpressApp()` but that creates a standalone Express app with DNS rebinding protection — not useful here since we're mounting on an existing app. Instead, we use `StreamableHTTPServerTransport` directly.

**Auth mechanism:** The Node wrapper's `handleRequest` signature is `(req: IncomingMessage & { auth?: AuthInfo }, res, parsedBody?)`. Auth is read from `req.auth`, not from an options object. The framework sets `req.auth` before calling `handleRequest`.

```typescript
export async function mountAnipMcpExpress(
  app: Express, service: ANIPService, opts?: { path?: string }
): Promise<void> {
  const mcpPath = opts?.path ?? "/mcp";

  const server = buildMcpServer(service);
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  await server.connect(transport);

  app.all(mcpPath, (req, res) => {
    const authHeader = req.headers.authorization;
    const token = authHeader?.startsWith("Bearer ") ? authHeader.slice(7).trim() : undefined;
    // Node wrapper reads auth from req.auth, not an options object
    if (token) {
      (req as any).auth = { token, clientId: "", scopes: [] };
    }
    transport.handleRequest(req, res);
  });
}
```

### Fastify (Node.js wrapper):

Fastify encapsulates Node.js `req`/`res` behind its own request/reply objects. To use `StreamableHTTPServerTransport`, the handler accesses Fastify's raw Node.js objects via `request.raw` and `reply.raw`. Auth is set on `request.raw.auth` (the raw `IncomingMessage`).

```typescript
export async function mountAnipMcpFastify(
  app: FastifyInstance, service: ANIPService, opts?: { path?: string }
): Promise<void> {
  const mcpPath = opts?.path ?? "/mcp";

  const server = buildMcpServer(service);
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  await server.connect(transport);

  app.all(mcpPath, (request, reply) => {
    const authHeader = request.headers.authorization;
    const token = typeof authHeader === "string" && authHeader.startsWith("Bearer ")
      ? authHeader.slice(7).trim() : undefined;
    // Set auth on raw Node.js IncomingMessage — Node wrapper reads req.auth
    if (token) {
      (request.raw as any).auth = { token, clientId: "", scopes: [] };
    }
    transport.handleRequest(request.raw, reply.raw);
  });
}
```

### Python (FastAPI):

```python
def mount_anip_mcp_http(app: FastAPI, service: ANIPService, *, path: str = "/mcp") -> None:
    # Uses mcp.server.streamable_http.StreamableHTTPServerTransport
    # Creates transport + server once at mount time
    # Extracts bearer from request, passes as auth_info to transport
    # Mounts GET/POST/DELETE handlers on the FastAPI app at the given path
```

## What Changes in `@anip-dev/mcp`

### Refactored (not new logic, just extracted):

- `invocation.ts` — `resolveAuth`, `invokeWithToken`, `translateResponse` extracted from current `routes.ts`
- `routes.ts` — stdio mount refactored to use `invocation.ts` (keeps `invokeWithMountCredentials`)

### New exports from `@anip-dev/mcp`:

- `buildMcpServer(service, opts?)` — creates an MCP `Server` with tools registered from the ANIPService. Used by all framework packages.
- `resolveAuth`, `invokeWithToken`, `translateResponse` — shared by HTTP framework packages
- Types: `InvokeResult`, `McpCredentials` (for stdio)

### Unchanged:

- `translation.ts` — capability → tool schema, description enrichment
- `mountAnipMcp` — stdio mount function (signature unchanged, internal refactor only)

## Testing

### Per framework package (`mcp-hono`, `mcp-express`, `mcp-fastify`):

Tests are end-to-end at the transport level using the real MCP Client SDK for faithful Streamable HTTP protocol flow:

- **Tool listing** — client connects, lists tools, gets registered capabilities
- **Authenticated tool call** — valid Bearer, invokes ANIP capability, returns result
- **Invalid auth** — invalid Bearer returns structured failure with `isError: true`
- **Unknown tool** — returns error
- **Cleanup/lifecycle** — mount, send requests, close/shutdown app, confirm no transport crash or double-connect

TypeScript tests: Hono `app.request()`, supertest for Express, Fastify `inject()`.
Python tests: FastAPI `TestClient`.

### Shared core (`@anip-dev/mcp`):

- `resolveAuth` — JWT success, API key fallback, invalid bearer re-throws `ANIPError`
- `invokeWithToken` — success result, failure result with `isError`
- `translateResponse` — success/failure text formatting
- Existing stdio tests continue to pass (regression)

## What This Does NOT Cover

- Changes to ANIP wire protocol
- Provider-specific auth integrations (OIDC, OAuth)
- ANIP version bump
- Session-bound auth (deferred — per-request is the first model)
- Rewriting the stdio credential model
- Resumability / EventStore (can be added later)
- Legacy SSE backward compatibility (deferred unless there's demand)
