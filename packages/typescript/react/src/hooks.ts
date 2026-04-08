/**
 * React hooks wrapping @anip-dev/client.
 *
 * Each hook provides reactive state (data/loading/error) and an action
 * function that calls the underlying ANIPClient method. All protocol logic
 * lives in @anip-dev/client — these hooks only add React state management.
 */

import { useState, useEffect, useCallback } from "react";
import { useAnipClientInternal } from "./provider.js";
import type { ANIPClient } from "@anip-dev/client";
import type {
  NormalizedDiscovery,
  NormalizedManifest,
  NormalizedCapability,
  NormalizedPermissions,
  NormalizedInvocationResult,
  NormalizedFailure,
  NormalizedAuditResult,
} from "@anip-dev/client";

// ---------------------------------------------------------------------------
// useAnipClient — access the context-provided ANIPClient
// ---------------------------------------------------------------------------

export function useAnipClient(): ANIPClient {
  return useAnipClientInternal();
}

// ---------------------------------------------------------------------------
// useAnipDiscovery — reactive discovery loading
// ---------------------------------------------------------------------------

export function useAnipDiscovery() {
  const client = useAnipClientInternal();
  const [data, setData] = useState<NormalizedDiscovery | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await client.discover();
      setData(result);
    } catch (e: any) {
      setData(null);
      setError(e.message ?? "Discovery failed");
    } finally {
      setLoading(false);
    }
  }, [client]);

  return { data, loading, error, load };
}

// ---------------------------------------------------------------------------
// useAnipManifest — reactive manifest loading
// ---------------------------------------------------------------------------

export function useAnipManifest() {
  const client = useAnipClientInternal();
  const [data, setData] = useState<NormalizedManifest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await client.getManifest();
      setData(result);
    } catch (e: any) {
      setData(null);
      setError(e.message ?? "Manifest loading failed");
    } finally {
      setLoading(false);
    }
  }, [client]);

  return { data, loading, error, load };
}

// ---------------------------------------------------------------------------
// useAnipCapability — get a single capability from cached manifest
// ---------------------------------------------------------------------------

/**
 * Get a single capability from the cached manifest.
 *
 * When `manifestData` is provided (from `useAnipManifest().data`), the
 * capability auto-resolves whenever the manifest changes.
 * Without `manifestData`, call `resolve()` manually after loading the manifest.
 */
export function useAnipCapability(
  name: string,
  manifestData?: NormalizedManifest | null,
) {
  const client = useAnipClientInternal();
  const [data, setData] = useState<NormalizedCapability | null>(() =>
    client.getCapability(name),
  );

  // Auto-resolve when manifestData changes.
  useEffect(() => {
    setData(client.getCapability(name));
  }, [client, name, manifestData]);

  const resolve = useCallback(() => {
    setData(client.getCapability(name));
  }, [client, name]);

  return { data, resolve };
}

// ---------------------------------------------------------------------------
// useAnipPermissions — reactive permissions query
// ---------------------------------------------------------------------------

export function useAnipPermissions() {
  const client = useAnipClientInternal();
  const [data, setData] = useState<NormalizedPermissions | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const query = useCallback(
    async (token: string) => {
      setLoading(true);
      setError(null);
      try {
        const result = await client.queryPermissions(token);
        setData(result);
      } catch (e: any) {
        setData(null);
        setError(e.message ?? "Permissions query failed");
      } finally {
        setLoading(false);
      }
    },
    [client],
  );

  return { data, loading, error, query };
}

// ---------------------------------------------------------------------------
// useAnipInvoke — invoke helper with reactive state
// ---------------------------------------------------------------------------

export function useAnipInvoke() {
  const client = useAnipClientInternal();
  const [result, setResult] = useState<NormalizedInvocationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clear = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  const invoke = useCallback(
    async (
      token: string,
      capability: string,
      params: Record<string, unknown>,
      opts?: {
        taskId?: string;
        parentInvocationId?: string;
        clientReferenceId?: string;
      },
    ) => {
      setLoading(true);
      setError(null);
      try {
        const res = await client.invoke(token, capability, params, opts);
        setResult(res);
      } catch (e: any) {
        setResult(null);
        setError(e.message ?? "Invocation failed");
      } finally {
        setLoading(false);
      }
    },
    [client],
  );

  return { result, loading, error, clear, invoke };
}

// ---------------------------------------------------------------------------
// useAnipAudit — audit query with reactive state
// ---------------------------------------------------------------------------

export function useAnipAudit() {
  const client = useAnipClientInternal();
  const [data, setData] = useState<NormalizedAuditResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const query = useCallback(
    async (
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
    ) => {
      setLoading(true);
      setError(null);
      try {
        const res = await client.queryAudit(token, filters);
        setData(res);
      } catch (e: any) {
        setData(null);
        setError(e.message ?? "Audit query failed");
      } finally {
        setLoading(false);
      }
    },
    [client],
  );

  return { data, loading, error, query };
}

// ---------------------------------------------------------------------------
// useAnipFailure — normalized failure state
// ---------------------------------------------------------------------------

export function useAnipFailure() {
  const [failure, setFailure] = useState<NormalizedFailure | null>(null);

  const clear = useCallback(() => {
    setFailure(null);
  }, []);

  const setFromResult = useCallback(
    (result: NormalizedInvocationResult) => {
      setFailure(result.failure ?? null);
    },
    [],
  );

  return { failure, clear, setFromResult };
}
