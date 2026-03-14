/**
 * Storage abstraction for ANIP server components.
 *
 * Provides a `StorageBackend` interface and an `InMemoryStorage` implementation
 * suitable for testing and lightweight use.  An optional `SQLiteStorage` class
 * (using better-sqlite3) may be added in a future release.
 */

export interface StorageBackend {
  storeToken(tokenData: Record<string, unknown>): void;
  loadToken(tokenId: string): Record<string, unknown> | null;
  storeAuditEntry(entry: Record<string, unknown>): void;
  queryAuditEntries(opts?: {
    capability?: string;
    rootPrincipal?: string;
    since?: string;
    limit?: number;
  }): Record<string, unknown>[];
  getLastAuditEntry(): Record<string, unknown> | null;
  getAuditEntriesRange(first: number, last: number): Record<string, unknown>[];
  storeCheckpoint(body: Record<string, unknown>, signature: string): void;
  getCheckpoints(limit?: number): Record<string, unknown>[];
  getCheckpointById(checkpointId: string): Record<string, unknown> | null;
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

  storeToken(tokenData: Record<string, unknown>): void {
    this.tokens.set(tokenData.token_id as string, { ...tokenData });
  }

  loadToken(tokenId: string): Record<string, unknown> | null {
    return this.tokens.get(tokenId) ?? null;
  }

  storeAuditEntry(entry: Record<string, unknown>): void {
    this.auditEntries.push({ ...entry });
  }

  queryAuditEntries(opts?: {
    capability?: string;
    rootPrincipal?: string;
    since?: string;
    limit?: number;
  }): Record<string, unknown>[] {
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
    results.sort(
      (a, b) =>
        (b.sequence_number as number) - (a.sequence_number as number),
    );
    return results.slice(0, opts?.limit ?? 50);
  }

  getLastAuditEntry(): Record<string, unknown> | null {
    if (this.auditEntries.length === 0) return null;
    return this.auditEntries.reduce((a, b) =>
      (a.sequence_number as number) > (b.sequence_number as number) ? a : b,
    );
  }

  getAuditEntriesRange(first: number, last: number): Record<string, unknown>[] {
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

  storeCheckpoint(body: Record<string, unknown>, signature: string): void {
    this.checkpoints.push({ ...body, signature });
  }

  getCheckpoints(limit: number = 10): Record<string, unknown>[] {
    return this.checkpoints.slice(0, limit);
  }

  getCheckpointById(checkpointId: string): Record<string, unknown> | null {
    return (
      this.checkpoints.find((c) => c.checkpoint_id === checkpointId) ?? null
    );
  }
}
