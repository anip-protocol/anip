/**
 * A streaming invocation runs the checks a unary invocation runs before the
 * handler, in the same order (SPEC.md §6.3, §6.6).
 *
 * In this runtime `stream: true` is an option of the one invoke pipeline: the
 * streaming path is the unary path with a progress sink. Each test sends the
 * same request twice, unary and streaming, to a streaming-capable capability
 * and compares the answers.
 */
import { describe, it, expect } from "vitest";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  ANIPError,
  createANIPService,
  defineCapability,
  type ANIPService,
  type CapabilityDef,
} from "../src/index.js";
import type { CapabilityDeclaration, DelegationToken } from "@anip-dev/core";
import { InMemoryStorage } from "@anip-dev/server";
import type { StorageBackend } from "@anip-dev/server";

const HUMAN = "human:test@example.com";

interface World {
  service: ANIPService;
  storage: StorageBackend;
  /** Names of the capabilities whose handler ran. */
  handled: string[];
}

function streamingCap(
  handled: string[],
  name: string,
  scope: string[],
  extra: Record<string, unknown> = {},
): CapabilityDef {
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
      kind: "atomic",
      ...extra,
    } as unknown as CapabilityDeclaration,
    handler: async (ctx, params) => {
      handled.push(name);
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

function makeWorld(): World {
  const handled: string[] = [];
  const storage = new InMemoryStorage();
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [
      streamingCap(handled, "stream_book", ["travel.book"], {
        cost: { certainty: "estimated", financial: { currency: "USD", range_min: 100, range_max: 900 } },
        requires_binding: [{ type: "quote", field: "quote", source_capability: "search", max_age: "PT15M" }],
        grant_policy: {
          allowed_grant_types: ["one_time", "session_bound"],
          default_grant_type: "one_time",
          expires_in_seconds: 900,
          max_uses: 1,
        },
      }),
      streamingCap(handled, "stream_ceiling", ["travel.book"], {
        control_requirements: [{ type: "cost_ceiling", enforcement: "reject" }],
      }),
      streamingCap(handled, "stream_other", ["travel.search"]),
    ],
    storage,
    keyPath: join(mkdtempSync(join(tmpdir(), "anip-streaming-prehandler-")), "keys.json"),
    authenticate: (bearer: string) => (bearer === "test-key" ? HUMAN : null),
  });
  return { service, storage, handled };
}

async function tokenFor(
  service: ANIPService,
  capability: string,
  scope: string[],
  extra: Record<string, unknown> = {},
): Promise<DelegationToken> {
  const issued = await service.issueToken(HUMAN, { subject: HUMAN, scope, capability, ...extra });
  return service.resolveBearerToken(issued.token as string);
}

const now = () => Math.floor(Date.now() / 1000);
const freshQuote = (extra: Record<string, unknown> = { price: 420 }) => ({ id: "q1", issued_at: now(), ...extra });

interface Request {
  capability: string;
  token: (service: ANIPService) => Promise<DelegationToken>;
  parameters: Record<string, unknown>;
  approvalGrant?: string;
}

interface Answer {
  result: Record<string, unknown>;
  failure: Record<string, unknown> | null;
  events: unknown[];
  handled: string[];
  audit: Array<[unknown, unknown]>;
}

/** Send the request to a fresh service, unary or streaming. */
async function send(request: Request, stream: boolean): Promise<Answer> {
  const world = makeWorld();
  const token = await request.token(world.service);
  const events: unknown[] = [];
  const result = await world.service.invoke(request.capability, token, request.parameters, {
    ...(request.approvalGrant === undefined ? {} : { approvalGrant: request.approvalGrant }),
    ...(stream ? { stream: true, progressSink: async (event: unknown) => { events.push(event); } } : {}),
  });
  const audit = (await world.service.queryAudit(token, { invocation_id: result.invocation_id })) as {
    entries: Array<Record<string, unknown>>;
  };
  return {
    result,
    failure: (result.failure as Record<string, unknown> | undefined) ?? null,
    events,
    handled: world.handled,
    audit: audit.entries.map((e) => [e.success, e.failure_type]),
  };
}

const bookToken = (extra: Record<string, unknown> = {}) => (service: ANIPService) =>
  tokenFor(service, "stream_book", ["travel.book"], extra);

const CASES: Array<{ row: number; name: string; expected: string; request: Request }> = [
  {
    row: 1,
    name: "budget exceeded (token budget below the cost)",
    expected: "budget_exceeded",
    request: {
      capability: "stream_book",
      token: bookToken({ budget: { currency: "USD", max_amount: 100 } }),
      parameters: { flight: "AA100", quote: freshQuote() },
    },
  },
  {
    row: 2,
    name: "budget not enforceable (estimated cost, binding without a price)",
    expected: "budget_not_enforceable",
    request: {
      capability: "stream_book",
      token: bookToken({ budget: { currency: "USD", max_amount: 1000 } }),
      parameters: { flight: "AA100", quote: freshQuote({}) },
    },
  },
  {
    row: 3,
    name: "binding missing",
    expected: "binding_missing",
    request: { capability: "stream_book", token: bookToken(), parameters: { flight: "AA100" } },
  },
  {
    row: 4,
    name: "binding stale",
    expected: "binding_stale",
    request: {
      capability: "stream_book",
      token: bookToken(),
      parameters: { flight: "AA100", quote: { id: "q1", price: 420, issued_at: now() - 3600 } },
    },
  },
  {
    row: 5,
    name: "unsatisfied control requirement (cost_ceiling without a budget)",
    expected: "control_requirement_unsatisfied",
    request: {
      capability: "stream_ceiling",
      token: (service) => tokenFor(service, "stream_ceiling", ["travel.book"]),
      parameters: { flight: "AA100" },
    },
  },
  {
    row: 6,
    name: "purpose mismatch (token bound to another capability)",
    expected: "purpose_mismatch",
    request: {
      capability: "stream_book",
      token: (service) => tokenFor(service, "stream_other", ["travel.search", "travel.book"]),
      parameters: { flight: "AA100", quote: freshQuote() },
    },
  },
  {
    row: 7,
    name: "insufficient scope",
    expected: "scope_insufficient",
    request: {
      capability: "stream_book",
      token: (service) => tokenFor(service, "stream_book", ["travel.search"]),
      parameters: { flight: "AA100", quote: freshQuote() },
    },
  },
  {
    row: 8,
    name: "blank approval grant",
    expected: "grant_not_found",
    request: {
      capability: "stream_book",
      token: bookToken(),
      parameters: { flight: "AA100", passengers: 5, quote: freshQuote() },
      approvalGrant: "",
    },
  },
  {
    row: 9,
    name: "unknown approval grant",
    expected: "grant_not_found",
    request: {
      capability: "stream_book",
      token: bookToken(),
      parameters: { flight: "AA100", passengers: 5, quote: freshQuote() },
      approvalGrant: "grant_000000000000",
    },
  },
  {
    row: 10,
    name: "parameter validation (missing required input)",
    expected: "invalid_parameters",
    request: { capability: "stream_book", token: bookToken(), parameters: { quote: freshQuote() } },
  },
];

describe("streaming invocation: the checks before the handler", () => {
  it("control: a valid streaming invocation runs the handler and emits progress", async () => {
    const answer = await send(
      { capability: "stream_book", token: bookToken(), parameters: { flight: "AA100", quote: freshQuote() } },
      true,
    );
    expect(answer.result.success).toBe(true);
    expect(answer.handled).toEqual(["stream_book"]);
    expect(answer.events).toHaveLength(1);
  });

  for (const { row, name, expected, request } of CASES) {
    it(`row ${row}: ${name} is ${expected}, as on the unary path`, async () => {
      const unary = await send(request, false);
      const streaming = await send(request, true);

      // The unary answer is the reference.
      expect(unary.result.success).toBe(false);
      expect(unary.failure?.type).toBe(expected);
      expect(unary.handled).toEqual([]);

      // The streaming answer is the same failure; the handler did not run.
      expect(streaming.result.success).toBe(false);
      expect(streaming.failure?.type).toBe(expected);
      expect(streaming.failure).toEqual(unary.failure);
      expect(streaming.result.result).toBeUndefined();
      expect(streaming.handled).toEqual([]);
      expect(streaming.events).toEqual([]);

      // The refusal is audited where the unary refusal is audited.
      expect(streaming.audit).toEqual(unary.audit);
    });
  }

  it("a refused streaming continuation does not reserve its grant", async () => {
    const world = makeWorld();
    const token = await tokenFor(world.service, "stream_book", ["travel.book"]);
    const parameters = { flight: "AA100", passengers: 5, quote: freshQuote() };
    const first = await world.service.invoke("stream_book", token, parameters);
    const requestId = ((first.failure as Record<string, unknown>).approval_required as Record<string, unknown>)
      .approval_request_id as string;
    const grant = await world.service.issueApprovalGrant(requestId, "one_time", { subject: "human:approver" });
    const grantId = grant.grant_id as string;
    world.handled.length = 0;
    const events: unknown[] = [];
    const streamOpts = { stream: true, approvalGrant: grantId, progressSink: async (e: unknown) => { events.push(e); } };

    // Invalid parameters: refused before the grant is looked at.
    const invalid = await world.service.invoke("stream_book", token, { ...parameters, flight: 7 }, streamOpts);
    expect((invalid.failure as Record<string, unknown>).type).toBe("invalid_parameters");
    // A missing binding: refused before the grant is looked at.
    const unbound = await world.service.invoke("stream_book", token, { flight: "AA100", passengers: 5 }, streamOpts);
    expect((unbound.failure as Record<string, unknown>).type).toBe("binding_missing");

    expect((await world.storage.getGrant(grantId))!.use_count).toBe(0);
    expect(world.handled).toEqual([]);
    expect(events).toEqual([]);

    // The grant is still good for the streaming continuation it was issued for.
    const continued = await world.service.invoke("stream_book", token, parameters, streamOpts);
    expect(continued.success).toBe(true);
    expect((await world.storage.getGrant(grantId))!.use_count).toBe(1);
    expect(world.handled).toEqual(["stream_book"]);
  });
});
