# GraphQL Package Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the standalone GraphQL adapters (`adapters/graphql-ts`, `adapters/graphql-py`) into reusable library packages (`@anip/graphql`, `anip-graphql`) that mount a GraphQL endpoint directly on an `ANIPService` instance — no HTTP proxying.

**Architecture:** Each package reuses the existing translation logic (capability → SDL schema with custom directives, camelCase conventions, query/mutation separation) but replaces the HTTP invocation bridge with direct `service.invoke()` calls. Auth is extracted from `Authorization: Bearer` headers — same JWT/API-key dual mode as REST. TypeScript uses `graphql-js` for schema building and execution on Hono. Python uses Ariadne on FastAPI.

**Tech Stack:** TypeScript (`@anip/service`, `hono`, `graphql`), Python (`anip-service`, `fastapi`, `ariadne`)

---

## File Structure

```
packages/typescript/graphql/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts              # re-exports mountAnipGraphQL
│   ├── translation.ts        # capability → SDL schema with directives
│   └── routes.ts             # mountAnipGraphQL() — /graphql endpoint
└── tests/
    └── graphql.test.ts

packages/python/anip-graphql/
├── pyproject.toml
├── src/anip_graphql/
│   ├── __init__.py
│   ├── translation.py        # capability → SDL schema with directives
│   └── routes.py             # mount_anip_graphql() — /graphql endpoint
└── tests/
    └── test_graphql.py
```

---

## Chunk 1: TypeScript GraphQL Package

### Task 1: Scaffold `@anip/graphql`

**Files:**
- Create: `packages/typescript/graphql/package.json`
- Create: `packages/typescript/graphql/tsconfig.json`
- Create: `packages/typescript/graphql/src/index.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@anip/graphql",
  "version": "0.8.0",
  "description": "ANIP GraphQL bindings — expose ANIPService capabilities via GraphQL",
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
    "hono": "^4.0.0",
    "graphql": "^16.9.0"
  },
  "devDependencies": {
    "@anip/core": "0.8.0",
    "@anip/server": "0.8.0",
    "typescript": "^5.5.0",
    "vitest": "^4.1.0"
  }
}
```

- [ ] **Step 2: Create tsconfig.json** (same as REST)

- [ ] **Step 3: Create src/index.ts**

```typescript
export { mountAnipGraphQL } from "./routes.js";
export type { GraphQLMountOptions } from "./routes.js";
```

- [ ] **Step 4: Add `"graphql"` to workspaces in `packages/typescript/package.json`**

- [ ] **Step 5: Commit**

```bash
git add packages/typescript/graphql/ packages/typescript/package.json
git commit -m "feat(graphql): scaffold @anip/graphql package"
```

---

### Task 2: Translation module

**Files:**
- Create: `packages/typescript/graphql/src/translation.ts`

Reuse from `adapters/graphql-ts/src/translation.ts`. Key conventions:
- ANIP `search_flights` → GraphQL query `searchFlights` (camelCase)
- Result type `SearchFlightsResult` (PascalCase)
- `side_effect === "read"` → Query, everything else → Mutation
- Custom directives: `@anipSideEffect`, `@anipCost`, `@anipRequires`, `@anipScope`

- [ ] **Step 1: Create translation.ts**

```typescript
/**
 * ANIP → GraphQL translation layer.
 *
 * Generates SDL schema from ANIP capabilities with custom directives,
 * camelCase field names, and query/mutation separation.
 */

export function toCamelCase(snake: string): string {
  const parts = snake.split("_");
  return parts[0] + parts.slice(1).map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join("");
}

export function toSnakeCase(camel: string): string {
  return camel.replace(/([A-Z])/g, "_$1").toLowerCase().replace(/^_/, "");
}

function toPascalCase(snake: string): string {
  return snake.split("_").map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join("");
}

function anipTypeToGraphQL(anipType: string): string {
  const typeMap: Record<string, string> = {
    string: "String",
    integer: "Int",
    number: "Float",
    boolean: "Boolean",
    object: "JSON",
    array: "JSON",
  };
  return typeMap[anipType] ?? "String";
}

function buildFieldArgs(decl: Record<string, unknown>): string {
  const inputs = (decl.inputs ?? []) as Array<Record<string, unknown>>;
  if (inputs.length === 0) return "";
  const args = inputs.map((inp) => {
    const name = toCamelCase(inp.name as string);
    let gqlType = anipTypeToGraphQL((inp.type as string) ?? "string");
    if (inp.required !== false) gqlType += "!";
    return `${name}: ${gqlType}`;
  });
  return "(" + args.join(", ") + ")";
}

function buildDirectives(decl: Record<string, unknown>): string {
  const parts: string[] = [];
  const se = decl.side_effect as Record<string, unknown> | string;
  const seType = typeof se === "string" ? se : (se as any)?.type ?? "read";
  const rollback = typeof se === "string" ? null : (se as any)?.rollback_window;

  let seDir = `@anipSideEffect(type: "${seType}"`;
  if (rollback) seDir += `, rollbackWindow: "${rollback}"`;
  seDir += ")";
  parts.push(seDir);

  const cost = decl.cost as Record<string, unknown> | undefined;
  if (cost) {
    const certainty = (cost.certainty as string) ?? "estimate";
    let costDir = `@anipCost(certainty: "${certainty}"`;
    const financial = cost.financial as Record<string, unknown> | undefined;
    if (financial) {
      if (financial.currency) costDir += `, currency: "${financial.currency}"`;
      if (financial.range_min !== undefined) costDir += `, rangeMin: ${financial.range_min}`;
      if (financial.range_max !== undefined) costDir += `, rangeMax: ${financial.range_max}`;
    }
    costDir += ")";
    parts.push(costDir);
  }

  const requires = (decl.requires ?? []) as Array<Record<string, unknown>>;
  if (requires.length > 0) {
    const capNames = requires.map((r) => `"${r.capability}"`).join(", ");
    parts.push(`@anipRequires(capabilities: [${capNames}])`);
  }

  const scope = (decl.minimum_scope ?? []) as string[];
  if (scope.length > 0) {
    const scopeVals = scope.map((s) => `"${s}"`).join(", ");
    parts.push(`@anipScope(scopes: [${scopeVals}])`);
  }

  return parts.join(" ");
}

/**
 * Generate a complete GraphQL SDL schema from service capabilities.
 */
export function generateSchema(
  capabilities: Record<string, Record<string, unknown>>,
): string {
  const lines: string[] = [];

  // Directives
  lines.push('directive @anipSideEffect(type: String!, rollbackWindow: String) on FIELD_DEFINITION');
  lines.push('directive @anipCost(certainty: String!, currency: String, rangeMin: Float, rangeMax: Float) on FIELD_DEFINITION');
  lines.push('directive @anipRequires(capabilities: [String!]!) on FIELD_DEFINITION');
  lines.push('directive @anipScope(scopes: [String!]!) on FIELD_DEFINITION');
  lines.push('');
  lines.push('scalar JSON');
  lines.push('');

  // Shared types
  lines.push('type CostActual { financial: FinancialCost, varianceFromEstimate: String }');
  lines.push('type FinancialCost { amount: Float, currency: String }');
  lines.push('type ANIPFailure { type: String!, detail: String!, resolution: Resolution, retry: Boolean! }');
  lines.push('type Resolution { action: String!, requires: String, grantableBy: String }');
  lines.push('');

  const queries: string[] = [];
  const mutations: string[] = [];

  for (const [name, decl] of Object.entries(capabilities)) {
    const pascal = toPascalCase(name);
    const camel = toCamelCase(name);

    // Result type
    lines.push(`type ${pascal}Result { success: Boolean!, result: JSON, costActual: CostActual, failure: ANIPFailure }`);

    // Field with args and directives
    const args = buildFieldArgs(decl);
    const directives = buildDirectives(decl);
    const fieldLine = `  ${camel}${args}: ${pascal}Result! ${directives}`;

    const se = decl.side_effect as Record<string, unknown> | string;
    const seType = typeof se === "string" ? se : (se as any)?.type ?? "read";
    if (seType === "read") {
      queries.push(fieldLine);
    } else {
      mutations.push(fieldLine);
    }
  }

  lines.push('');
  if (queries.length > 0) {
    lines.push('type Query {');
    lines.push(...queries);
    lines.push('}');
  }
  if (mutations.length > 0) {
    lines.push('type Mutation {');
    lines.push(...mutations);
    lines.push('}');
  }

  return lines.join('\n');
}

/**
 * Map an ANIP invoke response to the GraphQL result shape (camelCase).
 */
export function buildGraphQLResponse(result: Record<string, unknown>): Record<string, unknown> {
  const response: Record<string, unknown> = {
    success: result.success ?? false,
    result: result.result ?? null,
    costActual: null,
    failure: null,
  };

  const costActual = result.cost_actual as Record<string, unknown> | undefined;
  if (costActual) {
    response.costActual = {
      financial: costActual.financial ?? null,
      varianceFromEstimate: costActual.variance_from_estimate ?? null,
    };
  }

  const failure = result.failure as Record<string, unknown> | undefined;
  if (failure) {
    const resolution = failure.resolution as Record<string, unknown> | undefined;
    response.failure = {
      type: failure.type ?? "unknown",
      detail: failure.detail ?? "",
      resolution: resolution ? {
        action: resolution.action ?? "",
        requires: resolution.requires ?? null,
        grantableBy: resolution.grantable_by ?? null,
      } : null,
      retry: failure.retry ?? false,
    };
  }

  return response;
}
```

- [ ] **Step 2: Commit**

```bash
git add packages/typescript/graphql/src/translation.ts
git commit -m "feat(graphql): add SDL translation with directives and camelCase"
```

---

### Task 3: Route/mount module

**Files:**
- Create: `packages/typescript/graphql/src/routes.ts`

- [ ] **Step 1: Create routes.ts**

```typescript
/**
 * ANIP GraphQL bindings — mount a GraphQL endpoint on a Hono app.
 */
import { buildSchema, graphql } from "graphql";
import type { Hono } from "hono";
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";
import {
  generateSchema,
  buildGraphQLResponse,
  toCamelCase,
  toSnakeCase,
} from "./translation.js";

export interface GraphQLMountOptions {
  /** URL path for the GraphQL endpoint. Default: "/graphql" */
  path?: string;
  /** URL prefix. Default: none. */
  prefix?: string;
}

const FAILURE_STATUS: Record<string, number> = {
  authentication_required: 401,
  invalid_token: 401,
};

/**
 * Resolve auth — JWT first, then API key.
 * See REST plan for rationale on ordering.
 */
async function resolveAuth(
  authHeader: string | undefined,
  service: ANIPService,
  capabilityName: string,
) {
  if (!authHeader || !authHeader.startsWith("Bearer ")) return null;
  const bearer = authHeader.slice(7).trim();

  // Try as JWT first — preserves original delegation chain
  try {
    return await service.resolveBearerToken(bearer);
  } catch (e) {
    // Only swallow ANIPError (invalid_token) — rethrow unexpected failures
    if (!(e instanceof ANIPError)) throw e;
  }

  // Try as API key — issue synthetic token
  const principal = await service.authenticateBearer(bearer);
  if (principal) {
    const capDecl = service.getCapabilityDeclaration(capabilityName);
    const minScope = (capDecl?.minimum_scope as string[]) ?? [];
    const tokenResult = await service.issueToken(principal, {
      subject: "adapter:anip-graphql",
      scope: minScope.length > 0 ? minScope : ["*"],
      capability: capabilityName,
      purpose_parameters: { source: "graphql" },
    });
    return await service.resolveBearerToken(tokenResult.token as string);
  }

  return null;
}

/**
 * Mount a GraphQL endpoint on a Hono app.
 *
 * Does NOT own service lifecycle — the caller (or mountAnip) is
 * responsible for start/shutdown.
 */
export async function mountAnipGraphQL(
  app: Hono,
  service: ANIPService,
  opts?: GraphQLMountOptions,
): Promise<void> {
  const gqlPath = opts?.path ?? "/graphql";
  const prefix = opts?.prefix ?? "";
  const fullPath = `${prefix}${gqlPath}`;

  // Build capabilities map
  const manifest = service.getManifest();
  const capabilities: Record<string, Record<string, unknown>> = {};
  for (const name of Object.keys(manifest.capabilities)) {
    const decl = service.getCapabilityDeclaration(name);
    if (decl) capabilities[name] = decl;
  }

  // Generate and build schema
  const schemaSdl = generateSchema(capabilities);
  const schema = buildSchema(schemaSdl);

  // Build resolvers: camelCase field name → ANIP invoke
  const resolvers: Record<string, (args: Record<string, unknown>, creds: any) => Promise<Record<string, unknown>>> = {};
  for (const name of Object.keys(capabilities)) {
    const camelName = toCamelCase(name);
    resolvers[camelName] = async (args, creds) => {
      // Convert camelCase args back to snake_case for ANIP
      const snakeArgs: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(args)) {
        snakeArgs[toSnakeCase(k)] = v;
      }

      let token;
      try {
        token = await resolveAuth(creds?.authHeader, service, name);
      } catch (e) {
        if (e instanceof ANIPError) {
          return buildGraphQLResponse({
            success: false,
            failure: { type: e.errorType, detail: e.detail, resolution: e.resolution, retry: e.retry },
          });
        }
        throw e;
      }

      if (!token) {
        return buildGraphQLResponse({
          success: false,
          failure: {
            type: "authentication_required",
            detail: "Authorization header required",
            resolution: { action: "provide_credentials" },
            retry: true,
          },
        });
      }

      try {
        const result = await service.invoke(name, token, snakeArgs);
        return buildGraphQLResponse(result);
      } catch (e) {
        if (e instanceof ANIPError) {
          return buildGraphQLResponse({
            success: false,
            failure: { type: e.errorType, detail: e.detail, resolution: e.resolution, retry: e.retry },
          });
        }
        throw e;
      }
    };
  }

  // POST /graphql — execute query/mutation
  app.post(fullPath, async (c) => {
    const body = await c.req.json() as {
      query: string;
      variables?: Record<string, unknown>;
      operationName?: string;
    };

    const authHeader = c.req.header("authorization");

    // Wrap resolvers to inject auth context
    const rootValue: Record<string, (args: Record<string, unknown>) => Promise<Record<string, unknown>>> = {};
    for (const [name, resolver] of Object.entries(resolvers)) {
      rootValue[name] = (args) => resolver(args, { authHeader });
    }

    const result = await graphql({
      schema,
      source: body.query,
      rootValue,
      variableValues: body.variables,
      operationName: body.operationName,
    });

    return c.json(result);
  });

  // GET /graphql — simple playground
  app.get(fullPath, (c) => {
    return c.html(`<!DOCTYPE html>
<html><head><title>ANIP GraphQL</title></head><body>
<h2>ANIP GraphQL Playground</h2>
<textarea id="q" rows="10" cols="60">{ }</textarea><br>
<button onclick="run()">Run</button><pre id="r"></pre>
<script>
async function run() {
  const r = await fetch("${fullPath}", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({query: document.getElementById("q").value})
  });
  document.getElementById("r").textContent = JSON.stringify(await r.json(), null, 2);
}
</script></body></html>`);
  });

  // GET /schema.graphql — raw SDL
  app.get(`${prefix}/schema.graphql`, (c) => {
    return c.text(schemaSdl);
  });

}
```

- [ ] **Step 2: Commit**

```bash
git add packages/typescript/graphql/src/routes.ts
git commit -m "feat(graphql): add mountAnipGraphQL with resolvers and SDL"
```

---

### Task 4: TypeScript tests

**Files:**
- Create: `packages/typescript/graphql/tests/graphql.test.ts`

- [ ] **Step 1: Write tests**

```typescript
import { describe, it, expect } from "vitest";
import { Hono } from "hono";
import { createANIPService, defineCapability } from "@anip/service";
import { InMemoryStorage } from "@anip/server";
import type { CapabilityDeclaration } from "@anip/core";
import { mountAnip } from "@anip/hono";
import { mountAnipGraphQL } from "../src/routes.js";
import { generateSchema, toCamelCase, toSnakeCase } from "../src/translation.js";

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
      name: "book_item",
      description: "Book something",
      contract_version: "1.0",
      inputs: [{ name: "item_name", type: "string", required: true, description: "What" }],
      output: { type: "object", fields: ["booking_id"] },
      side_effect: { type: "irreversible", rollback_window: "none" },
      minimum_scope: ["book"],
      response_modes: ["unary"],
    } as CapabilityDeclaration,
    handler: (_ctx, params) => ({ booking_id: "BK-001", item: params.item_name }),
  });
}

async function makeApp() {
  const service = createANIPService({
    serviceId: "test-graphql-service",
    capabilities: [greetCap(), bookCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const app = new Hono();
  const { shutdown } = await mountAnip(app, service);
  await mountAnipGraphQL(app, service);
  return { app, shutdown };
}

describe("Case conversion", () => {
  it("toCamelCase converts snake_case", () => {
    expect(toCamelCase("search_flights")).toBe("searchFlights");
    expect(toCamelCase("book")).toBe("book");
  });

  it("toSnakeCase converts camelCase", () => {
    expect(toSnakeCase("searchFlights")).toBe("search_flights");
    expect(toSnakeCase("itemName")).toBe("item_name");
  });
});

describe("SDL generation", () => {
  it("generates valid SDL with queries and mutations", () => {
    const service = greetCap();
    const caps = {
      greet: service.declaration as unknown as Record<string, unknown>,
      book_item: bookCap().declaration as unknown as Record<string, unknown>,
    };
    const sdl = generateSchema(caps);
    expect(sdl).toContain("type Query");
    expect(sdl).toContain("type Mutation");
    expect(sdl).toContain("greet(name: String!): GreetResult!");
    expect(sdl).toContain("bookItem(itemName: String!): BookItemResult!");
    expect(sdl).toContain("@anipSideEffect");
  });
});

describe("GraphQL endpoint", () => {
  it("GET /schema.graphql returns SDL", async () => {
    const { app } = await makeApp();
    const res = await app.request("/schema.graphql");
    expect(res.status).toBe(200);
    const sdl = await res.text();
    expect(sdl).toContain("type Query");
  });

  it("query executes read capability", async () => {
    const { app, shutdown } = await makeApp();
    const res = await app.request("/graphql", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: '{ greet(name: "World") { success result } }',
      }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.data.greet.success).toBe(true);
    expect(data.data.greet.result.message).toBe("Hello, World!");
    await shutdown();
  });

  it("mutation executes write capability", async () => {
    const { app, shutdown } = await makeApp();
    const res = await app.request("/graphql", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: 'mutation { bookItem(itemName: "flight") { success result } }',
      }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.data.bookItem.success).toBe(true);
    await shutdown();
  });

  it("query without auth returns failure in result", async () => {
    const { app, shutdown } = await makeApp();
    const res = await app.request("/graphql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: '{ greet(name: "World") { success failure { type detail } } }',
      }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.data.greet.success).toBe(false);
    expect(data.data.greet.failure.type).toBe("authentication_required");
    await shutdown();
  });
});

describe("Lifecycle", () => {
  it("mountAnipGraphQL returns void — lifecycle owned by mountAnip", async () => {
    const { shutdown } = await makeApp();
    await shutdown();
  });
});
```

- [ ] **Step 2: Run tests**

Run: `cd packages/typescript/graphql && npx vitest run`

- [ ] **Step 3: Commit**

```bash
git add packages/typescript/graphql/tests/graphql.test.ts
git commit -m "feat(graphql): add tests for @anip/graphql package"
```

---

## Chunk 2: Python GraphQL Package

### Task 5: Scaffold `anip-graphql`

**Files:**
- Create: `packages/python/anip-graphql/pyproject.toml`
- Create: `packages/python/anip-graphql/src/anip_graphql/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "anip-graphql"
version = "0.8.0"
description = "ANIP GraphQL bindings — expose ANIPService capabilities via GraphQL"
requires-python = ">=3.11"
dependencies = [
    "anip-service>=0.8.0",
    "fastapi>=0.115.0",
    "ariadne>=0.24.0",
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
"""ANIP GraphQL bindings — expose ANIPService capabilities via GraphQL."""
from .routes import mount_anip_graphql

__all__ = ["mount_anip_graphql"]
```

- [ ] **Step 3: Commit**

```bash
git add packages/python/anip-graphql/
git commit -m "feat(graphql): scaffold anip-graphql Python package"
```

---

### Task 6: Python translation module

**Files:**
- Create: `packages/python/anip-graphql/src/anip_graphql/translation.py`

Same SDL generation logic as TypeScript, using `CapabilityDeclaration` Pydantic models with `.model_dump()` where needed.

- [ ] **Step 1: Create translation.py**

```python
"""ANIP → GraphQL translation layer.

Generates SDL schema from ANIP capabilities with custom directives,
camelCase field names, and query/mutation separation.
"""
from __future__ import annotations

from typing import Any

from anip_core.models import CapabilityDeclaration


def to_camel_case(snake: str) -> str:
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def to_snake_case(camel: str) -> str:
    import re
    return re.sub(r"([A-Z])", r"_\1", camel).lower().lstrip("_")


def _to_pascal_case(snake: str) -> str:
    return "".join(p.capitalize() for p in snake.split("_"))


_GQL_TYPE_MAP = {
    "string": "String",
    "integer": "Int",
    "number": "Float",
    "boolean": "Boolean",
    "object": "JSON",
    "array": "JSON",
}


def generate_schema(capabilities: dict[str, CapabilityDeclaration]) -> str:
    """Generate a complete GraphQL SDL schema from ANIP capabilities."""
    lines = [
        'directive @anipSideEffect(type: String!, rollbackWindow: String) on FIELD_DEFINITION',
        'directive @anipCost(certainty: String!, currency: String, rangeMin: Float, rangeMax: Float) on FIELD_DEFINITION',
        'directive @anipRequires(capabilities: [String!]!) on FIELD_DEFINITION',
        'directive @anipScope(scopes: [String!]!) on FIELD_DEFINITION',
        '',
        'scalar JSON',
        '',
        'type CostActual { financial: FinancialCost, varianceFromEstimate: String }',
        'type FinancialCost { amount: Float, currency: String }',
        'type ANIPFailure { type: String!, detail: String!, resolution: Resolution, retry: Boolean! }',
        'type Resolution { action: String!, requires: String, grantableBy: String }',
        '',
    ]

    queries = []
    mutations = []

    for name, decl in capabilities.items():
        pascal = _to_pascal_case(name)
        camel = to_camel_case(name)

        lines.append(f"type {pascal}Result {{ success: Boolean!, result: JSON, costActual: CostActual, failure: ANIPFailure }}")

        args = _build_field_args(decl)
        directives = _build_directives(decl)
        field_line = f"  {camel}{args}: {pascal}Result! {directives}"

        se_type = decl.side_effect.type.value if hasattr(decl.side_effect.type, "value") else str(decl.side_effect.type)
        if se_type == "read":
            queries.append(field_line)
        else:
            mutations.append(field_line)

    lines.append("")
    if queries:
        lines.append("type Query {")
        lines.extend(queries)
        lines.append("}")
    if mutations:
        lines.append("type Mutation {")
        lines.extend(mutations)
        lines.append("}")

    return "\n".join(lines)


def _build_field_args(decl: CapabilityDeclaration) -> str:
    if not decl.inputs:
        return ""
    args = []
    for inp in decl.inputs:
        gql_type = _GQL_TYPE_MAP.get(inp.type, "String")
        if inp.required:
            gql_type += "!"
        args.append(f"{to_camel_case(inp.name)}: {gql_type}")
    return "(" + ", ".join(args) + ")"


def _build_directives(decl: CapabilityDeclaration) -> str:
    parts = []
    se_type = decl.side_effect.type.value if hasattr(decl.side_effect.type, "value") else str(decl.side_effect.type)
    rollback = decl.side_effect.rollback_window

    se_dir = f'@anipSideEffect(type: "{se_type}"'
    if rollback:
        se_dir += f', rollbackWindow: "{rollback}"'
    se_dir += ")"
    parts.append(se_dir)

    if decl.cost:
        certainty = decl.cost.certainty.value if hasattr(decl.cost.certainty, "value") else str(decl.cost.certainty)
        cost_dir = f'@anipCost(certainty: "{certainty}"'
        if decl.cost.financial:
            financial = decl.cost.financial
            if hasattr(financial, "currency") and financial.currency:
                cost_dir += f', currency: "{financial.currency}"'
        cost_dir += ")"
        parts.append(cost_dir)

    if decl.requires:
        cap_names = ", ".join(f'"{r.capability}"' for r in decl.requires)
        parts.append(f"@anipRequires(capabilities: [{cap_names}])")

    if decl.minimum_scope:
        scope_vals = ", ".join(f'"{s}"' for s in decl.minimum_scope)
        parts.append(f"@anipScope(scopes: [{scope_vals}])")

    return " ".join(parts)


def build_graphql_response(result: dict[str, Any]) -> dict[str, Any]:
    """Map ANIP invoke response to GraphQL result shape (camelCase)."""
    response: dict[str, Any] = {
        "success": result.get("success", False),
        "result": result.get("result"),
        "costActual": None,
        "failure": None,
    }

    cost_actual = result.get("cost_actual")
    if cost_actual:
        response["costActual"] = {
            "financial": cost_actual.get("financial"),
            "varianceFromEstimate": cost_actual.get("variance_from_estimate"),
        }

    failure = result.get("failure")
    if failure:
        resolution = failure.get("resolution")
        response["failure"] = {
            "type": failure.get("type", "unknown"),
            "detail": failure.get("detail", ""),
            "resolution": {
                "action": resolution.get("action", ""),
                "requires": resolution.get("requires"),
                "grantableBy": resolution.get("grantable_by"),
            } if resolution else None,
            "retry": failure.get("retry", False),
        }

    return response
```

- [ ] **Step 2: Commit**

```bash
git add packages/python/anip-graphql/src/anip_graphql/translation.py
git commit -m "feat(graphql): add Python SDL translation with directives"
```

---

### Task 7: Python route/mount module

**Files:**
- Create: `packages/python/anip-graphql/src/anip_graphql/routes.py`

Uses Ariadne for schema building and resolver registration, mounted as ASGI middleware on FastAPI.

- [ ] **Step 1: Create routes.py**

```python
"""ANIP GraphQL bindings — mount a GraphQL endpoint on a FastAPI app."""
from __future__ import annotations

from typing import Any

from ariadne import QueryType, MutationType, ScalarType, make_executable_schema
from ariadne.asgi import GraphQL
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from anip_service import ANIPService, ANIPError
from .translation import (
    generate_schema,
    build_graphql_response,
    to_camel_case,
    to_snake_case,
)


async def _resolve_auth(request, service: ANIPService, capability_name: str):
    """Resolve auth — JWT first, then API key."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    bearer = auth[7:].strip()

    # Try as JWT first — preserves original delegation chain
    try:
        return await service.resolve_bearer_token(bearer)
    except ANIPError:
        pass  # Invalid token — fall through to API-key mode

    # Try as API key — issue synthetic token
    principal = await service.authenticate_bearer(bearer)
    if principal:
        cap_decl = service.get_capability_declaration(capability_name)
        min_scope = cap_decl.minimum_scope if cap_decl else []
        token_result = await service.issue_token(principal, {
            "subject": "adapter:anip-graphql",
            "scope": min_scope if min_scope else ["*"],
            "capability": capability_name,
            "purpose_parameters": {"source": "graphql"},
        })
        return await service.resolve_bearer_token(token_result["token"])

    return None


def _make_resolver(capability_name: str, service: ANIPService):
    """Create a resolver for a given capability."""

    async def resolver(_obj: Any, info: Any, **kwargs: Any) -> dict[str, Any]:
        # Convert camelCase args back to snake_case
        arguments = {to_snake_case(k): v for k, v in kwargs.items()}

        try:
            token = await _resolve_auth(info.context["request"], service, capability_name)
        except ANIPError as e:
            return build_graphql_response({
                "success": False,
                "failure": {"type": e.error_type, "detail": e.detail, "retry": e.retry},
            })

        if token is None:
            return build_graphql_response({
                "success": False,
                "failure": {
                    "type": "authentication_required",
                    "detail": "Authorization header required",
                    "resolution": {"action": "provide_credentials"},
                    "retry": True,
                },
            })

        try:
            result = await service.invoke(capability_name, token, arguments)
        except ANIPError as e:
            return build_graphql_response({
                "success": False,
                "failure": {"type": e.error_type, "detail": e.detail, "retry": e.retry},
            })

        return build_graphql_response(result)

    return resolver


def mount_anip_graphql(
    app: FastAPI,
    service: ANIPService,
    *,
    path: str = "/graphql",
    prefix: str = "",
) -> None:
    """Mount a GraphQL endpoint on a FastAPI app.

    Args:
        app: FastAPI app instance.
        service: ANIPService to expose.
        path: GraphQL endpoint path. Default: "/graphql".
        prefix: URL prefix.
    """
    manifest = service.get_manifest()
    capabilities = {}
    for name in manifest.capabilities:
        decl = service.get_capability_declaration(name)
        if decl:
            capabilities[name] = decl

    schema_sdl = generate_schema(capabilities)

    # Build Ariadne resolvers
    query = QueryType()
    mutation = MutationType()
    json_scalar = ScalarType("JSON")

    @json_scalar.serializer
    def serialize_json(value):
        return value

    @json_scalar.value_parser
    def parse_json_value(value):
        return value

    for name, decl in capabilities.items():
        camel_name = to_camel_case(name)
        resolver_fn = _make_resolver(name, service)
        se_type = decl.side_effect.type.value if hasattr(decl.side_effect.type, "value") else str(decl.side_effect.type)
        if se_type == "read":
            query.field(camel_name)(resolver_fn)
        else:
            mutation.field(camel_name)(resolver_fn)

    schema = make_executable_schema(schema_sdl, query, mutation, json_scalar)
    graphql_app = GraphQL(schema, debug=True)

    full_path = f"{prefix}{path}"
    app.mount(full_path, graphql_app)

    @app.get(f"{prefix}/schema.graphql")
    async def get_schema() -> PlainTextResponse:
        return PlainTextResponse(schema_sdl, media_type="text/plain")
```

- [ ] **Step 2: Commit**

```bash
git add packages/python/anip-graphql/src/anip_graphql/routes.py
git commit -m "feat(graphql): add mount_anip_graphql for Python FastAPI/Ariadne"
```

---

### Task 8: Python tests

**Files:**
- Create: `packages/python/anip-graphql/tests/test_graphql.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for the anip-graphql package."""
import pytest

from anip_core.models import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    SideEffect, SideEffectType,
)
from anip_graphql.translation import (
    generate_schema, to_camel_case, to_snake_case, build_graphql_response,
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
    name="book_item",
    description="Book something",
    inputs=[CapabilityInput(name="item_name", type="string", required=True, description="What")],
    output=CapabilityOutput(type="object", fields=["booking_id"]),
    side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
    minimum_scope=["book"],
)


class TestCaseConversion:
    def test_to_camel_case(self):
        assert to_camel_case("search_flights") == "searchFlights"
        assert to_camel_case("book") == "book"

    def test_to_snake_case(self):
        assert to_snake_case("searchFlights") == "search_flights"
        assert to_snake_case("itemName") == "item_name"


class TestSDLGeneration:
    def test_generates_query_for_read(self):
        sdl = generate_schema({"greet": GREET_DECL})
        assert "type Query" in sdl
        assert "greet(name: String!): GreetResult!" in sdl

    def test_generates_mutation_for_irreversible(self):
        sdl = generate_schema({"book_item": BOOK_DECL})
        assert "type Mutation" in sdl
        assert "bookItem(itemName: String!): BookItemResult!" in sdl

    def test_includes_directives(self):
        sdl = generate_schema({"greet": GREET_DECL})
        assert "@anipSideEffect" in sdl
        assert "@anipScope" in sdl

    def test_includes_shared_types(self):
        sdl = generate_schema({"greet": GREET_DECL})
        assert "type ANIPFailure" in sdl
        assert "scalar JSON" in sdl


class TestResponseMapping:
    def test_success_response(self):
        result = build_graphql_response({"success": True, "result": {"message": "Hi"}})
        assert result["success"] is True
        assert result["result"]["message"] == "Hi"

    def test_failure_response(self):
        result = build_graphql_response({
            "success": False,
            "failure": {
                "type": "scope_insufficient",
                "detail": "Missing scope",
                "resolution": {"action": "request_scope", "grantable_by": "admin"},
                "retry": False,
            },
        })
        assert result["success"] is False
        assert result["failure"]["type"] == "scope_insufficient"
        assert result["failure"]["resolution"]["grantableBy"] == "admin"

    def test_cost_actual_mapping(self):
        result = build_graphql_response({
            "success": True,
            "result": {},
            "cost_actual": {
                "financial": {"amount": 100, "currency": "USD"},
                "variance_from_estimate": "-5%",
            },
        })
        assert result["costActual"]["financial"]["amount"] == 100
        assert result["costActual"]["varianceFromEstimate"] == "-5%"


class TestMountIntegration:
    """Integration tests using a real ANIPService + FastAPI TestClient."""

    API_KEY = "test-key"

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from anip_service import ANIPService
        from anip_graphql import mount_anip_graphql

        service = ANIPService(
            service_id="test-graphql",
            capabilities=[
                {
                    "declaration": GREET_DECL,
                    "handler": lambda token, params: {"message": f"Hello, {params['name']}!"},
                },
                {
                    "declaration": BOOK_DECL,
                    "handler": lambda token, params: {"booking_id": "BK-001"},
                },
            ],
            authenticate=lambda bearer: "test-agent" if bearer == self.API_KEY else None,
        )
        app = FastAPI()
        mount_anip_graphql(app, service)
        return TestClient(app)

    def test_query_read_capability(self, client):
        resp = client.post(
            "/graphql",
            json={"query": '{ greet(name: "World") { success result } }'},
            headers={"Authorization": f"Bearer {self.API_KEY}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["greet"]["success"] is True
        assert data["data"]["greet"]["result"]["message"] == "Hello, World!"

    def test_mutation_write_capability(self, client):
        resp = client.post(
            "/graphql",
            json={"query": 'mutation { bookItem(itemName: "x") { success result } }'},
            headers={"Authorization": f"Bearer {self.API_KEY}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["bookItem"]["success"] is True

    def test_query_without_auth_returns_failure(self, client):
        resp = client.post(
            "/graphql",
            json={"query": '{ greet(name: "World") { success failure { type } } }'},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["greet"]["success"] is False
        assert data["data"]["greet"]["failure"]["type"] == "authentication_required"

    def test_schema_endpoint(self, client):
        resp = client.get("/schema.graphql")
        assert resp.status_code == 200
        assert "type Query" in resp.text
```

- [ ] **Step 2: Run tests**

Run: `cd packages/python/anip-graphql && pip install -e ".[dev]" -e "../anip-core" -e "../anip-service" && pytest tests/ -v`

- [ ] **Step 3: Commit**

```bash
git add packages/python/anip-graphql/tests/test_graphql.py
git commit -m "feat(graphql): add tests for anip-graphql Python package"
```

---

## Chunk 3: Integration

### Task 9: CI updates

- [ ] **Step 1:** Add `packages/typescript/graphql/**` and `packages/python/anip-graphql/**` to CI workflow path filters.
- [ ] **Step 2:** Add install/test steps for both packages.
- [ ] **Step 3:** Commit.

### Task 10: Example app updates (deferred)

Deferred until all three packages (MCP, REST, GraphQL) are implemented. Then update both example apps to demonstrate all four interfaces from a single service.
