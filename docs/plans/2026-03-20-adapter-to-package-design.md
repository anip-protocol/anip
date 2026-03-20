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
| `@anip/rest` | TypeScript | `packages/typescript/rest/` | `@anip/service` (framework-agnostic translation core, framework adapters mirror `@anip/hono`/`@anip/express`/`@anip/fastify` split) |
| `anip-rest` | Python | `packages/python/anip-rest/` | `anip-service`, `fastapi` |
| `@anip/graphql` | TypeScript | `packages/typescript/graphql/` | `@anip/service` (same framework split as REST) |
| `anip-graphql` | Python | `packages/python/anip-graphql/` | `anip-service`, `fastapi`, `ariadne` |

## Public API

All packages follow the existing binding pattern: you bring the framework instance, the package registers on it.

**Framework split (TypeScript):** The existing ANIP protocol bindings support Hono, Express, and Fastify (`@anip/hono`, `@anip/express`, `@anip/fastify`). The new REST and GraphQL packages follow the same split — each has a framework-agnostic translation core plus thin framework adapters. Examples below use Hono; Express and Fastify equivalents (`mountAnipRest`, `mountAnipGraphQL`) follow the same signature pattern as `@anip/express`/`@anip/fastify`.

**Python** has a single framework (FastAPI) so no split is needed.

### REST & GraphQL (mount on HTTP app)

```typescript
// TypeScript — single server, all interfaces (Hono example)
const app = new Hono();
const service = createANIPService({ ... });

await mountAnip(app, service);              // @anip/hono — ANIP protocol routes
await mountAnipRest(app, service);          // @anip/rest — /api/* REST endpoints
await mountAnipGraphQL(app, service);       // @anip/graphql — /graphql endpoint

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
await mountAnipMcp(app, service);           // @anip/mcp — /mcp SSE endpoint
```

**stdio (local) — mounts on MCP Server for CLI/IDE use:**

```typescript
const mcpServer = new Server({ name: "flights", version: "1.0" });
await mountAnipMcp(mcpServer, service, {
  credentials: {
    apiKey: "demo-human-key",
    scope: ["travel.search", "travel.book"],
    subject: "agent:mcp-bridge",
  }
});
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

**REST and GraphQL** endpoints accept `Authorization: Bearer <token>` headers. Two modes:

1. **JWT mode (default):** The package calls `service.resolveBearerToken(jwt)` to get a `DelegationToken`, then passes it to `service.invoke()`. The caller is responsible for obtaining a token first via `POST /anip/tokens`.

2. **API-key convenience mode:** When a bearer credential resolves as an API key (via `service.authenticateBearer(apiKey)`), the package issues a synthetic token before invoking. The synthetic token uses these concrete policies (matching what the current adapters do today):
   - **subject:** `"adapter:{package-name}"` (e.g., `"adapter:anip-rest"`)
   - **scope:** derived from the target capability's `minimum_scope` declaration
   - **capability:** bound to the specific capability being invoked
   - **purpose_parameters:** `{ "source": "rest" }` or `{ "source": "graphql" }`

   These choices affect audit lineage — the synthetic subject appears in the delegation chain, and scope is narrowed to exactly what the capability requires.

**MCP** tools need credentials at mount time, not per-request (especially for stdio where there are no HTTP headers). The package accepts an explicit credential config:

```typescript
// SSE — credentials come from MCP protocol context headers
mountAnipMcp(app, service);

// stdio — credentials provided at mount time
mountAnipMcp(mcpServer, service, {
  credentials: {
    apiKey: "demo-human-key",
    scope: ["travel.search", "travel.book"],
    subject: "agent:mcp-bridge",
  }
});
```

For SSE transport, the MCP protocol context provides an auth header per-request. For stdio transport, the mount-time `credentials` config is required — it works identically to the current adapter's `bridge.yaml` delegation config. The package issues one token per tool call using these credentials, scoped to the specific capability being invoked.

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
await mountAnip(app, service);
await mountAnipRest(app, service);
await mountAnipGraphQL(app, service);
await mountAnipMcp(app, service);
```

## Testing

Each package gets tests following the same pattern as existing bindings:

- Create a test service with a simple capability
- Test translation (capability → schema generation)
- Test invocation through the interface (REST endpoint, GraphQL query, MCP tool call)
- Test auth errors (no credentials, invalid token)
- Test unknown capability handling
- No Docker — in-process testing only
