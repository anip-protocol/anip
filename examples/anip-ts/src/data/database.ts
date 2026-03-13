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
import { MerkleTree } from "../merkle.js";
import { CheckpointPolicy } from "../checkpoint.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

let db: Database.Database | null = null;
const merkleTree = new MerkleTree();

// --- Auto-checkpointing state ---

let checkpointPolicy: CheckpointPolicy | null = null;
let entriesSinceCheckpoint = 0;
let lastCheckpointTime: number = Date.now();
let currentSignFn: ((payload: Buffer) => string) | null = null;

/**
 * Configure the checkpoint policy used for auto-checkpointing on audit write.
 */
export function setCheckpointPolicy(policy: CheckpointPolicy): void {
  checkpointPolicy = policy;
}

/**
 * Set the signing function used for auto-checkpoints.
 */
export function setCheckpointSignFn(signFn: (payload: Buffer) => string): void {
  currentSignFn = signFn;
}

/**
 * Return true when at least one audit entry has been written since the last
 * checkpoint.
 */
export function hasNewEntriesSinceCheckpoint(): boolean {
  return entriesSinceCheckpoint > 0;
}

/**
 * Return current anchoring lag — entries and seconds since the last checkpoint.
 */
export function getAnchoringLag(): { entries: number; seconds: number } {
  return {
    entries: entriesSinceCheckpoint,
    seconds: Math.round((Date.now() - lastCheckpointTime) / 1000),
  };
}

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

    CREATE TABLE IF NOT EXISTS checkpoints (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      checkpoint_id TEXT NOT NULL UNIQUE,
      first_sequence INTEGER NOT NULL,
      last_sequence INTEGER NOT NULL,
      merkle_root TEXT NOT NULL,
      previous_checkpoint TEXT,
      timestamp TEXT NOT NULL,
      entry_count INTEGER NOT NULL,
      signature TEXT NOT NULL
    );
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

  // Accumulate into Merkle tree (canonical JSON with sorted keys, excluding signature and id)
  const merkleData: Record<string, unknown> = {};
  for (const key of Object.keys(entry).sort()) {
    if (key !== "signature" && key !== "id") {
      merkleData[key] = (entry as Record<string, unknown>)[key];
    }
  }
  merkleTree.addLeaf(Buffer.from(JSON.stringify(merkleData)));

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

  // Auto-checkpoint if policy threshold is met
  entriesSinceCheckpoint++;
  if (checkpointPolicy && checkpointPolicy.shouldCheckpoint(entriesSinceCheckpoint)) {
    if (currentSignFn) {
      createCheckpoint(currentSignFn);
      entriesSinceCheckpoint = 0;
      lastCheckpointTime = Date.now();
    }
  }

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

export function getCheckpointById(checkpointId: string): {
  checkpoint_id: string;
  range: { first_sequence: number; last_sequence: number };
  merkle_root: string;
  previous_checkpoint: string | null;
  timestamp: string;
  entry_count: number;
  signature: string;
} | null {
  const conn = getConnection();
  const row = conn
    .prepare("SELECT * FROM checkpoints WHERE checkpoint_id = ?")
    .get(checkpointId) as Record<string, unknown> | undefined;
  if (row === undefined) return null;
  return {
    checkpoint_id: row.checkpoint_id as string,
    range: {
      first_sequence: row.first_sequence as number,
      last_sequence: row.last_sequence as number,
    },
    merkle_root: row.merkle_root as string,
    previous_checkpoint: (row.previous_checkpoint as string) ?? null,
    timestamp: row.timestamp as string,
    entry_count: row.entry_count as number,
    signature: row.signature as string,
  };
}

export function rebuildMerkleTreeTo(sequenceNumber: number): MerkleTree {
  const conn = getConnection();
  const rows = conn
    .prepare(
      "SELECT * FROM audit_log WHERE sequence_number <= ? ORDER BY sequence_number ASC"
    )
    .all(sequenceNumber) as Record<string, unknown>[];

  const tree = new MerkleTree();
  for (const row of rows) {
    const entry: Record<string, unknown> = { ...row };
    entry.success = Boolean(entry.success);
    for (const field of [
      "result_summary",
      "failure_type",
      "cost_actual",
      "cost_variance",
      "delegation_chain",
    ]) {
      if (typeof entry[field] === "string") {
        entry[field] = JSON.parse(entry[field] as string);
      }
    }
    // Build canonical JSON (sorted keys, excluding signature and id)
    const filtered: Record<string, unknown> = {};
    for (const key of Object.keys(entry).sort()) {
      if (key !== "signature" && key !== "id") {
        filtered[key] = entry[key];
      }
    }
    tree.addLeaf(Buffer.from(JSON.stringify(filtered)));
  }
  return tree;
}

export function getMerkleSnapshot() {
  return merkleTree.snapshot();
}

export function getMerkleInclusionProof(index: number) {
  try {
    return {
      path: merkleTree.inclusionProof(index),
      root: merkleTree.root,
      leaf_count: merkleTree.leafCount,
    };
  } catch {
    return null;
  }
}

// --- Checkpoints ---

export interface CheckpointBody {
  version: string;
  service_id: string;
  checkpoint_id: string;
  range: { first_sequence: number; last_sequence: number };
  merkle_root: string;
  previous_checkpoint: string | null;
  timestamp: string;
  entry_count: number;
}

export function storeCheckpoint(body: CheckpointBody, signature: string): void {
  const conn = getConnection();
  conn
    .prepare(
      `INSERT INTO checkpoints
       (checkpoint_id, first_sequence, last_sequence, merkle_root,
        previous_checkpoint, timestamp, entry_count, signature)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    )
    .run(
      body.checkpoint_id,
      body.range.first_sequence,
      body.range.last_sequence,
      body.merkle_root,
      body.previous_checkpoint,
      body.timestamp,
      body.entry_count,
      signature,
    );
}

export function getCheckpoints(limit: number = 10): Array<{
  checkpoint_id: string;
  first_sequence: number;
  last_sequence: number;
  merkle_root: string;
  previous_checkpoint: string | null;
  timestamp: string;
  entry_count: number;
  signature: string;
}> {
  const conn = getConnection();
  const rows = conn
    .prepare("SELECT * FROM checkpoints ORDER BY id ASC LIMIT ?")
    .all(limit) as Record<string, unknown>[];

  return rows.map((row) => ({
    checkpoint_id: row.checkpoint_id as string,
    first_sequence: row.first_sequence as number,
    last_sequence: row.last_sequence as number,
    merkle_root: row.merkle_root as string,
    previous_checkpoint: (row.previous_checkpoint as string) ?? null,
    timestamp: row.timestamp as string,
    entry_count: row.entry_count as number,
    signature: row.signature as string,
  }));
}

export function createCheckpoint(
  signFn: (payload: Buffer) => string,
): [CheckpointBody, string] {
  const snap = getMerkleSnapshot();
  const conn = getConnection();

  // Determine previous checkpoint (if any)
  const prevRow = conn
    .prepare("SELECT * FROM checkpoints ORDER BY id DESC LIMIT 1")
    .get() as Record<string, unknown> | undefined;

  let firstSequence: number;
  let previousCheckpoint: string | null;
  let checkpointNumber: number;

  if (prevRow === undefined) {
    firstSequence = 1;
    previousCheckpoint = null;
    checkpointNumber = 1;
  } else {
    firstSequence = (prevRow.last_sequence as number) + 1;
    // Hash the previous checkpoint body (canonical JSON, sorted keys, no whitespace)
    const prevBody: CheckpointBody = {
      version: "0.3",
      service_id: process.env.ANIP_SERVICE_ID ?? "anip-reference-server",
      checkpoint_id: prevRow.checkpoint_id as string,
      range: {
        first_sequence: prevRow.first_sequence as number,
        last_sequence: prevRow.last_sequence as number,
      },
      merkle_root: prevRow.merkle_root as string,
      previous_checkpoint: (prevRow.previous_checkpoint as string) ?? null,
      timestamp: prevRow.timestamp as string,
      entry_count: prevRow.entry_count as number,
    };
    const prevCanonical = canonicalJson(prevBody);
    previousCheckpoint = `sha256:${createHash("sha256").update(prevCanonical).digest("hex")}`;
    // Extract number from previous checkpoint_id
    const parts = (prevRow.checkpoint_id as string).split("-");
    checkpointNumber = parseInt(parts[1], 10) + 1;
  }

  const lastSequence = snap.leaf_count;
  const entryCount = lastSequence - firstSequence + 1;

  const body: CheckpointBody = {
    version: "0.3",
    service_id: process.env.ANIP_SERVICE_ID ?? "anip-reference-server",
    checkpoint_id: `ckpt-${checkpointNumber}`,
    range: {
      first_sequence: firstSequence,
      last_sequence: lastSequence,
    },
    merkle_root: snap.root,
    previous_checkpoint: previousCheckpoint,
    timestamp: new Date().toISOString(),
    entry_count: entryCount,
  };

  // Sign with detached JWS
  const canonicalBytes = Buffer.from(canonicalJson(body));
  const signature = signFn(canonicalBytes);

  storeCheckpoint(body, signature);

  // Reset auto-checkpoint counters
  entriesSinceCheckpoint = 0;
  lastCheckpointTime = Date.now();

  return [body, signature];
}

/**
 * Produce canonical JSON: sorted keys, no whitespace.
 */
function canonicalJson(obj: unknown): string {
  if (obj === null || obj === undefined) return "null";
  if (typeof obj === "string") return JSON.stringify(obj);
  if (typeof obj === "number" || typeof obj === "boolean") return String(obj);
  if (Array.isArray(obj)) {
    return `[${obj.map(canonicalJson).join(",")}]`;
  }
  const keys = Object.keys(obj as Record<string, unknown>).sort();
  const pairs = keys.map(
    (k) => `${JSON.stringify(k)}:${canonicalJson((obj as Record<string, unknown>)[k])}`,
  );
  return `{${pairs.join(",")}}`;
}
