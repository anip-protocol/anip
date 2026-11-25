/**
 * The HTTP status of each failure type and request bodies that are not JSON
 * on the Fastify binding (SPEC.md §6.3 "HTTP Status Codes").
 */
import { afterEach, describe, it, expect } from "vitest";
import Fastify from "fastify";
import type { FastifyInstance } from "fastify";
import { createANIPService, defineCapability } from "@anip-dev/service";
import { InMemoryStorage } from "@anip-dev/server";
import { failureStatusCode, type CapabilityDeclaration } from "@anip-dev/core";
import { mountAnip } from "../src/routes.js";

const API_KEY = "test-key-123";

const RETRY_NOW = { action: "retry_now", recovery_class: "retry_now" };

interface Reply {
  status: number;
  contentType: string;
  text: string;
  /** The body parsed as JSON, or null when it is not JSON. */
  data: any;
}

function reply(status: number, contentType: string, text: string): Reply {
  let data: unknown = null;
  try {
    data = JSON.parse(text);
  } catch {
    // not JSON (an SSE stream, or a framework error page)
  }
  return { status, contentType, text, data };
}

function capability(
  name: string,
  inputs: Array<Record<string, unknown>>,
  extra: Record<string, unknown>,
  calls: string[],
) {
  return defineCapability({
    declaration: {
      name,
      description: name,
      contract_version: "1.0",
      inputs,
      output: { type: "object", fields: [] },
      side_effect: { type: "read", rollback_window: "not_applicable" },
      minimum_scope: [name],
      ...extra,
    } as unknown as CapabilityDeclaration,
    handler: () => {
      calls.push(name);
      return { ok: true };
    },
  });
}

const stops: Array<() => void> = [];

afterEach(() => {
  for (const stop of stops.splice(0)) stop();
});

async function makeApp() {
  const calls: string[] = [];
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [
      capability("greet", [
        { name: "name", type: "string", required: true },
        { name: "times", type: "integer", required: false },
      ], {}, calls),
      capability("analyze", [{ name: "target", type: "string", required: true }], {
        response_modes: ["unary", "streaming"],
      }, calls),
      capability("book", [
        { name: "flight", type: "string", required: true },
        { name: "quote", type: "object", required: false },
      ], {
        cost: { certainty: "estimated", financial: { currency: "USD", range_min: 1, range_max: 9 } },
        requires_binding: [{ type: "quote", field: "quote", source_capability: "greet", max_age: "PT15M" }],
      }, calls),
    ],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const app = Fastify();
  const { stop } = await mountAnip(app, service);
  stops.push(stop);
  return { app, calls };
}

async function post(app: FastifyInstance, path: string, bearer: string | null, body: unknown, raw = false): Promise<Reply> {
  const res = await app.inject({
    method: "POST",
    url: path,
    headers: {
      "Content-Type": "application/json",
      ...(bearer === null ? {} : { Authorization: `Bearer ${bearer}` }),
    },
    payload: raw ? (body as string) : JSON.stringify(body),
  });
  return reply(res.statusCode, String(res.headers["content-type"] ?? ""), res.payload);
}

async function issue(app: FastifyInstance, capabilityName: string, extra: Record<string, unknown> = {}) {
  const res = await post(app, "/anip/tokens", API_KEY, {
    subject: "test-agent", scope: [capabilityName], capability: capabilityName, ...extra,
  });
  expect(res.status).toBe(200);
  return res.data as { token: string; token_id: string };
}

function expectInvalidParameters(res: Reply, context = "") {
  expect(res.status, context).toBe(400);
  expect(res.data, `${context}: ${res.text.slice(0, 200)}`).not.toBeNull();
  expect(res.data.success, context).toBe(false);
  expect(res.data.failure.type, context).toBe("invalid_parameters");
  expect(res.data.failure.resolution, context).toMatchObject(RETRY_NOW);
  expect(res.data.failure.retry, context).toBe(false);
  expect(typeof res.data.failure.detail, context).toBe("string");
}

describe("Fastify: a request body that is not JSON", () => {
  const MALFORMED = '{"parameters": ';

  it("POST /anip/invoke is invalid_parameters, HTTP 400", async () => {
    const { app, calls } = await makeApp();
    const { token } = await issue(app, "greet");

    expectInvalidParameters(await post(app, "/anip/invoke/greet", token, MALFORMED, true));
    expect(calls).toEqual([]);
  });

  it("POST /anip/invoke checks the credential first", async () => {
    const { app } = await makeApp();

    const none = await post(app, "/anip/invoke/greet", null, MALFORMED, true);
    expect(none.status).toBe(401);
    expect(none.data.failure.type).toBe("authentication_required");

    const bad = await post(app, "/anip/invoke/greet", "not-a-token", MALFORMED, true);
    expect(bad.status).toBe(401);
    expect(bad.data.failure.type).toBe("invalid_token");
  });

  it("POST /anip/invoke with a JSON body that is not an object is invalid_parameters, HTTP 400", async () => {
    const { app, calls } = await makeApp();
    const { token } = await issue(app, "greet");

    for (const body of ["[1]", '"x"', "7", "null"]) {
      expectInvalidParameters(await post(app, "/anip/invoke/greet", token, body, true), body);
    }
    expect(calls).toEqual([]);
  });

  it("POST /anip/tokens is invalid_parameters, HTTP 400", async () => {
    const { app } = await makeApp();

    expectInvalidParameters(await post(app, "/anip/tokens", API_KEY, '{"scope": ', true));
    for (const body of ["[]", '"x"', "null"]) {
      expectInvalidParameters(await post(app, "/anip/tokens", API_KEY, body, true), body);
    }
  });

  it("POST /anip/tokens checks the credential first", async () => {
    const { app } = await makeApp();

    const none = await post(app, "/anip/tokens", null, '{"scope": ', true);
    expect(none.status).toBe(401);
    expect(none.data.failure.type).toBe("authentication_required");

    const unknown = await post(app, "/anip/tokens", "not-a-key", '{"scope": ', true);
    expect(unknown.status).toBe(401);
    expect(unknown.data.failure.type).toBe("authentication_required");
  });

  it("POST /anip/approval_grants is invalid_parameters, HTTP 400, after the credential check", async () => {
    const { app } = await makeApp();
    const { token } = await issue(app, "greet");
    const malformed = '{"approval_request_id": ';

    expectInvalidParameters(await post(app, "/anip/approval_grants", token, malformed, true));

    const none = await post(app, "/anip/approval_grants", null, malformed, true);
    expect(none.status).toBe(401);
    expect(none.data.failure.type).toBe("authentication_required");
  });
});

describe("Fastify: HTTP status per failure type", () => {
  function expectFailure(res: Reply, type: string, status: number) {
    expect(res.data.failure.type).toBe(type);
    expect(res.status).toBe(status);
    expect(failureStatusCode(type)).toBe(status);
  }

  it("binding_missing and binding_stale are 403", async () => {
    const { app } = await makeApp();
    const { token } = await issue(app, "book");

    const missing = await post(app, "/anip/invoke/book", token, { parameters: { flight: "AA100" } });
    expectFailure(missing, "binding_missing", 403);

    const stale = await post(app, "/anip/invoke/book", token, {
      parameters: { flight: "AA100", quote: { price: 5, issued_at: 1000000 } },
    });
    expectFailure(stale, "binding_stale", 403);
  });

  it("budget_not_enforceable, budget_currency_mismatch and budget_exceeded are 403", async () => {
    const { app } = await makeApp();
    const now = Math.floor(Date.now() / 1000);
    const usd = await issue(app, "book", { budget: { currency: "USD", max_amount: 3 } });

    const noPrice = await post(app, "/anip/invoke/book", usd.token, {
      parameters: { flight: "AA100", quote: { issued_at: now } },
    });
    expectFailure(noPrice, "budget_not_enforceable", 403);

    const exceeded = await post(app, "/anip/invoke/book", usd.token, {
      parameters: { flight: "AA100", quote: { price: 5, issued_at: now } },
    });
    expectFailure(exceeded, "budget_exceeded", 403);

    const eur = await issue(app, "book", { budget: { currency: "EUR", max_amount: 100 } });
    const mismatch = await post(app, "/anip/invoke/book", eur.token, {
      parameters: { flight: "AA100", quote: { price: 5, issued_at: now } },
    });
    expectFailure(mismatch, "budget_currency_mismatch", 403);
  });

  it("scope_escalation at the token endpoint is 403", async () => {
    const { app } = await makeApp();
    const parent = await issue(app, "greet");

    const res = await post(app, "/anip/tokens", parent.token, {
      subject: "agent:child", scope: ["greet", "book"], capability: "greet", parent_token: parent.token_id,
    });

    expectFailure(res, "scope_escalation", 403);
  });

  it("unknown_capability is 404, scope_insufficient and purpose_mismatch 403, streaming_not_supported 400", async () => {
    const { app } = await makeApp();
    const { token } = await issue(app, "greet");

    const unknown = await post(app, "/anip/invoke/nope", token, { parameters: {} });
    expectFailure(unknown, "unknown_capability", 404);

    const narrow = await post(app, "/anip/invoke/analyze", token, { parameters: { target: "x" } });
    expectFailure(narrow, "scope_insufficient", 403);

    const both = await issue(app, "greet", { scope: ["greet", "analyze"] });
    const other = await post(app, "/anip/invoke/analyze", both.token, { parameters: { target: "x" } });
    expectFailure(other, "purpose_mismatch", 403);

    const stream = await post(app, "/anip/invoke/greet", token, { parameters: { name: "x" }, stream: true });
    expectFailure(stream, "streaming_not_supported", 400);
  });
});
