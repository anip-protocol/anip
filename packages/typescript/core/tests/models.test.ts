import { describe, it, expect } from "vitest";
import {
  ANIPManifest,
  DelegationToken,
  TrustPosture,
  AnchoringPolicy,
  ANIPFailure,
  CapabilityDeclaration,
  PermissionResponse,
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
