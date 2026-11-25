/**
 * Parameter validation against declared inputs (SPEC.md §4.1 "Inputs",
 * §6.3 "Parameter Validation").
 */
import { describe, it, expect } from "vitest";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  ANIPError,
  checkDeclaredInputs,
  createANIPService,
  mustBeSupplied,
  defineCapability,
  invalidParametersFailure,
  type ANIPService,
  type CapabilityDef,
  type LoggingHooks,
  type MetricsHooks,
} from "../src/index.js";
import type { CapabilityDeclaration, DelegationToken } from "@anip-dev/core";
import { InMemoryStorage } from "@anip-dev/server";
import type { StorageBackend } from "@anip-dev/server";

const HUMAN = "human:test@example.com";

const RESOLUTION = {
  action: "retry_now",
  recovery_class: "retry_now",
  requires: "parameters that match the capability's declared inputs",
};

type DeclaredInput = { name: string; type: string; required?: boolean; default?: unknown };

function input(name: string, type: string, required?: boolean, extra: Record<string, unknown> = {}): DeclaredInput {
  return { name, type, ...(required === undefined ? {} : { required }), ...extra };
}

// ---------------------------------------------------------------------------
// The check itself
// ---------------------------------------------------------------------------

describe("checkDeclaredInputs: required inputs", () => {
  const inputs = [
    input("flight_number", "string", true),
    input("date", "date", true),
    input("passengers", "integer", false, { default: 1 }),
  ];

  it("accepts a call that supplies every required input", () => {
    expect(checkDeclaredInputs("book_flight", inputs, { flight_number: "AA100", date: "2026-03-10" })).toBeNull();
  });

  it("names every missing input, in declaration order", () => {
    expect(checkDeclaredInputs("book_flight", inputs, { passengers: 2 })).toBe(
      "book_flight is missing required input(s): flight_number, date",
    );
    expect(checkDeclaredInputs("book_flight", inputs, { date: "2026-03-10" })).toBe(
      "book_flight is missing required input(s): flight_number",
    );
  });

  it("treats JSON null as missing", () => {
    expect(checkDeclaredInputs("book_flight", inputs, { flight_number: null, date: "2026-03-10" })).toBe(
      "book_flight is missing required input(s): flight_number",
    );
  });

  it("treats an undefined member as missing (it is absent from the JSON)", () => {
    expect(checkDeclaredInputs("book_flight", inputs, { flight_number: undefined, date: "2026-03-10" })).toBe(
      "book_flight is missing required input(s): flight_number",
    );
  });

  it("treats absent and null parameters as {}", () => {
    const expected = "book_flight is missing required input(s): flight_number, date";
    expect(checkDeclaredInputs("book_flight", inputs, undefined)).toBe(expected);
    expect(checkDeclaredInputs("book_flight", inputs, null)).toBe(expected);
    expect(checkDeclaredInputs("book_flight", [], null)).toBeNull();
  });

  it("requires an input whose declaration does not state `required`", () => {
    expect(checkDeclaredInputs("c", [input("a", "string")], {})).toBe("c is missing required input(s): a");
    expect(checkDeclaredInputs("c", [input("a", "string")], { a: "x" })).toBeNull();
  });

  it("does not let a declared default satisfy `required`", () => {
    expect(checkDeclaredInputs("c", [input("a", "integer", true, { default: 3 })], {})).toBe(
      "c is missing required input(s): a",
    );
  });

  it("does not check an optional input that is absent or null", () => {
    const optional = [input("a", "integer", false)];
    expect(checkDeclaredInputs("c", optional, {})).toBeNull();
    expect(checkDeclaredInputs("c", optional, { a: null })).toBeNull();
  });

  it("reports missing inputs before wrong types", () => {
    expect(checkDeclaredInputs("book_flight", inputs, { flight_number: 7 })).toBe(
      "book_flight is missing required input(s): date",
    );
  });
});

describe("checkDeclaredInputs: primitive types", () => {
  const VALUES: Record<string, unknown> = {
    string: "x",
    number: 1.5,
    boolean: true,
    array: ["x"],
    object: { x: true },
  };
  const ACCEPTS: Record<string, string[]> = {
    string: ["string"],
    integer: [],
    number: ["number"],
    boolean: ["boolean"],
    array: ["array"],
    object: ["object"],
  };

  for (const declared of Object.keys(ACCEPTS)) {
    for (const [received, value] of Object.entries(VALUES)) {
      const ok = ACCEPTS[declared].includes(received);
      it(`${declared} ${ok ? "accepts" : "rejects"} a JSON ${received}`, () => {
        const detail = checkDeclaredInputs("cap", [input("v", declared, true)], { v: value });
        expect(detail).toBe(ok ? null : `cap has invalid input(s): 'v' must be ${declared}, got ${received}`);
      });
    }
  }

  it("integer accepts any number with an integral value", () => {
    const inputs = [input("n", "integer", true)];
    for (const text of ["5", "5.0", "1e2", "-3", "0", "-0.0", "9007199254740993", "1e300"]) {
      expect(checkDeclaredInputs("cap", inputs, JSON.parse(`{"n": ${text}}`)), text).toBeNull();
    }
    expect(checkDeclaredInputs("cap", inputs, { n: 10n ** 30n })).toBeNull();
  });

  it("integer rejects a fractional or non-finite number", () => {
    const inputs = [input("n", "integer", true)];
    for (const value of [1.5, -0.25, 1e-7, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(checkDeclaredInputs("cap", inputs, { n: value }), String(value)).toBe(
        "cap has invalid input(s): 'n' must be integer, got number",
      );
    }
  });

  it("a boolean is never a number", () => {
    for (const declared of ["integer", "number"]) {
      for (const value of [true, false]) {
        expect(checkDeclaredInputs("cap", [input("n", declared, true)], { n: value })).toBe(
          `cap has invalid input(s): 'n' must be ${declared}, got boolean`,
        );
      }
    }
  });

  it("names every wrong input, in declaration order", () => {
    const inputs = [
      input("flight_number", "string", true),
      input("passengers", "integer", false),
      input("quote_id", "object", false),
    ];
    expect(
      checkDeclaredInputs("book_flight", inputs, { quote_id: ["q"], passengers: "two", flight_number: "AA100" }),
    ).toBe(
      "book_flight has invalid input(s): 'passengers' must be integer, got string; 'quote_id' must be object, got array",
    );
  });

  it("does not type-check a declared type that is not a primitive name", () => {
    const inputs = [
      input("origin", "airport_code", true),
      input("date", "date", true),
      input("shouting", "String", true),
      input("count", "int", true),
    ];
    expect(checkDeclaredInputs("cap", inputs, { origin: true, date: 7, shouting: [], count: "x" })).toBeNull();
  });

  it("leaves undeclared parameters alone", () => {
    expect(checkDeclaredInputs("cap", [input("a", "string", true)], { a: "x", extra: { any: [1, null] } })).toBeNull();
  });

  it("does not enforce allowed_values", () => {
    const inputs = [input("cabin", "string", true, { allowed_values: ["economy"] })];
    expect(checkDeclaredInputs("cap", inputs, { cabin: "first" })).toBeNull();
  });

  it("refuses parameters that are not a JSON object", () => {
    for (const [value, received] of [["x", "string"], [3, "number"], [true, "boolean"], [[1], "array"]] as const) {
      expect(checkDeclaredInputs("cap", [], value)).toBe(`cap parameters must be an object, got ${received}`);
    }
  });
});

// SPEC.md §6.3 item 1, exception; §4.10 "on_missing and parameter validation".
describe("checkDeclaredInputs: inputs that declare resolution.on_missing", () => {
  const ON_MISSING = [
    "clarify", "use_default", "use_actor_scope", "app_select_or_clarify", "deny", "deny_or_clarify", "omit",
  ];
  const withOnMissing = (behavior: string) =>
    input("region", "string", true, { default: "eu", resolution: { mode: "clarify", on_missing: behavior } });

  for (const behavior of ON_MISSING) {
    it(`a required input with on_missing=${behavior} is not refused when absent or null`, () => {
      expect(checkDeclaredInputs("cap", [withOnMissing(behavior)], {})).toBeNull();
      expect(checkDeclaredInputs("cap", [withOnMissing(behavior)], { region: null })).toBeNull();
      expect(checkDeclaredInputs("cap", [withOnMissing(behavior)], null)).toBeNull();
    });
  }

  it("the same input without a resolution block is refused", () => {
    expect(checkDeclaredInputs("cap", [input("region", "string", true)], {})).toBe(
      "cap is missing required input(s): region",
    );
    expect(checkDeclaredInputs("cap", [input("region", "string", true, { resolution: null })], {})).toBe(
      "cap is missing required input(s): region",
    );
  });

  it("a resolution block that does not set on_missing does not exempt the input", () => {
    for (const resolution of [
      { mode: "clarify" },
      { mode: "clarify", on_missing: null },
      { mode: "clarify", on_missing: undefined },
      { mode: "clarify", on_ambiguous: "clarify", on_unresolved: "deny" },
    ]) {
      expect(checkDeclaredInputs("cap", [input("region", "string", true, { resolution })], {})).toBe(
        "cap is missing required input(s): region",
      );
    }
  });

  it("a supplied value for an on_missing input is still type-checked", () => {
    expect(checkDeclaredInputs("cap", [withOnMissing("clarify")], { region: 7 })).toBe(
      "cap has invalid input(s): 'region' must be string, got number",
    );
    expect(checkDeclaredInputs("cap", [withOnMissing("clarify")], { region: "us" })).toBeNull();
  });

  it("only the inputs without on_missing are named as missing", () => {
    const inputs = [input("origin", "string", true), withOnMissing("clarify"), input("date", "date", true)];
    expect(checkDeclaredInputs("cap", inputs, {})).toBe("cap is missing required input(s): origin, date");
  });
});

describe("mustBeSupplied", () => {
  it("is true for a required input that declares no on_missing", () => {
    expect(mustBeSupplied({ required: true })).toBe(true);
    expect(mustBeSupplied({})).toBe(true);
    expect(mustBeSupplied({ required: true, resolution: null })).toBe(true);
    expect(mustBeSupplied({ required: true, resolution: { mode: "clarify", on_missing: null } })).toBe(true);
  });

  it("is false for an optional input and for one that sets on_missing", () => {
    expect(mustBeSupplied({ required: false })).toBe(false);
    expect(mustBeSupplied({ required: true, resolution: { mode: "clarify", on_missing: "clarify" } })).toBe(false);
    expect(mustBeSupplied({ resolution: { mode: "closed_values", on_missing: "deny" } })).toBe(false);
  });
});

describe("invalidParametersFailure", () => {
  it("is the failure SPEC.md §6.3 prints", () => {
    expect(invalidParametersFailure("book_flight is missing required input(s): date")).toEqual({
      type: "invalid_parameters",
      detail: "book_flight is missing required input(s): date",
      resolution: RESOLUTION,
      retry: false,
    });
  });
});

// ---------------------------------------------------------------------------
// The invoke pipeline
// ---------------------------------------------------------------------------

interface Recorder {
  calls: Array<Record<string, unknown>>;
}

function declaration(name: string, scope: string[], inputs: DeclaredInput[], extra: Record<string, unknown> = {}) {
  return {
    name,
    description: name,
    contract_version: "1.0",
    inputs,
    output: { type: "object", fields: [] },
    side_effect: { type: "read", rollback_window: "not_applicable" },
    minimum_scope: scope,
    kind: "atomic",
    ...extra,
  } as unknown as CapabilityDeclaration;
}

function recordingCap(
  recorder: Recorder,
  name: string,
  scope: string[],
  inputs: DeclaredInput[],
  extra: Record<string, unknown> = {},
  opts: { exclusiveLock?: boolean; handler?: CapabilityDef["handler"] } = {},
): CapabilityDef {
  return defineCapability({
    declaration: declaration(name, scope, inputs, extra),
    exclusiveLock: opts.exclusiveLock,
    handler: async (ctx, params) => {
      recorder.calls.push({ capability: name, params: { ...params } });
      if (opts.handler) return opts.handler(ctx, params);
      return { ok: true };
    },
  });
}

const BOOK_INPUTS = [
  input("flight_number", "string", true),
  input("date", "date", true),
  input("passengers", "integer", false, { default: 1 }),
  input("quote_id", "object", false),
];

function makeService(caps: CapabilityDef[], opts: { storage?: StorageBackend; hooks?: { logging?: LoggingHooks; metrics?: MetricsHooks } } = {}) {
  const storage = opts.storage ?? new InMemoryStorage();
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: caps,
    storage,
    keyPath: join(mkdtempSync(join(tmpdir(), "anip-input-validation-")), "keys.json"),
    authenticate: (bearer: string) => (bearer === "test-key" ? HUMAN : null),
    hooks: opts.hooks,
  });
  return { service, storage };
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

async function auditEntry(service: ANIPService, token: DelegationToken, invocationId: string) {
  const audit = (await service.queryAudit(token, { invocation_id: invocationId })) as {
    entries: Array<Record<string, unknown>>;
  };
  expect(audit.entries).toHaveLength(1);
  return audit.entries[0];
}

describe("invoke: parameter validation", () => {
  it("refuses a missing required input with the invalid_parameters failure and does not run the handler", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([recordingCap(recorder, "book_flight", ["travel.book"], BOOK_INPUTS)]);
    const token = await tokenFor(service, "book_flight", ["travel.book"]);

    const result = await service.invoke("book_flight", token, { passengers: 2 }, {
      clientReferenceId: "ref-1",
      upstreamService: "planner",
      parentInvocationId: "inv-000000000001",
    });

    expect(result.success).toBe(false);
    expect(result.result).toBeUndefined();
    expect(result.failure).toEqual({
      type: "invalid_parameters",
      detail: "book_flight is missing required input(s): flight_number, date",
      resolution: RESOLUTION,
      retry: false,
    });
    expect(result.invocation_id).toMatch(/^inv-[0-9a-f]{12}$/);
    expect(result.client_reference_id).toBe("ref-1");
    expect(result.upstream_service).toBe("planner");
    expect(result.parent_invocation_id).toBe("inv-000000000001");
    expect(recorder.calls).toEqual([]);
  });

  it("refuses a value of the wrong JSON type", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([recordingCap(recorder, "book_flight", ["travel.book"], BOOK_INPUTS)]);
    const token = await tokenFor(service, "book_flight", ["travel.book"]);

    const result = await service.invoke("book_flight", token, {
      flight_number: "AA100", date: "2026-03-10", passengers: "two", quote_id: ["q"],
    });

    expect(result.failure).toEqual({
      type: "invalid_parameters",
      detail:
        "book_flight has invalid input(s): 'passengers' must be integer, got string; 'quote_id' must be object, got array",
      resolution: RESOLUTION,
      retry: false,
    });
    expect(recorder.calls).toEqual([]);
  });

  it("passes a valid call to the handler with its parameters untouched", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([recordingCap(recorder, "book_flight", ["travel.book"], BOOK_INPUTS)]);
    const token = await tokenFor(service, "book_flight", ["travel.book"]);
    const params = JSON.parse('{"flight_number":"AA100","date":"2026-03-10","passengers":5.0,"note":{"vip":true}}');

    const result = await service.invoke("book_flight", token, params);

    expect(result.success).toBe(true);
    // No default is applied by the check, and the undeclared parameter arrives.
    expect(recorder.calls).toEqual([{ capability: "book_flight", params }]);
  });

  it("treats null parameters as {}", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([
      recordingCap(recorder, "ping", ["ping"], [input("note", "string", false)]),
      recordingCap(recorder, "greet", ["greet"], [input("name", "string", true)]),
    ]);

    const ping = await service.invoke(
      "ping", await tokenFor(service, "ping", ["ping"]), null as unknown as Record<string, unknown>);
    expect(ping.success).toBe(true);
    expect(recorder.calls).toEqual([{ capability: "ping", params: {} }]);

    const greet = await service.invoke(
      "greet", await tokenFor(service, "greet", ["greet"]), undefined as unknown as Record<string, unknown>);
    expect((greet.failure as Record<string, unknown>).detail).toBe("greet is missing required input(s): name");
  });

  it("refuses parameters that are not an object", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([recordingCap(recorder, "ping", ["ping"], [])]);
    const token = await tokenFor(service, "ping", ["ping"]);

    const result = await service.invoke("ping", token, "nope" as unknown as Record<string, unknown>);

    expect(result.failure).toEqual({
      type: "invalid_parameters",
      detail: "ping parameters must be an object, got string",
      resolution: RESOLUTION,
      retry: false,
    });
    expect(recorder.calls).toEqual([]);
  });

  it("refuses parameters that are not an object before binding enforcement", async () => {
    // SPEC.md §6.3: the value does not match the request schema; it is
    // refused like a body that is not JSON, so a capability with a binding
    // requirement answers invalid_parameters, not binding_missing.
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([
      recordingCap(recorder, "book", ["book"], BOOK_INPUTS, {
        requires_binding: [{ type: "quote", field: "quote_id", source_capability: "search", max_age: null }],
      }),
    ]);
    const token = await tokenFor(service, "book", ["book"]);

    const result = await service.invoke("book", token, [1] as unknown as Record<string, unknown>);

    expect(result.failure).toEqual({
      type: "invalid_parameters",
      detail: "book parameters must be an object, got array",
      resolution: RESOLUTION,
      retry: false,
    });
    expect(recorder.calls).toEqual([]);
  });

  it("audits the refusal like a delegation failure and fires the invocation hooks", async () => {
    const recorder: Recorder = { calls: [] };
    const ended: Array<Record<string, unknown>> = [];
    const durations: Array<Record<string, unknown>> = [];
    const started: unknown[] = [];
    const { service } = makeService(
      [recordingCap(recorder, "book_flight", ["travel.book"], BOOK_INPUTS)],
      {
        hooks: {
          logging: {
            onInvocationStart: (e) => started.push(e),
            onInvocationEnd: (e) => ended.push(e as unknown as Record<string, unknown>),
          },
          metrics: { onInvocationDuration: (e) => durations.push(e as unknown as Record<string, unknown>) },
        },
      },
    );
    const token = await tokenFor(service, "book_flight", ["travel.book"], {
      purpose_parameters: { task_id: "trip-1" },
    });

    const result = await service.invoke("book_flight", token, {}, {
      clientReferenceId: "ref-2",
      parentInvocationId: "inv-000000000002",
      upstreamService: "planner",
    });

    const entry = await auditEntry(service, token, result.invocation_id as string);
    expect(entry.success).toBe(false);
    expect(entry.failure_type).toBe("invalid_parameters");
    expect(entry.capability).toBe("book_flight");
    expect(entry.invocation_id).toBe(result.invocation_id);
    expect(entry.client_reference_id).toBe("ref-2");
    expect(entry.task_id).toBe("trip-1");
    expect(entry.parent_invocation_id).toBe("inv-000000000002");
    expect(entry.upstream_service).toBe("planner");
    expect(result.task_id).toBe("trip-1");

    expect(started).toEqual([]);
    expect(ended).toHaveLength(1);
    expect(ended[0]).toMatchObject({
      capability: "book_flight",
      invocationId: result.invocation_id,
      success: false,
      failureType: "invalid_parameters",
    });
    expect(durations).toHaveLength(1);
    expect(durations[0]).toMatchObject({ capability: "book_flight", success: false });
  });

  it("applies to a streaming invocation", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([
      recordingCap(recorder, "analyze", ["analyze"], [input("data", "string", true)], {
        response_modes: ["unary", "streaming"],
      }),
    ]);
    const token = await tokenFor(service, "analyze", ["analyze"]);
    const events: unknown[] = [];

    const result = await service.invoke("analyze", token, { data: 7 }, {
      stream: true,
      progressSink: async (event) => { events.push(event); },
    });

    expect(result.failure).toEqual({
      type: "invalid_parameters",
      detail: "analyze has invalid input(s): 'data' must be string, got number",
      resolution: RESOLUTION,
      retry: false,
    });
    expect(recorder.calls).toEqual([]);
    expect(events).toEqual([]);
    const entry = await auditEntry(service, token, result.invocation_id as string);
    expect(entry.failure_type).toBe("invalid_parameters");
  });
});

describe("invoke: where parameter validation runs", () => {
  it("after delegation validation: a caller without the scope is told that, not which parameters are wrong", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([
      recordingCap(recorder, "book_flight", ["travel.book"], BOOK_INPUTS),
      recordingCap(recorder, "search_flights", ["travel.search"], [input("origin", "airport_code", true)]),
    ]);

    const noScope = await tokenFor(service, "book_flight", ["travel.search"]);
    const scope = await service.invoke("book_flight", noScope, {});
    expect((scope.failure as Record<string, unknown>).type).toBe("scope_insufficient");

    const otherPurpose = await tokenFor(service, "search_flights", ["travel.search", "travel.book"]);
    const purpose = await service.invoke("book_flight", otherPurpose, {});
    expect((purpose.failure as Record<string, unknown>).type).toBe("purpose_mismatch");
  });

  it("after binding enforcement: a missing binding field is binding_missing", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([
      recordingCap(recorder, "book_flight", ["travel.book"], BOOK_INPUTS, {
        requires_binding: [{ type: "quote", field: "quote_id", source_capability: "search_flights" }],
      }),
    ]);
    const token = await tokenFor(service, "book_flight", ["travel.book"]);

    const missingBinding = await service.invoke("book_flight", token, {});
    expect((missingBinding.failure as Record<string, unknown>).type).toBe("binding_missing");

    const withBinding = await service.invoke("book_flight", token, { quote_id: { id: "q1" } });
    expect((withBinding.failure as Record<string, unknown>).detail).toBe(
      "book_flight is missing required input(s): flight_number, date",
    );
    expect(recorder.calls).toEqual([]);
  });

  it("after budget enforcement", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([
      recordingCap(recorder, "book_flight", ["travel.book"], BOOK_INPUTS, {
        cost: { certainty: "fixed", financial: { currency: "USD", amount: 300 } },
      }),
    ]);
    const token = await tokenFor(service, "book_flight", ["travel.book"], {
      budget: { currency: "USD", max_amount: 100 },
    });

    const result = await service.invoke("book_flight", token, {});

    expect((result.failure as Record<string, unknown>).type).toBe("budget_exceeded");
  });

  it("after control-requirement enforcement", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([
      recordingCap(recorder, "book_flight", ["travel.book"], BOOK_INPUTS, {
        control_requirements: [{ type: "cost_ceiling", enforcement: "reject" }],
      }),
    ]);
    const token = await tokenFor(service, "book_flight", ["travel.book"]);

    const result = await service.invoke("book_flight", token, {});

    expect((result.failure as Record<string, unknown>).type).toBe("control_requirement_unsatisfied");
  });

  it("before the exclusive lock is taken", async () => {
    const recorder: Recorder = { calls: [] };
    const storage = new InMemoryStorage();
    const lockAttempts: string[] = [];
    const tryAcquire = storage.tryAcquireExclusive.bind(storage);
    storage.tryAcquireExclusive = async (key: string, holder: string, ttl: number) => {
      lockAttempts.push(key);
      return tryAcquire(key, holder, ttl);
    };
    const { service } = makeService(
      [recordingCap(recorder, "book_flight", ["travel.book"], BOOK_INPUTS, {}, { exclusiveLock: true })],
      { storage },
    );
    const token = await tokenFor(service, "book_flight", ["travel.book"]);
    // The engine resolves the stored token: make that one exclusive.
    const stored = (await storage.loadToken(token.token_id))!;
    await storage.storeToken({
      ...stored,
      constraints: { ...(stored.constraints as Record<string, unknown>), concurrent_branches: "exclusive" },
    });

    const refused = await service.invoke("book_flight", token, {});
    expect((refused.failure as Record<string, unknown>).type).toBe("invalid_parameters");
    expect(lockAttempts).toEqual([]);

    // Control: the same token does take the lock on a valid call.
    const ok = await service.invoke("book_flight", token, { flight_number: "AA100", date: "2026-03-10" });
    expect(ok.success).toBe(true);
    expect(lockAttempts).toHaveLength(1);
  });

  it("before the handler can ask for approval: no approval request is created", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([approvalCap(recorder)]);
    const token = await tokenFor(service, "transfer_funds", ["finance.write"]);

    const control = await service.invoke("transfer_funds", token, { amount: 50000, to_account: "acct-2" });
    expect((control.failure as Record<string, unknown>).type).toBe("approval_required");
    expect(await service.listApprovalRequests()).toHaveLength(1);

    const result = await service.invoke("transfer_funds", token, { amount: 50000, to_account: 12345 });

    const failure = result.failure as Record<string, unknown>;
    expect(failure.type).toBe("invalid_parameters");
    expect(failure.approval_required).toBeUndefined();
    expect(await service.listApprovalRequests()).toHaveLength(1);
    expect(recorder.calls).toHaveLength(1);
  });

  it("before the approval grant is validated or reserved: an invalid continuation does not spend the grant", async () => {
    const recorder: Recorder = { calls: [] };
    const { service, storage } = makeService([approvalCap(recorder)]);
    const token = await tokenFor(service, "transfer_funds", ["finance.write"]);
    const parameters = { amount: 50000, to_account: "acct-2" };
    const first = await service.invoke("transfer_funds", token, parameters);
    const requestId = ((first.failure as Record<string, unknown>).approval_required as Record<string, unknown>)
      .approval_request_id as string;
    const grant = await service.issueApprovalGrant(requestId, "one_time", { subject: "human:approver" });
    const grantId = grant.grant_id as string;

    const refused = await service.invoke("transfer_funds", token, { ...parameters, to_account: 12345 }, {
      approvalGrant: grantId,
    });

    // Without the check this would be grant_param_drift (Phase A).
    expect((refused.failure as Record<string, unknown>).type).toBe("invalid_parameters");
    expect((await storage.getGrant(grantId))!.use_count).toBe(0);

    // An unknown grant is not looked up either.
    const unknownGrant = await service.invoke("transfer_funds", token, { amount: 50000 }, {
      approvalGrant: "grant_000000000000",
    });
    expect((unknownGrant.failure as Record<string, unknown>).type).toBe("invalid_parameters");

    const continued = await service.invoke("transfer_funds", token, parameters, { approvalGrant: grantId });
    expect(continued.success).toBe(true);
    expect((await storage.getGrant(grantId))!.use_count).toBe(1);
  });

  it("before any child step of a composed capability, and again for each child step", async () => {
    const recorder: Recorder = { calls: [] };
    const composed = (name: string, mappedInput: string) =>
      recordingCap(recorder, name, ["inv.read"], [input("q", "string", true)], {
        kind: "composed",
        composition: {
          authority_boundary: "same_service",
          steps: [
            { id: "select", capability: "select_cap" },
            { id: "enrich", capability: "enrich_cap" },
          ],
          input_mapping: {
            select: { q: "$.input.q" },
            enrich: { [mappedInput]: "$.steps.select.output.items" },
          },
          output_mapping: { count: "$.steps.enrich.output.count" },
          failure_policy: {
            child_clarification: "propagate",
            child_denial: "propagate",
            child_approval_required: "propagate",
            child_error: "fail_parent",
          },
          audit_policy: { record_child_invocations: true, parent_task_lineage: true },
        },
      });
    const { service } = makeService([
      recordingCap(recorder, "select_cap", ["inv.read"], [input("q", "string", true)], {}, {
        handler: () => ({ items: ["a", "b"] }),
      }),
      recordingCap(recorder, "enrich_cap", ["inv.read"], [input("items", "array", true)], {}, {
        handler: () => ({ count: 2 }),
      }),
      composed("summary", "items"),
      composed("summary_wrong_mapping", "elements"),
    ]);

    // The parent's own parameters are checked before any child runs.
    const parentToken = await tokenFor(service, "summary", ["inv.read"]);
    const parent = await service.invoke("summary", parentToken, {});
    expect((parent.failure as Record<string, unknown>).detail).toBe("summary is missing required input(s): q");
    expect(recorder.calls).toEqual([]);

    const ok = await service.invoke("summary", parentToken, { q: "x" });
    expect(ok.success).toBe(true);
    expect(ok.result).toEqual({ count: 2 });

    // A child step is an invocation of its own: its inputs are checked too.
    recorder.calls.length = 0;
    const wrongToken = await tokenFor(service, "summary_wrong_mapping", ["inv.read"]);
    const wrong = await service.invoke("summary_wrong_mapping", wrongToken, { q: "x" });
    expect(wrong.success).toBe(false);
    const failure = wrong.failure as Record<string, unknown>;
    expect(failure.type).toBe("invalid_parameters");
    expect(failure.detail).toBe("enrich_cap is missing required input(s): items");
    expect(recorder.calls.map((c) => c.capability)).toEqual(["select_cap"]);
  });
});

function approvalCap(recorder: Recorder): CapabilityDef {
  return recordingCap(
    recorder,
    "transfer_funds",
    ["finance.write"],
    [input("amount", "number", true), input("to_account", "string", true)],
    {
      side_effect: { type: "irreversible", rollback_window: "none" },
      grant_policy: {
        allowed_grant_types: ["one_time", "session_bound"],
        default_grant_type: "one_time",
        expires_in_seconds: 900,
        max_uses: 1,
      },
    },
    {
      handler: (ctx, params) => {
        if ((params.amount as number) > 10000 && !ctx.approvalGrant) {
          throw new ANIPError("approval_required", "transfers above $10000 require approval", undefined, false, {
            preview: { amount: params.amount },
          });
        }
        return { transfer_id: "tx-1" };
      },
    },
  );
}

// ---------------------------------------------------------------------------
// Inputs that declare resolution.on_missing are left to the service
// ---------------------------------------------------------------------------

describe("invoke: a required input that declares resolution.on_missing", () => {
  function clarifyingService(resolution: Record<string, unknown> | null) {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([
      recordingCap(
        recorder,
        "list_orders",
        ["orders.read"],
        [
          input("status", "string", true),
          input("region", "string", true, resolution === null ? {} : { resolution }),
        ],
        {},
        {
          // The handler implements the on_missing path.
          handler: (_ctx, params) => {
            if (params.region === undefined || params.region === null) {
              throw new ANIPError("clarification_required", "which region?", {
                action: "retry_now",
                recovery_class: "retry_now",
                requires: "region",
              });
            }
            return { orders: [] };
          },
        },
      ),
    ]);
    return { service, recorder };
  }

  it("reaches the handler when the input is absent or null", async () => {
    const { service, recorder } = clarifyingService({ mode: "clarify", on_missing: "clarify" });
    const token = await tokenFor(service, "list_orders", ["orders.read"]);

    const absent = await service.invoke("list_orders", token, { status: "open" });
    expect((absent.failure as Record<string, unknown>).type).toBe("clarification_required");

    const asNull = await service.invoke("list_orders", token, { status: "open", region: null });
    expect((asNull.failure as Record<string, unknown>).type).toBe("clarification_required");

    expect(recorder.calls).toEqual([
      { capability: "list_orders", params: { status: "open" } },
      { capability: "list_orders", params: { status: "open", region: null } },
    ]);

    const supplied = await service.invoke("list_orders", token, { status: "open", region: "eu" });
    expect(supplied.success).toBe(true);
  });

  it("is refused without a resolution block", async () => {
    const { service, recorder } = clarifyingService(null);
    const token = await tokenFor(service, "list_orders", ["orders.read"]);

    const result = await service.invoke("list_orders", token, { status: "open" });

    expect(result.failure).toEqual({
      type: "invalid_parameters",
      detail: "list_orders is missing required input(s): region",
      resolution: RESOLUTION,
      retry: false,
    });
    expect(recorder.calls).toEqual([]);
  });

  it("is refused when the resolution block does not set on_missing", async () => {
    const { service, recorder } = clarifyingService({ mode: "clarify", on_ambiguous: "clarify" });
    const token = await tokenFor(service, "list_orders", ["orders.read"]);

    const result = await service.invoke("list_orders", token, { status: "open" });

    expect((result.failure as Record<string, unknown>).detail).toBe(
      "list_orders is missing required input(s): region",
    );
    expect(recorder.calls).toEqual([]);
  });

  it("still refuses a supplied value of the wrong type, and a missing input without on_missing", async () => {
    const { service, recorder } = clarifyingService({ mode: "clarify", on_missing: "clarify" });
    const token = await tokenFor(service, "list_orders", ["orders.read"]);

    const wrong = await service.invoke("list_orders", token, { status: "open", region: 7 });
    expect((wrong.failure as Record<string, unknown>).detail).toBe(
      "list_orders has invalid input(s): 'region' must be string, got number",
    );

    const missing = await service.invoke("list_orders", token, {});
    expect((missing.failure as Record<string, unknown>).detail).toBe(
      "list_orders is missing required input(s): status",
    );
    expect(recorder.calls).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// A handler's own invalid_parameters
// ---------------------------------------------------------------------------

describe("invalid_parameters raised by a handler", () => {
  it("gets the retry_now resolution when the handler gives none", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([
      recordingCap(recorder, "search", ["search"], [input("date", "date", true)], {}, {
        handler: () => {
          throw new ANIPError("invalid_parameters", "date must be YYYY-MM-DD");
        },
      }),
    ]);
    const token = await tokenFor(service, "search", ["search"]);

    const result = await service.invoke("search", token, { date: "tomorrow" });

    const failure = result.failure as Record<string, unknown>;
    expect(failure.type).toBe("invalid_parameters");
    expect(failure.detail).toBe("date must be YYYY-MM-DD");
    expect(failure.resolution).toMatchObject({ action: "retry_now", recovery_class: "retry_now" });
    // The same request cannot succeed: retry is stated, and false.
    expect(failure.retry).toBe(false);
  });

  it("keeps the resolution and retry the handler gives", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([
      recordingCap(recorder, "search", ["search"], [input("date", "date", true)], {}, {
        handler: () => {
          throw new ANIPError(
            "invalid_parameters",
            "the fare table is being reloaded",
            { action: "wait_and_retry", recovery_class: "wait_then_retry" },
            true,
          );
        },
      }),
    ]);
    const token = await tokenFor(service, "search", ["search"]);

    const result = await service.invoke("search", token, { date: "2026-03-10" });

    const failure = result.failure as Record<string, unknown>;
    expect(failure.resolution).toEqual({ action: "wait_and_retry", recovery_class: "wait_then_retry" });
    expect(failure.retry).not.toBe(false);
  });
});

// ---------------------------------------------------------------------------
// `required` defaults to true (SPEC.md §4.1)
// ---------------------------------------------------------------------------

describe("`required` defaults to true", () => {
  it("an input declared without `required` is required at invocation", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([recordingCap(recorder, "greet", ["greet"], [input("name", "string")])]);
    const token = await tokenFor(service, "greet", ["greet"]);

    const result = await service.invoke("greet", token, {});

    expect((result.failure as Record<string, unknown>).detail).toBe("greet is missing required input(s): name");
    expect(recorder.calls).toEqual([]);
  });

  it("the manifest and the declaration state `required` explicitly", async () => {
    const recorder: Recorder = { calls: [] };
    const { service } = makeService([
      recordingCap(recorder, "greet", ["greet"], [
        input("name", "string"),
        input("title", "string", false),
        input("greeting", "string", true),
      ]),
    ]);

    const fromManifest = service.getManifest().capabilities.greet.inputs;
    expect(fromManifest.map((i) => [i.name, i.required])).toEqual([
      ["name", true], ["title", false], ["greeting", true],
    ]);
    const [bytes] = await service.getSignedManifest();
    const signed = JSON.parse(new TextDecoder().decode(bytes));
    expect(signed.capabilities.greet.inputs.map((i: Record<string, unknown>) => i.required)).toEqual([
      true, false, true,
    ]);
    const declared = service.getCapabilityDeclaration("greet")!.inputs as Array<Record<string, unknown>>;
    expect(declared.map((i) => i.required)).toEqual([true, false, true]);
  });
});
