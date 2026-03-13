/**
 * Checkpoint sink interface and implementations.
 *
 * Mirrors the Python reference implementation's sinks.py.
 */

import { writeFileSync, mkdirSync } from "fs";
import { join } from "path";

export interface CheckpointSink {
  /** Publish a checkpoint. Should be idempotent. */
  publish(checkpoint: Record<string, unknown>): void;
}

/**
 * Writes checkpoints as JSON files to a local directory.
 *
 * Reference implementation — not a real external anchor.
 */
export class LocalFileSink implements CheckpointSink {
  private directory: string;

  constructor(directory: string) {
    this.directory = directory;
    mkdirSync(directory, { recursive: true });
  }

  publish(checkpoint: Record<string, unknown>): void {
    const filename = `${checkpoint.checkpoint_id}.json`;
    writeFileSync(
      join(this.directory, filename),
      JSON.stringify(checkpoint, Object.keys(checkpoint).sort(), 2),
    );
  }
}
