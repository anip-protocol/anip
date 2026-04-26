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
import { computeEntryHash } from "./hashing.js";
import Database from "better-sqlite3";

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
    session_id TEXT,
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
    task_id TEXT,
    parent_invocation_id TEXT,
    upstream_service TEXT,
    stream_summary TEXT,
    previous_hash TEXT NOT NULL,
    signature TEXT,
    event_class TEXT,
    retention_tier TEXT,
    expires_at TEXT,
    storage_redacted INTEGER DEFAULT 0,
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
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN task_id TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN parent_invocation_id TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN upstream_service TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN stream_summary TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN event_class TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN retention_tier TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN expires_at TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN storage_redacted INTEGER DEFAULT 0");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN entry_type TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN grouping_key TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN aggregation_window TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN aggregation_count INTEGER");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN first_seen TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN last_seen TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE audit_log ADD COLUMN representative_detail TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE delegation_tokens ADD COLUMN caller_class TEXT");
} catch {
  // Column may already exist
}
try {
  db.exec("ALTER TABLE delegation_tokens ADD COLUMN session_id TEXT");
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
      expires, constraints, root_principal, caller_class,
      session_id, registered_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
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
    (tokenData.caller_class as string) ?? null,
    (tokenData.session_id as string) ?? null,
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
    caller_class: row.caller_class ?? null,
    session_id: row.session_id ?? null,
  };
}

function storeAuditEntry(entry: Record<string, unknown>): void {
  db.prepare(
    `INSERT INTO audit_log
     (sequence_number, timestamp, capability, token_id, issuer,
      subject, root_principal, parameters, success, result_summary,
      failure_type, cost_actual, delegation_chain, invocation_id,
      client_reference_id, task_id, parent_invocation_id,
      upstream_service, stream_summary, previous_hash, signature,
      event_class, retention_tier, expires_at,
      storage_redacted, entry_type, grouping_key,
      aggregation_window, aggregation_count, first_seen,
      last_seen, representative_detail)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
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
    (entry.task_id as string) ?? null,
    (entry.parent_invocation_id as string) ?? null,
    (entry.upstream_service as string) ?? null,
    entry.stream_summary != null
      ? JSON.stringify(entry.stream_summary)
      : null,
    entry.previous_hash as string,
    (entry.signature as string) ?? null,
    (entry.event_class as string) ?? null,
    (entry.retention_tier as string) ?? null,
    (entry.expires_at as string) ?? null,
    entry.storage_redacted ? 1 : 0,
    (entry.entry_type as string) ?? null,
    entry.grouping_key != null ? JSON.stringify(entry.grouping_key) : null,
    entry.aggregation_window != null
      ? JSON.stringify(entry.aggregation_window)
      : null,
    (entry.aggregation_count as number) ?? null,
    (entry.first_seen as string) ?? null,
    (entry.last_seen as string) ?? null,
    (entry.representative_detail as string) ?? null,
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
  entry.storage_redacted = Boolean(entry.storage_redacted);
  return entry;
}

function queryAuditEntries(opts?: {
  capability?: string;
  rootPrincipal?: string;
  since?: string;
  invocationId?: string;
  clientReferenceId?: string;
  taskId?: string;
  parentInvocationId?: string;
  eventClass?: string;
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
  if (opts?.taskId) {
    conditions.push("task_id = ?");
    params.push(opts.taskId);
  }
  if (opts?.parentInvocationId) {
    conditions.push("parent_invocation_id = ?");
    params.push(opts.parentInvocationId);
  }
  if (opts?.eventClass) {
    conditions.push("event_class = ?");
    params.push(opts.eventClass);
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

function getEarliestExpiryInRange(firstSeq: number, lastSeq: number): string | null {
  const row = db
    .prepare(
      "SELECT MIN(expires_at) as min_exp FROM audit_log WHERE sequence_number BETWEEN ? AND ? AND expires_at IS NOT NULL",
    )
    .get(firstSeq, lastSeq) as Record<string, unknown> | undefined;
  if (row === undefined) return null;
  return (row.min_exp as string) ?? null;
}

function deleteExpiredAuditEntries(nowIso: string): number {
  const result = db.prepare(
    "DELETE FROM audit_log WHERE expires_at IS NOT NULL AND expires_at < ?",
  ).run(nowIso);
  return result.changes;
}

// ---------------------------------------------------------------------------
// Horizontal-scaling methods
// ---------------------------------------------------------------------------

function appendAuditEntry(entryData: Record<string, unknown>): Record<string, unknown> {
  const last = getLastAuditEntry();
  const sequenceNumber = last === null ? 1 : (last.sequence_number as number) + 1;
  const previousHash = last === null ? "sha256:0" : computeEntryHash(last);
  const entry = { ...entryData, sequence_number: sequenceNumber, previous_hash: previousHash };
  storeAuditEntry(entry);
  return entry;
}

function updateAuditSignature(sequenceNumber: number, signature: string): void {
  db.prepare("UPDATE audit_log SET signature = ? WHERE sequence_number = ?").run(signature, sequenceNumber);
}

function getMaxAuditSequence(): number | null {
  const row = db.prepare("SELECT MAX(sequence_number) as max_seq FROM audit_log").get() as any;
  return row?.max_seq ?? null;
}

// ---------------------------------------------------------------------------
// Method dispatch table
// ---------------------------------------------------------------------------

function closeDb(): void {
  db.close();
}

function clearAll(): void {
  db.exec("DELETE FROM delegation_tokens");
  db.exec("DELETE FROM audit_log");
  db.exec("DELETE FROM checkpoints");
}

const methods: Record<string, (...args: any[]) => unknown> = {
  storeToken,
  loadToken,
  storeAuditEntry,
  queryAuditEntries,
  getLastAuditEntry,
  getAuditEntriesRange,
  getEarliestExpiryInRange,
  deleteExpiredAuditEntries,
  appendAuditEntry,
  updateAuditSignature,
  getMaxAuditSequence,
  storeCheckpoint,
  getCheckpoints,
  getCheckpointById,
  closeDb,
  clearAll,
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
