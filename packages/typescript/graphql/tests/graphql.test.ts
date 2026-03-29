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
