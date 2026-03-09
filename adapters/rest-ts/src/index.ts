#!/usr/bin/env node
/**
 * ANIP REST Adapter (TypeScript)
 *
 * A generic adapter that discovers any ANIP-compliant service and
 * exposes its capabilities as REST endpoints with an auto-generated
 * OpenAPI specification. Point it at any ANIP service URL — zero
 * per-service code required.
 *
 * Usage:
 *   ANIP_SERVICE_URL=http://localhost:8000 npx tsx src/index.ts
 */

import { Hono } from "hono";
import { serve } from "@hono/node-server";

import { loadConfig } from "./config.js";
import type { AdapterConfig } from "./config.js";
import { discoverService } from "./discovery.js";
import type { ANIPCapability, ANIPService } from "./discovery.js";
import { ANIPInvoker } from "./invocation.js";
import {
  generateRoutes,
  generateOpenAPISpec,
  type RESTRoute,
} from "./translation.js";

// ANIP failure type -> HTTP status code mapping
const FAILURE_STATUS_MAP: Record<string, number> = {
  unknown_capability: 404,
  insufficient_authority: 403,
  budget_exceeded: 403,
  purpose_mismatch: 403,
  invalid_parameters: 400,
  delegation_expired: 401,
};

function convertParamTypes(
  args: Record<string, string>,
  cap: ANIPCapability
): Record<string, unknown> {
  const converted: Record<string, unknown> = {};
  const inputTypes: Record<string, string> = {};
  for (const inp of cap.inputs) {
    inputTypes[inp.name] = inp.type ?? "string";
  }

  for (const [key, value] of Object.entries(args)) {
    const inpType = inputTypes[key] ?? "string";
    if (inpType === "integer") {
      const parsed = parseInt(value, 10);
      converted[key] = isNaN(parsed) ? value : parsed;
    } else if (inpType === "number") {
      const parsed = parseFloat(value);
      converted[key] = isNaN(parsed) ? value : parsed;
    } else if (inpType === "boolean") {
      converted[key] = ["true", "1", "yes"].includes(value.toLowerCase());
    } else {
      converted[key] = value;
    }
  }

  return converted;
}

async function invokeAndRespond(
  invoker: ANIPInvoker,
  capabilityName: string,
  args: Record<string, unknown>,
  cap: ANIPCapability
): Promise<{ status: number; body: Record<string, unknown> }> {
  let result: Record<string, unknown>;
  try {
    result = await invoker.invoke(capabilityName, args);
  } catch (e) {
    return {
      status: 502,
      body: {
        success: false,
        failure: {
          type: "adapter_error",
          detail: e instanceof Error ? e.message : String(e),
          retry: true,
        },
      },
    };
  }

  // Build response with warnings
  const response: Record<string, unknown> = {
    success: result.success ?? false,
    result: result.result,
  };

  if (result.cost_actual) {
    response.cost_actual = result.cost_actual;
  }

  // Add warnings for irreversible/financial operations
  const warnings: string[] = [];
  if (cap.sideEffect === "irreversible") {
    warnings.push("IRREVERSIBLE: this action cannot be undone");
  }
  if (cap.financial) {
    warnings.push("FINANCIAL: this action involves real charges");
  }
  if (warnings.length > 0) {
    response.warnings = warnings;
  }

  if (result.success) {
    return { status: 200, body: response };
  }

  // Map ANIP failure to HTTP status
  const failure = (result.failure ?? {}) as Record<string, unknown>;
  response.failure = failure;
  const status =
    FAILURE_STATUS_MAP[(failure.type as string) ?? ""] ?? 500;
  return { status, body: response };
}

export async function buildApp(config: AdapterConfig): Promise<Hono> {
  // Step 1: Discover the ANIP service
  console.error(
    `[anip-rest-adapter] Discovering ANIP service at ${config.anipServiceUrl}`
  );
  const service = await discoverService(config.anipServiceUrl);
  console.error(
    `[anip-rest-adapter] Discovered ${service.baseUrl} (${service.compliance}) with ${service.capabilities.size} capabilities`
  );
  for (const [name, cap] of service.capabilities) {
    console.error(
      `[anip-rest-adapter]   ${name}: ${cap.sideEffect} [${cap.contractVersion}]${cap.financial ? " (financial)" : ""}`
    );
  }

  // Step 2: Set up the invoker with delegation tokens
  const invoker = new ANIPInvoker(service, {
    issuer: config.delegation.issuer,
    scope: config.delegation.scope,
    tokenTtlMinutes: config.delegation.tokenTtlMinutes,
  });
  await invoker.setup();
  console.error("[anip-rest-adapter] Delegation token registered");

  // Step 3: Generate routes and OpenAPI spec
  const routes = generateRoutes(service, config.routes);
  const openApiSpec = generateOpenAPISpec(service, routes);

  // Step 4: Build Hono app
  const app = new Hono();

  // OpenAPI spec endpoint
  app.get("/openapi.json", (c) => c.json(openApiSpec));

  // Simple docs page
  app.get("/docs", (c) => {
    return c.html(`<!DOCTYPE html>
<html>
<head><title>ANIP REST Adapter</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({ url: "/openapi.json", dom_id: "#swagger-ui" });</script>
</body>
</html>`);
  });

  // Register dynamic routes
  for (const [name, route] of routes) {
    registerRoute(app, route, invoker);
  }

  return app;
}

function registerRoute(
  app: Hono,
  route: RESTRoute,
  invoker: ANIPInvoker
): void {
  const capName = route.capabilityName;
  const cap = route.capability;

  if (route.method === "GET") {
    app.get(route.path, async (c) => {
      const queryParams: Record<string, string> = {};
      for (const [k, v] of Object.entries(c.req.query())) {
        if (v !== undefined) queryParams[k] = v;
      }
      const args = convertParamTypes(queryParams, cap);
      const { status, body } = await invokeAndRespond(
        invoker,
        capName,
        args,
        cap
      );
      return c.json(body, status as 200);
    });
  } else {
    app.post(route.path, async (c) => {
      const body = await c.req.json();
      const { status, body: responseBody } = await invokeAndRespond(
        invoker,
        capName,
        body,
        cap
      );
      return c.json(responseBody, status as 200);
    });
  }
}

// CLI entry point
async function main() {
  const config = loadConfig();

  // Allow --url override
  const urlIdx = process.argv.indexOf("--url");
  if (urlIdx !== -1 && process.argv[urlIdx + 1]) {
    config.anipServiceUrl = process.argv[urlIdx + 1];
  }

  const app = await buildApp(config);

  console.error(
    `[anip-rest-adapter] Starting server on port ${config.port}`
  );
  serve({
    fetch: app.fetch,
    port: config.port,
  });
}

// Run if executed directly
const isMain =
  process.argv[1]?.endsWith("index.ts") ||
  process.argv[1]?.endsWith("index.js");
if (isMain) {
  main().catch((err) => {
    console.error("[anip-rest-adapter] Fatal:", err);
    process.exit(1);
  });
}
