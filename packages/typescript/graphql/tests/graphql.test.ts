import { describe, it, expect } from "vitest";
import { Hono } from "hono";
import { createANIPService, defineCapability } from "@anip-dev/service";
import { InMemoryStorage } from "@anip-dev/server";
import type { CapabilityDeclaration } from "@anip-dev/core";
import { mountAnip } from "@anip-dev/hono";
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

  it("query with invalid JWT returns invalid_token failure", async () => {
    const { app, shutdown } = await makeApp();
    const res = await app.request("/graphql", {
      method: "POST",
      headers: {
        "Authorization": "Bearer garbage-not-a-jwt",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: '{ greet(name: "World") { success failure { type detail } } }',
      }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.data.greet.success).toBe(false);
    expect(data.data.greet.failure.type).toBe("invalid_token");
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

// SPEC.md §6.3 "Parameter Validation" through the GraphQL adapter. The schema
// marks a required input non-null, so GraphQL itself refuses a query that
// leaves one out; a value that the schema lets through (the JSON scalar of an
// `object` or `array` input) is checked by the service and comes back in the
// adapter's failure shape.
describe("GraphQL parameter validation", () => {
  async function makeValidationApp() {
    const calls: string[] = [];
    const service = createANIPService({
      serviceId: "test-graphql-validation",
      capabilities: [
        defineCapability({
          declaration: {
            name: "price_quote",
            description: "Price a quote",
            contract_version: "1.0",
            inputs: [
              { name: "quote", type: "object", required: true, description: "The quote" },
              { name: "tags", type: "array", required: false, description: "Tags" },
            ],
            output: { type: "object", fields: ["ok"] },
            side_effect: { type: "read", rollback_window: "not_applicable" },
            minimum_scope: ["quote"],
            response_modes: ["unary"],
          } as CapabilityDeclaration,
          handler: () => {
            calls.push("price_quote");
            return { ok: true };
          },
        }),
      ],
      storage: new InMemoryStorage(),
      authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
    });
    const app = new Hono();
    const { shutdown } = await mountAnip(app, service);
    await mountAnipGraphQL(app, service);
    return { app, shutdown, calls };
  }

  const SELECTION = "{ success result failure { type detail retry resolution { action recoveryClass requires } } }";

  async function run(app: Hono, query: string, variables?: Record<string, unknown>) {
    const res = await app.request("/graphql", {
      method: "POST",
      headers: { "Authorization": `Bearer ${API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({ query, variables }),
    });
    expect(res.status).toBe(200);
    return res.json();
  }

  it("a valid call reaches the handler", async () => {
    const { app, shutdown, calls } = await makeValidationApp();
    const data = await run(app, `query($q: JSON!) { priceQuote(quote: $q) ${SELECTION} }`, { q: { id: "q1" } });
    expect(data.errors).toBeUndefined();
    expect(data.data.priceQuote.success).toBe(true);
    expect(calls).toEqual(["price_quote"]);
    await shutdown();
  });

  it("a value of the wrong JSON type is an invalid_parameters failure in the result", async () => {
    const { app, shutdown, calls } = await makeValidationApp();
    const data = await run(
      app,
      `query($q: JSON!, $t: JSON) { priceQuote(quote: $q, tags: $t) ${SELECTION} }`,
      { q: "not-an-object", t: { not: "an array" } },
    );
    expect(data.errors).toBeUndefined();
    expect(data.data.priceQuote.success).toBe(false);
    expect(data.data.priceQuote.result).toBeNull();
    expect(data.data.priceQuote.failure).toEqual({
      type: "invalid_parameters",
      detail: "price_quote has invalid input(s): 'quote' must be object, got string; 'tags' must be array, got object",
      retry: false,
      resolution: {
        action: "retry_now",
        recoveryClass: "retry_now",
        requires: "parameters that match the capability's declared inputs",
      },
    });
    expect(calls).toEqual([]);
    await shutdown();
  });

  it("a required input passed as null through a variable is refused before the handler", async () => {
    const { app, shutdown, calls } = await makeValidationApp();
    // GraphQL refuses null for a non-null argument itself.
    const data = await run(app, `query($q: JSON!) { priceQuote(quote: $q) ${SELECTION} }`, { q: null });
    expect(data.errors).toBeDefined();
    expect(calls).toEqual([]);
    await shutdown();
  });

  it("a query that leaves out a required input is refused by the schema", async () => {
    const { app, shutdown, calls } = await makeValidationApp();
    const data = await run(app, `{ priceQuote ${SELECTION} }`);
    expect(data.errors).toBeDefined();
    expect(String(data.errors[0].message)).toContain("quote");
    expect(calls).toEqual([]);
    await shutdown();
  });
});

// SPEC.md §4.10: a required input that sets resolution.on_missing is answered
// by the service, so the schema must not make its argument non-null.
describe("GraphQL inputs that declare resolution.on_missing", () => {
  function clarifyDeclaration() {
    return {
      name: "list_orders",
      description: "List orders",
      contract_version: "1.0",
      inputs: [
        { name: "status", type: "string", required: true, description: "Order status" },
        {
          name: "region", type: "string", required: true, description: "Region",
          resolution: { mode: "clarify", on_missing: "clarify" },
        },
        {
          name: "channel", type: "string", required: true, description: "Channel",
          resolution: { mode: "clarify" },
        },
      ],
      output: { type: "object", fields: ["orders"] },
      side_effect: { type: "read", rollback_window: "not_applicable" },
      minimum_scope: ["orders"],
      response_modes: ["unary"],
    } as unknown as CapabilityDeclaration;
  }

  it("are nullable arguments in the schema", () => {
    const sdl = generateSchema({ list_orders: clarifyDeclaration() as unknown as Record<string, unknown> });
    expect(sdl).toContain("listOrders(status: String!, region: String, channel: String!): ListOrdersResult!");
  });

  it("reach the handler when the query leaves them out", async () => {
    const calls: Array<Record<string, unknown>> = [];
    const service = createANIPService({
      serviceId: "test-graphql-on-missing",
      capabilities: [
        defineCapability({
          declaration: clarifyDeclaration(),
          handler: (_ctx, params) => {
            calls.push({ ...params });
            return { orders: [] };
          },
        }),
      ],
      storage: new InMemoryStorage(),
      authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
    });
    const app = new Hono();
    const { shutdown } = await mountAnip(app, service);
    await mountAnipGraphQL(app, service);
    const run = async (query: string) => {
      const res = await app.request("/graphql", {
        method: "POST",
        headers: { "Authorization": `Bearer ${API_KEY}`, "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      return res.json();
    };

    const ok = await run('{ listOrders(status: "open", channel: "web") { success failure { type detail } } }');
    expect(ok.errors).toBeUndefined();
    expect(ok.data.listOrders.success).toBe(true);
    expect(calls).toEqual([{ status: "open", channel: "web" }]);

    // `channel` declares a resolution without on_missing: the schema still demands it.
    const refused = await run('{ listOrders(status: "open") { success } }');
    expect(refused.errors).toBeDefined();
    expect(calls).toHaveLength(1);
    await shutdown();
  });
});
