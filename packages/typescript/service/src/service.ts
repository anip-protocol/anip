/**
 * ANIP service runtime — the main developer-facing builder.
 *
 * `createANIPService(opts)` returns an ANIPService object that owns all
 * SDK instances (keys, storage, delegation engine, audit log) and exposes
 * domain-level operations — no HTTP types.
 */

import { randomUUID } from "node:crypto";

import type {
  ANIPManifest,
  CapabilityDeclaration,
  DelegationToken,
} from "@anip/core";
import { PROTOCOL_VERSION, DEFAULT_PROFILE } from "@anip/core";
import { KeyManager } from "@anip/crypto";
import {
  AuditLog,
  buildManifest,
  CheckpointPolicy,
  CheckpointScheduler,
  createCheckpoint,
  DelegationEngine,
  discoverPermissions,
  InMemoryStorage,
  MerkleTree,
  SQLiteStorage,
  type CheckpointSink,
  type StorageBackend,
} from "@anip/server";

import { ANIPError } from "./types.js";
import type { CapabilityDef, Handler, InvocationContext } from "./types.js";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface ANIPServiceOpts {
  serviceId: string;
  capabilities: CapabilityDef[];
  storage?: { type: "sqlite" | "memory"; path?: string } | StorageBackend;
  keyPath?: string;
  trust?:
    | "signed"
    | "anchored"
    | {
        level: string;
        anchoring?: {
          cadence?: string;
          maxLag?: number;
          sinks?: CheckpointSink[];
        };
      };
  checkpointPolicy?: CheckpointPolicy;
  authenticate?: (bearer: string) => string | null;
}

export interface ANIPService {
  getDiscovery(opts?: { baseUrl?: string }): Record<string, unknown>;
  getManifest(): ANIPManifest;
  getSignedManifest(): Promise<[Uint8Array, string]>;
  getJwks(): Promise<Record<string, unknown>>;
  authenticateBearer(bearerValue: string): Promise<string | null>;
  resolveBearerToken(jwtString: string): Promise<DelegationToken>;
  issueToken(
    authenticatedPrincipal: string,
    request: Record<string, unknown>,
  ): Promise<Record<string, unknown>>;
  discoverPermissions(token: DelegationToken): Record<string, unknown>;
  invoke(
    capabilityName: string,
    token: DelegationToken,
    params: Record<string, unknown>,
    opts?: {
      clientReferenceId?: string | null;
      stream?: boolean;
      progressSink?: (event: Record<string, unknown>) => Promise<void>;
    },
  ): Promise<Record<string, unknown>>;
  getCapabilityDeclaration(capabilityName: string): Record<string, unknown> | null;
  queryAudit(
    token: DelegationToken,
    filters?: Record<string, unknown>,
  ): Promise<Record<string, unknown>>;
  getCheckpoints(limit?: number): Promise<Record<string, unknown>>;
  getCheckpoint(
    checkpointId: string,
    options?: Record<string, unknown>,
  ): Promise<Record<string, unknown> | null>;
  start(): void;
  stop(): void;
}

// ---------------------------------------------------------------------------
// defineCapability helper
// ---------------------------------------------------------------------------

export function defineCapability(opts: CapabilityDef): CapabilityDef {
  return opts;
}

// ---------------------------------------------------------------------------
// ANIPFailure duck-type guard
// ---------------------------------------------------------------------------

function isANIPFailure(
  value: unknown,
): value is { type: string; detail: string; resolution: unknown; retry: boolean } {
  return (
    typeof value === "object" &&
    value !== null &&
    "type" in value &&
    "detail" in value &&
    "resolution" in value
  );
}

// ---------------------------------------------------------------------------
// Stable JSON serialization (recursive key-sorting)
// ---------------------------------------------------------------------------

function stableStringify(obj: unknown): string {
  if (obj === null || obj === undefined) return "null";
  if (typeof obj === "string") return JSON.stringify(obj);
  if (typeof obj === "number" || typeof obj === "boolean") return String(obj);
  if (Array.isArray(obj)) {
    return `[${obj.map(stableStringify).join(",")}]`;
  }
  const keys = Object.keys(obj as Record<string, unknown>).sort();
  const pairs = keys.map(
    (k) =>
      `${JSON.stringify(k)}:${stableStringify((obj as Record<string, unknown>)[k])}`,
  );
  return `{${pairs.join(",")}}`;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export function createANIPService(opts: ANIPServiceOpts): ANIPService {
  const {
    serviceId,
    capabilities: capDefs,
    keyPath,
    authenticate: authenticateFn,
  } = opts;

  // --- Capability registry ---
  const capabilities = new Map<string, CapabilityDef>();
  const capDeclarations: Record<string, CapabilityDeclaration> = {};
  for (const cap of capDefs) {
    const name = cap.declaration.name;
    capabilities.set(name, cap);
    capDeclarations[name] = cap.declaration;
  }

  // --- Storage ---
  let storage: StorageBackend;
  if (opts.storage === undefined || opts.storage === null) {
    storage = new SQLiteStorage("anip.db");
  } else if (typeof opts.storage === "object" && "storeToken" in opts.storage) {
    // Already a StorageBackend instance
    storage = opts.storage as StorageBackend;
  } else if (typeof opts.storage === "object" && "type" in opts.storage) {
    const storageOpts = opts.storage as { type: string; path?: string };
    if (storageOpts.type === "memory") {
      storage = new InMemoryStorage();
    } else if (storageOpts.type === "sqlite") {
      storage = new SQLiteStorage(storageOpts.path ?? "anip.db");
    } else {
      throw new Error(`Unknown storage type: ${storageOpts.type}`);
    }
  } else {
    storage = new InMemoryStorage();
  }

  // --- Keys ---
  const keys = new KeyManager(keyPath);
  // keys.ready() is awaited lazily before first crypto use

  // --- Delegation engine ---
  const engine = new DelegationEngine(storage, { serviceId });

  // --- Audit log ---
  const audit = new AuditLog(storage, (entry) => keys.signAuditEntry(entry));

  // --- Trust ---
  let trustLevel: string;
  let sinks: CheckpointSink[] = [];

  let anchoringPolicy: {
    cadence?: string | null;
    max_lag?: number | null;
    sink?: string[] | null;
  } | null = null;

  if (typeof opts.trust === "string" || opts.trust === undefined) {
    trustLevel = opts.trust ?? "signed";
  } else {
    trustLevel = opts.trust.level ?? "signed";
    const anchoringCfg = opts.trust.anchoring;
    if (anchoringCfg) {
      sinks = anchoringCfg.sinks ?? [];
      const sinkUris: string[] = [];
      for (const s of sinks) {
        if ("uri" in s) {
          sinkUris.push((s as unknown as { uri: string }).uri);
        } else if ("directory" in s) {
          sinkUris.push(
            `file://${(s as unknown as { directory: string }).directory}`,
          );
        }
      }
      anchoringPolicy = {
        cadence: anchoringCfg.cadence ?? null,
        max_lag: anchoringCfg.maxLag ?? null,
        sink: sinkUris.length > 0 ? sinkUris : null,
      };
    }
  }

  if (trustLevel === "attested") {
    throw new Error(
      "Attested trust requires witness sinks — not yet supported.",
    );
  }

  const trustPosture = {
    level: trustLevel as "signed" | "anchored",
    anchoring: anchoringPolicy,
  };

  // --- Manifest ---
  const serviceIdentity = {
    id: serviceId,
    jwks_uri: "/.well-known/jwks.json",
    issuer_mode: "first-party",
  };
  const manifest = buildManifest({
    capabilities: capDeclarations,
    trust: trustPosture,
    serviceIdentity,
  });

  // --- Checkpoint scheduling ---
  const checkpointPolicy = opts.checkpointPolicy ?? null;
  let scheduler: CheckpointScheduler | null = null;
  let entriesSinceCheckpoint = 0;

  if (trustLevel === "anchored" && checkpointPolicy) {
    scheduler = new CheckpointScheduler(
      60, // default interval
      () => createAndPublishCheckpoint(),
      () => entriesSinceCheckpoint > 0,
    );
  }

  // --- Internal helpers ---

  async function ensureKeys(): Promise<void> {
    await keys.ready();
  }

  async function logAudit(
    capability: string,
    token: DelegationToken,
    auditOpts: {
      success: boolean;
      failureType?: string | null;
      resultSummary?: Record<string, unknown> | null;
      costActual?: Record<string, unknown> | null;
      invocationId?: string | null;
      clientReferenceId?: string | null;
      streamSummary?: Record<string, unknown> | null;
    },
  ): Promise<void> {
    const chain = await engine.getChain(token);
    await audit.logEntry({
      capability,
      token_id: token.token_id,
      root_principal: await engine.getRootPrincipal(token),
      success: auditOpts.success,
      failure_type: auditOpts.failureType ?? null,
      result_summary: auditOpts.resultSummary ?? null,
      cost_actual: auditOpts.costActual ?? null,
      delegation_chain: chain.map((t) => t.token_id),
      invocation_id: auditOpts.invocationId ?? null,
      client_reference_id: auditOpts.clientReferenceId ?? null,
      streamSummary: auditOpts.streamSummary ?? null,
    });

    entriesSinceCheckpoint++;
    if (
      checkpointPolicy &&
      checkpointPolicy.shouldCheckpoint(entriesSinceCheckpoint)
    ) {
      createAndPublishCheckpoint();
    }
  }

  async function createAndPublishCheckpoint(): Promise<void> {
    try {
      const snapshot = audit.getMerkleSnapshot();
      const lastCkpt = await getLastCheckpoint();
      // Get the checkpoint body without signing (signFn is sync, our signer is async)
      const { body } = createCheckpoint({
        merkleSnapshot: snapshot,
        serviceId,
        previousCheckpoint: lastCkpt,
      });
      // Sign asynchronously with the dedicated audit key
      await ensureKeys();
      const canonicalBytes = new TextEncoder().encode(stableStringify(body));
      const signature = await keys.signJWSDetachedAudit(
        new Uint8Array(canonicalBytes),
      );
      await storage.storeCheckpoint(body, signature);
      for (const sink of sinks) {
        sink.publish({ body, signature });
      }
      entriesSinceCheckpoint = 0;
    } catch {
      // Checkpoint failures are non-fatal
    }
  }

  async function getLastCheckpoint(): Promise<Record<string, unknown> | null> {
    const rows = await storage.getCheckpoints(10000);
    return rows.length > 0 ? rows[rows.length - 1] : null;
  }

  function summarizeResult(
    result: Record<string, unknown>,
  ): Record<string, unknown> {
    const summary: Record<string, unknown> = {};
    const resultKeys = Object.keys(result).slice(0, 5);
    for (const key of resultKeys) {
      const val = result[key];
      if (
        typeof val === "string" ||
        typeof val === "number" ||
        typeof val === "boolean" ||
        val === null
      ) {
        summary[key] = val;
      } else if (Array.isArray(val)) {
        summary[key] = `[${val.length} items]`;
      } else {
        summary[key] = "...";
      }
    }
    return summary;
  }

  async function rebuildMerkleTo(sequenceNumber: number): Promise<MerkleTree> {
    const entries = await storage.getAuditEntriesRange(1, sequenceNumber);
    const tree = new MerkleTree();
    for (const row of entries) {
      const filtered: Record<string, unknown> = {};
      for (const key of Object.keys(row).sort()) {
        if (key !== "signature" && key !== "id") {
          filtered[key] = row[key];
        }
      }
      tree.addLeaf(Buffer.from(JSON.stringify(filtered)));
    }
    return tree;
  }

  // --- Build service object ---

  const service: ANIPService = {
    getDiscovery(opts?: { baseUrl?: string }): Record<string, unknown> {
      const capsSummary: Record<string, unknown> = {};
      for (const [name, cap] of capabilities) {
        const decl = cap.declaration;
        capsSummary[name] = {
          description: decl.description,
          side_effect: decl.side_effect?.type ?? null,
          minimum_scope: decl.minimum_scope,
          financial: decl.cost?.financial != null,
          contract: decl.contract_version,
        };
      }

      const doc: Record<string, unknown> = {
        protocol: PROTOCOL_VERSION,
        compliance: "anip-compliant",
        profile: { ...DEFAULT_PROFILE },
        auth: {
          delegation_token_required: true,
          supported_formats: ["anip-v1"],
          minimum_scope_for_discovery: "none",
        },
        capabilities: capsSummary,
        trust_level: trustLevel,
        endpoints: {
          manifest: "/anip/manifest",
          permissions: "/anip/permissions",
          invoke: "/anip/invoke/{capability}",
          tokens: "/anip/tokens",
          audit: "/anip/audit",
          checkpoints: "/anip/checkpoints",
          jwks: "/.well-known/jwks.json",
        },
      };

      if (opts?.baseUrl != null) {
        doc.base_url = opts.baseUrl;
      }

      return { anip_discovery: doc };
    },

    getManifest(): ANIPManifest {
      return manifest;
    },

    async getSignedManifest(): Promise<[Uint8Array, string]> {
      await ensureKeys();
      const bodyStr = stableStringify(manifest);
      const bodyBytes = new TextEncoder().encode(bodyStr);
      const signature = await keys.signJWSDetached(bodyBytes);
      return [bodyBytes, signature];
    },

    async getJwks(): Promise<Record<string, unknown>> {
      await ensureKeys();
      return keys.getJWKS();
    },

    async authenticateBearer(bearerValue: string): Promise<string | null> {
      // Try bootstrap auth (API keys, external auth)
      if (authenticateFn) {
        const principal = authenticateFn(bearerValue);
        if (principal !== null) {
          return principal;
        }
      }

      // Try ANIP JWT
      try {
        const stored = await service.resolveBearerToken(bearerValue);
        return await engine.getRootPrincipal(stored);
      } catch {
        // Not a valid JWT
      }

      return null;
    },

    async resolveBearerToken(jwtString: string): Promise<DelegationToken> {
      await ensureKeys();

      let claims: Record<string, unknown>;
      try {
        claims = await keys.verifyJWT(jwtString, {
          audience: serviceId,
          issuer: serviceId,
        });
      } catch (exc) {
        throw new ANIPError(
          "invalid_token",
          exc instanceof Error ? exc.message : String(exc),
        );
      }

      const tokenId = claims.jti as string | undefined;
      if (!tokenId) {
        throw new ANIPError("invalid_token", "JWT missing jti claim");
      }

      const stored = await engine.getToken(tokenId);
      if (stored === null) {
        throw new ANIPError("invalid_token", `Unknown token: ${tokenId}`);
      }

      // TRUST BOUNDARY: compare signed claims against stored token fields.
      const mismatches: string[] = [];

      if (claims.sub !== stored.subject) {
        mismatches.push(
          `sub: jwt=${String(claims.sub)} store=${stored.subject}`,
        );
      }

      const jwtScope = (claims.scope as string[]) ?? [];
      const storedScope = stored.scope ?? [];
      if (
        JSON.stringify([...jwtScope].sort()) !==
        JSON.stringify([...storedScope].sort())
      ) {
        mismatches.push(
          `scope: jwt=${JSON.stringify(jwtScope)} store=${JSON.stringify(storedScope)}`,
        );
      }

      const storedCapability = stored.purpose?.capability ?? null;
      if (claims.capability !== storedCapability) {
        mismatches.push(
          `capability: jwt=${String(claims.capability)} store=${String(storedCapability)}`,
        );
      }

      const jwtRoot = claims.root_principal as string | undefined;
      const storedRoot = await engine.getRootPrincipal(stored);
      if (jwtRoot === undefined || jwtRoot === null) {
        mismatches.push("root_principal: missing from JWT claims");
      } else if (jwtRoot !== storedRoot) {
        mismatches.push(
          `root_principal: jwt=${jwtRoot} store=${storedRoot}`,
        );
      }

      const jwtParent = (claims.parent_token_id as string | null) ?? null;
      if (jwtParent !== stored.parent) {
        mismatches.push(
          `parent: jwt=${String(jwtParent)} store=${String(stored.parent)}`,
        );
      }

      const jwtConstraints = claims.constraints as
        | Record<string, unknown>
        | undefined;
      if (jwtConstraints === undefined || jwtConstraints === null) {
        mismatches.push("constraints: missing from JWT claims");
      } else {
        const storedConstraints = stored.constraints as unknown as Record<
          string,
          unknown
        >;
        if (
          JSON.stringify(jwtConstraints) !== JSON.stringify(storedConstraints)
        ) {
          mismatches.push(
            `constraints: jwt=${JSON.stringify(jwtConstraints)} store=${JSON.stringify(storedConstraints)}`,
          );
        }
      }

      if (mismatches.length > 0) {
        throw new ANIPError(
          "invalid_token",
          `JWT/store mismatch: ${mismatches.join("; ")}`,
        );
      }

      return stored;
    },

    async issueToken(
      authenticatedPrincipal: string,
      request: Record<string, unknown>,
    ): Promise<Record<string, unknown>> {
      await ensureKeys();

      const parentTokenId = request.parent_token as string | undefined;
      const ttlHours = (request.ttl_hours as number) ?? 2;

      let result:
        | { token: DelegationToken; tokenId: string }
        | Awaited<ReturnType<DelegationEngine["delegate"]>>;

      if (parentTokenId) {
        // Delegation from existing token
        const parent = await engine.getToken(parentTokenId);
        if (parent === null) {
          throw new ANIPError(
            "invalid_token",
            `Parent token not found: ${parentTokenId}`,
          );
        }

        // TRUST BOUNDARY: only the delegatee (parent's subject) can sub-delegate.
        if (authenticatedPrincipal !== parent.subject) {
          throw new ANIPError(
            "insufficient_authority",
            `Caller '${authenticatedPrincipal}' is not the parent token's ` +
              `subject ('${parent.subject}') — only the delegatee can sub-delegate`,
          );
        }

        result = await engine.delegate({
          parentToken: parent,
          subject: (request.subject as string) ?? authenticatedPrincipal,
          scope: (request.scope as string[]) ?? [],
          capability: request.capability as string,
          purposeParameters: request.purpose_parameters as
            | Record<string, unknown>
            | undefined,
          ttlHours,
        });
      } else {
        // Root token
        result = await engine.issueRootToken({
          authenticatedPrincipal,
          subject: (request.subject as string) ?? authenticatedPrincipal,
          scope: (request.scope as string[]) ?? [],
          capability: request.capability as string,
          purposeParameters: request.purpose_parameters as
            | Record<string, unknown>
            | undefined,
          ttlHours,
        });
      }

      // Check for delegation failure
      if (isANIPFailure(result)) {
        throw new ANIPError(result.type, result.detail);
      }

      const { token, tokenId } = result as {
        token: DelegationToken;
        tokenId: string;
      };

      // Build and sign JWT
      const now = Math.floor(Date.now() / 1000);
      const exp = now + ttlHours * 3600;

      const claims: Record<string, unknown> = {
        jti: tokenId,
        iss: serviceId,
        sub: token.subject,
        aud: serviceId,
        iat: now,
        exp,
        scope: token.scope,
        root_principal: token.root_principal,
      };

      // Top-level claims checked by resolveBearerToken trust boundary
      if (token.purpose) {
        claims.capability = token.purpose.capability;
        claims.purpose = token.purpose;
      }
      claims.parent_token_id = token.parent;
      if (token.constraints) {
        claims.constraints = token.constraints;
      }

      const jwtStr = await keys.signJWT(claims);

      return {
        issued: true,
        token_id: tokenId,
        token: jwtStr,
        expires: new Date(exp * 1000).toISOString(),
      };
    },

    discoverPermissions(token: DelegationToken): Record<string, unknown> {
      return discoverPermissions(
        token,
        capDeclarations,
      ) as unknown as Record<string, unknown>;
    },

    getCapabilityDeclaration(capabilityName: string): Record<string, unknown> | null {
      const cap = capabilities.get(capabilityName);
      return cap ? (cap.declaration as Record<string, unknown>) : null;
    },

    async invoke(
      capabilityName: string,
      token: DelegationToken,
      params: Record<string, unknown>,
      opts?: {
        clientReferenceId?: string | null;
        stream?: boolean;
        progressSink?: (event: Record<string, unknown>) => Promise<void>;
      },
    ): Promise<Record<string, unknown>> {
      const invocationId = `inv-${randomUUID().replace(/-/g, "").slice(0, 12)}`;
      const clientReferenceId = opts?.clientReferenceId ?? null;

      // 1. Check capability exists
      if (!capabilities.has(capabilityName)) {
        return {
          success: false,
          failure: {
            type: "unknown_capability",
            detail: `Capability '${capabilityName}' not found`,
          },
          invocation_id: invocationId,
          client_reference_id: clientReferenceId,
        };
      }

      const cap = capabilities.get(capabilityName)!;
      const decl = cap.declaration;

      // Check streaming support
      const stream = opts?.stream ?? false;
      const progressSink = opts?.progressSink ?? null;
      if (stream) {
        const responseModes = (decl as any).response_modes ?? ["unary"];
        if (!responseModes.includes("streaming")) {
          return {
            success: false,
            failure: {
              type: "streaming_not_supported",
              detail: `Capability '${capabilityName}' does not support streaming`,
            },
            invocation_id: invocationId,
            client_reference_id: clientReferenceId,
          };
        }
      }

      // 2. Validate delegation
      const minScope = decl.minimum_scope ?? [];
      const validationResult = await engine.validateDelegation(
        token,
        minScope,
        capabilityName,
      );

      // Check for validation failure
      if (isANIPFailure(validationResult)) {
        const failure = {
          type: validationResult.type,
          detail: validationResult.detail,
          resolution: validationResult.resolution,
        };
        await logAudit(capabilityName, token, {
          success: false,
          failureType: failure.type,
          invocationId,
          clientReferenceId,
        });
        return {
          success: false,
          failure,
          invocation_id: invocationId,
          client_reference_id: clientReferenceId,
        };
      }

      // Use the resolved/stored token from validation
      const resolvedToken = validationResult as DelegationToken;

      // 3. Build invocation context
      const chain = await engine.getChain(resolvedToken);
      let costActual: Record<string, unknown> | null = null;
      let eventsEmitted = 0;
      let eventsDelivered = 0;
      let clientDisconnected = false;
      const streamStart = stream ? performance.now() : 0;

      const ctx: InvocationContext = {
        token: resolvedToken,
        rootPrincipal: await engine.getRootPrincipal(resolvedToken),
        subject: resolvedToken.subject,
        scopes: resolvedToken.scope ?? [],
        delegationChain: chain.map((t) => t.token_id),
        invocationId,
        clientReferenceId,
        setCostActual(cost: Record<string, unknown>): void {
          costActual = cost;
        },
        async emitProgress(payload: Record<string, unknown>): Promise<void> {
          if (!stream) return;
          eventsEmitted++;
          if (progressSink) {
            try {
              await progressSink({
                invocation_id: invocationId,
                client_reference_id: clientReferenceId,
                payload,
              });
              eventsDelivered++;
            } catch {
              clientDisconnected = true;
            }
          }
        },
      };

      // 4. Call handler
      try {
        const result = await cap.handler(ctx, params);

        // 5. Build stream summary (before audit so it can be persisted)
        let streamSummary: Record<string, unknown> | null = null;
        if (stream) {
          streamSummary = {
            response_mode: "streaming",
            events_emitted: eventsEmitted,
            events_delivered: eventsDelivered,
            duration_ms: Math.round(performance.now() - streamStart),
            client_disconnected: clientDisconnected,
          };
        }

        // 6. Log audit (success)
        await logAudit(capabilityName, resolvedToken, {
          success: true,
          resultSummary: summarizeResult(result),
          costActual,
          invocationId,
          clientReferenceId,
          streamSummary,
        });

        // 7. Build response
        const response: Record<string, unknown> = {
          success: true,
          result,
          invocation_id: invocationId,
          client_reference_id: clientReferenceId,
        };
        if (costActual) {
          response.cost_actual = costActual;
        }
        if (streamSummary) {
          response.stream_summary = streamSummary;
        }

        return response;
      } catch (err) {
        const failStreamSummary = stream
          ? {
              response_mode: "streaming",
              events_emitted: eventsEmitted,
              events_delivered: eventsDelivered,
              duration_ms: Math.round(performance.now() - streamStart),
              client_disconnected: clientDisconnected,
            }
          : null;

        if (err instanceof ANIPError) {
          await logAudit(capabilityName, resolvedToken, {
            success: false,
            failureType: err.errorType,
            resultSummary: { detail: err.detail },
            invocationId,
            clientReferenceId,
            streamSummary: failStreamSummary,
          });
          const response: Record<string, unknown> = {
            success: false,
            failure: { type: err.errorType, detail: err.detail },
            invocation_id: invocationId,
            client_reference_id: clientReferenceId,
          };
          if (failStreamSummary) {
            response.stream_summary = failStreamSummary;
          }
          return response;
        }

        // Unexpected error — do NOT leak details
        await logAudit(capabilityName, resolvedToken, {
          success: false,
          failureType: "internal_error",
          invocationId,
          clientReferenceId,
          streamSummary: failStreamSummary,
        });
        const response: Record<string, unknown> = {
          success: false,
          failure: { type: "internal_error", detail: "Internal error" },
          invocation_id: invocationId,
          client_reference_id: clientReferenceId,
        };
        if (failStreamSummary) {
          response.stream_summary = failStreamSummary;
        }
        return response;
      }
    },

    async queryAudit(
      token: DelegationToken,
      filters?: Record<string, unknown>,
    ): Promise<Record<string, unknown>> {
      const rootPrincipal = await engine.getRootPrincipal(token);
      const f = filters ?? {};

      const entries = await audit.query({
        rootPrincipal,
        capability: f.capability as string | undefined,
        since: f.since as string | undefined,
        invocationId: f.invocation_id as string | undefined,
        clientReferenceId: f.client_reference_id as string | undefined,
        limit: Math.min((f.limit as number) ?? 50, 1000),
      });

      return {
        entries,
        count: entries.length,
        root_principal: rootPrincipal,
        capability_filter: f.capability ?? null,
        since_filter: f.since ?? null,
      };
    },

    async getCheckpoints(limit: number = 10): Promise<Record<string, unknown>> {
      const clampedLimit = Math.min(limit, 100);
      const rows = await storage.getCheckpoints(clampedLimit);

      const checkpoints = rows.map((row) => {
        const rng = (row.range as Record<string, number>) ?? {};
        return {
          checkpoint_id: row.checkpoint_id,
          range: {
            first_sequence:
              rng.first_sequence ?? row.first_sequence,
            last_sequence:
              rng.last_sequence ?? row.last_sequence,
          },
          merkle_root: row.merkle_root,
          previous_checkpoint: row.previous_checkpoint ?? null,
          timestamp: row.timestamp,
          entry_count: row.entry_count,
          signature: row.signature,
        };
      });

      return { checkpoints };
    },

    async getCheckpoint(
      checkpointId: string,
      options?: Record<string, unknown>,
    ): Promise<Record<string, unknown> | null> {
      const row = await storage.getCheckpointById(checkpointId);
      if (row === null) return null;

      const rng = (row.range as Record<string, number>) ?? {};
      const result: Record<string, unknown> = {
        checkpoint: {
          checkpoint_id: row.checkpoint_id,
          range: {
            first_sequence:
              rng.first_sequence ?? row.first_sequence,
            last_sequence:
              rng.last_sequence ?? row.last_sequence,
          },
          merkle_root: row.merkle_root,
          previous_checkpoint: row.previous_checkpoint ?? null,
          timestamp: row.timestamp,
          entry_count: row.entry_count,
          signature: row.signature,
        },
      };

      const opts2 = options ?? {};

      // Inclusion proof
      if (opts2.include_proof && opts2.leaf_index !== undefined) {
        const leafIndex = opts2.leaf_index as number;
        const lastSeq =
          rng.last_sequence ?? (row.last_sequence as number) ?? 0;
        const tree = await rebuildMerkleTo(lastSeq);
        try {
          const proof = tree.inclusionProof(leafIndex);
          result.inclusion_proof = {
            leaf_index: leafIndex,
            path: proof,
            merkle_root: tree.root,
            leaf_count: tree.leafCount,
          };
        } catch {
          // index out of range — skip
        }
      }

      // Consistency proof
      const consistencyFrom = opts2.consistency_from as string | undefined;
      if (consistencyFrom) {
        const oldRow = await storage.getCheckpointById(consistencyFrom);
        if (oldRow) {
          const oldRng = (oldRow.range as Record<string, number>) ?? {};
          const oldLast =
            oldRng.last_sequence ?? (oldRow.last_sequence as number) ?? 0;
          const newLast =
            rng.last_sequence ?? (row.last_sequence as number) ?? 0;
          const oldTree = await rebuildMerkleTo(oldLast);
          const newTree = await rebuildMerkleTo(newLast);
          try {
            const path = newTree.consistencyProof(oldTree.leafCount);
            result.consistency_proof = {
              old_checkpoint_id: consistencyFrom,
              new_checkpoint_id: checkpointId,
              old_size: oldTree.leafCount,
              new_size: newTree.leafCount,
              old_root: oldTree.root,
              new_root: newTree.root,
              path,
            };
          } catch {
            // skip
          }
        }
      }

      return result;
    },

    start(): void {
      if (scheduler) {
        scheduler.start();
      }
    },

    stop(): void {
      if (scheduler) {
        scheduler.stop();
      }
    },
  };

  return service;
}
