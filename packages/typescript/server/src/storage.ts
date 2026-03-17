/**
 * Storage abstraction for ANIP server components.
 *
 * Provides a `StorageBackend` interface with two implementations:
 * - `InMemoryStorage` — suitable for testing and lightweight use.
 * - `SQLiteStorage` — persistent storage backed by better-sqlite3 in a
 *   worker thread for genuine async I/O.
 */

import { Worker } from "node:worker_threads";
import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";

export interface StorageBackend {
  storeToken(tokenData: Record<string, unknown>): Promise<void>;
  loadToken(tokenId: string): Promise<Record<string, unknown> | null>;
  storeAuditEntry(entry: Record<string, unknown>): Promise<void>;
  queryAuditEntries(opts?: {
    capability?: string;
    rootPrincipal?: string;
    since?: string;
    invocationId?: string;
    clientReferenceId?: string;
    eventClass?: string;
    limit?: number;
  }): Promise<Record<string, unknown>[]>;
  getLastAuditEntry(): Promise<Record<string, unknown> | null>;
  getAuditEntriesRange(first: number, last: number): Promise<Record<string, unknown>[]>;
  deleteExpiredAuditEntries(nowIso: string): Promise<number>;
  storeCheckpoint(body: Record<string, unknown>, signature: string): Promise<void>;
  getCheckpoints(limit?: number): Promise<Record<string, unknown>[]>;
  getCheckpointById(checkpointId: string): Promise<Record<string, unknown> | null>;
}

/**
 * In-memory implementation of {@link StorageBackend}.
 *
 * All data is held in plain Maps/arrays — ideal for tests and single-process
 * servers that don't need persistence across restarts.
 */
export class InMemoryStorage implements StorageBackend {
  private tokens = new Map<string, Record<string, unknown>>();
  private auditEntries: Record<string, unknown>[] = [];
  private checkpoints: Record<string, unknown>[] = [];

  async storeToken(tokenData: Record<string, unknown>): Promise<void> {
    this.tokens.set(tokenData.token_id as string, { ...tokenData });
  }

  async loadToken(tokenId: string): Promise<Record<string, unknown> | null> {
    return this.tokens.get(tokenId) ?? null;
  }

  async storeAuditEntry(entry: Record<string, unknown>): Promise<void> {
    this.auditEntries.push({ ...entry });
  }

  async queryAuditEntries(opts?: {
    capability?: string;
    rootPrincipal?: string;
    since?: string;
    invocationId?: string;
    clientReferenceId?: string;
    eventClass?: string;
    limit?: number;
  }): Promise<Record<string, unknown>[]> {
    let results = [...this.auditEntries];
    if (opts?.capability) {
      results = results.filter((e) => e.capability === opts.capability);
    }
    if (opts?.rootPrincipal) {
      results = results.filter((e) => e.root_principal === opts.rootPrincipal);
    }
    if (opts?.since) {
      results = results.filter((e) => (e.timestamp as string) >= opts.since!);
    }
    if (opts?.invocationId) {
      results = results.filter((e) => e.invocation_id === opts.invocationId);
    }
    if (opts?.clientReferenceId) {
      results = results.filter((e) => e.client_reference_id === opts.clientReferenceId);
    }
    if (opts?.eventClass) {
      results = results.filter((e) => e.event_class === opts.eventClass);
    }
    results.sort(
      (a, b) =>
        (b.sequence_number as number) - (a.sequence_number as number),
    );
    return results.slice(0, opts?.limit ?? 50);
  }

  async deleteExpiredAuditEntries(nowIso: string): Promise<number> {
    const before = this.auditEntries.length;
    this.auditEntries = this.auditEntries.filter(
      (e) => e.expires_at == null || (e.expires_at as string) >= nowIso,
    );
    return before - this.auditEntries.length;
  }

  async getLastAuditEntry(): Promise<Record<string, unknown> | null> {
    if (this.auditEntries.length === 0) return null;
    return this.auditEntries.reduce((a, b) =>
      (a.sequence_number as number) > (b.sequence_number as number) ? a : b,
    );
  }

  async getAuditEntriesRange(first: number, last: number): Promise<Record<string, unknown>[]> {
    return this.auditEntries
      .filter((e) => {
        const seq = e.sequence_number as number;
        return seq >= first && seq <= last;
      })
      .sort(
        (a, b) =>
          (a.sequence_number as number) - (b.sequence_number as number),
      );
  }

  async storeCheckpoint(body: Record<string, unknown>, signature: string): Promise<void> {
    this.checkpoints.push({ ...body, signature });
  }

  async getCheckpoints(limit: number = 10): Promise<Record<string, unknown>[]> {
    return this.checkpoints.slice(0, limit);
  }

  async getCheckpointById(checkpointId: string): Promise<Record<string, unknown> | null> {
    return (
      this.checkpoints.find((c) => c.checkpoint_id === checkpointId) ?? null
    );
  }
}

/**
 * SQLite-backed implementation of {@link StorageBackend}.
 *
 * Delegates all synchronous better-sqlite3 calls to a dedicated worker
 * thread so that the main event loop is never blocked. The worker script
 * (`sqlite-worker.ts` / `.js`) owns the database connection and schema.
 */
export class SQLiteStorage implements StorageBackend {
  private worker: Worker;
  private pending = new Map<string, { resolve: Function; reject: Function }>();
  private ready: Promise<void>;

  constructor(dbPath: string = "anip.db") {
    // Resolve the worker script.  Prefer the built .js file because
    // Node worker threads cannot load .ts files without an explicit
    // TS loader (vitest's TS transforms don't propagate to workers).
    //
    // Resolution order:
    //   1. sqlite-worker.js next to this file (production / dist)
    //   2. ../dist/sqlite-worker.js (vitest runs from src/ after tsc)
    //   3. sqlite-worker.ts next to this file (dev without build —
    //      requires a TS-capable runtime like tsx)
    const dir = dirname(fileURLToPath(import.meta.url));
    const jsHere = resolve(dir, "sqlite-worker.js");
    const jsDist = resolve(dir, "../dist/sqlite-worker.js");
    const tsHere = resolve(dir, "sqlite-worker.ts");
    const workerPath = existsSync(jsHere)
      ? jsHere
      : existsSync(jsDist)
        ? jsDist
        : tsHere;

    this.worker = new Worker(workerPath, { workerData: { dbPath } });

    // Wait for the worker to signal it has finished DB init.
    this.ready = new Promise<void>((resolve, reject) => {
      const onReady = (msg: any) => {
        if (msg.type === "ready") {
          this.worker.off("message", onReady);
          resolve();
        }
      };
      this.worker.on("message", onReady);
      this.worker.on("error", reject);
      this.worker.on("exit", (code) => {
        if (code !== 0) reject(new Error(`SQLite worker exited with code ${code} during init`));
      });
    });

    // Route method responses to their pending promises.
    this.worker.on("message", (msg: { id?: string; result?: unknown; error?: string }) => {
      if (!msg.id) return; // skip non-RPC messages (e.g. "ready")
      const p = this.pending.get(msg.id);
      if (p) {
        this.pending.delete(msg.id);
        if (msg.error) p.reject(new Error(msg.error));
        else p.resolve(msg.result);
      }
    });

    // If the worker crashes or exits unexpectedly, reject all in-flight
    // RPCs so callers fail fast instead of hanging indefinitely.
    const rejectAll = (err: unknown) => {
      for (const [id, p] of this.pending) {
        this.pending.delete(id);
        this.worker.unref();
        p.reject(err);
      }
    };
    this.worker.on("error", (err) => rejectAll(err));
    this.worker.on("exit", (code) => {
      if (code !== 0) rejectAll(new Error(`SQLite worker exited unexpectedly with code ${code}`));
    });

    // Allow the process to exit naturally when no RPC calls are in flight.
    // The worker is ref'd while a call is pending and unref'd when idle.
    this.worker.unref();
  }

  /**
   * Send an RPC call to the worker and return a promise for the result.
   * Waits for the worker to be ready before dispatching.
   */
  private async call(method: string, args: unknown[]): Promise<unknown> {
    await this.ready;
    const id = randomUUID();
    // Keep the worker (and therefore the process) alive while a call
    // is in flight; unref again once the promise settles.
    this.worker.ref();
    return new Promise((resolve, reject) => {
      this.pending.set(id, {
        resolve: (v: unknown) => { this.worker.unref(); resolve(v); },
        reject: (e: unknown) => { this.worker.unref(); reject(e); },
      });
      this.worker.postMessage({ id, method, args });
    });
  }

  // -- tokens ---------------------------------------------------------------

  async storeToken(tokenData: Record<string, unknown>): Promise<void> {
    await this.call("storeToken", [tokenData]);
  }

  async loadToken(tokenId: string): Promise<Record<string, unknown> | null> {
    return (await this.call("loadToken", [tokenId])) as Record<string, unknown> | null;
  }

  // -- audit log ------------------------------------------------------------

  async storeAuditEntry(entry: Record<string, unknown>): Promise<void> {
    await this.call("storeAuditEntry", [entry]);
  }

  async queryAuditEntries(opts?: {
    capability?: string;
    rootPrincipal?: string;
    since?: string;
    invocationId?: string;
    clientReferenceId?: string;
    eventClass?: string;
    limit?: number;
  }): Promise<Record<string, unknown>[]> {
    return (await this.call("queryAuditEntries", [opts])) as Record<string, unknown>[];
  }

  async getLastAuditEntry(): Promise<Record<string, unknown> | null> {
    return (await this.call("getLastAuditEntry", [])) as Record<string, unknown> | null;
  }

  async getAuditEntriesRange(first: number, last: number): Promise<Record<string, unknown>[]> {
    return (await this.call("getAuditEntriesRange", [first, last])) as Record<string, unknown>[];
  }

  async deleteExpiredAuditEntries(nowIso: string): Promise<number> {
    return (await this.call("deleteExpiredAuditEntries", [nowIso])) as number;
  }

  // -- checkpoints ----------------------------------------------------------

  async storeCheckpoint(body: Record<string, unknown>, signature: string): Promise<void> {
    await this.call("storeCheckpoint", [body, signature]);
  }

  async getCheckpoints(limit: number = 10): Promise<Record<string, unknown>[]> {
    return (await this.call("getCheckpoints", [limit])) as Record<string, unknown>[];
  }

  async getCheckpointById(checkpointId: string): Promise<Record<string, unknown> | null> {
    return (await this.call("getCheckpointById", [checkpointId])) as Record<string, unknown> | null;
  }

  // -- lifecycle ------------------------------------------------------------

  /**
   * Delete all rows from every table.  Useful in test suites that
   * share a single SQLiteStorage instance across multiple tests.
   */
  async clearAll(): Promise<void> {
    await this.call("clearAll", []);
  }

  /**
   * Gracefully close the database and terminate the worker thread.
   * Call this in test teardown (afterEach / afterAll) to prevent
   * vitest from hanging.
   */
  async terminate(): Promise<void> {
    try {
      await this.call("closeDb", []);
    } catch {
      // Worker may already be dead
    }
    await this.worker.terminate();
  }
}
