import { describe, it, expect, afterEach } from "vitest";
import express from "express";
import request from "supertest";
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
  const app = express();
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const { stop } = mountAnip(app, service);
  return { app, stop };
}

describe("Express routes", () => {
  let stopFn: (() => void) | undefined;

  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("GET /.well-known/anip returns discovery", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await request(app).get("/.well-known/anip");
    expect(res.status).toBe(200);
    expect(res.body.anip_discovery).toBeDefined();
    expect(res.body.anip_discovery.capabilities.greet).toBeDefined();
  });

  it("GET /.well-known/jwks.json returns keys", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await request(app).get("/.well-known/jwks.json");
    expect(res.status).toBe(200);
    expect(res.body.keys).toBeDefined();
  });

  it("GET /anip/manifest returns signed manifest", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await request(app).get("/anip/manifest");
    expect(res.status).toBe(200);
    expect(res.headers["x-anip-signature"]).toBeTruthy();
  });

  it("GET /anip/checkpoints returns list", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await request(app).get("/anip/checkpoints");
    expect(res.status).toBe(200);
    expect(res.body.checkpoints).toBeDefined();
  });

  it("GET /anip/checkpoints/:id returns 404 for unknown", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await request(app).get("/anip/checkpoints/ckpt-nonexistent");
    expect(res.status).toBe(404);
  });

  it("POST /anip/tokens without auth returns 401", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await request(app)
      .post("/anip/tokens")
      .send({ scope: ["greet"] });
    expect(res.status).toBe(401);
  });

  it("POST /anip/invoke/:capability with valid token succeeds", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;

    // Get a token first
    const tokenRes = await request(app)
      .post("/anip/tokens")
      .set("Authorization", `Bearer ${API_KEY}`)
      .send({ scope: ["greet"], capability: "greet" });
    expect(tokenRes.status).toBe(200);
    const token = tokenRes.body.token;

    // Invoke
    const res = await request(app)
      .post("/anip/invoke/greet")
      .set("Authorization", `Bearer ${token}`)
      .send({ parameters: { name: "World" } });
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.result.message).toBe("Hello, World!");
  });

  it("stop() can be called without error", () => {
    const { stop } = makeApp();
    stop(); // Should not throw
  });
});
