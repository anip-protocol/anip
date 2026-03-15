import { describe, it, expect } from "vitest";
import { Hono } from "hono";
import { createANIPService, defineCapability } from "@anip/service";
import { mountAnip } from "../src/routes.js";
import { InMemoryStorage } from "@anip/server";
import type { CapabilityDeclaration } from "@anip/core";

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
    } as CapabilityDeclaration,
    handler: (_ctx, params) => ({ message: `Hello, ${params.name}!` }),
  });
}

const API_KEY = "test-key-123";

function makeApp() {
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const app = new Hono();
  const { stop } = mountAnip(app, service);
  return { app, stop };
}

describe("Hono routes", () => {
  it("GET /.well-known/anip returns discovery", async () => {
    const { app } = makeApp();
    const res = await app.request("/.well-known/anip");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.anip_discovery).toBeDefined();
    expect(data.anip_discovery.capabilities.greet).toBeDefined();
  });

  it("GET /.well-known/jwks.json returns keys", async () => {
    const { app } = makeApp();
    const res = await app.request("/.well-known/jwks.json");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.keys).toBeDefined();
  });

  it("GET /anip/manifest returns signed manifest", async () => {
    const { app } = makeApp();
    const res = await app.request("/anip/manifest");
    expect(res.status).toBe(200);
    expect(res.headers.get("X-ANIP-Signature")).toBeTruthy();
  });

  it("GET /anip/checkpoints returns list", async () => {
    const { app } = makeApp();
    const res = await app.request("/anip/checkpoints");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.checkpoints).toBeDefined();
  });

  it("GET /anip/checkpoints/:id returns 404 for unknown", async () => {
    const { app } = makeApp();
    const res = await app.request("/anip/checkpoints/ckpt-nonexistent");
    expect(res.status).toBe(404);
  });

  it("invoke response has invocation_id", async () => {
    const { app } = makeApp();

    // Get a token first
    const tokenRes = await app.request("/anip/tokens", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${API_KEY}`,
      },
      body: JSON.stringify({ scope: ["greet"], capability: "greet" }),
    });
    expect(tokenRes.status).toBe(200);
    const { token } = await tokenRes.json();

    // Invoke
    const res = await app.request("/anip/invoke/greet", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ parameters: { name: "World" } }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.success).toBe(true);
    expect(data.invocation_id).toBeDefined();
    expect(data.invocation_id).toMatch(/^inv-/);
  });

  it("invoke passes client_reference_id", async () => {
    const { app } = makeApp();

    // Get a token first
    const tokenRes = await app.request("/anip/tokens", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${API_KEY}`,
      },
      body: JSON.stringify({ scope: ["greet"], capability: "greet" }),
    });
    expect(tokenRes.status).toBe(200);
    const { token } = await tokenRes.json();

    // Invoke with client_reference_id
    const res = await app.request("/anip/invoke/greet", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        parameters: { name: "World" },
        client_reference_id: "my-ref-123",
      }),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.success).toBe(true);
    expect(data.client_reference_id).toBe("my-ref-123");
  });
});
