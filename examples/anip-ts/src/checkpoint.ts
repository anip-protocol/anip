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
