/**
 * Retention enforcer -- background cleanup of expired audit entries (v0.8).
 */
import type { StorageBackend } from "./storage.js";

export interface RetentionEnforcerOpts {
  skipAuditRetention?: boolean;
}

export class RetentionEnforcer {
  private _storage: StorageBackend;
  private _interval: number;
  private _timer: ReturnType<typeof setInterval> | null = null;
  private _skipAuditRetention: boolean;

  constructor(storage: StorageBackend, intervalSeconds: number = 60, opts?: RetentionEnforcerOpts) {
    this._storage = storage;
    this._interval = intervalSeconds;
    this._skipAuditRetention = opts?.skipAuditRetention ?? false;
  }

  isRunning(): boolean {
    return this._timer !== null;
  }

  async sweep(): Promise<number> {
    if (this._skipAuditRetention) return 0;
    const now = new Date().toISOString();
    return this._storage.deleteExpiredAuditEntries(now);
  }

  start(): void {
    if (this._timer) return;
    this._timer = setInterval(() => {
      this.sweep().catch(() => {});
    }, this._interval * 1000);
    // Allow the timer to not prevent process exit (matches CheckpointScheduler)
    if (this._timer && typeof this._timer === "object" && "unref" in this._timer) {
      (this._timer as NodeJS.Timeout).unref();
    }
  }

  stop(): void {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  }
}
