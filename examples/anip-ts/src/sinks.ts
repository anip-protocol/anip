/**
 * Checkpoint sink interface and implementations.
 *
 * Mirrors the Python reference implementation's sinks.py.
 */

import { writeFileSync, mkdirSync } from "fs";
import { join } from "path";

export interface CheckpointSink {
  /**
   * Publish a signed checkpoint (body + detached JWS signature).
   * The record has `body` (checkpoint data) and `signature` (detached JWS string).
   * Should be idempotent.
   */
  publish(signedCheckpoint: Record<string, unknown>): void;
}

/**
 * Writes signed checkpoints as JSON files to a local directory.
 *
 * Reference implementation — not a real external anchor.
 */
export class LocalFileSink implements CheckpointSink {
  private directory: string;

  constructor(directory: string) {
    this.directory = directory;
    mkdirSync(directory, { recursive: true });
  }

  publish(signedCheckpoint: Record<string, unknown>): void {
    const body = signedCheckpoint.body as Record<string, unknown>;
    const filename = `${body.checkpoint_id}.json`;
    writeFileSync(
      join(this.directory, filename),
      JSON.stringify(signedCheckpoint, null, 2),
    );
  }
}
