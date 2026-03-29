/**
 * ANIP service runtime — the main developer-facing builder.
 *
 * `createANIPService(opts)` returns an ANIPService object that owns all
 * SDK instances (keys, storage, delegation engine, audit log) and exposes
 * domain-level operations — no HTTP types.
 */

import { randomUUID } from "node:crypto";
import { hostname } from "node:os";

import type {
  ANIPManifest,
  CapabilityDeclaration,
  DelegationToken,
} from "@anip-dev/core";
import { PROTOCOL_VERSION, DEFAULT_PROFILE } from "@anip-dev/core";
import { KeyManager } from "@anip-dev/crypto";
import {
  AuditLog,
  buildManifest,
  CheckpointPolicy,
  CheckpointScheduler,
  DelegationEngine,
  discoverPermissions,
  InMemoryStorage,
  MerkleTree,
  reconstructAndCreateCheckpoint,
  RetentionEnforcer,
  SQLiteStorage,
  type CheckpointSink,
  type StorageBackend,
} from "@anip-dev/server";

import { ANIPError } from "./types.js";
import type { CapabilityDef, Handler, InvocationContext } from "./types.js";
import type { ANIPHooks, LoggingHooks, TracingHooks, HealthReport } from "./hooks.js";
import { AuditAggregator, type AggregatedEntry } from "./aggregation.js";
import { classifyEvent } from "./classification.js";
import { resolveDisclosureLevel } from "./disclosure.js";
import { redactFailure } from "./redaction.js";
import { RetentionPolicy } from "./retention.js";
import { storageRedactEntry } from "./storage-redaction.js";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface ANIPServiceOpts {
  serviceId: string;
  capabilities: CapabilityDef[];
  storage?: { type: "sqlite" | "memory"; path?: string } | StorageBackend | string;
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
  authenticate?: (bearer: string) => string | null | Promise<string | null>;
  retentionPolicy?: RetentionPolicy;
  disclosureLevel?: string;
  disclosurePolicy?: Record<string, string>;
  aggregationWindow?: number;
  hooks?: ANIPHooks;
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
  getHealth(): HealthReport;
  start(): Promise<void>;
  stop(): void;
  shutdown(): Promise<void>;
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

  // --- Observability hooks (v0.11) ---
  const hooks = opts.hooks ?? {};
  const logHooks = hooks.logging;
  const metricsHooks = hooks.metrics;
  const tracingHooks = hooks.tracing;

  // --- Safe hook invocation helper ---
  // Hooks are optional instrumentation and must never affect correctness.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function safeHook(fn: ((...args: any[]) => void) | undefined, payload: any): void {
    try { fn?.(payload); } catch { /* hook must not affect correctness */ }
  }

  // --- withSpan helper (tracing) ---
  function withSpan<T>(
    name: string,
    attrs: Record<string, string | number | boolean>,
    parentSpan: unknown | undefined,
    fn: (span: unknown) => T,
  ): T {
    if (!tracingHooks?.startSpan) return fn(undefined);
    let span: unknown;
    try {
      span = tracingHooks.startSpan({ name, attributes: attrs, parentSpan });
    } catch {
      // startSpan threw — skip tracing entirely and run fn without a span
      return fn(undefined);
    }
    try {
      const result = fn(span);
      if (result instanceof Promise) {
        return result.then(
          (v) => { try { tracingHooks.endSpan?.({ span, status: "ok" }); } catch { /* swallow */ } return v; },
          (e: any) => { try { tracingHooks.endSpan?.({ span, status: "error", errorType: e?.name, errorMessage: e?.message }); } catch { /* swallow */ } throw e; },
        ) as T;
      }
      try { tracingHooks.endSpan?.({ span, status: "ok" }); } catch { /* swallow */ }
      return result;
    } catch (e: any) {
      try { tracingHooks.endSpan?.({ span, status: "error", errorType: e?.name, errorMessage: e?.message }); } catch { /* swallow */ }
      throw e;
    }
  }

  // --- Disclosure level (v0.8) ---
  const disclosureLevel = opts.disclosureLevel ?? "full";
  const disclosurePolicy = opts.disclosurePolicy ?? undefined;

  // --- Retention policy (v0.8) ---
  const retentionPolicy = opts.retentionPolicy ?? new RetentionPolicy();

  // --- Capability registry ---
  const capabilities = new Map<string, CapabilityDef>();
  const capDeclarations: Record<string, CapabilityDeclaration> = {};
  for (const cap of capDefs) {
    const name = cap.declaration.name;
    capabilities.set(name, cap);
    capDeclarations[name] = cap.declaration;
  }

  // --- Storage ---
  // Postgres DSN is stored so the async start() can lazily import and create
  // the backend — createANIPService is synchronous, and dynamic import() is
  // async, so we cannot resolve it here.
  let storage: StorageBackend;
  let isPostgresBackend = false;
  let postgresDsn: string | null = null;
  if (opts.storage === undefined || opts.storage === null) {
    storage = new SQLiteStorage("anip.db");
  } else if (typeof opts.storage === "string" && opts.storage.startsWith("postgres")) {
    // Defer Postgres backend creation to start() where we can use dynamic import.
    // Use InMemoryStorage as a temporary placeholder — it will be replaced in start().
    postgresDsn = opts.storage;
    storage = new InMemoryStorage(); // placeholder, replaced in start()
    isPostgresBackend = true;
  } else if (typeof opts.storage === "object" && "storeToken" in opts.storage) {
    // Already a StorageBackend instance
    storage = opts.storage as StorageBackend;
    // Duck-type detection for Postgres: check for the `initialize` method
    // that only PostgresStorage exposes.
    isPostgresBackend = typeof (storage as unknown as Record<string, unknown>).initialize === "function"
      && typeof (storage as unknown as Record<string, unknown>).close === "function";
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
  const exclusiveTtl = 60;
  let engine = new DelegationEngine(storage, { serviceId, exclusiveTtl });

  // --- Audit log ---
  let audit = new AuditLog(storage, (entry) => keys.signAuditEntry(entry));

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
  let lastCheckpointAt: string | null = null; // Updated only when a checkpoint is actually published

  function getHolderId(): string {
    return `${hostname()}:${process.pid}`;
  }

  async function leaderCheckpointTick(): Promise<void> {
    const holder = getHolderId();
    const acquired = await storage.tryAcquireLeader("checkpoint", holder, 120);
    if (!acquired) return;
    try {
      await withSpan("anip.checkpoint.create", {}, undefined, async () => {
        const result = await reconstructAndCreateCheckpoint({
          storage,
          serviceId,
        });
        if (result) {
          // Sign asynchronously with the dedicated audit key
          await ensureKeys();
          const canonicalBytes = new TextEncoder().encode(stableStringify(result.body));
          const signature = await keys.signJWSDetachedAudit(
            new Uint8Array(canonicalBytes),
          );
          await storage.storeCheckpoint(result.body, signature);
          for (const sink of sinks) {
            sink.publish({ body: result.body, signature });
          }
          safeHook(logHooks?.onCheckpointCreated, {
            checkpointId: result.body.checkpoint_id as string,
            entryCount: result.body.entry_count as number,
            merkleRoot: result.body.merkle_root as string,
            timestamp: new Date().toISOString(),
          });
          // Lag = time since previous checkpoint *publication* (not scheduler tick).
          const lagSeconds = lastCheckpointAt
            ? Math.round((Date.now() - new Date(lastCheckpointAt).getTime()) / 1000)
            : 0;
          safeHook(metricsHooks?.onCheckpointCreated, { lagSeconds });
          lastCheckpointAt = new Date().toISOString();
        }
      });
    } catch (e) {
      safeHook(metricsHooks?.onCheckpointFailed, { error: String(e) });
      throw e;
    } finally {
      await storage.releaseLeader("checkpoint", holder);
    }
  }

  if (trustLevel === "anchored" && checkpointPolicy) {
    scheduler = new CheckpointScheduler(
      60, // default interval
      leaderCheckpointTick,
      {
        onError: (error) => {
          try { hooks.diagnostics?.onBackgroundError?.({ source: "checkpoint", error, timestamp: new Date().toISOString() }); } catch { /* hook must not affect correctness */ }
        },
      },
    );
  }

  // --- Retention enforcer (v0.8) ---
  // When Postgres is the backend, skip audit retention enforcement
  // — Postgres handles row TTL natively or via external policy.
  let retentionEnforcer = new RetentionEnforcer(storage, 60, {
    skipAuditRetention: isPostgresBackend,
    onSweep: (deletedCount, durationMs) => {
      safeHook(logHooks?.onRetentionSweep, { deletedCount, durationMs, timestamp: new Date().toISOString() });
      safeHook(metricsHooks?.onRetentionDeleted, { count: deletedCount });
    },
    onError: (error) => {
      try { hooks.diagnostics?.onBackgroundError?.({ source: "retention", error, timestamp: new Date().toISOString() }); } catch { /* hook must not affect correctness */ }
    },
  });

  // --- Audit aggregation (v0.9) ---
  const aggregator: AuditAggregator | null =
    opts.aggregationWindow != null
      ? new AuditAggregator({ windowSeconds: opts.aggregationWindow })
      : null;
  const aggregationWindow = opts.aggregationWindow ?? null;
  let flushTimer: ReturnType<typeof setInterval> | null = null;

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
      eventClass?: string | null;
      retentionTier?: string | null;
      expiresAt?: string | null;
      parentSpan?: unknown;
    },
  ): Promise<void> {
    const chain = await engine.getChain(token);
    const entryData: Record<string, unknown> = {
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
      event_class: auditOpts.eventClass ?? null,
      retention_tier: auditOpts.retentionTier ?? null,
      expires_at: auditOpts.expiresAt ?? null,
    };

    // Apply storage-side redaction (after classification, before persistence)
    const redactedEntry = storageRedactEntry(entryData);

    // Route low-value denials through the aggregator when enabled
    if (aggregator && auditOpts.eventClass === "malformed_or_spam") {
      redactedEntry.timestamp = new Date().toISOString();
      aggregator.submit(redactedEntry);
      return;
    }

    await withSpan("anip.audit.append", { capability }, auditOpts.parentSpan, async () => {
      const auditStart = performance.now();
      let stored: Record<string, unknown>;
      try {
        stored = await audit.logEntry(redactedEntry);
      } catch (e) {
        const auditDurationMs = Math.round(performance.now() - auditStart);
        safeHook(metricsHooks?.onAuditAppendDuration, { durationMs: auditDurationMs, success: false });
        throw e;
      }
      const auditDurationMs = Math.round(performance.now() - auditStart);
      safeHook(metricsHooks?.onAuditAppendDuration, { durationMs: auditDurationMs, success: true });
      safeHook(logHooks?.onAuditAppend, {
        sequenceNumber: (stored.sequence_number as number) ?? 0,
        capability,
        invocationId: (auditOpts.invocationId as string) ?? "",
        success: auditOpts.success,
        timestamp: new Date().toISOString(),
      });
    });
  }

  async function flushAggregator(): Promise<void> {
    if (!aggregator) return;
    await withSpan("anip.aggregation.flush", {}, undefined, async () => {
      const results = aggregator.flush(new Date());
      let entriesFlushed = 0;
      for (const item of results) {
        let entry: Record<string, unknown>;
        if (typeof item === "object" && item !== null && "toAuditDict" in item) {
          entry = storageRedactEntry((item as AggregatedEntry).toAuditDict());
        } else {
          entry = storageRedactEntry(item as Record<string, unknown>);
        }
        await audit.logEntry(entry);
        entriesFlushed++;
      }
      safeHook(logHooks?.onAggregationFlush, {
        windowCount: results.length,
        entriesFlushed,
        timestamp: new Date().toISOString(),
      });
      safeHook(metricsHooks?.onAggregationFlushed, { windowCount: results.length });
    });
  }

  async function runWithExclusiveHeartbeat(
    storageRef: StorageBackend,
    key: string,
    holder: string,
    ttl: number,
    handler: () => Promise<unknown>,
  ): Promise<unknown> {
    const timer = setInterval(async () => {
      await storageRef.tryAcquireExclusive(key, holder, ttl);
    }, (ttl / 2) * 1000);
    try {
      return await handler();
    } finally {
      clearInterval(timer);
    }
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
    if (entries.length < sequenceNumber) {
      throw new Error(
        `Cannot rebuild proof: audit entries have been deleted by retention enforcement. ` +
        `Expected ${sequenceNumber} entries, found ${entries.length}.`
      );
    }
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

      const isAnchored = trustLevel === "anchored" || trustLevel === "attested";

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
        posture: {
          audit: {
            enabled: true,
            signed: true,
            queryable: true,
            retention: retentionPolicy.defaultRetention,
            retention_enforced: retentionEnforcer.isRunning() && !isPostgresBackend,
          },
          lineage: {
            invocation_id: true,
            client_reference_id: {
              supported: true,
              max_length: 256,
              opaque: true,
              propagation: "bounded",
            },
          },
          metadata_policy: {
            bounded_lineage: true,
            freeform_context: false,
            downstream_propagation: "minimal",
          },
          failure_disclosure: {
            detail_level: disclosureLevel,
            caller_classes: disclosureLevel === "policy" && disclosurePolicy
              ? Object.keys(disclosurePolicy)
              : null,
          },
          anchoring: {
            enabled: isAnchored,
            cadence: anchoringPolicy?.cadence ?? null,
            max_lag: anchoringPolicy?.max_lag ?? null,
            proofs_available: isAnchored && checkpointPolicy !== null,
          },
        },
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
        const principal = await authenticateFn(bearerValue);
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

      // Apply caller_class from request
      const callerClass = request.caller_class as string | undefined;
      if (callerClass != null) {
        (token as Record<string, unknown>).caller_class = callerClass;
      }

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
      if (token.caller_class != null) {
        claims["anip:caller_class"] = token.caller_class;
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
      const invokeStartTime = performance.now();
      const invocationId = `inv-${randomUUID().replace(/-/g, "").slice(0, 12)}`;
      const clientReferenceId = opts?.clientReferenceId ?? null;

      // Resolve effective disclosure level for this caller
      const effectiveLevel = resolveDisclosureLevel(
        disclosureLevel,
        token ? { "anip:caller_class": token.caller_class, scope: token.scope } : null,
        disclosurePolicy,
      );

      // Wrap entire invoke body in a root tracing span
      return withSpan("anip.invoke", { capability: capabilityName }, undefined, async (rootSpan) => {

      // 1. Check capability exists
      if (!capabilities.has(capabilityName)) {
        const durationMs = performance.now() - invokeStartTime;
        safeHook(logHooks?.onInvocationEnd,{
          capability: capabilityName,
          invocationId,
          success: false,
          failureType: "unknown_capability",
          durationMs,
          timestamp: new Date().toISOString(),
        });
        safeHook(metricsHooks?.onInvocationDuration,{ capability: capabilityName, durationMs, success: false });
        return {
          success: false,
          failure: redactFailure({
            type: "unknown_capability",
            detail: `Capability '${capabilityName}' not found`,
          }, effectiveLevel),
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
          const durationMs = performance.now() - invokeStartTime;
          safeHook(logHooks?.onInvocationEnd,{
            capability: capabilityName,
            invocationId,
            success: false,
            failureType: "streaming_not_supported",
            durationMs,
            timestamp: new Date().toISOString(),
          });
          safeHook(metricsHooks?.onInvocationDuration,{ capability: capabilityName, durationMs, success: false });
          return {
            success: false,
            failure: redactFailure({
              type: "streaming_not_supported",
              detail: `Capability '${capabilityName}' does not support streaming`,
            }, effectiveLevel),
            invocation_id: invocationId,
            client_reference_id: clientReferenceId,
          };
        }
      }

      // 2. Validate delegation
      const minScope = decl.minimum_scope ?? [];
      const validationResult = await withSpan("anip.delegation.validate", { capability: capabilityName }, rootSpan, async () => {
        return engine.validateDelegation(
          token,
          minScope,
          capabilityName,
        );
      });

      // Check for validation failure
      if (isANIPFailure(validationResult)) {
        const failure = {
          type: validationResult.type,
          detail: validationResult.detail,
          resolution: validationResult.resolution,
        };
        safeHook(logHooks?.onDelegationFailure,{
          reason: failure.type,
          tokenId: token.token_id ?? null,
          timestamp: new Date().toISOString(),
        });
        safeHook(metricsHooks?.onDelegationDenied,{ reason: failure.type });
        const sideEffectType = (decl as any).side_effect?.type ?? null;
        const eventClass = classifyEvent(sideEffectType, false, failure.type);
        const retTier = retentionPolicy.resolveTier(eventClass);
        const expiresAt = retentionPolicy.computeExpiresAt(retTier);
        await logAudit(capabilityName, token, {
          success: false,
          failureType: failure.type,
          invocationId,
          clientReferenceId,
          eventClass,
          retentionTier: retTier,
          expiresAt,
          parentSpan: rootSpan,
        });
        const delegDurationMs = performance.now() - invokeStartTime;
        safeHook(logHooks?.onInvocationEnd,{
          capability: capabilityName,
          invocationId,
          success: false,
          failureType: failure.type,
          durationMs: delegDurationMs,
          timestamp: new Date().toISOString(),
        });
        safeHook(metricsHooks?.onInvocationDuration,{ capability: capabilityName, durationMs: delegDurationMs, success: false });
        return {
          success: false,
          failure: redactFailure(failure, effectiveLevel),
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

      const ctxRootPrincipal = await engine.getRootPrincipal(resolvedToken);
      const ctx: InvocationContext = {
        token: resolvedToken,
        rootPrincipal: ctxRootPrincipal,
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
              safeHook(metricsHooks?.onStreamingDeliveryFailure, { capability: capabilityName });
            }
          }
        },
      };

      safeHook(logHooks?.onInvocationStart, {
        capability: capabilityName,
        invocationId,
        clientReferenceId,
        rootPrincipal: ctxRootPrincipal,
        subject: resolvedToken.subject,
        timestamp: new Date().toISOString(),
      });

      // 4. Acquire exclusive lock if configured
      let locked = false;
      const lockResult = cap.exclusiveLock
        ? await engine.acquireExclusiveLock(resolvedToken)
        : null;
      if (lockResult) {
        const sideEffectTypeL = (decl as any).side_effect?.type ?? null;
        const eventClassL = classifyEvent(sideEffectTypeL, false, "concurrent_lock");
        const retTierL = retentionPolicy.resolveTier(eventClassL);
        const expiresAtL = retentionPolicy.computeExpiresAt(retTierL);
        await logAudit(capabilityName, resolvedToken, {
          success: false,
          failureType: "concurrent_lock",
          invocationId,
          clientReferenceId,
          eventClass: eventClassL,
          retentionTier: retTierL,
          expiresAt: expiresAtL,
          parentSpan: rootSpan,
        });
        const lockDurationMs = performance.now() - invokeStartTime;
        safeHook(logHooks?.onInvocationEnd,{
          capability: capabilityName,
          invocationId,
          success: false,
          failureType: "concurrent_lock",
          durationMs: lockDurationMs,
          timestamp: new Date().toISOString(),
        });
        safeHook(metricsHooks?.onInvocationDuration,{ capability: capabilityName, durationMs: lockDurationMs, success: false });
        return {
          success: false,
          failure: redactFailure({ type: lockResult.type, detail: lockResult.detail }, effectiveLevel),
          invocation_id: invocationId,
          client_reference_id: clientReferenceId,
        };
      }
      locked = true;

      // 5. Call handler (with exclusive heartbeat renewal if applicable)
      try {
        const runHandler = async () => cap.handler(ctx, params);
        const exclusiveKey = cap.exclusiveLock && resolvedToken.constraints?.concurrent_branches === "exclusive"
          ? `exclusive:${serviceId}:${await engine.getRootPrincipal(resolvedToken)}`
          : null;
        const result = await withSpan("anip.handler.execute", { capability: capabilityName }, rootSpan, async () => {
          return exclusiveKey
            ? await runWithExclusiveHeartbeat(storage, exclusiveKey, getHolderId(), exclusiveTtl, runHandler) as Record<string, unknown>
            : await runHandler();
        });

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
        const sideEffectTypeS = (decl as any).side_effect?.type ?? null;
        const eventClassS = classifyEvent(sideEffectTypeS, true, null);
        const retTierS = retentionPolicy.resolveTier(eventClassS);
        const expiresAtS = retentionPolicy.computeExpiresAt(retTierS);
        await logAudit(capabilityName, resolvedToken, {
          success: true,
          resultSummary: summarizeResult(result),
          costActual,
          invocationId,
          clientReferenceId,
          streamSummary,
          eventClass: eventClassS,
          retentionTier: retTierS,
          expiresAt: expiresAtS,
          parentSpan: rootSpan,
        });

        // Fire streaming summary hook
        if (stream && streamSummary) {
          safeHook(logHooks?.onStreamingSummary,{
            invocationId,
            capability: capabilityName,
            eventsEmitted,
            eventsDelivered,
            clientDisconnected,
            durationMs: streamSummary.duration_ms as number,
            timestamp: new Date().toISOString(),
          });
        }

        const successDurationMs = performance.now() - invokeStartTime;
        safeHook(logHooks?.onInvocationEnd,{
          capability: capabilityName,
          invocationId,
          success: true,
          failureType: null,
          durationMs: successDurationMs,
          timestamp: new Date().toISOString(),
        });
        safeHook(metricsHooks?.onInvocationDuration,{ capability: capabilityName, durationMs: successDurationMs, success: true });

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
          const sideEffectTypeE = (decl as any).side_effect?.type ?? null;
          const eventClassE = classifyEvent(sideEffectTypeE, false, err.errorType);
          const retTierE = retentionPolicy.resolveTier(eventClassE);
          const expiresAtE = retentionPolicy.computeExpiresAt(retTierE);
          await logAudit(capabilityName, resolvedToken, {
            success: false,
            failureType: err.errorType,
            resultSummary: { detail: err.detail },
            invocationId,
            clientReferenceId,
            streamSummary: failStreamSummary,
            eventClass: eventClassE,
            retentionTier: retTierE,
            expiresAt: expiresAtE,
            parentSpan: rootSpan,
          });
          if (stream && failStreamSummary) {
            safeHook(logHooks?.onStreamingSummary,{
              invocationId,
              capability: capabilityName,
              eventsEmitted,
              eventsDelivered,
              clientDisconnected,
              durationMs: failStreamSummary.duration_ms as number,
              timestamp: new Date().toISOString(),
            });
          }
          const anipErrDurationMs = performance.now() - invokeStartTime;
          safeHook(logHooks?.onInvocationEnd,{
            capability: capabilityName,
            invocationId,
            success: false,
            failureType: err.errorType,
            durationMs: anipErrDurationMs,
            timestamp: new Date().toISOString(),
          });
          safeHook(metricsHooks?.onInvocationDuration,{ capability: capabilityName, durationMs: anipErrDurationMs, success: false });
          const response: Record<string, unknown> = {
            success: false,
            failure: redactFailure({ type: err.errorType, detail: err.detail }, effectiveLevel),
            invocation_id: invocationId,
            client_reference_id: clientReferenceId,
          };
          if (failStreamSummary) {
            response.stream_summary = failStreamSummary;
          }
          return response;
        }

        // Unexpected error — do NOT leak details
        const sideEffectTypeU = (decl as any).side_effect?.type ?? null;
        const eventClassU = classifyEvent(sideEffectTypeU, false, "internal_error");
        const retTierU = retentionPolicy.resolveTier(eventClassU);
        const expiresAtU = retentionPolicy.computeExpiresAt(retTierU);
        await logAudit(capabilityName, resolvedToken, {
          success: false,
          failureType: "internal_error",
          invocationId,
          clientReferenceId,
          streamSummary: failStreamSummary,
          eventClass: eventClassU,
          retentionTier: retTierU,
          expiresAt: expiresAtU,
          parentSpan: rootSpan,
        });
        if (stream && failStreamSummary) {
          safeHook(logHooks?.onStreamingSummary,{
            invocationId,
            capability: capabilityName,
            eventsEmitted,
            eventsDelivered,
            clientDisconnected,
            durationMs: failStreamSummary.duration_ms as number,
            timestamp: new Date().toISOString(),
          });
        }
        const internalErrDurationMs = performance.now() - invokeStartTime;
        safeHook(logHooks?.onInvocationEnd,{
          capability: capabilityName,
          invocationId,
          success: false,
          failureType: "internal_error",
          durationMs: internalErrDurationMs,
          timestamp: new Date().toISOString(),
        });
        safeHook(metricsHooks?.onInvocationDuration,{ capability: capabilityName, durationMs: internalErrDurationMs, success: false });
        const response: Record<string, unknown> = {
          success: false,
          failure: redactFailure({ type: "internal_error", detail: "Internal error" }, effectiveLevel),
          invocation_id: invocationId,
          client_reference_id: clientReferenceId,
        };
        if (failStreamSummary) {
          response.stream_summary = failStreamSummary;
        }
        return response;
      } finally {
        if (locked) {
          await engine.releaseExclusiveLock(resolvedToken);
        }
      }

      }); // end withSpan("anip.invoke")
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
        eventClass: f.event_class as string | undefined,
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

      // Compute expires_hint from earliest expiry in the checkpoint's range
      const firstSeq = rng.first_sequence ?? (row.first_sequence as number);
      const lastSeq = rng.last_sequence ?? (row.last_sequence as number);
      if (firstSeq != null && lastSeq != null) {
        const expiresHint = await storage.getEarliestExpiryInRange(
          firstSeq as number,
          lastSeq as number,
        );
        if (expiresHint != null) {
          result.expires_hint = expiresHint;
        }
      }

      const opts2 = options ?? {};

      // Inclusion proof
      if (opts2.include_proof && opts2.leaf_index !== undefined) {
        const leafIndex = opts2.leaf_index as number;
        const lastSeq =
          rng.last_sequence ?? (row.last_sequence as number) ?? 0;
        const proofStart = performance.now();
        try {
          await withSpan("anip.proof.generate", { checkpointId }, undefined, async () => {
            const tree = await rebuildMerkleTo(lastSeq);
            try {
              const proof = tree.inclusionProof(leafIndex);
              result.inclusion_proof = {
                leaf_index: leafIndex,
                path: proof,
                merkle_root: tree.root,
                leaf_count: tree.leafCount,
              };
              safeHook(metricsHooks?.onProofGenerated,{ durationMs: Math.round(performance.now() - proofStart) });
            } catch {
              // index out of range — skip
              safeHook(metricsHooks?.onProofUnavailable,{ reason: "leaf_index_out_of_range" });
            }
          });
        } catch (err: unknown) {
          if (err instanceof Error && err.message.includes("audit entries have been deleted")) {
            result.proof_unavailable = "audit_entries_expired";
            safeHook(metricsHooks?.onProofUnavailable,{ reason: "audit_entries_expired" });
          } else {
            throw err;
          }
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
          const consProofStart = performance.now();
          try {
            await withSpan("anip.proof.generate", { checkpointId }, undefined, async () => {
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
                safeHook(metricsHooks?.onProofGenerated,{ durationMs: Math.round(performance.now() - consProofStart) });
              } catch {
                // skip
                safeHook(metricsHooks?.onProofUnavailable,{ reason: "consistency_proof_failed" });
              }
            });
          } catch (err: unknown) {
            if (err instanceof Error && err.message.includes("audit entries have been deleted")) {
              result.proof_unavailable = "audit_entries_expired";
              safeHook(metricsHooks?.onProofUnavailable,{ reason: "audit_entries_expired" });
            } else {
              throw err;
            }
          }
        }
      }

      return result;
    },

    getHealth(): HealthReport {
      const storageType = isPostgresBackend
        ? "postgres"
        : storage instanceof SQLiteStorage
          ? "sqlite"
          : "memory";

      const checkpointHealth = scheduler
        ? {
            healthy: scheduler.getLastError() === null,
            lastRunAt: scheduler.getLastRunAt(),
            lagSeconds: scheduler.getLastRunAt()
              ? Math.round((Date.now() - new Date(scheduler.getLastRunAt()!).getTime()) / 1000)
              : null,
          }
        : null;

      const retentionHealth = {
        healthy: retentionEnforcer.isRunning() && retentionEnforcer.getLastError() === null,
        lastRunAt: retentionEnforcer.getLastRunAt(),
        lastDeletedCount: retentionEnforcer.getLastDeletedCount(),
      };

      const aggregationHealth = aggregator
        ? { pendingWindows: aggregator.getPendingCount() }
        : null;

      // Derive overall status
      let status: "healthy" | "degraded" | "unhealthy" = "healthy";
      if (checkpointHealth && !checkpointHealth.healthy) status = "degraded";
      if (!retentionHealth.healthy) status = "degraded";

      return {
        status,
        storage: { type: storageType },
        checkpoint: checkpointHealth,
        retention: retentionHealth,
        aggregation: aggregationHealth,
      };
    },

    async start(): Promise<void> {
      // Create Postgres backend if a DSN was provided (deferred from constructor
      // because dynamic import() is async).
      if (postgresDsn) {
        const mod = await import("@anip-dev/server");
        const PgStorage = mod.PostgresStorage as unknown as new (dsn: string) => StorageBackend & { initialize(): Promise<void>; close(): Promise<void> };
        storage = new PgStorage(postgresDsn);
        postgresDsn = null; // Only create once

        // Re-create components that captured the placeholder InMemoryStorage
        // reference so they now use the real Postgres backend.
        engine = new DelegationEngine(storage, { serviceId, exclusiveTtl });
        audit = new AuditLog(storage, (entry) => keys.signAuditEntry(entry));
        retentionEnforcer = new RetentionEnforcer(storage, 60, {
          skipAuditRetention: isPostgresBackend,
          onSweep: (deletedCount, durationMs) => {
            safeHook(logHooks?.onRetentionSweep, { deletedCount, durationMs, timestamp: new Date().toISOString() });
            safeHook(metricsHooks?.onRetentionDeleted, { count: deletedCount });
          },
          onError: (error) => {
            try { hooks.diagnostics?.onBackgroundError?.({ source: "retention", error, timestamp: new Date().toISOString() }); } catch { /* hook must not affect correctness */ }
          },
        });
      }

      // Initialise storage (PostgresStorage needs pool + schema setup).
      if (typeof (storage as unknown as Record<string, unknown>).initialize === "function") {
        await (storage as unknown as { initialize(): Promise<void> }).initialize();
      }

      if (scheduler) {
        scheduler.start();
      }
      retentionEnforcer.start();

      if (aggregator && aggregationWindow != null) {
        flushTimer = setInterval(() => {
          flushAggregator().catch((e: unknown) => {
            try { hooks.diagnostics?.onBackgroundError?.({ source: "aggregation", error: String(e), timestamp: new Date().toISOString() }); } catch { /* hook must not affect correctness */ }
          });
        }, aggregationWindow * 1000);
        flushTimer.unref();
      }
    },

    stop(): void {
      if (scheduler) {
        scheduler.stop();
      }
      retentionEnforcer.stop();
      if (flushTimer !== null) {
        clearInterval(flushTimer);
        flushTimer = null;
      }
    },

    async shutdown(): Promise<void> {
      if (aggregator) {
        await flushAggregator();
      }
      if (typeof (storage as any).close === "function") {
        await (storage as any).close();
      }
    },
  };

  return service;
}
