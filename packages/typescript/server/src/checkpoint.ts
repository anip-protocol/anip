/**
 * Checkpoint policy and scheduling for ANIP audit logs.
 */

import { createHash } from "crypto";

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
 */
export class CheckpointScheduler {
  private _interval: number;
  private _createFn: () => void;
  private _hasNewEntriesFn: () => boolean;
  private _timer: ReturnType<typeof setInterval> | null = null;

  constructor(
    intervalSeconds: number,
    createFn: () => void,
    hasNewEntriesFn: () => boolean,
  ) {
    this._interval = intervalSeconds;
    this._createFn = createFn;
    this._hasNewEntriesFn = hasNewEntriesFn;
  }

  start(): void {
    this._timer = setInterval(() => {
      if (this._hasNewEntriesFn()) {
        this._createFn();
      }
    }, this._interval * 1000);
    // Allow the timer to not prevent process exit
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

    const prevBodyCanonical = JSON.stringify(previousCheckpoint, Object.keys(previousCheckpoint).sort());
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

  const canonicalBytes = Buffer.from(
    JSON.stringify(body, Object.keys(body).sort()),
  );
  const signature = signFn ? signFn(canonicalBytes) : "";

  return { body, signature };
}
