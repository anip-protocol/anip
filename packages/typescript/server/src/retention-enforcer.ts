/**
 * Retention enforcer -- background cleanup of expired audit entries (v0.8).
 */
import type { StorageBackend } from "./storage.js";

export interface RetentionEnforcerOpts {
  skipAuditRetention?: boolean;
  onSweep?: (deletedCount: number, durationMs: number) => void;
  onError?: (error: string) => void;
}

export class RetentionEnforcer {
  private _storage: StorageBackend;
  private _interval: number;
  private _timer: ReturnType<typeof setInterval> | null = null;
  private _skipAuditRetention: boolean;
  private _onSweep?: (deletedCount: number, durationMs: number) => void;
  private _onError?: (error: string) => void;
  private _lastRunAt: string | null = null;
  private _lastDeletedCount: number = 0;
  private _lastError: string | null = null;

  constructor(storage: StorageBackend, intervalSeconds: number = 60, opts?: RetentionEnforcerOpts) {
    this._storage = storage;
    this._interval = intervalSeconds;
    this._skipAuditRetention = opts?.skipAuditRetention ?? false;
    this._onSweep = opts?.onSweep;
    this._onError = opts?.onError;
  }

  getLastRunAt(): string | null { return this._lastRunAt; }
  getLastDeletedCount(): number { return this._lastDeletedCount; }
  getLastError(): string | null { return this._lastError; }

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
    this._timer = setInterval(async () => {
      const start = performance.now();
      try {
        const count = await this.sweep();
        const durationMs = Math.round(performance.now() - start);
        this._lastRunAt = new Date().toISOString();
        this._lastDeletedCount = count;
        this._lastError = null;
        this._onSweep?.(count, durationMs);
      } catch (e: unknown) {
        this._lastError = String(e);
        this._onError?.(String(e));
      }
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
