import { describe, it, expect } from "vitest";
import {
  createANIPService,
  defineCapability,
  ANIPError,
} from "../src/index.js";
import type { CapabilityDef, InvocationContext, TracingHooks } from "../src/index.js";
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

interface SpanEvent {
  name: string;
  attributes: Record<string, string | number | boolean>;
  parentSpan?: unknown;
}

interface EndSpanEvent {
  span: unknown;
  status: "ok" | "error";
  errorType?: string;
  errorMessage?: string;
  attributes?: Record<string, string | number | boolean>;
}

/** Collects tracing hook events into arrays for assertions. */
function createMockTracingHooks() {
  const started: SpanEvent[] = [];
  const ended: EndSpanEvent[] = [];
  let spanCounter = 0;

  const tracing: TracingHooks = {
    startSpan(event) {
      spanCounter++;
      const span = { id: spanCounter, name: event.name };
      started.push(event);
      return span;
    },
    endSpan(event) {
      ended.push(event);
    },
  };

  return { started, ended, tracing };
}

function makeService(opts: {
  caps?: CapabilityDef[];
  tracing?: TracingHooks;
  storage?: StorageBackend;
}) {
  const storage = opts.storage ?? new InMemoryStorage();
  return {
    service: createANIPService({
      serviceId: "test-service",
      capabilities: opts.caps ?? [testCap()],
      storage,
      hooks: opts.tracing ? { tracing: opts.tracing } : undefined,
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

describe("Tracing hooks: successful invocation fires correct spans", () => {
  it("fires anip.invoke, anip.delegation.validate, anip.handler.execute, and anip.audit.append", async () => {
    const { started, ended, tracing } = createMockTracingHooks();
    const { service, storage } = makeService({ tracing });
    await service.start();

    const token = await issueTestToken(storage);
    const result = await service.invoke("greet", token, { name: "World" });

    expect(result.success).toBe(true);

    // Check started spans
    const spanNames = started.map((s) => s.name);
    expect(spanNames).toContain("anip.invoke");
    expect(spanNames).toContain("anip.delegation.validate");
    expect(spanNames).toContain("anip.handler.execute");
    expect(spanNames).toContain("anip.audit.append");

    // All spans should end with status "ok"
    expect(ended.length).toBe(started.length);
    for (const e of ended) {
      expect(e.status).toBe("ok");
    }

    // Check anip.invoke attributes
    const invokeStart = started.find((s) => s.name === "anip.invoke")!;
    expect(invokeStart.attributes.capability).toBe("greet");

    service.stop();
  });
});

describe("Tracing hooks: handler error fires endSpan with error status", () => {
  it("fires endSpan with status='error' for anip.handler.execute on ANIPError", async () => {
    const { started, ended, tracing } = createMockTracingHooks();
    const { service, storage } = makeService({
      caps: [errorCap()],
      tracing,
    });
    await service.start();

    const token = await issueTestToken(storage, {
      scope: ["fail"],
      capability: "fail",
    });
    const result = await service.invoke("fail", token, {});

    expect(result.success).toBe(false);

    // anip.handler.execute should have ended with error
    const handlerStart = started.find((s) => s.name === "anip.handler.execute");
    expect(handlerStart).toBeDefined();

    const handlerEnd = ended.find(
      (e) => (e.span as any).name === "anip.handler.execute",
    );
    expect(handlerEnd).toBeDefined();
    expect(handlerEnd!.status).toBe("error");
    expect(handlerEnd!.errorType).toBe("ANIPError");
    expect(handlerEnd!.errorMessage).toContain("intentional failure");

    // anip.invoke root span should still end ok (because invoke catches errors and returns)
    const invokeEnd = ended.find(
      (e) => (e.span as any).name === "anip.invoke",
    );
    expect(invokeEnd).toBeDefined();
    expect(invokeEnd!.status).toBe("ok");

    service.stop();
  });

  it("fires endSpan with status='error' for anip.handler.execute on unexpected error", async () => {
    const { started, ended, tracing } = createMockTracingHooks();
    const { service, storage } = makeService({
      caps: [crashCap()],
      tracing,
    });
    await service.start();

    const token = await issueTestToken(storage, {
      scope: ["crash"],
      capability: "crash",
    });
    const result = await service.invoke("crash", token, {});

    expect(result.success).toBe(false);

    const handlerEnd = ended.find(
      (e) => (e.span as any).name === "anip.handler.execute",
    );
    expect(handlerEnd).toBeDefined();
    expect(handlerEnd!.status).toBe("error");
    expect(handlerEnd!.errorType).toBe("Error");
    expect(handlerEnd!.errorMessage).toBe("unexpected boom");

    service.stop();
  });
});

describe("Tracing hooks: span nesting via parentSpan", () => {
  it("inner spans receive parentSpan from anip.invoke root span", async () => {
    const { started, tracing } = createMockTracingHooks();
    const { service, storage } = makeService({ tracing });
    await service.start();

    const token = await issueTestToken(storage);
    await service.invoke("greet", token, { name: "World" });

    // The root span (anip.invoke) should have no parentSpan
    const invokeStart = started.find((s) => s.name === "anip.invoke")!;
    expect(invokeStart.parentSpan).toBeUndefined();

    // Inner spans should have parentSpan set to the root span object
    const rootSpanObj = invokeStart; // startSpan returned { id, name } object
    const handlerStart = started.find(
      (s) => s.name === "anip.handler.execute",
    )!;
    expect(handlerStart.parentSpan).toBeDefined();
    // The parentSpan should be the object returned by startSpan for anip.invoke
    expect((handlerStart.parentSpan as any).name).toBe("anip.invoke");

    const auditStart = started.find((s) => s.name === "anip.audit.append")!;
    expect(auditStart.parentSpan).toBeDefined();
    expect((auditStart.parentSpan as any).name).toBe("anip.invoke");

    const delegationStart = started.find(
      (s) => s.name === "anip.delegation.validate",
    )!;
    expect(delegationStart.parentSpan).toBeDefined();
    expect((delegationStart.parentSpan as any).name).toBe("anip.invoke");

    service.stop();
  });
});

describe("Tracing hooks: no errors when tracing hooks are omitted", () => {
  it("invocation works fine without tracing hooks", async () => {
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

describe("Tracing hooks: delegation failure still fires spans", () => {
  it("fires anip.invoke and anip.delegation.validate on scope mismatch", async () => {
    const { started, ended, tracing } = createMockTracingHooks();
    const { service, storage } = makeService({ tracing });
    await service.start();

    const token = await issueTestToken(storage, {
      scope: ["other"],
      capability: "other",
    });
    const result = await service.invoke("greet", token, { name: "World" });

    expect(result.success).toBe(false);

    const spanNames = started.map((s) => s.name);
    expect(spanNames).toContain("anip.invoke");
    expect(spanNames).toContain("anip.delegation.validate");
    // audit should also be traced (for the failure audit entry)
    expect(spanNames).toContain("anip.audit.append");

    // Root span should end ok (invoke returns failure dict, not throwing)
    const invokeEnd = ended.find(
      (e) => (e.span as any).name === "anip.invoke",
    );
    expect(invokeEnd).toBeDefined();
    expect(invokeEnd!.status).toBe("ok");

    service.stop();
  });
});

describe("Tracing hooks: unknown capability still fires root span", () => {
  it("fires anip.invoke for unknown capability", async () => {
    const { started, ended, tracing } = createMockTracingHooks();
    const { service, storage } = makeService({ tracing });
    await service.start();

    const token = await issueTestToken(storage);
    const result = await service.invoke("nonexistent", token, {});

    expect(result.success).toBe(false);

    const spanNames = started.map((s) => s.name);
    expect(spanNames).toContain("anip.invoke");

    const invokeEnd = ended.find(
      (e) => (e.span as any).name === "anip.invoke",
    );
    expect(invokeEnd).toBeDefined();
    expect(invokeEnd!.status).toBe("ok");

    service.stop();
  });
});
