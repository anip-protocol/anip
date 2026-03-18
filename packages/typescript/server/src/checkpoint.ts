/**
 * Checkpoint policy and scheduling for ANIP audit logs.
 */

import { createHash } from "crypto";
import type { StorageBackend } from "./storage.js";
import { MerkleTree } from "./merkle.js";
import { canonicalBytes } from "./hashing.js";

/**
 * Recursively sorted JSON serialization — matches Python's
 * json.dumps(obj, sort_keys=True, separators=(',', ':')).
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
    (k) =>
      `${JSON.stringify(k)}:${canonicalJson((obj as Record<string, unknown>)[k])}`,
  );
  return `{${pairs.join(",")}}`;
}

export interface CheckpointPolicyOpts {
  entryCount?: number;
  intervalSeconds?: number;
}

/**
 * Defines when a checkpoint should be created.
 */
export class CheckpointPolicy {
  private _entryCount: number | null;
  private _intervalSeconds: number | null;

  constructor(opts: CheckpointPolicyOpts) {
    this._entryCount = opts.entryCount ?? null;
    this._intervalSeconds = opts.intervalSeconds ?? null;
  }

  shouldCheckpoint(
    entriesSinceLast: number,
    secondsSinceLast: number = 0,
  ): boolean {
    if (this._entryCount !== null && entriesSinceLast >= this._entryCount) {
      return true;
    }
    if (
      this._intervalSeconds !== null &&
      secondsSinceLast >= this._intervalSeconds
    ) {
      return true;
    }
    return false;
  }
}

/**
 * Periodically triggers checkpoint creation using `setInterval`.
 *
 * The `createFn` callback is async — the caller is responsible for
 * leader acquisition and "has new entries" checks inside the callback.
 */
export class CheckpointScheduler {
  private _interval: number;
  private _createFn: () => Promise<void>;
  private _timer: ReturnType<typeof setInterval> | null = null;

  constructor(
    intervalSeconds: number,
    createFn: () => Promise<void>,
  ) {
    this._interval = intervalSeconds;
    this._createFn = createFn;
  }

  start(): void {
    this._timer = setInterval(async () => {
      try {
        await this._createFn();
      } catch {
        // Non-fatal
      }
    }, this._interval * 1000);
    if (this._timer && typeof this._timer === "object" && "unref" in this._timer) {
      (this._timer as NodeJS.Timeout).unref();
    }
  }

  stop(): void {
    if (this._timer !== null) {
      clearInterval(this._timer);
      this._timer = null;
    }
  }
}

export interface CreateCheckpointOpts {
  merkleSnapshot: { root: string; leaf_count: number };
  serviceId: string;
  previousCheckpoint: Record<string, unknown> | null;
  signFn?: (data: Buffer) => string;
}

/**
 * Create a checkpoint body and sign it.
 *
 * Returns `{ body, signature }`.
 */
export function createCheckpoint(opts: CreateCheckpointOpts): {
  body: Record<string, unknown>;
  signature: string;
} {
  const { merkleSnapshot, serviceId, previousCheckpoint, signFn } = opts;

  let firstSequence: number;
  let prevHash: string | null;
  let checkpointNumber: number;

  if (previousCheckpoint === null) {
    firstSequence = 1;
    prevHash = null;
    checkpointNumber = 1;
  } else {
    const prevRange = (previousCheckpoint.range as Record<string, number>) ?? {};
    firstSequence =
      (prevRange.last_sequence ?? (previousCheckpoint.last_sequence as number) ?? 0) + 1;

    const prevBodyCanonical = canonicalJson(previousCheckpoint);
    const hash = createHash("sha256")
      .update(prevBodyCanonical)
      .digest("hex");
    prevHash = `sha256:${hash}`;

    const prevId = (previousCheckpoint.checkpoint_id as string) ?? "ckpt-0";
    checkpointNumber = parseInt(prevId.split("-")[1], 10) + 1;
  }

  const lastSequence = merkleSnapshot.leaf_count;
  const entryCount = lastSequence - firstSequence + 1;

  const body: Record<string, unknown> = {
    version: "0.3",
    service_id: serviceId,
    checkpoint_id: `ckpt-${checkpointNumber}`,
    range: {
      first_sequence: firstSequence,
      last_sequence: lastSequence,
    },
    merkle_root: merkleSnapshot.root,
    previous_checkpoint: prevHash,
    timestamp: new Date().toISOString(),
    entry_count: entryCount,
  };

  const canonicalBodyBytes = Buffer.from(canonicalJson(body));
  const signature = signFn ? signFn(canonicalBodyBytes) : "";

  return { body, signature };
}

/**
 * Build a checkpoint by reading ALL audit entries from storage and
 * reconstructing the Merkle tree from scratch (cumulative, not delta).
 *
 * Returns `null` when there are no entries or no new entries since the
 * last stored checkpoint.
 */
export async function reconstructAndCreateCheckpoint(opts: {
  storage: StorageBackend;
  serviceId: string;
  signFn?: (data: Buffer) => string;
}): Promise<{ body: Record<string, unknown>; signature: string } | null> {
  const { storage, serviceId, signFn } = opts;

  const maxSeq = await storage.getMaxAuditSequence();
  if (maxSeq === null) return null;

  // Find the most-recent checkpoint to determine what is already covered.
  // getCheckpoints returns results in insertion order (oldest first),
  // so fetch all and take the last.
  const checkpoints = await storage.getCheckpoints(1_000_000);
  const lastCp =
    checkpoints.length > 0 ? checkpoints[checkpoints.length - 1] : null;
  const lastCovered = lastCp
    ? ((lastCp.range as Record<string, number>)?.last_sequence ??
        (lastCp.last_sequence as number) ??
        0)
    : 0;

  if (maxSeq <= lastCovered) return null;

  // Full reconstruction from entry 1
  const entries = await storage.getAuditEntriesRange(1, maxSeq);

  // Rebuild Merkle tree over every entry
  const tree = new MerkleTree();
  for (const entry of entries) {
    tree.addLeaf(Buffer.from(canonicalBytes(entry)));
  }

  const snapshot = tree.snapshot();

  // For cumulative checkpoints the range always starts at 1 because the
  // Merkle tree is rebuilt from the very first entry.  createCheckpoint
  // would normally compute firstSequence from the previous checkpoint's
  // last_sequence, so we pass a synthetic copy with last_sequence=0 to
  // force firstSequence=1 while keeping checkpoint_id for numbering.
  let syntheticPrev: Record<string, unknown> | null = null;
  if (lastCp !== null) {
    syntheticPrev = {
      ...lastCp,
      range: { ...(lastCp.range as Record<string, unknown>), last_sequence: 0 },
    };
  }

  const result = createCheckpoint({
    merkleSnapshot: snapshot,
    serviceId,
    previousCheckpoint: syntheticPrev,
    signFn,
  });

  // Restore the correct previous_checkpoint hash (computed from the real
  // stored checkpoint, not the synthetic copy).
  if (lastCp !== null) {
    const prevBodyCanonical = canonicalJson(lastCp);
    const hash = createHash("sha256").update(prevBodyCanonical).digest("hex");
    result.body.previous_checkpoint = `sha256:${hash}`;

    // Re-sign with the corrected body if a signFn was provided.
    if (signFn) {
      const correctedBytes = Buffer.from(canonicalJson(result.body));
      result.signature = signFn(correctedBytes);
    }
  }

  return result;
}
