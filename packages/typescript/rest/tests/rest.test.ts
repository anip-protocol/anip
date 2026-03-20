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

describe("OpenAPI", () => {
  it("GET /rest/openapi.json returns spec", async () => {
    const { app } = await makeApp();
    const res = await app.request("/rest/openapi.json");
    expect(res.status).toBe(200);
    const spec = await res.json();
    expect(spec.openapi).toBe("3.1.0");
    expect(spec.paths["/api/greet"]).toBeDefined();
    expect(spec.paths["/api/book"]).toBeDefined();
  });

  it("GET /rest/docs returns Swagger UI", async () => {
    const { app } = await makeApp();
    const res = await app.request("/rest/docs");
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
