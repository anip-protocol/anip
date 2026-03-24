import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { AnipStdioServer } from "../src/server.js";
import {
  createANIPService,
  defineCapability,
} from "@anip/service";
import type { ANIPService, CapabilityDef } from "@anip/service";
import type { CapabilityDeclaration } from "@anip/core";

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
