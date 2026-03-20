# Adapter-to-Package Conversion Design

**Goal:** Convert the 6 standalone adapters (`adapters/mcp-*`, `adapters/rest-*`, `adapters/graphql-*`) into reusable library packages under `packages/`, following the same `mountAnip` pattern as existing framework bindings.

**Architecture:** Each new package takes an `ANIPService` instance directly and mounts protocol-specific endpoints on a framework app (or MCP server). No HTTP discovery, no remote proxying — capabilities are invoked via `service.invoke()` in-process.

**Tech Stack:** TypeScript (Hono for HTTP, `@modelcontextprotocol/sdk` for MCP, `graphql` for GraphQL), Python (FastAPI, `mcp`, `ariadne` for GraphQL)

---

## New Packages

| Package | Language | Location | Depends On |
|---------|----------|----------|------------|
| `@anip/mcp` | TypeScript | `packages/typescript/mcp/` | `@anip/service`, `@modelcontextprotocol/sdk` |
| `anip-mcp` | Python | `packages/python/anip-mcp/` | `anip-service`, `mcp` |
| `@anip/rest` | TypeScript | `packages/typescript/rest/` | `@anip/service`, `hono` |
| `anip-rest` | Python | `packages/python/anip-rest/` | `anip-service`, `fastapi` |
| `@anip/graphql` | TypeScript | `packages/typescript/graphql/` | `@anip/service`, `hono`, `graphql` |
| `anip-graphql` | Python | `packages/python/anip-graphql/` | `anip-service`, `fastapi`, `ariadne` |

## Public API

All packages follow the existing binding pattern: you bring the framework instance, the package registers on it.

### REST & GraphQL (mount on HTTP app)

```typescript
// TypeScript — single server, all interfaces
const app = new Hono();
const service = createANIPService({ ... });

mountAnip(app, service);              // @anip/hono — ANIP protocol routes
mountAnipRest(app, service);          // @anip/rest — /api/* REST endpoints
mountAnipGraphQL(app, service);       // @anip/graphql — /graphql endpoint

serve(app, { port: 4100 });
```

```python
# Python — same pattern
app = FastAPI()
service = ANIPService(...)

mount_anip(app, service)              # anip-fastapi
mount_anip_rest(app, service)         # anip-rest
mount_anip_graphql(app, service)      # anip-graphql

uvicorn.run(app, port=8090)
```

### MCP (two transport modes)

**SSE (remote) — mounts on HTTP app alongside other interfaces:**

```typescript
mountAnipMcp(app, service);           // @anip/mcp — /mcp SSE endpoint
```

**stdio (local) — mounts on MCP Server for CLI/IDE use:**

```typescript
const mcpServer = new Server({ name: "flights", version: "1.0" });
mountAnipMcp(mcpServer, service);
await mcpServer.connect(new StdioServerTransport());
```

### REST Route Overrides

REST supports custom route configuration for proper RESTful semantics:

```typescript
mountAnipRest(app, service, {
  routes: {
    search_flights: { path: "/api/flights", method: "GET" },
    book_flight: { path: "/api/bookings", method: "POST" },
  }
});
```

Without overrides, defaults to `/api/{capability_name}` with GET for read, POST for write/irreversible.

## Internal Architecture

Each package has three responsibilities:

### 1. Translation

Convert ANIP `CapabilityDeclaration` to the target protocol's schema:

- **REST:** capability → OpenAPI 3.1 spec with `x-anip-*` extensions
- **GraphQL:** capability → SDL with types, queries (read), mutations (write), custom directives
- **MCP:** capability → MCP tool with JSON Schema inputs and enriched descriptions

Translation modules are largely reused from the current adapters — the logic doesn't change.

### 2. Route/Handler Registration

Mount endpoints on the framework instance:

- **REST:** `/api/{capability}` routes, `/openapi.json`, `/docs`
- **GraphQL:** `/graphql` endpoint with resolvers, `/schema.graphql` for SDL
- **MCP (SSE):** `/mcp` endpoint on HTTP app
- **MCP (stdio):** `list_tools` and `call_tool` handlers on MCP `Server`

### 3. Invocation Bridge

Current adapters:
```
HTTP request → issue token via HTTP → invoke via HTTP → translate response
```

New packages:
```
request → service.resolveBearerToken(jwt) → service.invoke(capability, token, params) → translate response
```

No network hop. No token issuance dance. Direct method calls on the `ANIPService` instance.

### Authentication

REST and GraphQL endpoints accept `Authorization: Bearer <token>` headers. The package calls `service.resolveBearerToken(jwt)` to get a `DelegationToken`, then passes it to `service.invoke()`. For API-key convenience, the package calls `service.authenticateBearer(apiKey)` then `service.issueToken()`.

MCP tools receive credentials through the MCP protocol context.

## What Changes

### Removed

- `adapters/` directory deleted entirely
- Remote HTTP discovery (`discover_service`)
- `ANIPInvoker` (HTTP-based invocation)
- Docker compose test infrastructure (`test-e2e.sh`)

### Preserved

- Translation modules (capability → OpenAPI/SDL/MCP tool schema)
- Description enrichment (side-effect warnings, cost estimates, prerequisites)
- REST route override configuration
- GraphQL camelCase convention and custom directives

### Added

- Direct `ANIPService` integration (in-process method calls)
- MCP SSE transport mountable on HTTP app
- Proper vitest/pytest test suites (same pattern as existing bindings)

## Example App Updates

Both example apps demonstrate one service exposed through all four interfaces:

```typescript
// examples/anip-ts/src/app.ts
import { mountAnip } from "@anip/hono";
import { mountAnipRest } from "@anip/rest";
import { mountAnipGraphQL } from "@anip/graphql";
import { mountAnipMcp } from "@anip/mcp";

const app = new Hono();
mountAnip(app, service);
mountAnipRest(app, service);
mountAnipGraphQL(app, service);
mountAnipMcp(app, service);
```

## Testing

Each package gets tests following the same pattern as existing bindings:

- Create a test service with a simple capability
- Test translation (capability → schema generation)
- Test invocation through the interface (REST endpoint, GraphQL query, MCP tool call)
- Test auth errors (no credentials, invalid token)
- Test unknown capability handling
- No Docker — in-process testing only
