/**
 * A streaming invocation runs the checks a unary invocation runs before the
 * handler (SPEC.md §6.3, §6.6), on the Express binding.
 *
 * Each request is sent twice to a streaming-capable capability: unary, and
 * with `stream: true`. The unary answer is a JSON failure with the status of
 * its type; the streaming answer is this runtime's existing delivery of a
 * refusal made before the handler, an SSE `failed` event on a 200 stream,
 * carrying the same failure object.
 */
import { afterEach, describe, it, expect } from "vitest";
import express from "express";
import type { Express } from "express";
import request from "supertest";
import { ANIPError, createANIPService, defineCapability } from "@anip-dev/service";
import { InMemoryStorage } from "@anip-dev/server";
import { failureStatusCode, type CapabilityDeclaration } from "@anip-dev/core";
import { mountAnip } from "../src/routes.js";

const API_KEY = "test-key-123";

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
    // not JSON (an SSE stream)
  }
  return { status, contentType, text, data };
}

function streamingCap(calls: string[], name: string, scope: string[], extra: Record<string, unknown> = {}) {
  return defineCapability({
    declaration: {
      name,
      description: name,
      contract_version: "1.0",
      inputs: [
        { name: "flight", type: "string", required: true, description: "Flight" },
        { name: "passengers", type: "integer", required: false, description: "Passengers" },
        { name: "quote", type: "object", required: false, description: "Quote" },
      ],
      output: { type: "object", fields: ["booking_id"] },
      side_effect: { type: "irreversible", rollback_window: "none" },
      minimum_scope: scope,
      response_modes: ["unary", "streaming"],
      ...extra,
    } as unknown as CapabilityDeclaration,
    handler: async (ctx, params) => {
      calls.push(name);
      await ctx.emitProgress({ step: "booking" });
      if ((params.passengers as number) >= 5 && !ctx.approvalGrant) {
        throw new ANIPError("approval_required", "group bookings need approval", undefined, false, {
          preview: { passengers: params.passengers },
        });
      }
      return { booking_id: "BK-1" };
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
      streamingCap(calls, "stream_book", ["travel.book"], {
        cost: { certainty: "estimated", financial: { currency: "USD", range_min: 100, range_max: 900 } },
        requires_binding: [{ type: "quote", field: "quote", source_capability: "search", max_age: "PT15M" }],
        grant_policy: {
          allowed_grant_types: ["one_time", "session_bound"],
          default_grant_type: "one_time",
          expires_in_seconds: 900,
          max_uses: 1,
        },
      }),
      streamingCap(calls, "stream_ceiling", ["travel.book"], {
        control_requirements: [{ type: "cost_ceiling", enforcement: "reject" }],
      }),
      streamingCap(calls, "stream_other", ["travel.search"]),
    ],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const app = express();
  const { stop } = await mountAnip(app, service);
  stops.push(stop);
  return { app, calls };
}

async function post(app: Express, path: string, bearer: string | null, body: unknown, raw = false): Promise<Reply> {
  let req = request(app).post(path).set("Content-Type", "application/json");
  if (bearer !== null) req = req.set("Authorization", `Bearer ${bearer}`);
  const res = await req.send(raw ? (body as string) : JSON.stringify(body));
  return reply(res.status, String(res.headers["content-type"] ?? ""), res.text);
}

async function issue(
  app: Express,
  capabilityName: string,
  scope: string[],
  extra: Record<string, unknown> = {},
): Promise<string> {
  const res = await post(app, "/anip/tokens", API_KEY, {
    subject: "test-agent", scope, capability: capabilityName, ...extra,
  });
  expect(res.status).toBe(200);
  return res.data.token as string;
}

/** The terminal event of an SSE stream: [event name, data]. */
function terminalEvent(text: string): [string, any] {
  const events = [...text.matchAll(/event: (\w+)\ndata: (.*)\n/g)].map((m) => [m[1], JSON.parse(m[2])] as [string, any]);
  expect(events.length).toBeGreaterThan(0);
  return events[events.length - 1];
}

const now = () => Math.floor(Date.now() / 1000);
const freshQuote = (extra: Record<string, unknown> = { price: 420 }) => ({ id: "q1", issued_at: now(), ...extra });

interface Case {
  row: number | string;
  name: string;
  expected: string;
  capability: string;
  token: (app: Express) => Promise<string>;
  /** The invocation body, without `stream`. */
  body: Record<string, unknown>;
}

const bookToken = (extra: Record<string, unknown> = {}) => (app: Express) =>
  issue(app, "stream_book", ["travel.book"], extra);

const CASES: Case[] = [
  {
    row: 1,
    name: "budget exceeded (token budget below the cost)",
    expected: "budget_exceeded",
    capability: "stream_book",
    token: bookToken({ budget: { currency: "USD", max_amount: 100 } }),
    body: { parameters: { flight: "AA100", quote: freshQuote() } },
  },
  {
    row: "1b",
    name: "budget exceeded (budget in the request below the cost)",
    expected: "budget_exceeded",
    capability: "stream_book",
    token: bookToken(),
    body: { parameters: { flight: "AA100", quote: freshQuote() }, budget: { currency: "USD", max_amount: 100 } },
  },
  {
    row: 2,
    name: "budget not enforceable (estimated cost, binding without a price)",
    expected: "budget_not_enforceable",
    capability: "stream_book",
    token: bookToken({ budget: { currency: "USD", max_amount: 1000 } }),
    body: { parameters: { flight: "AA100", quote: freshQuote({}) } },
  },
  {
    row: 3,
    name: "binding missing",
    expected: "binding_missing",
    capability: "stream_book",
    token: bookToken(),
    body: { parameters: { flight: "AA100" } },
  },
  {
    row: 4,
    name: "binding stale",
    expected: "binding_stale",
    capability: "stream_book",
    token: bookToken(),
    body: { parameters: { flight: "AA100", quote: { id: "q1", price: 420, issued_at: now() - 3600 } } },
  },
  {
    row: 5,
    name: "unsatisfied control requirement (cost_ceiling without a budget)",
    expected: "control_requirement_unsatisfied",
    capability: "stream_ceiling",
    token: (app) => issue(app, "stream_ceiling", ["travel.book"]),
    body: { parameters: { flight: "AA100" } },
  },
  {
    row: 6,
    name: "purpose mismatch (token bound to another capability)",
    expected: "purpose_mismatch",
    capability: "stream_book",
    token: (app) => issue(app, "stream_other", ["travel.search", "travel.book"]),
    body: { parameters: { flight: "AA100", quote: freshQuote() } },
  },
  {
    row: 7,
    name: "insufficient scope",
    expected: "scope_insufficient",
    capability: "stream_book",
    token: (app) => issue(app, "stream_book", ["travel.search"]),
    body: { parameters: { flight: "AA100", quote: freshQuote() } },
  },
  {
    row: 8,
    name: "blank approval grant",
    expected: "grant_not_found",
    capability: "stream_book",
    token: bookToken(),
    body: { parameters: { flight: "AA100", passengers: 5, quote: freshQuote() }, approval_grant: "" },
  },
  {
    row: 9,
    name: "unknown approval grant",
    expected: "grant_not_found",
    capability: "stream_book",
    token: bookToken(),
    body: {
      parameters: { flight: "AA100", passengers: 5, quote: freshQuote() },
      approval_grant: "grant_000000000000",
    },
  },
  {
    row: 10,
    name: "parameter validation (missing required input)",
    expected: "invalid_parameters",
    capability: "stream_book",
    token: bookToken(),
    body: { parameters: { quote: freshQuote() } },
  },
  {
    row: "10b",
    name: "parameters that are not an object",
    expected: "invalid_parameters",
    capability: "stream_book",
    token: bookToken(),
    body: { parameters: ["AA100"] },
  },
];

describe("Express streaming: the checks before the handler", () => {
  it("control: a valid streaming invocation runs the handler", async () => {
    const { app, calls } = await makeApp();
    const token = await bookToken()(app);

    const res = await post(app, "/anip/invoke/stream_book", token, {
      parameters: { flight: "AA100", quote: freshQuote() }, stream: true,
    });

    expect(res.status).toBe(200);
    expect(res.contentType).toContain("text/event-stream");
    expect(res.text).toContain("event: progress");
    expect(terminalEvent(res.text)[0]).toBe("completed");
    expect(calls).toEqual(["stream_book"]);
  });

  for (const c of CASES) {
    it(`row ${c.row}: ${c.name} is ${c.expected}, as on the unary path`, async () => {
      const { app, calls } = await makeApp();
      const token = await c.token(app);
      const path = `/anip/invoke/${c.capability}`;

      // Unary: the reference answer, a JSON failure with the status of its type.
      const unary = await post(app, path, token, c.body);
      expect(unary.data.success).toBe(false);
      expect(unary.data.failure.type).toBe(c.expected);
      expect(unary.status).toBe(failureStatusCode(c.expected));

      // Streaming: the same failure, in the SSE `failed` event of a 200 stream.
      const streaming = await post(app, path, token, { ...c.body, stream: true });
      expect(streaming.status).toBe(200);
      expect(streaming.contentType).toContain("text/event-stream");
      expect(streaming.text).not.toContain("event: progress");
      const [event, data] = terminalEvent(streaming.text);
      expect(event).toBe("failed");
      expect(data.success).toBe(false);
      expect(data.failure).toEqual(unary.data.failure);
      expect(data.invocation_id).toMatch(/^inv-[0-9a-f]{12}$/);

      expect(calls).toEqual([]);
    });
  }

  it("a refused streaming continuation does not reserve its grant", async () => {
    const { app, calls } = await makeApp();
    const token = await bookToken()(app);
    const approver = await issue(app, "stream_book", ["approver:stream_book"]);
    const parameters = { flight: "AA100", passengers: 5, quote: freshQuote() };
    const first = await post(app, "/anip/invoke/stream_book", token, { parameters });
    expect(first.data.failure.type).toBe("approval_required");
    const granted = await post(app, "/anip/approval_grants", approver, {
      approval_request_id: first.data.failure.approval_required.approval_request_id,
      grant_type: "one_time",
    });
    expect(granted.status).toBe(200);
    const grantId = granted.data.grant_id as string;
    calls.length = 0;

    const refused = await post(app, "/anip/invoke/stream_book", token, {
      parameters: { ...parameters, flight: 7 }, approval_grant: grantId, stream: true,
    });
    expect(terminalEvent(refused.text)[1].failure.type).toBe("invalid_parameters");
    expect(calls).toEqual([]);

    // The one_time grant is still good for the streaming continuation.
    const continued = await post(app, "/anip/invoke/stream_book", token, {
      parameters, approval_grant: grantId, stream: true,
    });
    const [event, data] = terminalEvent(continued.text);
    expect(event).toBe("completed");
    expect(data.success).toBe(true);
    expect(calls).toEqual(["stream_book"]);

    // And it is spent now.
    const again = await post(app, "/anip/invoke/stream_book", token, {
      parameters, approval_grant: grantId, stream: true,
    });
    expect(terminalEvent(again.text)[1].failure.type).toBe("grant_consumed");
  });
});
