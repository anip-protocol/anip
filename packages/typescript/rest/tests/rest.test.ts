import { describe, it, expect } from "vitest";
import { Hono } from "hono";
import { ANIPError, createANIPService, defineCapability } from "@anip-dev/service";
import { InMemoryStorage } from "@anip-dev/server";
import { failureStatusCode, type CapabilityDeclaration } from "@anip-dev/core";
import { mountAnip } from "@anip-dev/hono";
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

// SPEC.md §6.3 "Parameter Validation" through the REST adapter.
describe("Parameter validation", () => {
  const RESOLUTION = {
    action: "retry_now",
    recovery_class: "retry_now",
    requires: "parameters that match the capability's declared inputs",
  };

  it("GET without a required input is an invalid_parameters failure", async () => {
    const { app } = await makeApp();
    const res = await app.request("/api/greet", {
      headers: { "Authorization": `Bearer ${API_KEY}` },
    });
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.result).toBeUndefined();
    expect(data.failure).toEqual({
      type: "invalid_parameters",
      detail: "greet is missing required input(s): name",
      resolution: RESOLUTION,
      retry: false,
    });
  });

  it("POST without a required input is an invalid_parameters failure", async () => {
    const { app } = await makeApp();
    const res = await app.request("/api/book", {
      method: "POST",
      headers: { "Authorization": `Bearer ${API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure).toEqual({
      type: "invalid_parameters",
      detail: "book is missing required input(s): item",
      resolution: RESOLUTION,
      retry: false,
    });
  });

  it("POST with a value of the wrong JSON type is an invalid_parameters failure", async () => {
    const { app } = await makeApp();
    const res = await app.request("/api/book", {
      method: "POST",
      headers: { "Authorization": `Bearer ${API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({ parameters: { item: 7 } }),
    });
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("invalid_parameters");
    expect(data.failure.detail).toBe("book has invalid input(s): 'item' must be string, got number");
  });
});

// SPEC.md §6.3 "HTTP Status Codes": the REST adapter answers a failure with
// the status of its type, like the protocol endpoints.
describe("HTTP status per failure type", () => {
  async function issueJwt(app: Hono, scope: string[], capability: string): Promise<string> {
    const res = await app.request("/anip/tokens", {
      method: "POST",
      headers: { "Authorization": `Bearer ${API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({ subject: "test-agent", scope, capability }),
    });
    expect(res.status).toBe(200);
    return (await res.json()).token as string;
  }

  function postBook(app: Hono, bearer: string | null, body: string) {
    return app.request("/api/book", {
      method: "POST",
      headers: {
        ...(bearer === null ? {} : { "Authorization": `Bearer ${bearer}` }),
        "Content-Type": "application/json",
      },
      body,
    });
  }

  it("the OpenAPI document lists the statuses a failure can have", async () => {
    const { app } = await makeApp();
    const spec = await (await app.request("/rest/openapi.json")).json();
    const responses = spec.paths["/api/book"].post.responses;
    expect(Object.keys(responses).sort()).toEqual(["200", "400", "401", "403", "404", "409", "500", "503"]);
  });

  it("a successful invocation is 200", async () => {
    const { app } = await makeApp();
    const res = await postBook(app, API_KEY, JSON.stringify({ item: "flight" }));
    expect(res.status).toBe(200);
    expect((await res.json()).success).toBe(true);
  });

  it("invalid_parameters from the invocation is 400", async () => {
    const { app } = await makeApp();

    const get = await app.request("/api/greet", { headers: { "Authorization": `Bearer ${API_KEY}` } });
    expect(get.status).toBe(failureStatusCode("invalid_parameters"));
    expect(get.status).toBe(400);
    expect((await get.json()).failure.type).toBe("invalid_parameters");

    const post = await postBook(app, API_KEY, "{}");
    expect(post.status).toBe(400);
    expect((await post.json()).failure.type).toBe("invalid_parameters");
  });

  it("scope_insufficient and purpose_mismatch from the invocation are 403", async () => {
    const { app } = await makeApp();

    const narrow = await postBook(app, await issueJwt(app, ["greet"], "book"), JSON.stringify({ item: "x" }));
    expect((await narrow.json()).failure.type).toBe("scope_insufficient");
    expect(narrow.status).toBe(403);

    const other = await postBook(app, await issueJwt(app, ["greet", "book"], "greet"), JSON.stringify({ item: "x" }));
    expect((await other.json()).failure.type).toBe("purpose_mismatch");
    expect(other.status).toBe(403);
  });

  it("a failure type the table does not list is 400", async () => {
    const service = createANIPService({
      serviceId: "test-rest-status",
      capabilities: [
        defineCapability({
          declaration: {
            name: "sold_out",
            description: "Always sold out",
            contract_version: "1.0",
            inputs: [],
            output: { type: "object", fields: [] },
            side_effect: { type: "irreversible", rollback_window: "none" },
            minimum_scope: ["book"],
            response_modes: ["unary"],
          } as CapabilityDeclaration,
          handler: () => {
            throw new ANIPError("capability_unavailable", "sold out");
          },
        }),
        defineCapability({
          declaration: {
            name: "crash",
            description: "Always crashes",
            contract_version: "1.0",
            inputs: [],
            output: { type: "object", fields: [] },
            side_effect: { type: "irreversible", rollback_window: "none" },
            minimum_scope: ["book"],
            response_modes: ["unary"],
          } as CapabilityDeclaration,
          handler: () => {
            throw new Error("boom");
          },
        }),
      ],
      storage: new InMemoryStorage(),
      authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
    });
    const app = new Hono();
    await mountAnip(app, service);
    await mountAnipRest(app, service);
    const post = (path: string) =>
      app.request(path, {
        method: "POST",
        headers: { "Authorization": `Bearer ${API_KEY}`, "Content-Type": "application/json" },
        body: "{}",
      });

    const soldOut = await post("/api/sold_out");
    expect((await soldOut.json()).failure.type).toBe("capability_unavailable");
    expect(soldOut.status).toBe(400);

    const crash = await post("/api/crash");
    expect((await crash.json()).failure.type).toBe("internal_error");
    expect(crash.status).toBe(500);
  });

  it("a request body that is not JSON is invalid_parameters, 400", async () => {
    const { app } = await makeApp();

    for (const body of ['{"item": ', "[1]", '"x"', "null"]) {
      const res = await postBook(app, API_KEY, body);
      expect(res.status, body).toBe(400);
      const data = await res.json();
      expect(data.success, body).toBe(false);
      expect(data.failure.type, body).toBe("invalid_parameters");
      expect(data.failure.resolution, body).toMatchObject({ action: "retry_now", recovery_class: "retry_now" });
      expect(data.failure.retry, body).toBe(false);
    }
  });

  it("the credential is checked before the body", async () => {
    const { app } = await makeApp();

    const none = await postBook(app, null, '{"item": ');
    expect(none.status).toBe(401);
    expect((await none.json()).failure.type).toBe("authentication_required");

    const bad = await postBook(app, "garbage-not-a-jwt", '{"item": ');
    expect(bad.status).toBe(401);
    expect((await bad.json()).failure.type).toBe("invalid_token");
  });
});

// SPEC.md §4.10: a required input that sets resolution.on_missing is answered
// by the service, so the OpenAPI document must not mark it required.
describe("Inputs that declare resolution.on_missing", () => {
  async function makeClarifyApp() {
    const calls: Array<Record<string, unknown>> = [];
    const inputs = [
      { name: "status", type: "string", required: true, description: "Order status" },
      {
        name: "region", type: "string", required: true, description: "Region",
        resolution: { mode: "clarify", on_missing: "clarify" },
      },
      {
        name: "channel", type: "string", required: true, description: "Channel",
        resolution: { mode: "clarify" },
      },
    ];
    const cap = (name: string, sideEffect: Record<string, unknown>) =>
      defineCapability({
        declaration: {
          name,
          description: name,
          contract_version: "1.0",
          inputs,
          output: { type: "object", fields: ["orders"] },
          side_effect: sideEffect,
          minimum_scope: ["orders"],
          response_modes: ["unary"],
        } as unknown as CapabilityDeclaration,
        handler: (_ctx, params) => {
          calls.push({ ...params });
          return { orders: [] };
        },
      });
    const service = createANIPService({
      serviceId: "test-rest-on-missing",
      capabilities: [
        cap("list_orders", { type: "read", rollback_window: "not_applicable" }),
        cap("archive_orders", { type: "irreversible", rollback_window: "none" }),
      ],
      storage: new InMemoryStorage(),
      authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
    });
    const app = new Hono();
    await mountAnip(app, service);
    await mountAnipRest(app, service);
    return { app, calls };
  }

  it("are not required in the OpenAPI document", async () => {
    const { app } = await makeClarifyApp();
    const spec = await (await app.request("/rest/openapi.json")).json();

    const query = Object.fromEntries(
      spec.paths["/api/list_orders"].get.parameters.map((p: Record<string, unknown>) => [p.name, p.required]),
    );
    expect(query).toEqual({ status: true, region: false, channel: true });

    const body = spec.paths["/api/archive_orders"].post.requestBody.content["application/json"].schema;
    expect(Object.keys(body.properties)).toEqual(["status", "region", "channel"]);
    expect(body.required).toEqual(["status", "channel"]);
  });

  it("reach the handler when the request leaves them out", async () => {
    const { app, calls } = await makeClarifyApp();

    const get = await app.request("/api/list_orders?status=open&channel=web", {
      headers: { "Authorization": `Bearer ${API_KEY}` },
    });
    expect(get.status).toBe(200);

    const post = await app.request("/api/archive_orders", {
      method: "POST",
      headers: { "Authorization": `Bearer ${API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({ status: "open", channel: "web", region: null }),
    });
    expect(post.status).toBe(200);
    expect(calls).toEqual([
      { status: "open", channel: "web" },
      { status: "open", channel: "web", region: null },
    ]);

    // `channel` declares a resolution without on_missing: it is still required.
    const refused = await app.request("/api/list_orders?status=open", {
      headers: { "Authorization": `Bearer ${API_KEY}` },
    });
    expect(refused.status).toBe(400);
    expect((await refused.json()).failure.detail).toBe("list_orders is missing required input(s): channel");
  });
});

// The service checks a supplied value against a declared primitive type
// (SPEC.md §6.3), so the OpenAPI document has to name that same JSON type,
// and a query string has to be able to carry an object or an array.
describe("Declared primitive types", () => {
  async function makeTypedApp() {
    const calls: Array<Record<string, unknown>> = [];
    const inputs = [
      { name: "quote", type: "object", required: true, description: "The quote" },
      { name: "tags", type: "array", required: false, description: "Tags" },
      { name: "count", type: "integer", required: false, description: "Count" },
      { name: "sku", type: "product_code", required: false, description: "A domain type" },
    ];
    const cap = (name: string, sideEffect: Record<string, unknown>) =>
      defineCapability({
        declaration: {
          name,
          description: name,
          contract_version: "1.0",
          inputs,
          output: { type: "object", fields: ["ok"] },
          side_effect: sideEffect,
          minimum_scope: ["quote"],
          response_modes: ["unary"],
        } as unknown as CapabilityDeclaration,
        handler: (_ctx, params) => {
          calls.push({ ...params });
          return { ok: true };
        },
      });
    const service = createANIPService({
      serviceId: "test-rest-types",
      capabilities: [
        cap("read_quote", { type: "read", rollback_window: "not_applicable" }),
        cap("save_quote", { type: "irreversible", rollback_window: "none" }),
      ],
      storage: new InMemoryStorage(),
      authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
    });
    const app = new Hono();
    await mountAnip(app, service);
    await mountAnipRest(app, service);
    return { app, calls };
  }

  it("the OpenAPI document names the JSON type the service will accept", async () => {
    const { app } = await makeTypedApp();
    const spec = await (await app.request("/rest/openapi.json")).json();
    const expected = { quote: "object", tags: "array", count: "integer", sku: "string" };

    const body = spec.paths["/api/save_quote"].post.requestBody.content["application/json"].schema;
    expect(Object.fromEntries(Object.entries(body.properties).map(([n, p]: [string, any]) => [n, p.type]))).toEqual(expected);

    const query = spec.paths["/api/read_quote"].get.parameters;
    expect(Object.fromEntries(query.map((p: any) => [p.name, p.schema.type]))).toEqual(expected);
  });

  it("a GET carries an object or array input as JSON in the query string", async () => {
    const { app, calls } = await makeTypedApp();
    const query = new URLSearchParams({
      quote: JSON.stringify({ id: "q1", price: 420 }),
      tags: JSON.stringify(["a", "b"]),
      count: "2",
      sku: "{not-json",
    });

    const res = await app.request(`/api/read_quote?${query}`, { headers: { "Authorization": `Bearer ${API_KEY}` } });

    expect(res.status).toBe(200);
    expect(calls).toEqual([{ quote: { id: "q1", price: 420 }, tags: ["a", "b"], count: 2, sku: "{not-json" }]);
  });

  it("a GET with a query value that is not the declared type is refused", async () => {
    const { app, calls } = await makeTypedApp();

    for (const [quote, received] of [["not-json", "string"], ["[1]", "array"], ["7", "number"]]) {
      const res = await app.request(`/api/read_quote?quote=${encodeURIComponent(quote)}`, {
        headers: { "Authorization": `Bearer ${API_KEY}` },
      });
      expect(res.status).toBe(400);
      expect((await res.json()).failure.detail).toBe(
        `read_quote has invalid input(s): 'quote' must be object, got ${received}`,
      );
    }
    expect(calls).toEqual([]);
  });

  it("a GET reads numbers and booleans as JSON does", async () => {
    const calls: Array<Record<string, unknown>> = [];
    const service = createANIPService({
      serviceId: "test-rest-query",
      capabilities: [
        defineCapability({
          declaration: {
            name: "page",
            description: "page",
            contract_version: "1.0",
            inputs: [
              { name: "size", type: "integer", required: false, description: "Size" },
              { name: "ratio", type: "number", required: false, description: "Ratio" },
              { name: "all", type: "boolean", required: false, description: "All" },
            ],
            output: { type: "object", fields: ["ok"] },
            side_effect: { type: "read", rollback_window: "not_applicable" },
            minimum_scope: ["page"],
            response_modes: ["unary"],
          } as unknown as CapabilityDeclaration,
          handler: (_ctx, params) => {
            calls.push({ ...params });
            return { ok: true };
          },
        }),
      ],
      storage: new InMemoryStorage(),
      authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
    });
    const app = new Hono();
    await mountAnip(app, service);
    await mountAnipRest(app, service);
    const get = (query: string) => app.request(`/api/page?${query}`, { headers: { "Authorization": `Bearer ${API_KEY}` } });

    expect((await get("size=5.0&ratio=1e2&all=false")).status).toBe(200);
    expect(calls).toEqual([{ size: 5, ratio: 100, all: false }]);

    for (const [query, detail] of [
      ["size=1.5", "'size' must be integer, got number"],
      ["size=2abc", "'size' must be integer, got string"],
      ["ratio=abc", "'ratio' must be number, got string"],
      ["all=yes", "'all' must be boolean, got string"],
    ]) {
      const res = await get(query);
      expect(res.status, query).toBe(400);
      expect((await res.json()).failure.detail, query).toBe(`page has invalid input(s): ${detail}`);
    }
    expect(calls).toHaveLength(1);
  });
});
