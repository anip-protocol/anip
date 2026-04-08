/**
 * ANIPClient — framework-agnostic ANIP consumer adapter.
 *
 * Wraps the raw HTTP surface of an ANIP service and returns normalized,
 * consumer-friendly types.  Uses the `fetch` API internally so it works
 * in browsers, Node 20+, and edge runtimes.
 */

import type {
  NormalizedDiscovery,
  NormalizedManifest,
  NormalizedCapability,
  NormalizedPermissions,
  NormalizedTokenResponse,
  NormalizedInvocationResult,
  NormalizedAuditResult,
  TokenIssueRequest,
} from "./types.js";
import { normalizeDiscovery } from "./discovery.js";
import { normalizeManifest } from "./manifest.js";
import { normalizePermissions } from "./permissions.js";
import { normalizeFailure } from "./failures.js";

export interface ANIPClientOptions {
  /** Request timeout in milliseconds (default: 30 000). */
  timeout?: number;
}

export class ANIPClient {
  private baseUrl: string;
  private readonly timeout: number;

  /** Cached discovery document. */
  private discoveryCache: NormalizedDiscovery | null = null;
  /** Cached manifest. */
  private manifestCache: NormalizedManifest | null = null;

  constructor(baseUrl: string, opts?: ANIPClientOptions) {
    // Strip trailing slash for consistent path joining.
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.timeout = opts?.timeout ?? 30_000;
  }

  /**
   * Update the target ANIP service URL and clear cached discovery/manifest
   * state when switching services.
   */
  setBaseUrl(baseUrl: string): void {
    const normalized = baseUrl.replace(/\/+$/, "");
    if (normalized === this.baseUrl) return;
    this.baseUrl = normalized;
    this.discoveryCache = null;
    this.manifestCache = null;
  }

  // -----------------------------------------------------------------------
  // Internal helpers
  // -----------------------------------------------------------------------

  private async request(
    path: string,
    init?: RequestInit,
  ): Promise<Response> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...init,
        signal: controller.signal,
      });
      return response;
    } finally {
      clearTimeout(timer);
    }
  }

  private async json(path: string, init?: RequestInit): Promise<any> {
    const response = await this.request(path, init);
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new Error(
        `ANIP request failed: ${response.status} ${response.statusText} — ${body}`,
      );
    }
    return response.json();
  }

  /**
   * Resolve an endpoint path from the discovery document.
   * Falls back to a sensible default if discovery has not been loaded yet.
   */
  private resolveEndpoint(
    name: string,
    substitutions?: Record<string, string>,
  ): string {
    let path =
      this.discoveryCache?.endpoints[name] ?? defaultEndpoints[name] ?? `/${name}`;
    if (substitutions) {
      for (const [key, value] of Object.entries(substitutions)) {
        path = path.replace(`{${key}}`, encodeURIComponent(value));
      }
    }
    return path;
  }

  // -----------------------------------------------------------------------
  // Discovery
  // -----------------------------------------------------------------------

  async discover(): Promise<NormalizedDiscovery> {
    const raw = await this.json("/.well-known/anip");
    this.discoveryCache = normalizeDiscovery(raw);
    return this.discoveryCache;
  }

  // -----------------------------------------------------------------------
  // Manifest
  // -----------------------------------------------------------------------

  async getManifest(): Promise<NormalizedManifest> {
    const path = this.resolveEndpoint("manifest");
    const response = await this.request(path);
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new Error(
        `ANIP request failed: ${response.status} ${response.statusText} — ${body}`,
      );
    }
    const raw = await response.json();
    const signature = response.headers?.get?.("X-ANIP-Signature") ?? undefined;
    this.manifestCache = normalizeManifest(raw, { signature });
    return this.manifestCache;
  }

  // -----------------------------------------------------------------------
  // Capability lookup (from cached manifest)
  // -----------------------------------------------------------------------

  getCapability(name: string): NormalizedCapability | null {
    return this.manifestCache?.capabilities[name] ?? null;
  }

  // -----------------------------------------------------------------------
  // Permissions
  // -----------------------------------------------------------------------

  async queryPermissions(token: string): Promise<NormalizedPermissions> {
    const path = this.resolveEndpoint("permissions");
    const raw = await this.json(path, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });
    return normalizePermissions(raw);
  }

  // -----------------------------------------------------------------------
  // Token issuance
  // -----------------------------------------------------------------------

  async issueToken(
    apiKeyOrToken: string,
    request: TokenIssueRequest,
  ): Promise<NormalizedTokenResponse> {
    const path = this.resolveEndpoint("tokens");
    const body: Record<string, unknown> = {
      scope: request.scope,
    };
    if (request.subject) body.subject = request.subject;
    if (request.capability) body.capability = request.capability;
    if (request.parentToken) body.parent_token = request.parentToken;
    if (request.purposeParameters) body.purpose_parameters = request.purposeParameters;
    if (request.ttlHours !== undefined) body.ttl_hours = request.ttlHours;
    if (request.callerClass) body.caller_class = request.callerClass;
    if (request.budget) {
      body.budget = {
        currency: request.budget.currency,
        max_amount: request.budget.maxAmount,
      };
    }
    if (request.concurrentBranches) body.concurrent_branches = request.concurrentBranches;

    const raw = await this.json(path, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKeyOrToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    return normalizeTokenResponse(raw);
  }

  async issueCapabilityToken(
    apiKeyOrToken: string,
    capability: string,
    scope: string[],
    opts?: {
      subject?: string;
      ttlHours?: number;
      budget?: { currency: string; maxAmount: number };
      callerClass?: string;
    },
  ): Promise<NormalizedTokenResponse> {
    return this.issueToken(apiKeyOrToken, {
      capability,
      scope,
      subject: opts?.subject,
      ttlHours: opts?.ttlHours,
      budget: opts?.budget,
      callerClass: opts?.callerClass,
    });
  }

  async issueDelegatedCapabilityToken(
    apiKeyOrToken: string,
    parentToken: string,
    capability: string,
    scope: string[],
    subject: string,
    opts?: {
      ttlHours?: number;
      budget?: { currency: string; maxAmount: number };
      callerClass?: string;
      concurrentBranches?: string;
    },
  ): Promise<NormalizedTokenResponse> {
    return this.issueToken(apiKeyOrToken, {
      capability,
      scope,
      subject,
      parentToken,
      ttlHours: opts?.ttlHours,
      budget: opts?.budget,
      callerClass: opts?.callerClass,
      concurrentBranches: opts?.concurrentBranches,
    });
  }

  // -----------------------------------------------------------------------
  // Invoke
  // -----------------------------------------------------------------------

  async invoke(
    token: string,
    capability: string,
    params: Record<string, unknown>,
    opts?: {
      taskId?: string;
      parentInvocationId?: string;
      clientReferenceId?: string;
    },
  ): Promise<NormalizedInvocationResult> {
    const path = this.resolveEndpoint("invoke", { capability });

    const body: Record<string, unknown> = {
      parameters: params,
    };
    if (opts?.taskId) body.task_id = opts.taskId;
    if (opts?.parentInvocationId) body.parent_invocation_id = opts.parentInvocationId;
    if (opts?.clientReferenceId) body.client_reference_id = opts.clientReferenceId;

    const raw = await this.json(path, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    return normalizeInvocationResult(raw);
  }

  // -----------------------------------------------------------------------
  // Audit
  // -----------------------------------------------------------------------

  async queryAudit(
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
  ): Promise<NormalizedAuditResult> {
    const basePath = this.resolveEndpoint("audit");

    // ANIP audit is POST with optional query parameters (not body).
    const searchParams = new URLSearchParams();
    if (filters?.capability) searchParams.set("capability", filters.capability);
    if (filters?.since) searchParams.set("since", filters.since);
    if (filters?.invocationId) searchParams.set("invocation_id", filters.invocationId);
    if (filters?.clientReferenceId) searchParams.set("client_reference_id", filters.clientReferenceId);
    if (filters?.taskId) searchParams.set("task_id", filters.taskId);
    if (filters?.parentInvocationId) searchParams.set("parent_invocation_id", filters.parentInvocationId);
    if (filters?.eventClass) searchParams.set("event_class", filters.eventClass);
    if (filters?.limit !== undefined) searchParams.set("limit", String(filters.limit));

    const qs = searchParams.toString();
    const path = qs ? `${basePath}?${qs}` : basePath;

    const raw = await this.json(path, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    return {
      entries: Array.isArray(raw.entries) ? raw.entries : [],
      count: typeof raw.count === "number" ? raw.count : (raw.entries?.length ?? 0),
    };
  }

  // -----------------------------------------------------------------------
  // Graph
  // -----------------------------------------------------------------------

  async getCapabilityGraph(capability: string): Promise<any> {
    const path = this.resolveEndpoint("graph", { capability });
    return this.json(path);
  }

  // -----------------------------------------------------------------------
  // Checkpoints
  // -----------------------------------------------------------------------

  async getCheckpoints(opts?: { limit?: number }): Promise<any> {
    const basePath = this.resolveEndpoint("checkpoints");
    const searchParams = new URLSearchParams();
    if (opts?.limit !== undefined) searchParams.set("limit", String(opts.limit));
    const qs = searchParams.toString();
    const path = qs ? `${basePath}?${qs}` : basePath;
    return this.json(path);
  }
}

// ---------------------------------------------------------------------------
// Default endpoint paths (used when discovery has not been loaded)
// ---------------------------------------------------------------------------

const defaultEndpoints: Record<string, string> = {
  manifest: "/anip/manifest",
  invoke: "/anip/invoke/{capability}",
  permissions: "/anip/permissions",
  tokens: "/anip/tokens",
  audit: "/anip/audit",
  graph: "/anip/graph/{capability}",
  checkpoints: "/anip/checkpoints",
};

// ---------------------------------------------------------------------------
// Response normalization helpers
// ---------------------------------------------------------------------------

function normalizeTokenResponse(raw: any): NormalizedTokenResponse {
  const result: NormalizedTokenResponse = {
    issued: raw.issued ?? true,
    tokenId: raw.token_id ?? "",
    token: raw.token ?? "",
    expires: raw.expires ?? "",
  };
  if (raw.task_id) result.taskId = raw.task_id;
  if (raw.budget) {
    result.budget = {
      currency: raw.budget.currency ?? "",
      maxAmount: raw.budget.max_amount ?? 0,
    };
  }
  return result;
}

function normalizeInvocationResult(raw: any): NormalizedInvocationResult {
  const result: NormalizedInvocationResult = {
    success: raw.success ?? false,
    invocationId: raw.invocation_id ?? "",
  };

  // task_id may come from the invocation response or the token's purpose.
  if (raw.task_id) result.taskId = raw.task_id;

  if (raw.result) result.result = raw.result;

  if (raw.failure) {
    result.failure = normalizeFailure(raw.failure);
  }

  if (raw.budget_context) {
    const bc = raw.budget_context;
    result.budgetContext = {
      budgetMax: bc.budget_max ?? 0,
      budgetCurrency: bc.budget_currency ?? "",
      costCheckAmount: bc.cost_check_amount ?? 0,
    };
  }

  if (raw.stream_summary) {
    const ss = raw.stream_summary;
    result.streamSummary = {
      responseMode: ss.response_mode ?? "streaming",
      eventsEmitted: ss.events_emitted ?? 0,
      eventsDelivered: ss.events_delivered ?? 0,
      durationMs: ss.duration_ms ?? 0,
      clientDisconnected: ss.client_disconnected ?? false,
    };
  }

  return result;
}
