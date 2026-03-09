/**
 * Integration tests for the ANIP GraphQL adapter (TypeScript).
 *
 * Usage:
 *   npx tsx test-adapter.ts http://localhost:9100
 */

import { loadConfig } from "./src/config.js";
import type { AdapterConfig } from "./src/config.js";
import { discoverService } from "./src/discovery.js";
import { ANIPInvoker } from "./src/invocation.js";
import { generateSchema, toCamelCase, toSnakeCase } from "./src/translation.js";
import { buildApp } from "./src/index.js";
import { buildSchema } from "graphql";

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

  const oldUrl = process.env.ANIP_SERVICE_URL;
  const oldPort = process.env.ANIP_ADAPTER_PORT;
  const oldIssuer = process.env.ANIP_ISSUER;
  const oldScope = process.env.ANIP_SCOPE;
  const oldTtl = process.env.ANIP_TOKEN_TTL;
  const oldConfig = process.env.ANIP_ADAPTER_CONFIG;

  delete process.env.ANIP_SERVICE_URL;
  delete process.env.ANIP_ADAPTER_PORT;
  delete process.env.ANIP_ISSUER;
  delete process.env.ANIP_SCOPE;
  delete process.env.ANIP_TOKEN_TTL;
  delete process.env.ANIP_ADAPTER_CONFIG;

  const cfg = loadConfig("/nonexistent/path.yaml");

  if (oldUrl) process.env.ANIP_SERVICE_URL = oldUrl;
  if (oldPort) process.env.ANIP_ADAPTER_PORT = oldPort;
  if (oldIssuer) process.env.ANIP_ISSUER = oldIssuer;
  if (oldScope) process.env.ANIP_SCOPE = oldScope;
  if (oldTtl) process.env.ANIP_TOKEN_TTL = oldTtl;
  if (oldConfig) process.env.ANIP_ADAPTER_CONFIG = oldConfig;

  assert(
    cfg.anipServiceUrl === "http://localhost:8000",
    "default service URL",
    `got ${cfg.anipServiceUrl}`
  );
  assert(cfg.port === 3002, "default port", `got ${cfg.port}`);
  assert(
    cfg.delegation.issuer === "human:user@example.com",
    "default issuer",
    `got ${cfg.delegation.issuer}`
  );
  assert(
    JSON.stringify(cfg.delegation.scope) === JSON.stringify(["*"]),
    "default scope",
    `got ${JSON.stringify(cfg.delegation.scope)}`
  );
  assert(
    cfg.delegation.tokenTtlMinutes === 60,
    "default TTL",
    `got ${cfg.delegation.tokenTtlMinutes}`
  );
  assert(
    cfg.graphqlPath === "/graphql",
    "default graphql path",
    `got ${cfg.graphqlPath}`
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
// 3. Schema generation
// ---------------------------------------------------------------------------

async function testSchemaGeneration(anipUrl: string): Promise<void> {
  console.log("\n--- Schema generation ---");

  const service = await discoverService(anipUrl);
  const sdl = generateSchema(service);

  // Directives present
  assert(sdl.includes("directive @anipSideEffect"), "SDL has @anipSideEffect directive");
  assert(sdl.includes("directive @anipCost"), "SDL has @anipCost directive");
  assert(sdl.includes("directive @anipRequires"), "SDL has @anipRequires directive");
  assert(sdl.includes("directive @anipScope"), "SDL has @anipScope directive");

  // Shared types
  assert(sdl.includes("scalar JSON"), "SDL has JSON scalar");
  assert(sdl.includes("type CostActual"), "SDL has CostActual type");
  assert(sdl.includes("type ANIPFailure"), "SDL has ANIPFailure type");
  assert(sdl.includes("type Resolution"), "SDL has Resolution type");

  // Query and Mutation
  assert(sdl.includes("type Query"), "SDL has Query type");
  assert(sdl.includes("type Mutation"), "SDL has Mutation type");

  // camelCase names
  assert(sdl.includes("searchFlights"), "SDL uses camelCase searchFlights");
  assert(sdl.includes("bookFlight"), "SDL uses camelCase bookFlight");

  // Result types (PascalCase)
  assert(sdl.includes("SearchFlightsResult"), "SDL has SearchFlightsResult type");
  assert(sdl.includes("BookFlightResult"), "SDL has BookFlightResult type");

  // searchFlights is in Query (read), bookFlight is in Mutation
  const queryStart = sdl.indexOf("type Query");
  const queryEnd = sdl.indexOf("}", queryStart);
  const queryBlock = sdl.substring(queryStart, queryEnd + 1);
  assert(queryBlock.includes("searchFlights"), "searchFlights is in Query type");

  const mutationStart = sdl.indexOf("type Mutation");
  const mutationEnd = sdl.indexOf("}", mutationStart);
  const mutationBlock = sdl.substring(mutationStart, mutationEnd + 1);
  assert(mutationBlock.includes("bookFlight"), "bookFlight is in Mutation type");

  // Directives applied to fields
  const afterQuery = sdl.substring(queryStart);
  assert(afterQuery.includes("@anipSideEffect"), "fields have @anipSideEffect");

  // Verify schema can be built with buildSchema()
  try {
    buildSchema(sdl);
    ok("SDL can be parsed by buildSchema()");
  } catch (e) {
    fail("SDL can be parsed by buildSchema()", String(e));
  }
}

// ---------------------------------------------------------------------------
// 4. Invocation
// ---------------------------------------------------------------------------

async function testInvocation(anipUrl: string): Promise<void> {
  console.log("\n--- Invocation ---");

  const service = await discoverService(anipUrl);
  const invoker = new ANIPInvoker(service, {
    issuer: "human:test@example.com",
    scope: ["*"],
    tokenTtlMinutes: 60,
  });
  await invoker.setup();

  // Search flights
  const result = await invoker.invoke("search_flights", {
    origin: "SEA",
    destination: "SFO",
    date: "2026-03-10",
    passengers: 1,
  });
  assert(typeof result === "object", "search_flights returns dict");
  assert(result.success === true, "search_flights succeeds");
  assert("result" in result, "search_flights has result");

  // Book flight
  const bookResult = await invoker.invoke("book_flight", {
    flight_number: "AA100",
    date: "2026-03-10",
    passengers: 1,
  });
  assert(typeof bookResult === "object", "book_flight returns dict");
  assert("success" in bookResult, "book_flight has success key");
}

// ---------------------------------------------------------------------------
// 5. Full server (Hono app.request)
// ---------------------------------------------------------------------------

async function testServer(anipUrl: string): Promise<void> {
  console.log("\n--- Server (Hono + graphql-js) ---");

  const config: AdapterConfig = {
    anipServiceUrl: anipUrl,
    port: 0,
    delegation: {
      issuer: "human:user@example.com",
      scope: ["*"],
      tokenTtlMinutes: 60,
    },
    graphqlPath: "/graphql",
  };

  const app = await buildApp(config);

  // GET /schema.graphql returns SDL
  let resp = await app.request("/schema.graphql");
  assert(resp.status === 200, "GET /schema.graphql returns 200");
  const sdl = await resp.text();
  assert(sdl.includes("type Query"), "schema.graphql contains Query type");
  assert(
    sdl.includes("directive @anipSideEffect"),
    "schema.graphql has directives"
  );

  // POST /graphql with searchFlights query
  resp = await app.request("/graphql", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: `query {
        searchFlights(
          origin: "SEA"
          destination: "SFO"
          date: "2026-03-10"
        ) {
          success
          result
        }
      }`,
    }),
  });
  assert(resp.status === 200, "POST /graphql searchFlights returns 200");
  let data = (await resp.json()) as Record<string, unknown>;
  const errors = data.errors as unknown[] | undefined;
  assert(
    !errors || errors.length === 0,
    `searchFlights has no errors`,
    JSON.stringify(errors)
  );
  const searchData = ((data.data as Record<string, unknown>) ?? {})
    .searchFlights as Record<string, unknown> | undefined;
  assert(searchData?.success === true, "searchFlights success is true");
  assert(searchData?.result != null, "searchFlights has result");

  // POST /graphql with bookFlight mutation
  resp = await app.request("/graphql", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: `mutation {
        bookFlight(
          flightNumber: "AA100"
          date: "2026-03-10"
          passengers: 1
        ) {
          success
          result
          costActual {
            financial {
              amount
              currency
            }
            varianceFromEstimate
          }
        }
      }`,
    }),
  });
  assert(resp.status === 200, "POST /graphql bookFlight returns 200");
  data = (await resp.json()) as Record<string, unknown>;
  const bookErrors = data.errors as unknown[] | undefined;
  assert(
    !bookErrors || bookErrors.length === 0,
    `bookFlight has no errors`,
    JSON.stringify(bookErrors)
  );
  const bookData = ((data.data as Record<string, unknown>) ?? {})
    .bookFlight as Record<string, unknown> | undefined;
  assert(bookData != null && "success" in bookData, "bookFlight has success key");

  // GET /graphql returns HTML playground
  resp = await app.request("/graphql");
  assert(resp.status === 200, "GET /graphql returns 200 (playground)");
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
  console.log(`Testing ANIP GraphQL adapter (TS) against ${anipUrl}`);

  // 1. Config (sync)
  testConfigDefaults();

  // 2-5. Async tests
  await testDiscovery(anipUrl);
  await testSchemaGeneration(anipUrl);
  await testInvocation(anipUrl);
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
