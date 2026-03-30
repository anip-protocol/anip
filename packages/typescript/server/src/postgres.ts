/**
 * PostgreSQL-backed implementation of {@link StorageBackend}.
 *
 * Uses `pg.Pool` for connection pooling and supports true transactional
 * audit-log appends with row-level locking via an `audit_append_head` table.
 *
 * Two-phase lifecycle:
 *   1. `new PostgresStorage(dsn)` — captures connection string only.
 *   2. `await initialize()` — creates the pool, connects, ensures schema.
 *   3. `await close()` — drains the pool.
 */

import { Pool } from "pg";
import type { PoolClient } from "pg";
import { computeEntryHash } from "./hashing.js";
import type { StorageBackend } from "./storage.js";

// ---------------------------------------------------------------------------
// JSON audit fields that need parse/stringify round-tripping
// ---------------------------------------------------------------------------

const JSON_AUDIT_FIELDS = [
  "parameters",
  "result_summary",
  "cost_actual",
  "delegation_chain",
  "stream_summary",
  "grouping_key",
  "aggregation_window",
] as const;

// ---------------------------------------------------------------------------
// SQL schema
// ---------------------------------------------------------------------------

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
    caller_class TEXT,
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    sequence_number BIGINT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL,
    capability TEXT NOT NULL,
    token_id TEXT,
    issuer TEXT,
    subject TEXT,
    root_principal TEXT,
    parameters TEXT,
    success BOOLEAN NOT NULL,
    result_summary TEXT,
    failure_type TEXT,
    cost_actual TEXT,
    delegation_chain TEXT,
    invocation_id TEXT,
    client_reference_id TEXT,
    task_id TEXT,
    parent_invocation_id TEXT,
    stream_summary TEXT,
    previous_hash TEXT NOT NULL,
    signature TEXT,
    event_class TEXT,
    retention_tier TEXT,
    expires_at TEXT,
    storage_redacted BOOLEAN DEFAULT FALSE,
    entry_type TEXT,
    grouping_key TEXT,
    aggregation_window TEXT,
    aggregation_count INTEGER,
    first_seen TEXT,
    last_seen TEXT,
    representative_detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_capability ON audit_log(capability);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_root_principal ON audit_log(root_principal);
CREATE INDEX IF NOT EXISTS idx_audit_invocation_id ON audit_log(invocation_id);
CREATE INDEX IF NOT EXISTS idx_audit_client_reference_id ON audit_log(client_reference_id);
CREATE INDEX IF NOT EXISTS idx_audit_task_id ON audit_log(task_id);
CREATE INDEX IF NOT EXISTS idx_audit_parent_invocation_id ON audit_log(parent_invocation_id);
CREATE INDEX IF NOT EXISTS idx_audit_event_class ON audit_log(event_class);
CREATE INDEX IF NOT EXISTS idx_audit_expires_at ON audit_log(expires_at);

CREATE TABLE IF NOT EXISTS audit_append_head (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_sequence_number BIGINT NOT NULL DEFAULT 0,
    last_hash TEXT NOT NULL DEFAULT 'sha256:0'
);

INSERT INTO audit_append_head (id, last_sequence_number, last_hash)
VALUES (1, 0, 'sha256:0')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS checkpoints (
    id SERIAL PRIMARY KEY,
    checkpoint_id TEXT NOT NULL UNIQUE,
    first_sequence INTEGER,
    last_sequence INTEGER,
    merkle_root TEXT NOT NULL,
    previous_checkpoint TEXT,
    timestamp TEXT,
    entry_count INTEGER,
    signature TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exclusive_leases (
    key TEXT PRIMARY KEY,
    holder TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS leader_leases (
    role TEXT PRIMARY KEY,
    holder TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);
`;

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

export class PostgresStorage implements StorageBackend {
  private pool: Pool | null = null;
  private dsn: string;

  constructor(dsn: string) {
    this.dsn = dsn;
  }

  // -----------------------------------------------------------------------
  // Lifecycle
  // -----------------------------------------------------------------------

  async initialize(): Promise<void> {
    this.pool = new Pool({ connectionString: this.dsn });
    const client = await this.pool.connect();
    try {
      await this.ensureSchema(client);
    } finally {
      client.release();
    }
  }

  async close(): Promise<void> {
    if (this.pool) {
      await this.pool.end();
      this.pool = null;
    }
  }

  private async ensureSchema(client: PoolClient): Promise<void> {
    await client.query(SCHEMA);
  }

  private getPool(): Pool {
    if (!this.pool) {
      throw new Error("PostgresStorage not initialized — call initialize() first");
    }
    return this.pool;
  }

  // -----------------------------------------------------------------------
  // Tokens
  // -----------------------------------------------------------------------

  async storeToken(tokenData: Record<string, unknown>): Promise<void> {
    const pool = this.getPool();
    await pool.query(
      `INSERT INTO delegation_tokens
       (token_id, issuer, subject, scope, purpose, parent,
        expires, constraints, root_principal, caller_class, registered_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)`,
      [
        tokenData.token_id as string,
        tokenData.issuer as string,
        tokenData.subject as string,
        JSON.stringify(tokenData.scope ?? []),
        JSON.stringify(tokenData.purpose ?? null),
        (tokenData.parent as string) ?? null,
        tokenData.expires as string,
        JSON.stringify(tokenData.constraints ?? null),
        (tokenData.root_principal as string) ?? null,
        (tokenData.caller_class as string) ?? null,
        new Date().toISOString(),
      ],
    );
  }

  async loadToken(tokenId: string): Promise<Record<string, unknown> | null> {
    const pool = this.getPool();
    const result = await pool.query(
      "SELECT * FROM delegation_tokens WHERE token_id = $1",
      [tokenId],
    );
    if (result.rows.length === 0) return null;
    const row = result.rows[0];
    return {
      token_id: row.token_id,
      issuer: row.issuer,
      subject: row.subject,
      scope: JSON.parse(row.scope),
      purpose: row.purpose ? JSON.parse(row.purpose) : null,
      parent: row.parent ?? null,
      expires: row.expires,
      constraints: row.constraints ? JSON.parse(row.constraints) : null,
      root_principal: row.root_principal ?? null,
      caller_class: row.caller_class ?? null,
    };
  }

  // -----------------------------------------------------------------------
  // Audit log — legacy (storeAuditEntry)
  // -----------------------------------------------------------------------

  async storeAuditEntry(entry: Record<string, unknown>): Promise<void> {
    const pool = this.getPool();
    await pool.query(
      `INSERT INTO audit_log
       (sequence_number, timestamp, capability, token_id, issuer,
        subject, root_principal, parameters, success, result_summary,
        failure_type, cost_actual, delegation_chain, invocation_id,
        client_reference_id, task_id, parent_invocation_id,
        stream_summary, previous_hash, signature,
        event_class, retention_tier, expires_at,
        storage_redacted, entry_type, grouping_key,
        aggregation_window, aggregation_count, first_seen,
        last_seen, representative_detail)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31)`,
      [
        entry.sequence_number as number,
        entry.timestamp as string,
        entry.capability as string,
        (entry.token_id as string) ?? null,
        (entry.issuer as string) ?? null,
        (entry.subject as string) ?? null,
        (entry.root_principal as string) ?? null,
        entry.parameters != null ? JSON.stringify(entry.parameters) : null,
        entry.success ? true : false,
        entry.result_summary != null ? JSON.stringify(entry.result_summary) : null,
        (entry.failure_type as string) ?? null,
        entry.cost_actual != null ? JSON.stringify(entry.cost_actual) : null,
        entry.delegation_chain != null ? JSON.stringify(entry.delegation_chain) : null,
        (entry.invocation_id as string) ?? null,
        (entry.client_reference_id as string) ?? null,
        (entry.task_id as string) ?? null,
        (entry.parent_invocation_id as string) ?? null,
        entry.stream_summary != null ? JSON.stringify(entry.stream_summary) : null,
        entry.previous_hash as string,
        (entry.signature as string) ?? null,
        (entry.event_class as string) ?? null,
        (entry.retention_tier as string) ?? null,
        (entry.expires_at as string) ?? null,
        entry.storage_redacted ? true : false,
        (entry.entry_type as string) ?? null,
        entry.grouping_key != null ? JSON.stringify(entry.grouping_key) : null,
        entry.aggregation_window != null ? JSON.stringify(entry.aggregation_window) : null,
        (entry.aggregation_count as number) ?? null,
        (entry.first_seen as string) ?? null,
        (entry.last_seen as string) ?? null,
        (entry.representative_detail as string) ?? null,
      ],
    );
  }

  // -----------------------------------------------------------------------
  // Audit log — queries
  // -----------------------------------------------------------------------

  async queryAuditEntries(opts?: {
    capability?: string;
    rootPrincipal?: string;
    since?: string;
    invocationId?: string;
    clientReferenceId?: string;
    taskId?: string;
    parentInvocationId?: string;
    eventClass?: string;
    limit?: number;
  }): Promise<Record<string, unknown>[]> {
    const pool = this.getPool();
    const conditions: string[] = [];
    const params: unknown[] = [];
    let paramIndex = 1;

    if (opts?.capability) {
      conditions.push(`capability = $${paramIndex++}`);
      params.push(opts.capability);
    }
    if (opts?.rootPrincipal) {
      conditions.push(`root_principal = $${paramIndex++}`);
      params.push(opts.rootPrincipal);
    }
    if (opts?.since) {
      conditions.push(`timestamp >= $${paramIndex++}`);
      params.push(opts.since);
    }
    if (opts?.invocationId) {
      conditions.push(`invocation_id = $${paramIndex++}`);
      params.push(opts.invocationId);
    }
    if (opts?.clientReferenceId) {
      conditions.push(`client_reference_id = $${paramIndex++}`);
      params.push(opts.clientReferenceId);
    }
    if (opts?.taskId) {
      conditions.push(`task_id = $${paramIndex++}`);
      params.push(opts.taskId);
    }
    if (opts?.parentInvocationId) {
      conditions.push(`parent_invocation_id = $${paramIndex++}`);
      params.push(opts.parentInvocationId);
    }
    if (opts?.eventClass) {
      conditions.push(`event_class = $${paramIndex++}`);
      params.push(opts.eventClass);
    }

    const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
    params.push(opts?.limit ?? 50);

    const result = await pool.query(
      `SELECT * FROM audit_log ${where} ORDER BY sequence_number DESC LIMIT $${paramIndex}`,
      params,
    );

    return result.rows.map((r) => this.parseAuditRow(r));
  }

  async getLastAuditEntry(): Promise<Record<string, unknown> | null> {
    const pool = this.getPool();
    const result = await pool.query(
      "SELECT * FROM audit_log ORDER BY sequence_number DESC LIMIT 1",
    );
    if (result.rows.length === 0) return null;
    return this.parseAuditRow(result.rows[0]);
  }

  async getAuditEntriesRange(first: number, last: number): Promise<Record<string, unknown>[]> {
    const pool = this.getPool();
    const result = await pool.query(
      "SELECT * FROM audit_log WHERE sequence_number BETWEEN $1 AND $2 ORDER BY sequence_number ASC",
      [first, last],
    );
    return result.rows.map((r) => this.parseAuditRow(r));
  }

  async deleteExpiredAuditEntries(nowIso: string): Promise<number> {
    const pool = this.getPool();
    const result = await pool.query(
      "DELETE FROM audit_log WHERE expires_at IS NOT NULL AND expires_at < $1",
      [nowIso],
    );
    return result.rowCount ?? 0;
  }

  async getEarliestExpiryInRange(firstSeq: number, lastSeq: number): Promise<string | null> {
    const pool = this.getPool();
    const result = await pool.query(
      "SELECT MIN(expires_at) as min_exp FROM audit_log WHERE sequence_number BETWEEN $1 AND $2 AND expires_at IS NOT NULL",
      [firstSeq, lastSeq],
    );
    if (result.rows.length === 0) return null;
    return result.rows[0].min_exp ?? null;
  }

  // -----------------------------------------------------------------------
  // Checkpoints
  // -----------------------------------------------------------------------

  async storeCheckpoint(body: Record<string, unknown>, signature: string): Promise<void> {
    const pool = this.getPool();
    const range = (body.range as Record<string, unknown>) ?? {};
    await pool.query(
      `INSERT INTO checkpoints
       (checkpoint_id, first_sequence, last_sequence, merkle_root,
        previous_checkpoint, timestamp, entry_count, signature)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
      [
        body.checkpoint_id as string,
        (range.first_sequence as number) ?? (body.first_sequence as number) ?? null,
        (range.last_sequence as number) ?? (body.last_sequence as number) ?? null,
        body.merkle_root as string,
        (body.previous_checkpoint as string) ?? null,
        (body.timestamp as string) ?? null,
        (body.entry_count as number) ?? null,
        signature,
      ],
    );
  }

  async getCheckpoints(limit: number = 10): Promise<Record<string, unknown>[]> {
    const pool = this.getPool();
    const result = await pool.query(
      "SELECT * FROM checkpoints ORDER BY id ASC LIMIT $1",
      [limit],
    );
    return result.rows.map((row) => ({
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
    const pool = this.getPool();
    const result = await pool.query(
      "SELECT * FROM checkpoints WHERE checkpoint_id = $1",
      [checkpointId],
    );
    if (result.rows.length === 0) return null;
    const row = result.rows[0];
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

  // -----------------------------------------------------------------------
  // Horizontal-scaling: transactional append
  // -----------------------------------------------------------------------

  async appendAuditEntry(entryData: Record<string, unknown>): Promise<Record<string, unknown>> {
    const pool = this.getPool();
    const client = await pool.connect();
    try {
      await client.query("BEGIN");

      // Row-level lock on the append head
      const headResult = await client.query(
        "SELECT last_sequence_number, last_hash FROM audit_append_head FOR UPDATE",
      );
      const head = headResult.rows[0];
      const lastSequenceNumber = Number(head.last_sequence_number);
      const lastHash = head.last_hash as string;

      const sequenceNumber = lastSequenceNumber + 1;

      // Compute previous_hash: for first entry it's the genesis hash,
      // otherwise compute from the previous entry's data.
      let previousHash: string;
      if (lastSequenceNumber === 0) {
        previousHash = "sha256:0";
      } else {
        // Fetch the previous entry to compute its hash
        const prevResult = await client.query(
          "SELECT * FROM audit_log WHERE sequence_number = $1",
          [lastSequenceNumber],
        );
        if (prevResult.rows.length === 0) {
          previousHash = lastHash;
        } else {
          previousHash = computeEntryHash(this.parseAuditRow(prevResult.rows[0]));
        }
      }

      const entry: Record<string, unknown> = {
        ...entryData,
        sequence_number: sequenceNumber,
        previous_hash: previousHash,
      };

      // Insert the new audit entry
      await client.query(
        `INSERT INTO audit_log
         (sequence_number, timestamp, capability, token_id, issuer,
          subject, root_principal, parameters, success, result_summary,
          failure_type, cost_actual, delegation_chain, invocation_id,
          client_reference_id, task_id, parent_invocation_id,
          stream_summary, previous_hash, signature,
          event_class, retention_tier, expires_at,
          storage_redacted, entry_type, grouping_key,
          aggregation_window, aggregation_count, first_seen,
          last_seen, representative_detail)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31)`,
        [
          sequenceNumber,
          entry.timestamp as string,
          entry.capability as string,
          (entry.token_id as string) ?? null,
          (entry.issuer as string) ?? null,
          (entry.subject as string) ?? null,
          (entry.root_principal as string) ?? null,
          entry.parameters != null ? JSON.stringify(entry.parameters) : null,
          entry.success ? true : false,
          entry.result_summary != null ? JSON.stringify(entry.result_summary) : null,
          (entry.failure_type as string) ?? null,
          entry.cost_actual != null ? JSON.stringify(entry.cost_actual) : null,
          entry.delegation_chain != null ? JSON.stringify(entry.delegation_chain) : null,
          (entry.invocation_id as string) ?? null,
          (entry.client_reference_id as string) ?? null,
          (entry.task_id as string) ?? null,
          (entry.parent_invocation_id as string) ?? null,
          entry.stream_summary != null ? JSON.stringify(entry.stream_summary) : null,
          previousHash,
          (entry.signature as string) ?? null,
          (entry.event_class as string) ?? null,
          (entry.retention_tier as string) ?? null,
          (entry.expires_at as string) ?? null,
          entry.storage_redacted ? true : false,
          (entry.entry_type as string) ?? null,
          entry.grouping_key != null ? JSON.stringify(entry.grouping_key) : null,
          entry.aggregation_window != null ? JSON.stringify(entry.aggregation_window) : null,
          (entry.aggregation_count as number) ?? null,
          (entry.first_seen as string) ?? null,
          (entry.last_seen as string) ?? null,
          (entry.representative_detail as string) ?? null,
        ],
      );

      // Compute the new hash for the head
      const newHash = computeEntryHash(entry);

      // Update the append head
      await client.query(
        "UPDATE audit_append_head SET last_sequence_number = $1, last_hash = $2",
        [sequenceNumber, newHash],
      );

      await client.query("COMMIT");

      return entry;
    } catch (err) {
      await client.query("ROLLBACK");
      throw err;
    } finally {
      client.release();
    }
  }

  async updateAuditSignature(sequenceNumber: number, signature: string): Promise<void> {
    const pool = this.getPool();
    await pool.query(
      "UPDATE audit_log SET signature = $1 WHERE sequence_number = $2",
      [signature, sequenceNumber],
    );
  }

  async getMaxAuditSequence(): Promise<number | null> {
    const pool = this.getPool();
    const result = await pool.query(
      "SELECT MAX(sequence_number) as max_seq FROM audit_log",
    );
    const val = result.rows[0]?.max_seq;
    return val != null ? Number(val) : null;
  }

  // -----------------------------------------------------------------------
  // Exclusive leases
  // -----------------------------------------------------------------------

  async tryAcquireExclusive(key: string, holder: string, ttlSeconds: number): Promise<boolean> {
    const pool = this.getPool();
    const result = await pool.query(
      `INSERT INTO exclusive_leases (key, holder, expires_at)
       VALUES ($1, $2, NOW() + ($3 || ' seconds')::INTERVAL)
       ON CONFLICT (key) DO UPDATE
         SET holder = $2, expires_at = NOW() + ($3 || ' seconds')::INTERVAL
         WHERE exclusive_leases.expires_at < NOW() OR exclusive_leases.holder = $2`,
      [key, holder, String(ttlSeconds)],
    );
    return (result.rowCount ?? 0) > 0;
  }

  async releaseExclusive(key: string, holder: string): Promise<void> {
    const pool = this.getPool();
    await pool.query(
      "DELETE FROM exclusive_leases WHERE key = $1 AND holder = $2",
      [key, holder],
    );
  }

  // -----------------------------------------------------------------------
  // Leader leases
  // -----------------------------------------------------------------------

  async tryAcquireLeader(role: string, holder: string, ttlSeconds: number): Promise<boolean> {
    const pool = this.getPool();
    const result = await pool.query(
      `INSERT INTO leader_leases (role, holder, expires_at)
       VALUES ($1, $2, NOW() + ($3 || ' seconds')::INTERVAL)
       ON CONFLICT (role) DO UPDATE
         SET holder = $2, expires_at = NOW() + ($3 || ' seconds')::INTERVAL
         WHERE leader_leases.expires_at < NOW() OR leader_leases.holder = $2`,
      [role, holder, String(ttlSeconds)],
    );
    return (result.rowCount ?? 0) > 0;
  }

  async releaseLeader(role: string, holder: string): Promise<void> {
    const pool = this.getPool();
    await pool.query(
      "DELETE FROM leader_leases WHERE role = $1 AND holder = $2",
      [role, holder],
    );
  }

  // -----------------------------------------------------------------------
  // Utilities
  // -----------------------------------------------------------------------

  /**
   * Delete all rows from every table. Useful in test suites that share
   * a single PostgresStorage instance across multiple tests.
   */
  async clearAll(): Promise<void> {
    const pool = this.getPool();
    await pool.query("DELETE FROM delegation_tokens");
    await pool.query("DELETE FROM audit_log");
    await pool.query("DELETE FROM checkpoints");
    await pool.query("DELETE FROM exclusive_leases");
    await pool.query("DELETE FROM leader_leases");
    await pool.query("UPDATE audit_append_head SET last_sequence_number = 0, last_hash = 'sha256:0'");
  }

  private parseAuditRow(row: Record<string, unknown>): Record<string, unknown> {
    const entry: Record<string, unknown> = { ...row };
    for (const field of JSON_AUDIT_FIELDS) {
      if (entry[field] != null && typeof entry[field] === "string") {
        entry[field] = JSON.parse(entry[field] as string);
      }
    }
    // Postgres returns booleans natively, but ensure consistency
    entry.success = Boolean(entry.success);
    entry.storage_redacted = Boolean(entry.storage_redacted);
    // Postgres BIGINT comes back as string; coerce sequence_number to number
    if (entry.sequence_number != null) {
      entry.sequence_number = Number(entry.sequence_number);
    }
    return entry;
  }
}
