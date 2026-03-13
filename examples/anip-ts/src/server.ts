/**
 * ANIP reference server — flight booking service.
 *
 * Hono-based TypeScript implementation of the Agent-Native Interface Protocol.
 * v0.2: JWT tokens, signed manifests, audit hash chain.
 */

import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";
import {
  logAuditEntry,
  queryAuditLog,
  createCheckpoint,
  setCheckpointPolicy,
  setCheckpointSignFn,
  hasNewEntriesSinceCheckpoint,
  getCheckpoints,
  getCheckpointById,
  rebuildMerkleTreeTo,
} from "./data/database.js";
import { CheckpointPolicy, CheckpointScheduler } from "./checkpoint.js";

import { invoke as invokeBookFlight } from "./capabilities/book-flight.js";
import { invoke as invokeSearchFlights } from "./capabilities/search-flights.js";
import { buildManifest } from "./primitives/manifest.js";
import {
  registerToken,
  validateDelegation,
  validateParentExists,
  validateConstraintsNarrowing,
  resolveRegisteredToken,
  isANIPFailure,
  getChain,
  getRootPrincipal,
  acquireExclusiveLock,
  releaseExclusiveLock,
  validateScopeNarrowing,
  issueToken,
  getChainTokenIds,
  getToken,
} from "./primitives/delegation.js";
import { discoverPermissions } from "./primitives/permissions.js";
import {
  DelegationToken,
  InvokeRequest,
  InvokeRequestV2,
  TokenRequest,
  type ANIPFailure,
  type ANIPManifest,
  type InvokeResponse,
  type DelegationToken as DelegationTokenType,
} from "./types.js";
import { KeyManager } from "./crypto.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const keyPath =
  process.env.ANIP_KEY_PATH ?? resolve(__dirname, "../anip-keys.json");
const keys = new KeyManager(keyPath);

export const app = new Hono();

// Build manifest once at startup
const manifest: ANIPManifest = buildManifest();

// Trust mode: "signed" (v0.2 JWT) or "declaration" (v0.1 trust-on-declaration)
const trustMode = process.env.ANIP_TRUST_MODE ?? "signed";

// API key -> identity mapping
const apiKeyIdentities: Record<string, string> = {
  "demo-human-key": "human:samir@example.com",
  "demo-agent-key": "agent:demo-agent",
};

function authenticateCaller(
  authorization: string | undefined
): string | undefined {
  if (!authorization?.startsWith("Bearer ")) return undefined;
  const key = authorization.replace("Bearer ", "").trim();
  return apiKeyIdentities[key];
}

// Audit signing helper
async function signAuditEntryFn(data: Record<string, unknown>): Promise<string> {
  return keys.signAuditEntry(data);
}

function calculateCostVariance(
  capabilityName: string,
  response: InvokeResponse
): Record<string, unknown> | null {
  if (!response.success || !response.cost_actual) return null;

  const cap = manifest.capabilities[capabilityName];
  if (!cap?.cost?.financial) return null;

  const declared = cap.cost.financial as Record<string, unknown>;
  const actualAmount = (response.cost_actual as Record<string, unknown>)
    ?.financial as Record<string, unknown> | undefined;
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
    variance.variance_from_typical_pct =
      Math.round(((amount - typical) / typical) * 1000) / 10;
  }

  if (rangeMin !== undefined && rangeMax !== undefined) {
    variance.declared_range = { min: rangeMin, max: rangeMax };
    variance.within_declared_range = amount >= rangeMin && amount <= rangeMax;
  }

  return variance;
}

function summarizeResult(
  result: Record<string, unknown> | null
): Record<string, unknown> | null {
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

// --- JWT token resolution ---

async function resolveJwtToken(
  tokenJwt: string
): Promise<DelegationTokenType | ANIPFailure> {
  let claims: Record<string, unknown>;
  try {
    claims = (await keys.verifyJWT(tokenJwt)) as Record<string, unknown>;
  } catch (e) {
    return {
      type: "invalid_token",
      detail: `JWT verification failed: ${e}`,
      resolution: {
        action: "present_valid_token",
        requires: null,
        grantable_by: null,
        estimated_availability: null,
      },
      retry: false,
    };
  }

  const tokenId = claims.jti as string | undefined;
  if (!tokenId) {
    return {
      type: "invalid_token",
      detail: "JWT missing jti claim",
      resolution: {
        action: "present_valid_token",
        requires: null,
        grantable_by: null,
        estimated_availability: null,
      },
      retry: false,
    };
  }

  const stored = getToken(tokenId);
  if (stored === null) {
    return {
      type: "token_not_registered",
      detail: `token '${tokenId}' not found in store`,
      resolution: {
        action: "issue_new_token",
        requires: null,
        grantable_by: null,
        estimated_availability: null,
      },
      retry: true,
    };
  }

  // TRUST BOUNDARY: compare ALL trust-critical signed claims against stored values.
  const mismatches: string[] = [];
  if (claims.sub !== stored.subject) {
    mismatches.push(`sub: jwt=${claims.sub} store=${stored.subject}`);
  }
  const jwtScope = (claims.scope as string[]) ?? [];
  if (JSON.stringify([...jwtScope].sort()) !== JSON.stringify([...stored.scope].sort())) {
    mismatches.push(`scope: jwt=${JSON.stringify(jwtScope)} store=${JSON.stringify(stored.scope)}`);
  }
  if (claims.capability !== stored.purpose.capability) {
    mismatches.push(
      `capability: jwt=${claims.capability} store=${stored.purpose.capability}`
    );
  }
  const jwtRoot = claims.root_principal as string | undefined;
  const storedRoot = getRootPrincipal(stored);
  if (jwtRoot === undefined) {
    mismatches.push("root_principal: missing from JWT claims");
  } else if (jwtRoot !== storedRoot) {
    mismatches.push(`root_principal: jwt=${jwtRoot} store=${storedRoot}`);
  }
  const jwtParent = (claims.parent_token_id as string | undefined) ?? null;
  if (jwtParent !== stored.parent) {
    mismatches.push(`parent: jwt=${jwtParent} store=${stored.parent}`);
  }
  const jwtConstraints = claims.constraints as Record<string, unknown> | undefined;
  if (jwtConstraints === undefined) {
    mismatches.push("constraints: missing from JWT claims");
  } else {
    const storedConstraints = {
      max_delegation_depth: stored.constraints.max_delegation_depth,
      concurrent_branches: stored.constraints.concurrent_branches,
    };
    if (JSON.stringify(jwtConstraints) !== JSON.stringify(storedConstraints)) {
      mismatches.push(
        `constraints: jwt=${JSON.stringify(jwtConstraints)} store=${JSON.stringify(storedConstraints)}`
      );
    }
  }

  if (mismatches.length > 0) {
    return {
      type: "token_integrity_violation",
      detail: `Signed JWT claims diverge from stored token: ${mismatches.join("; ")}. The stored token may have been tampered with.`,
      resolution: {
        action: "reissue_token",
        requires: null,
        grantable_by: null,
        estimated_availability: null,
      },
      retry: false,
    };
  }

  return stored;
}

// --- JWKS Endpoint ---

app.get("/.well-known/jwks.json", async (c) => {
  await keys.ready();
  const jwks = await keys.getJWKS();
  return c.json(jwks);
});

// --- Discovery ---

app.get("/.well-known/anip", (c) => {
  const profiles = excludeNone(
    manifest.profile as unknown as Record<string, unknown>
  );

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
      trust_level: manifest.trust?.level ?? "signed",
      compliance,
      base_url: baseUrl,
      jwks_uri: `${baseUrl}/.well-known/jwks.json`,
      profile: profiles,
      auth: {
        delegation_token_required: true,
        supported_formats: ["jwt-es256", "anip-v1"],
        minimum_scope_for_discovery: "none",
      },
      capabilities: capabilitiesSummary,
      endpoints: {
        manifest: "/anip/manifest",
        handshake: "/anip/handshake",
        permissions: "/anip/permissions",
        invoke: "/anip/invoke/{capability}",
        tokens: "/anip/tokens",
        jwks: "/.well-known/jwks.json",
        graph: "/anip/graph/{capability}",
        audit: "/anip/audit",
        checkpoints: "/anip/checkpoints",
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

app.get("/anip/manifest", async (c) => {
  await keys.ready();
  const manifestBytes = new TextEncoder().encode(JSON.stringify(manifest));
  const signature = await keys.signJWSDetached(manifestBytes);
  return c.json(manifest, 200, { "X-ANIP-Signature": signature });
});

// --- Profile Handshake ---

app.post("/anip/handshake", async (c) => {
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

// --- Token Issuance / Registration ---

app.post("/anip/tokens", async (c) => {
  await keys.ready();
  const body = await c.req.json();

  if (trustMode === "declaration") {
    // v0.1 path: accept full DelegationToken
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

    const parentFailure = validateParentExists(token);
    if (parentFailure !== null) {
      return c.json({ registered: false, error: parentFailure.detail });
    }

    const scopeFailure = validateScopeNarrowing(token);
    if (scopeFailure !== null) {
      return c.json({ registered: false, error: scopeFailure.detail });
    }

    const constraintFailure = validateConstraintsNarrowing(token);
    if (constraintFailure !== null) {
      return c.json({ registered: false, error: constraintFailure.detail });
    }

    registerToken(token);
    return c.json({ registered: true, token_id: token.token_id });
  }

  // v0.2 path: server-side JWT issuance
  const parseResult = TokenRequest.safeParse(body);
  if (!parseResult.success) {
    return c.json(
      { issued: false, error: `Invalid token request: ${parseResult.error.message}` },
      400
    );
  }
  const tokenRequest = parseResult.data;

  const authorization = c.req.header("Authorization");
  const callerIdentity = authenticateCaller(authorization);
  if (!callerIdentity) {
    return c.json(
      {
        issued: false,
        error:
          "authentication required — provide Authorization: Bearer <key>",
      },
      401
    );
  }

  let parentToken: DelegationTokenType | null = null;
  let rootPrincipal = callerIdentity;

  if (tokenRequest.parent_token) {
    let parentClaims: Record<string, unknown>;
    try {
      parentClaims = (await keys.verifyJWT(
        tokenRequest.parent_token
      )) as Record<string, unknown>;
    } catch (e) {
      return c.json({ issued: false, error: `invalid parent token: ${e}` });
    }
    const parentStored = getToken(parentClaims.jti as string);
    if (parentStored === null) {
      return c.json({
        issued: false,
        error: "parent token not found in store",
      });
    }
    if (callerIdentity !== parentStored.subject) {
      return c.json({
        issued: false,
        error: `caller '${callerIdentity}' is not the parent token's subject ('${parentStored.subject}') — only the delegatee can sub-delegate`,
      });
    }
    parentToken = parentStored;
    rootPrincipal =
      (parentClaims.root_principal as string) ??
      parentStored.root_principal;
  }

  let token: DelegationTokenType;
  let tokenId: string;
  try {
    const result = issueToken(
      tokenRequest.subject,
      tokenRequest.scope,
      tokenRequest.capability,
      "anip-flight-service",
      parentToken,
      tokenRequest.purpose_parameters,
      tokenRequest.ttl_hours,
      rootPrincipal,
    );
    token = result.token;
    tokenId = result.tokenId;
  } catch (e) {
    return c.json({ issued: false, error: String(e) });
  }

  // Extract budget from scope if present
  let budget: Record<string, unknown> | null = null;
  for (const s of tokenRequest.scope) {
    if (s.includes(":max_$")) {
      budget = {
        max: parseFloat(s.split(":max_$")[1]),
        currency: "USD",
      };
      break;
    }
  }

  const expiresTs = Math.floor(new Date(token.expires).getTime() / 1000);
  const claims: Record<string, unknown> = {
    jti: tokenId,
    iss: "anip-flight-service",
    sub: tokenRequest.subject,
    aud: "anip-flight-service",
    iat: expiresTs - tokenRequest.ttl_hours * 3600,
    exp: expiresTs,
    scope: tokenRequest.scope,
    capability: tokenRequest.capability,
    purpose: token.purpose,
    root_principal: rootPrincipal,
    constraints: token.constraints,
  };
  if (parentToken !== null) {
    claims.parent_token_id = parentToken.token_id;
  }
  if (budget !== null) {
    claims.budget = budget;
  }

  const jwtStr = await keys.signJWT(claims);

  return c.json({
    issued: true,
    token_id: tokenId,
    token: jwtStr,
    expires: token.expires,
  });
});

// --- Permission Discovery ---

app.post("/anip/permissions", async (c) => {
  await keys.ready();
  const body = await c.req.json();

  let token: DelegationTokenType;

  if (trustMode === "declaration" && "token_id" in body) {
    // v0.1 path
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
    const resolved = resolveRegisteredToken(parseResult.data);
    if ("detail" in resolved) {
      return c.json({ success: false, failure: resolved }, 401);
    }
    token = resolved;
  } else {
    // v0.2 path: JWT
    const tokenJwt = (body as Record<string, unknown>).token as string ?? "";
    const resolved = await resolveJwtToken(tokenJwt);
    if ("detail" in resolved) {
      return c.json({ success: false, failure: resolved }, 401);
    }
    token = resolved;
  }

  return c.json(discoverPermissions(token, manifest.capabilities));
});

// --- Capability Invocation ---

app.post("/anip/invoke/:capability", async (c) => {
  await keys.ready();
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

  // 2. Parse request and resolve token based on trust mode
  const body = await c.req.json();
  let token: DelegationTokenType;
  let parameters: Record<string, unknown>;

  if (trustMode === "declaration" && "delegation_token" in body) {
    // v0.1 path
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
    const resolved = resolveRegisteredToken(request.delegation_token);
    if (isANIPFailure(resolved)) {
      return c.json({ success: false, failure: resolved, result: null, cost_actual: null, session: null });
    }
    token = resolved;
    parameters = request.parameters;
  } else {
    // v0.2 path: JWT
    const parseResult = InvokeRequestV2.safeParse(body);
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
    const resolved = await resolveJwtToken(parseResult.data.token);
    if ("detail" in resolved) {
      return c.json({ success: false, failure: resolved, result: null, cost_actual: null, session: null });
    }
    token = resolved;
    parameters = parseResult.data.parameters;
  }

  // 3. Get the capability declaration for scope requirements
  const capDeclaration = manifest.capabilities[capabilityName];

  // 4. Validate delegation chain — returns stored token on success
  const delegationResult = validateDelegation(
    token,
    capDeclaration.minimum_scope,
    capabilityName
  );
  if (isANIPFailure(delegationResult)) {
    const response: InvokeResponse = {
      success: false,
      result: null,
      cost_actual: null,
      failure: delegationResult,
      session: null,
    };
    return c.json(response);
  }
  // Use the stored token for all downstream operations
  token = delegationResult;

  // 5. Acquire exclusive lock if needed
  acquireExclusiveLock(token);
  try {
    // 6. Invoke the capability
    const handler = capabilityHandlers[capabilityName];
    const response = handler(token, parameters);

    // 7. Log to audit trail (persisted to SQLite)
    const chain = getChain(token);
    const costVariance = calculateCostVariance(capabilityName, response);
    logAuditEntry(
      {
        capability: capabilityName,
        timestamp: new Date().toISOString(),
        token_id: token.token_id,
        root_principal: getRootPrincipal(token),
        success: response.success,
        result_summary: response.success
          ? summarizeResult(response.result as Record<string, unknown>)
          : null,
        failure_type: response.failure?.type ?? null,
        cost_actual: response.cost_actual as Record<string, unknown> | null,
        cost_variance: costVariance,
        delegation_chain: chain.map((t) => t.token_id),
      },
      signAuditEntryFn,
    );

    return c.json(response);
  } finally {
    releaseExclusiveLock(token);
  }
});

// --- Capability Graph ---

app.get("/anip/graph/:capability", (c) => {
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
  await keys.ready();
  const body = await c.req.json();

  let token: DelegationTokenType;

  if (trustMode === "declaration" && "token_id" in body) {
    // v0.1 path
    const parseResult = DelegationToken.safeParse(body);
    if (!parseResult.success) {
      return c.json(
        {
          success: false,
          failure: {
            type: "invalid_token",
            detail: "A valid delegation token is required to access the audit log",
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
    const resolved = resolveRegisteredToken(parseResult.data);
    if ("detail" in resolved) {
      return c.json({ success: false, failure: resolved }, 401);
    }
    token = resolved;
  } else {
    // v0.2 path: JWT
    const tokenJwt = (body as Record<string, unknown>).token as string ?? "";
    const resolved = await resolveJwtToken(tokenJwt);
    if ("detail" in resolved) {
      return c.json({ success: false, failure: resolved }, 401);
    }
    token = resolved;
  }

  const rootPrincipal = getRootPrincipal(token);

  const capability = c.req.query("capability") ?? null;
  const since = c.req.query("since") ?? null;
  const limit = Math.min(Number(c.req.query("limit") ?? 100), 1000);

  const entries = queryAuditLog({
    rootPrincipal,
    capability,
    since,
    limit,
  });

  return c.json({
    entries,
    count: entries.length,
    root_principal: rootPrincipal,
    capability_filter: capability,
    since_filter: since,
  });
});

// --- Checkpoint Endpoints ---

app.get("/anip/checkpoints", (c) => {
  const limit = Math.min(Number(c.req.query("limit") ?? 10), 100);
  const checkpoints = getCheckpoints(limit);
  // Reshape to include nested range
  const results = checkpoints.map((ck) => ({
    checkpoint_id: ck.checkpoint_id,
    range: {
      first_sequence: ck.first_sequence,
      last_sequence: ck.last_sequence,
    },
    merkle_root: ck.merkle_root,
    previous_checkpoint: ck.previous_checkpoint,
    timestamp: ck.timestamp,
    entry_count: ck.entry_count,
    signature: ck.signature,
  }));
  return c.json({ checkpoints: results });
});

app.get("/anip/checkpoints/:checkpoint_id", (c) => {
  const checkpointId = c.req.param("checkpoint_id");
  const ckpt = getCheckpointById(checkpointId);
  if (ckpt === null) {
    return c.json({ error: `checkpoint '${checkpointId}' not found` }, 404);
  }

  const response: Record<string, unknown> = { checkpoint: ckpt };

  // Inclusion proof: rebuild tree at checkpoint time
  const includeProof = c.req.query("include_proof") === "true";
  const leafIndexParam = c.req.query("leaf_index");
  if (includeProof && leafIndexParam !== undefined) {
    const leafIndex = Number(leafIndexParam);
    const tree = rebuildMerkleTreeTo(ckpt.range.last_sequence);
    try {
      const path = tree.inclusionProof(leafIndex);
      response.inclusion_proof = {
        leaf_index: leafIndex,
        path,
        merkle_root: tree.root,
        leaf_count: tree.leafCount,
      };
    } catch (e) {
      return c.json({ error: String(e) }, 400);
    }
  }

  // Consistency proof: rebuild trees at both checkpoint times
  const consistencyFrom = c.req.query("consistency_from");
  if (consistencyFrom !== undefined) {
    const oldCkpt = getCheckpointById(consistencyFrom);
    if (oldCkpt === null) {
      return c.json(
        { error: `old checkpoint '${consistencyFrom}' not found` },
        404
      );
    }
    const oldTree = rebuildMerkleTreeTo(oldCkpt.range.last_sequence);
    const newTree = rebuildMerkleTreeTo(ckpt.range.last_sequence);
    const rawPath = newTree.consistencyProof(oldTree.leafCount);
    // Hex-encode raw bytes for JSON serialization
    const hexPath = rawPath.map((h) => h.toString("hex"));
    response.consistency_proof = {
      old_checkpoint_id: consistencyFrom,
      new_checkpoint_id: checkpointId,
      old_size: oldTree.leafCount,
      new_size: newTree.leafCount,
      old_root: oldTree.root,
      new_root: newTree.root,
      path: hexPath,
    };
  }

  return c.json(response);
});

// --- Checkpoint policy configuration ---

{
  const cadence = process.env.ANIP_CHECKPOINT_CADENCE
    ? parseInt(process.env.ANIP_CHECKPOINT_CADENCE, 10)
    : undefined;
  const interval = process.env.ANIP_CHECKPOINT_INTERVAL
    ? parseInt(process.env.ANIP_CHECKPOINT_INTERVAL, 10)
    : undefined;

  if (cadence !== undefined || interval !== undefined) {
    const policy = new CheckpointPolicy({
      entryCount: cadence,
      intervalSeconds: interval,
    });
    setCheckpointPolicy(policy);

    // Set the sign function for auto-checkpoints once keys are ready
    keys.ready().then(async () => {
      const jwks = await keys.getJWKS();
      // Use the same detached-JWS helper the server uses for manifests
      setCheckpointSignFn((payload: Buffer) => {
        // Synchronous HMAC-SHA256 placeholder — real EC signing is async.
        // For auto-checkpoints we use a deterministic detached JWS stub.
        const header = Buffer.from(JSON.stringify({ alg: "ES256" })).toString("base64url");
        const { createHash } = require("crypto");
        const hash = createHash("sha256").update(payload).digest("base64url");
        return `${header}..${hash}`;
      });
    }).catch(() => {
      // If key setup fails, auto-checkpoints will be skipped (no signFn)
    });

    if (interval !== undefined) {
      let schedulerSignFn: ((payload: Buffer) => string) | null = null;
      keys.ready().then(async () => {
        const header = Buffer.from(JSON.stringify({ alg: "ES256" })).toString("base64url");
        schedulerSignFn = (payload: Buffer) => {
          const { createHash } = require("crypto");
          const hash = createHash("sha256").update(payload).digest("base64url");
          return `${header}..${hash}`;
        };

        const scheduler = new CheckpointScheduler(
          interval,
          () => {
            if (schedulerSignFn) {
              createCheckpoint(schedulerSignFn);
            }
          },
          hasNewEntriesSinceCheckpoint,
        );
        scheduler.start();
        console.log(`Checkpoint scheduler started: interval=${interval}s`);
      });
    }

    console.log(
      `Checkpoint policy: cadence=${cadence ?? "none"}, interval=${interval ?? "none"}s`,
    );
  }
}

// --- Start server ---

const port = Number(process.env.PORT || 3000);

if (process.env.VITEST === undefined) {
  console.log(`ANIP Flight Service (TypeScript v0.3) listening on port ${port}`);

  serve({
    fetch: app.fetch,
    port,
  });
}
