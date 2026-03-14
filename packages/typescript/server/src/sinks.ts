/**
 * Checkpoint sink interface and implementations.
 *
 * Sinks receive signed checkpoints and persist them to external storage
 * (local filesystem, S3, etc.).
 */

import { writeFileSync, mkdirSync } from "fs";
import { join } from "path";

export interface CheckpointSink {
  /** Publish a signed checkpoint (body + detached JWS signature). */
  publish(signedCheckpoint: {
    body: Record<string, unknown>;
    signature: string;
  }): void;
}

/**
 * Writes signed checkpoints as JSON files to a local directory.
 */
export class LocalFileSink implements CheckpointSink {
  private _directory: string;

  constructor(directory: string) {
    this._directory = directory;
    mkdirSync(directory, { recursive: true });
  }

  publish(signedCheckpoint: {
    body: Record<string, unknown>;
    signature: string;
  }): void {
    const body = signedCheckpoint.body;
    const filename = `${body.checkpoint_id as string}.json`;
    const path = join(this._directory, filename);
    writeFileSync(path, JSON.stringify(signedCheckpoint, null, 2));
  }
}
