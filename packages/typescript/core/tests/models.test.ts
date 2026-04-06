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
  ResponseMode,
  StreamSummary,
  AuditPosture,
  ClientReferenceIdPosture,
  LineagePosture,
  MetadataPolicy,
  FailureDisclosure,
  AnchoringPosture,
  DiscoveryPosture,
  EventClass,
  RetentionTier,
  DisclosureLevel,
  CheckpointDetailResponse,
  CrossServiceContract,
  CrossServiceContractEntry,
  RecoveryTarget,
  Resolution,
  ServiceCapabilityRef,
} from "../src/index.js";

describe("Protocol constants", () => {
  it("exports correct protocol version", () => {
    // Intentionally hardcoded — this is the one place that verifies the constant value.
    // Update this when bumping the protocol version.
    expect(PROTOCOL_VERSION).toBe("anip/0.21");
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
      resolution: { action: "request_broader_scope", recovery_class: "redelegation_then_retry" },
      retry: false,
    });
    expect(result.type).toBe("scope_insufficient");
  });
});

describe("ANIPManifest", () => {
  it("parses minimal manifest", () => {
    const result = ANIPManifest.safeParse({
      protocol: PROTOCOL_VERSION,
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

describe("ResponseMode", () => {
  it("accepts valid values", () => {
    expect(ResponseMode.parse("unary")).toBe("unary");
    expect(ResponseMode.parse("streaming")).toBe("streaming");
  });

  it("rejects invalid values", () => {
    expect(() => ResponseMode.parse("invalid")).toThrow();
  });
});

describe("StreamSummary", () => {
  it("parses a valid stream summary", () => {
    const ss = StreamSummary.parse({
      response_mode: "streaming",
      events_emitted: 5,
      events_delivered: 3,
      duration_ms: 1200,
      client_disconnected: true,
    });
    expect(ss.events_emitted).toBe(5);
    expect(ss.client_disconnected).toBe(true);
  });
});

describe("CapabilityDeclaration with response_modes", () => {
  it("defaults to unary", () => {
    const decl = CapabilityDeclaration.parse({
      name: "test", description: "Test", inputs: [],
      output: { type: "object", fields: [] },
      side_effect: { type: "read" }, minimum_scope: ["test"],
    });
    expect(decl.response_modes).toEqual(["unary"]);
  });

  it("accepts streaming", () => {
    const decl = CapabilityDeclaration.parse({
      name: "test", description: "Test", inputs: [],
      output: { type: "object", fields: [] },
      side_effect: { type: "read" }, minimum_scope: ["test"],
      response_modes: ["unary", "streaming"],
    });
    expect(decl.response_modes).toEqual(["unary", "streaming"]);
  });
});

describe("InvokeRequest with stream", () => {
  it("defaults stream to false", () => {
    const req = InvokeRequest.parse({ token: "jwt" });
    expect(req.stream).toBe(false);
  });

  it("accepts stream true", () => {
    const req = InvokeRequest.parse({ token: "jwt", stream: true });
    expect(req.stream).toBe(true);
  });
});

// --- Discovery Posture (v0.7) ---

describe("AuditPosture", () => {
  it("defaults to enabled, signed, queryable", () => {
    const ap = AuditPosture.parse({});
    expect(ap.enabled).toBe(true);
    expect(ap.signed).toBe(true);
    expect(ap.queryable).toBe(true);
    expect(ap.retention).toBe("P90D");
  });

  it("accepts custom retention", () => {
    const ap = AuditPosture.parse({ retention: "P365D" });
    expect(ap.retention).toBe("P365D");
  });
});

describe("ClientReferenceIdPosture", () => {
  it("defaults correctly", () => {
    const crp = ClientReferenceIdPosture.parse({});
    expect(crp.supported).toBe(true);
    expect(crp.max_length).toBe(256);
    expect(crp.opaque).toBe(true);
    expect(crp.propagation).toBe("bounded");
  });
});

describe("LineagePosture", () => {
  it("defaults correctly", () => {
    const lp = LineagePosture.parse({});
    expect(lp.invocation_id).toBe(true);
    expect(lp.client_reference_id.supported).toBe(true);
  });
});

describe("MetadataPolicy", () => {
  it("defaults correctly", () => {
    const mp = MetadataPolicy.parse({});
    expect(mp.bounded_lineage).toBe(true);
    expect(mp.freeform_context).toBe(false);
    expect(mp.downstream_propagation).toBe("minimal");
  });
});

describe("FailureDisclosure", () => {
  it("defaults to redacted", () => {
    const fd = FailureDisclosure.parse({});
    expect(fd.detail_level).toBe("redacted");
  });

  it("accepts full", () => {
    const fd = FailureDisclosure.parse({ detail_level: "full" });
    expect(fd.detail_level).toBe("full");
  });
});

describe("AnchoringPosture", () => {
  it("defaults to disabled", () => {
    const ap = AnchoringPosture.parse({});
    expect(ap.enabled).toBe(false);
    expect(ap.cadence).toBeNull();
    expect(ap.max_lag).toBeNull();
    expect(ap.proofs_available).toBe(false);
  });

  it("accepts enabled with config", () => {
    const ap = AnchoringPosture.parse({
      enabled: true,
      cadence: "PT30S",
      max_lag: 120,
      proofs_available: true,
    });
    expect(ap.enabled).toBe(true);
    expect(ap.cadence).toBe("PT30S");
    expect(ap.max_lag).toBe(120);
    expect(ap.proofs_available).toBe(true);
  });
});

describe("DiscoveryPosture", () => {
  it("defaults fully", () => {
    const dp = DiscoveryPosture.parse({});
    expect(dp.audit.enabled).toBe(true);
    expect(dp.lineage.invocation_id).toBe(true);
    expect(dp.metadata_policy.bounded_lineage).toBe(true);
    expect(dp.failure_disclosure.detail_level).toBe("redacted");
    expect(dp.anchoring.enabled).toBe(false);
  });

  it("roundtrips with anchoring", () => {
    const input = {
      anchoring: { enabled: true, cadence: "PT30S", max_lag: 120, proofs_available: true },
    };
    const dp = DiscoveryPosture.parse(input);
    expect(dp.anchoring.enabled).toBe(true);
    expect(dp.anchoring.cadence).toBe("PT30S");
  });
});

// --- v0.8 Security Hardening Enums ---

describe("EventClass", () => {
  it("parses all valid values", () => {
    const values = [
      "high_risk_success",
      "high_risk_denial",
      "low_risk_success",
      "repeated_low_value_denial",
      "malformed_or_spam",
    ];
    for (const v of values) {
      expect(EventClass.parse(v)).toBe(v);
    }
  });

  it("rejects invalid values", () => {
    expect(() => EventClass.parse("invalid")).toThrow();
  });
});

describe("RetentionTier", () => {
  it("parses all valid values", () => {
    const values = ["long", "medium", "short", "aggregate_only"];
    for (const v of values) {
      expect(RetentionTier.parse(v)).toBe(v);
    }
  });

  it("rejects invalid values", () => {
    expect(() => RetentionTier.parse("invalid")).toThrow();
  });
});

describe("DisclosureLevel", () => {
  it("parses all valid values", () => {
    const values = ["full", "reduced", "redacted"];
    for (const v of values) {
      expect(DisclosureLevel.parse(v)).toBe(v);
    }
  });

  it("rejects invalid values", () => {
    expect(() => DisclosureLevel.parse("invalid")).toThrow();
  });
});

describe("AuditPosture with retention_enforced", () => {
  it("defaults retention_enforced to false", () => {
    const ap = AuditPosture.parse({});
    expect(ap.retention_enforced).toBe(false);
  });

  it("accepts retention_enforced true", () => {
    const ap = AuditPosture.parse({ retention_enforced: true });
    expect(ap.retention_enforced).toBe(true);
  });
});

describe("FailureDisclosure with reduced", () => {
  it("accepts reduced detail_level", () => {
    const fd = FailureDisclosure.parse({ detail_level: "reduced" });
    expect(fd.detail_level).toBe("reduced");
  });
});

// --- CheckpointDetailResponse (v0.9) ---

describe("CheckpointDetailResponse", () => {
  it("defaults expires_hint to null", () => {
    const resp = CheckpointDetailResponse.parse({
      checkpoint: {
        service_id: "svc-1",
        checkpoint_id: "ckpt-1",
        range: { first_sequence: 1, last_sequence: 10 },
        merkle_root: "sha256:abc",
        timestamp: "2026-01-01T00:00:00Z",
        entry_count: 10,
      },
    });
    expect(resp.expires_hint).toBeNull();
  });

  it("accepts expires_hint", () => {
    const resp = CheckpointDetailResponse.parse({
      checkpoint: {
        service_id: "svc-1",
        checkpoint_id: "ckpt-1",
        range: { first_sequence: 1, last_sequence: 10 },
        merkle_root: "sha256:abc",
        timestamp: "2026-01-01T00:00:00Z",
        entry_count: 10,
      },
      expires_hint: "2026-04-01T00:00:00Z",
    });
    expect(resp.expires_hint).toBe("2026-04-01T00:00:00Z");
  });
});

// --- CrossServiceContract model round-trip (v0.21) ---

describe("CrossServiceContractEntry", () => {
  it("parses a valid entry with all fields", () => {
    const result = CrossServiceContractEntry.safeParse({
      target: { service: "booking-service", capability: "confirm_booking" },
      required_for_task_completion: true,
      continuity: "same_task",
      completion_mode: "downstream_acceptance",
    });
    expect(result.success).toBe(true);
    expect(result.data!.target.service).toBe("booking-service");
    expect(result.data!.required_for_task_completion).toBe(true);
    expect(result.data!.completion_mode).toBe("downstream_acceptance");
  });

  it("defaults required_for_task_completion to false", () => {
    const result = CrossServiceContractEntry.parse({
      target: { service: "svc", capability: "cap" },
      completion_mode: "followup_status",
    });
    expect(result.required_for_task_completion).toBe(false);
  });

  it("defaults continuity to same_task", () => {
    const result = CrossServiceContractEntry.parse({
      target: { service: "svc", capability: "cap" },
      completion_mode: "verification_result",
    });
    expect(result.continuity).toBe("same_task");
  });

  it("rejects invalid completion_mode", () => {
    const result = CrossServiceContractEntry.safeParse({
      target: { service: "svc", capability: "cap" },
      completion_mode: "invalid_mode",
    });
    expect(result.success).toBe(false);
  });
});

describe("CrossServiceContract", () => {
  it("defaults to empty arrays", () => {
    const contract = CrossServiceContract.parse({});
    expect(contract.handoff).toEqual([]);
    expect(contract.followup).toEqual([]);
    expect(contract.verification).toEqual([]);
  });

  it("roundtrips with handoff entry", () => {
    const input = {
      handoff: [
        {
          target: { service: "booking-service", capability: "confirm_booking" },
          required_for_task_completion: true,
          completion_mode: "downstream_acceptance",
        },
      ],
    };
    const contract = CrossServiceContract.parse(input);
    expect(contract.handoff).toHaveLength(1);
    expect(contract.handoff[0].target.service).toBe("booking-service");
    expect(contract.handoff[0].required_for_task_completion).toBe(true);
  });

  it("roundtrips with verification entry", () => {
    const contract = CrossServiceContract.parse({
      verification: [
        {
          target: { service: "verify-svc", capability: "verify_identity" },
          completion_mode: "verification_result",
        },
      ],
    });
    expect(contract.verification[0].completion_mode).toBe("verification_result");
  });
});

// --- RecoveryTarget model round-trip (v0.21) ---

describe("RecoveryTarget", () => {
  it("parses all valid kind values", () => {
    for (const kind of ["refresh", "redelegation", "revalidation", "escalation"] as const) {
      const rt = RecoveryTarget.parse({ kind });
      expect(rt.kind).toBe(kind);
    }
  });

  it("rejects invalid kind", () => {
    const result = RecoveryTarget.safeParse({ kind: "invalid_kind" });
    expect(result.success).toBe(false);
  });

  it("defaults continuity to same_task", () => {
    const rt = RecoveryTarget.parse({ kind: "refresh" });
    expect(rt.continuity).toBe("same_task");
  });

  it("defaults retry_after_target to false", () => {
    const rt = RecoveryTarget.parse({ kind: "refresh" });
    expect(rt.retry_after_target).toBe(false);
  });

  it("defaults target to null", () => {
    const rt = RecoveryTarget.parse({ kind: "escalation" });
    expect(rt.target).toBeNull();
  });

  it("roundtrips with target service ref", () => {
    const input = {
      kind: "refresh",
      target: { service: "auth-service", capability: "refresh_token" },
      continuity: "same_task",
      retry_after_target: true,
    };
    const rt = RecoveryTarget.parse(input);
    expect(rt.target?.service).toBe("auth-service");
    expect(rt.target?.capability).toBe("refresh_token");
    expect(rt.retry_after_target).toBe(true);
  });
});

// --- CapabilityDeclaration with cross_service_contract (v0.21) ---

describe("CapabilityDeclaration with cross_service_contract", () => {
  const baseDecl = {
    name: "search_flights",
    description: "Search for flights",
    inputs: [],
    output: { type: "object", fields: ["flights"] },
    side_effect: { type: "read" },
    minimum_scope: ["travel.search"],
  };

  it("defaults cross_service_contract to null", () => {
    const decl = CapabilityDeclaration.parse(baseDecl);
    expect(decl.cross_service_contract).toBeNull();
  });

  it("accepts cross_service_contract with handoff entries", () => {
    const decl = CapabilityDeclaration.parse({
      ...baseDecl,
      cross_service_contract: {
        handoff: [
          {
            target: { service: "booking-service", capability: "confirm_booking" },
            required_for_task_completion: true,
            completion_mode: "downstream_acceptance",
          },
        ],
      },
    });
    expect(decl.cross_service_contract).not.toBeNull();
    expect(decl.cross_service_contract!.handoff).toHaveLength(1);
    expect(decl.cross_service_contract!.handoff[0].target.service).toBe("booking-service");
    expect(decl.cross_service_contract!.handoff[0].required_for_task_completion).toBe(true);
  });
});

// --- Resolution with recovery_target (v0.21) ---

describe("Resolution with recovery_target", () => {
  it("defaults recovery_target to null", () => {
    const res = Resolution.parse({
      action: "request_broader_scope",
      recovery_class: "redelegation_then_retry",
    });
    expect(res.recovery_target).toBeNull();
  });

  it("roundtrips recovery_target", () => {
    const res = Resolution.parse({
      action: "refresh_token",
      recovery_class: "refresh_then_retry",
      recovery_target: {
        kind: "refresh",
        target: { service: "auth-service", capability: "refresh_token" },
        retry_after_target: true,
      },
    });
    expect(res.recovery_target).not.toBeNull();
    expect(res.recovery_target!.kind).toBe("refresh");
    expect(res.recovery_target!.target?.service).toBe("auth-service");
    expect(res.recovery_target!.retry_after_target).toBe(true);
  });
});

// --- ANIPFailure carries recovery_target through resolution (v0.21) ---

describe("ANIPFailure with recovery_target in resolution", () => {
  it("carries recovery_target end-to-end", () => {
    const failure = ANIPFailure.parse({
      type: "token_expired",
      detail: "Token has expired",
      resolution: {
        action: "refresh_token",
        recovery_class: "refresh_then_retry",
        recovery_target: {
          kind: "refresh",
          target: { service: "auth-service", capability: "refresh_token" },
          retry_after_target: true,
        },
      },
      retry: false,
    });
    expect(failure.resolution.recovery_target).not.toBeNull();
    expect(failure.resolution.recovery_target!.kind).toBe("refresh");
    expect(failure.resolution.recovery_target!.target?.service).toBe("auth-service");
  });
});
