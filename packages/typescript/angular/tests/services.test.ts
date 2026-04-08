import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ANIPClient } from "@anip-dev/client";
import type {
  NormalizedDiscovery,
  NormalizedManifest,
  NormalizedCapability,
  NormalizedPermissions,
  NormalizedInvocationResult,
  NormalizedAuditResult,
} from "@anip-dev/client";

import {
  AnipClientService,
  AnipDiscoveryService,
  AnipManifestService,
  AnipCapabilityService,
  AnipPermissionsService,
  AnipInvokeService,
  AnipAuditService,
  AnipFailureService,
} from "../src/services.js";

// ---------------------------------------------------------------------------
// Mock client factory — patches the ANIPClient returned by the service
// ---------------------------------------------------------------------------

function patchClient(
  service: AnipClientService,
  overrides: Partial<ANIPClient>,
): void {
  const client = service.client;
  for (const [key, value] of Object.entries(overrides)) {
    (client as any)[key] = value;
  }
}

// ---------------------------------------------------------------------------
// AnipClientService
// ---------------------------------------------------------------------------

describe("AnipClientService", () => {
  it("creates an ANIPClient with the given base URL", () => {
    const service = new AnipClientService("https://api.example.com");
    expect(service.client).toBeDefined();
    expect(typeof service.client.discover).toBe("function");
    expect(typeof service.client.invoke).toBe("function");
  });

  it("supports setBaseUrl for dynamic service switching", () => {
    const service = new AnipClientService("https://api.example.com");
    // Should not throw
    service.setBaseUrl("https://other.example.com");
  });

  it("creates client with timeout option", () => {
    const service = new AnipClientService("https://api.example.com", 5000);
    expect(service.client).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// AnipDiscoveryService
// ---------------------------------------------------------------------------

describe("AnipDiscoveryService", () => {
  let clientService: AnipClientService;

  beforeEach(() => {
    clientService = new AnipClientService("https://api.example.com");
  });

  it("starts with null data, false loading, null error", () => {
    const service = new AnipDiscoveryService(clientService);
    expect(service.data()).toBeNull();
    expect(service.loading()).toBe(false);
    expect(service.error()).toBeNull();
  });

  it("transitions loading -> data on success", async () => {
    const discoveryDoc: NormalizedDiscovery = {
      protocol: "anip/0.22",
      compliance: "full",
      trustLevel: "signed",
      endpoints: { manifest: "/anip/manifest" },
      profiles: { core: "1.0" },
      capabilityNames: ["search_flights"],
      capabilities: {},
      raw: {},
    };
    patchClient(clientService, {
      discover: vi.fn().mockResolvedValue(discoveryDoc),
    });

    const service = new AnipDiscoveryService(clientService);

    const promise = service.load();
    expect(service.loading()).toBe(true);

    await promise;

    expect(service.loading()).toBe(false);
    expect(service.error()).toBeNull();
    expect(service.data()).toEqual(discoveryDoc);
  });

  it("transitions loading -> error on failure", async () => {
    patchClient(clientService, {
      discover: vi.fn().mockRejectedValue(new Error("Network error")),
    });

    const service = new AnipDiscoveryService(clientService);
    await service.load();

    expect(service.loading()).toBe(false);
    expect(service.error()).toBe("Network error");
    expect(service.data()).toBeNull();
  });

  it("clears stale data on error", async () => {
    const discoveryDoc: NormalizedDiscovery = {
      protocol: "anip/0.22",
      compliance: "full",
      endpoints: {},
      profiles: {},
      capabilityNames: [],
      capabilities: {},
      raw: {},
    };

    let callCount = 0;
    patchClient(clientService, {
      discover: vi.fn().mockImplementation(async () => {
        callCount++;
        if (callCount === 1) return discoveryDoc;
        throw new Error("Second failure");
      }),
    });

    const service = new AnipDiscoveryService(clientService);

    await service.load();
    expect(service.data()).toEqual(discoveryDoc);

    await service.load();
    expect(service.data()).toBeNull();
    expect(service.error()).toBe("Second failure");
  });

  it("clears previous error on reload", async () => {
    let callCount = 0;
    const discoveryDoc: NormalizedDiscovery = {
      protocol: "anip/0.22",
      compliance: "full",
      endpoints: {},
      profiles: {},
      capabilityNames: [],
      capabilities: {},
      raw: {},
    };
    patchClient(clientService, {
      discover: vi.fn().mockImplementation(async () => {
        callCount++;
        if (callCount === 1) throw new Error("First failure");
        return discoveryDoc;
      }),
    });

    const service = new AnipDiscoveryService(clientService);

    await service.load();
    expect(service.error()).toBe("First failure");

    await service.load();
    expect(service.error()).toBeNull();
    expect(service.data()).toEqual(discoveryDoc);
  });
});

// ---------------------------------------------------------------------------
// AnipManifestService
// ---------------------------------------------------------------------------

describe("AnipManifestService", () => {
  let clientService: AnipClientService;

  beforeEach(() => {
    clientService = new AnipClientService("https://api.example.com");
  });

  it("transitions loading -> data on success", async () => {
    const manifestDoc: NormalizedManifest = {
      protocol: "anip/0.22",
      capabilities: {
        search_flights: {
          name: "search_flights",
          description: "Search for flights",
          minimumScope: ["travel.search"],
          sideEffect: { type: "read" },
          responseModes: ["unary"],
          raw: {},
        },
      },
      raw: {},
    };
    patchClient(clientService, {
      getManifest: vi.fn().mockResolvedValue(manifestDoc),
    });

    const service = new AnipManifestService(clientService);
    await service.load();

    expect(service.loading()).toBe(false);
    expect(service.error()).toBeNull();
    expect(service.data()).toEqual(manifestDoc);
  });

  it("transitions loading -> error on failure", async () => {
    patchClient(clientService, {
      getManifest: vi
        .fn()
        .mockRejectedValue(new Error("Manifest fetch error")),
    });

    const service = new AnipManifestService(clientService);
    await service.load();

    expect(service.error()).toBe("Manifest fetch error");
    expect(service.data()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// AnipCapabilityService
// ---------------------------------------------------------------------------

describe("AnipCapabilityService", () => {
  let clientService: AnipClientService;

  beforeEach(() => {
    clientService = new AnipClientService("https://api.example.com");
  });

  it("returns null when manifest not loaded", () => {
    patchClient(clientService, {
      getCapability: vi.fn().mockReturnValue(null),
    });

    const service = new AnipCapabilityService(clientService);
    service.resolve("search_flights");
    expect(service.data()).toBeNull();
  });

  it("resolves capability from cached manifest", () => {
    const cap: NormalizedCapability = {
      name: "search_flights",
      description: "Search for flights",
      minimumScope: ["travel.search"],
      sideEffect: { type: "read" },
      responseModes: ["unary"],
      raw: {},
    };
    patchClient(clientService, {
      getCapability: vi.fn().mockReturnValue(cap),
    });

    const service = new AnipCapabilityService(clientService);
    service.resolve("search_flights");
    expect(service.data()).toEqual(cap);
  });

  it("re-resolves after manifest load via resolveFromManifest()", () => {
    let loaded = false;
    const cap: NormalizedCapability = {
      name: "search_flights",
      description: "Search for flights",
      minimumScope: ["travel.search"],
      sideEffect: { type: "read" },
      responseModes: ["unary"],
      raw: {},
    };
    patchClient(clientService, {
      getCapability: vi
        .fn()
        .mockImplementation(() => (loaded ? cap : null)),
    });

    const service = new AnipCapabilityService(clientService);
    service.resolve("search_flights");
    expect(service.data()).toBeNull();

    loaded = true;
    service.resolveFromManifest();
    expect(service.data()).toEqual(cap);
  });
});

// ---------------------------------------------------------------------------
// AnipPermissionsService
// ---------------------------------------------------------------------------

describe("AnipPermissionsService", () => {
  let clientService: AnipClientService;

  beforeEach(() => {
    clientService = new AnipClientService("https://api.example.com");
  });

  it("queries permissions and updates state", async () => {
    const perms: NormalizedPermissions = {
      available: [{ capability: "search_flights" }],
      restricted: [
        { capability: "book_flight", reasonType: "scope_insufficient" },
      ],
      denied: [],
    };
    patchClient(clientService, {
      queryPermissions: vi.fn().mockResolvedValue(perms),
    });

    const service = new AnipPermissionsService(clientService);
    await service.query("test-token");

    expect(service.loading()).toBe(false);
    expect(service.error()).toBeNull();
    expect(service.data()).toEqual(perms);
  });

  it("sets error on query failure", async () => {
    patchClient(clientService, {
      queryPermissions: vi
        .fn()
        .mockRejectedValue(new Error("Auth failed")),
    });

    const service = new AnipPermissionsService(clientService);
    await service.query("bad-token");

    expect(service.error()).toBe("Auth failed");
    expect(service.data()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// AnipInvokeService
// ---------------------------------------------------------------------------

describe("AnipInvokeService", () => {
  let clientService: AnipClientService;

  beforeEach(() => {
    clientService = new AnipClientService("https://api.example.com");
  });

  it("transitions loading -> result on success", async () => {
    const invocationResult: NormalizedInvocationResult = {
      success: true,
      invocationId: "inv-001",
      taskId: "task-001",
      result: { flights: [{ id: "fl-1" }] },
    };
    patchClient(clientService, {
      invoke: vi.fn().mockResolvedValue(invocationResult),
    });

    const service = new AnipInvokeService(clientService);
    expect(service.result()).toBeNull();

    await service.invoke("token", "search_flights", { origin: "SFO" });

    expect(service.loading()).toBe(false);
    expect(service.error()).toBeNull();
    expect(service.result()).toEqual(invocationResult);
  });

  it("passes opts through to client.invoke", async () => {
    const invocationResult: NormalizedInvocationResult = {
      success: true,
      invocationId: "inv-002",
    };
    const mockInvoke = vi.fn().mockResolvedValue(invocationResult);
    patchClient(clientService, { invoke: mockInvoke });

    const service = new AnipInvokeService(clientService);
    await service.invoke("token", "search_flights", {}, {
      taskId: "task-001",
      parentInvocationId: "inv-000",
      clientReferenceId: "ref-abc",
    });

    expect(mockInvoke).toHaveBeenCalledWith("token", "search_flights", {}, {
      taskId: "task-001",
      parentInvocationId: "inv-000",
      clientReferenceId: "ref-abc",
    });
  });

  it("transitions loading -> error on failure and clears stale result", async () => {
    const invocationResult: NormalizedInvocationResult = {
      success: true,
      invocationId: "inv-001",
      result: { flights: [] },
    };

    let callCount = 0;
    patchClient(clientService, {
      invoke: vi.fn().mockImplementation(async () => {
        callCount++;
        if (callCount === 1) return invocationResult;
        throw new Error("Invoke failed");
      }),
    });

    const service = new AnipInvokeService(clientService);

    await service.invoke("token", "search_flights", {});
    expect(service.result()).toEqual(invocationResult);

    await service.invoke("token", "search_flights", {});
    expect(service.error()).toBe("Invoke failed");
    expect(service.result()).toBeNull();
  });

  it("clears state via clear()", async () => {
    const invocationResult: NormalizedInvocationResult = {
      success: true,
      invocationId: "inv-001",
    };
    patchClient(clientService, {
      invoke: vi.fn().mockResolvedValue(invocationResult),
    });

    const service = new AnipInvokeService(clientService);
    await service.invoke("token", "search_flights", {});
    expect(service.result()).not.toBeNull();

    service.clear();
    expect(service.result()).toBeNull();
    expect(service.error()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// AnipAuditService
// ---------------------------------------------------------------------------

describe("AnipAuditService", () => {
  let clientService: AnipClientService;

  beforeEach(() => {
    clientService = new AnipClientService("https://api.example.com");
  });

  it("queries audit and updates state", async () => {
    const auditResult: NormalizedAuditResult = {
      entries: [{ invocation_id: "inv-001", event: "invoke" }],
      count: 1,
    };
    const mockQueryAudit = vi.fn().mockResolvedValue(auditResult);
    patchClient(clientService, { queryAudit: mockQueryAudit });

    const service = new AnipAuditService(clientService);
    await service.query("token", { capability: "search_flights", limit: 10 });

    expect(service.loading()).toBe(false);
    expect(service.error()).toBeNull();
    expect(service.data()).toEqual(auditResult);
    expect(mockQueryAudit).toHaveBeenCalledWith("token", {
      capability: "search_flights",
      limit: 10,
    });
  });

  it("sets error on audit query failure", async () => {
    patchClient(clientService, {
      queryAudit: vi.fn().mockRejectedValue(new Error("Audit error")),
    });

    const service = new AnipAuditService(clientService);
    await service.query("token");

    expect(service.error()).toBe("Audit error");
    expect(service.data()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// AnipFailureService
// ---------------------------------------------------------------------------

describe("AnipFailureService", () => {
  it("starts with null failure", () => {
    const service = new AnipFailureService();
    expect(service.failure()).toBeNull();
  });

  it("extracts failure from invocation result", () => {
    const service = new AnipFailureService();

    service.setFromResult({
      success: false,
      invocationId: "inv-001",
      failure: {
        type: "scope_insufficient",
        detail: "Missing travel.book",
        retryable: false,
        permissionRelated: true,
        displaySummary: "Additional permissions are required.",
      },
    });

    expect(service.failure()).toBeDefined();
    expect(service.failure()!.type).toBe("scope_insufficient");
    expect(service.failure()!.permissionRelated).toBe(true);
  });

  it("sets null when result has no failure", () => {
    const service = new AnipFailureService();

    // First set a failure
    service.setFromResult({
      success: false,
      invocationId: "inv-001",
      failure: {
        type: "scope_insufficient",
        detail: "Missing scope",
        retryable: false,
        permissionRelated: true,
        displaySummary: "Error",
      },
    });
    expect(service.failure()).not.toBeNull();

    // Then set a successful result — failure should be cleared
    service.setFromResult({
      success: true,
      invocationId: "inv-002",
    });
    expect(service.failure()).toBeNull();
  });

  it("clears failure explicitly", () => {
    const service = new AnipFailureService();

    service.setFromResult({
      success: false,
      invocationId: "inv-001",
      failure: {
        type: "rate_limited",
        detail: "Too many requests",
        retryable: true,
        permissionRelated: false,
        displaySummary: "Rate limited.",
      },
    });
    expect(service.failure()).not.toBeNull();

    service.clear();
    expect(service.failure()).toBeNull();
  });
});
