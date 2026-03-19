/**
 * Audit aggregation — collapses repeated low-value denials into summary records.
 */

export interface AggregatedEntry {
  event_class: "repeated_low_value_denial";
  retention_tier: "aggregate_only";
  grouping_key: { actor_key: string; capability: string; failure_type: string };
  window_start: string;
  window_end: string;
  count: number;
  first_seen: string;
  last_seen: string;
  representative_detail: string | null;
  toAuditDict(): Record<string, unknown>;
}

function bucketKey(timestampIso: string, windowSeconds: number): number {
  const epoch = Math.floor(new Date(timestampIso).getTime() / 1000);
  return epoch - (epoch % windowSeconds);
}

function groupingKey(event: Record<string, unknown>): string {
  const ak = String(event.actor_key ?? "anonymous");
  const cap = String(event.capability ?? "_pre_auth");
  const ft = String(event.failure_type ?? "unknown");
  return `${ak}\0${cap}\0${ft}`;
}

function parseGroupingKey(key: string): { actor_key: string; capability: string; failure_type: string } {
  const [actor_key, capability, failure_type] = key.split("\0");
  return { actor_key, capability, failure_type };
}

function createAggregatedEntry(
  gk: { actor_key: string; capability: string; failure_type: string },
  events: Record<string, unknown>[],
  bucketEpoch: number,
  windowSeconds: number,
): AggregatedEntry {
  const timestamps = events.map((e) => String(e.timestamp));
  const firstDetail = events[0].detail;
  let repDetail: string | null = null;
  if (firstDetail != null) {
    repDetail = String(firstDetail).slice(0, 200);
  }

  const windowStart = new Date(bucketEpoch * 1000).toISOString();
  const windowEnd = new Date((bucketEpoch + windowSeconds) * 1000).toISOString();

  return {
    event_class: "repeated_low_value_denial",
    retention_tier: "aggregate_only",
    grouping_key: gk,
    window_start: windowStart,
    window_end: windowEnd,
    count: events.length,
    first_seen: timestamps.sort()[0],
    last_seen: timestamps.sort()[timestamps.length - 1],
    representative_detail: repDetail,
    toAuditDict() {
      return {
        entry_type: "aggregated",
        event_class: this.event_class,
        retention_tier: this.retention_tier,
        grouping_key: this.grouping_key,
        window: { start: this.window_start, end: this.window_end },
        count: this.count,
        first_seen: this.first_seen,
        last_seen: this.last_seen,
        representative_detail: this.representative_detail,
      };
    },
  };
}

export class AuditAggregator {
  private _windowSeconds: number;
  private _buckets: Map<number, Map<string, Record<string, unknown>[]>> = new Map();

  constructor(opts?: { windowSeconds?: number }) {
    this._windowSeconds = opts?.windowSeconds ?? 60;
  }

  submit(event: Record<string, unknown>): void {
    const ts = String(event.timestamp ?? new Date().toISOString());
    const bucket = bucketKey(ts, this._windowSeconds);
    const gk = groupingKey(event);

    if (!this._buckets.has(bucket)) {
      this._buckets.set(bucket, new Map());
    }
    const bucketMap = this._buckets.get(bucket)!;
    if (!bucketMap.has(gk)) {
      bucketMap.set(gk, []);
    }
    bucketMap.get(gk)!.push(event);
  }

  getPendingCount(): number {
    return this._buckets.size;
  }

  flush(now: Date): Array<Record<string, unknown> | AggregatedEntry> {
    const nowEpoch = Math.floor(now.getTime() / 1000);
    const results: Array<Record<string, unknown> | AggregatedEntry> = [];
    const closedBuckets: number[] = [];

    const sortedKeys = [...this._buckets.keys()].sort((a, b) => a - b);
    for (const bucketEpoch of sortedKeys) {
      const bucketEnd = bucketEpoch + this._windowSeconds;
      if (bucketEnd > nowEpoch) continue;

      closedBuckets.push(bucketEpoch);
      const bucketMap = this._buckets.get(bucketEpoch)!;
      for (const [gkStr, events] of bucketMap) {
        if (events.length === 1) {
          results.push(events[0]);
        } else {
          results.push(
            createAggregatedEntry(
              parseGroupingKey(gkStr),
              events,
              bucketEpoch,
              this._windowSeconds,
            ),
          );
        }
      }
    }

    for (const b of closedBuckets) {
      this._buckets.delete(b);
    }
    return results;
  }
}
