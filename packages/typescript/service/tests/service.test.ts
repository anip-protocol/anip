import { describe, it, expect } from "vitest";
import {
  createANIPService,
  defineCapability,
  ANIPError,
} from "../src/index.js";
import type { CapabilityDef, InvocationContext } from "../src/index.js";
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

function makeService(opts?: {
  caps?: CapabilityDef[];
  authenticate?: (bearer: string) => string | null;
  storage?: StorageBackend;
}) {
  const storage = opts?.storage ?? new InMemoryStorage();
  return {
    service: createANIPService({
      serviceId: "test-service",
      capabilities: opts?.caps ?? [testCap()],
      storage,
      authenticate: opts?.authenticate,
    }),
    storage,
  };
}

function issueTestToken(
  storage: StorageBackend,
  opts?: { scope?: string[]; capability?: string },
): DelegationToken {
  const engine = new DelegationEngine(storage, { serviceId: "test-service" });
  const { token } = engine.issueRootToken({
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
// Construction
// ---------------------------------------------------------------------------

describe("ANIPService construction", () => {
  it("minimal construction", () => {
    const { service } = makeService();
    // Service should be created without errors
    const disc = service.getDiscovery();
    expect(disc).toBeDefined();
  });

  it("manifest built from capabilities", () => {
    const { service } = makeService();
    const manifest = service.getManifest();
    expect(manifest.capabilities).toBeDefined();
    expect(manifest.capabilities["greet"]).toBeDefined();
  });

  it("discovery document structure", () => {
    const { service } = makeService();
    const disc = service.getDiscovery() as Record<string, any>;
    expect(disc.anip_discovery).toBeDefined();
    expect(disc.anip_discovery.capabilities["greet"]).toBeDefined();
    expect(disc.anip_discovery.trust_level).toBe("signed");
    expect(disc.anip_discovery.endpoints).toBeDefined();
    expect(disc.anip_discovery.endpoints.manifest).toBe("/anip/manifest");
  });

  it("JWKS available", async () => {
    const { service } = makeService();
    const jwks = (await service.getJwks()) as Record<string, any>;
    expect(jwks.keys).toBeDefined();
    expect(Array.isArray(jwks.keys)).toBe(true);
    expect(jwks.keys.length).toBeGreaterThan(0);
  });

  it("attested trust rejected", () => {
    expect(() =>
      createANIPService({
        serviceId: "test-service",
        capabilities: [testCap()],
        trust: "attested" as any,
      }),
    ).toThrow("not yet supported");
  });
});

// ---------------------------------------------------------------------------
// Invoke
// ---------------------------------------------------------------------------

describe("ANIPService invoke", () => {
  it("invoke success", async () => {
    const { service, storage } = makeService();
    const token = issueTestToken(storage);
    const result = await service.invoke("greet", token, { name: "World" });
    expect(result.success).toBe(true);
    expect((result.result as Record<string, any>).message).toBe(
      "Hello, World!",
    );
  });

  it("invoke unknown capability", async () => {
    const { service, storage } = makeService();
    const token = issueTestToken(storage);
    const result = await service.invoke("nonexistent", token, {});
    expect(result.success).toBe(false);
    expect((result.failure as Record<string, any>).type).toBe(
      "unknown_capability",
    );
  });

  it("invoke with ANIPError", async () => {
    const failCap = defineCapability({
      declaration: {
        name: "fail_cap",
        description: "Always fails",
        contract_version: "1.0",
        inputs: [],
        output: { type: "object", fields: [] },
        side_effect: { type: "read", rollback_window: null },
        minimum_scope: ["test"],
      } as CapabilityDeclaration,
      handler: () => {
        throw new ANIPError("not_found", "Thing not found");
      },
    });
    const { service, storage } = makeService({ caps: [failCap] });
    const token = issueTestToken(storage, {
      scope: ["test"],
      capability: "fail_cap",
    });
    const result = await service.invoke("fail_cap", token, {});
    expect(result.success).toBe(false);
    expect((result.failure as Record<string, any>).type).toBe("not_found");
  });

  it("invoke with unexpected error", async () => {
    const crashCap = defineCapability({
      declaration: {
        name: "crash_cap",
        description: "Crashes",
        contract_version: "1.0",
        inputs: [],
        output: { type: "object", fields: [] },
        side_effect: { type: "read", rollback_window: null },
        minimum_scope: ["test"],
      } as CapabilityDeclaration,
      handler: () => {
        throw new Error("boom");
      },
    });
    const { service, storage } = makeService({ caps: [crashCap] });
    const token = issueTestToken(storage, {
      scope: ["test"],
      capability: "crash_cap",
    });
    const result = await service.invoke("crash_cap", token, {});
    expect(result.success).toBe(false);
    expect((result.failure as Record<string, any>).type).toBe(
      "internal_error",
    );
    // Detail should NOT leak the actual exception
    expect((result.failure as Record<string, any>).detail).not.toContain(
      "boom",
    );
  });

  it("cost tracking via setCostActual", async () => {
    const costCap = defineCapability({
      declaration: {
        name: "cost_cap",
        description: "Tracks cost",
        contract_version: "1.0",
        inputs: [],
        output: { type: "object", fields: [] },
        side_effect: { type: "read", rollback_window: null },
        minimum_scope: ["test"],
      } as CapabilityDeclaration,
      handler: (ctx, _params) => {
        ctx.setCostActual({
          financial: { amount: 450.0, currency: "USD" },
        });
        return { booked: true };
      },
    });
    const { service, storage } = makeService({ caps: [costCap] });
    const token = issueTestToken(storage, {
      scope: ["test"],
      capability: "cost_cap",
    });
    const result = await service.invoke("cost_cap", token, {});
    expect(result.success).toBe(true);
    const costActual = result.cost_actual as Record<string, any>;
    expect(costActual.financial.amount).toBe(450.0);
  });
});

// ---------------------------------------------------------------------------
// Token lifecycle
// ---------------------------------------------------------------------------

describe("ANIPService token lifecycle", () => {
  it("token round-trip (issue → resolve)", async () => {
    const { service } = makeService();
    const issued = (await service.issueToken("human:test@example.com", {
      subject: "human:test@example.com",
      scope: ["greet"],
      capability: "greet",
      purpose_parameters: { task_id: "test" },
    })) as Record<string, any>;

    expect(issued.issued).toBe(true);
    expect(issued.token).toBeDefined();

    // Round-trip: resolve the JWT we just issued
    const resolved = await service.resolveBearerToken(issued.token as string);
    expect(resolved.subject).toBe("human:test@example.com");
  });

  it("authenticate bearer with API key", async () => {
    const { service } = makeService({
      authenticate: (bearer) =>
        bearer === "test-key" ? "human:test@example.com" : null,
    });
    const principal = await service.authenticateBearer("test-key");
    expect(principal).toBe("human:test@example.com");
  });

  it("authenticate bearer unknown returns null", async () => {
    const { service } = makeService({
      authenticate: (bearer) =>
        bearer === "test-key" ? "human:test@example.com" : null,
    });
    const principal = await service.authenticateBearer("unknown-key");
    expect(principal).toBeNull();
  });

  it("sub-delegation guardrail", async () => {
    const { service } = makeService({
      authenticate: (bearer) =>
        bearer === "test-key" ? "human:test@example.com" : null,
    });

    const issued = (await service.issueToken("human:test@example.com", {
      subject: "agent:bot-1",
      scope: ["greet"],
      capability: "greet",
      purpose_parameters: { task_id: "test" },
    })) as Record<string, any>;

    // The wrong principal tries to sub-delegate
    await expect(
      service.issueToken("human:wrong@example.com", {
        parent_token: issued.token_id as string,
        subject: "agent:bot-2",
        scope: ["greet"],
        capability: "greet",
      }),
    ).rejects.toThrow("insufficient_authority");
  });
});

// ---------------------------------------------------------------------------
// Async handler
// ---------------------------------------------------------------------------

describe("ANIPService async handler", () => {
  it("handler can return a Promise", async () => {
    const asyncCap = defineCapability({
      declaration: {
        name: "async_cap",
        description: "Async handler",
        contract_version: "1.0",
        inputs: [],
        output: { type: "object", fields: ["ok"] },
        side_effect: { type: "read", rollback_window: null },
        minimum_scope: ["test"],
      } as CapabilityDeclaration,
      handler: async (_ctx, _params) => {
        return { ok: true };
      },
    });
    const { service, storage } = makeService({ caps: [asyncCap] });
    const token = issueTestToken(storage, {
      scope: ["test"],
      capability: "async_cap",
    });
    const result = await service.invoke("async_cap", token, {});
    expect(result.success).toBe(true);
    expect((result.result as Record<string, any>).ok).toBe(true);
  });
});
