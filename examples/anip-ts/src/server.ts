/**
 * ANIP reference server — flight booking service.
 *
 * Hono-based TypeScript implementation of the Agent-Native Interface Protocol.
 */

import { serve } from "@hono/node-server";
import { Hono } from "hono";

import { invoke as invokeBookFlight } from "./capabilities/book-flight.js";
import { invoke as invokeSearchFlights } from "./capabilities/search-flights.js";
import { buildManifest } from "./primitives/manifest.js";
import { registerToken, validateDelegation, validateParentExists, validateConstraintsNarrowing, validateTokenRegistered, getChain, getRootPrincipal, acquireExclusiveLock, releaseExclusiveLock, validateScopeNarrowing } from "./primitives/delegation.js";
import { discoverPermissions } from "./primitives/permissions.js";
import {
  DelegationToken,
  InvokeRequest,
  type ANIPFailure,
  type ANIPManifest,
  type InvokeResponse,
  type DelegationToken as DelegationTokenType,
} from "./types.js";

const app = new Hono();

// Build manifest once at startup
const manifest: ANIPManifest = buildManifest();

// --- In-memory audit log ---

interface AuditEntry {
  capability: string;
  timestamp: string;
  token_id: string;
  root_principal: string;
  success: boolean;
  result_summary: Record<string, unknown> | null;
  failure_type: string | null;
  cost_actual: Record<string, unknown> | null;
  cost_variance: Record<string, unknown> | null;
  delegation_chain: string[];
}

const auditLog: AuditEntry[] = [];

function logInvocation(entry: AuditEntry): void {
  auditLog.push(entry);
}

function calculateCostVariance(
  capabilityName: string,
  response: InvokeResponse,
): Record<string, unknown> | null {
  if (!response.success || !response.cost_actual) return null;

  const cap = manifest.capabilities[capabilityName];
  if (!cap?.cost?.financial) return null;

  const declared = cap.cost.financial as Record<string, unknown>;
  const actualAmount = (response.cost_actual as Record<string, unknown>)?.financial as Record<string, unknown> | undefined;
  if (!actualAmount?.amount) return null;

  const amount = actualAmount.amount as number;
  const typical = declared.typical as number | undefined;
  const rangeMin = declared.range_min as number | undefined;
  const rangeMax = declared.range_max as number | undefined;

  const variance: Record<string, unknown> = {
    actual: amount,
    currency: (declared.currency as string) ?? "USD",
    certainty: cap.cost.certainty,
  };

  if (typical !== undefined) {
    variance.declared_typical = typical;
    variance.variance_from_typical_pct = Math.round(((amount - typical) / typical) * 1000) / 10;
  }

  if (rangeMin !== undefined && rangeMax !== undefined) {
    variance.declared_range = { min: rangeMin, max: rangeMax };
    variance.within_declared_range = amount >= rangeMin && amount <= rangeMax;
  }

  return variance;
}

function summarizeResult(result: Record<string, unknown> | null): Record<string, unknown> | null {
  if (!result) return null;
  const summary: Record<string, unknown> = {};
  if ("booking_id" in result) summary.booking_id = result.booking_id;
  if ("count" in result) summary.result_count = result.count;
  if ("total_cost" in result) summary.total_cost = result.total_cost;
  return Object.keys(summary).length > 0 ? summary : { type: "result_logged" };
}

// Capability registry — maps name to invoke function
const capabilityHandlers: Record<
  string,
  (
    token: DelegationTokenType,
    parameters: Record<string, unknown>
  ) => InvokeResponse
> = {
  search_flights: invokeSearchFlights,
  book_flight: invokeBookFlight,
};

// --- Utility: strip null values from profile ---

function excludeNone(
  obj: Record<string, unknown>
): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    if (value !== null && value !== undefined) {
      result[key] = value;
    }
  }
  return result;
}

// --- Discovery ---

app.get("/.well-known/anip", (c) => {
  /**
   * ANIP discovery document — the single entry point to the protocol.
   *
   * Lightweight, cacheable. Tells the agent everything it needs to know
   * to decide whether to fetch the full manifest.
   */
  const profiles = excludeNone(manifest.profile as unknown as Record<string, unknown>);

  // Build capability summaries for discovery
  const capabilitiesSummary: Record<string, unknown> = {};
  for (const [name, cap] of Object.entries(manifest.capabilities)) {
    capabilitiesSummary[name] = {
      description: cap.description,
      side_effect: cap.side_effect.type,
      minimum_scope: cap.minimum_scope,
      financial: cap.cost?.financial != null,
      contract: cap.contract_version,
    };
  }

  // Collect side-effect types present
  const sideEffectTypesPresent = [
    ...new Set(
      Object.values(manifest.capabilities).map(
        (cap) => cap.side_effect.type
      )
    ),
  ].sort();

  // Determine compliance level from profile
  const compliance =
    profiles["cost"] &&
    profiles["capability_graph"] &&
    profiles["state_session"] &&
    profiles["observability"]
      ? "anip-complete"
      : "anip-compliant";

  // Build base_url from the incoming request
  const url = new URL(c.req.url);
  const baseUrl = `${url.protocol}//${url.host}`;

  return c.json({
    anip_discovery: {
      protocol: manifest.protocol,
      compliance,
      base_url: baseUrl,
      profile: profiles,
      auth: {
        delegation_token_required: true,
        supported_formats: ["anip-v1"],
        minimum_scope_for_discovery: "none",
      },
      capabilities: capabilitiesSummary,
      endpoints: {
        manifest: "/anip/manifest",
        handshake: "/anip/handshake",
        permissions: "/anip/permissions",
        invoke: "/anip/invoke/{capability}",
        tokens: "/anip/tokens",
        graph: "/anip/graph/{capability}",
        audit: "/anip/audit",
        test: "/anip/test/{capability}",
      },
      metadata: {
        service_name: "Flight Booking Service",
        service_description: "ANIP-compliant flight search and booking",
        service_category: "travel.booking",
        service_tags: ["flights", "booking", "irreversible-financial"],
        capability_side_effect_types_present: sideEffectTypesPresent,
        max_delegation_depth: 5,
        concurrent_branches_supported: true,
        test_mode_available: false,
        test_mode_unavailable_policy:
          "require_explicit_authorization_for_irreversible",
        generated_at: new Date().toISOString(),
        ttl: "PT1H",
      },
    },
  });
});

// --- Manifest ---

app.get("/anip/manifest", (c) => {
  /** Full ANIP manifest — all capability declarations. */
  return c.json(manifest);
});

// --- Profile Handshake ---

app.post("/anip/handshake", async (c) => {
  /** Check if this service meets the agent's profile requirements. */
  const body = (await c.req.json()) as {
    required_profiles: Record<string, string>;
  };
  const serviceProfiles = excludeNone(
    manifest.profile as unknown as Record<string, unknown>
  );
  const missing: Record<string, string> = {};

  for (const [profile, requiredVersion] of Object.entries(
    body.required_profiles
  )) {
    if (!(profile in serviceProfiles)) {
      missing[profile] = `not supported (required: ${requiredVersion})`;
    } else if (serviceProfiles[profile] !== requiredVersion) {
      missing[profile] =
        `version mismatch: have ${serviceProfiles[profile]}, need ${requiredVersion}`;
    }
  }

  return c.json({
    compatible: Object.keys(missing).length === 0,
    service_profiles: serviceProfiles,
    missing: Object.keys(missing).length > 0 ? missing : null,
  });
});

// --- Delegation Token Registration ---

app.post("/anip/tokens", async (c) => {
  /**
   * Register a delegation token with the service.
   *
   * In production, tokens would be cryptographically verified.
   * In this demo, we trust-on-declaration (per ANIP v1 spec).
   */
  const body = await c.req.json();
  const parseResult = DelegationToken.safeParse(body);
  if (!parseResult.success) {
    return c.json(
      {
        success: false,
        failure: {
          type: "invalid_token",
          detail: `Invalid delegation token: ${parseResult.error.message}`,
          resolution: {
            action: "fix_token_format",
            requires: null,
            grantable_by: null,
            estimated_availability: null,
          },
          retry: true,
        },
      },
      400
    );
  }

  const token = parseResult.data;

  // Validate parent exists: child tokens must reference a registered parent
  const parentFailure = validateParentExists(token);
  if (parentFailure !== null) {
    return c.json({ registered: false, error: parentFailure.detail });
  }

  // Validate scope narrowing: child tokens cannot widen parent scope
  const scopeFailure = validateScopeNarrowing(token);
  if (scopeFailure !== null) {
    return c.json({ registered: false, error: scopeFailure.detail });
  }

  // Validate constraints narrowing: child cannot weaken parent constraints
  const constraintFailure = validateConstraintsNarrowing(token);
  if (constraintFailure !== null) {
    return c.json({ registered: false, error: constraintFailure.detail });
  }

  registerToken(token);
  return c.json({ registered: true, token_id: token.token_id });
});

// --- Permission Discovery ---

app.post("/anip/permissions", async (c) => {
  /** Discover what the agent can do given its delegation chain. */
  const body = await c.req.json();
  const parseResult = DelegationToken.safeParse(body);
  if (!parseResult.success) {
    return c.json(
      {
        success: false,
        failure: {
          type: "invalid_token",
          detail: `Invalid delegation token: ${parseResult.error.message}`,
          resolution: {
            action: "fix_token_format",
            requires: null,
            grantable_by: null,
            estimated_availability: null,
          },
          retry: true,
        },
      },
      400
    );
  }

  const token = parseResult.data;

  // Verify the token is registered — prevents forged tokens from querying permissions
  const regFailure = validateTokenRegistered(token);
  if (regFailure !== null) {
    return c.json({
      success: false,
      failure: regFailure,
    });
  }

  return c.json(discoverPermissions(token, manifest.capabilities));
});

// --- Capability Invocation ---

app.post("/anip/invoke/:capability", async (c) => {
  /** Invoke an ANIP capability with full delegation chain validation. */
  const capabilityName = c.req.param("capability");

  // 1. Check capability exists
  if (!(capabilityName in capabilityHandlers)) {
    const response: InvokeResponse = {
      success: false,
      result: null,
      cost_actual: null,
      failure: {
        type: "unknown_capability",
        detail: `capability '${capabilityName}' does not exist`,
        resolution: {
          action: "check_manifest",
          requires: null,
          grantable_by: null,
          estimated_availability: null,
        },
        retry: false,
      },
      session: null,
    };
    return c.json(response);
  }

  // 2. Parse the request
  const body = await c.req.json();
  const parseResult = InvokeRequest.safeParse(body);
  if (!parseResult.success) {
    const response: InvokeResponse = {
      success: false,
      result: null,
      cost_actual: null,
      failure: {
        type: "invalid_request",
        detail: `Invalid invoke request: ${parseResult.error.message}`,
        resolution: {
          action: "fix_request_format",
          requires: null,
          grantable_by: null,
          estimated_availability: null,
        },
        retry: true,
      },
      session: null,
    };
    return c.json(response, 400);
  }

  const request = parseResult.data;

  // 3. Get the capability declaration for scope requirements
  const capDeclaration = manifest.capabilities[capabilityName];

  // 4. Validate delegation chain
  const delegationFailure = validateDelegation(
    request.delegation_token,
    capDeclaration.minimum_scope,
    capabilityName
  );
  if (delegationFailure !== null) {
    const response: InvokeResponse = {
      success: false,
      result: null,
      cost_actual: null,
      failure: delegationFailure,
      session: null,
    };
    return c.json(response);
  }

  // 5. Acquire exclusive lock if needed
  acquireExclusiveLock(request.delegation_token);
  try {
    // 6. Invoke the capability
    const handler = capabilityHandlers[capabilityName];
    const response = handler(request.delegation_token, request.parameters);

    // 7. Log to audit trail
    const chain = getChain(request.delegation_token);
    const costVariance = calculateCostVariance(capabilityName, response);
    logInvocation({
      capability: capabilityName,
      timestamp: new Date().toISOString(),
      token_id: request.delegation_token.token_id,
      root_principal: getRootPrincipal(request.delegation_token),
      success: response.success,
      result_summary: response.success ? summarizeResult(response.result as Record<string, unknown>) : null,
      failure_type: response.failure?.type ?? null,
      cost_actual: response.cost_actual as Record<string, unknown> | null,
      cost_variance: costVariance,
      delegation_chain: chain.map((t) => t.token_id),
    });

    return c.json(response);
  } finally {
    releaseExclusiveLock(request.delegation_token);
  }
});

// --- Capability Graph ---

app.get("/anip/graph/:capability", (c) => {
  /** Get the capability graph — prerequisites and composition. */
  const capabilityName = c.req.param("capability");

  if (!(capabilityName in manifest.capabilities)) {
    return c.json({ error: `capability '${capabilityName}' not found` }, 404);
  }

  const cap = manifest.capabilities[capabilityName];
  return c.json({
    capability: capabilityName,
    requires: cap.requires,
    composes_with: cap.composes_with,
  });
});

// --- Audit / Observability ---

app.post("/anip/audit", async (c) => {
  /**
   * Query the audit log with optional filters.
   *
   * Access is restricted by the observability contract:
   * only the root principal of the delegation chain can access
   * their own audit records. A valid delegation token is required.
   */
  const body = await c.req.json();
  const parseResult = DelegationToken.safeParse(body);
  if (!parseResult.success) {
    return c.json(
      {
        success: false,
        failure: {
          type: "invalid_token",
          detail: `A valid delegation token is required to access the audit log`,
          resolution: {
            action: "provide_delegation_token",
            requires: null,
            grantable_by: null,
            estimated_availability: null,
          },
          retry: true,
        },
      },
      401
    );
  }

  const token = parseResult.data;

  // Verify the token is registered — prevents forged tokens from querying audit data
  const regFailure = validateTokenRegistered(token);
  if (regFailure !== null) {
    return c.json({
      success: false,
      failure: regFailure,
    }, 401);
  }

  const rootPrincipal = getRootPrincipal(token);

  const capability = c.req.query("capability") ?? null;
  const since = c.req.query("since") ?? null;
  const limit = Math.min(Number(c.req.query("limit") ?? 100), 1000);

  // Filter to only entries belonging to this root principal
  let entries = auditLog.filter((e) => e.root_principal === rootPrincipal);

  if (capability) {
    entries = entries.filter((e) => e.capability === capability);
  }
  if (since) {
    const sinceDate = new Date(since);
    entries = entries.filter((e) => new Date(e.timestamp) >= sinceDate);
  }

  entries = entries.slice(-limit);

  return c.json({
    entries,
    count: entries.length,
    root_principal: rootPrincipal,
    capability_filter: capability,
    since_filter: since,
  });
});

// --- Start server ---

const port = Number(process.env.PORT || 8000);
console.log(`ANIP Flight Service (TypeScript) listening on port ${port}`);

serve({
  fetch: app.fetch,
  port,
});
