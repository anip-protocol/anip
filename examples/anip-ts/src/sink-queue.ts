/**
 * Async sink publication queue — example-specific.
 *
 * The SDK provides CheckpointSink / LocalFileSink but the async drain
 * loop is application-level wiring kept in this local module.
 */

import type { CheckpointSink } from "@anip/server";

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
        _sink.publish(ckpt as { body: Record<string, unknown>; signature: string });
        _sinkQueue.shift();
      } catch {
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
