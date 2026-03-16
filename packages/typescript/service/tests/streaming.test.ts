import { describe, it, expect } from "vitest";
import {
  createANIPService,
  defineCapability,
} from "../src/index.js";
import type { CapabilityDef, InvocationContext } from "../src/index.js";
import type { CapabilityDeclaration, DelegationToken } from "@anip/core";
import { InMemoryStorage, DelegationEngine } from "@anip/server";
import type { StorageBackend } from "@anip/server";

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function streamingCap(): CapabilityDef {
  return defineCapability({
    declaration: {
      name: "analyze",
      description: "Analyze data with streaming support",
      contract_version: "1.0",
      inputs: [
        { name: "data", type: "string", required: true, description: "Data to analyze" },
      ],
      output: { type: "object", fields: ["result"] },
      side_effect: { type: "read", rollback_window: null },
      minimum_scope: ["analyze"],
      response_modes: ["unary", "streaming"],
    } as CapabilityDeclaration,
    handler: async (ctx: InvocationContext, params: Record<string, unknown>) => {
      await ctx.emitProgress({ step: 1, status: "parsing" });
      await ctx.emitProgress({ step: 2, status: "complete" });
      return { result: `analyzed: ${params.data}` };
    },
  });
}

function unaryOnlyCap(): CapabilityDef {
  return defineCapability({
    declaration: {
      name: "greet",
      description: "Say hello (unary only)",
      contract_version: "1.0",
      inputs: [
        { name: "name", type: "string", required: true, description: "Who to greet" },
      ],
      output: { type: "object", fields: ["message"] },
      side_effect: { type: "read", rollback_window: null },
      minimum_scope: ["greet"],
    } as CapabilityDeclaration,
    handler: (_ctx, params) => ({
      message: `Hello, ${params.name}!`,
    }),
  });
}

function makeStreamingService(opts?: { storage?: StorageBackend }) {
  const storage = opts?.storage ?? new InMemoryStorage();
  return {
    service: createANIPService({
      serviceId: "test-service",
      capabilities: [streamingCap(), unaryOnlyCap()],
      storage,
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
    scope: opts?.scope ?? ["analyze"],
    capability: opts?.capability ?? "analyze",
    purposeParameters: { task_id: "test" },
    ttlHours: 1,
  });
  return token;
}

// ---------------------------------------------------------------------------
// Streaming tests
// ---------------------------------------------------------------------------

describe("ANIPService streaming invocation", () => {
  it("calls progressSink with structured events in real time", async () => {
    const { service, storage } = makeStreamingService();
    const token = await issueTestToken(storage);

    const events: Record<string, unknown>[] = [];
    const result = await service.invoke("analyze", token, { data: "test" }, {
      stream: true,
      progressSink: async (event: Record<string, unknown>) => {
        events.push(event);
      },
    });

    expect(result.success).toBe(true);

    // Verify 2 progress events were collected
    expect(events).toHaveLength(2);

    // Each event should have structured metadata
    for (const event of events) {
      expect(event.invocation_id).toBeDefined();
      expect((event.invocation_id as string).startsWith("inv-")).toBe(true);
      expect(event).toHaveProperty("client_reference_id");
      expect(event.payload).toBeDefined();
    }

    // Verify payloads
    expect((events[0].payload as Record<string, unknown>).step).toBe(1);
    expect((events[0].payload as Record<string, unknown>).status).toBe("parsing");
    expect((events[1].payload as Record<string, unknown>).step).toBe(2);
    expect((events[1].payload as Record<string, unknown>).status).toBe("complete");

    // Verify stream_summary
    const summary = result.stream_summary as Record<string, unknown>;
    expect(summary).toBeDefined();
    expect(summary.response_mode).toBe("streaming");
    expect(summary.events_emitted).toBe(2);
    expect(summary.events_delivered).toBe(2);
    expect(typeof summary.duration_ms).toBe("number");
    expect(summary.client_disconnected).toBe(false);
  });

  it("ignores progress in unary mode", async () => {
    const { service, storage } = makeStreamingService();
    const token = await issueTestToken(storage);

    const events: Record<string, unknown>[] = [];
    const result = await service.invoke("analyze", token, { data: "test" }, {
      progressSink: async (event: Record<string, unknown>) => {
        events.push(event);
      },
    });

    expect(result.success).toBe(true);
    // No events should have been collected — stream flag was not set
    expect(events).toHaveLength(0);
    // stream_summary should not be present
    expect(result.stream_summary).toBeUndefined();
  });

  it("rejects streaming for unary-only capabilities", async () => {
    const { service, storage } = makeStreamingService();
    const token = await issueTestToken(storage, {
      scope: ["greet"],
      capability: "greet",
    });

    const result = await service.invoke("greet", token, { name: "World" }, {
      stream: true,
    });

    expect(result.success).toBe(false);
    expect((result.failure as Record<string, unknown>).type).toBe(
      "streaming_not_supported",
    );
  });

  it("getCapabilityDeclaration returns declaration", () => {
    const { service } = makeStreamingService();
    const decl = service.getCapabilityDeclaration("analyze");
    expect(decl).not.toBeNull();
    expect((decl as Record<string, unknown>).name).toBe("analyze");
    expect((decl as Record<string, unknown>).response_modes).toEqual(["unary", "streaming"]);
  });

  it("getCapabilityDeclaration returns null for unknown", () => {
    const { service } = makeStreamingService();
    const decl = service.getCapabilityDeclaration("nonexistent");
    expect(decl).toBeNull();
  });
});
