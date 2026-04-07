import { describe, it, expect, vi, beforeEach } from "vitest";
import { AnipClientKey } from "../src/plugin.js";
import {
  useAnipClient,
  useAnipDiscovery,
  useAnipManifest,
  useAnipPermissions,
  useAnipCapability,
  useAnipInvoke,
  useAnipAudit,
  useAnipFailure,
} from "../src/composables.js";
import { createAnipPlugin } from "../src/plugin.js";
import type { ANIPClient } from "@anip-dev/client";
import type {
  NormalizedDiscovery,
  NormalizedManifest,
  NormalizedCapability,
  NormalizedPermissions,
  NormalizedInvocationResult,
  NormalizedAuditResult,
} from "@anip-dev/client";

// ---------------------------------------------------------------------------
// Mock vue — intercept inject() so we can control what the composables see
// ---------------------------------------------------------------------------

let injectReturnValue: ANIPClient | undefined;

vi.mock("vue", async (importOriginal) => {
  const actual = await importOriginal<typeof import("vue")>();
  return {
    ...actual,
    inject: (key: any) => {
      if (key === AnipClientKey) return injectReturnValue;
      return undefined;
    },
  };
});

// ---------------------------------------------------------------------------
// Mock client factory
// ---------------------------------------------------------------------------

function createMockClient(overrides: Partial<ANIPClient> = {}): ANIPClient {
  return {
    discover: vi.fn(),
    getManifest: vi.fn(),
    getCapability: vi.fn().mockReturnValue(null),
    queryPermissions: vi.fn(),
    issueToken: vi.fn(),
    issueCapabilityToken: vi.fn(),
    issueDelegatedCapabilityToken: vi.fn(),
    invoke: vi.fn(),
    queryAudit: vi.fn(),
    getCapabilityGraph: vi.fn(),
    getCheckpoints: vi.fn(),
    ...overrides,
  } as unknown as ANIPClient;
}

// ---------------------------------------------------------------------------
// Plugin
// ---------------------------------------------------------------------------

describe("createAnipPlugin", () => {
  it("creates a plugin that provides the ANIPClient", () => {
    const plugin = createAnipPlugin("https://example.com", { timeout: 5000 });
    const provideSpy = vi.fn();
    const mockApp = { provide: provideSpy } as any;

    plugin.install(mockApp);

    expect(provideSpy).toHaveBeenCalledTimes(1);
    expect(provideSpy.mock.calls[0][0]).toBe(AnipClientKey);
    // The provided value should be an ANIPClient instance
    const providedClient = provideSpy.mock.calls[0][1];
    expect(providedClient).toBeDefined();
    expect(typeof providedClient.discover).toBe("function");
    expect(typeof providedClient.invoke).toBe("function");
  });
});

// ---------------------------------------------------------------------------
// useAnipClient
// ---------------------------------------------------------------------------

describe("useAnipClient", () => {
  beforeEach(() => {
    injectReturnValue = undefined;
  });

  it("returns the injected client", () => {
    const mock = createMockClient();
    injectReturnValue = mock;
    expect(useAnipClient()).toBe(mock);
  });

  it("throws when no client is provided", () => {
    injectReturnValue = undefined;
    expect(() => useAnipClient()).toThrow(
      "ANIPClient not provided. Did you install the ANIP plugin?",
    );
  });
});

// ---------------------------------------------------------------------------
// useAnipDiscovery
// ---------------------------------------------------------------------------

describe("useAnipDiscovery", () => {
  beforeEach(() => {
    injectReturnValue = undefined;
  });

  it("transitions loading -> data on success", async () => {
    const discoveryDoc: NormalizedDiscovery = {
      protocol: "anip/0.22",
      compliance: "full",
      trustLevel: "signed",
      endpoints: { manifest: "/anip/manifest" },
      profiles: { core: "1.0" },
      capabilities: ["search_flights"],
    };
    const mock = createMockClient({
      discover: vi.fn().mockResolvedValue(discoveryDoc),
    });
    injectReturnValue = mock;

    const { data, loading, error, load } = useAnipDiscovery();

    expect(data.value).toBeNull();
    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();

    const promise = load();
    expect(loading.value).toBe(true);

    await promise;

    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();
    expect(data.value).toEqual(discoveryDoc);
  });

  it("transitions loading -> error on failure", async () => {
    const mock = createMockClient({
      discover: vi.fn().mockRejectedValue(new Error("Network error")),
    });
    injectReturnValue = mock;

    const { data, loading, error, load } = useAnipDiscovery();

    await load();

    expect(loading.value).toBe(false);
    expect(error.value).toBe("Network error");
    expect(data.value).toBeNull();
  });

  it("clears previous error on reload", async () => {
    let callCount = 0;
    const discoveryDoc: NormalizedDiscovery = {
      protocol: "anip/0.22",
      compliance: "full",
      endpoints: {},
      profiles: {},
      capabilities: [],
    };
    const mock = createMockClient({
      discover: vi.fn().mockImplementation(async () => {
        callCount++;
        if (callCount === 1) throw new Error("First failure");
        return discoveryDoc;
      }),
    });
    injectReturnValue = mock;

    const { data, error, load } = useAnipDiscovery();

    await load();
    expect(error.value).toBe("First failure");

    await load();
    expect(error.value).toBeNull();
    expect(data.value).toEqual(discoveryDoc);
  });
});

// ---------------------------------------------------------------------------
// useAnipManifest
// ---------------------------------------------------------------------------

describe("useAnipManifest", () => {
  beforeEach(() => {
    injectReturnValue = undefined;
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
        },
      },
    };
    const mock = createMockClient({
      getManifest: vi.fn().mockResolvedValue(manifestDoc),
    });
    injectReturnValue = mock;

    const { data, loading, error, load } = useAnipManifest();

    expect(data.value).toBeNull();

    await load();

    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();
    expect(data.value).toEqual(manifestDoc);
  });

  it("transitions loading -> error on failure", async () => {
    const mock = createMockClient({
      getManifest: vi.fn().mockRejectedValue(new Error("Manifest fetch error")),
    });
    injectReturnValue = mock;

    const { data, error, load } = useAnipManifest();

    await load();

    expect(error.value).toBe("Manifest fetch error");
    expect(data.value).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// useAnipPermissions
// ---------------------------------------------------------------------------

describe("useAnipPermissions", () => {
  beforeEach(() => {
    injectReturnValue = undefined;
  });

  it("queries permissions and updates state", async () => {
    const perms: NormalizedPermissions = {
      available: ["search_flights"],
      restricted: [{ capability: "book_flight", reasonType: "scope_insufficient" }],
      denied: [],
    };
    const mock = createMockClient({
      queryPermissions: vi.fn().mockResolvedValue(perms),
    });
    injectReturnValue = mock;

    const { data, loading, error, query } = useAnipPermissions();

    await query("test-token");

    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();
    expect(data.value).toEqual(perms);
    expect(mock.queryPermissions).toHaveBeenCalledWith("test-token");
  });

  it("sets error on query failure", async () => {
    const mock = createMockClient({
      queryPermissions: vi.fn().mockRejectedValue(new Error("Auth failed")),
    });
    injectReturnValue = mock;

    const { data, error, query } = useAnipPermissions();

    await query("bad-token");

    expect(error.value).toBe("Auth failed");
    expect(data.value).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// useAnipCapability
// ---------------------------------------------------------------------------

describe("useAnipCapability", () => {
  beforeEach(() => {
    injectReturnValue = undefined;
  });

  it("returns null when manifest not loaded", () => {
    const mock = createMockClient({
      getCapability: vi.fn().mockReturnValue(null),
    });
    injectReturnValue = mock;

    const { data } = useAnipCapability("search_flights");
    expect(data.value).toBeNull();
  });

  it("resolves capability from cached manifest", () => {
    const cap: NormalizedCapability = {
      name: "search_flights",
      description: "Search for flights",
      minimumScope: ["travel.search"],
      sideEffect: { type: "read" },
      responseModes: ["unary"],
    };
    const mock = createMockClient({
      getCapability: vi.fn().mockReturnValue(cap),
    });
    injectReturnValue = mock;

    const { data } = useAnipCapability("search_flights");
    expect(data.value).toEqual(cap);
  });

  it("can re-resolve after manifest load via resolve()", () => {
    let loaded = false;
    const cap: NormalizedCapability = {
      name: "search_flights",
      description: "Search for flights",
      minimumScope: ["travel.search"],
      sideEffect: { type: "read" },
      responseModes: ["unary"],
    };
    const mock = createMockClient({
      getCapability: vi.fn().mockImplementation(() => (loaded ? cap : null)),
    });
    injectReturnValue = mock;

    const { data, resolve } = useAnipCapability("search_flights");
    expect(data.value).toBeNull();

    loaded = true;
    resolve();
    expect(data.value).toEqual(cap);
  });
});

// ---------------------------------------------------------------------------
// useAnipInvoke
// ---------------------------------------------------------------------------

describe("useAnipInvoke", () => {
  beforeEach(() => {
    injectReturnValue = undefined;
  });

  it("transitions loading -> result on success", async () => {
    const invocationResult: NormalizedInvocationResult = {
      success: true,
      invocationId: "inv-001",
      taskId: "task-001",
      result: { flights: [{ id: "fl-1" }] },
    };
    const mock = createMockClient({
      invoke: vi.fn().mockResolvedValue(invocationResult),
    });
    injectReturnValue = mock;

    const { result, loading, error, invoke } = useAnipInvoke();

    expect(result.value).toBeNull();

    await invoke("token", "search_flights", { origin: "SFO" });

    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();
    expect(result.value).toEqual(invocationResult);
    expect(mock.invoke).toHaveBeenCalledWith(
      "token",
      "search_flights",
      { origin: "SFO" },
      undefined,
    );
  });

  it("passes opts through to client.invoke", async () => {
    const invocationResult: NormalizedInvocationResult = {
      success: true,
      invocationId: "inv-002",
    };
    const mock = createMockClient({
      invoke: vi.fn().mockResolvedValue(invocationResult),
    });
    injectReturnValue = mock;

    const { invoke } = useAnipInvoke();

    await invoke("token", "search_flights", {}, {
      taskId: "task-001",
      parentInvocationId: "inv-000",
      clientReferenceId: "ref-abc",
    });

    expect(mock.invoke).toHaveBeenCalledWith("token", "search_flights", {}, {
      taskId: "task-001",
      parentInvocationId: "inv-000",
      clientReferenceId: "ref-abc",
    });
  });

  it("transitions loading -> error on failure", async () => {
    const mock = createMockClient({
      invoke: vi.fn().mockRejectedValue(new Error("Invoke failed")),
    });
    injectReturnValue = mock;

    const { result, error, invoke } = useAnipInvoke();

    await invoke("token", "search_flights", {});

    expect(error.value).toBe("Invoke failed");
    expect(result.value).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// useAnipAudit
// ---------------------------------------------------------------------------

describe("useAnipAudit", () => {
  beforeEach(() => {
    injectReturnValue = undefined;
  });

  it("queries audit and updates state", async () => {
    const auditResult: NormalizedAuditResult = {
      entries: [{ invocation_id: "inv-001", event: "invoke" }],
      count: 1,
    };
    const mock = createMockClient({
      queryAudit: vi.fn().mockResolvedValue(auditResult),
    });
    injectReturnValue = mock;

    const { data, loading, error, query } = useAnipAudit();

    await query("token", { capability: "search_flights", limit: 10 });

    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();
    expect(data.value).toEqual(auditResult);
    expect(mock.queryAudit).toHaveBeenCalledWith("token", {
      capability: "search_flights",
      limit: 10,
    });
  });

  it("sets error on audit query failure", async () => {
    const mock = createMockClient({
      queryAudit: vi.fn().mockRejectedValue(new Error("Audit error")),
    });
    injectReturnValue = mock;

    const { data, error, query } = useAnipAudit();

    await query("token");

    expect(error.value).toBe("Audit error");
    expect(data.value).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// useAnipFailure
// ---------------------------------------------------------------------------

describe("useAnipFailure", () => {
  it("starts with null failure", () => {
    const { failure } = useAnipFailure();
    expect(failure.value).toBeNull();
  });

  it("extracts failure from invocation result", () => {
    const { failure, setFromResult } = useAnipFailure();

    setFromResult({
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

    expect(failure.value).toBeDefined();
    expect(failure.value!.type).toBe("scope_insufficient");
    expect(failure.value!.permissionRelated).toBe(true);
  });

  it("sets null when result has no failure", () => {
    const { failure, setFromResult } = useAnipFailure();

    // First set a failure
    setFromResult({
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
    expect(failure.value).not.toBeNull();

    // Then set a successful result — failure should be cleared
    setFromResult({
      success: true,
      invocationId: "inv-002",
    });
    expect(failure.value).toBeNull();
  });

  it("clears failure explicitly", () => {
    const { failure, setFromResult, clear } = useAnipFailure();

    setFromResult({
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
    expect(failure.value).not.toBeNull();

    clear();
    expect(failure.value).toBeNull();
  });
});
