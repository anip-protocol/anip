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

async function makeApp() {
  const app = express();
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const { stop } = await mountAnip(app, service);
  return { app, stop };
}

describe("Express routes", () => {
  let stopFn: (() => void) | undefined;

  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("GET /.well-known/anip returns discovery", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app).get("/.well-known/anip");
    expect(res.status).toBe(200);
    expect(res.body.anip_discovery).toBeDefined();
    expect(res.body.anip_discovery.capabilities.greet).toBeDefined();
  });

  it("GET /.well-known/jwks.json returns keys", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app).get("/.well-known/jwks.json");
    expect(res.status).toBe(200);
    expect(res.body.keys).toBeDefined();
  });

  it("GET /anip/manifest returns signed manifest", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app).get("/anip/manifest");
    expect(res.status).toBe(200);
    expect(res.headers["x-anip-signature"]).toBeTruthy();
  });

  it("GET /anip/checkpoints returns list", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app).get("/anip/checkpoints");
    expect(res.status).toBe(200);
    expect(res.body.checkpoints).toBeDefined();
  });

  it("GET /anip/checkpoints/:id returns 404 for unknown", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app).get("/anip/checkpoints/ckpt-nonexistent");
    expect(res.status).toBe(404);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("not_found");
  });

  it("POST /anip/tokens without auth returns 401", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app)
      .post("/anip/tokens")
      .send({ scope: ["greet"] });
    expect(res.status).toBe(401);
  });

  it("POST /anip/invoke/:capability with valid token succeeds", async () => {
    const { app, stop } = await makeApp();
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

  it("invoke response has invocation_id", async () => {
    const { app, stop } = await makeApp();
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
    expect(res.body.invocation_id).toBeDefined();
    expect(res.body.invocation_id).toMatch(/^inv-/);
  });

  it("invoke passes client_reference_id", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;

    // Get a token first
    const tokenRes = await request(app)
      .post("/anip/tokens")
      .set("Authorization", `Bearer ${API_KEY}`)
      .send({ scope: ["greet"], capability: "greet" });
    expect(tokenRes.status).toBe(200);
    const token = tokenRes.body.token;

    // Invoke with client_reference_id
    const res = await request(app)
      .post("/anip/invoke/greet")
      .set("Authorization", `Bearer ${token}`)
      .send({
        parameters: { name: "World" },
        client_reference_id: "my-ref-123",
      });
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.client_reference_id).toBe("my-ref-123");
  });

  it("stop() can be called without error", async () => {
    const { stop } = await makeApp();
    stop(); // Should not throw
  });
});

describe("Permissions endpoint", () => {
  let stopFn: (() => void) | undefined;

  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("returns available/restricted/denied buckets", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const tokenRes = await request(app)
      .post("/anip/tokens")
      .set("Authorization", `Bearer ${API_KEY}`)
      .send({ scope: ["greet"], capability: "greet" });
    const token = tokenRes.body.token;
    const res = await request(app)
      .post("/anip/permissions")
      .set("Authorization", `Bearer ${token}`)
      .send({});
    expect(res.status).toBe(200);
    expect(res.body.available).toBeDefined();
    expect(res.body.restricted).toBeDefined();
    expect(res.body.denied).toBeDefined();
  });

  it("shows restricted for missing scope", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const tokenRes = await request(app)
      .post("/anip/tokens")
      .set("Authorization", `Bearer ${API_KEY}`)
      .send({ scope: ["unrelated"], capability: "greet" });
    const token = tokenRes.body.token;
    const res = await request(app)
      .post("/anip/permissions")
      .set("Authorization", `Bearer ${token}`)
      .send({});
    expect(res.status).toBe(200);
    expect(res.body.restricted.some((c: any) => c.capability === "greet")).toBe(true);
  });
});

describe("Audit endpoint", () => {
  let stopFn: (() => void) | undefined;

  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("returns entries after invocation", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const tokenRes = await request(app)
      .post("/anip/tokens")
      .set("Authorization", `Bearer ${API_KEY}`)
      .send({ scope: ["greet"], capability: "greet" });
    const token = tokenRes.body.token;
    await request(app)
      .post("/anip/invoke/greet")
      .set("Authorization", `Bearer ${token}`)
      .send({ parameters: { name: "World" } });
    const res = await request(app)
      .post("/anip/audit")
      .set("Authorization", `Bearer ${token}`)
      .send({});
    expect(res.status).toBe(200);
    expect(res.body.entries).toBeDefined();
    expect(res.body.count).toBeGreaterThanOrEqual(1);
  });
});

// --- Health endpoint tests ---

async function makeHealthApp() {
  const app = express();
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const { stop } = await mountAnip(app, service, { healthEndpoint: true });
  return { app, stop };
}

describe("Express health endpoint", () => {
  let stopFn: (() => void) | undefined;

  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("is not registered by default", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app).get("/-/health");
    expect(res.status).toBe(404);
  });

  it("returns health report when enabled", async () => {
    const { app, stop } = await makeHealthApp();
    stopFn = stop;
    const res = await request(app).get("/-/health");
    expect(res.status).toBe(200);
    expect(res.body.status).toBeDefined();
    expect(res.body.storage).toBeDefined();
    expect(res.body.retention).toBeDefined();
  });
});

describe("Auth error responses", () => {
  let stopFn: (() => void) | undefined;

  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("POST /anip/tokens without auth returns ANIPFailure with provide_api_key", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app)
      .post("/anip/tokens")
      .send({ scope: ["greet"] });
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("authentication_required");
    expect(res.body.failure.resolution.action).toBe("provide_api_key");
    expect(res.body.failure.retry).toBe(true);
  });

  it("POST /anip/invoke without auth returns ANIPFailure with obtain_delegation_token", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app)
      .post("/anip/invoke/greet")
      .send({ parameters: { name: "X" } });
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("authentication_required");
    expect(res.body.failure.resolution.action).toBe("obtain_delegation_token");
    expect(res.body.failure.retry).toBe(true);
  });

  it("POST /anip/permissions without auth returns ANIPFailure with obtain_delegation_token", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app)
      .post("/anip/permissions")
      .send({});
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("authentication_required");
    expect(res.body.failure.resolution.action).toBe("obtain_delegation_token");
  });

  it("POST /anip/audit without auth returns ANIPFailure with obtain_delegation_token", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app)
      .post("/anip/audit")
      .send({});
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("authentication_required");
    expect(res.body.failure.resolution.action).toBe("obtain_delegation_token");
  });

  it("POST /anip/invoke with invalid JWT returns structured invalid_token", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app)
      .post("/anip/invoke/greet")
      .set("Authorization", "Bearer not-a-valid-jwt")
      .send({ parameters: { name: "X" } });
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("invalid_token");
  });

  it("POST /anip/permissions with invalid JWT returns structured invalid_token", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await request(app)
      .post("/anip/permissions")
      .set("Authorization", "Bearer not-a-valid-jwt")
      .send({});
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("invalid_token");
  });
});

function streamingCap() {
  return defineCapability({
    declaration: {
      name: "analyze",
      description: "Long-running analysis",
      contract_version: "1.0",
      inputs: [{ name: "target", type: "string", required: true, description: "target" }],
      output: { type: "object", fields: ["result"] },
      side_effect: { type: "read", rollback_window: "not_applicable" },
      minimum_scope: ["analyze"],
      response_modes: ["unary", "streaming"],
    } as CapabilityDeclaration,
    async handler(ctx, _params) {
      await ctx.emitProgress({ step: 1, status: "working" });
      return { result: "done" };
    },
  });
}

async function makeStreamingApp() {
  const app = express();
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap(), streamingCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const { stop } = await mountAnip(app, service);
  return { app, stop };
}

describe("Express streaming routes", () => {
  let stopFn: (() => void) | undefined;

  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("stream:true returns text/event-stream with progress + completed", async () => {
    const { app, stop } = await makeStreamingApp();
    stopFn = stop;

    // Issue token
    const tokenRes = await request(app)
      .post("/anip/tokens")
      .set("Authorization", `Bearer ${API_KEY}`)
      .send({ subject: "test-agent", scope: ["analyze"], capability: "analyze" });
    const jwt = tokenRes.body.token;

    // Invoke with streaming
    const res = await request(app)
      .post("/anip/invoke/analyze")
      .set("Authorization", `Bearer ${jwt}`)
      .send({ parameters: { target: "x" }, stream: true });

    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toContain("text/event-stream");
    expect(res.text).toContain("event: progress");
    expect(res.text).toContain("event: completed");
  });

  it("stream:true on unary-only capability returns 400 JSON", async () => {
    const { app, stop } = await makeStreamingApp();
    stopFn = stop;

    const tokenRes = await request(app)
      .post("/anip/tokens")
      .set("Authorization", `Bearer ${API_KEY}`)
      .send({ subject: "test-agent", scope: ["greet"], capability: "greet" });
    const jwt = tokenRes.body.token;

    const res = await request(app)
      .post("/anip/invoke/greet")
      .set("Authorization", `Bearer ${jwt}`)
      .send({ parameters: { name: "world" }, stream: true });

    expect(res.status).toBe(400);
    expect(res.body.failure.type).toBe("streaming_not_supported");
  });
});
