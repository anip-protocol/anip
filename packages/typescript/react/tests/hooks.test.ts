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

// ---------------------------------------------------------------------------
// Mock React — minimal useState/useEffect/useCallback/useContext/useRef/createContext
// ---------------------------------------------------------------------------

let contextValue: ANIPClient | null = null;

// Track the latest effect callback for manual triggering
let latestEffectCallback: (() => void) | null = null;
let latestEffectDeps: unknown[] | undefined = undefined;

vi.mock("react", () => {
  return {
    createContext: (defaultValue: any) => ({ _defaultValue: defaultValue }),
    useContext: () => contextValue,
    useRef: (initial: any) => {
      const ref = { current: initial };
      return ref;
    },
    useState: (init: any) => {
      let value = typeof init === "function" ? init() : init;
      const setter = (newVal: any) => {
        value = typeof newVal === "function" ? newVal(value) : newVal;
        // Synchronously update for test purposes
        stateStore.set(setter, value);
      };
      stateStore.set(setter, value);
      return [value, setter];
    },
    useEffect: (cb: () => void, deps?: unknown[]) => {
      latestEffectCallback = cb;
      latestEffectDeps = deps;
      // Run immediately for test purposes
      cb();
    },
    useCallback: (fn: any, _deps?: unknown[]) => fn,
  };
});

// A simple map to track state values across re-reads
const stateStore = new Map<Function, any>();

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
    setBaseUrl: vi.fn(),
    ...overrides,
  } as unknown as ANIPClient;
}

// ---------------------------------------------------------------------------
// Import hooks after mocks are set up
// ---------------------------------------------------------------------------

import {
  useAnipClient,
  useAnipDiscovery,
  useAnipManifest,
  useAnipCapability,
  useAnipPermissions,
  useAnipInvoke,
  useAnipAudit,
  useAnipFailure,
} from "../src/hooks.js";
import { AnipProvider, AnipClientContext } from "../src/provider.js";

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

describe("AnipProvider", () => {
  it("exports AnipClientContext", () => {
    expect(AnipClientContext).toBeDefined();
  });

  it("exports AnipProvider function", () => {
    expect(typeof AnipProvider).toBe("function");
  });
});

// ---------------------------------------------------------------------------
// useAnipClient
// ---------------------------------------------------------------------------

describe("useAnipClient", () => {
  beforeEach(() => {
    contextValue = null;
  });

  it("returns the context client", () => {
    const mock = createMockClient();
    contextValue = mock;
    expect(useAnipClient()).toBe(mock);
  });

  it("throws when no client is provided", () => {
    contextValue = null;
    expect(() => useAnipClient()).toThrow(
      "ANIPClient not provided. Wrap your component tree in <AnipProvider>.",
    );
  });
});

// ---------------------------------------------------------------------------
// useAnipDiscovery
// ---------------------------------------------------------------------------

describe("useAnipDiscovery", () => {
  beforeEach(() => {
    contextValue = null;
  });

  it("starts with null data, false loading, null error", () => {
    const mock = createMockClient();
    contextValue = mock;

    const { data, loading, error } = useAnipDiscovery();

    expect(data).toBeNull();
    expect(loading).toBe(false);
    expect(error).toBeNull();
  });

  it("calls client.discover() on load", async () => {
    const discoveryDoc: NormalizedDiscovery = {
      protocol: "anip/0.23",
      compliance: "full",
      trustLevel: "signed",
      endpoints: { manifest: "/anip/manifest" },
      profiles: { core: "1.0" },
      capabilityNames: ["search_flights"],
      capabilities: {},
      raw: {},
    };
    const mock = createMockClient({
      discover: vi.fn().mockResolvedValue(discoveryDoc),
    });
    contextValue = mock;

    const { load } = useAnipDiscovery();

    await load();

    expect(mock.discover).toHaveBeenCalledTimes(1);
  });

  it("calls client.discover() and handles error", async () => {
    const mock = createMockClient({
      discover: vi.fn().mockRejectedValue(new Error("Network error")),
    });
    contextValue = mock;

    const { load } = useAnipDiscovery();

    // Should not throw — error is captured in state
    await load();
    expect(mock.discover).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// useAnipManifest
// ---------------------------------------------------------------------------

describe("useAnipManifest", () => {
  beforeEach(() => {
    contextValue = null;
  });

  it("starts with null data", () => {
    const mock = createMockClient();
    contextValue = mock;

    const { data, loading, error } = useAnipManifest();

    expect(data).toBeNull();
    expect(loading).toBe(false);
    expect(error).toBeNull();
  });

  it("calls client.getManifest() on load", async () => {
    const manifestDoc: NormalizedManifest = {
      protocol: "anip/0.23",
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
    const mock = createMockClient({
      getManifest: vi.fn().mockResolvedValue(manifestDoc),
    });
    contextValue = mock;

    const { load } = useAnipManifest();
    await load();

    expect(mock.getManifest).toHaveBeenCalledTimes(1);
  });

  it("handles manifest load error", async () => {
    const mock = createMockClient({
      getManifest: vi.fn().mockRejectedValue(new Error("Manifest fetch error")),
    });
    contextValue = mock;

    const { load } = useAnipManifest();
    await load();

    expect(mock.getManifest).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// useAnipCapability
// ---------------------------------------------------------------------------

describe("useAnipCapability", () => {
  beforeEach(() => {
    contextValue = null;
  });

  it("returns null when manifest not loaded", () => {
    const mock = createMockClient({
      getCapability: vi.fn().mockReturnValue(null),
    });
    contextValue = mock;

    const { data } = useAnipCapability("search_flights");
    expect(data).toBeNull();
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
    const mock = createMockClient({
      getCapability: vi.fn().mockReturnValue(cap),
    });
    contextValue = mock;

    const { data } = useAnipCapability("search_flights");
    expect(data).toEqual(cap);
  });

  it("can re-resolve via resolve()", () => {
    let loaded = false;
    const cap: NormalizedCapability = {
      name: "search_flights",
      description: "Search for flights",
      minimumScope: ["travel.search"],
      sideEffect: { type: "read" },
      responseModes: ["unary"],
      raw: {},
    };
    const mock = createMockClient({
      getCapability: vi.fn().mockImplementation(() => (loaded ? cap : null)),
    });
    contextValue = mock;

    const { resolve } = useAnipCapability("search_flights");

    loaded = true;
    resolve();
    // resolve() was called — client.getCapability was invoked again
    expect(mock.getCapability).toHaveBeenCalledWith("search_flights");
  });
});

// ---------------------------------------------------------------------------
// useAnipPermissions
// ---------------------------------------------------------------------------

describe("useAnipPermissions", () => {
  beforeEach(() => {
    contextValue = null;
  });

  it("queries permissions via client", async () => {
    const perms: NormalizedPermissions = {
      available: [{ capability: "search_flights" }],
      restricted: [{ capability: "book_flight", reasonType: "scope_insufficient" }],
      denied: [],
    };
    const mock = createMockClient({
      queryPermissions: vi.fn().mockResolvedValue(perms),
    });
    contextValue = mock;

    const { query } = useAnipPermissions();
    await query("test-token");

    expect(mock.queryPermissions).toHaveBeenCalledWith("test-token");
  });

  it("handles permissions query error", async () => {
    const mock = createMockClient({
      queryPermissions: vi.fn().mockRejectedValue(new Error("Auth failed")),
    });
    contextValue = mock;

    const { query } = useAnipPermissions();
    await query("bad-token");

    expect(mock.queryPermissions).toHaveBeenCalledWith("bad-token");
  });
});

// ---------------------------------------------------------------------------
// useAnipInvoke
// ---------------------------------------------------------------------------

describe("useAnipInvoke", () => {
  beforeEach(() => {
    contextValue = null;
  });

  it("invokes via client", async () => {
    const invocationResult: NormalizedInvocationResult = {
      success: true,
      invocationId: "inv-001",
      taskId: "task-001",
      result: { flights: [{ id: "fl-1" }] },
    };
    const mock = createMockClient({
      invoke: vi.fn().mockResolvedValue(invocationResult),
    });
    contextValue = mock;

    const { invoke } = useAnipInvoke();
    await invoke("token", "search_flights", { origin: "SFO" });

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
    contextValue = mock;

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

  it("handles invoke error", async () => {
    const mock = createMockClient({
      invoke: vi.fn().mockRejectedValue(new Error("Invoke failed")),
    });
    contextValue = mock;

    const { invoke } = useAnipInvoke();
    await invoke("token", "search_flights", {});

    expect(mock.invoke).toHaveBeenCalledTimes(1);
  });

  it("exposes clear() to reset state", () => {
    const mock = createMockClient();
    contextValue = mock;

    const { clear } = useAnipInvoke();
    // Should not throw
    clear();
  });
});

// ---------------------------------------------------------------------------
// useAnipAudit
// ---------------------------------------------------------------------------

describe("useAnipAudit", () => {
  beforeEach(() => {
    contextValue = null;
  });

  it("queries audit via client", async () => {
    const auditResult: NormalizedAuditResult = {
      entries: [{ invocation_id: "inv-001", event: "invoke" }],
      count: 1,
    };
    const mock = createMockClient({
      queryAudit: vi.fn().mockResolvedValue(auditResult),
    });
    contextValue = mock;

    const { query } = useAnipAudit();
    await query("token", { capability: "search_flights", limit: 10 });

    expect(mock.queryAudit).toHaveBeenCalledWith("token", {
      capability: "search_flights",
      limit: 10,
    });
  });

  it("handles audit query error", async () => {
    const mock = createMockClient({
      queryAudit: vi.fn().mockRejectedValue(new Error("Audit error")),
    });
    contextValue = mock;

    const { query } = useAnipAudit();
    await query("token");

    expect(mock.queryAudit).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// useAnipFailure
// ---------------------------------------------------------------------------

describe("useAnipFailure", () => {
  it("starts with null failure", () => {
    // useAnipFailure doesn't need the client context
    const mock = createMockClient();
    contextValue = mock;

    const { failure } = useAnipFailure();
    expect(failure).toBeNull();
  });

  it("exposes clear() and setFromResult()", () => {
    const mock = createMockClient();
    contextValue = mock;

    const { clear, setFromResult } = useAnipFailure();
    expect(typeof clear).toBe("function");
    expect(typeof setFromResult).toBe("function");

    // Should not throw
    clear();
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
  });

  it("sets null when result has no failure", () => {
    const mock = createMockClient();
    contextValue = mock;

    const { setFromResult } = useAnipFailure();

    // Calling with a success result should not throw
    setFromResult({
      success: true,
      invocationId: "inv-002",
    });
  });
});
