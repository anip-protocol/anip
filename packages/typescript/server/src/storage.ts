/**
 * Storage abstraction for ANIP server components.
 *
 * Provides a `StorageBackend` interface with two implementations:
 * - `InMemoryStorage` — suitable for testing and lightweight use.
 * - `SQLiteStorage` — persistent storage backed by better-sqlite3.
 */

import Database from "better-sqlite3";

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
    limit?: number;
  }): Promise<Record<string, unknown>[]>;
  getLastAuditEntry(): Promise<Record<string, unknown> | null>;
  getAuditEntriesRange(first: number, last: number): Promise<Record<string, unknown>[]>;
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
    results.sort(
      (a, b) =>
        (b.sequence_number as number) - (a.sequence_number as number),
    );
    return results.slice(0, opts?.limit ?? 50);
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

// ---------------------------------------------------------------------------
// JSON audit fields that need parse/stringify round-tripping
// ---------------------------------------------------------------------------

const JSON_AUDIT_FIELDS = [
  "parameters",
  "result_summary",
  "cost_actual",
  "delegation_chain",
] as const;

const SCHEMA = `
CREATE TABLE IF NOT EXISTS delegation_tokens (
    token_id TEXT PRIMARY KEY,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    scope TEXT NOT NULL,
    purpose TEXT,
    parent TEXT,
    expires TEXT NOT NULL,
    constraints TEXT,
    root_principal TEXT,
    registered_at TEXT NOT NULL,
    FOREIGN KEY (parent) REFERENCES delegation_tokens(token_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_number INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    capability TEXT NOT NULL,
    token_id TEXT,
    issuer TEXT,
    subject TEXT,
    root_principal TEXT,
    parameters TEXT,
    success INTEGER NOT NULL,
    result_summary TEXT,
    failure_type TEXT,
    cost_actual TEXT,
    delegation_chain TEXT,
    invocation_id TEXT,
    client_reference_id TEXT,
    previous_hash TEXT NOT NULL,
    signature TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_capability ON audit_log(capability);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_root_principal ON audit_log(root_principal);
CREATE INDEX IF NOT EXISTS idx_audit_invocation_id ON audit_log(invocation_id);
CREATE INDEX IF NOT EXISTS idx_audit_client_reference_id ON audit_log(client_reference_id);

CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_id TEXT NOT NULL UNIQUE,
    first_sequence INTEGER,
    last_sequence INTEGER,
    merkle_root TEXT NOT NULL,
    previous_checkpoint TEXT,
    timestamp TEXT,
    entry_count INTEGER,
    signature TEXT NOT NULL
);
`;

/**
 * SQLite-backed implementation of {@link StorageBackend}.
 *
 * Persists delegation tokens, audit log entries, and checkpoints to a local
 * SQLite database via better-sqlite3.  Schema mirrors the Python SDK's
 * `SQLiteStorage`.
 */
export class SQLiteStorage implements StorageBackend {
  private db: Database.Database;

  constructor(dbPath: string = "anip.db") {
    this.db = new Database(dbPath);
    this.db.pragma("journal_mode = WAL");
    this.db.pragma("foreign_keys = ON");
    this.db.exec(SCHEMA);

    // Migration support for existing v0.3 databases
    try {
      this.db.exec("ALTER TABLE audit_log ADD COLUMN invocation_id TEXT");
    } catch {
      // Column may already exist
    }
    try {
      this.db.exec("ALTER TABLE audit_log ADD COLUMN client_reference_id TEXT");
    } catch {
      // Column may already exist
    }
  }

  // -- tokens ---------------------------------------------------------------

  async storeToken(tokenData: Record<string, unknown>): Promise<void> {
    this.db
      .prepare(
        `INSERT INTO delegation_tokens
         (token_id, issuer, subject, scope, purpose, parent,
          expires, constraints, root_principal, registered_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        tokenData.token_id as string,
        tokenData.issuer as string,
        tokenData.subject as string,
        JSON.stringify(tokenData.scope ?? []),
        JSON.stringify(tokenData.purpose ?? null),
        (tokenData.parent as string) ?? null,
        tokenData.expires as string,
        JSON.stringify(tokenData.constraints ?? null),
        (tokenData.root_principal as string) ?? null,
        new Date().toISOString(),
      );
  }

  async loadToken(tokenId: string): Promise<Record<string, unknown> | null> {
    const row = this.db
      .prepare("SELECT * FROM delegation_tokens WHERE token_id = ?")
      .get(tokenId) as Record<string, unknown> | undefined;
    if (row === undefined) return null;
    return {
      token_id: row.token_id,
      issuer: row.issuer,
      subject: row.subject,
      scope: JSON.parse(row.scope as string),
      purpose: row.purpose ? JSON.parse(row.purpose as string) : null,
      parent: row.parent ?? null,
      expires: row.expires,
      constraints: row.constraints
        ? JSON.parse(row.constraints as string)
        : null,
      root_principal: row.root_principal ?? null,
    };
  }

  // -- audit log ------------------------------------------------------------

  async storeAuditEntry(entry: Record<string, unknown>): Promise<void> {
    this.db
      .prepare(
        `INSERT INTO audit_log
         (sequence_number, timestamp, capability, token_id, issuer,
          subject, root_principal, parameters, success, result_summary,
          failure_type, cost_actual, delegation_chain, invocation_id,
          client_reference_id, previous_hash, signature)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        entry.sequence_number as number,
        entry.timestamp as string,
        entry.capability as string,
        (entry.token_id as string) ?? null,
        (entry.issuer as string) ?? null,
        (entry.subject as string) ?? null,
        (entry.root_principal as string) ?? null,
        entry.parameters != null ? JSON.stringify(entry.parameters) : null,
        entry.success ? 1 : 0,
        entry.result_summary != null
          ? JSON.stringify(entry.result_summary)
          : null,
        (entry.failure_type as string) ?? null,
        entry.cost_actual != null ? JSON.stringify(entry.cost_actual) : null,
        entry.delegation_chain != null
          ? JSON.stringify(entry.delegation_chain)
          : null,
        (entry.invocation_id as string) ?? null,
        (entry.client_reference_id as string) ?? null,
        entry.previous_hash as string,
        (entry.signature as string) ?? null,
      );
  }

  private parseAuditRow(row: Record<string, unknown>): Record<string, unknown> {
    const entry: Record<string, unknown> = { ...row };
    for (const field of JSON_AUDIT_FIELDS) {
      if (entry[field] != null && typeof entry[field] === "string") {
        entry[field] = JSON.parse(entry[field] as string);
      }
    }
    entry.success = Boolean(entry.success);
    return entry;
  }

  async queryAuditEntries(opts?: {
    capability?: string;
    rootPrincipal?: string;
    since?: string;
    invocationId?: string;
    clientReferenceId?: string;
    limit?: number;
  }): Promise<Record<string, unknown>[]> {
    const conditions: string[] = [];
    const params: unknown[] = [];

    if (opts?.capability) {
      conditions.push("capability = ?");
      params.push(opts.capability);
    }
    if (opts?.rootPrincipal) {
      conditions.push("root_principal = ?");
      params.push(opts.rootPrincipal);
    }
    if (opts?.since) {
      conditions.push("timestamp >= ?");
      params.push(opts.since);
    }
    if (opts?.invocationId) {
      conditions.push("invocation_id = ?");
      params.push(opts.invocationId);
    }
    if (opts?.clientReferenceId) {
      conditions.push("client_reference_id = ?");
      params.push(opts.clientReferenceId);
    }

    const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
    params.push(opts?.limit ?? 50);

    const rows = this.db
      .prepare(
        `SELECT * FROM audit_log ${where} ORDER BY sequence_number DESC LIMIT ?`,
      )
      .all(...params) as Record<string, unknown>[];

    return rows.map((r) => this.parseAuditRow(r));
  }

  async getLastAuditEntry(): Promise<Record<string, unknown> | null> {
    const row = this.db
      .prepare("SELECT * FROM audit_log ORDER BY sequence_number DESC LIMIT 1")
      .get() as Record<string, unknown> | undefined;
    if (row === undefined) return null;
    return this.parseAuditRow(row);
  }

  async getAuditEntriesRange(first: number, last: number): Promise<Record<string, unknown>[]> {
    const rows = this.db
      .prepare(
        "SELECT * FROM audit_log WHERE sequence_number BETWEEN ? AND ? ORDER BY sequence_number ASC",
      )
      .all(first, last) as Record<string, unknown>[];
    return rows.map((r) => this.parseAuditRow(r));
  }

  // -- checkpoints ----------------------------------------------------------

  async storeCheckpoint(body: Record<string, unknown>, signature: string): Promise<void> {
    const range = (body.range as Record<string, unknown>) ?? {};
    this.db
      .prepare(
        `INSERT INTO checkpoints
         (checkpoint_id, first_sequence, last_sequence, merkle_root,
          previous_checkpoint, timestamp, entry_count, signature)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        body.checkpoint_id as string,
        (range.first_sequence as number) ?? (body.first_sequence as number),
        (range.last_sequence as number) ?? (body.last_sequence as number),
        body.merkle_root as string,
        (body.previous_checkpoint as string) ?? null,
        (body.timestamp as string) ?? null,
        (body.entry_count as number) ?? null,
        signature,
      );
  }

  async getCheckpoints(limit: number = 10): Promise<Record<string, unknown>[]> {
    const rows = this.db
      .prepare("SELECT * FROM checkpoints ORDER BY id ASC LIMIT ?")
      .all(limit) as Record<string, unknown>[];
    return rows.map((row) => ({
      checkpoint_id: row.checkpoint_id,
      range: {
        first_sequence: row.first_sequence,
        last_sequence: row.last_sequence,
      },
      merkle_root: row.merkle_root,
      previous_checkpoint: row.previous_checkpoint ?? null,
      timestamp: row.timestamp,
      entry_count: row.entry_count,
      signature: row.signature,
    }));
  }

  async getCheckpointById(checkpointId: string): Promise<Record<string, unknown> | null> {
    const row = this.db
      .prepare("SELECT * FROM checkpoints WHERE checkpoint_id = ?")
      .get(checkpointId) as Record<string, unknown> | undefined;
    if (row === undefined) return null;
    return {
      checkpoint_id: row.checkpoint_id,
      range: {
        first_sequence: row.first_sequence,
        last_sequence: row.last_sequence,
      },
      merkle_root: row.merkle_root,
      previous_checkpoint: row.previous_checkpoint ?? null,
      timestamp: row.timestamp,
      entry_count: row.entry_count,
      signature: row.signature,
    };
  }
}
