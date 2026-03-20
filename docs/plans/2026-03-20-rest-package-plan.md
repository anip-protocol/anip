# REST Package Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the standalone REST adapters (`adapters/rest-ts`, `adapters/rest-py`) into reusable library packages (`@anip/rest`, `anip-rest`) that mount RESTful API endpoints directly on an `ANIPService` instance — no HTTP proxying.

**Architecture:** Each package reuses the existing translation logic (capability → OpenAPI spec, route generation) but replaces the HTTP invocation bridge with direct `service.invoke()` calls. Auth is extracted from `Authorization: Bearer` headers — JWT mode resolves tokens directly, API-key mode issues a synthetic token per request. TypeScript starts with Hono (matching `@anip/hono`); Express/Fastify adapters follow the same pattern later. Python uses FastAPI.

**Tech Stack:** TypeScript (`@anip/service`, `hono`), Python (`anip-service`, `fastapi`)

---

## File Structure

```
packages/typescript/rest/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts              # re-exports mountAnipRest
│   ├── translation.ts        # capability → OpenAPI spec, route generation
│   └── routes.ts             # mountAnipRest() — registers /api/* routes
└── tests/
    └── rest.test.ts           # tests against in-memory ANIPService

packages/python/anip-rest/
├── pyproject.toml
├── src/anip_rest/
│   ├── __init__.py           # re-exports mount_anip_rest
│   ├── translation.py        # capability → OpenAPI spec, route generation
│   └── routes.py             # mount_anip_rest() — registers /api/* routes
└── tests/
    └── test_rest.py           # tests against in-memory ANIPService
```

---

## Chunk 1: TypeScript REST Package

### Task 1: Scaffold `@anip/rest`

**Files:**
- Create: `packages/typescript/rest/package.json`
- Create: `packages/typescript/rest/tsconfig.json`
- Create: `packages/typescript/rest/src/index.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@anip/rest",
  "version": "0.8.0",
  "description": "ANIP REST bindings — expose ANIPService capabilities as RESTful API endpoints",
  "type": "module",
  "engines": { "node": ">=20" },
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "test": "vitest run"
  },
  "dependencies": {
    "@anip/service": "0.8.0",
    "hono": "^4.0.0"
  },
  "devDependencies": {
    "@anip/core": "0.8.0",
    "@anip/server": "0.8.0",
    "typescript": "^5.5.0",
    "vitest": "^4.1.0"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "dist",
    "rootDir": "src",
    "declaration": true,
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create src/index.ts**

```typescript
export { mountAnipRest } from "./routes.js";
export type { RestMountOptions, RouteOverride } from "./routes.js";
```

- [ ] **Step 4: Add to workspace**

Add `"rest"` to the `workspaces` array in `packages/typescript/package.json`.

- [ ] **Step 5: Commit**

```bash
git add packages/typescript/rest/ packages/typescript/package.json
git commit -m "feat(rest): scaffold @anip/rest package"
```

---

### Task 2: Translation module

**Files:**
- Create: `packages/typescript/rest/src/translation.ts`

Reuse from `adapters/rest-ts/src/translation.ts`. Key changes: use `service.getCapabilityDeclaration()` (returns `Record<string, unknown>`) instead of the adapter's `ANIPCapability` interface.

- [ ] **Step 1: Create translation.ts**

```typescript
/**
 * ANIP → REST translation layer.
 *
 * Generates OpenAPI 3.1 specs and route mappings from ANIP capabilities.
 */

const TYPE_MAP: Record<string, string> = {
  string: "string",
  integer: "integer",
  number: "number",
  boolean: "boolean",
  date: "string",
  airport_code: "string",
};

export interface RouteOverride {
  path: string;
  method: string;
}

export interface RESTRoute {
  capabilityName: string;
  path: string;
  method: string; // "GET" or "POST"
  declaration: Record<string, unknown>;
}

/**
 * Generate REST routes from service capabilities.
 * Default: GET for read side_effect, POST for everything else.
 * Route overrides allow custom paths and methods.
 */
export function generateRoutes(
  capabilities: Record<string, Record<string, unknown>>,
  overrides?: Record<string, RouteOverride>,
): RESTRoute[] {
  const routes: RESTRoute[] = [];
  for (const [name, decl] of Object.entries(capabilities)) {
    const override = overrides?.[name];
    const se = decl.side_effect as Record<string, unknown> | string;
    const seType = typeof se === "string" ? se : (se as any)?.type ?? "read";

    routes.push({
      capabilityName: name,
      path: override?.path ?? `/api/${name}`,
      method: (override?.method ?? (seType === "read" ? "GET" : "POST")).toUpperCase(),
      declaration: decl,
    });
  }
  return routes;
}

/**
 * Build OpenAPI 3.1 query parameters from capability inputs (for GET routes).
 */
function buildQueryParameters(decl: Record<string, unknown>): Record<string, unknown>[] {
  const inputs = (decl.inputs ?? []) as Array<Record<string, unknown>>;
  return inputs.map((inp) => ({
    name: inp.name,
    in: "query",
    required: inp.required !== false,
    schema: {
      type: TYPE_MAP[(inp.type as string) ?? "string"] ?? "string",
      ...(inp.type === "date" ? { format: "date" } : {}),
      ...(inp.default != null ? { default: inp.default } : {}),
    },
    description: inp.description ?? "",
  }));
}

/**
 * Build OpenAPI 3.1 request body from capability inputs (for POST routes).
 */
function buildRequestBody(decl: Record<string, unknown>): Record<string, unknown> {
  const inputs = (decl.inputs ?? []) as Array<Record<string, unknown>>;
  const properties: Record<string, unknown> = {};
  const required: string[] = [];
  for (const inp of inputs) {
    properties[inp.name as string] = {
      type: TYPE_MAP[(inp.type as string) ?? "string"] ?? "string",
      ...(inp.type === "date" ? { format: "date" } : {}),
      description: inp.description ?? "",
    };
    if (inp.required !== false) required.push(inp.name as string);
  }
  return {
    required: true,
    content: {
      "application/json": {
        schema: { type: "object", properties, ...(required.length > 0 ? { required } : {}) },
      },
    },
  };
}

/**
 * Generate a complete OpenAPI 3.1 spec from routes.
 */
export function generateOpenAPISpec(
  serviceId: string,
  routes: RESTRoute[],
): Record<string, unknown> {
  const paths: Record<string, unknown> = {};
  for (const route of routes) {
    const method = route.method.toLowerCase();
    const se = route.declaration.side_effect as Record<string, unknown> | string;
    const seType = typeof se === "string" ? se : (se as any)?.type ?? "read";
    const minScope = (route.declaration.minimum_scope ?? []) as string[];
    const financial = !!(route.declaration.cost as any)?.financial;

    const operation: Record<string, unknown> = {
      summary: route.declaration.description as string,
      operationId: route.capabilityName,
      responses: {
        "200": { description: "Success", content: { "application/json": { schema: { $ref: "#/components/schemas/ANIPResponse" } } } },
        "401": { description: "Authentication required" },
        "403": { description: "Authorization failed" },
        "404": { description: "Unknown capability" },
      },
      "x-anip-side-effect": seType,
      "x-anip-minimum-scope": minScope,
      "x-anip-financial": financial,
    };

    if (method === "get") {
      operation.parameters = buildQueryParameters(route.declaration);
    } else {
      operation.requestBody = buildRequestBody(route.declaration);
    }

    paths[route.path] = { [method]: operation };
  }

  return {
    openapi: "3.1.0",
    info: { title: `ANIP REST — ${serviceId}`, version: "1.0" },
    paths,
    components: {
      schemas: {
        ANIPResponse: {
          type: "object",
          properties: {
            success: { type: "boolean" },
            result: { type: "object" },
            invocation_id: { type: "string" },
            failure: { $ref: "#/components/schemas/ANIPFailure" },
          },
        },
        ANIPFailure: {
          type: "object",
          properties: {
            type: { type: "string" },
            detail: { type: "string" },
            resolution: { type: "object" },
            retry: { type: "boolean" },
          },
        },
      },
      securitySchemes: {
        bearer: { type: "http", scheme: "bearer", bearerFormat: "JWT" },
      },
    },
    security: [{ bearer: [] }],
  };
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd packages/typescript/rest && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add packages/typescript/rest/src/translation.ts
git commit -m "feat(rest): add OpenAPI translation and route generation"
```

---

### Task 3: Route/mount module

**Files:**
- Create: `packages/typescript/rest/src/routes.ts`

- [ ] **Step 1: Create routes.ts**

```typescript
/**
 * ANIP REST bindings — mount RESTful API endpoints on a Hono app.
 */
import type { Hono } from "hono";
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";
import {
  generateRoutes,
  generateOpenAPISpec,
  type RouteOverride,
  type RESTRoute,
} from "./translation.js";

export type { RouteOverride } from "./translation.js";

export interface RestMountOptions {
  /** Custom route paths/methods per capability. */
  routes?: Record<string, RouteOverride>;
  /** Prefix for all REST routes. Default: none. */
  prefix?: string;
}

const FAILURE_STATUS: Record<string, number> = {
  authentication_required: 401,
  invalid_token: 401,
  scope_insufficient: 403,
  budget_exceeded: 403,
  purpose_mismatch: 403,
  unknown_capability: 404,
  invalid_parameters: 400,
  unavailable: 409,
  internal_error: 500,
};

/**
 * Resolve auth from Authorization header.
 *
 * Order matters: try JWT first, then API key. authenticateBearer()
 * also accepts valid JWTs internally, so calling it first would
 * misidentify a caller-supplied JWT as an API key and issue a
 * synthetic token, losing the original delegation chain.
 */
async function resolveAuth(
  authHeader: string | undefined,
  service: ANIPService,
  capabilityName: string,
  adapterSubject: string,
) {
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return null;
  }
  const bearer = authHeader.slice(7).trim();

  // Try as JWT first — preserves original delegation chain
  let jwtError: ANIPError | null = null;
  try {
    return await service.resolveBearerToken(bearer);
  } catch (e) {
    if (!(e instanceof ANIPError)) throw e;
    jwtError = e; // Stash the structured error
  }

  // Try as API key — only if JWT failed
  const principal = await service.authenticateBearer(bearer);
  if (principal) {
    // This is a real API key — issue synthetic token
    const capDecl = service.getCapabilityDeclaration(capabilityName);
    const minScope = (capDecl?.minimum_scope as string[]) ?? [];
    const tokenResult = await service.issueToken(principal, {
      subject: adapterSubject,
      scope: minScope.length > 0 ? minScope : ["*"],
      capability: capabilityName,
      purpose_parameters: { source: "rest" },
    });
    const jwt = tokenResult.token as string;
    return await service.resolveBearerToken(jwt);
  }

  // Neither JWT nor API key — surface the original JWT error if we had one,
  // so the caller gets invalid_token/token_expired instead of generic 401
  if (jwtError) throw jwtError;
  return null;
}

/**
 * Convert query string values to appropriate types based on capability inputs.
 */
function convertQueryParams(
  query: Record<string, string>,
  decl: Record<string, unknown>,
): Record<string, unknown> {
  const inputs = (decl.inputs ?? []) as Array<Record<string, unknown>>;
  const typeMap = new Map(inputs.map((i) => [i.name as string, i.type as string]));
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(query)) {
    const type = typeMap.get(key);
    if (type === "integer") result[key] = parseInt(value, 10);
    else if (type === "number") result[key] = parseFloat(value);
    else if (type === "boolean") result[key] = value === "true";
    else result[key] = value;
  }
  return result;
}

/**
 * Mount RESTful API endpoints on a Hono app.
 *
 * Does NOT own service lifecycle — the caller (or mountAnip) is
 * responsible for calling service.start() before and service.shutdown()
 * after. This avoids double-starting when multiple mount functions
 * share the same ANIPService.
 */
export async function mountAnipRest(
  app: Hono,
  service: ANIPService,
  opts?: RestMountOptions,
): Promise<void> {
  const prefix = opts?.prefix ?? "";

  // Build routes from manifest
  const manifest = service.getManifest();
  const capabilities: Record<string, Record<string, unknown>> = {};
  for (const name of Object.keys(manifest.capabilities)) {
    const decl = service.getCapabilityDeclaration(name);
    if (decl) capabilities[name] = decl;
  }
  const routes = generateRoutes(capabilities, opts?.routes);
  const openApiSpec = generateOpenAPISpec(
    (manifest as any).service_id ?? "anip-service",
    routes,
  );

  // Register OpenAPI endpoints
  app.get(`${prefix}/openapi.json`, (c) => c.json(openApiSpec));
  app.get(`${prefix}/docs`, (c) => {
    return c.html(`<!DOCTYPE html>
<html><head><title>ANIP REST API</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
</head><body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({ url: "${prefix}/openapi.json", dom_id: "#swagger-ui" });</script>
</body></html>`);
  });

  // Register capability routes
  for (const route of routes) {
    const handler = async (c: any) => {
      const authHeader = c.req.header("authorization");
      let token;
      try {
        token = await resolveAuth(authHeader, service, route.capabilityName, "adapter:anip-rest");
      } catch (e) {
        if (e instanceof ANIPError) {
          const status = FAILURE_STATUS[e.errorType] ?? 400;
          return c.json({
            success: false,
            failure: { type: e.errorType, detail: e.detail, resolution: e.resolution, retry: e.retry },
          }, status);
        }
        throw e;
      }

      if (!token) {
        return c.json({
          success: false,
          failure: {
            type: "authentication_required",
            detail: "Authorization header with Bearer token or API key required",
            resolution: { action: "provide_credentials", requires: "Bearer token or API key" },
            retry: true,
          },
        }, 401);
      }

      // Extract parameters
      let params: Record<string, unknown>;
      if (route.method === "GET") {
        const query = Object.fromEntries(new URL(c.req.url).searchParams);
        params = convertQueryParams(query, route.declaration);
      } else {
        const body = await c.req.json();
        params = body.parameters ?? body;
      }

      const clientReferenceId = c.req.header("x-client-reference-id") ?? undefined;

      try {
        const result = await service.invoke(route.capabilityName, token, params, {
          clientReferenceId,
        });
        return c.json(result);
      } catch (e) {
        if (e instanceof ANIPError) {
          const status = FAILURE_STATUS[e.errorType] ?? 400;
          return c.json({
            success: false,
            failure: { type: e.errorType, detail: e.detail, resolution: e.resolution, retry: e.retry },
          }, status);
        }
        throw e;
      }
    };

    if (route.method === "GET") {
      app.get(`${prefix}${route.path}`, handler);
    } else {
      app.post(`${prefix}${route.path}`, handler);
    }
  }

}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd packages/typescript && npm install && cd rest && npx tsc`

- [ ] **Step 3: Commit**

```bash
git add packages/typescript/rest/src/routes.ts
git commit -m "feat(rest): add mountAnipRest with route overrides and OpenAPI"
```

---

### Task 4: TypeScript tests

**Files:**
- Create: `packages/typescript/rest/tests/rest.test.ts`

- [ ] **Step 1: Write tests**

Follow the same pattern as `packages/typescript/hono/tests/routes.test.ts` — create an in-memory service, mount REST routes, use Hono's `app.request()` for testing.

```typescript
import { describe, it, expect } from "vitest";
import { Hono } from "hono";
import { createANIPService, defineCapability } from "@anip/service";
import { InMemoryStorage } from "@anip/server";
import type { CapabilityDeclaration } from "@anip/core";
import { mountAnip } from "@anip/hono";
import { mountAnipRest } from "../src/routes.js";

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

function bookCap() {
  return defineCapability({
    declaration: {
      name: "book",
      description: "Book something",
      contract_version: "1.0",
      inputs: [{ name: "item", type: "string", required: true, description: "What" }],
      output: { type: "object", fields: ["booking_id"] },
      side_effect: { type: "irreversible", rollback_window: "none" },
      minimum_scope: ["book"],
      response_modes: ["unary"],
    } as CapabilityDeclaration,
    handler: (_ctx, params) => ({ booking_id: "BK-001", item: params.item }),
  });
}

async function makeApp(routeOverrides?: Record<string, any>) {
  const service = createANIPService({
    serviceId: "test-rest-service",
    capabilities: [greetCap(), bookCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const app = new Hono();
  // mountAnip owns lifecycle; mountAnipRest just adds routes
  const { stop, shutdown } = await mountAnip(app, service);
  await mountAnipRest(app, service, { routes: routeOverrides });
  return { app, stop, shutdown, service };
}

async function getToken(app: Hono): Promise<string> {
  // Use the service's token endpoint (need to mount ANIP routes too for this)
  // For REST tests, we use the API key directly in Authorization header
  return API_KEY;
}

describe("OpenAPI", () => {
  it("GET /openapi.json returns spec", async () => {
    const { app } = await makeApp();
    const res = await app.request("/openapi.json");
    expect(res.status).toBe(200);
    const spec = await res.json();
    expect(spec.openapi).toBe("3.1.0");
    expect(spec.paths["/api/greet"]).toBeDefined();
    expect(spec.paths["/api/book"]).toBeDefined();
  });

  it("GET /docs returns Swagger UI", async () => {
    const { app } = await makeApp();
    const res = await app.request("/docs");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("swagger-ui");
  });
});

describe("Default routes", () => {
  it("read capability defaults to GET", async () => {
    const { app } = await makeApp();
    const res = await app.request("/api/greet?name=World", {
      headers: { "Authorization": `Bearer ${API_KEY}` },
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.success).toBe(true);
    expect(data.result.message).toBe("Hello, World!");
  });

  it("irreversible capability defaults to POST", async () => {
    const { app } = await makeApp();
    const res = await app.request("/api/book", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ item: "flight" }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.success).toBe(true);
    expect(data.result.booking_id).toBe("BK-001");
  });
});

describe("Route overrides", () => {
  it("uses custom path and method", async () => {
    const { app } = await makeApp({
      greet: { path: "/api/hello", method: "POST" },
    });
    const res = await app.request("/api/hello", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name: "Override" }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.result.message).toBe("Hello, Override!");
  });
});

describe("Auth errors", () => {
  it("missing auth returns 401", async () => {
    const { app } = await makeApp();
    const res = await app.request("/api/greet?name=World");
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
  });

  it("invalid JWT returns 401 with invalid_token failure type", async () => {
    const { app } = await makeApp();
    const res = await app.request("/api/greet?name=World", {
      headers: { "Authorization": "Bearer garbage-not-a-jwt" },
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("invalid_token");
  });
});

describe("Lifecycle", () => {
  it("service lifecycle owned by mountAnip, not mountAnipRest", async () => {
    const { shutdown } = await makeApp();
    // mountAnipRest returns void — it doesn't own lifecycle
    await shutdown();
  });
});
```

- [ ] **Step 2: Run tests**

Run: `cd packages/typescript/rest && npx vitest run`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add packages/typescript/rest/tests/rest.test.ts
git commit -m "feat(rest): add tests for @anip/rest package"
```

---

## Chunk 2: Python REST Package

### Task 5: Scaffold `anip-rest`

**Files:**
- Create: `packages/python/anip-rest/pyproject.toml`
- Create: `packages/python/anip-rest/src/anip_rest/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "anip-rest"
version = "0.8.0"
description = "ANIP REST bindings — expose ANIPService capabilities as RESTful API endpoints"
requires-python = ">=3.11"
dependencies = [
    "anip-service>=0.8.0",
    "anip-fastapi>=0.8.0",
    "fastapi>=0.115.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create __init__.py**

```python
"""ANIP REST bindings — expose ANIPService capabilities as RESTful API endpoints."""
from .routes import mount_anip_rest

__all__ = ["mount_anip_rest"]
```

- [ ] **Step 3: Commit**

```bash
git add packages/python/anip-rest/
git commit -m "feat(rest): scaffold anip-rest Python package"
```

---

### Task 6: Python translation module

**Files:**
- Create: `packages/python/anip-rest/src/anip_rest/translation.py`

Reuse from `adapters/rest-py/anip_rest_adapter/translation.py`. Key change: accepts `CapabilityDeclaration` (Pydantic model) and calls `.model_dump()` where dict access is needed.

- [ ] **Step 1: Create translation.py**

```python
"""ANIP → REST translation layer.

Generates OpenAPI 3.1 specs and route mappings from ANIP capabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from anip_core.models import CapabilityDeclaration

_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "date": "string",
    "airport_code": "string",
}


@dataclass
class RouteOverride:
    path: str
    method: str


@dataclass
class RESTRoute:
    capability_name: str
    path: str
    method: str  # "GET" or "POST"
    declaration: CapabilityDeclaration


def generate_routes(
    capabilities: dict[str, CapabilityDeclaration],
    overrides: dict[str, RouteOverride] | None = None,
) -> list[RESTRoute]:
    """Generate REST routes from service capabilities."""
    routes = []
    for name, decl in capabilities.items():
        override = (overrides or {}).get(name)
        se_type = decl.side_effect.type.value if hasattr(decl.side_effect.type, "value") else str(decl.side_effect.type)
        routes.append(RESTRoute(
            capability_name=name,
            path=override.path if override else f"/api/{name}",
            method=(override.method if override else ("GET" if se_type == "read" else "POST")).upper(),
            declaration=decl,
        ))
    return routes


def generate_openapi_spec(
    service_id: str,
    routes: list[RESTRoute],
) -> dict[str, Any]:
    """Generate a complete OpenAPI 3.1 spec from routes."""
    paths: dict[str, Any] = {}
    for route in routes:
        method = route.method.lower()
        decl = route.declaration
        se_type = decl.side_effect.type.value if hasattr(decl.side_effect.type, "value") else str(decl.side_effect.type)
        financial = decl.cost is not None and decl.cost.financial is not None

        operation: dict[str, Any] = {
            "summary": decl.description,
            "operationId": route.capability_name,
            "responses": {
                "200": {"description": "Success"},
                "401": {"description": "Authentication required"},
                "403": {"description": "Authorization failed"},
                "404": {"description": "Unknown capability"},
            },
            "x-anip-side-effect": se_type,
            "x-anip-minimum-scope": decl.minimum_scope,
            "x-anip-financial": financial,
        }

        if method == "get":
            operation["parameters"] = _build_query_parameters(decl)
        else:
            operation["requestBody"] = _build_request_body(decl)

        paths[route.path] = {method: operation}

    return {
        "openapi": "3.1.0",
        "info": {"title": f"ANIP REST — {service_id}", "version": "1.0"},
        "paths": paths,
    }


def _build_query_parameters(decl: CapabilityDeclaration) -> list[dict]:
    return [
        {
            "name": inp.name,
            "in": "query",
            "required": inp.required,
            "schema": {
                "type": _TYPE_MAP.get(inp.type, "string"),
                **({"format": "date"} if inp.type == "date" else {}),
            },
            "description": inp.description,
        }
        for inp in decl.inputs
    ]


def _build_request_body(decl: CapabilityDeclaration) -> dict:
    properties = {}
    required = []
    for inp in decl.inputs:
        properties[inp.name] = {
            "type": _TYPE_MAP.get(inp.type, "string"),
            "description": inp.description,
        }
        if inp.required:
            required.append(inp.name)
    return {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"type": "object", "properties": properties, **({"required": required} if required else {})},
            },
        },
    }
```

- [ ] **Step 2: Commit**

```bash
git add packages/python/anip-rest/src/anip_rest/translation.py
git commit -m "feat(rest): add Python OpenAPI translation and route generation"
```

---

### Task 7: Python route/mount module

**Files:**
- Create: `packages/python/anip-rest/src/anip_rest/routes.py`

- [ ] **Step 1: Create routes.py**

```python
"""ANIP REST bindings — mount RESTful API endpoints on a FastAPI app."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from anip_service import ANIPService, ANIPError
from .translation import generate_routes, generate_openapi_spec, RouteOverride, RESTRoute

_FAILURE_STATUS = {
    "authentication_required": 401,
    "invalid_token": 401,
    "scope_insufficient": 403,
    "budget_exceeded": 403,
    "purpose_mismatch": 403,
    "unknown_capability": 404,
    "invalid_parameters": 400,
    "unavailable": 409,
    "internal_error": 500,
}


async def _resolve_auth(
    request: Request,
    service: ANIPService,
    capability_name: str,
):
    """Resolve auth from Authorization header.

    Order: try JWT first, then API key. authenticate_bearer() also
    accepts valid JWTs internally, so calling it first would misidentify
    a caller-supplied JWT as an API key and issue a synthetic token.
    """
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    bearer = auth[7:].strip()

    # Try as JWT first — preserves original delegation chain
    jwt_error = None
    try:
        return await service.resolve_bearer_token(bearer)
    except ANIPError as e:
        jwt_error = e  # Stash the structured error

    # Try as API key — only if JWT failed
    principal = await service.authenticate_bearer(bearer)
    if principal:
        cap_decl = service.get_capability_declaration(capability_name)
        min_scope = cap_decl.minimum_scope if cap_decl else []
        token_result = await service.issue_token(principal, {
            "subject": "adapter:anip-rest",
            "scope": min_scope if min_scope else ["*"],
            "capability": capability_name,
            "purpose_parameters": {"source": "rest"},
        })
        jwt_str = token_result["token"]
        return await service.resolve_bearer_token(jwt_str)

    # Neither JWT nor API key — surface the original JWT error
    if jwt_error:
        raise jwt_error
    return None


def _error_response(error: ANIPError) -> JSONResponse:
    status = _FAILURE_STATUS.get(error.error_type, 400)
    return JSONResponse(
        {
            "success": False,
            "failure": {
                "type": error.error_type,
                "detail": error.detail,
                "resolution": error.resolution,
                "retry": error.retry,
            },
        },
        status_code=status,
    )


def _convert_query_params(query: dict[str, str], decl) -> dict[str, Any]:
    """Convert query string values to appropriate types."""
    type_map = {inp.name: inp.type for inp in decl.inputs}
    result = {}
    for key, value in query.items():
        t = type_map.get(key)
        if t == "integer":
            result[key] = int(value)
        elif t == "number":
            result[key] = float(value)
        elif t == "boolean":
            result[key] = value.lower() == "true"
        else:
            result[key] = value
    return result


def mount_anip_rest(
    app: FastAPI,
    service: ANIPService,
    *,
    routes: dict[str, RouteOverride] | None = None,
    prefix: str = "",
) -> None:
    """Mount RESTful API endpoints on a FastAPI app.

    Args:
        app: FastAPI app instance.
        service: ANIPService to expose.
        routes: Optional route overrides per capability.
        prefix: URL prefix for all REST routes.
    """
    manifest = service.get_manifest()
    capabilities = {}
    for name in manifest.capabilities:
        decl = service.get_capability_declaration(name)
        if decl:
            capabilities[name] = decl

    rest_routes = generate_routes(capabilities, routes)
    openapi_spec = generate_openapi_spec(
        getattr(manifest, "service_id", "anip-service"),
        rest_routes,
    )

    @app.get(f"{prefix}/openapi.json")
    async def get_openapi():
        return openapi_spec

    @app.get(f"{prefix}/docs", response_class=HTMLResponse)
    async def get_docs():
        return f"""<!DOCTYPE html>
<html><head><title>ANIP REST API</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
</head><body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({{ url: "{prefix}/openapi.json", dom_id: "#swagger-ui" }});</script>
</body></html>"""

    for route in rest_routes:
        _register_route(app, service, route, prefix)


def _register_route(app: FastAPI, service: ANIPService, route: RESTRoute, prefix: str) -> None:
    """Register a single capability as a REST endpoint."""
    path = f"{prefix}{route.path}"

    async def handler(request: Request) -> JSONResponse:
        try:
            token = await _resolve_auth(request, service, route.capability_name)
        except ANIPError as e:
            return _error_response(e)

        if token is None:
            return JSONResponse(
                {
                    "success": False,
                    "failure": {
                        "type": "authentication_required",
                        "detail": "Authorization header with Bearer token or API key required",
                        "resolution": {"action": "provide_credentials"},
                        "retry": True,
                    },
                },
                status_code=401,
            )

        if route.method == "GET":
            params = _convert_query_params(dict(request.query_params), route.declaration)
        else:
            body = await request.json()
            params = body.get("parameters", body)

        client_reference_id = request.headers.get("x-client-reference-id")

        try:
            result = await service.invoke(
                route.capability_name, token, params,
                client_reference_id=client_reference_id,
            )
            return JSONResponse(result)
        except ANIPError as e:
            return _error_response(e)

    if route.method == "GET":
        app.get(path)(handler)
    else:
        app.post(path)(handler)
```

- [ ] **Step 2: Commit**

```bash
git add packages/python/anip-rest/src/anip_rest/routes.py
git commit -m "feat(rest): add mount_anip_rest for Python FastAPI"
```

---

### Task 8: Python tests

**Files:**
- Create: `packages/python/anip-rest/tests/test_rest.py`

- [ ] **Step 1: Write tests**

Follow the pattern from `packages/python/anip-fastapi/tests/test_routes.py` — create an in-memory service, mount REST routes on a FastAPI app, use `TestClient` for testing.

```python
"""Tests for the anip-rest package."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anip_rest.translation import generate_routes, generate_openapi_spec, RouteOverride

# Translation tests use the CapabilityDeclaration model directly
from anip_core.models import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    SideEffect, SideEffectType,
)

GREET_DECL = CapabilityDeclaration(
    name="greet",
    description="Say hello",
    inputs=[CapabilityInput(name="name", type="string", required=True, description="Who")],
    output=CapabilityOutput(type="object", fields=["message"]),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["greet"],
)

BOOK_DECL = CapabilityDeclaration(
    name="book",
    description="Book something",
    inputs=[CapabilityInput(name="item", type="string", required=True, description="What")],
    output=CapabilityOutput(type="object", fields=["booking_id"]),
    side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
    minimum_scope=["book"],
)


class TestTranslation:
    def test_read_capability_generates_get_route(self):
        routes = generate_routes({"greet": GREET_DECL})
        assert routes[0].method == "GET"
        assert routes[0].path == "/api/greet"

    def test_irreversible_capability_generates_post_route(self):
        routes = generate_routes({"book": BOOK_DECL})
        assert routes[0].method == "POST"
        assert routes[0].path == "/api/book"

    def test_route_override(self):
        overrides = {"greet": RouteOverride(path="/api/hello", method="POST")}
        routes = generate_routes({"greet": GREET_DECL}, overrides)
        assert routes[0].method == "POST"
        assert routes[0].path == "/api/hello"

    def test_openapi_spec_structure(self):
        routes = generate_routes({"greet": GREET_DECL})
        spec = generate_openapi_spec("test-service", routes)
        assert spec["openapi"] == "3.1.0"
        assert "/api/greet" in spec["paths"]


class TestMountIntegration:
    """Integration tests using a real ANIPService + FastAPI TestClient."""

    API_KEY = "test-key"

    @pytest.fixture
    def client(self):
        """Create service, mount ANIP + REST routes, return TestClient.

        mount_anip() wires FastAPI startup/shutdown hooks for service lifecycle.
        TestClient triggers them automatically.
        """
        from anip_service import ANIPService, Capability
        from anip_fastapi import mount_anip
        from anip_rest import mount_anip_rest

        service = ANIPService(
            service_id="test-rest",
            capabilities=[
                Capability(
                    declaration=GREET_DECL,
                    handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
                ),
                Capability(
                    declaration=BOOK_DECL,
                    handler=lambda ctx, params: {"booking_id": "BK-001", "item": params["item"]},
                ),
            ],
            authenticate=lambda bearer: "test-agent" if bearer == self.API_KEY else None,
        )
        app = FastAPI()
        mount_anip(app, service)       # owns lifecycle via app hooks
        mount_anip_rest(app, service)  # adds REST routes only
        return TestClient(app)

    def test_get_read_capability(self, client):
        resp = client.get("/api/greet", params={"name": "World"},
                          headers={"Authorization": f"Bearer {self.API_KEY}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["result"]["message"] == "Hello, World!"

    def test_post_write_capability(self, client):
        resp = client.post("/api/book",
                           json={"item": "flight"},
                           headers={"Authorization": f"Bearer {self.API_KEY}"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_missing_auth_returns_401(self, client):
        resp = client.get("/api/greet", params={"name": "World"})
        assert resp.status_code == 401
        assert resp.json()["failure"]["type"] == "authentication_required"

    def test_invalid_jwt_returns_structured_error(self, client):
        resp = client.get("/api/greet", params={"name": "World"},
                          headers={"Authorization": "Bearer garbage-not-a-jwt"})
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "invalid_token"

    def test_openapi_spec(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert spec["openapi"] == "3.1.0"
        assert "/api/greet" in spec["paths"]

    def test_docs_html(self, client):
        resp = client.get("/docs")
        assert resp.status_code == 200
        assert "swagger-ui" in resp.text
```

- [ ] **Step 2: Install and run tests**

Run:
```bash
cd packages/python/anip-rest
pip install -e ".[dev]" -e "../anip-core" -e "../anip-service" -e "../anip-fastapi"
pytest tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add packages/python/anip-rest/tests/test_rest.py
git commit -m "feat(rest): add tests for anip-rest Python package"
```

---

## Chunk 3: Integration

### Task 9: CI updates

- [ ] **Step 1:** Add `packages/typescript/rest/**` and `packages/python/anip-rest/**` to the relevant CI workflow path filters.
- [ ] **Step 2:** Add install/test steps for both packages.
- [ ] **Step 3:** Commit.
