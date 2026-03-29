import { describe, it, expect } from "vitest";
import {
  createANIPService,
  defineCapability,
  ANIPError,
} from "../src/index.js";
import type { CapabilityDef, InvocationContext, LoggingHooks } from "../src/index.js";
import type { CapabilityDeclaration, DelegationToken } from "@anip-dev/core";
import { InMemoryStorage, DelegationEngine } from "@anip-dev/server";
import type { StorageBackend } from "@anip-dev/server";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function testCap(
  name = "greet",
  scope: string[] = ["greet"],
): CapabilityDef {
  return defineCapability({
    declaration: {
      name,
      description: "Say hello",
      contract_version: "1.0",
      inputs: [
        { name: "name", type: "string", required: true, description: "Who to greet" },
      ],
      output: { type: "object", fields: ["message"] },
      side_effect: { type: "read", rollback_window: null },
      minimum_scope: scope,
    } as CapabilityDeclaration,
    handler: (_ctx, params) => ({
      message: `Hello, ${params.name}!`,
    }),
  });
}

function errorCap(): CapabilityDef {
  return defineCapability({
    declaration: {
      name: "fail",
      description: "Always fails",
      contract_version: "1.0",
      inputs: [],
      output: { type: "object", fields: [] },
      side_effect: { type: "read", rollback_window: null },
      minimum_scope: ["fail"],
    } as CapabilityDeclaration,
    handler: () => {
      throw new ANIPError("handler_error", "intentional failure");
    },
  });
}

function crashCap(): CapabilityDef {
  return defineCapability({
    declaration: {
      name: "crash",
      description: "Throws unexpected error",
      contract_version: "1.0",
      inputs: [],
      output: { type: "object", fields: [] },
      side_effect: { type: "read", rollback_window: null },
      minimum_scope: ["crash"],
    } as CapabilityDeclaration,
    handler: () => {
      throw new Error("unexpected boom");
    },
  });
}

/** Collects hook events into arrays for assertions. */
function createMockHooks() {
  const events: Record<string, unknown[]> = {
    invocationStart: [],
    invocationEnd: [],
    delegationFailure: [],
    auditAppend: [],
    checkpointCreated: [],
    aggregationFlush: [],
    streamingSummary: [],
  };

  const logging: LoggingHooks = {
    onInvocationStart(event) {
      events.invocationStart.push(event);
    },
    onInvocationEnd(event) {
      events.invocationEnd.push(event);
    },
    onDelegationFailure(event) {
      events.delegationFailure.push(event);
    },
    onAuditAppend(event) {
      events.auditAppend.push(event);
    },
    onCheckpointCreated(event) {
      events.checkpointCreated.push(event);
    },
    onAggregationFlush(event) {
      events.aggregationFlush.push(event);
    },
    onStreamingSummary(event) {
      events.streamingSummary.push(event);
    },
  };

  return { events, logging };
}

function makeService(opts: {
  caps?: CapabilityDef[];
  hooks?: { logging: LoggingHooks };
  storage?: StorageBackend;
}) {
  const storage = opts.storage ?? new InMemoryStorage();
  return {
    service: createANIPService({
      serviceId: "test-service",
      capabilities: opts.caps ?? [testCap()],
      storage,
      hooks: opts.hooks ? { logging: opts.hooks.logging } : undefined,
    }),
    storage,
  };
}

async function issueTestToken(
  storage: StorageBackend,
  opts?: { scope?: string[]; capability?: string },
): Promise<DelegationToken> {
  const engine = new DelegationEngine(storage, { serviceId: "test-service" });
  const { token } = await engine.issueRootToken({
    authenticatedPrincipal: "human:test@example.com",
    subject: "human:test@example.com",
    scope: opts?.scope ?? ["greet"],
    capability: opts?.capability ?? "greet",
    purposeParameters: { task_id: "test" },
    ttlHours: 1,
  });
  return token;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Logging hooks: onInvocationStart + onInvocationEnd (success)", () => {
  it("fires both hooks with correct payloads on a successful invocation", async () => {
    const { events, logging } = createMockHooks();
    const { service, storage } = makeService({ hooks: { logging } });
    await service.start();

    const token = await issueTestToken(storage);
    const result = await service.invoke("greet", token, { name: "World" });

    expect(result.success).toBe(true);

    // onInvocationStart
    expect(events.invocationStart).toHaveLength(1);
    const start = events.invocationStart[0] as Record<string, unknown>;
    expect(start.capability).toBe("greet");
    expect(start.invocationId).toMatch(/^inv-/);
    expect(start.clientReferenceId).toBeNull();
    expect(start.rootPrincipal).toBe("human:test@example.com");
    expect(start.subject).toBe("human:test@example.com");
    expect(typeof start.timestamp).toBe("string");

    // onInvocationEnd
    expect(events.invocationEnd).toHaveLength(1);
    const end = events.invocationEnd[0] as Record<string, unknown>;
    expect(end.capability).toBe("greet");
    expect(end.invocationId).toBe(start.invocationId);
    expect(end.success).toBe(true);
    expect(end.failureType).toBeNull();
    expect(typeof end.durationMs).toBe("number");
    expect((end.durationMs as number)).toBeGreaterThanOrEqual(0);
    expect(typeof end.timestamp).toBe("string");

    service.stop();
  });
});

describe("Logging hooks: onInvocationEnd (handler error — ANIPError)", () => {
  it("fires onInvocationEnd with success=false and correct failureType", async () => {
    const { events, logging } = createMockHooks();
    const { service, storage } = makeService({
      caps: [errorCap()],
      hooks: { logging },
    });
    await service.start();

    const token = await issueTestToken(storage, {
      scope: ["fail"],
      capability: "fail",
    });
    const result = await service.invoke("fail", token, {});

    expect(result.success).toBe(false);

    // onInvocationStart should fire (context was built before handler)
    expect(events.invocationStart).toHaveLength(1);

    // onInvocationEnd
    expect(events.invocationEnd).toHaveLength(1);
    const end = events.invocationEnd[0] as Record<string, unknown>;
    expect(end.success).toBe(false);
    expect(end.failureType).toBe("handler_error");
    expect(typeof end.durationMs).toBe("number");

    service.stop();
  });
});

describe("Logging hooks: onInvocationEnd (unexpected error — internal_error)", () => {
  it("fires onInvocationEnd with failureType=internal_error for non-ANIPError", async () => {
    const { events, logging } = createMockHooks();
    const { service, storage } = makeService({
      caps: [crashCap()],
      hooks: { logging },
    });
    await service.start();

    const token = await issueTestToken(storage, {
      scope: ["crash"],
      capability: "crash",
    });
    const result = await service.invoke("crash", token, {});

    expect(result.success).toBe(false);

    expect(events.invocationEnd).toHaveLength(1);
    const end = events.invocationEnd[0] as Record<string, unknown>;
    expect(end.success).toBe(false);
    expect(end.failureType).toBe("internal_error");

    service.stop();
  });
});

describe("Logging hooks: no errors when hooks are omitted", () => {
  it("invocation works fine without hooks", async () => {
    const { service, storage } = makeService({});
    await service.start();

    const token = await issueTestToken(storage);
    const result = await service.invoke("greet", token, { name: "World" });

    expect(result.success).toBe(true);
    expect((result.result as Record<string, unknown>).message).toBe(
      "Hello, World!",
    );

    service.stop();
  });
});

describe("Logging hooks: onAuditAppend", () => {
  it("fires onAuditAppend after a successful invocation", async () => {
    const { events, logging } = createMockHooks();
    const { service, storage } = makeService({ hooks: { logging } });
    await service.start();

    const token = await issueTestToken(storage);
    await service.invoke("greet", token, { name: "World" });

    expect(events.auditAppend.length).toBeGreaterThanOrEqual(1);
    const audit = events.auditAppend[0] as Record<string, unknown>;
    expect(audit.capability).toBe("greet");
    expect(audit.success).toBe(true);
    expect(typeof audit.sequenceNumber).toBe("number");
    expect(typeof audit.invocationId).toBe("string");
    expect(typeof audit.timestamp).toBe("string");

    service.stop();
  });

  it("fires onAuditAppend after a failed invocation", async () => {
    const { events, logging } = createMockHooks();
    const { service, storage } = makeService({
      caps: [errorCap()],
      hooks: { logging },
    });
    await service.start();

    const token = await issueTestToken(storage, {
      scope: ["fail"],
      capability: "fail",
    });
    await service.invoke("fail", token, {});

    expect(events.auditAppend.length).toBeGreaterThanOrEqual(1);
    const audit = events.auditAppend[0] as Record<string, unknown>;
    expect(audit.capability).toBe("fail");
    expect(audit.success).toBe(false);

    service.stop();
  });
});

describe("Logging hooks: onInvocationEnd for unknown capability", () => {
  it("fires onInvocationEnd with failureType=unknown_capability", async () => {
    const { events, logging } = createMockHooks();
    const { service, storage } = makeService({ hooks: { logging } });
    await service.start();

    const token = await issueTestToken(storage);
    const result = await service.invoke("nonexistent", token, {});

    expect(result.success).toBe(false);

    // onInvocationStart should NOT fire (no context built)
    expect(events.invocationStart).toHaveLength(0);

    // onInvocationEnd should fire
    expect(events.invocationEnd).toHaveLength(1);
    const end = events.invocationEnd[0] as Record<string, unknown>;
    expect(end.capability).toBe("nonexistent");
    expect(end.success).toBe(false);
    expect(end.failureType).toBe("unknown_capability");

    service.stop();
  });
});

describe("Logging hooks: onDelegationFailure", () => {
  it("fires onDelegationFailure when token scope is insufficient", async () => {
    const { events, logging } = createMockHooks();
    const { service, storage } = makeService({ hooks: { logging } });
    await service.start();

    // Issue token with wrong scope
    const token = await issueTestToken(storage, {
      scope: ["other"],
      capability: "other",
    });
    const result = await service.invoke("greet", token, { name: "World" });

    expect(result.success).toBe(false);

    expect(events.delegationFailure.length).toBeGreaterThanOrEqual(1);
    const df = events.delegationFailure[0] as Record<string, unknown>;
    expect(typeof df.reason).toBe("string");
    expect(typeof df.timestamp).toBe("string");

    // onInvocationEnd should also fire
    expect(events.invocationEnd).toHaveLength(1);
    const end = events.invocationEnd[0] as Record<string, unknown>;
    expect(end.success).toBe(false);

    service.stop();
  });
});

describe("Logging hooks: clientReferenceId propagation", () => {
  it("passes clientReferenceId through to onInvocationStart", async () => {
    const { events, logging } = createMockHooks();
    const { service, storage } = makeService({ hooks: { logging } });
    await service.start();

    const token = await issueTestToken(storage);
    await service.invoke("greet", token, { name: "World" }, {
      clientReferenceId: "ref-123",
    });

    const start = events.invocationStart[0] as Record<string, unknown>;
    expect(start.clientReferenceId).toBe("ref-123");

    service.stop();
  });
});
