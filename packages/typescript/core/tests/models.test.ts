import { describe, it, expect } from "vitest";
import {
  ANIPManifest,
  DelegationToken,
  TrustPosture,
  AnchoringPolicy,
  ANIPFailure,
  CapabilityDeclaration,
  PermissionResponse,
  InvokeRequest,
  InvokeResponse,
  PROTOCOL_VERSION,
} from "../src/index.js";

describe("Protocol constants", () => {
  it("exports correct protocol version", () => {
    expect(PROTOCOL_VERSION).toBe("anip/0.3");
  });
});

describe("DelegationToken", () => {
  it("parses valid token", () => {
    const result = DelegationToken.safeParse({
      token_id: "tok-1",
      issuer: "svc",
      subject: "agent",
      scope: ["travel.search"],
      purpose: {
        capability: "search_flights",
        parameters: {},
        task_id: "t1",
      },
      parent: null,
      expires: "2026-12-31T23:59:59Z",
      constraints: {
        max_delegation_depth: 3,
        concurrent_branches: "allowed",
      },
    });
    expect(result.success).toBe(true);
  });

  it("rejects missing required fields", () => {
    const result = DelegationToken.safeParse({ token_id: "tok-1" });
    expect(result.success).toBe(false);
  });
});

describe("TrustPosture", () => {
  it("defaults to signed level", () => {
    const result = TrustPosture.parse({});
    expect(result.level).toBe("signed");
  });

  it("parses anchored with policy", () => {
    const result = TrustPosture.parse({
      level: "anchored",
      anchoring: {
        cadence: "PT60S",
        max_lag: 100,
        sink: ["witness:example.com"],
      },
    });
    expect(result.anchoring?.max_lag).toBe(100);
  });
});

describe("ANIPFailure", () => {
  it("parses failure with resolution", () => {
    const result = ANIPFailure.parse({
      type: "scope_insufficient",
      detail: "Missing scope",
      resolution: { action: "request_broader_scope" },
      retry: false,
    });
    expect(result.type).toBe("scope_insufficient");
  });
});

describe("ANIPManifest", () => {
  it("parses minimal manifest", () => {
    const result = ANIPManifest.safeParse({
      protocol: "anip/0.3",
      profile: { core: "1.0" },
      capabilities: {},
    });
    expect(result.success).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// InvokeRequest — lineage fields (v0.4)
// ---------------------------------------------------------------------------

describe("InvokeRequest", () => {
  it("has token field (string), not delegation_token", () => {
    const result = InvokeRequest.safeParse({ token: "jwt.token.here" });
    expect(result.success).toBe(true);
    expect(result.data!.token).toBe("jwt.token.here");
    // delegation_token should not be a recognized field
    expect("delegation_token" in result.data!).toBe(false);
  });

  it("requires token field", () => {
    const result = InvokeRequest.safeParse({});
    expect(result.success).toBe(false);
  });

  it("rejects delegation_token as the only auth field", () => {
    const result = InvokeRequest.safeParse({
      delegation_token: { token_id: "tok-1" },
    });
    expect(result.success).toBe(false);
  });

  it("defaults client_reference_id to null", () => {
    const result = InvokeRequest.parse({ token: "t" });
    expect(result.client_reference_id).toBeNull();
  });

  it("accepts client_reference_id up to 256 chars", () => {
    const id256 = "a".repeat(256);
    const result = InvokeRequest.safeParse({
      token: "t",
      client_reference_id: id256,
    });
    expect(result.success).toBe(true);
    expect(result.data!.client_reference_id).toBe(id256);
  });

  it("rejects client_reference_id longer than 256 chars", () => {
    const id257 = "a".repeat(257);
    const result = InvokeRequest.safeParse({
      token: "t",
      client_reference_id: id257,
    });
    expect(result.success).toBe(false);
  });

  it("accepts explicit null for client_reference_id", () => {
    const result = InvokeRequest.parse({
      token: "t",
      client_reference_id: null,
    });
    expect(result.client_reference_id).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// InvokeResponse — lineage fields (v0.4)
// ---------------------------------------------------------------------------

describe("InvokeResponse", () => {
  const validInvocationId = "inv-0123456789ab";

  it("requires invocation_id", () => {
    const result = InvokeResponse.safeParse({ success: true });
    expect(result.success).toBe(false);
  });

  it("accepts valid invocation_id matching ^inv-[0-9a-f]{12}$", () => {
    const result = InvokeResponse.safeParse({
      success: true,
      invocation_id: validInvocationId,
    });
    expect(result.success).toBe(true);
    expect(result.data!.invocation_id).toBe(validInvocationId);
  });

  it("rejects invocation_id that does not match pattern", () => {
    const badIds = [
      "inv-0123456789a",     // too short (11 hex)
      "inv-0123456789abc",   // too long (13 hex)
      "inv-0123456789AG",    // uppercase hex
      "abc-0123456789ab",    // wrong prefix
      "0123456789ab",        // no prefix
    ];
    for (const id of badIds) {
      const result = InvokeResponse.safeParse({
        success: true,
        invocation_id: id,
      });
      expect(result.success).toBe(false);
    }
  });

  it("defaults client_reference_id to null on response", () => {
    const result = InvokeResponse.parse({
      success: true,
      invocation_id: validInvocationId,
    });
    expect(result.client_reference_id).toBeNull();
  });

  it("echoes client_reference_id when provided", () => {
    const result = InvokeResponse.parse({
      success: true,
      invocation_id: validInvocationId,
      client_reference_id: "my-ref-123",
    });
    expect(result.client_reference_id).toBe("my-ref-123");
  });

  it("accepts null client_reference_id on response", () => {
    const result = InvokeResponse.parse({
      success: true,
      invocation_id: validInvocationId,
      client_reference_id: null,
    });
    expect(result.client_reference_id).toBeNull();
  });

  it("rejects client_reference_id longer than 256 chars on response", () => {
    const result = InvokeResponse.safeParse({
      success: true,
      invocation_id: validInvocationId,
      client_reference_id: "x".repeat(257),
    });
    expect(result.success).toBe(false);
  });
});
