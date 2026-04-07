/**
 * Vue 3 composables wrapping @anip-dev/client.
 *
 * Each composable provides reactive state (data/loading/error) and an action
 * function that calls the underlying ANIPClient method.  All protocol logic
 * lives in @anip-dev/client — these composables only add reactivity.
 */

import { ref, inject, readonly } from "vue";
import { AnipClientKey } from "./plugin.js";
import type { ANIPClient } from "@anip-dev/client";
import type {
  NormalizedDiscovery,
  NormalizedManifest,
  NormalizedCapability,
  NormalizedPermissions,
  NormalizedTokenResponse,
  NormalizedInvocationResult,
  NormalizedFailure,
  NormalizedAuditResult,
  TokenIssueRequest,
} from "@anip-dev/client";

// ---------------------------------------------------------------------------
// useAnipClient — access the injected ANIPClient
// ---------------------------------------------------------------------------

export function useAnipClient(): ANIPClient {
  const client = inject(AnipClientKey);
  if (!client) {
    throw new Error(
      "ANIPClient not provided. Did you install the ANIP plugin?",
    );
  }
  return client;
}

// ---------------------------------------------------------------------------
// useAnipDiscovery — reactive discovery loading
// ---------------------------------------------------------------------------

export function useAnipDiscovery() {
  const client = useAnipClient();
  const data = ref<NormalizedDiscovery | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function load() {
    loading.value = true;
    error.value = null;
    try {
      data.value = await client.discover();
    } catch (e: any) {
      error.value = e.message ?? "Discovery failed";
    } finally {
      loading.value = false;
    }
  }

  return {
    data: readonly(data),
    loading: readonly(loading),
    error: readonly(error),
    load,
  };
}

// ---------------------------------------------------------------------------
// useAnipManifest — reactive manifest loading
// ---------------------------------------------------------------------------

export function useAnipManifest() {
  const client = useAnipClient();
  const data = ref<NormalizedManifest | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function load() {
    loading.value = true;
    error.value = null;
    try {
      data.value = await client.getManifest();
    } catch (e: any) {
      error.value = e.message ?? "Manifest loading failed";
    } finally {
      loading.value = false;
    }
  }

  return {
    data: readonly(data),
    loading: readonly(loading),
    error: readonly(error),
    load,
  };
}

// ---------------------------------------------------------------------------
// useAnipPermissions — reactive permissions query
// ---------------------------------------------------------------------------

export function useAnipPermissions() {
  const client = useAnipClient();
  const data = ref<NormalizedPermissions | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function query(token: string) {
    loading.value = true;
    error.value = null;
    try {
      data.value = await client.queryPermissions(token);
    } catch (e: any) {
      error.value = e.message ?? "Permissions query failed";
    } finally {
      loading.value = false;
    }
  }

  return {
    data: readonly(data),
    loading: readonly(loading),
    error: readonly(error),
    query,
  };
}

// ---------------------------------------------------------------------------
// useAnipCapability — get a single capability from cached manifest
// ---------------------------------------------------------------------------

export function useAnipCapability(name: string) {
  const client = useAnipClient();
  const data = ref<NormalizedCapability | null>(null);

  function resolve() {
    data.value = client.getCapability(name);
  }

  // Resolve immediately in case manifest is already cached.
  resolve();

  return {
    data: readonly(data),
    resolve,
  };
}

// ---------------------------------------------------------------------------
// useAnipInvoke — invoke helper with reactive state
// ---------------------------------------------------------------------------

export function useAnipInvoke() {
  const client = useAnipClient();
  const result = ref<NormalizedInvocationResult | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function invoke(
    token: string,
    capability: string,
    params: Record<string, unknown>,
    opts?: {
      taskId?: string;
      parentInvocationId?: string;
      clientReferenceId?: string;
    },
  ) {
    loading.value = true;
    error.value = null;
    try {
      result.value = await client.invoke(token, capability, params, opts);
    } catch (e: any) {
      error.value = e.message ?? "Invocation failed";
    } finally {
      loading.value = false;
    }
  }

  return {
    result: readonly(result),
    loading: readonly(loading),
    error: readonly(error),
    invoke,
  };
}

// ---------------------------------------------------------------------------
// useAnipAudit — audit query with reactive state
// ---------------------------------------------------------------------------

export function useAnipAudit() {
  const client = useAnipClient();
  const data = ref<NormalizedAuditResult | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function query(
    token: string,
    filters?: {
      capability?: string;
      since?: string;
      invocationId?: string;
      clientReferenceId?: string;
      taskId?: string;
      parentInvocationId?: string;
      eventClass?: string;
      limit?: number;
    },
  ) {
    loading.value = true;
    error.value = null;
    try {
      data.value = await client.queryAudit(token, filters);
    } catch (e: any) {
      error.value = e.message ?? "Audit query failed";
    } finally {
      loading.value = false;
    }
  }

  return {
    data: readonly(data),
    loading: readonly(loading),
    error: readonly(error),
    query,
  };
}

// ---------------------------------------------------------------------------
// useAnipFailure — normalized failure state
// ---------------------------------------------------------------------------

export function useAnipFailure() {
  const failure = ref<NormalizedFailure | null>(null);

  function clear() {
    failure.value = null;
  }

  function setFromResult(result: NormalizedInvocationResult) {
    failure.value = result.failure ?? null;
  }

  return {
    failure: readonly(failure),
    clear,
    setFromResult,
  };
}
