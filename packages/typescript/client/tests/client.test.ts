import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  normalizeFailure,
  normalizePermissions,
  normalizeDiscovery,
  normalizeManifest,
  normalizeCapability,
  ANIPClient,
} from "../src/index.js";

// ---------------------------------------------------------------------------
// Failure normalization
// ---------------------------------------------------------------------------

describe("normalizeFailure", () => {
  it("marks scope_insufficient as permission-related and not retryable", () => {
    const result = normalizeFailure({
      type: "scope_insufficient",
      detail: "Missing travel.book scope",
      retry: false,
      resolution: {
        action: "request_broader_scope",
        recovery_class: "redelegation_then_retry",
        requires: "travel.book",
        grantable_by: "root",
      },
    });

    expect(result.type).toBe("scope_insufficient");
    expect(result.permissionRelated).toBe(true);
    expect(result.retryable).toBe(false);
    expect(result.recoveryClass).toBe("redelegation_then_retry");
    expect(result.resolution?.action).toBe("request_broader_scope");
    expect(result.resolution?.requires).toBe("travel.book");
    expect(result.resolution?.grantableBy).toBe("root");
    expect(result.displaySummary).toBe(
      "Additional permissions are required to perform this action.",
    );
  });

  it("marks rate_limited as retryable and not permission-related", () => {
    const result = normalizeFailure({
      type: "rate_limited",
      detail: "Too many requests",
      retry: true,
      resolution: {
        action: "retry_now",
        recovery_class: "retry_now",
      },
    });

    expect(result.retryable).toBe(true);
    expect(result.permissionRelated).toBe(false);
    expect(result.displaySummary).toBe(
      "Too many requests. Please wait and try again.",
    );
  });

  it("marks token_expired as permission-related", () => {
    const result = normalizeFailure({
      type: "token_expired",
      detail: "Token has expired",
      retry: false,
      resolution: {
        action: "refresh_token",
        recovery_class: "refresh_then_retry",
        recovery_target: {
          kind: "refresh",
          target: { service: "auth-service", capability: "refresh_token" },
          continuity: "same_task",
          retry_after_target: true,
        },
      },
    });

    expect(result.permissionRelated).toBe(true);
    expect(result.retryable).toBe(false);
    expect(result.recoveryTarget).toBeDefined();
    expect(result.recoveryTarget!.kind).toBe("refresh");
    expect(result.recoveryTarget!.target?.service).toBe("auth-service");
    expect(result.recoveryTarget!.target?.capability).toBe("refresh_token");
    expect(result.recoveryTarget!.retryAfterTarget).toBe(true);
    expect(result.recoveryTarget!.continuity).toBe("same_task");
  });

  it("uses wire retry field over type inference", () => {
    // rate_limited would normally be retryable, but wire says retry: false
    const result = normalizeFailure({
      type: "rate_limited",
      detail: "Permanently rate limited",
      retry: false,
      resolution: { action: "contact_service_owner", recovery_class: "terminal" },
    });
    expect(result.retryable).toBe(false);
  });

  it("infers retryable from type when retry field is absent", () => {
    const result = normalizeFailure({
      type: "temporary_unavailable",
      detail: "Service is down",
      resolution: { action: "retry_now", recovery_class: "retry_now" },
    });
    expect(result.retryable).toBe(true);
  });

  it("handles null/undefined input gracefully", () => {
    const result = normalizeFailure(null);
    expect(result.type).toBe("unknown");
    expect(result.retryable).toBe(false);
    expect(result.permissionRelated).toBe(false);
    expect(result.displaySummary).toBe("An unknown error occurred.");
  });

  it("handles unknown type with fallback display summary", () => {
    const result = normalizeFailure({
      type: "something_unexpected",
      detail: "Detailed error info here",
      resolution: { action: "retry_now", recovery_class: "retry_now" },
    });
    expect(result.type).toBe("something_unexpected");
    expect(result.displaySummary).toBe("Detailed error info here");
  });

  it("falls back to generic message when type unknown and detail empty", () => {
    const result = normalizeFailure({
      type: "something_unexpected",
      detail: "",
      resolution: { action: "retry_now", recovery_class: "retry_now" },
    });
    expect(result.displaySummary).toBe("An error occurred.");
  });

  it("marks delegation_depth_exceeded as permission-related", () => {
    const result = normalizeFailure({
      type: "delegation_depth_exceeded",
      detail: "Delegation chain too deep",
      resolution: {
        action: "escalate_to_root_principal",
        recovery_class: "terminal",
      },
    });
    expect(result.permissionRelated).toBe(true);
    expect(result.retryable).toBe(false);
  });

  it("marks budget_exceeded as permission-related", () => {
    const result = normalizeFailure({
      type: "budget_exceeded",
      detail: "Budget limit reached",
      resolution: {
        action: "request_budget_increase",
        recovery_class: "redelegation_then_retry",
      },
    });
    expect(result.permissionRelated).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Permission normalization
// ---------------------------------------------------------------------------

describe("normalizePermissions", () => {
  it("normalizes a full permission response", () => {
    const result = normalizePermissions({
      available: [
        { capability: "search_flights", scope_match: "travel.search" },
        { capability: "get_quote", scope_match: "travel.quote" },
      ],
      restricted: [
        {
          capability: "book_flight",
          reason: "Scope insufficient",
          reason_type: "scope_insufficient",
          grantable_by: "root",
          resolution_hint: "Request travel.book scope",
        },
      ],
      denied: [
        {
          capability: "admin_override",
          reason: "Non-delegable",
          reason_type: "non_delegable_action",
        },
      ],
    });

    expect(result.available).toEqual([
      { capability: "search_flights", scopeMatch: "travel.search" },
      { capability: "get_quote", scopeMatch: "travel.quote" },
    ]);
    expect(result.restricted).toHaveLength(1);
    expect(result.restricted[0].capability).toBe("book_flight");
    expect(result.restricted[0].reason).toBe("Scope insufficient");
    expect(result.restricted[0].reasonType).toBe("scope_insufficient");
    expect(result.restricted[0].grantableBy).toBe("root");
    expect(result.restricted[0].resolutionHint).toBe("Request travel.book scope");
    expect(result.denied).toHaveLength(1);
    expect(result.denied[0].capability).toBe("admin_override");
    expect(result.denied[0].reason).toBe("Non-delegable");
    expect(result.denied[0].reasonType).toBe("non_delegable_action");
  });

  it("handles empty arrays", () => {
    const result = normalizePermissions({
      available: [],
      restricted: [],
      denied: [],
    });
    expect(result.available).toEqual([]);
    expect(result.restricted).toEqual([]);
    expect(result.denied).toEqual([]);
  });

  it("handles null input", () => {
    const result = normalizePermissions(null);
    expect(result.available).toEqual([]);
    expect(result.restricted).toEqual([]);
    expect(result.denied).toEqual([]);
  });

  it("handles missing arrays gracefully", () => {
    const result = normalizePermissions({ available: [{ capability: "cap1" }] });
    expect(result.available).toEqual([{ capability: "cap1", scopeMatch: undefined }]);
    expect(result.restricted).toEqual([]);
    expect(result.denied).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Discovery normalization
// ---------------------------------------------------------------------------

describe("normalizeDiscovery", () => {
  it("normalizes a full discovery document", () => {
    const result = normalizeDiscovery({
      protocol: "anip/0.22",
      compliance: "full",
      trust: { level: "signed" },
      endpoints: {
        manifest: "/anip/manifest",
        invoke: "/anip/invoke/{capability}",
        permissions: "/anip/permissions",
        token: "/anip/token",
        audit: "/anip/audit",
        graph: "/anip/graph/{capability}",
        checkpoints: "/anip/checkpoints",
      },
      profiles: { core: "1.0", cost: "1.0" },
      capabilities: ["search_flights", "book_flight"],
    });

    expect(result.protocol).toBe("anip/0.22");
    expect(result.compliance).toBe("full");
    expect(result.trustLevel).toBe("signed");
    expect(result.endpoints.manifest).toBe("/anip/manifest");
    expect(result.endpoints.invoke).toBe("/anip/invoke/{capability}");
    expect(result.profiles.core).toBe("1.0");
    expect(result.capabilityNames).toEqual(["search_flights", "book_flight"]);
    expect(Object.keys(result.capabilities)).toEqual(["search_flights", "book_flight"]);
  });

  it("handles missing trust level", () => {
    const result = normalizeDiscovery({
      protocol: "anip/0.22",
      compliance: "full",
      endpoints: {},
      capabilities: [],
    });
    expect(result.trustLevel).toBeUndefined();
  });

  it("handles null input", () => {
    const result = normalizeDiscovery(null);
    expect(result.protocol).toBe("unknown");
    expect(result.compliance).toBe("unknown");
    expect(result.endpoints).toEqual({});
    expect(result.capabilityNames).toEqual([]);
    expect(result.capabilities).toEqual({});
  });

  it("accepts profile (singular) as fallback for profiles", () => {
    const result = normalizeDiscovery({
      protocol: "anip/0.22",
      compliance: "full",
      profile: { core: "1.0" },
      endpoints: {},
      capabilities: [],
    });
    expect(result.profiles.core).toBe("1.0");
  });
});

// ---------------------------------------------------------------------------
// Manifest normalization
// ---------------------------------------------------------------------------

describe("normalizeManifest", () => {
  it("normalizes a manifest with capabilities", () => {
    const result = normalizeManifest({
      protocol: "anip/0.22",
      manifest_metadata: { version: "1", sha256: "abc" },
      service_identity: { id: "svc", jwks_uri: "/jwks", issuer_mode: "self" },
      trust: { level: "signed" },
      profile: { core: "1.0" },
      capabilities: {
        search_flights: {
          name: "search_flights",
          description: "Search for flights",
          minimum_scope: ["travel.search"],
          side_effect: { type: "read", rollback_window: null },
          response_modes: ["unary"],
          inputs: [],
          output: { type: "object", fields: ["flights"] },
          cost: {
            certainty: "fixed",
            financial: { currency: "USD", amount: 0.01 },
          },
        },
        book_flight: {
          name: "book_flight",
          description: "Book a flight",
          minimum_scope: ["travel.book"],
          side_effect: { type: "write", rollback_window: "PT24H" },
          response_modes: ["unary", "streaming"],
          inputs: [],
          output: { type: "object", fields: ["booking"] },
          control_requirements: [{ type: "cost_ceiling", enforcement: "reject" }],
          requires: [{ capability: "get_quote", reason: "Need a quote first" }],
          composes_with: [{ capability: "search_flights", optional: true }],
          cross_service_contract: {
            handoff: [
              {
                target: { service: "booking-service", capability: "confirm_booking" },
                required_for_task_completion: true,
                completion_mode: "downstream_acceptance",
              },
            ],
          },
        },
      },
    });

    expect(result.protocol).toBe("anip/0.22");
    expect(result.manifestMetadata?.version).toBe("1");
    expect(result.serviceIdentity?.id).toBe("svc");
    expect(result.trust?.level).toBe("signed");
    expect(Object.keys(result.capabilities)).toHaveLength(2);

    const search = result.capabilities.search_flights;
    expect(search.name).toBe("search_flights");
    expect(search.minimumScope).toEqual(["travel.search"]);
    expect(search.sideEffect.type).toBe("read");
    expect(search.responseModes).toEqual(["unary"]);
    expect(search.cost?.financial?.currency).toBe("USD");
    expect(search.cost?.financial?.estimatedAmount).toBe(0.01);
    expect(search.raw.name).toBe("search_flights");

    const book = result.capabilities.book_flight;
    expect(book.sideEffect.type).toBe("write");
    expect(book.sideEffect.rollbackWindow).toBe("PT24H");
    expect(book.responseModes).toEqual(["unary", "streaming"]);
    expect(book.contractVersion).toBeUndefined();
    expect(book.inputs).toEqual([]);
    expect(book.controlRequirements).toHaveLength(1);
    expect(book.controlRequirements![0].type).toBe("cost_ceiling");
    expect(book.graph?.requires).toHaveLength(1);
    expect(book.graph?.requires![0].capability).toBe("get_quote");
    expect(book.graph?.composesWith).toHaveLength(1);
    expect(book.graph?.composesWith![0].capability).toBe("search_flights");
    expect(book.crossServiceContract?.handoff).toHaveLength(1);
    expect(book.crossServiceContract!.handoff![0].service).toBe("booking-service");
    expect(book.crossServiceContract!.handoff![0].requiredForTaskCompletion).toBe(true);
  });

  it("handles null input", () => {
    const result = normalizeManifest(null);
    expect(result.protocol).toBe("unknown");
    expect(result.capabilities).toEqual({});
    expect(result.raw).toEqual({});
  });

  it("handles empty capabilities", () => {
    const result = normalizeManifest({
      protocol: "anip/0.22",
      capabilities: {},
    });
    expect(Object.keys(result.capabilities)).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// normalizeCapability — individual capability normalization
// ---------------------------------------------------------------------------

describe("normalizeCapability", () => {
  it("defaults response_modes to [unary] when absent", () => {
    const cap = normalizeCapability("test_cap", {
      description: "Test",
      minimum_scope: ["test"],
      side_effect: { type: "read" },
    });
    expect(cap.responseModes).toEqual(["unary"]);
  });

  it("uses estimated cost fields (typical, range_max, upper_bound) as fallback", () => {
    const cap = normalizeCapability("test_cap", {
      description: "Test",
      minimum_scope: [],
      side_effect: { type: "read" },
      cost: {
        certainty: "estimated",
        financial: { currency: "EUR", typical: 5.0, range_max: 10.0 },
      },
    });
    expect(cap.cost?.financial?.currency).toBe("EUR");
    expect(cap.cost?.financial?.estimatedAmount).toBe(5.0);
  });
});

// ---------------------------------------------------------------------------
// Token response normalization (via ANIPClient with mocked fetch)
// ---------------------------------------------------------------------------

describe("ANIPClient token issuance", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("normalizes token response with task_id", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        issued: true,
        token_id: "tok-abc123",
        token: "eyJhbGciOiJFUzI1NiJ9.test.sig",
        expires: "2026-12-31T23:59:59Z",
        task_id: "task-001",
        budget: { currency: "USD", max_amount: 100 },
      }),
    } as Response);

    const client = new ANIPClient("https://example.com");
    const result = await client.issueToken("api-key", {
      scope: ["travel.search"],
      capability: "search_flights",
      subject: "agent-1",
    });

    expect(result.issued).toBe(true);
    expect(result.tokenId).toBe("tok-abc123");
    expect(result.token).toBe("eyJhbGciOiJFUzI1NiJ9.test.sig");
    expect(result.expires).toBe("2026-12-31T23:59:59Z");
    expect(result.taskId).toBe("task-001");
    expect(result.budget?.currency).toBe("USD");
    expect(result.budget?.maxAmount).toBe(100);
  });

  it("normalizes token response without task_id", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        issued: true,
        token_id: "tok-def456",
        token: "jwt-string",
        expires: "2026-06-01T00:00:00Z",
      }),
    } as Response);

    const client = new ANIPClient("https://example.com");
    const result = await client.issueToken("api-key", {
      scope: ["travel.search"],
    });

    expect(result.issued).toBe(true);
    expect(result.taskId).toBeUndefined();
    expect(result.budget).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// ANIPClient invocation normalization
// ---------------------------------------------------------------------------

describe("ANIPClient invoke", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("normalizes a successful invocation result", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        invocation_id: "inv-0123456789ab",
        task_id: "task-001",
        result: { flights: [{ id: "fl-1" }] },
        budget_context: {
          budget_max: 100,
          budget_currency: "USD",
          cost_check_amount: 0.01,
        },
      }),
    } as Response);

    const client = new ANIPClient("https://example.com");
    const result = await client.invoke("token", "search_flights", { origin: "SFO" });

    expect(result.success).toBe(true);
    expect(result.invocationId).toBe("inv-0123456789ab");
    expect(result.taskId).toBe("task-001");
    expect(result.result?.flights).toBeDefined();
    expect(result.budgetContext?.budgetMax).toBe(100);
    expect(result.budgetContext?.budgetCurrency).toBe("USD");
    expect(result.budgetContext?.costCheckAmount).toBe(0.01);
  });

  it("normalizes a failed invocation with failure details", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: false,
        invocation_id: "inv-abcdef012345",
        failure: {
          type: "scope_insufficient",
          detail: "Missing travel.book",
          retry: false,
          resolution: {
            action: "request_broader_scope",
            recovery_class: "redelegation_then_retry",
            requires: "travel.book",
            grantable_by: "root",
          },
        },
      }),
    } as Response);

    const client = new ANIPClient("https://example.com");
    const result = await client.invoke("token", "book_flight", { flightId: "fl-1" });

    expect(result.success).toBe(false);
    expect(result.failure).toBeDefined();
    expect(result.failure!.type).toBe("scope_insufficient");
    expect(result.failure!.permissionRelated).toBe(true);
    expect(result.failure!.retryable).toBe(false);
    expect(result.failure!.resolution?.action).toBe("request_broader_scope");
  });

  it("throws on HTTP error responses", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      text: async () => "server error body",
    } as Response);

    const client = new ANIPClient("https://example.com");
    await expect(
      client.invoke("token", "search_flights", {}),
    ).rejects.toThrow("ANIP request failed: 500 Internal Server Error");
  });
});

// ---------------------------------------------------------------------------
// ANIPClient discovery integration
// ---------------------------------------------------------------------------

describe("ANIPClient discover", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("loads discovery and caches endpoints for later use", async () => {
    const fetchSpy = vi.fn();

    // First call: discovery
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        protocol: "anip/0.22",
        compliance: "full",
        trust: { level: "signed" },
        endpoints: {
          manifest: "/custom/manifest",
          invoke: "/custom/invoke/{capability}",
        },
        capabilities: ["search_flights"],
      }),
    } as Response);

    // Second call: manifest (should use discovered endpoint)
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        protocol: "anip/0.22",
        capabilities: {},
      }),
    } as Response);

    globalThis.fetch = fetchSpy;

    const client = new ANIPClient("https://example.com");
    const disc = await client.discover();
    expect(disc.protocol).toBe("anip/0.22");
    expect(disc.capabilityNames).toEqual(["search_flights"]);

    const manifest = await client.getManifest();
    expect(manifest.signature).toBeUndefined();

    // Verify the manifest request used the discovered custom path
    const manifestCall = fetchSpy.mock.calls[1];
    expect(manifestCall[0]).toBe("https://example.com/custom/manifest");
  });

  it("captures manifest signature headers", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          protocol: "anip/0.22",
          compliance: "full",
          endpoints: { manifest: "/anip/manifest" },
          capabilities: [],
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        headers: new Headers({ "X-ANIP-Signature": "sig-123" }),
        json: async () => ({
          protocol: "anip/0.22",
          capabilities: {},
        }),
      } as Response);

    const client = new ANIPClient("https://example.com");
    await client.discover();
    const manifest = await client.getManifest();
    expect(manifest.signature).toBe("sig-123");
  });
});

// ---------------------------------------------------------------------------
// ANIPClient getCapability
// ---------------------------------------------------------------------------

describe("ANIPClient getCapability", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("returns null before manifest is loaded", () => {
    const client = new ANIPClient("https://example.com");
    expect(client.getCapability("search_flights")).toBeNull();
  });

  it("returns capability after manifest is loaded", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        protocol: "anip/0.22",
        capabilities: {
          search_flights: {
            name: "search_flights",
            description: "Search for flights",
            minimum_scope: ["travel.search"],
            side_effect: { type: "read" },
            response_modes: ["unary"],
          },
        },
      }),
    } as Response);

    const client = new ANIPClient("https://example.com");
    await client.getManifest();

    const cap = client.getCapability("search_flights");
    expect(cap).not.toBeNull();
    expect(cap!.name).toBe("search_flights");
    expect(cap!.minimumScope).toEqual(["travel.search"]);
  });

  it("returns null for unknown capability", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        protocol: "anip/0.22",
        capabilities: {},
      }),
    } as Response);

    const client = new ANIPClient("https://example.com");
    await client.getManifest();
    expect(client.getCapability("nonexistent")).toBeNull();
  });
});
