/**
 * Parameter validation against declared inputs on the Fastify binding
 * (SPEC.md §6.3 "Parameter Validation").
 */
import { afterEach, describe, it, expect } from "vitest";
import Fastify from "fastify";
import type { FastifyInstance } from "fastify";
import { createANIPService, defineCapability } from "@anip-dev/service";
import { InMemoryStorage } from "@anip-dev/server";
import type { CapabilityDeclaration } from "@anip-dev/core";
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

describe("Fastify: parameter validation", () => {
  it("a missing required input is invalid_parameters, HTTP 400, and the handler does not run", async () => {
    const { app, calls } = await makeApp();
    const { token } = await issue(app, "greet");

    const res = await post(app, "/anip/invoke/greet", token, { parameters: { times: 2 } });

    expect(res.status).toBe(400);
    expect(res.data.success).toBe(false);
    expect(res.data.invocation_id).toMatch(/^inv-[0-9a-f]{12}$/);
    expect(res.data.failure).toEqual({
      type: "invalid_parameters",
      detail: "greet is missing required input(s): name",
      resolution: { ...RETRY_NOW, requires: "parameters that match the capability's declared inputs" },
      retry: false,
    });
    expect(calls).toEqual([]);
  });

  it("a value of the wrong JSON type is invalid_parameters, HTTP 400", async () => {
    const { app, calls } = await makeApp();
    const { token } = await issue(app, "greet");

    const res = await post(app, "/anip/invoke/greet", token, { parameters: { name: "World", times: "2" } });

    expect(res.status).toBe(400);
    expect(res.data.failure.type).toBe("invalid_parameters");
    expect(res.data.failure.detail).toBe("greet has invalid input(s): 'times' must be integer, got string");
    expect(calls).toEqual([]);
  });

  it("an integral float is an integer", async () => {
    const { app, calls } = await makeApp();
    const { token } = await issue(app, "greet");

    const res = await post(app, "/anip/invoke/greet", token, '{"parameters": {"name": "World", "times": 2.0}}', true);

    expect(res.status).toBe(200);
    expect(res.data.success).toBe(true);
    expect(calls).toEqual(["greet"]);
  });

  it("parameters that are not an object are invalid_parameters, HTTP 400", async () => {
    const { app, calls } = await makeApp();
    const { token } = await issue(app, "greet");

    const res = await post(app, "/anip/invoke/greet", token, { parameters: "World" });

    expect(res.status).toBe(400);
    expect(res.data.failure.type).toBe("invalid_parameters");
    expect(res.data.failure.resolution).toMatchObject(RETRY_NOW);
    expect(calls).toEqual([]);
  });

  it("streaming: the refusal is the same failure, delivered as the SSE failed event", async () => {
    const { app, calls } = await makeApp();
    const { token } = await issue(app, "analyze");

    const res = await post(app, "/anip/invoke/analyze", token, { parameters: {}, stream: true });

    expect(res.status).toBe(200);
    expect(res.contentType).toContain("text/event-stream");
    expect(res.text).not.toContain("event: completed");
    const match = /event: failed\ndata: (.*)\n/.exec(res.text);
    expect(match).not.toBeNull();
    const event = JSON.parse(match![1]);
    expect(event.success).toBe(false);
    expect(event.failure).toEqual({
      type: "invalid_parameters",
      detail: "analyze is missing required input(s): target",
      resolution: { ...RETRY_NOW, requires: "parameters that match the capability's declared inputs" },
      retry: false,
    });
    expect(calls).toEqual([]);
  });
});
