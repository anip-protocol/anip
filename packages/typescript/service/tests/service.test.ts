import { describe, it, expect } from "vitest";
import {
  createANIPService,
  defineCapability,
  ANIPError,
} from "../src/index.js";
import type { CapabilityDef, InvocationContext } from "../src/index.js";
import type { CapabilityDeclaration, DelegationToken } from "@anip-dev/core";
import { PROTOCOL_VERSION } from "@anip-dev/core";
import { InMemoryStorage, DelegationEngine, CheckpointPolicy } from "@anip-dev/server";
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
    const disc = service.getDiscovery({ baseUrl: "https://test.example.com" }) as Record<string, any>;
    const ad = disc.anip_discovery;

    // Required fields per SPEC.md §6.1
    expect(ad.protocol).toBe(PROTOCOL_VERSION);
    expect(ad.compliance).toBe("anip-compliant");
    expect(ad.base_url).toBe("https://test.example.com");
    expect(ad.profile.core).toBe("1.0");
    expect(ad.auth.delegation_token_required).toBe(true);
    expect(ad.auth.minimum_scope_for_discovery).toBe("none");

    // Capability summary shape
    expect(ad.capabilities["greet"].description).toBe("Say hello");
    expect(ad.capabilities["greet"].financial).toBe(false);
    expect(ad.capabilities["greet"].contract).toBe("1.0");
    expect(ad.capabilities["greet"].contract_version).toBeUndefined();

    // Trust and endpoints — only implemented endpoints
    expect(ad.trust_level).toBe("signed");
    expect(ad.endpoints.manifest).toBe("/anip/manifest");
    expect(ad.endpoints.permissions).toBe("/anip/permissions");
    expect(ad.endpoints.handshake).toBeUndefined();
  });

  it("discovery omits base_url when not passed", () => {
    const { service } = makeService();
    const disc = service.getDiscovery() as Record<string, any>;
    expect(disc.anip_discovery.base_url).toBeUndefined();
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

  it("discovery includes posture block", () => {
    const { service } = makeService();
    const disc = service.getDiscovery() as Record<string, any>;
    const posture = disc.anip_discovery.posture;
    expect(posture).toBeDefined();
    expect(posture.audit.enabled).toBe(true);
    expect(posture.audit.signed).toBe(true);
    expect(posture.audit.queryable).toBe(true);
    expect(posture.lineage.invocation_id).toBe(true);
    expect(posture.lineage.client_reference_id.supported).toBe(true);
    expect(posture.lineage.client_reference_id.max_length).toBe(256);
    expect(posture.metadata_policy.bounded_lineage).toBe(true);
    expect(posture.metadata_policy.freeform_context).toBe(false);
    expect(posture.failure_disclosure.detail_level).toBe("full");
    expect(posture.anchoring.enabled).toBe(false);
    expect(posture.anchoring.proofs_available).toBe(false);
  });

  it("discovery posture reflects anchored trust with checkpoint policy", () => {
    const service = createANIPService({
      serviceId: "test-service",
      capabilities: [testCap()],
      storage: { type: "memory" },
      trust: {
        level: "anchored",
        anchoring: {
          cadence: "PT30S",
          maxLag: 120,
        },
      },
      checkpointPolicy: new CheckpointPolicy({ entryCount: 100 }),
    });
    const disc = service.getDiscovery() as Record<string, any>;
    const posture = disc.anip_discovery.posture;
    expect(posture.anchoring.enabled).toBe(true);
    expect(posture.anchoring.cadence).toBe("PT30S");
    expect(posture.anchoring.max_lag).toBe(120);
    expect(posture.anchoring.proofs_available).toBe(true);
  });

  it("discovery posture retention_enforced false before start", () => {
    const { service } = makeService();
    const doc = service.getDiscovery();
    const posture = (doc.anip_discovery as Record<string, unknown>).posture as Record<string, unknown>;
    const audit = posture.audit as Record<string, unknown>;
    expect(audit.retention_enforced).toBe(false);
  });

  it("discovery posture: anchored without checkpoint policy has no proofs", () => {
    const service = createANIPService({
      serviceId: "test-service",
      capabilities: [testCap()],
      storage: { type: "memory" },
      trust: {
        level: "anchored",
        anchoring: {
          cadence: "PT30S",
          maxLag: 120,
        },
      },
    });
    const disc = service.getDiscovery() as Record<string, any>;
    const posture = disc.anip_discovery.posture;
    expect(posture.anchoring.enabled).toBe(true);
    expect(posture.anchoring.proofs_available).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Invoke
// ---------------------------------------------------------------------------

describe("ANIPService invoke", () => {
  it("invoke success", async () => {
    const { service, storage } = makeService();
    const token = await issueTestToken(storage);
    const result = await service.invoke("greet", token, { name: "World" });
    expect(result.success).toBe(true);
    expect((result.result as Record<string, any>).message).toBe(
      "Hello, World!",
    );
  });

  it("invoke unknown capability", async () => {
    const { service, storage } = makeService();
    const token = await issueTestToken(storage);
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
    const token = await issueTestToken(storage, {
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
    const token = await issueTestToken(storage, {
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

  it("response includes invocation_id", async () => {
    const { service, storage } = makeService();
    const token = await issueTestToken(storage);
    const result = await service.invoke("greet", token, { name: "World" });
    expect(result.success).toBe(true);
    expect(result.invocation_id).toBeDefined();
    expect((result.invocation_id as string).startsWith("inv-")).toBe(true);
    expect((result.invocation_id as string).length).toBe(16);
  });

  it("response echoes client_reference_id", async () => {
    const { service, storage } = makeService();
    const token = await issueTestToken(storage);
    const result = await service.invoke("greet", token, { name: "World" }, {
      clientReferenceId: "task:42",
    });
    expect(result.client_reference_id).toBe("task:42");
  });

  it("client_reference_id null when absent", async () => {
    const { service, storage } = makeService();
    const token = await issueTestToken(storage);
    const result = await service.invoke("greet", token, { name: "World" });
    expect(result.client_reference_id).toBeNull();
  });

  it("failure response still has invocation_id", async () => {
    const { service, storage } = makeService();
    const token = await issueTestToken(storage);
    const result = await service.invoke("nonexistent", token, {});
    expect(result.success).toBe(false);
    expect(result.invocation_id).toBeDefined();
    expect((result.invocation_id as string).startsWith("inv-")).toBe(true);
  });

  it("handler context includes lineage", async () => {
    let capturedCtx: Record<string, unknown> = {};
    const ctxCap = defineCapability({
      declaration: {
        name: "ctx_cap",
        description: "Captures context",
        contract_version: "1.0",
        inputs: [],
        output: { type: "object", fields: [] },
        side_effect: { type: "read", rollback_window: null },
        minimum_scope: ["test"],
      } as CapabilityDeclaration,
      handler: (ctx, _params) => {
        capturedCtx = {
          invocationId: ctx.invocationId,
          clientReferenceId: ctx.clientReferenceId,
        };
        return { ok: true };
      },
    });
    const { service, storage } = makeService({ caps: [ctxCap] });
    const token = await issueTestToken(storage, {
      scope: ["test"],
      capability: "ctx_cap",
    });
    await service.invoke("ctx_cap", token, {}, {
      clientReferenceId: "ref-abc",
    });
    expect((capturedCtx.invocationId as string).startsWith("inv-")).toBe(true);
    expect(capturedCtx.clientReferenceId).toBe("ref-abc");
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
    const token = await issueTestToken(storage, {
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
// Event classification in audit (v0.8)
// ---------------------------------------------------------------------------

describe("ANIPService event classification in audit", () => {
  it("successful read invocation stores low_risk_success", async () => {
    const { service, storage } = makeService();
    const token = await issueTestToken(storage);
    const result = await service.invoke("greet", token, { name: "World" });
    expect(result.success).toBe(true);

    const auditResult = await service.queryAudit(token);
    const entries = (auditResult as any).entries as Record<string, unknown>[];
    expect(entries.length).toBeGreaterThanOrEqual(1);
    const entry = entries[0];
    expect(entry.event_class).toBe("low_risk_success");
    expect(entry.retention_tier).toBe("short");
    expect(entry.expires_at).toBeDefined();
    expect(entry.expires_at).not.toBeNull();
  });

  it("failed invocation (ANIPError) stores correct event_class", async () => {
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
    const token = await issueTestToken(storage, {
      scope: ["test"],
      capability: "fail_cap",
    });
    const result = await service.invoke("fail_cap", token, {});
    expect(result.success).toBe(false);

    const auditResult = await service.queryAudit(token);
    const entries = (auditResult as any).entries as Record<string, unknown>[];
    expect(entries.length).toBeGreaterThanOrEqual(1);
    const entry = entries[0];
    // "not_found" is not in MALFORMED_FAILURE_TYPES -> high_risk_denial
    expect(entry.event_class).toBe("high_risk_denial");
    expect(entry.retention_tier).toBe("medium");
    expect(entry.expires_at).not.toBeNull();
  });

  it("unexpected error stores malformed_or_spam", async () => {
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
    const token = await issueTestToken(storage, {
      scope: ["test"],
      capability: "crash_cap",
    });
    const result = await service.invoke("crash_cap", token, {});
    expect(result.success).toBe(false);

    const auditResult = await service.queryAudit(token);
    const entries = (auditResult as any).entries as Record<string, unknown>[];
    expect(entries.length).toBeGreaterThanOrEqual(1);
    const entry = entries[0];
    // "internal_error" IS in MALFORMED_FAILURE_TYPES -> malformed_or_spam
    expect(entry.event_class).toBe("malformed_or_spam");
    expect(entry.retention_tier).toBe("short");
    expect(entry.expires_at).not.toBeNull();
  });

  it("write capability success stores high_risk_success", async () => {
    const writeCap = defineCapability({
      declaration: {
        name: "write_cap",
        description: "A write capability",
        contract_version: "1.0",
        inputs: [],
        output: { type: "object", fields: [] },
        side_effect: { type: "write", rollback_window: "PT1H" },
        minimum_scope: ["write"],
      } as CapabilityDeclaration,
      handler: () => ({ written: true }),
    });
    const { service, storage } = makeService({ caps: [writeCap] });
    const token = await issueTestToken(storage, {
      scope: ["write"],
      capability: "write_cap",
    });
    const result = await service.invoke("write_cap", token, {});
    expect(result.success).toBe(true);

    const auditResult = await service.queryAudit(token);
    const entries = (auditResult as any).entries as Record<string, unknown>[];
    expect(entries.length).toBeGreaterThanOrEqual(1);
    const entry = entries[0];
    expect(entry.event_class).toBe("high_risk_success");
    expect(entry.retention_tier).toBe("long");
    expect(entry.expires_at).not.toBeNull();
  });

  it("queryAudit event_class filter works", async () => {
    const { service, storage } = makeService();
    const token = await issueTestToken(storage);

    // Successful invocation -> low_risk_success
    await service.invoke("greet", token, { name: "World" });

    const filtered = await service.queryAudit(token, { event_class: "low_risk_success" });
    expect((filtered as any).count).toBeGreaterThanOrEqual(1);

    const filteredEmpty = await service.queryAudit(token, { event_class: "high_risk_success" });
    expect((filteredEmpty as any).count).toBe(0);
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
    const token = await issueTestToken(storage, {
      scope: ["test"],
      capability: "async_cap",
    });
    const result = await service.invoke("async_cap", token, {});
    expect(result.success).toBe(true);
    expect((result.result as Record<string, any>).ok).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// issueCapabilityToken
// ---------------------------------------------------------------------------

describe("ANIPService issueCapabilityToken", () => {
  it("issues a root token bound to a capability", async () => {
    const { service } = makeService();
    await service.start();

    const resp = (await service.issueCapabilityToken(
      "human:alice@example.com",
      "greet",
      ["greet"],
    )) as Record<string, any>;

    expect(resp.issued).toBe(true);
    expect(resp.token_id).toBeDefined();
    expect(resp.token).toBeDefined();
    expect(resp.expires).toBeDefined();

    // Resolve the token and check capability binding.
    const resolved = await service.resolveBearerToken(resp.token);
    expect(resolved.subject).toBe("human:alice@example.com");
    expect(resolved.purpose?.capability).toBe("greet");
  });

  it("passes optional parameters through", async () => {
    const { service } = makeService();
    await service.start();

    const resp = (await service.issueCapabilityToken(
      "human:bob@example.com",
      "greet",
      ["greet"],
      {
        purposeParameters: { task_id: "task-123" },
        ttlHours: 4,
        budget: { currency: "USD", max_amount: 50 },
      },
    )) as Record<string, any>;

    expect(resp.issued).toBe(true);
    expect(resp.token_id).toBeDefined();
  });

  it("scope must be explicit (not derived from capability)", async () => {
    const { service } = makeService();
    await service.start();

    // Use a scope that differs from the capability name.
    const resp = (await service.issueCapabilityToken(
      "human:carol@example.com",
      "greet",
      ["custom.scope"],
    )) as Record<string, any>;

    expect(resp.issued).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// issueDelegatedCapabilityToken
// ---------------------------------------------------------------------------

describe("ANIPService issueDelegatedCapabilityToken", () => {
  it("issues a delegated token from a parent token", async () => {
    const { service } = makeService();
    await service.start();

    // Issue root token first
    const rootResp = (await service.issueCapabilityToken(
      "human:alice@example.com",
      "greet",
      ["greet"],
    )) as Record<string, any>;
    expect(rootResp.issued).toBe(true);

    // Delegate
    const resp = (await service.issueDelegatedCapabilityToken(
      "human:alice@example.com",
      rootResp.token_id,
      "greet",
      ["greet"],
      "agent:helper",
    )) as Record<string, any>;

    expect(resp.issued).toBe(true);
    expect(resp.token_id).toBeDefined();
    expect(resp.token).toBeDefined();

    // Resolve and verify delegation
    const resolved = await service.resolveBearerToken(resp.token);
    expect(resolved.subject).toBe("agent:helper");
    expect(resolved.purpose?.capability).toBe("greet");
    expect(resolved.parent).toBe(rootResp.token_id);
  });

  it("scope must be explicit (not inferred from capability)", async () => {
    const { service } = makeService();
    await service.start();

    // Root token with broader scope
    const rootResp = (await service.issueCapabilityToken(
      "human:bob@example.com",
      "greet",
      ["greet", "greet.read"],
    )) as Record<string, any>;

    // Delegate with a subset scope — scope is explicit, not derived from capability.
    const resp = (await service.issueDelegatedCapabilityToken(
      "human:bob@example.com",
      rootResp.token_id,
      "greet",
      ["greet"],
      "agent:worker",
    )) as Record<string, any>;

    expect(resp.issued).toBe(true);
  });

  it("passes optional parameters through", async () => {
    const { service } = makeService();
    await service.start();

    const rootResp = (await service.issueCapabilityToken(
      "human:carol@example.com",
      "greet",
      ["greet"],
    )) as Record<string, any>;

    const resp = (await service.issueDelegatedCapabilityToken(
      "human:carol@example.com",
      rootResp.token_id,
      "greet",
      ["greet"],
      "agent:delegate",
      {
        callerClass: "automated",
        purposeParameters: { task_id: "task-456" },
        ttlHours: 1,
        budget: { currency: "USD", max_amount: 50 },
      },
    )) as Record<string, any>;

    expect(resp.issued).toBe(true);
    expect(resp.token_id).toBeDefined();
  });
});
