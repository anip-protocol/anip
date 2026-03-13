/**
 * Checkpoint policy for the ANIP audit log.
 *
 * Mirrors the Python reference implementation's checkpoint.py.
 */

import type { CheckpointSink } from "./sinks.js";

// --- Async sink publication queue ---

let _sink: CheckpointSink | null = null;
const _sinkQueue: Record<string, unknown>[] = [];
let _drainTimer: ReturnType<typeof setInterval> | null = null;

/**
 * Configure the checkpoint sink used for async publication.
 * Starts the background drain loop if not already running.
 */
export function setSink(sink: CheckpointSink): void {
  _sink = sink;
  if (_drainTimer === null) {
    _drainTimer = setInterval(_drainSinkQueue, 50);
    // Allow the process to exit even if the timer is running
    if (_drainTimer && typeof _drainTimer === "object" && "unref" in _drainTimer) {
      _drainTimer.unref();
    }
  }
}

/**
 * Enqueue a checkpoint for async publication to the configured sink.
 */
export function enqueueForSink(checkpoint: Record<string, unknown>): void {
  if (_sink !== null) {
    _sinkQueue.push(checkpoint);
  }
}

/**
 * Return the number of checkpoints waiting to be published.
 */
export function getPendingSinkCount(): number {
  return _sinkQueue.length;
}

function _drainSinkQueue(): void {
  while (_sinkQueue.length > 0) {
    const ckpt = _sinkQueue[0];
    if (_sink) {
      try {
        _sink.publish(ckpt);
        _sinkQueue.shift(); // Remove only after successful publish
      } catch {
        // Leave in queue for retry on next drain cycle
        break;
      }
    } else {
      _sinkQueue.shift();
    }
  }
}

/**
 * Stop the drain timer and reset sink state. Useful for tests.
 */
export function resetSink(): void {
  if (_drainTimer !== null) {
    clearInterval(_drainTimer);
    _drainTimer = null;
  }
  _sink = null;
  _sinkQueue.length = 0;
}

export interface CheckpointPolicyOptions {
  entryCount?: number;
  intervalSeconds?: number;
}

export class CheckpointPolicy {
  readonly entryCount?: number;
  readonly intervalSeconds?: number;

  constructor(opts: CheckpointPolicyOptions = {}) {
    this.entryCount = opts.entryCount;
    this.intervalSeconds = opts.intervalSeconds;
  }

  /**
   * Return true when any configured threshold is met.
   */
  shouldCheckpoint(
    entriesSinceLast: number,
    secondsSinceLast: number = 0,
  ): boolean {
    if (
      this.entryCount !== undefined &&
      entriesSinceLast >= this.entryCount
    ) {
      return true;
    }
    if (
      this.intervalSeconds !== undefined &&
      secondsSinceLast >= this.intervalSeconds
    ) {
      return true;
    }
    return false;
  }
}

/**
 * Periodic checkpoint scheduler — fires at a fixed interval and creates a
 * checkpoint whenever new audit entries have accumulated.
 */
export class CheckpointScheduler {
  private interval: number;
  private createFn: () => void;
  private hasNewEntriesFn: () => boolean;
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(
    intervalSeconds: number,
    createFn: () => void,
    hasNewEntriesFn: () => boolean,
  ) {
    this.interval = intervalSeconds * 1000;
    this.createFn = createFn;
    this.hasNewEntriesFn = hasNewEntriesFn;
  }

  start(): void {
    this.timer = setInterval(() => {
      if (this.hasNewEntriesFn()) {
        this.createFn();
      }
    }, this.interval);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}
