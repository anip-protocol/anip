/**
 * SQLite-backed audit log with hash chain.
 *
 * Mirrors the Python reference server's database.py — persists audit entries
 * so that restarts don't drop the log, sequence numbers, or hash chain.
 */

import Database from "better-sqlite3";
import { createHash } from "crypto";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

let db: Database.Database | null = null;

export interface AuditEntry {
  sequence_number: number;
  capability: string;
  timestamp: string;
  token_id: string;
  root_principal: string;
  success: boolean;
  result_summary: Record<string, unknown> | null;
  failure_type: string | null;
  cost_actual: Record<string, unknown> | null;
  cost_variance: Record<string, unknown> | null;
  delegation_chain: string[];
  previous_hash: string;
  signature: string | null;
}

function getConnection(): Database.Database {
  if (db !== null) return db;

  const dbPath =
    process.env.ANIP_DB_PATH ?? resolve(__dirname, "../../anip.db");
  db = new Database(dbPath);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  initSchema(db);
  return db;
}

function initSchema(conn: Database.Database): void {
  conn.exec(`
    CREATE TABLE IF NOT EXISTS audit_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sequence_number INTEGER NOT NULL,
      timestamp TEXT NOT NULL,
      capability TEXT NOT NULL,
      token_id TEXT,
      root_principal TEXT,
      success INTEGER NOT NULL,
      result_summary TEXT,
      failure_type TEXT,
      cost_actual TEXT,
      cost_variance TEXT,
      delegation_chain TEXT,
      previous_hash TEXT NOT NULL,
      signature TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_audit_capability ON audit_log(capability);
    CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
    CREATE INDEX IF NOT EXISTS idx_audit_root_principal ON audit_log(root_principal);
  `);
}

function computeEntryHash(entry: Record<string, unknown>): string {
  const filtered: Record<string, unknown> = {};
  for (const key of Object.keys(entry).sort()) {
    if (key !== "signature" && key !== "id") {
      filtered[key] = entry[key];
    }
  }
  const canonical = JSON.stringify(filtered);
  return `sha256:${createHash("sha256").update(canonical).digest("hex")}`;
}

export function logAuditEntry(
  entryData: Omit<AuditEntry, "sequence_number" | "previous_hash" | "signature">,
  signFn: ((data: Record<string, unknown>) => Promise<string>) | null = null,
): AuditEntry {
  const conn = getConnection();

  // Get last entry for chain continuity
  const lastRow = conn
    .prepare(
      "SELECT sequence_number, timestamp, capability, token_id, root_principal, " +
        "success, result_summary, failure_type, cost_actual, cost_variance, " +
        "delegation_chain, previous_hash, signature " +
        "FROM audit_log ORDER BY sequence_number DESC LIMIT 1"
    )
    .get() as Record<string, unknown> | undefined;

  let sequenceNumber: number;
  let previousHash: string;

  if (lastRow === undefined) {
    sequenceNumber = 1;
    previousHash = "sha256:0";
  } else {
    sequenceNumber = (lastRow.sequence_number as number) + 1;
    // Reconstruct entry for hashing (parse JSON fields)
    const lastEntry: Record<string, unknown> = {
      ...lastRow,
      success: Boolean(lastRow.success),
    };
    for (const field of [
      "result_summary",
      "failure_type",
      "cost_actual",
      "cost_variance",
      "delegation_chain",
    ]) {
      if (typeof lastEntry[field] === "string") {
        lastEntry[field] = JSON.parse(lastEntry[field] as string);
      }
    }
    previousHash = computeEntryHash(lastEntry);
  }

  const entry: AuditEntry = {
    sequence_number: sequenceNumber,
    ...entryData,
    previous_hash: previousHash,
    signature: null,
  };

  // Insert (signature is set asynchronously after if signFn provided)
  conn
    .prepare(
      `INSERT INTO audit_log
       (sequence_number, timestamp, capability, token_id, root_principal,
        success, result_summary, failure_type, cost_actual, cost_variance,
        delegation_chain, previous_hash, signature)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
    )
    .run(
      entry.sequence_number,
      entry.timestamp,
      entry.capability,
      entry.token_id,
      entry.root_principal,
      entry.success ? 1 : 0,
      entry.result_summary ? JSON.stringify(entry.result_summary) : null,
      entry.failure_type,
      entry.cost_actual ? JSON.stringify(entry.cost_actual) : null,
      entry.cost_variance ? JSON.stringify(entry.cost_variance) : null,
      JSON.stringify(entry.delegation_chain),
      entry.previous_hash,
      null,
    );

  // Sign asynchronously and update
  if (signFn !== null) {
    const signData: Record<string, unknown> = { ...entry };
    signFn(signData)
      .then((sig) => {
        entry.signature = sig;
        conn
          .prepare(
            "UPDATE audit_log SET signature = ? WHERE sequence_number = ?"
          )
          .run(sig, entry.sequence_number);
      })
      .catch(() => {
        // If signing fails, leave signature null
      });
  }

  return entry;
}

export function queryAuditLog(opts: {
  rootPrincipal: string;
  capability?: string | null;
  since?: string | null;
  limit?: number;
}): AuditEntry[] {
  const conn = getConnection();
  const conditions: string[] = ["root_principal = ?"];
  const params: unknown[] = [opts.rootPrincipal];

  if (opts.capability) {
    conditions.push("capability = ?");
    params.push(opts.capability);
  }
  if (opts.since) {
    conditions.push("timestamp >= ?");
    params.push(opts.since);
  }

  const limit = Math.min(opts.limit ?? 100, 1000);
  const where = `WHERE ${conditions.join(" AND ")}`;

  const rows = conn
    .prepare(
      `SELECT sequence_number, timestamp, capability, token_id, root_principal,
              success, result_summary, failure_type, cost_actual, cost_variance,
              delegation_chain, previous_hash, signature
       FROM audit_log ${where} ORDER BY sequence_number DESC LIMIT ?`
    )
    .all(...params, limit) as Record<string, unknown>[];

  return rows.map((row) => ({
    sequence_number: row.sequence_number as number,
    capability: row.capability as string,
    timestamp: row.timestamp as string,
    token_id: row.token_id as string,
    root_principal: row.root_principal as string,
    success: Boolean(row.success),
    result_summary: row.result_summary
      ? (JSON.parse(row.result_summary as string) as Record<string, unknown>)
      : null,
    failure_type: (row.failure_type as string) ?? null,
    cost_actual: row.cost_actual
      ? (JSON.parse(row.cost_actual as string) as Record<string, unknown>)
      : null,
    cost_variance: row.cost_variance
      ? (JSON.parse(row.cost_variance as string) as Record<string, unknown>)
      : null,
    delegation_chain: row.delegation_chain
      ? (JSON.parse(row.delegation_chain as string) as string[])
      : [],
    previous_hash: row.previous_hash as string,
    signature: (row.signature as string) ?? null,
  }));
}
