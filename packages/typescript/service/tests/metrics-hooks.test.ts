import { describe, it, expect } from "vitest";
import {
  createANIPService,
  defineCapability,
  ANIPError,
} from "../src/index.js";
import type { CapabilityDef, InvocationContext, MetricsHooks } from "../src/index.js";
import type { CapabilityDeclaration, DelegationToken } from "@anip/core";
import { InMemoryStorage, DelegationEngine } from "@anip/server";
import type { StorageBackend } from "@anip/server";

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

/** Collects metrics hook events into arrays for assertions. */
function createMockMetricsHooks() {
  const events: Record<string, unknown[]> = {
    invocationDuration: [],
    delegationDenied: [],
    auditAppendDuration: [],
    checkpointCreated: [],
    checkpointFailed: [],
    proofGenerated: [],
    proofUnavailable: [],
    retentionDeleted: [],
    aggregationFlushed: [],
    streamingDeliveryFailure: [],
  };

  const metrics: MetricsHooks = {
    onInvocationDuration(event) {
      events.invocationDuration.push(event);
    },
    onDelegationDenied(event) {
      events.delegationDenied.push(event);
    },
    onAuditAppendDuration(event) {
      events.auditAppendDuration.push(event);
    },
    onCheckpointCreated(event) {
      events.checkpointCreated.push(event);
    },
    onCheckpointFailed(event) {
      events.checkpointFailed.push(event);
    },
    onProofGenerated(event) {
      events.proofGenerated.push(event);
    },
    onProofUnavailable(event) {
      events.proofUnavailable.push(event);
    },
    onRetentionDeleted(event) {
      events.retentionDeleted.push(event);
    },
    onAggregationFlushed(event) {
      events.aggregationFlushed.push(event);
    },
    onStreamingDeliveryFailure(event) {
      events.streamingDeliveryFailure.push(event);
    },
  };

  return { events, metrics };
}

function makeService(opts: {
  caps?: CapabilityDef[];
  metrics?: MetricsHooks;
  storage?: StorageBackend;
}) {
  const storage = opts.storage ?? new InMemoryStorage();
  return {
    service: createANIPService({
      serviceId: "test-service",
      capabilities: opts.caps ?? [testCap()],
      storage,
      hooks: opts.metrics ? { metrics: opts.metrics } : undefined,
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

describe("Metrics hooks: onInvocationDuration (success)", () => {
  it("fires with correct payload on a successful invocation", async () => {
    const { events, metrics } = createMockMetricsHooks();
    const { service, storage } = makeService({ metrics });
    await service.start();

    const token = await issueTestToken(storage);
    const result = await service.invoke("greet", token, { name: "World" });

    expect(result.success).toBe(true);

    expect(events.invocationDuration).toHaveLength(1);
    const dur = events.invocationDuration[0] as Record<string, unknown>;
    expect(dur.capability).toBe("greet");
    expect(dur.success).toBe(true);
    expect(typeof dur.durationMs).toBe("number");
    expect((dur.durationMs as number)).toBeGreaterThanOrEqual(0);

    service.stop();
  });
});

describe("Metrics hooks: onInvocationDuration (failure)", () => {
  it("fires with success=false on ANIPError", async () => {
    const { events, metrics } = createMockMetricsHooks();
    const { service, storage } = makeService({
      caps: [errorCap()],
      metrics,
    });
    await service.start();

    const token = await issueTestToken(storage, {
      scope: ["fail"],
      capability: "fail",
    });
    const result = await service.invoke("fail", token, {});

    expect(result.success).toBe(false);

    expect(events.invocationDuration).toHaveLength(1);
    const dur = events.invocationDuration[0] as Record<string, unknown>;
    expect(dur.capability).toBe("fail");
    expect(dur.success).toBe(false);
    expect(typeof dur.durationMs).toBe("number");

    service.stop();
  });

  it("fires with success=false on unexpected error", async () => {
    const { events, metrics } = createMockMetricsHooks();
    const { service, storage } = makeService({
      caps: [crashCap()],
      metrics,
    });
    await service.start();

    const token = await issueTestToken(storage, {
      scope: ["crash"],
      capability: "crash",
    });
    const result = await service.invoke("crash", token, {});

    expect(result.success).toBe(false);

    expect(events.invocationDuration).toHaveLength(1);
    const dur = events.invocationDuration[0] as Record<string, unknown>;
    expect(dur.success).toBe(false);

    service.stop();
  });
});

describe("Metrics hooks: onDelegationDenied", () => {
  it("fires when delegation validation fails", async () => {
    const { events, metrics } = createMockMetricsHooks();
    const { service, storage } = makeService({ metrics });
    await service.start();

    // Issue token with wrong scope
    const token = await issueTestToken(storage, {
      scope: ["other"],
      capability: "other",
    });
    const result = await service.invoke("greet", token, { name: "World" });

    expect(result.success).toBe(false);

    expect(events.delegationDenied.length).toBeGreaterThanOrEqual(1);
    const dd = events.delegationDenied[0] as Record<string, unknown>;
    expect(typeof dd.reason).toBe("string");

    // onInvocationDuration should also fire
    expect(events.invocationDuration).toHaveLength(1);
    const dur = events.invocationDuration[0] as Record<string, unknown>;
    expect(dur.success).toBe(false);

    service.stop();
  });
});

describe("Metrics hooks: onAuditAppendDuration", () => {
  it("fires after a successful invocation", async () => {
    const { events, metrics } = createMockMetricsHooks();
    const { service, storage } = makeService({ metrics });
    await service.start();

    const token = await issueTestToken(storage);
    await service.invoke("greet", token, { name: "World" });

    expect(events.auditAppendDuration.length).toBeGreaterThanOrEqual(1);
    const audit = events.auditAppendDuration[0] as Record<string, unknown>;
    expect(typeof audit.durationMs).toBe("number");
    expect((audit.durationMs as number)).toBeGreaterThanOrEqual(0);
    expect(audit.success).toBe(true);

    service.stop();
  });
});

describe("Metrics hooks: no errors when metrics hooks are omitted", () => {
  it("invocation works fine without metrics hooks", async () => {
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

describe("Metrics hooks: onInvocationDuration for unknown capability", () => {
  it("fires with success=false for unknown capability", async () => {
    const { events, metrics } = createMockMetricsHooks();
    const { service, storage } = makeService({ metrics });
    await service.start();

    const token = await issueTestToken(storage);
    const result = await service.invoke("nonexistent", token, {});

    expect(result.success).toBe(false);

    expect(events.invocationDuration).toHaveLength(1);
    const dur = events.invocationDuration[0] as Record<string, unknown>;
    expect(dur.capability).toBe("nonexistent");
    expect(dur.success).toBe(false);

    service.stop();
  });
});
