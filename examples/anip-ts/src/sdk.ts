/**
 * Shared SDK instances for the ANIP flight demo.
 *
 * Centralises construction of the DelegationEngine, AuditLog, and KeyManager
 * so every module in the example operates on the same storage / key material.
 *
 * Supports lazy initialization: calling `ensureInit()` from any module
 * guarantees the singletons exist, using ANIP_DB_PATH and ANIP_KEY_PATH
 * env vars (defaulting to in-memory / ephemeral if not set).
 */

import { KeyManager } from "@anip/crypto";
import {
  DelegationEngine,
  AuditLog,
  InMemoryStorage,
  SQLiteStorage,
  MerkleTree,
  CheckpointPolicy,
  type StorageBackend,
} from "@anip/server";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

// ---------------------------------------------------------------------------
// Singleton instances — initialised by `initSDK()` or `ensureInit()`
// ---------------------------------------------------------------------------

export let engine: DelegationEngine;
export let auditLog: AuditLog;
export let keys: KeyManager;
export let storage: StorageBackend;

/**
 * The live Merkle tree that accumulates audit entries.  Used for checkpoints
 * and inclusion/consistency proofs at the HTTP layer.
 */
export let merkleTree: MerkleTree;

// --- Auto-checkpointing state ---
export let checkpointPolicy: CheckpointPolicy | null = null;
export let entriesSinceCheckpoint = 0;
export let lastCheckpointTime: number = Date.now();
export let currentSignFn: ((payload: Buffer) => Promise<string>) | null = null;

export function setCheckpointPolicy(policy: CheckpointPolicy): void {
  checkpointPolicy = policy;
}

export function setCheckpointSignFn(signFn: (payload: Buffer) => Promise<string>): void {
  currentSignFn = signFn;
}

export function hasNewEntriesSinceCheckpoint(): boolean {
  return entriesSinceCheckpoint > 0;
}

export function getEntriesSinceCheckpoint(): number {
  return entriesSinceCheckpoint;
}

export function incrementEntriesSinceCheckpoint(): void {
  entriesSinceCheckpoint++;
}

export function resetCheckpointCounters(): void {
  entriesSinceCheckpoint = 0;
  lastCheckpointTime = Date.now();
}

let _initialized = false;

/**
 * Bootstrap all SDK singletons.
 *
 * @param keyPath  filesystem path for persisted keys (or undefined for ephemeral)
 * @param dbPath   SQLite path (`:memory:` for tests, or InMemoryStorage)
 * @param serviceId  ANIP service identifier
 */
export function initSDK(
  keyPath: string | undefined,
  dbPath: string,
  serviceId: string,
): void {
  if (_initialized) return;
  _initialized = true;

  keys = new KeyManager(keyPath);

  if (dbPath === ":memory:") {
    storage = new InMemoryStorage();
  } else {
    storage = new SQLiteStorage(dbPath);
  }

  engine = new DelegationEngine(storage, { serviceId });
  merkleTree = new MerkleTree();

  // AuditLog — signer delegates to KeyManager (async; logEntry awaits it)
  auditLog = new AuditLog(storage, (entry) => keys.signAuditEntry(entry));
}

/**
 * Ensure the SDK is initialized. If not yet initialized, uses env vars
 * or sensible defaults.
 */
export function ensureInit(): void {
  if (_initialized) return;
  const dbPath = process.env.ANIP_DB_PATH ?? ":memory:";
  const keyPath = process.env.ANIP_KEY_PATH ?? undefined;
  initSDK(keyPath, dbPath, "anip-flight-service");
}

/**
 * Reset initialization state (for tests that need to reinit).
 */
export function resetSDK(): void {
  _initialized = false;
  entriesSinceCheckpoint = 0;
  lastCheckpointTime = Date.now();
  checkpointPolicy = null;
  currentSignFn = null;
}
