import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { AnipStdioServer } from "../src/server.js";
import {
  createANIPService,
  defineCapability,
} from "@anip-dev/service";
import type { ANIPService, CapabilityDef } from "@anip-dev/service";
import type { CapabilityDeclaration } from "@anip-dev/core";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function echoCap(): CapabilityDef {
  return defineCapability({
    declaration: {
      name: "echo",
      description: "Echo the input",
      contract_version: "1.0",
      inputs: [
        { name: "message", type: "string", required: true, description: "What to echo" },
      ],
      output: { type: "object", fields: ["message"] },
      side_effect: { type: "read", rollback_window: null },
      minimum_scope: ["echo"],
    } as CapabilityDeclaration,
    handler: (_ctx, params) => ({
      message: params.message,
    }),
  });
}

function rpc(
  method: string,
  params: Record<string, unknown> = {},
  id: number | string = 1,
): Record<string, unknown> {
  return { jsonrpc: "2.0", id, method, params };
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

describe("AnipStdioServer", () => {
  let service: ANIPService;
  let server: AnipStdioServer;

  beforeAll(async () => {
    service = createANIPService({
      serviceId: "test-stdio-service",
      capabilities: [echoCap()],
      storage: { type: "memory" },
      authenticate: (bearer) =>
        bearer === "test-api-key" ? "human:test@example.com" : null,
    });
    server = new AnipStdioServer(service);
    await service.start();
  });

  afterAll(async () => {
    await service.shutdown();
    service.stop();
  });

  /** Issue a delegation token via the server and return the JWT string. */
  async function issueJwt(opts?: {
    scope?: string[];
    capability?: string;
  }): Promise<string> {
    const resp = (await server.handleRequest(
      rpc("anip.tokens.issue", {
        auth: { bearer: "test-api-key" },
        subject: "human:test@example.com",
        scope: opts?.scope ?? ["echo"],
        capability: opts?.capability ?? "echo",
        purpose_parameters: { task_id: "test" },
        ttl_hours: 1,
      }),
    )) as any;
    if (resp.error) {
      throw new Error(`issueJwt failed: ${JSON.stringify(resp.error)}`);
    }
    return resp.result.token;
  }

  // -----------------------------------------------------------------------
  // Validation
  // -----------------------------------------------------------------------

  describe("request validation", () => {
    it("rejects missing jsonrpc field", async () => {
      const resp = (await server.handleRequest({ id: 1, method: "anip.discovery" })) as any;
      expect(resp.error).toBeDefined();
      expect(resp.error.code).toBe(-32600);
    });

    it("rejects missing method field", async () => {
      const resp = (await server.handleRequest({ jsonrpc: "2.0", id: 1 })) as any;
      expect(resp.error).toBeDefined();
      expect(resp.error.code).toBe(-32600);
    });

    it("rejects missing id field", async () => {
      const resp = (await server.handleRequest({
        jsonrpc: "2.0",
        method: "anip.discovery",
      })) as any;
      expect(resp.error).toBeDefined();
      expect(resp.error.code).toBe(-32600);
    });

    it("rejects unknown method", async () => {
      const resp = (await server.handleRequest(
        rpc("anip.nonexistent"),
      )) as any;
      expect(resp.error).toBeDefined();
      expect(resp.error.code).toBe(-32601);
      expect(resp.error.message).toContain("anip.nonexistent");
    });
  });

  // -----------------------------------------------------------------------
  // anip.discovery
  // -----------------------------------------------------------------------

  describe("anip.discovery", () => {
    it("returns discovery document", async () => {
      const resp = (await server.handleRequest(rpc("anip.discovery"))) as any;
      expect(resp.error).toBeUndefined();
      expect(resp.result).toBeDefined();
      expect(resp.result.anip_discovery).toBeDefined();
    });
  });

  // -----------------------------------------------------------------------
  // anip.manifest
  // -----------------------------------------------------------------------

  describe("anip.manifest", () => {
    it("returns manifest and signature", async () => {
      const resp = (await server.handleRequest(rpc("anip.manifest"))) as any;
      expect(resp.error).toBeUndefined();
      expect(resp.result.manifest).toBeDefined();
      expect(resp.result.signature).toBeDefined();
      expect(typeof resp.result.signature).toBe("string");
    });
  });

  // -----------------------------------------------------------------------
  // anip.jwks
  // -----------------------------------------------------------------------

  describe("anip.jwks", () => {
    it("returns JWKS", async () => {
      const resp = (await server.handleRequest(rpc("anip.jwks"))) as any;
      expect(resp.error).toBeUndefined();
      expect(resp.result.keys).toBeDefined();
      expect(Array.isArray(resp.result.keys)).toBe(true);
    });
  });

  // -----------------------------------------------------------------------
  // anip.tokens.issue
  // -----------------------------------------------------------------------

  describe("anip.tokens.issue", () => {
    it("issues token with valid API key", async () => {
      const resp = (await server.handleRequest(
        rpc("anip.tokens.issue", {
          auth: { bearer: "test-api-key" },
          subject: "human:test@example.com",
          scope: ["echo"],
          capability: "echo",
          purpose_parameters: { task_id: "test" },
          ttl_hours: 1,
        }),
      )) as any;
      expect(resp.error).toBeUndefined();
      expect(resp.result).toBeDefined();
      expect(resp.result.issued).toBe(true);
      expect(resp.result.token).toBeDefined();
      expect(typeof resp.result.token).toBe("string");
    });

    it("rejects missing auth", async () => {
      const resp = (await server.handleRequest(
        rpc("anip.tokens.issue", {
          subject: "human:test@example.com",
          scope: ["echo"],
          capability: "echo",
        }),
      )) as any;
      expect(resp.error).toBeDefined();
      expect(resp.error.code).toBe(-32001);
    });

    it("rejects invalid API key", async () => {
      const resp = (await server.handleRequest(
        rpc("anip.tokens.issue", {
          auth: { bearer: "wrong-key" },
          subject: "human:test@example.com",
          scope: ["echo"],
          capability: "echo",
        }),
      )) as any;
      expect(resp.error).toBeDefined();
      expect(resp.error.code).toBe(-32001);
      // SPEC.md §6.3 Token Issuance: an unrecognised credential is
      // authentication_required, like no credential at all.
      expect(resp.error.data.type).toBe("authentication_required");
    });
  });

  // -----------------------------------------------------------------------
  // anip.permissions
  // -----------------------------------------------------------------------

  describe("anip.permissions", () => {
    it("returns permissions for valid token", async () => {
      const jwt = await issueJwt();
      const resp = (await server.handleRequest(
        rpc("anip.permissions", { auth: { bearer: jwt } }),
      )) as any;
      expect(resp.error).toBeUndefined();
      expect(resp.result).toBeDefined();
    });

    it("rejects missing auth", async () => {
      const resp = (await server.handleRequest(
        rpc("anip.permissions", {}),
      )) as any;
      expect(resp.error).toBeDefined();
      expect(resp.error.code).toBe(-32001);
    });
  });

  // -----------------------------------------------------------------------
  // anip.invoke
  // -----------------------------------------------------------------------

  describe("anip.invoke", () => {
    it("invokes echo capability", async () => {
      const jwt = await issueJwt();
      const resp = (await server.handleRequest(
        rpc("anip.invoke", {
          auth: { bearer: jwt },
          capability: "echo",
          parameters: { message: "hello" },
        }),
      )) as any;
      expect(resp.error).toBeUndefined();
      expect(resp.result).toBeDefined();
    });

    it("rejects missing capability", async () => {
      const jwt = await issueJwt();
      const resp = (await server.handleRequest(
        rpc("anip.invoke", {
          auth: { bearer: jwt },
          parameters: { message: "hello" },
        }),
      )) as any;
      expect(resp.error).toBeDefined();
      expect(resp.error.data?.type).toBe("unknown_capability");
    });

    it("rejects missing auth", async () => {
      const resp = (await server.handleRequest(
        rpc("anip.invoke", {
          capability: "echo",
          parameters: { message: "hello" },
        }),
      )) as any;
      expect(resp.error).toBeDefined();
      expect(resp.error.code).toBe(-32001);
    });
  });

  // -----------------------------------------------------------------------
  // anip.audit.query
  // -----------------------------------------------------------------------

  describe("anip.audit.query", () => {
    it("queries audit log", async () => {
      const jwt = await issueJwt();
      const resp = (await server.handleRequest(
        rpc("anip.audit.query", {
          auth: { bearer: jwt },
        }),
      )) as any;
      expect(resp.error).toBeUndefined();
      expect(resp.result).toBeDefined();
    });

    it("rejects missing auth", async () => {
      const resp = (await server.handleRequest(
        rpc("anip.audit.query", {}),
      )) as any;
      expect(resp.error).toBeDefined();
      expect(resp.error.code).toBe(-32001);
    });
  });

  // -----------------------------------------------------------------------
  // anip.checkpoints.list
  // -----------------------------------------------------------------------

  describe("anip.checkpoints.list", () => {
    it("lists checkpoints", async () => {
      const resp = (await server.handleRequest(
        rpc("anip.checkpoints.list", {}),
      )) as any;
      expect(resp.error).toBeUndefined();
      expect(resp.result).toBeDefined();
    });
  });

  // -----------------------------------------------------------------------
  // anip.checkpoints.get
  // -----------------------------------------------------------------------

  describe("anip.checkpoints.get", () => {
    it("rejects missing id", async () => {
      const resp = (await server.handleRequest(
        rpc("anip.checkpoints.get", {}),
      )) as any;
      expect(resp.error).toBeDefined();
      expect(resp.error.data?.type).toBe("not_found");
    });

    it("rejects unknown checkpoint", async () => {
      const resp = (await server.handleRequest(
        rpc("anip.checkpoints.get", { id: "nonexistent" }),
      )) as any;
      expect(resp.error).toBeDefined();
      expect(resp.error.data?.type).toBe("not_found");
    });
  });

  // -----------------------------------------------------------------------
  // JSON-RPC response structure
  // -----------------------------------------------------------------------

  describe("response structure", () => {
    it("success responses have jsonrpc, id, result", async () => {
      const resp = (await server.handleRequest(rpc("anip.discovery", {}, 42))) as any;
      expect(resp.jsonrpc).toBe("2.0");
      expect(resp.id).toBe(42);
      expect(resp.result).toBeDefined();
      expect(resp.error).toBeUndefined();
    });

    it("error responses have jsonrpc, id, error", async () => {
      const resp = (await server.handleRequest(rpc("anip.nonexistent", {}, 99))) as any;
      expect(resp.jsonrpc).toBe("2.0");
      expect(resp.id).toBe(99);
      expect(resp.error).toBeDefined();
      expect(resp.result).toBeUndefined();
    });

    it("preserves string ids", async () => {
      const resp = (await server.handleRequest(
        rpc("anip.discovery", {}, "abc-123"),
      )) as any;
      expect(resp.id).toBe("abc-123");
    });
  });
});

// ---------------------------------------------------------------------------
// Parameter validation (SPEC.md §6.3): the refusal is in the response message
// ---------------------------------------------------------------------------

describe("AnipStdioServer: parameter validation", () => {
  let service: ANIPService;
  let server: AnipStdioServer;
  const calls: string[] = [];

  function recordingCap(name: string, responseModes: string[]): CapabilityDef {
    return defineCapability({
      declaration: {
        name,
        description: name,
        contract_version: "1.0",
        inputs: [
          { name: "message", type: "string", required: true, description: "What to echo" },
          { name: "times", type: "integer", required: false, description: "How often" },
        ],
        output: { type: "object", fields: ["message"] },
        side_effect: { type: "read", rollback_window: null },
        minimum_scope: [name],
        response_modes: responseModes,
        cost: { certainty: "fixed", financial: { currency: "USD", amount: 300 } },
      } as CapabilityDeclaration,
      handler: async (ctx, params) => {
        calls.push(name);
        await ctx.emitProgress({ step: 1 });
        return { message: params.message };
      },
    });
  }

  beforeAll(async () => {
    service = createANIPService({
      serviceId: "test-stdio-validation",
      capabilities: [recordingCap("echo", ["unary"]), recordingCap("stream_echo", ["unary", "streaming"])],
      storage: { type: "memory" },
      authenticate: (bearer) => (bearer === "test-api-key" ? "human:test@example.com" : null),
    });
    server = new AnipStdioServer(service);
    await service.start();
  });

  afterAll(async () => {
    await service.shutdown();
    service.stop();
  });

  async function issueJwt(capability: string): Promise<string> {
    const resp = (await server.handleRequest(
      rpc("anip.tokens.issue", {
        auth: { bearer: "test-api-key" },
        subject: "human:test@example.com",
        scope: [capability],
        capability,
      }),
    )) as any;
    expect(resp.error).toBeUndefined();
    return resp.result.token;
  }

  const RESOLUTION = {
    action: "retry_now",
    recovery_class: "retry_now",
    requires: "parameters that match the capability's declared inputs",
  };

  it("a missing required input is an invalid_parameters failure in the response", async () => {
    calls.length = 0;
    const jwt = await issueJwt("echo");

    const resp = (await server.handleRequest(
      rpc("anip.invoke", { auth: { bearer: jwt }, capability: "echo", parameters: { times: 2 } }),
    )) as any;

    expect(resp.error).toBeUndefined();
    expect(resp.result.success).toBe(false);
    expect(resp.result.invocation_id).toMatch(/^inv-[0-9a-f]{12}$/);
    expect(resp.result.failure).toEqual({
      type: "invalid_parameters",
      detail: "echo is missing required input(s): message",
      resolution: RESOLUTION,
      retry: false,
    });
    expect(calls).toEqual([]);
  });

  it("absent parameters count as {}", async () => {
    calls.length = 0;
    const jwt = await issueJwt("echo");

    const resp = (await server.handleRequest(
      rpc("anip.invoke", { auth: { bearer: jwt }, capability: "echo" }),
    )) as any;

    expect(resp.result.failure.detail).toBe("echo is missing required input(s): message");
    expect(calls).toEqual([]);
  });

  it("a value of the wrong JSON type is an invalid_parameters failure in the response", async () => {
    calls.length = 0;
    const jwt = await issueJwt("echo");

    const resp = (await server.handleRequest(
      rpc("anip.invoke", { auth: { bearer: jwt }, capability: "echo", parameters: { message: "hi", times: 1.5 } }),
    )) as any;

    expect(resp.result.failure).toEqual({
      type: "invalid_parameters",
      detail: "echo has invalid input(s): 'times' must be integer, got number",
      resolution: RESOLUTION,
      retry: false,
    });
    expect(calls).toEqual([]);
  });

  it("a streaming invocation is refused the same way, with no progress notification", async () => {
    calls.length = 0;
    const jwt = await issueJwt("stream_echo");

    const control = (await server.handleRequest(
      rpc("anip.invoke", { auth: { bearer: jwt }, capability: "stream_echo", parameters: { message: "hi" }, stream: true }),
    )) as any[];
    expect(control.map((m) => m.method)).toEqual(["anip.invoke.progress", undefined]);
    expect(control[1].result.success).toBe(true);

    calls.length = 0;
    const messages = (await server.handleRequest(
      rpc("anip.invoke", { auth: { bearer: jwt }, capability: "stream_echo", parameters: {}, stream: true }),
    )) as any[];

    expect(messages).toHaveLength(1);
    expect(messages[0].result.success).toBe(false);
    expect(messages[0].result.failure).toEqual({
      type: "invalid_parameters",
      detail: "stream_echo is missing required input(s): message",
      resolution: RESOLUTION,
      retry: false,
    });
    expect(calls).toEqual([]);
  });

  it("a streaming invocation gets the budget check of the unary one", async () => {
    calls.length = 0;
    const jwt = await issueJwt("stream_echo");
    const request = (stream: boolean) =>
      rpc("anip.invoke", {
        auth: { bearer: jwt },
        capability: "stream_echo",
        parameters: { message: "hi" },
        budget: { currency: "USD", max_amount: 100 },
        ...(stream ? { stream: true } : {}),
      });

    const unary = (await server.handleRequest(request(false))) as any;
    expect(unary.result.failure.type).toBe("budget_exceeded");

    const messages = (await server.handleRequest(request(true))) as any[];
    expect(messages).toHaveLength(1);
    expect(messages[0].result.success).toBe(false);
    expect(messages[0].result.failure).toEqual(unary.result.failure);
    expect(calls).toEqual([]);
  });
});
