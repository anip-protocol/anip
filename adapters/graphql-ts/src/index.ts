#!/usr/bin/env node
/**
 * ANIP GraphQL Adapter (TypeScript)
 *
 * A generic adapter that discovers any ANIP-compliant service and
 * exposes its capabilities as a GraphQL endpoint with custom @anip*
 * directives. Point it at any ANIP service URL — zero per-service
 * code required.
 *
 * Usage:
 *   ANIP_SERVICE_URL=http://localhost:8000 npx tsx src/index.ts
 */

import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { buildSchema, graphql } from "graphql";

import { loadConfig } from "./config.js";
import type { AdapterConfig } from "./config.js";
import { discoverService } from "./discovery.js";
import type { ANIPService } from "./discovery.js";
import { ANIPInvoker, CredentialError, IssuanceError } from "./invocation.js";
import { generateSchema, toCamelCase, toSnakeCase } from "./translation.js";

function buildAnipResponse(result: Record<string, unknown>): Record<string, unknown> {
  const response: Record<string, unknown> = {
    success: result.success ?? false,
    result: result.result ?? null,
    costActual: null,
    failure: null,
  };

  // Map cost_actual -> costActual
  const costActual = result.cost_actual as Record<string, unknown> | undefined;
  if (costActual) {
    const financial = costActual.financial as Record<string, unknown> | undefined;
    response.costActual = {
      financial: financial ?? null,
      varianceFromEstimate: costActual.variance_from_estimate ?? null,
    };
  }

  // Map failure with resolution
  const failure = result.failure as Record<string, unknown> | undefined;
  if (failure) {
    const resolution = failure.resolution as Record<string, unknown> | undefined;
    let mappedResolution = null;
    if (resolution) {
      mappedResolution = {
        action: resolution.action ?? "",
        requires: resolution.requires ?? null,
        grantableBy: resolution.grantable_by ?? null,
      };
    }
    response.failure = {
      type: failure.type ?? "unknown",
      detail: failure.detail ?? "",
      resolution: mappedResolution,
      retry: failure.retry ?? false,
    };
  }

  return response;
}

function makeResolver(capabilityName: string, invoker: ANIPInvoker) {
  return async (
    args: Record<string, unknown>,
    creds: { token?: string; apiKey?: string },
  ) => {
    const snakeArgs: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(args)) {
      snakeArgs[toSnakeCase(k)] = v;
    }

    try {
      const result = await invoker.invoke(capabilityName, snakeArgs, creds);
      return buildAnipResponse(result);
    } catch (e) {
      if (e instanceof CredentialError) {
        return {
          success: false, result: null, costActual: null,
          failure: { type: "missing_credentials", detail: e.message, resolution: null, retry: false },
        };
      }
      if (e instanceof IssuanceError) {
        return {
          success: false, result: null, costActual: null,
          failure: { type: "token_issuance_denied", detail: e.error, resolution: null, retry: false },
        };
      }
      console.error(`ANIP invocation failed for ${capabilityName}:`, e);
      return {
        success: false, result: null, costActual: null,
        failure: {
          type: "adapter_error",
          detail: e instanceof Error ? e.message : String(e),
          resolution: null, retry: true,
        },
      };
    }
  };
}

export async function buildApp(config: AdapterConfig): Promise<Hono> {
  // Step 1: Discover the ANIP service
  console.error(
    `[anip-graphql-adapter] Discovering ANIP service at ${config.anipServiceUrl}`
  );
  const service = await discoverService(config.anipServiceUrl);
  console.error(
    `[anip-graphql-adapter] Discovered ${service.baseUrl} (${service.compliance}) with ${service.capabilities.size} capabilities`
  );
  for (const [name, cap] of service.capabilities) {
    console.error(
      `[anip-graphql-adapter]   ${name}: ${cap.sideEffect} [${cap.contractVersion}]${cap.financial ? " (financial)" : ""}`
    );
  }

  // Step 2: Set up the invoker
  const invoker = new ANIPInvoker(service);
  console.error("[anip-graphql-adapter] Invoker ready (stateless credential pass-through)");

  // Step 3: Generate GraphQL schema SDL
  const schemaSdl = generateSchema(service);

  // Step 4: Build the schema object (validates SDL)
  const schema = buildSchema(schemaSdl);

  // Step 5: Build root resolvers
  const rootValue: Record<string, (args: Record<string, unknown>, creds: { token?: string; apiKey?: string }) => Promise<Record<string, unknown>>> = {};
  for (const [name, cap] of service.capabilities) {
    const camelName = toCamelCase(name);
    rootValue[camelName] = makeResolver(name, invoker);
  }

  // Step 6: Build Hono app
  const app = new Hono();

  // POST /graphql — execute GraphQL query/mutation
  app.post(config.graphqlPath, async (c) => {
    const body = await c.req.json() as {
      query: string;
      variables?: Record<string, unknown>;
      operationName?: string;
    };

    // Extract credentials from HTTP headers
    const token = c.req.header("x-anip-token") ?? undefined;
    const apiKey = c.req.header("x-anip-api-key") ?? undefined;
    const creds = { token, apiKey };

    // Wrap resolvers to inject credentials
    const rootValueWithCreds: Record<string, (args: Record<string, unknown>) => Promise<Record<string, unknown>>> = {};
    for (const [name, resolver] of Object.entries(rootValue)) {
      rootValueWithCreds[name] = (args: Record<string, unknown>) => resolver(args, creds);
    }

    const result = await graphql({
      schema,
      source: body.query,
      rootValue: rootValueWithCreds,
      variableValues: body.variables,
      operationName: body.operationName,
    });

    return c.json(result);
  });

  // GET /graphql — simple playground HTML
  app.get(config.graphqlPath, (c) => {
    // If ?query= param, run it
    const query = c.req.query("query");
    if (query) {
      // Extract credentials from HTTP headers
      const token = c.req.header("x-anip-token") ?? undefined;
      const apiKey = c.req.header("x-anip-api-key") ?? undefined;
      const creds = { token, apiKey };

      // Wrap resolvers to inject credentials
      const rootValueWithCreds: Record<string, (args: Record<string, unknown>) => Promise<Record<string, unknown>>> = {};
      for (const [name, resolver] of Object.entries(rootValue)) {
        rootValueWithCreds[name] = (args: Record<string, unknown>) => resolver(args, creds);
      }

      // Execute inline query (for simple testing)
      return (async () => {
        const result = await graphql({
          schema,
          source: query,
          rootValue: rootValueWithCreds,
        });
        return c.json(result);
      })();
    }

    return c.html(`<!DOCTYPE html>
<html>
<head>
  <title>ANIP GraphQL Adapter</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }
    textarea { width: 100%; height: 200px; font-family: monospace; }
    pre { background: #f4f4f4; padding: 16px; overflow-x: auto; }
    button { padding: 8px 16px; cursor: pointer; }
  </style>
</head>
<body>
  <h1>ANIP GraphQL Adapter</h1>
  <p>POST queries to <code>${config.graphqlPath}</code> or download the <a href="/schema.graphql">schema</a>.</p>
  <textarea id="query">query {
  searchFlights(origin: "SEA", destination: "SFO", date: "2026-03-10") {
    success
    result
  }
}</textarea>
  <br><button onclick="run()">Run</button>
  <pre id="result"></pre>
  <script>
    async function run() {
      const query = document.getElementById('query').value;
      const resp = await fetch('${config.graphqlPath}', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      const data = await resp.json();
      document.getElementById('result').textContent = JSON.stringify(data, null, 2);
    }
  </script>
</body>
</html>`);
  });

  // GET /schema.graphql — raw SDL text
  app.get("/schema.graphql", (c) => {
    return c.text(schemaSdl);
  });

  return app;
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
    `[anip-graphql-adapter] Starting server on port ${config.port}`
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
    console.error("[anip-graphql-adapter] Fatal:", err);
    process.exit(1);
  });
}
