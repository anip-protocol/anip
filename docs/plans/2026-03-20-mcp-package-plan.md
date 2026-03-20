# MCP Package Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the standalone MCP adapters (`adapters/mcp-ts`, `adapters/mcp-py`) into reusable library packages (`@anip/mcp`, `anip-mcp`) that mount directly on an `ANIPService` instance — no HTTP proxying.

**Architecture:** Each package reuses the existing translation logic (capability → MCP tool schema, description enrichment) but replaces the HTTP invocation bridge with direct `service.invoke()` calls. Both packages support stdio transport only — mount on an MCP `Server` instance with mount-time credential config. SSE transport is deferred to a follow-up plan.

**Tech Stack:** TypeScript (`@modelcontextprotocol/sdk`, `@anip/service`), Python (`mcp`, `anip-service`)

---

## File Structure

```
packages/typescript/mcp/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts              # re-exports mountAnipMcp
│   ├── translation.ts        # capability → MCP tool schema (reused from adapter)
│   └── routes.ts             # mountAnipMcp() for MCP Server stdio
└── tests/
    └── mcp.test.ts           # tests against in-memory ANIPService

packages/python/anip-mcp/
├── pyproject.toml
├── src/anip_mcp/
│   ├── __init__.py           # re-exports mount_anip_mcp
│   ├── translation.py        # capability → MCP tool schema (reused from adapter)
│   └── routes.py             # mount_anip_mcp() for stdio
└── tests/
    └── test_mcp.py           # tests against in-memory ANIPService
```

---

## Chunk 1: TypeScript MCP Package

### Task 1: Scaffold `@anip/mcp` package

**Files:**
- Create: `packages/typescript/mcp/package.json`
- Create: `packages/typescript/mcp/tsconfig.json`
- Create: `packages/typescript/mcp/src/index.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@anip/mcp",
  "version": "0.8.0",
  "description": "ANIP MCP bindings — expose ANIPService capabilities as MCP tools",
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
    "@modelcontextprotocol/sdk": "^1.12.0"
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
export { mountAnipMcp } from "./routes.js";
export type { McpMountOptions, McpCredentials } from "./routes.js";
```

- [ ] **Step 4: Add to workspace**

Add `"mcp"` to the `workspaces` array in `packages/typescript/package.json`.

- [ ] **Step 5: Install and build**

Run: `cd packages/typescript && npm install && cd mcp && npx tsc --noEmit`
Expected: No errors (index.ts will fail until routes.ts exists — that's fine)

- [ ] **Step 6: Commit**

```bash
git add packages/typescript/mcp/package.json packages/typescript/mcp/tsconfig.json packages/typescript/mcp/src/index.ts packages/typescript/package.json
git commit -m "feat(mcp): scaffold @anip/mcp package"
```

---

### Task 2: Translation module

**Files:**
- Create: `packages/typescript/mcp/src/translation.ts`

- [ ] **Step 1: Create translation.ts**

Copy and adapt from `adapters/mcp-ts/src/translation.ts`. The logic is identical — no HTTP dependencies. Remove the import of `ANIPCapability` from `discovery.js` and use `@anip/core`'s `CapabilityDeclaration` instead.

```typescript
/**
 * ANIP → MCP translation layer.
 *
 * Converts ANIP capability declarations into MCP tool schemas,
 * enriching descriptions with ANIP metadata that MCP cannot
 * natively represent.
 */
import type { CapabilityDeclaration } from "@anip/core";

const TYPE_MAP: Record<string, string> = {
  string: "string",
  integer: "integer",
  number: "number",
  boolean: "boolean",
  date: "string",
  airport_code: "string",
};

export interface MCPInputSchema {
  type: "object";
  properties: Record<string, Record<string, unknown>>;
  required?: string[];
  [key: string]: unknown;
}

export function capabilityToInputSchema(
  declaration: CapabilityDeclaration,
): MCPInputSchema {
  const properties: Record<string, Record<string, unknown>> = {};
  const required: string[] = [];

  for (const input of declaration.inputs) {
    const jsonType = TYPE_MAP[input.type] ?? "string";
    const prop: Record<string, unknown> = {
      type: jsonType,
      description: input.description ?? "",
    };
    if (input.type === "date") {
      prop.format = "date";
    }
    if (input.default !== undefined && input.default !== null) {
      prop.default = input.default;
    }
    properties[input.name] = prop;
    if (input.required !== false) {
      required.push(input.name);
    }
  }

  const schema: MCPInputSchema = { type: "object", properties };
  if (required.length > 0) {
    schema.required = required;
  }
  return schema;
}

export function enrichDescription(declaration: CapabilityDeclaration): string {
  const parts: string[] = [declaration.description];
  const se = declaration.side_effect;
  const seType = typeof se === "string" ? se : se.type;
  const rollback = typeof se === "string" ? null : se.rollback_window;

  if (seType === "irreversible") {
    parts.push("WARNING: IRREVERSIBLE action — cannot be undone.");
    if (rollback === "none") {
      parts.push("No rollback window.");
    }
  } else if (seType === "write") {
    if (rollback && rollback !== "none" && rollback !== "not_applicable") {
      parts.push(`Reversible within ${rollback}.`);
    }
  } else if (seType === "read") {
    parts.push("Read-only, no side effects.");
  }

  const cost = declaration.cost as Record<string, unknown> | undefined;
  if (cost) {
    const financial = cost.financial as Record<string, unknown> | undefined;
    const certainty = cost.certainty as string | undefined;
    if (certainty === "fixed" && financial) {
      const amount = financial.amount as number;
      const currency = (financial.currency as string) ?? "USD";
      if (amount > 0) parts.push(`Cost: ${currency} ${amount} (fixed).`);
    } else if (certainty === "estimated" && financial) {
      const rangeMin = financial.range_min as number | undefined;
      const rangeMax = financial.range_max as number | undefined;
      const currency = (financial.currency as string) ?? "USD";
      if (rangeMin !== undefined && rangeMax !== undefined) {
        parts.push(`Estimated cost: ${currency} ${rangeMin}-${rangeMax}.`);
      }
    }
  }

  const requires = declaration.requires ?? [];
  if (requires.length > 0) {
    const prereqs = requires.map((r: any) => r.capability);
    parts.push(`Requires calling first: ${prereqs.join(", ")}.`);
  }

  const scope = declaration.minimum_scope ?? [];
  if (scope.length > 0) {
    parts.push(`Delegation scope: ${scope.join(", ")}.`);
  }

  return parts.join(" ");
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd packages/typescript/mcp && npx tsc --noEmit`
Expected: Only errors from missing routes.ts (not translation.ts)

- [ ] **Step 3: Commit**

```bash
git add packages/typescript/mcp/src/translation.ts
git commit -m "feat(mcp): add MCP tool schema translation module"
```

---

### Task 3: Route/mount module

**Files:**
- Create: `packages/typescript/mcp/src/routes.ts`

This is the core of the package. It provides `mountAnipMcp()` which registers `list_tools` and `call_tool` handlers on an MCP `Server` instance for stdio transport.

- [ ] **Step 1: Create routes.ts**

```typescript
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
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";
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
 * Invoke an ANIP capability directly via the service instance.
 * Uses mount-time credentials to issue a synthetic token per call.
 */
async function invokeCapability(
  service: ANIPService,
  capabilityName: string,
  args: Record<string, unknown>,
  credentials: McpCredentials,
): Promise<string> {
  // Authenticate the bootstrap credential
  const principal = await service.authenticateBearer(credentials.apiKey);
  if (!principal) {
    return "FAILED: authentication_required\nDetail: Invalid bootstrap credential\nRetryable: no";
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
      return `FAILED: ${e.errorType}\nDetail: ${e.detail}\nRetryable: no`;
    }
    throw e;
  }

  const jwt = tokenResult.token as string;
  const token = await service.resolveBearerToken(jwt);

  // Invoke the capability
  const result = await service.invoke(capabilityName, token, args);
  return translateResponse(result);
}

function translateResponse(response: Record<string, unknown>): string {
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
    return parts.join("");
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
  return parts.join("\n");
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
      const result = await invokeCapability(
        service, name, (args ?? {}) as Record<string, unknown>, credentials,
      );
      return { content: [{ type: "text" as const, text: result }] };
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
      await service.shutdown();
    },
  };
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd packages/typescript && npm install && cd mcp && npx tsc`
Expected: Clean build

- [ ] **Step 3: Commit**

```bash
git add packages/typescript/mcp/src/routes.ts
git commit -m "feat(mcp): add mountAnipMcp for stdio transport"
```

---

### Task 4: TypeScript tests

**Files:**
- Create: `packages/typescript/mcp/tests/mcp.test.ts`

- [ ] **Step 1: Write tests**

```typescript
import { describe, it, expect } from "vitest";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { createANIPService, defineCapability } from "@anip/service";
import { InMemoryStorage } from "@anip/server";
import type { CapabilityDeclaration } from "@anip/core";
import { mountAnipMcp } from "../src/routes.js";
import { capabilityToInputSchema, enrichDescription } from "../src/translation.js";

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

async function makeService() {
  return createANIPService({
    serviceId: "test-mcp-service",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
}

const CREDENTIALS = { apiKey: API_KEY, scope: ["greet"], subject: "test-agent" };

describe("Translation", () => {
  it("converts capability inputs to JSON Schema", () => {
    const decl = greetCap().declaration;
    const schema = capabilityToInputSchema(decl);
    expect(schema.type).toBe("object");
    expect(schema.properties.name).toBeDefined();
    expect(schema.properties.name.type).toBe("string");
    expect(schema.required).toContain("name");
  });

  it("enriches description with side-effect info", () => {
    const decl = greetCap().declaration;
    const desc = enrichDescription(decl);
    expect(desc).toContain("Read-only");
    expect(desc).toContain("Delegation scope: greet");
  });
});

describe("mountAnipMcp", () => {
  it("requires credentials for MCP Server", async () => {
    const service = await makeService();
    const server = new Server(
      { name: "test", version: "1.0" },
      { capabilities: { tools: {} } },
    );
    await expect(mountAnipMcp(server, service)).rejects.toThrow("credentials");
  });

  it("mounts and returns lifecycle handle", async () => {
    const service = await makeService();
    const server = new Server(
      { name: "test", version: "1.0" },
      { capabilities: { tools: {} } },
    );
    const lifecycle = await mountAnipMcp(server, service, { credentials: CREDENTIALS });
    expect(lifecycle.stop).toBeTypeOf("function");
    expect(lifecycle.shutdown).toBeTypeOf("function");
    await lifecycle.shutdown();
  });

  it("list_tools returns registered tools", async () => {
    const service = await makeService();
    const server = new Server(
      { name: "test", version: "1.0" },
      { capabilities: { tools: {} } },
    );
    const lifecycle = await mountAnipMcp(server, service, { credentials: CREDENTIALS });

    // Full list_tools verification is in the integration tests below.
    // Here we just confirm mount succeeded and lifecycle works.
    await lifecycle.shutdown();
  });
});

// Integration test: full tool call through MCP Client + Server
// This tests the real invocation path: list_tools → call_tool → ANIP invoke
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";

describe("MCP tool invocation (integration)", () => {
  it("call_tool invokes ANIP capability and returns result", async () => {
    const service = await makeService();
    const server = new Server(
      { name: "test", version: "1.0" },
      { capabilities: { tools: {} } },
    );
    const lifecycle = await mountAnipMcp(server, service, { credentials: CREDENTIALS });

    // Connect client and server over in-memory transport
    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);
    const client = new Client({ name: "test-client", version: "1.0" });
    await client.connect(clientTransport);

    // List tools
    const tools = await client.listTools();
    expect(tools.tools.length).toBe(1);
    expect(tools.tools[0].name).toBe("greet");

    // Call tool — should invoke the ANIP capability
    const result = await client.callTool({ name: "greet", arguments: { name: "World" } });
    expect(result.isError).toBeFalsy();
    const text = (result.content as any[])[0].text;
    expect(text).toContain("Hello, World!");

    await client.close();
    await lifecycle.shutdown();
  });

  it("call_tool with unknown tool returns error", async () => {
    const service = await makeService();
    const server = new Server(
      { name: "test", version: "1.0" },
      { capabilities: { tools: {} } },
    );
    const lifecycle = await mountAnipMcp(server, service, { credentials: CREDENTIALS });

    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);
    const client = new Client({ name: "test-client", version: "1.0" });
    await client.connect(clientTransport);

    const result = await client.callTool({ name: "nonexistent", arguments: {} });
    expect(result.isError).toBe(true);
    const text = (result.content as any[])[0].text;
    expect(text).toContain("Unknown tool");

    await client.close();
    await lifecycle.shutdown();
  });

  it("call_tool with invalid credentials returns failure", async () => {
    const service = await makeService();
    const server = new Server(
      { name: "test", version: "1.0" },
      { capabilities: { tools: {} } },
    );
    const badCreds = { apiKey: "wrong-key", scope: ["greet"], subject: "test" };
    const lifecycle = await mountAnipMcp(server, service, { credentials: badCreds });

    const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
    await server.connect(serverTransport);
    const client = new Client({ name: "test-client", version: "1.0" });
    await client.connect(clientTransport);

    const result = await client.callTool({ name: "greet", arguments: { name: "World" } });
    const text = (result.content as any[])[0].text;
    expect(text).toContain("FAILED");
    expect(text).toContain("authentication_required");

    await client.close();
    await lifecycle.shutdown();
  });
});
```

- [ ] **Step 2: Run tests**

Run: `cd packages/typescript/mcp && npx vitest run`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add packages/typescript/mcp/tests/mcp.test.ts
git commit -m "feat(mcp): add tests for @anip/mcp package"
```

---

## Chunk 2: Python MCP Package

### Task 5: Scaffold `anip-mcp` package

**Files:**
- Create: `packages/python/anip-mcp/pyproject.toml`
- Create: `packages/python/anip-mcp/src/anip_mcp/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "anip-mcp"
version = "0.8.0"
description = "ANIP MCP bindings — expose ANIPService capabilities as MCP tools"
requires-python = ">=3.11"
dependencies = [
    "anip-service>=0.8.0",
    "mcp>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create __init__.py**

```python
"""ANIP MCP bindings — expose ANIPService capabilities as MCP tools."""
from .routes import mount_anip_mcp, McpCredentials, McpLifecycle

__all__ = ["mount_anip_mcp", "McpCredentials", "McpLifecycle"]
```

- [ ] **Step 3: Commit**

```bash
git add packages/python/anip-mcp/pyproject.toml packages/python/anip-mcp/src/anip_mcp/__init__.py
git commit -m "feat(mcp): scaffold anip-mcp Python package"
```

---

### Task 6: Python translation module

**Files:**
- Create: `packages/python/anip-mcp/src/anip_mcp/translation.py`

- [ ] **Step 1: Create translation.py**

Copy and adapt from `adapters/mcp-py/anip_mcp_bridge/translation.py`. Replace the `ANIPCapability` dataclass import with the service's `CapabilityDeclaration` (or use plain dicts from the manifest).

```python
"""ANIP → MCP translation layer.

Converts ANIP capability declarations into MCP tool schemas,
enriching descriptions with ANIP metadata.
"""
from __future__ import annotations

from typing import Any

_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "date": "string",
    "airport_code": "string",
}


def capability_to_input_schema(declaration: dict[str, Any]) -> dict:
    """Convert ANIP capability inputs to JSON Schema for MCP tool."""
    properties = {}
    required = []

    for inp in declaration.get("inputs", []):
        json_type = _TYPE_MAP.get(inp.get("type", "string"), "string")
        prop: dict = {"type": json_type, "description": inp.get("description", "")}
        if inp.get("type") == "date":
            prop["format"] = "date"
        if "default" in inp and inp["default"] is not None:
            prop["default"] = inp["default"]
        properties[inp["name"]] = prop
        if inp.get("required", True):
            required.append(inp["name"])

    schema: dict = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def enrich_description(declaration: dict[str, Any]) -> str:
    """Enrich MCP tool description with ANIP metadata."""
    parts = [declaration.get("description", "")]
    se = declaration.get("side_effect", {})
    se_type = se.get("type") if isinstance(se, dict) else se
    rollback = se.get("rollback_window") if isinstance(se, dict) else None

    if se_type == "irreversible":
        parts.append("WARNING: IRREVERSIBLE action — cannot be undone.")
        if rollback == "none":
            parts.append("No rollback window.")
    elif se_type == "write":
        if rollback and rollback not in ("none", "not_applicable"):
            parts.append(f"Reversible within {rollback}.")
    elif se_type == "read":
        parts.append("Read-only, no side effects.")

    cost = declaration.get("cost")
    if cost:
        financial = cost.get("financial", {})
        certainty = cost.get("certainty")
        if certainty == "fixed" and financial:
            amount = financial.get("amount", 0)
            currency = financial.get("currency", "USD")
            if amount and float(amount) > 0:
                parts.append(f"Cost: {currency} {amount} (fixed).")
        elif certainty == "estimated" and financial:
            rmin = financial.get("range_min")
            rmax = financial.get("range_max")
            currency = financial.get("currency", "USD")
            if rmin is not None and rmax is not None:
                parts.append(f"Estimated cost: {currency} {rmin}-{rmax}.")

    requires = declaration.get("requires", [])
    if requires:
        prereqs = [r.get("capability", r) if isinstance(r, dict) else r for r in requires]
        parts.append(f"Requires calling first: {', '.join(prereqs)}.")

    scope = declaration.get("minimum_scope", [])
    if scope:
        parts.append(f"Delegation scope: {', '.join(scope)}.")

    return " ".join(parts)
```

- [ ] **Step 2: Commit**

```bash
git add packages/python/anip-mcp/src/anip_mcp/translation.py
git commit -m "feat(mcp): add Python MCP tool schema translation module"
```

---

### Task 7: Python route/mount module

**Files:**
- Create: `packages/python/anip-mcp/src/anip_mcp/routes.py`

- [ ] **Step 1: Create routes.py**

```python
"""ANIP MCP bindings — mount ANIPService capabilities as MCP tools.

Supports stdio transport via the mcp library.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server

from anip_service import ANIPService, ANIPError
from .translation import capability_to_input_schema, enrich_description


@dataclass
class McpCredentials:
    """Mount-time credentials for stdio transport."""
    api_key: str
    scope: list[str]
    subject: str


async def _invoke_capability(
    service: ANIPService,
    capability_name: str,
    args: dict[str, Any],
    credentials: McpCredentials,
) -> str:
    """Invoke an ANIP capability directly via the service instance."""
    principal = await service.authenticate_bearer(credentials.api_key)
    if not principal:
        return "FAILED: authentication_required\nDetail: Invalid bootstrap credential\nRetryable: no"

    # Narrow scope to what the capability needs
    cap_decl = service.get_capability_declaration(capability_name)
    min_scope = cap_decl.minimum_scope if cap_decl else []
    cap_scope = credentials.scope
    if min_scope:
        needed = set(min_scope)
        narrowed = [s for s in credentials.scope if s.split(":")[0] in needed or s in needed]
        if narrowed:
            cap_scope = narrowed

    # Issue a synthetic token
    try:
        token_result = await service.issue_token(principal, {
            "subject": credentials.subject,
            "scope": cap_scope,
            "capability": capability_name,
            "purpose_parameters": {"source": "mcp"},
        })
    except ANIPError as e:
        return f"FAILED: {e.error_type}\nDetail: {e.detail}\nRetryable: no"

    jwt_str = token_result["token"]
    token = await service.resolve_bearer_token(jwt_str)

    result = await service.invoke(capability_name, token, args)
    return _translate_response(result)


def _translate_response(response: dict[str, Any]) -> str:
    """Translate an ANIP InvokeResponse into an MCP result string."""
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
        return "".join(parts)

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
    return "\n".join(parts)


@dataclass
class McpLifecycle:
    """Lifecycle handle returned by mount_anip_mcp."""
    _service: ANIPService

    def stop(self) -> None:
        self._service.stop()

    async def shutdown(self) -> None:
        await self._service.shutdown()


async def mount_anip_mcp(
    server: Server,
    service: ANIPService,
    *,
    credentials: McpCredentials,
    enrich_descriptions: bool = True,
) -> McpLifecycle:
    """Mount ANIP capabilities as MCP tools on an MCP Server.

    Starts the service lifecycle (storage init, background workers).
    Caller must call the returned lifecycle.stop() / lifecycle.shutdown()
    on teardown.

    Args:
        server: MCP Server instance (for stdio transport).
        service: ANIPService to expose.
        credentials: Bootstrap credentials for token issuance.
        enrich_descriptions: Include ANIP metadata in tool descriptions.

    Returns:
        McpLifecycle with stop() and shutdown() methods.
    """
    await service.start()

    # Build tool map from service manifest
    manifest = service.get_manifest()
    mcp_tools: dict[str, types.Tool] = {}

    for name in manifest.capabilities:
        decl = service.get_capability_declaration(name)
        if not decl:
            continue
        decl_dict = decl.model_dump()
        description = enrich_description(decl_dict) if enrich_descriptions else decl.description
        mcp_tools[name] = types.Tool(
            name=name,
            description=description,
            inputSchema=capability_to_input_schema(decl_dict),
        )

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return list(mcp_tools.values())

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict,
    ) -> list[types.TextContent]:
        if name not in mcp_tools:
            return [types.TextContent(
                type="text",
                text=f"Unknown tool: {name}. Available: {list(mcp_tools.keys())}",
            )]

        try:
            result = await _invoke_capability(service, name, arguments or {}, credentials)
            return [types.TextContent(type="text", text=result)]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"ANIP invocation error: {e}",
            )]

    return McpLifecycle(_service=service)
```

- [ ] **Step 2: Commit**

```bash
git add packages/python/anip-mcp/src/anip_mcp/routes.py
git commit -m "feat(mcp): add mount_anip_mcp for Python stdio transport"
```

---

### Task 8: Python tests

**Files:**
- Create: `packages/python/anip-mcp/tests/test_mcp.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for the anip-mcp package."""
import pytest

from anip_mcp.translation import capability_to_input_schema, enrich_description
from anip_mcp.routes import _invoke_capability, _translate_response, McpCredentials


GREET_DECLARATION = {
    "name": "greet",
    "description": "Say hello",
    "contract_version": "1.0",
    "inputs": [
        {"name": "name", "type": "string", "required": True, "description": "Who"},
    ],
    "output": {"type": "object", "fields": ["message"]},
    "side_effect": {"type": "read", "rollback_window": "not_applicable"},
    "minimum_scope": ["greet"],
    "response_modes": ["unary"],
}


class TestTranslation:
    def test_input_schema_properties(self):
        schema = capability_to_input_schema(GREET_DECLARATION)
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert schema["properties"]["name"]["type"] == "string"

    def test_input_schema_required(self):
        schema = capability_to_input_schema(GREET_DECLARATION)
        assert "name" in schema["required"]

    def test_enrich_description_read(self):
        desc = enrich_description(GREET_DECLARATION)
        assert "Read-only" in desc
        assert "Delegation scope: greet" in desc

    def test_enrich_description_irreversible(self):
        decl = {
            **GREET_DECLARATION,
            "side_effect": {"type": "irreversible", "rollback_window": "none"},
        }
        desc = enrich_description(decl)
        assert "IRREVERSIBLE" in desc
        assert "No rollback window" in desc


class TestTranslateResponse:
    def test_success_response(self):
        resp = {"success": True, "result": {"message": "Hello!"}}
        text = _translate_response(resp)
        assert "Hello!" in text

    def test_failure_response(self):
        resp = {
            "success": False,
            "failure": {
                "type": "scope_insufficient",
                "detail": "Missing travel.book",
                "resolution": {"action": "request_broader_scope"},
                "retry": False,
            },
        }
        text = _translate_response(resp)
        assert "FAILED: scope_insufficient" in text
        assert "Missing travel.book" in text
        assert "Retryable: no" in text


class TestInvokeCapability:
    """Integration tests using a real ANIPService instance."""

    @pytest.fixture
    def service(self):
        """Create a test service with a greet capability."""
        from anip_core.models import (
            CapabilityDeclaration, SideEffect, SideEffectType,
            CapabilityInput, CapabilityOutput,
        )
        from anip_service import ANIPService

        API_KEY = "test-key"

        service = ANIPService(
            service_id="test-mcp",
            capabilities=[
                {
                    "declaration": CapabilityDeclaration(
                        name="greet",
                        description="Say hello",
                        inputs=[CapabilityInput(name="name", type="string", required=True, description="Who")],
                        output=CapabilityOutput(type="object", fields=["message"]),
                        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                        minimum_scope=["greet"],
                    ),
                    "handler": lambda token, params: {"message": f"Hello, {params['name']}!"},
                },
            ],
            authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
        )
        return service, API_KEY

    async def test_invoke_with_valid_credentials(self, service):
        svc, api_key = service
        await svc.start()
        creds = McpCredentials(api_key=api_key, scope=["greet"], subject="test-agent")
        result = await _invoke_capability(svc, "greet", {"name": "World"}, creds)
        assert "Hello, World!" in result
        svc.stop()

    async def test_invoke_with_invalid_credentials(self, service):
        svc, _ = service
        await svc.start()
        creds = McpCredentials(api_key="wrong-key", scope=["greet"], subject="test")
        result = await _invoke_capability(svc, "greet", {"name": "World"}, creds)
        assert "FAILED" in result
        assert "authentication_required" in result
        svc.stop()
```

**Note:** The `TestInvokeCapability` tests create a real `ANIPService` and test the full invocation path: authenticate → issue token → resolve token → invoke. The exact fixture shape depends on the service's constructor — the implementer should adapt the fixture to match the actual `ANIPService` API (which may use `create_anip_service()` or the class constructor directly). Check `packages/python/anip-fastapi/tests/test_routes.py` for the working pattern.

**Important:** The implementer MUST also add an integration test that exercises the full `mount_anip_mcp()` → `list_tools` → `call_tool` path on a real MCP `Server` instance — mirroring the TypeScript `InMemoryTransport` integration tests. The Python `mcp` library provides `mcp.server.stdio.stdio_server()` for production and in-process testing patterns. The test should:

1. Create a real `ANIPService` and MCP `Server`
2. Call `await mount_anip_mcp(server, service, credentials=...)` to register handlers
3. Verify `list_tools` returns the expected tool(s)
4. Verify `call_tool` with valid args returns a success result
5. Verify `call_tool` with an unknown tool name returns an error
6. Call `lifecycle.shutdown()` to verify clean teardown

If the `mcp` library does not expose an in-memory transport for testing (check `mcp.server` and `mcp.client` modules), the implementer should test handler registration by calling the decorated handler functions directly (`handle_list_tools()`, `handle_call_tool("greet", {"name": "World"})`) — these are async functions registered on the server object.

- [ ] **Step 2: Install and run tests**

Run:
```bash
cd packages/python/anip-mcp
pip install -e ".[dev]" -e "../anip-core" -e "../anip-service"
pytest tests/ -v
```
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add packages/python/anip-mcp/tests/test_mcp.py
git commit -m "feat(mcp): add tests for anip-mcp Python package"
```

---

## Chunk 3: Integration & Cleanup

### Task 9: Update CI workflows

**Files:**
- Modify: `.github/workflows/ci-typescript.yml`
- Modify: `.github/workflows/ci-python.yml`

- [ ] **Step 1: Add MCP to TypeScript CI**

Add `packages/typescript/mcp/**` to the path filters and add MCP to the build/test matrix.

- [ ] **Step 2: Add MCP to Python CI**

Add `packages/python/anip-mcp/**` to the path filters and add `anip-mcp` to the install/test steps.

- [ ] **Step 3: Verify CI passes locally**

Run:
```bash
cd packages/typescript/mcp && npm test
cd ../../python/anip-mcp && pytest tests/ -v
```
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci-typescript.yml .github/workflows/ci-python.yml
git commit -m "ci: add @anip/mcp and anip-mcp to CI workflows"
```

---

### Task 10: Update example apps (optional, deferred)

The example apps can optionally be updated to demonstrate MCP alongside the existing ANIP protocol routes. This is deferred until the REST and GraphQL packages are also ready, so all four interfaces can be added together.
