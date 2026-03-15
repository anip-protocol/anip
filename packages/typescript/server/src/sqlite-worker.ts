/**
 * Worker-thread script for SQLiteStorage.
 *
 * Runs synchronous better-sqlite3 operations off the main event loop.
 * Receives `{ id, method, args }` messages from the parent and replies
 * with `{ id, result }` or `{ id, error }`.
 *
 * This file is an internal implementation detail and is NOT exported
 * from the package's public API.
 */

import { parentPort, workerData } from "node:worker_threads";
import Database from "better-sqlite3";

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

// ---------------------------------------------------------------------------
// Initialise database
// ---------------------------------------------------------------------------

const db = new Database(workerData.dbPath as string);
db.pragma("journal_mode = WAL");
db.pragma("foreign_keys = ON");
db.exec(SCHEMA);

// Migration support for existing v0.3 databases
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN invocation_id TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN client_reference_id TEXT");
} catch {
  // Column may already exist
}

// ---------------------------------------------------------------------------
// Storage method implementations
// ---------------------------------------------------------------------------

function storeToken(tokenData: Record<string, unknown>): void {
  db.prepare(
    `INSERT INTO delegation_tokens
     (token_id, issuer, subject, scope, purpose, parent,
      expires, constraints, root_principal, registered_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
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

function loadToken(tokenId: string): Record<string, unknown> | null {
  const row = db
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

function storeAuditEntry(entry: Record<string, unknown>): void {
  db.prepare(
    `INSERT INTO audit_log
     (sequence_number, timestamp, capability, token_id, issuer,
      subject, root_principal, parameters, success, result_summary,
      failure_type, cost_actual, delegation_chain, invocation_id,
      client_reference_id, previous_hash, signature)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
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

function parseAuditRow(row: Record<string, unknown>): Record<string, unknown> {
  const entry: Record<string, unknown> = { ...row };
  for (const field of JSON_AUDIT_FIELDS) {
    if (entry[field] != null && typeof entry[field] === "string") {
      entry[field] = JSON.parse(entry[field] as string);
    }
  }
  entry.success = Boolean(entry.success);
  return entry;
}

function queryAuditEntries(opts?: {
  capability?: string;
  rootPrincipal?: string;
  since?: string;
  invocationId?: string;
  clientReferenceId?: string;
  limit?: number;
}): Record<string, unknown>[] {
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

  const where =
    conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
  params.push(opts?.limit ?? 50);

  const rows = db
    .prepare(
      `SELECT * FROM audit_log ${where} ORDER BY sequence_number DESC LIMIT ?`,
    )
    .all(...params) as Record<string, unknown>[];

  return rows.map((r) => parseAuditRow(r));
}

function getLastAuditEntry(): Record<string, unknown> | null {
  const row = db
    .prepare("SELECT * FROM audit_log ORDER BY sequence_number DESC LIMIT 1")
    .get() as Record<string, unknown> | undefined;
  if (row === undefined) return null;
  return parseAuditRow(row);
}

function getAuditEntriesRange(
  first: number,
  last: number,
): Record<string, unknown>[] {
  const rows = db
    .prepare(
      "SELECT * FROM audit_log WHERE sequence_number BETWEEN ? AND ? ORDER BY sequence_number ASC",
    )
    .all(first, last) as Record<string, unknown>[];
  return rows.map((r) => parseAuditRow(r));
}

function storeCheckpoint(
  body: Record<string, unknown>,
  signature: string,
): void {
  const range = (body.range as Record<string, unknown>) ?? {};
  db.prepare(
    `INSERT INTO checkpoints
     (checkpoint_id, first_sequence, last_sequence, merkle_root,
      previous_checkpoint, timestamp, entry_count, signature)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
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

function getCheckpoints(limit: number = 10): Record<string, unknown>[] {
  const rows = db
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

function getCheckpointById(
  checkpointId: string,
): Record<string, unknown> | null {
  const row = db
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

// ---------------------------------------------------------------------------
// Method dispatch table
// ---------------------------------------------------------------------------

const methods: Record<string, (...args: any[]) => unknown> = {
  storeToken,
  loadToken,
  storeAuditEntry,
  queryAuditEntries,
  getLastAuditEntry,
  getAuditEntriesRange,
  storeCheckpoint,
  getCheckpoints,
  getCheckpointById,
};

// ---------------------------------------------------------------------------
// Message handler
// ---------------------------------------------------------------------------

parentPort!.on(
  "message",
  (msg: { id: string; method: string; args: unknown[] }) => {
    try {
      const fn = methods[msg.method];
      if (!fn) {
        parentPort!.postMessage({
          id: msg.id,
          error: `Unknown method: ${msg.method}`,
        });
        return;
      }
      const result = fn(...msg.args);
      parentPort!.postMessage({ id: msg.id, result });
    } catch (err: unknown) {
      parentPort!.postMessage({
        id: msg.id,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  },
);

// Signal to parent that the worker is ready
parentPort!.postMessage({ type: "ready" });
