/**
 * Checkpoint policy for the ANIP audit log.
 *
 * Mirrors the Python reference implementation's checkpoint.py.
 */

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
