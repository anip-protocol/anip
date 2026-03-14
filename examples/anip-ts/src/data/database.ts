/**
 * Database layer — now delegates to the SDK's AuditLog and StorageBackend.
 *
 * Retains example-specific wiring: auto-checkpointing, sink publication,
 * Merkle tree rebuild for proofs, and anchoring lag tracking.
 */

import { createHash } from "crypto";
import { MerkleTree } from "@anip/server";
import {
  ensureInit,
  checkpointPolicy,
  currentSignFn,
  incrementEntriesSinceCheckpoint,
  resetCheckpointCounters,
  getEntriesSinceCheckpoint,
  lastCheckpointTime,
  auditLog as _auditLog,
  storage as _storage,
  merkleTree as _merkleTree,
} from "../sdk.js";
import { enqueueForSink, getPendingSinkCount } from "../sink-queue.js";

// Re-export SDK state accessors for server.ts and tests
export {
  setCheckpointPolicy,
  setCheckpointSignFn,
  hasNewEntriesSinceCheckpoint,
} from "../sdk.js";

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

/**
 * Return current anchoring lag.
 */
export function getAnchoringLag(): { entries: number; seconds: number; pending_sink_publications: number } {
  return {
    entries: getEntriesSinceCheckpoint(),
    seconds: Math.round((Date.now() - lastCheckpointTime) / 1000),
    pending_sink_publications: getPendingSinkCount(),
  };
}

export async function logAuditEntry(
  entryData: Omit<AuditEntry, "sequence_number" | "previous_hash" | "signature">,
): Promise<AuditEntry> {
  ensureInit();

  // Use the SDK's AuditLog to handle hash chain, sequence numbers, signing, and Merkle
  const sdkEntry = await _auditLog.logEntry({
    capability: entryData.capability,
    token_id: entryData.token_id,
    root_principal: entryData.root_principal,
    success: entryData.success,
    result_summary: entryData.result_summary,
    failure_type: entryData.failure_type,
    cost_actual: entryData.cost_actual,
    delegation_chain: entryData.delegation_chain,
  });

  // Also accumulate into the example-level Merkle tree for proof endpoints
  const merkleData: Record<string, unknown> = {};
  for (const key of Object.keys(sdkEntry).sort()) {
    if (key !== "signature" && key !== "id") {
      merkleData[key] = sdkEntry[key];
    }
  }
  _merkleTree.addLeaf(Buffer.from(JSON.stringify(merkleData)));

  // Auto-checkpoint if policy threshold is met
  incrementEntriesSinceCheckpoint();
  if (checkpointPolicy && checkpointPolicy.shouldCheckpoint(
    getEntriesSinceCheckpoint()
  )) {
    if (currentSignFn) {
      createCheckpoint(currentSignFn).catch(() => {});
    }
  }

  return {
    sequence_number: sdkEntry.sequence_number as number,
    capability: sdkEntry.capability as string,
    timestamp: sdkEntry.timestamp as string,
    token_id: sdkEntry.token_id as string,
    root_principal: sdkEntry.root_principal as string,
    success: sdkEntry.success as boolean,
    result_summary: sdkEntry.result_summary as Record<string, unknown> | null,
    failure_type: (sdkEntry.failure_type as string) ?? null,
    cost_actual: sdkEntry.cost_actual as Record<string, unknown> | null,
    cost_variance: (entryData.cost_variance as Record<string, unknown>) ?? null,
    delegation_chain: (sdkEntry.delegation_chain as string[]) ?? [],
    previous_hash: sdkEntry.previous_hash as string,
    signature: (sdkEntry.signature as string) ?? null,
  };
}

export function queryAuditLog(opts: {
  rootPrincipal: string;
  capability?: string | null;
  since?: string | null;
  limit?: number;
}): AuditEntry[] {
  ensureInit();
  const entries = _auditLog.query({
    rootPrincipal: opts.rootPrincipal,
    capability: opts.capability ?? undefined,
    since: opts.since ?? undefined,
    limit: opts.limit,
  });

  return entries.map((row) => ({
    sequence_number: row.sequence_number as number,
    capability: row.capability as string,
    timestamp: row.timestamp as string,
    token_id: row.token_id as string,
    root_principal: row.root_principal as string,
    success: Boolean(row.success),
    result_summary: row.result_summary as Record<string, unknown> | null,
    failure_type: (row.failure_type as string) ?? null,
    cost_actual: row.cost_actual as Record<string, unknown> | null,
    cost_variance: (row.cost_variance as Record<string, unknown>) ?? null,
    delegation_chain: (row.delegation_chain as string[]) ?? [],
    previous_hash: row.previous_hash as string,
    signature: (row.signature as string) ?? null,
  }));
}

export function getMerkleSnapshot() {
  ensureInit();
  return _merkleTree.snapshot();
}

export function getMerkleInclusionProof(index: number) {
  ensureInit();
  try {
    return {
      path: _merkleTree.inclusionProof(index),
      root: _merkleTree.root,
      leaf_count: _merkleTree.leafCount,
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

export function getCheckpointById(checkpointId: string): {
  checkpoint_id: string;
  range: { first_sequence: number; last_sequence: number };
  merkle_root: string;
  previous_checkpoint: string | null;
  timestamp: string;
  entry_count: number;
  signature: string;
} | null {
  ensureInit();
  const row = _storage.getCheckpointById(checkpointId);
  if (row === null) return null;
  const range = (row.range as Record<string, number>) ?? {};
  return {
    checkpoint_id: row.checkpoint_id as string,
    range: {
      first_sequence: (range.first_sequence ?? row.first_sequence) as number,
      last_sequence: (range.last_sequence ?? row.last_sequence) as number,
    },
    merkle_root: row.merkle_root as string,
    previous_checkpoint: (row.previous_checkpoint as string) ?? null,
    timestamp: row.timestamp as string,
    entry_count: row.entry_count as number,
    signature: row.signature as string,
  };
}

export function rebuildMerkleTreeTo(sequenceNumber: number): MerkleTree {
  ensureInit();
  const entries = _storage.getAuditEntriesRange(1, sequenceNumber);
  const tree = new MerkleTree();
  for (const row of entries) {
    const entry: Record<string, unknown> = { ...row };
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
  ensureInit();
  const rows = _storage.getCheckpoints(limit);
  return rows.map((row) => {
    const range = (row.range as Record<string, number>) ?? {};
    return {
      checkpoint_id: row.checkpoint_id as string,
      first_sequence: (range.first_sequence ?? row.first_sequence) as number,
      last_sequence: (range.last_sequence ?? row.last_sequence) as number,
      merkle_root: row.merkle_root as string,
      previous_checkpoint: (row.previous_checkpoint as string) ?? null,
      timestamp: row.timestamp as string,
      entry_count: row.entry_count as number,
      signature: row.signature as string,
    };
  });
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
  const ks = Object.keys(obj as Record<string, unknown>).sort();
  const pairs = ks.map(
    (k) => `${JSON.stringify(k)}:${canonicalJson((obj as Record<string, unknown>)[k])}`,
  );
  return `{${pairs.join(",")}}`;
}

export async function createCheckpoint(
  signFn: (payload: Buffer) => Promise<string>,
): Promise<[CheckpointBody, string]> {
  ensureInit();
  const snap = getMerkleSnapshot();

  // Determine previous checkpoint (if any)
  const allCheckpoints = _storage.getCheckpoints(1000);
  const prevRow = allCheckpoints.length > 0
    ? allCheckpoints[allCheckpoints.length - 1]
    : null;

  let firstSequence: number;
  let previousCheckpoint: string | null;
  let checkpointNumber: number;

  if (prevRow === null) {
    firstSequence = 1;
    previousCheckpoint = null;
    checkpointNumber = 1;
  } else {
    const prevRange = (prevRow.range as Record<string, number>) ?? {};
    const prevLastSeq = (prevRange.last_sequence ?? prevRow.last_sequence) as number;
    firstSequence = prevLastSeq + 1;
    const prevBody: CheckpointBody = {
      version: "0.3",
      service_id: process.env.ANIP_SERVICE_ID ?? "anip-reference-server",
      checkpoint_id: prevRow.checkpoint_id as string,
      range: {
        first_sequence: (prevRange.first_sequence ?? prevRow.first_sequence) as number,
        last_sequence: prevLastSeq,
      },
      merkle_root: prevRow.merkle_root as string,
      previous_checkpoint: (prevRow.previous_checkpoint as string) ?? null,
      timestamp: prevRow.timestamp as string,
      entry_count: prevRow.entry_count as number,
    };
    const prevCanonical = canonicalJson(prevBody);
    previousCheckpoint = `sha256:${createHash("sha256").update(prevCanonical).digest("hex")}`;
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

  const canonicalBytes = Buffer.from(canonicalJson(body));
  const signature = await signFn(canonicalBytes);

  _storage.storeCheckpoint(body as unknown as Record<string, unknown>, signature);

  enqueueForSink({ body, signature } as unknown as Record<string, unknown>);

  resetCheckpointCounters();

  return [body, signature];
}
