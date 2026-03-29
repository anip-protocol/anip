import { describe, it, expect } from "vitest";
import { Hono } from "hono";
import { createANIPService, defineCapability } from "@anip-dev/service";
import { mountAnip } from "../src/routes.js";
import { InMemoryStorage } from "@anip-dev/server";
import type { CapabilityDeclaration } from "@anip-dev/core";
import type { InvocationContext } from "@anip-dev/service";

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
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const app = new Hono();
  const { stop } = await mountAnip(app, service);
  return { app, stop };
}

describe("Hono routes", () => {
  it("GET /.well-known/anip returns discovery", async () => {
    const { app } = await makeApp();
    const res = await app.request("/.well-known/anip");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.anip_discovery).toBeDefined();
    expect(data.anip_discovery.capabilities.greet).toBeDefined();
  });

  it("GET /.well-known/jwks.json returns keys", async () => {
    const { app } = await makeApp();
    const res = await app.request("/.well-known/jwks.json");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.keys).toBeDefined();
  });

  it("GET /anip/manifest returns signed manifest", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/manifest");
    expect(res.status).toBe(200);
    expect(res.headers.get("X-ANIP-Signature")).toBeTruthy();
  });

  it("GET /anip/checkpoints returns list", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/checkpoints");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.checkpoints).toBeDefined();
  });

  it("GET /anip/checkpoints/:id returns 404 for unknown", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/checkpoints/ckpt-nonexistent");
    expect(res.status).toBe(404);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("not_found");
  });

  it("invoke response has invocation_id", async () => {
    const { app } = await makeApp();

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
    const { app } = await makeApp();

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

// --- Health endpoint tests ---

async function makeHealthApp() {
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const app = new Hono();
  const { stop } = await mountAnip(app, service, { healthEndpoint: true });
  return { app, stop };
}

describe("Health endpoint", () => {
  it("is not registered by default", async () => {
    const { app } = await makeApp();
    const resp = await app.request("/-/health");
    expect(resp.status).toBe(404);
  });

  it("returns health report when enabled", async () => {
    const { app } = await makeHealthApp();
    const resp = await app.request("/-/health");
    expect(resp.status).toBe(200);
    const data = await resp.json();
    expect(data.status).toBeDefined();
    expect(data.storage).toBeDefined();
    expect(data.retention).toBeDefined();
  });
});

// --- Streaming helpers and tests ---

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
    async handler(ctx: InvocationContext, _params: Record<string, unknown>) {
      await ctx.emitProgress({ step: 1, status: "working" });
      return { result: "done" };
    },
  });
}

async function makeStreamingApp() {
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap(), streamingCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const app = new Hono();
  const { stop } = await mountAnip(app, service);
  return { app, stop };
}

async function issueToken(app: Hono, scope: string[], capability: string): Promise<string> {
  const res = await app.request("/anip/tokens", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({ subject: "test-agent", scope, capability }),
  });
  const data = await res.json();
  return data.token;
}

describe("Auth error responses", () => {
  it("POST /anip/tokens without auth returns ANIPFailure", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/tokens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: ["greet"] }),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("provide_api_key");
    expect(data.failure.retry).toBe(true);
  });

  it("POST /anip/invoke without auth returns ANIPFailure", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/invoke/greet", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parameters: { name: "X" } }),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("obtain_delegation_token");
    expect(data.failure.retry).toBe(true);
  });

  it("POST /anip/permissions without auth returns ANIPFailure", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/permissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("obtain_delegation_token");
  });

  it("POST /anip/audit without auth returns ANIPFailure", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("obtain_delegation_token");
  });

  it("POST /anip/invoke with invalid JWT returns structured invalid_token", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/invoke/greet", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer not-a-valid-jwt",
      },
      body: JSON.stringify({ parameters: { name: "X" } }),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("invalid_token");
  });

  it("POST /anip/permissions with invalid JWT returns structured invalid_token", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/permissions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer not-a-valid-jwt",
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("invalid_token");
  });
});

describe("Permissions endpoint", () => {
  it("returns available/restricted/denied buckets", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, ["greet"], "greet");
    const res = await app.request("/anip/permissions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.available).toBeDefined();
    expect(data.restricted).toBeDefined();
    expect(data.denied).toBeDefined();
    expect(data.available.some((c: any) => c.capability === "greet")).toBe(true);
  });

  it("shows restricted for missing scope", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, ["unrelated"], "greet");
    const res = await app.request("/anip/permissions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.restricted.some((c: any) => c.capability === "greet")).toBe(true);
  });
});

describe("Audit endpoint", () => {
  it("returns entries after invocation", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, ["greet"], "greet");
    await app.request("/anip/invoke/greet", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ parameters: { name: "World" } }),
    });
    const res = await app.request("/anip/audit", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.entries).toBeDefined();
    expect(data.count).toBeGreaterThanOrEqual(1);
  });

  it("filters by capability", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, ["greet"], "greet");
    await app.request("/anip/invoke/greet", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ parameters: { name: "World" } }),
    });
    const res = await app.request("/anip/audit?capability=greet", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.capability_filter).toBe("greet");
  });
});

describe("Hono streaming routes", () => {
  it("stream:true returns text/event-stream with progress + completed", async () => {
    const { app } = await makeStreamingApp();
    const jwt = await issueToken(app, ["analyze"], "analyze");
    const res = await app.request("/anip/invoke/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwt}`,
      },
      body: JSON.stringify({ parameters: { target: "x" }, stream: true }),
    });
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/event-stream");
    const body = await res.text();
    expect(body).toContain("event: progress");
    expect(body).toContain("event: completed");
    expect(body).toContain('"result":"done"');
  });

  it("stream:true on unary-only capability returns 400 JSON", async () => {
    const { app } = await makeStreamingApp();
    const jwt = await issueToken(app, ["greet"], "greet");
    const res = await app.request("/anip/invoke/greet", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwt}`,
      },
      body: JSON.stringify({ parameters: { name: "world" }, stream: true }),
    });
    expect(res.status).toBe(400);
    const data = await res.json();
    expect(data.failure.type).toBe("streaming_not_supported");
  });
});
