/**
 * Integration tests for the ANIP REST adapter (TypeScript).
 *
 * Usage:
 *   npx tsx test-adapter.ts http://localhost:9100
 */

import { loadConfig } from "./src/config.js";
import type { AdapterConfig } from "./src/config.js";
import { discoverService } from "./src/discovery.js";
import { ANIPInvoker, CredentialError } from "./src/invocation.js";
import { generateRoutes, generateOpenAPISpec } from "./src/translation.js";
import { buildApp } from "./src/index.js";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

let passCount = 0;
let failCount = 0;

function ok(label: string): void {
  passCount++;
  console.log(`  PASS  ${label}`);
}

function fail(label: string, detail = ""): void {
  failCount++;
  let msg = `  FAIL  ${label}`;
  if (detail) msg += `  \u2014 ${detail}`;
  console.log(msg);
}

function assert(condition: boolean, label: string, detail = ""): void {
  if (condition) ok(label);
  else fail(label, detail);
}

// ---------------------------------------------------------------------------
// 1. Config defaults
// ---------------------------------------------------------------------------

function testConfigDefaults(): void {
  console.log("\n--- Config defaults ---");

  // Test with no config file and no env vars — use defaults
  const oldUrl = process.env.ANIP_SERVICE_URL;
  const oldPort = process.env.ANIP_ADAPTER_PORT;
  const oldConfig = process.env.ANIP_ADAPTER_CONFIG;

  delete process.env.ANIP_SERVICE_URL;
  delete process.env.ANIP_ADAPTER_PORT;
  delete process.env.ANIP_ADAPTER_CONFIG;

  // loadConfig without a path and without adapter.yaml in CWD
  // We pass a non-existent path to force defaults
  const cfg = loadConfig("/nonexistent/path.yaml");

  // Restore env vars
  if (oldUrl) process.env.ANIP_SERVICE_URL = oldUrl;
  if (oldPort) process.env.ANIP_ADAPTER_PORT = oldPort;
  if (oldConfig) process.env.ANIP_ADAPTER_CONFIG = oldConfig;

  assert(
    cfg.anipServiceUrl === "http://localhost:8000",
    "default service URL",
    `got ${cfg.anipServiceUrl}`
  );
  assert(cfg.port === 3001, "default port", `got ${cfg.port}`);
  assert(
    Object.keys(cfg.routes).length === 0,
    "default routes empty",
    `got ${JSON.stringify(cfg.routes)}`
  );
}

// ---------------------------------------------------------------------------
// 2. Discovery
// ---------------------------------------------------------------------------

async function testDiscovery(anipUrl: string): Promise<void> {
  console.log("\n--- Discovery ---");

  const service = await discoverService(anipUrl);
  assert(service.baseUrl !== "", "base_url populated");
  assert(service.protocol !== "", "protocol populated");
  assert(service.capabilities.size > 0, "capabilities discovered");
  assert(service.capabilities.has("search_flights"), "search_flights found");
  assert(service.capabilities.has("book_flight"), "book_flight found");

  const sf = service.capabilities.get("search_flights")!;
  assert(sf.sideEffect === "read", "search_flights is read");
  assert(sf.financial === false, "search_flights not financial");

  const bf = service.capabilities.get("book_flight")!;
  assert(
    bf.sideEffect === "write" || bf.sideEffect === "irreversible",
    "book_flight has side effect"
  );
  assert(bf.financial === true, "book_flight is financial");
  assert(bf.requires.length > 0, "book_flight has prerequisites");
}

// ---------------------------------------------------------------------------
// 3. Invocation
// ---------------------------------------------------------------------------

async function testInvocation(anipUrl: string): Promise<void> {
  console.log("\n--- Invocation ---");

  const service = await discoverService(anipUrl);
  const invoker = new ANIPInvoker(service);

  // API-key path: search flights
  const result = await invoker.invoke(
    "search_flights",
    {
      origin: "SEA",
      destination: "SFO",
      date: "2026-03-10",
      passengers: 1,
    },
    { apiKey: "demo-human-key" },
  );
  assert(typeof result === "object", "search_flights returns dict");
  assert(result.success === true, "search_flights succeeds");
  assert("result" in result, "search_flights has result");

  // API-key path: book flight
  const bookResult = await invoker.invoke(
    "book_flight",
    {
      flight_number: "AA100",
      date: "2026-03-10",
      passengers: 1,
    },
    { apiKey: "demo-human-key" },
  );
  assert(typeof bookResult === "object", "book_flight returns dict");
  assert("success" in bookResult, "book_flight has success key");

  // Token path: pre-issue a token, then invoke with it
  const tokenResp = await fetch(service.endpoints.tokens, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer demo-human-key",
    },
    body: JSON.stringify({
      subject: "adapter:anip-rest-adapter-ts",
      scope: ["*"],
      capability: "search_flights",
    }),
  });
  assert(tokenResp.ok, "token request succeeded");
  const tokenData = (await tokenResp.json()) as Record<string, unknown>;
  assert(tokenData.issued === true, "token issued for token-path test");
  const jwt = tokenData.token as string;

  const tokenResult = await invoker.invoke(
    "search_flights",
    {
      origin: "SEA",
      destination: "SFO",
      date: "2026-03-10",
      passengers: 1,
    },
    { token: jwt },
  );
  assert(typeof tokenResult === "object", "token-path search_flights returns dict");
  assert(tokenResult.success === true, "token-path search_flights succeeds");

  // No credentials raises CredentialError
  try {
    await invoker.invoke(
      "search_flights",
      { origin: "SEA", destination: "SFO", date: "2026-03-10", passengers: 1 },
      {},
    );
    fail("no-creds raises CredentialError", "no exception raised");
  } catch (e) {
    if (e instanceof CredentialError) {
      ok("no-creds raises CredentialError");
    } else {
      fail(
        "no-creds raises CredentialError",
        `wrong exception: ${e instanceof Error ? e.constructor.name : String(e)}`
      );
    }
  }
}

// ---------------------------------------------------------------------------
// 4. Translation
// ---------------------------------------------------------------------------

async function testTranslation(anipUrl: string): Promise<void> {
  console.log("\n--- Translation ---");

  const service = await discoverService(anipUrl);

  // Route generation
  const routes = generateRoutes(service);
  assert(routes.has("search_flights"), "search_flights route generated");
  assert(routes.has("book_flight"), "book_flight route generated");

  const sfRoute = routes.get("search_flights")!;
  assert(sfRoute.method === "GET", "search_flights is GET (read)");
  assert(
    sfRoute.path === "/api/search_flights",
    "search_flights default path"
  );

  const bfRoute = routes.get("book_flight")!;
  assert(bfRoute.method === "POST", "book_flight is POST (write)");
  assert(bfRoute.path === "/api/book_flight", "book_flight default path");

  // OpenAPI spec
  const spec = generateOpenAPISpec(service, routes) as Record<string, any>;
  assert(spec.openapi === "3.1.0", "OpenAPI 3.1.0");
  assert(
    "/api/search_flights" in spec.paths,
    "spec has search_flights path"
  );
  assert("/api/book_flight" in spec.paths, "spec has book_flight path");

  const sfOp = spec.paths["/api/search_flights"].get;
  assert(
    "x-anip-side-effect" in sfOp,
    "search_flights has x-anip-side-effect"
  );
  assert(
    sfOp["x-anip-side-effect"] === "read",
    "x-anip-side-effect is read"
  );
  assert(
    "x-anip-financial" in sfOp,
    "search_flights has x-anip-financial"
  );
  assert(sfOp["x-anip-financial"] === false, "x-anip-financial is False");
  assert("x-anip-minimum-scope" in sfOp, "has x-anip-minimum-scope");
  assert(
    "x-anip-contract-version" in sfOp,
    "has x-anip-contract-version"
  );
  assert("parameters" in sfOp, "GET has query parameters");

  const bfOp = spec.paths["/api/book_flight"].post;
  assert(
    bfOp["x-anip-financial"] === true,
    "book_flight x-anip-financial is True"
  );
  assert("x-anip-requires" in bfOp, "book_flight has x-anip-requires");
  assert("requestBody" in bfOp, "POST has requestBody");

  // ANIPResponse schema
  assert(
    "ANIPResponse" in spec.components.schemas,
    "ANIPResponse schema present"
  );

  // Route overrides
  const overrides = {
    search_flights: { path: "/api/flights/search", method: "GET" },
  };
  const routes2 = generateRoutes(service, overrides);
  assert(
    routes2.get("search_flights")!.path === "/api/flights/search",
    "route override path applied"
  );
}

// ---------------------------------------------------------------------------
// 5. Full server (HTTP requests via fetch)
// ---------------------------------------------------------------------------

async function testServer(anipUrl: string): Promise<void> {
  console.log("\n--- Server (Hono) ---");

  const config: AdapterConfig = {
    anipServiceUrl: anipUrl,
    port: 0, // not used — we test via app.request()
    routes: {},
  };

  const app = await buildApp(config);

  // OpenAPI spec endpoint
  let resp = await app.request("/openapi.json");
  assert(resp.status === 200, "GET /openapi.json returns 200");
  const spec = (await resp.json()) as Record<string, any>;
  assert(spec.openapi === "3.1.0", "served spec is 3.1.0");
  assert(
    "/api/search_flights" in spec.paths,
    "spec paths include search_flights"
  );

  // 401 test: no credentials
  const searchParamsNoCreds = new URLSearchParams({
    origin: "SEA",
    destination: "SFO",
    date: "2026-03-10",
    passengers: "1",
  });
  resp = await app.request(`/api/search_flights?${searchParamsNoCreds}`);
  assert(resp.status === 401, "GET without credentials returns 401");

  // API-key path: GET search_flights
  const searchParams = new URLSearchParams({
    origin: "SEA",
    destination: "SFO",
    date: "2026-03-10",
    passengers: "1",
  });
  resp = await app.request(`/api/search_flights?${searchParams}`, {
    headers: { "X-ANIP-API-Key": "demo-human-key" },
  });
  assert(resp.status === 200, "GET /api/search_flights with API key returns 200");
  let data = (await resp.json()) as Record<string, any>;
  assert(data.success === true, "search_flights response success (api-key)");
  assert("result" in data, "search_flights response has result (api-key)");

  // Token path: pre-issue a signed token, then use it
  const service = await discoverService(anipUrl);
  const tokenResp = await fetch(service.endpoints.tokens, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer demo-human-key",
    },
    body: JSON.stringify({
      subject: "adapter:anip-rest-adapter-ts",
      scope: ["*"],
      capability: "search_flights",
    }),
  });
  const tokenData = (await tokenResp.json()) as Record<string, unknown>;
  const signedToken = tokenData.token as string;

  resp = await app.request(`/api/search_flights?${searchParams}`, {
    headers: { "X-ANIP-Token": signedToken },
  });
  assert(resp.status === 200, "GET /api/search_flights with token returns 200");
  data = (await resp.json()) as Record<string, any>;
  assert(data.success === true, "search_flights response success (token)");

  // POST book_flight with API key — first search for a real flight
  const searchResp = await app.request(
    `/api/search_flights?${searchParams}`,
    { headers: { "X-ANIP-API-Key": "demo-human-key" } },
  );
  const searchData = (await searchResp.json()) as Record<string, any>;
  const flights = searchData.result?.flights ?? [];
  const flightNumber = flights.length > 0 ? flights[0].flight_number : "UA100";

  resp = await app.request("/api/book_flight", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-ANIP-API-Key": "demo-human-key",
    },
    body: JSON.stringify({
      flight_number: flightNumber,
      date: "2026-03-10",
      passengers: 1,
    }),
  });
  assert(resp.status === 200, "POST /api/book_flight returns 200");
  data = (await resp.json()) as Record<string, any>;
  assert("success" in data, "book_flight response has success key");

  // Docs endpoint is available
  resp = await app.request("/docs");
  assert(resp.status === 200, "GET /docs returns 200");
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  if (process.argv.length < 3) {
    console.log("Usage: npx tsx test-adapter.ts <anip-service-url>");
    console.log("Example: npx tsx test-adapter.ts http://localhost:9100");
    process.exit(1);
  }

  const anipUrl = process.argv[2];
  console.log(`Testing ANIP REST adapter (TS) against ${anipUrl}`);

  // 1. Config (sync)
  testConfigDefaults();

  // 2-5. Async tests
  await testDiscovery(anipUrl);
  await testInvocation(anipUrl);
  await testTranslation(anipUrl);
  await testServer(anipUrl);

  // Summary
  console.log(`\n${"=".repeat(50)}`);
  console.log(`Results: ${passCount} passed, ${failCount} failed`);
  if (failCount > 0) {
    process.exit(1);
  }
  console.log("All tests passed!");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
