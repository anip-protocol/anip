import { describe, it, expect, afterEach } from "vitest";
import Fastify from "fastify";
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
  const app = Fastify();
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const { stop } = await mountAnip(app, service);
  return { app, stop };
}

describe("Fastify routes", () => {
  let stopFn: (() => void) | undefined;

  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("GET /.well-known/anip returns discovery", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await app.inject({ method: "GET", url: "/.well-known/anip" });
    expect(res.statusCode).toBe(200);
    const data = res.json();
    expect(data.anip_discovery).toBeDefined();
    expect(data.anip_discovery.capabilities.greet).toBeDefined();
  });

  it("GET /.well-known/jwks.json returns keys", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await app.inject({ method: "GET", url: "/.well-known/jwks.json" });
    expect(res.statusCode).toBe(200);
    expect(res.json().keys).toBeDefined();
  });

  it("GET /anip/manifest returns signed manifest", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await app.inject({ method: "GET", url: "/anip/manifest" });
    expect(res.statusCode).toBe(200);
    expect(res.headers["x-anip-signature"]).toBeTruthy();
  });

  it("GET /anip/checkpoints returns list", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await app.inject({ method: "GET", url: "/anip/checkpoints" });
    expect(res.statusCode).toBe(200);
    expect(res.json().checkpoints).toBeDefined();
  });

  it("GET /anip/checkpoints/:id returns 404 for unknown", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await app.inject({ method: "GET", url: "/anip/checkpoints/ckpt-nonexistent" });
    expect(res.statusCode).toBe(404);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("not_found");
  });

  it("POST /anip/tokens without auth returns 401", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      payload: { scope: ["greet"] },
    });
    expect(res.statusCode).toBe(401);
  });

  it("POST /anip/invoke/:capability with valid token succeeds", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;

    // Get a token first
    const tokenRes = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      headers: { authorization: `Bearer ${API_KEY}` },
      payload: { scope: ["greet"], capability: "greet" },
    });
    expect(tokenRes.statusCode).toBe(200);
    const token = tokenRes.json().token;

    // Invoke
    const res = await app.inject({
      method: "POST",
      url: "/anip/invoke/greet",
      headers: { authorization: `Bearer ${token}` },
      payload: { parameters: { name: "World" } },
    });
    expect(res.statusCode).toBe(200);
    const data = res.json();
    expect(data.success).toBe(true);
    expect(data.result.message).toBe("Hello, World!");
  });

  it("invoke response has invocation_id", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;

    // Get a token first
    const tokenRes = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      headers: { authorization: `Bearer ${API_KEY}` },
      payload: { scope: ["greet"], capability: "greet" },
    });
    expect(tokenRes.statusCode).toBe(200);
    const token = tokenRes.json().token;

    // Invoke
    const res = await app.inject({
      method: "POST",
      url: "/anip/invoke/greet",
      headers: { authorization: `Bearer ${token}` },
      payload: { parameters: { name: "World" } },
    });
    expect(res.statusCode).toBe(200);
    const data = res.json();
    expect(data.success).toBe(true);
    expect(data.invocation_id).toBeDefined();
    expect(data.invocation_id).toMatch(/^inv-/);
  });

  it("invoke passes client_reference_id", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;

    // Get a token first
    const tokenRes = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      headers: { authorization: `Bearer ${API_KEY}` },
      payload: { scope: ["greet"], capability: "greet" },
    });
    expect(tokenRes.statusCode).toBe(200);
    const token = tokenRes.json().token;

    // Invoke with client_reference_id
    const res = await app.inject({
      method: "POST",
      url: "/anip/invoke/greet",
      headers: { authorization: `Bearer ${token}` },
      payload: {
        parameters: { name: "World" },
        client_reference_id: "my-ref-123",
      },
    });
    expect(res.statusCode).toBe(200);
    const data = res.json();
    expect(data.success).toBe(true);
    expect(data.client_reference_id).toBe("my-ref-123");
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
    const tokenRes = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      headers: { authorization: `Bearer ${API_KEY}` },
      payload: { scope: ["greet"], capability: "greet" },
    });
    const token = JSON.parse(tokenRes.payload).token;
    const res = await app.inject({
      method: "POST",
      url: "/anip/permissions",
      headers: { authorization: `Bearer ${token}` },
      payload: {},
    });
    expect(res.statusCode).toBe(200);
    const data = JSON.parse(res.payload);
    expect(data.available).toBeDefined();
    expect(data.restricted).toBeDefined();
    expect(data.denied).toBeDefined();
  });

  it("shows restricted for missing scope", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const tokenRes = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      headers: { authorization: `Bearer ${API_KEY}` },
      payload: { scope: ["unrelated"], capability: "greet" },
    });
    const token = JSON.parse(tokenRes.payload).token;
    const res = await app.inject({
      method: "POST",
      url: "/anip/permissions",
      headers: { authorization: `Bearer ${token}` },
      payload: {},
    });
    expect(res.statusCode).toBe(200);
    const data = JSON.parse(res.payload);
    expect(data.restricted.some((c: any) => c.capability === "greet")).toBe(true);
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
    const tokenRes = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      headers: { authorization: `Bearer ${API_KEY}` },
      payload: { scope: ["greet"], capability: "greet" },
    });
    const token = JSON.parse(tokenRes.payload).token;
    await app.inject({
      method: "POST",
      url: "/anip/invoke/greet",
      headers: { authorization: `Bearer ${token}` },
      payload: { parameters: { name: "World" } },
    });
    const res = await app.inject({
      method: "POST",
      url: "/anip/audit",
      headers: { authorization: `Bearer ${token}` },
      payload: {},
    });
    expect(res.statusCode).toBe(200);
    const data = JSON.parse(res.payload);
    expect(data.entries).toBeDefined();
    expect(data.count).toBeGreaterThanOrEqual(1);
  });
});

// --- Health endpoint tests ---

async function makeHealthApp() {
  const app = Fastify();
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const { stop } = await mountAnip(app, service, { healthEndpoint: true });
  return { app, stop };
}

describe("Fastify health endpoint", () => {
  let stopFn: (() => void) | undefined;

  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("is not registered by default", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await app.inject({ method: "GET", url: "/-/health" });
    expect(res.statusCode).toBe(404);
  });

  it("returns health report when enabled", async () => {
    const { app, stop } = await makeHealthApp();
    stopFn = stop;
    const res = await app.inject({ method: "GET", url: "/-/health" });
    expect(res.statusCode).toBe(200);
    const data = res.json();
    expect(data.status).toBeDefined();
    expect(data.storage).toBeDefined();
    expect(data.retention).toBeDefined();
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
    const res = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      payload: { scope: ["greet"] },
    });
    expect(res.statusCode).toBe(401);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("provide_api_key");
    expect(data.failure.retry).toBe(true);
  });

  it("POST /anip/invoke without auth returns ANIPFailure with obtain_delegation_token", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await app.inject({
      method: "POST",
      url: "/anip/invoke/greet",
      payload: { parameters: { name: "X" } },
    });
    expect(res.statusCode).toBe(401);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("obtain_delegation_token");
    expect(data.failure.retry).toBe(true);
  });

  it("POST /anip/permissions without auth returns ANIPFailure with obtain_delegation_token", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await app.inject({
      method: "POST",
      url: "/anip/permissions",
      payload: {},
    });
    expect(res.statusCode).toBe(401);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("obtain_delegation_token");
  });

  it("POST /anip/audit without auth returns ANIPFailure with obtain_delegation_token", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await app.inject({
      method: "POST",
      url: "/anip/audit",
      payload: {},
    });
    expect(res.statusCode).toBe(401);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("obtain_delegation_token");
  });

  it("POST /anip/invoke with invalid JWT returns structured invalid_token", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await app.inject({
      method: "POST",
      url: "/anip/invoke/greet",
      headers: { authorization: "Bearer not-a-valid-jwt" },
      payload: { parameters: { name: "X" } },
    });
    expect(res.statusCode).toBe(401);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("invalid_token");
  });

  it("POST /anip/permissions with invalid JWT returns structured invalid_token", async () => {
    const { app, stop } = await makeApp();
    stopFn = stop;
    const res = await app.inject({
      method: "POST",
      url: "/anip/permissions",
      headers: { authorization: "Bearer not-a-valid-jwt" },
      payload: {},
    });
    expect(res.statusCode).toBe(401);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("invalid_token");
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
  const app = Fastify();
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap(), streamingCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const { stop } = await mountAnip(app, service);
  return { app, stop };
}

describe("Fastify streaming routes", () => {
  let stopFn: (() => void) | undefined;

  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("stream:true returns text/event-stream with progress + completed", async () => {
    const { app, stop } = await makeStreamingApp();
    stopFn = stop;

    // Issue token
    const tokenRes = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${API_KEY}`,
      },
      payload: { subject: "test-agent", scope: ["analyze"], capability: "analyze" },
    });
    const jwt = tokenRes.json().token;

    // Invoke with streaming
    const res = await app.inject({
      method: "POST",
      url: "/anip/invoke/analyze",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwt}`,
      },
      payload: { parameters: { target: "x" }, stream: true },
    });

    expect(res.statusCode).toBe(200);
    expect(res.headers["content-type"]).toContain("text/event-stream");
    expect(res.payload).toContain("event: progress");
    expect(res.payload).toContain("event: completed");
  });

  it("stream:true on unary-only capability returns 400 JSON", async () => {
    const { app, stop } = await makeStreamingApp();
    stopFn = stop;

    const tokenRes = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${API_KEY}`,
      },
      payload: { subject: "test-agent", scope: ["greet"], capability: "greet" },
    });
    const jwt = tokenRes.json().token;

    const res = await app.inject({
      method: "POST",
      url: "/anip/invoke/greet",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwt}`,
      },
      payload: { parameters: { name: "world" }, stream: true },
    });

    expect(res.statusCode).toBe(400);
    expect(res.json().failure.type).toBe("streaming_not_supported");
  });
});
