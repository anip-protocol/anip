# ANIP v0.9 Protocol Follow-up Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Activate the four v0.8 placeholders — audit aggregation, storage-side redaction, caller-class-aware disclosure, and proof_unavailable client semantics — across both Python and TypeScript runtimes.

**Architecture:** Sequential implementation in dependency order. Each feature builds on the previous: aggregation activates the `repeated_low_value_denial` event class, storage-side redaction uses event class as its signal, caller-class redaction extends the response-boundary layer, and proof semantics adds schema/spec fields. Both runtimes are updated per feature before moving to the next.

**Tech Stack:** Python (Pydantic, pytest, asyncio), TypeScript (Zod, vitest, better-sqlite3), JSON Schema

**Design doc:** `docs/plans/2026-03-17-v09-protocol-followup-design.md`

---

## Task 1: Audit Aggregation — Python Aggregator

**Files:**
- Create: `packages/python/anip-service/src/anip_service/aggregation.py`
- Test: `packages/python/anip-service/tests/test_aggregation.py`

**Context:** The classifier (`classification.py`) never returns `repeated_low_value_denial`. The `aggregate_only` retention tier maps to P7D (same as `short`). This task creates the aggregation layer that groups repeated low-value denials within time-bucketed windows and emits summary records.

**Step 1: Write failing tests for the aggregator**

```python
"""Tests for audit aggregation."""
import pytest
from datetime import datetime, timezone, timedelta
from anip_service.aggregation import AuditAggregator, AggregatedEntry


def _make_event(
    *,
    actor_key: str = "agent-1",
    capability: str = "search_flights",
    failure_type: str = "scope_insufficient",
    timestamp: datetime | None = None,
) -> dict:
    return {
        "actor_key": actor_key,
        "capability": capability,
        "failure_type": failure_type,
        "detail": "Missing scope travel.search",
        "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
    }


class TestAuditAggregator:
    def test_single_event_not_aggregated(self):
        """A single event in a window is returned as-is, not aggregated."""
        agg = AuditAggregator(window_seconds=60)
        now = datetime(2026, 1, 1, 0, 0, 30, tzinfo=timezone.utc)
        event = _make_event(timestamp=now)
        results = agg.submit(event)
        assert results is None  # buffered, not yet emitted

        # Flush the window
        results = agg.flush(now + timedelta(seconds=61))
        assert len(results) == 1
        assert not isinstance(results[0], AggregatedEntry)

    def test_two_identical_events_aggregated(self):
        """Two events with same grouping key within a window produce one aggregated entry."""
        agg = AuditAggregator(window_seconds=60)
        t1 = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 1, 0, 0, 20, tzinfo=timezone.utc)
        agg.submit(_make_event(timestamp=t1))
        agg.submit(_make_event(timestamp=t2))

        results = agg.flush(t1 + timedelta(seconds=61))
        assert len(results) == 1
        entry = results[0]
        assert isinstance(entry, AggregatedEntry)
        assert entry.count == 2
        assert entry.event_class == "repeated_low_value_denial"
        assert entry.retention_tier == "aggregate_only"
        assert entry.first_seen == t1.isoformat()
        assert entry.last_seen == t2.isoformat()

    def test_different_keys_not_aggregated(self):
        """Events with different grouping keys are not merged."""
        agg = AuditAggregator(window_seconds=60)
        t = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        agg.submit(_make_event(actor_key="agent-1", timestamp=t))
        agg.submit(_make_event(actor_key="agent-2", timestamp=t))

        results = agg.flush(t + timedelta(seconds=61))
        assert len(results) == 2
        assert not isinstance(results[0], AggregatedEntry)
        assert not isinstance(results[1], AggregatedEntry)

    def test_representative_detail_truncated(self):
        """representative_detail is truncated to 200 chars."""
        agg = AuditAggregator(window_seconds=60)
        t = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        long_detail = "x" * 500
        agg.submit(_make_event(timestamp=t) | {"detail": long_detail})
        agg.submit(_make_event(timestamp=t + timedelta(seconds=5)))

        results = agg.flush(t + timedelta(seconds=61))
        entry = results[0]
        assert isinstance(entry, AggregatedEntry)
        assert len(entry.representative_detail) == 200

    def test_representative_detail_nullable(self):
        """representative_detail is None when original detail is None."""
        agg = AuditAggregator(window_seconds=60)
        t = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        agg.submit(_make_event(timestamp=t) | {"detail": None})
        agg.submit(_make_event(timestamp=t + timedelta(seconds=5)) | {"detail": None})

        results = agg.flush(t + timedelta(seconds=61))
        entry = results[0]
        assert isinstance(entry, AggregatedEntry)
        assert entry.representative_detail is None

    def test_anonymous_actor_key(self):
        """Events with no subject use 'anonymous' as actor_key."""
        agg = AuditAggregator(window_seconds=60)
        t = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        agg.submit(_make_event(actor_key="anonymous", timestamp=t))
        agg.submit(_make_event(actor_key="anonymous", timestamp=t + timedelta(seconds=5)))

        results = agg.flush(t + timedelta(seconds=61))
        assert len(results) == 1
        entry = results[0]
        assert isinstance(entry, AggregatedEntry)
        assert entry.grouping_key["actor_key"] == "anonymous"

    def test_window_boundary(self):
        """Events in different windows are not aggregated together."""
        agg = AuditAggregator(window_seconds=60)
        t1 = datetime(2026, 1, 1, 0, 0, 50, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 1, 0, 1, 10, tzinfo=timezone.utc)  # next window
        agg.submit(_make_event(timestamp=t1))
        agg.submit(_make_event(timestamp=t2))

        # Flush first window
        r1 = agg.flush(t1 + timedelta(seconds=61))
        assert len(r1) == 1
        assert not isinstance(r1[0], AggregatedEntry)

        # Flush second window
        r2 = agg.flush(t2 + timedelta(seconds=61))
        assert len(r2) == 1
        assert not isinstance(r2[0], AggregatedEntry)

    def test_pre_auth_capability_bucket(self):
        """Pre-auth failures use '_pre_auth' as capability."""
        agg = AuditAggregator(window_seconds=60)
        t = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        agg.submit(_make_event(capability="_pre_auth", failure_type="invalid_token", timestamp=t))
        agg.submit(_make_event(capability="_pre_auth", failure_type="invalid_token",
                               timestamp=t + timedelta(seconds=5)))

        results = agg.flush(t + timedelta(seconds=61))
        assert len(results) == 1
        entry = results[0]
        assert isinstance(entry, AggregatedEntry)
        assert entry.grouping_key["capability"] == "_pre_auth"

    def test_aggregated_entry_to_dict(self):
        """AggregatedEntry serializes to the expected audit entry dict shape."""
        agg = AuditAggregator(window_seconds=60)
        t = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
        agg.submit(_make_event(timestamp=t))
        agg.submit(_make_event(timestamp=t + timedelta(seconds=5)))

        results = agg.flush(t + timedelta(seconds=61))
        entry = results[0]
        d = entry.to_audit_dict()
        assert d["entry_type"] == "aggregated"
        assert d["event_class"] == "repeated_low_value_denial"
        assert d["retention_tier"] == "aggregate_only"
        assert d["count"] == 2
        assert "grouping_key" in d
        assert "window" in d
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/python/anip-service && python -m pytest tests/test_aggregation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'anip_service.aggregation'`

**Step 3: Implement the aggregator**

```python
"""Audit aggregation — collapses repeated low-value denials into summary records."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AggregatedEntry:
    """Summary record for repeated low-value denials within a time window."""

    event_class: str = "repeated_low_value_denial"
    retention_tier: str = "aggregate_only"
    grouping_key: dict[str, str] = field(default_factory=dict)
    window_start: str = ""
    window_end: str = ""
    count: int = 0
    first_seen: str = ""
    last_seen: str = ""
    representative_detail: str | None = None

    def to_audit_dict(self) -> dict:
        """Serialize to the audit entry dict shape for persistence."""
        return {
            "entry_type": "aggregated",
            "event_class": self.event_class,
            "retention_tier": self.retention_tier,
            "grouping_key": self.grouping_key,
            "window": {
                "start": self.window_start,
                "end": self.window_end,
            },
            "count": self.count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "representative_detail": self.representative_detail,
        }


def _bucket_key(timestamp_iso: str, window_seconds: int) -> int:
    """Return the bucket start epoch for a given timestamp."""
    dt = datetime.fromisoformat(timestamp_iso)
    epoch = int(dt.timestamp())
    return epoch - (epoch % window_seconds)


def _grouping_key(event: dict) -> tuple[str, str, str]:
    """Extract the (actor_key, capability, failure_type) tuple."""
    return (
        event.get("actor_key", "anonymous"),
        event.get("capability", "_pre_auth"),
        event.get("failure_type", "unknown"),
    )


class AuditAggregator:
    """Time-window bucketed aggregator for low-value audit denials."""

    def __init__(self, *, window_seconds: int = 60) -> None:
        self._window_seconds = window_seconds
        # _buckets: {bucket_epoch: {grouping_key_tuple: [events]}}
        self._buckets: dict[int, dict[tuple[str, str, str], list[dict]]] = {}

    def submit(self, event: dict) -> None:
        """Buffer an event into the appropriate time-window bucket."""
        ts = event.get("timestamp", datetime.now(timezone.utc).isoformat())
        bucket = _bucket_key(ts, self._window_seconds)
        gk = _grouping_key(event)

        if bucket not in self._buckets:
            self._buckets[bucket] = {}
        if gk not in self._buckets[bucket]:
            self._buckets[bucket][gk] = []
        self._buckets[bucket][gk].append(event)

    def flush(self, now: datetime) -> list[dict | AggregatedEntry]:
        """Flush all closed windows (windows whose end time <= now).

        Returns a list of individual events or AggregatedEntry objects.
        """
        now_epoch = int(now.timestamp())
        results: list[dict | AggregatedEntry] = []
        closed_buckets = []

        for bucket_epoch in sorted(self._buckets.keys()):
            bucket_end = bucket_epoch + self._window_seconds
            if bucket_end > now_epoch:
                continue  # window not yet closed

            closed_buckets.append(bucket_epoch)
            for gk, events in self._buckets[bucket_epoch].items():
                if len(events) == 1:
                    results.append(events[0])
                else:
                    timestamps = [e["timestamp"] for e in events]
                    first_detail = events[0].get("detail")
                    rep_detail = None
                    if first_detail is not None:
                        rep_detail = str(first_detail)[:200]

                    window_start = datetime.fromtimestamp(
                        bucket_epoch, tz=timezone.utc
                    ).isoformat()
                    window_end = datetime.fromtimestamp(
                        bucket_epoch + self._window_seconds, tz=timezone.utc
                    ).isoformat()

                    results.append(
                        AggregatedEntry(
                            grouping_key={
                                "actor_key": gk[0],
                                "capability": gk[1],
                                "failure_type": gk[2],
                            },
                            window_start=window_start,
                            window_end=window_end,
                            count=len(events),
                            first_seen=min(timestamps),
                            last_seen=max(timestamps),
                            representative_detail=rep_detail,
                        )
                    )

        for b in closed_buckets:
            del self._buckets[b]

        return results
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/python/anip-service && python -m pytest tests/test_aggregation.py -v`
Expected: PASS (all 9 tests)

**Step 5: Commit**

```bash
git add packages/python/anip-service/src/anip_service/aggregation.py packages/python/anip-service/tests/test_aggregation.py
git commit -m "feat(python): add audit aggregation layer for repeated low-value denials"
```

---

## Task 2: Audit Aggregation — TypeScript Aggregator

**Files:**
- Create: `packages/typescript/service/src/aggregation.ts`
- Test: `packages/typescript/service/tests/aggregation.test.ts`

**Context:** Mirror of the Python aggregator. Same grouping key `(actor_key, capability, failure_type)`, same bucketed window logic, same AggregatedEntry shape.

**Step 1: Write failing tests**

```typescript
import { describe, it, expect } from "vitest";
import { AuditAggregator, AggregatedEntry } from "../src/aggregation.js";

function makeEvent(overrides: Partial<{
  actor_key: string;
  capability: string;
  failure_type: string;
  detail: string | null;
  timestamp: string;
}> = {}): Record<string, unknown> {
  return {
    actor_key: "agent-1",
    capability: "search_flights",
    failure_type: "scope_insufficient",
    detail: "Missing scope travel.search",
    timestamp: new Date("2026-01-01T00:00:30Z").toISOString(),
    ...overrides,
  };
}

describe("AuditAggregator", () => {
  it("single event not aggregated", () => {
    const agg = new AuditAggregator({ windowSeconds: 60 });
    const t = new Date("2026-01-01T00:00:30Z");
    agg.submit(makeEvent({ timestamp: t.toISOString() }));

    const results = agg.flush(new Date(t.getTime() + 61_000));
    expect(results).toHaveLength(1);
    expect(results[0]).not.toHaveProperty("count");
  });

  it("two identical events aggregated", () => {
    const agg = new AuditAggregator({ windowSeconds: 60 });
    const t1 = new Date("2026-01-01T00:00:10Z");
    const t2 = new Date("2026-01-01T00:00:20Z");
    agg.submit(makeEvent({ timestamp: t1.toISOString() }));
    agg.submit(makeEvent({ timestamp: t2.toISOString() }));

    const results = agg.flush(new Date(t1.getTime() + 61_000));
    expect(results).toHaveLength(1);
    const entry = results[0] as AggregatedEntry;
    expect(entry.count).toBe(2);
    expect(entry.event_class).toBe("repeated_low_value_denial");
    expect(entry.retention_tier).toBe("aggregate_only");
    expect(entry.first_seen).toBe(t1.toISOString());
    expect(entry.last_seen).toBe(t2.toISOString());
  });

  it("different keys not aggregated", () => {
    const agg = new AuditAggregator({ windowSeconds: 60 });
    const t = new Date("2026-01-01T00:00:10Z");
    agg.submit(makeEvent({ actor_key: "agent-1", timestamp: t.toISOString() }));
    agg.submit(makeEvent({ actor_key: "agent-2", timestamp: t.toISOString() }));

    const results = agg.flush(new Date(t.getTime() + 61_000));
    expect(results).toHaveLength(2);
    expect(results[0]).not.toHaveProperty("count");
    expect(results[1]).not.toHaveProperty("count");
  });

  it("representative_detail truncated to 200 chars", () => {
    const agg = new AuditAggregator({ windowSeconds: 60 });
    const t = new Date("2026-01-01T00:00:10Z");
    agg.submit(makeEvent({ detail: "x".repeat(500), timestamp: t.toISOString() }));
    agg.submit(makeEvent({ timestamp: new Date(t.getTime() + 5_000).toISOString() }));

    const results = agg.flush(new Date(t.getTime() + 61_000));
    const entry = results[0] as AggregatedEntry;
    expect(entry.representative_detail).toHaveLength(200);
  });

  it("representative_detail nullable", () => {
    const agg = new AuditAggregator({ windowSeconds: 60 });
    const t = new Date("2026-01-01T00:00:10Z");
    agg.submit(makeEvent({ detail: null, timestamp: t.toISOString() }));
    agg.submit(makeEvent({ detail: null, timestamp: new Date(t.getTime() + 5_000).toISOString() }));

    const results = agg.flush(new Date(t.getTime() + 61_000));
    const entry = results[0] as AggregatedEntry;
    expect(entry.representative_detail).toBeNull();
  });

  it("window boundary separates events", () => {
    const agg = new AuditAggregator({ windowSeconds: 60 });
    const t1 = new Date("2026-01-01T00:00:50Z");
    const t2 = new Date("2026-01-01T00:01:10Z"); // next window
    agg.submit(makeEvent({ timestamp: t1.toISOString() }));
    agg.submit(makeEvent({ timestamp: t2.toISOString() }));

    const r1 = agg.flush(new Date(t1.getTime() + 61_000));
    expect(r1).toHaveLength(1);
    expect(r1[0]).not.toHaveProperty("count");

    const r2 = agg.flush(new Date(t2.getTime() + 61_000));
    expect(r2).toHaveLength(1);
    expect(r2[0]).not.toHaveProperty("count");
  });

  it("pre-auth capability bucket", () => {
    const agg = new AuditAggregator({ windowSeconds: 60 });
    const t = new Date("2026-01-01T00:00:10Z");
    agg.submit(makeEvent({ capability: "_pre_auth", failure_type: "invalid_token", timestamp: t.toISOString() }));
    agg.submit(makeEvent({ capability: "_pre_auth", failure_type: "invalid_token", timestamp: new Date(t.getTime() + 5_000).toISOString() }));

    const results = agg.flush(new Date(t.getTime() + 61_000));
    expect(results).toHaveLength(1);
    const entry = results[0] as AggregatedEntry;
    expect(entry.grouping_key.capability).toBe("_pre_auth");
  });

  it("toAuditDict produces expected shape", () => {
    const agg = new AuditAggregator({ windowSeconds: 60 });
    const t = new Date("2026-01-01T00:00:10Z");
    agg.submit(makeEvent({ timestamp: t.toISOString() }));
    agg.submit(makeEvent({ timestamp: new Date(t.getTime() + 5_000).toISOString() }));

    const results = agg.flush(new Date(t.getTime() + 61_000));
    const entry = results[0] as AggregatedEntry;
    const d = entry.toAuditDict();
    expect(d.entry_type).toBe("aggregated");
    expect(d.event_class).toBe("repeated_low_value_denial");
    expect(d.retention_tier).toBe("aggregate_only");
    expect(d.count).toBe(2);
    expect(d.grouping_key).toBeDefined();
    expect(d.window).toBeDefined();
  });
});
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/typescript/service && npx vitest run tests/aggregation.test.ts`
Expected: FAIL with module not found

**Step 3: Implement the aggregator**

```typescript
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
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/typescript/service && npx vitest run tests/aggregation.test.ts`
Expected: PASS (all 8 tests)

**Step 5: Commit**

```bash
git add packages/typescript/service/src/aggregation.ts packages/typescript/service/tests/aggregation.test.ts
git commit -m "feat(typescript): add audit aggregation layer for repeated low-value denials"
```

---

## Task 3: Audit Aggregation — Update Retention Defaults

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/retention.py`
- Modify: `packages/python/anip-service/tests/test_retention.py`
- Modify: `packages/typescript/service/src/retention.ts`
- Modify: `packages/typescript/service/tests/retention.test.ts`

**Context:** `aggregate_only` currently maps to P7D (same as `short`). Per design, it should map to P1D. Also, `repeated_low_value_denial` should map to `aggregate_only` tier (currently maps to `short`).

**Step 1: Write failing tests (Python)**

Add to `test_retention.py`:

```python
def test_aggregate_only_maps_to_p1d():
    """aggregate_only retention tier is P1D, not P7D."""
    policy = RetentionPolicy()
    expires = policy.compute_expires_at("aggregate_only")
    now_plus_1d = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    now_plus_2d = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    assert expires is not None
    assert expires < now_plus_2d
    assert expires > datetime.now(timezone.utc).isoformat()


def test_repeated_low_value_denial_maps_to_aggregate_only():
    """repeated_low_value_denial event class maps to aggregate_only tier."""
    policy = RetentionPolicy()
    tier = policy.resolve_tier("repeated_low_value_denial")
    assert tier == "aggregate_only"
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/python/anip-service && python -m pytest tests/test_retention.py::test_aggregate_only_maps_to_p1d tests/test_retention.py::test_repeated_low_value_denial_maps_to_aggregate_only -v`
Expected: FAIL (aggregate_only still P7D, repeated_low_value_denial still maps to short)

**Step 3: Update retention defaults (Python)**

In `packages/python/anip-service/src/anip_service/retention.py`, update:

```python
DEFAULT_CLASS_TO_TIER = {
    "high_risk_success": "long",
    "high_risk_denial": "medium",
    "low_risk_success": "short",
    "repeated_low_value_denial": "aggregate_only",  # was "short"
    "malformed_or_spam": "short",
}

DEFAULT_TIER_TO_DURATION = {
    "long": "P365D",
    "medium": "P90D",
    "short": "P7D",
    "aggregate_only": "P1D",  # was "P7D"
}
```

**Step 4: Fix any existing tests that assert old values**

The existing test `test_aggregate_only_same_expires_as_short` will fail because aggregate_only is no longer P7D. Update it to verify P1D instead:

```python
def test_aggregate_only_expires_p1d():
    """aggregate_only tier expires after 1 day."""
    policy = RetentionPolicy()
    expires = policy.compute_expires_at("aggregate_only")
    assert expires is not None
    # Should be ~1 day from now, not 7
```

**Step 5: Run all retention tests**

Run: `cd packages/python/anip-service && python -m pytest tests/test_retention.py -v`
Expected: PASS

**Step 6: Write failing tests (TypeScript)**

Add to `retention.test.ts`:

```typescript
it("aggregate_only maps to P1D", () => {
  const policy = new RetentionPolicy();
  const expires = policy.computeExpiresAt("aggregate_only");
  expect(expires).not.toBeNull();
  const expiresDate = new Date(expires!);
  const twoDaysFromNow = new Date(Date.now() + 2 * 86_400_000);
  expect(expiresDate.getTime()).toBeLessThan(twoDaysFromNow.getTime());
});

it("repeated_low_value_denial maps to aggregate_only tier", () => {
  const policy = new RetentionPolicy();
  const tier = policy.resolveTier("repeated_low_value_denial");
  expect(tier).toBe("aggregate_only");
});
```

**Step 7: Run tests to verify they fail**

Run: `cd packages/typescript/service && npx vitest run tests/retention.test.ts`
Expected: FAIL

**Step 8: Update retention defaults (TypeScript)**

In `packages/typescript/service/src/retention.ts`, update the same two constants:

```typescript
const DEFAULT_CLASS_TO_TIER: Record<string, string> = {
  high_risk_success: "long",
  high_risk_denial: "medium",
  low_risk_success: "short",
  repeated_low_value_denial: "aggregate_only",  // was "short"
  malformed_or_spam: "short",
};

const DEFAULT_TIER_TO_DURATION: Record<string, string | null> = {
  long: "P365D",
  medium: "P90D",
  short: "P7D",
  aggregate_only: "P1D",  // was "P7D"
};
```

**Step 9: Fix any existing tests that assert old values and run all**

Run: `cd packages/typescript/service && npx vitest run tests/retention.test.ts`
Expected: PASS

**Step 10: Commit**

```bash
git add packages/python/anip-service/src/anip_service/retention.py packages/python/anip-service/tests/test_retention.py packages/typescript/service/src/retention.ts packages/typescript/service/tests/retention.test.ts
git commit -m "feat: update retention defaults — aggregate_only P1D, repeated_low_value_denial maps to aggregate_only"
```

---

## Task 4: Audit Aggregation — Service Integration

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/typescript/service/src/service.ts`
- Modify: `packages/python/anip-service/src/anip_service/__init__.py`
- Modify: `packages/typescript/service/src/index.ts`

**Context:** Wire the aggregator into the service's audit logging flow. Low-value denial events (classified as `malformed_or_spam` or with pre-auth failures) are routed through the aggregator instead of being logged immediately. A periodic flush emits aggregated entries. The aggregator is optional — services that don't want aggregation can skip it.

**Step 1: Python — Add aggregator to service constructor**

In `service.py`, add:
- Import `AuditAggregator` and `AggregatedEntry` from `anip_service.aggregation`
- Add `aggregation_window: int | None = None` to `__init__` (None = disabled, integer = window seconds)
- If enabled, create `self._aggregator = AuditAggregator(window_seconds=aggregation_window)`
- Modify `_log_audit` to check: if aggregator is enabled and event_class is `malformed_or_spam`, route through aggregator instead of immediate logging
- Add `_flush_aggregator` method called periodically (on each invoke, flush closed windows)

**Step 2: TypeScript — Add aggregator to service**

Same pattern in `service.ts`:
- Import `AuditAggregator` from `./aggregation.js`
- Add `aggregationWindow?: number` to `ANIPServiceOpts`
- Wire into `logAudit` flow

**Step 3: Export new types**

In `packages/python/anip-service/src/anip_service/__init__.py`, add `AuditAggregator` to `__all__`.
In `packages/typescript/service/src/index.ts`, add `export { AuditAggregator } from "./aggregation.js"`.

**Step 4: Run full test suites**

Run: `cd packages/python/anip-service && python -m pytest -v`
Run: `cd packages/typescript/service && npx vitest run`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/python/anip-service/src/anip_service/service.py packages/python/anip-service/src/anip_service/__init__.py packages/typescript/service/src/service.ts packages/typescript/service/src/index.ts
git commit -m "feat: integrate audit aggregator into service invoke flow"
```

---

## Task 5: Storage-Side Redaction — Python

**Files:**
- Create: `packages/python/anip-service/src/anip_service/storage_redaction.py`
- Test: `packages/python/anip-service/tests/test_storage_redaction.py`

**Context:** Storage-side redaction strips `parameters` from audit entries with event class `low_risk_success`, `malformed_or_spam`, or `repeated_low_value_denial` before they are persisted. High-risk events are stored at full fidelity. A `storage_redacted: True` marker is added to redacted entries.

**Step 1: Write failing tests**

```python
"""Tests for storage-side redaction."""
import pytest
from anip_service.storage_redaction import storage_redact_entry

_LOW_VALUE_CLASSES = ["low_risk_success", "malformed_or_spam", "repeated_low_value_denial"]
_HIGH_VALUE_CLASSES = ["high_risk_success", "high_risk_denial"]


def _make_entry(event_class: str) -> dict:
    return {
        "sequence_number": 1,
        "timestamp": "2026-01-01T00:00:00Z",
        "capability": "search_flights",
        "token_id": "tok-1",
        "root_principal": "user@example.com",
        "parameters": {"origin": "JFK", "destination": "LAX"},
        "success": event_class.endswith("success"),
        "failure_type": None if event_class.endswith("success") else "scope_insufficient",
        "event_class": event_class,
        "retention_tier": "short",
        "invocation_id": "inv-000000000001",
    }


class TestStorageRedaction:
    @pytest.mark.parametrize("event_class", _LOW_VALUE_CLASSES)
    def test_low_value_strips_parameters(self, event_class: str):
        entry = _make_entry(event_class)
        result = storage_redact_entry(entry)
        assert "parameters" not in result or result["parameters"] is None
        assert result["storage_redacted"] is True

    @pytest.mark.parametrize("event_class", _HIGH_VALUE_CLASSES)
    def test_high_value_preserves_parameters(self, event_class: str):
        entry = _make_entry(event_class)
        result = storage_redact_entry(entry)
        assert result["parameters"] == {"origin": "JFK", "destination": "LAX"}
        assert result["storage_redacted"] is False

    def test_preserves_envelope_fields(self):
        entry = _make_entry("low_risk_success")
        result = storage_redact_entry(entry)
        assert result["timestamp"] == "2026-01-01T00:00:00Z"
        assert result["capability"] == "search_flights"
        assert result["token_id"] == "tok-1"
        assert result["event_class"] == "low_risk_success"
        assert result["invocation_id"] == "inv-000000000001"

    def test_does_not_mutate_original(self):
        entry = _make_entry("low_risk_success")
        original_params = entry["parameters"].copy()
        storage_redact_entry(entry)
        assert entry["parameters"] == original_params

    def test_no_event_class_treated_as_high_value(self):
        """Entry without event_class is not redacted (safe default)."""
        entry = _make_entry("high_risk_success")
        del entry["event_class"]
        result = storage_redact_entry(entry)
        assert result["parameters"] is not None
        assert result["storage_redacted"] is False
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/python/anip-service && python -m pytest tests/test_storage_redaction.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement storage-side redaction**

```python
"""Storage-side redaction — strips parameters from low-value audit entries before persistence."""
from __future__ import annotations

from typing import Any

_LOW_VALUE_CLASSES = frozenset({
    "low_risk_success",
    "malformed_or_spam",
    "repeated_low_value_denial",
})


def storage_redact_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the audit entry with parameters stripped for low-value events.

    High-risk events are returned unchanged (with storage_redacted=False).
    The persisted redacted entry is the canonical hashed form for checkpointing.
    """
    result = {**entry}
    event_class = result.get("event_class")

    if event_class in _LOW_VALUE_CLASSES:
        result["parameters"] = None
        result["storage_redacted"] = True
    else:
        result["storage_redacted"] = False

    return result
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/python/anip-service && python -m pytest tests/test_storage_redaction.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/python/anip-service/src/anip_service/storage_redaction.py packages/python/anip-service/tests/test_storage_redaction.py
git commit -m "feat(python): add storage-side redaction for low-value audit entries"
```

---

## Task 6: Storage-Side Redaction — TypeScript

**Files:**
- Create: `packages/typescript/service/src/storage-redaction.ts`
- Test: `packages/typescript/service/tests/storage-redaction.test.ts`

**Context:** TypeScript mirror of the Python storage-side redaction. Same behavior, same event class scope, same `storage_redacted` marker.

**Step 1: Write failing tests**

```typescript
import { describe, it, expect } from "vitest";
import { storageRedactEntry } from "../src/storage-redaction.js";

const LOW_VALUE_CLASSES = ["low_risk_success", "malformed_or_spam", "repeated_low_value_denial"];
const HIGH_VALUE_CLASSES = ["high_risk_success", "high_risk_denial"];

function makeEntry(eventClass: string): Record<string, unknown> {
  return {
    sequence_number: 1,
    timestamp: "2026-01-01T00:00:00Z",
    capability: "search_flights",
    token_id: "tok-1",
    root_principal: "user@example.com",
    parameters: { origin: "JFK", destination: "LAX" },
    success: eventClass.endsWith("success"),
    failure_type: eventClass.endsWith("success") ? null : "scope_insufficient",
    event_class: eventClass,
    retention_tier: "short",
    invocation_id: "inv-000000000001",
  };
}

describe("storageRedactEntry", () => {
  for (const ec of LOW_VALUE_CLASSES) {
    it(`strips parameters for ${ec}`, () => {
      const result = storageRedactEntry(makeEntry(ec));
      expect(result.parameters).toBeNull();
      expect(result.storage_redacted).toBe(true);
    });
  }

  for (const ec of HIGH_VALUE_CLASSES) {
    it(`preserves parameters for ${ec}`, () => {
      const result = storageRedactEntry(makeEntry(ec));
      expect(result.parameters).toEqual({ origin: "JFK", destination: "LAX" });
      expect(result.storage_redacted).toBe(false);
    });
  }

  it("preserves envelope fields", () => {
    const result = storageRedactEntry(makeEntry("low_risk_success"));
    expect(result.timestamp).toBe("2026-01-01T00:00:00Z");
    expect(result.capability).toBe("search_flights");
    expect(result.invocation_id).toBe("inv-000000000001");
  });

  it("does not mutate original", () => {
    const entry = makeEntry("low_risk_success");
    storageRedactEntry(entry);
    expect(entry.parameters).toEqual({ origin: "JFK", destination: "LAX" });
  });

  it("no event_class treated as high value", () => {
    const entry = makeEntry("high_risk_success");
    delete entry.event_class;
    const result = storageRedactEntry(entry);
    expect(result.parameters).not.toBeNull();
    expect(result.storage_redacted).toBe(false);
  });
});
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/typescript/service && npx vitest run tests/storage-redaction.test.ts`
Expected: FAIL

**Step 3: Implement**

```typescript
/**
 * Storage-side redaction — strips parameters from low-value audit entries before persistence.
 *
 * The persisted redacted entry is the canonical hashed form for checkpointing.
 * This is independent of response-boundary redaction (disclosure level).
 */

const LOW_VALUE_CLASSES = new Set([
  "low_risk_success",
  "malformed_or_spam",
  "repeated_low_value_denial",
]);

export function storageRedactEntry(
  entry: Record<string, unknown>,
): Record<string, unknown> {
  const result = { ...entry };
  const eventClass = result.event_class as string | undefined;

  if (eventClass != null && LOW_VALUE_CLASSES.has(eventClass)) {
    result.parameters = null;
    result.storage_redacted = true;
  } else {
    result.storage_redacted = false;
  }

  return result;
}
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/typescript/service && npx vitest run tests/storage-redaction.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/typescript/service/src/storage-redaction.ts packages/typescript/service/tests/storage-redaction.test.ts
git commit -m "feat(typescript): add storage-side redaction for low-value audit entries"
```

---

## Task 7: Storage-Side Redaction — Service Integration

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/typescript/service/src/service.ts`

**Context:** Wire `storage_redact_entry` / `storageRedactEntry` into the audit logging flow. The redaction runs after classification and before persistence. The audit log's `logEntry` receives the redacted entry as its canonical form for Merkle tree hashing.

**Step 1: Python — Import and apply**

In `service.py`:
- Add `from anip_service.storage_redaction import storage_redact_entry`
- In `_log_audit`, after building the entry dict and before passing to `self._audit.log_entry()`, apply `entry = storage_redact_entry(entry)`

**Step 2: TypeScript — Import and apply**

In `service.ts`:
- Add `import { storageRedactEntry } from "./storage-redaction.js"`
- In `logAudit`, after building the entry object and before passing to `audit.logEntry()`, apply `entry = storageRedactEntry(entry)`

**Step 3: Add `storage_redacted` column to storage schema**

In both runtimes' SQLite storage:
- `packages/python/anip-server/src/anip_server/storage.py` — add `storage_redacted INTEGER DEFAULT 0` to the audit_entries CREATE TABLE
- `packages/typescript/server/src/storage.ts` — same column addition

**Step 4: Run full test suites**

Run: `cd packages/python && python -m pytest -v` (runs all Python tests)
Run: `cd packages/typescript && npx vitest run` (runs all TypeScript tests)
Expected: PASS (existing tests should still pass; storage_redacted is additive)

**Step 5: Commit**

```bash
git add packages/python/anip-service/src/anip_service/service.py packages/typescript/service/src/service.ts packages/python/anip-server/src/anip_server/storage.py packages/typescript/server/src/storage.ts
git commit -m "feat: integrate storage-side redaction into audit logging flow"
```

---

## Task 8: Caller-Class-Aware Redaction — Python

**Files:**
- Create: `packages/python/anip-service/src/anip_service/disclosure.py`
- Test: `packages/python/anip-service/tests/test_disclosure.py`

**Context:** Implements the two-mode disclosure resolution: fixed mode (v0.8 behavior) and policy mode (per-caller). The token's `anip:caller_class` claim is used when available; the service's disclosure policy maps caller class to max disclosure level.

**Step 1: Write failing tests**

```python
"""Tests for caller-class-aware disclosure resolution."""
import pytest
from anip_service.disclosure import resolve_disclosure_level


class TestFixedMode:
    def test_full_returns_full(self):
        assert resolve_disclosure_level("full", token_claims={}) == "full"

    def test_reduced_returns_reduced(self):
        assert resolve_disclosure_level("reduced", token_claims={}) == "reduced"

    def test_redacted_returns_redacted(self):
        assert resolve_disclosure_level("redacted", token_claims={}) == "redacted"

    def test_fixed_mode_ignores_token_claims(self):
        """In fixed mode, token caller_class is irrelevant."""
        result = resolve_disclosure_level(
            "redacted",
            token_claims={"anip:caller_class": "internal"},
            disclosure_policy={"internal": "full"},
        )
        assert result == "redacted"


class TestPolicyMode:
    def test_resolves_from_caller_class(self):
        result = resolve_disclosure_level(
            "policy",
            token_claims={"anip:caller_class": "internal"},
            disclosure_policy={"internal": "full", "default": "redacted"},
        )
        assert result == "full"

    def test_falls_back_to_default(self):
        result = resolve_disclosure_level(
            "policy",
            token_claims={"anip:caller_class": "unknown_class"},
            disclosure_policy={"internal": "full", "default": "reduced"},
        )
        assert result == "reduced"

    def test_falls_back_to_redacted_when_no_default(self):
        result = resolve_disclosure_level(
            "policy",
            token_claims={"anip:caller_class": "unknown_class"},
            disclosure_policy={"internal": "full"},
        )
        assert result == "redacted"

    def test_no_token_claim_uses_default(self):
        result = resolve_disclosure_level(
            "policy",
            token_claims={},
            disclosure_policy={"internal": "full", "default": "reduced"},
        )
        assert result == "reduced"

    def test_scope_derived_class(self):
        """If no anip:caller_class claim, derive from scope."""
        result = resolve_disclosure_level(
            "policy",
            token_claims={"scope": ["audit:full", "travel.search"]},
            disclosure_policy={"audit_full": "full", "default": "redacted"},
        )
        assert result == "full"

    def test_no_policy_in_policy_mode_returns_redacted(self):
        result = resolve_disclosure_level(
            "policy",
            token_claims={"anip:caller_class": "internal"},
            disclosure_policy=None,
        )
        assert result == "redacted"

    def test_policy_mode_with_none_claims(self):
        result = resolve_disclosure_level(
            "policy",
            token_claims=None,
            disclosure_policy={"default": "reduced"},
        )
        assert result == "reduced"
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/python/anip-service && python -m pytest tests/test_disclosure.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement disclosure resolution**

```python
"""Caller-class-aware disclosure resolution.

Two modes:
- Fixed mode (disclosure_level != "policy"): returns the fixed level for all callers.
- Policy mode (disclosure_level == "policy"): resolves from token claims via disclosure_policy.
"""
from __future__ import annotations

from typing import Any

_SCOPE_TO_CLASS = {
    "audit:full": "audit_full",
}


def _resolve_caller_class(token_claims: dict[str, Any] | None) -> str:
    """Extract caller class from token claims."""
    if token_claims is None:
        return "default"

    # 1. Explicit claim
    caller_class = token_claims.get("anip:caller_class")
    if caller_class is not None:
        return str(caller_class)

    # 2. Scope-derived
    scopes = token_claims.get("scope", [])
    if isinstance(scopes, list):
        for scope in scopes:
            if scope in _SCOPE_TO_CLASS:
                return _SCOPE_TO_CLASS[scope]

    return "default"


def resolve_disclosure_level(
    disclosure_level: str,
    *,
    token_claims: dict[str, Any] | None = None,
    disclosure_policy: dict[str, str] | None = None,
) -> str:
    """Resolve the effective disclosure level for a caller.

    If disclosure_level is not "policy", returns that fixed level (v0.8 behavior).
    If "policy", resolves from caller class via disclosure_policy.
    """
    if disclosure_level != "policy":
        return disclosure_level

    caller_class = _resolve_caller_class(token_claims)

    if disclosure_policy is None:
        return "redacted"

    level = disclosure_policy.get(caller_class)
    if level is not None:
        return level

    return disclosure_policy.get("default", "redacted")
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/python/anip-service && python -m pytest tests/test_disclosure.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/python/anip-service/src/anip_service/disclosure.py packages/python/anip-service/tests/test_disclosure.py
git commit -m "feat(python): add caller-class-aware disclosure resolution"
```

---

## Task 9: Caller-Class-Aware Redaction — TypeScript

**Files:**
- Create: `packages/typescript/service/src/disclosure.ts`
- Test: `packages/typescript/service/tests/disclosure.test.ts`

**Context:** TypeScript mirror of the Python disclosure resolver. Same two-mode logic.

**Step 1: Write failing tests**

```typescript
import { describe, it, expect } from "vitest";
import { resolveDisclosureLevel } from "../src/disclosure.js";

describe("Fixed mode", () => {
  it("full returns full", () => {
    expect(resolveDisclosureLevel("full", {})).toBe("full");
  });
  it("reduced returns reduced", () => {
    expect(resolveDisclosureLevel("reduced", {})).toBe("reduced");
  });
  it("redacted returns redacted", () => {
    expect(resolveDisclosureLevel("redacted", {})).toBe("redacted");
  });
  it("ignores token claims in fixed mode", () => {
    expect(
      resolveDisclosureLevel("redacted", { "anip:caller_class": "internal" }, { internal: "full" }),
    ).toBe("redacted");
  });
});

describe("Policy mode", () => {
  it("resolves from caller class", () => {
    expect(
      resolveDisclosureLevel("policy", { "anip:caller_class": "internal" }, { internal: "full", default: "redacted" }),
    ).toBe("full");
  });
  it("falls back to default", () => {
    expect(
      resolveDisclosureLevel("policy", { "anip:caller_class": "unknown" }, { internal: "full", default: "reduced" }),
    ).toBe("reduced");
  });
  it("falls back to redacted when no default", () => {
    expect(
      resolveDisclosureLevel("policy", { "anip:caller_class": "unknown" }, { internal: "full" }),
    ).toBe("redacted");
  });
  it("no token claim uses default", () => {
    expect(
      resolveDisclosureLevel("policy", {}, { internal: "full", default: "reduced" }),
    ).toBe("reduced");
  });
  it("no policy returns redacted", () => {
    expect(
      resolveDisclosureLevel("policy", { "anip:caller_class": "internal" }),
    ).toBe("redacted");
  });
  it("null claims uses default", () => {
    expect(
      resolveDisclosureLevel("policy", null, { default: "reduced" }),
    ).toBe("reduced");
  });
});
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/typescript/service && npx vitest run tests/disclosure.test.ts`
Expected: FAIL

**Step 3: Implement**

```typescript
/**
 * Caller-class-aware disclosure resolution.
 *
 * Two modes:
 * - Fixed mode (disclosureLevel != "policy"): returns the fixed level.
 * - Policy mode ("policy"): resolves from token claims via disclosurePolicy.
 */

const SCOPE_TO_CLASS: Record<string, string> = {
  "audit:full": "audit_full",
};

function resolveCallerClass(
  tokenClaims: Record<string, unknown> | null,
): string {
  if (tokenClaims == null) return "default";

  const callerClass = tokenClaims["anip:caller_class"];
  if (callerClass != null) return String(callerClass);

  const scopes = tokenClaims.scope;
  if (Array.isArray(scopes)) {
    for (const scope of scopes) {
      if (typeof scope === "string" && scope in SCOPE_TO_CLASS) {
        return SCOPE_TO_CLASS[scope];
      }
    }
  }

  return "default";
}

export function resolveDisclosureLevel(
  disclosureLevel: string,
  tokenClaims: Record<string, unknown> | null,
  disclosurePolicy?: Record<string, string>,
): string {
  if (disclosureLevel !== "policy") return disclosureLevel;

  const callerClass = resolveCallerClass(tokenClaims);

  if (disclosurePolicy == null) return "redacted";

  const level = disclosurePolicy[callerClass];
  if (level != null) return level;

  return disclosurePolicy["default"] ?? "redacted";
}
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/typescript/service && npx vitest run tests/disclosure.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/typescript/service/src/disclosure.ts packages/typescript/service/tests/disclosure.test.ts
git commit -m "feat(typescript): add caller-class-aware disclosure resolution"
```

---

## Task 10: Caller-Class Redaction — Service Integration + Discovery

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/typescript/service/src/service.ts`
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/typescript/core/src/models.ts`

**Context:** Wire the disclosure resolver into the service. The service gets a new optional `disclosure_policy` config. When `disclosure_level` is `"policy"`, the resolver is called per-invocation with the token's claims. The discovery posture now reports `caller_classes` when in policy mode.

**Step 1: Python — Add disclosure_policy to service constructor**

In `service.py`:
- Add `disclosure_policy: dict[str, str] | None = None` to `__init__`
- Store as `self._disclosure_policy`
- Import `resolve_disclosure_level` from `anip_service.disclosure`
- Replace `self._disclosure_level` usage in `invoke()`: instead of passing fixed level to `redact_failure`, call `resolve_disclosure_level(self._disclosure_level, token_claims=token_claims, disclosure_policy=self._disclosure_policy)`
- Extract token claims from the DelegationToken (subject, scope, and any extra claims)

**Step 2: Python — Update discovery posture**

In `get_discovery()`, when `self._disclosure_level == "policy"`:
- Set `detail_level: "policy"`
- Add `caller_classes: list(self._disclosure_policy.keys())` if policy exists

**Step 3: Python — Update FailureDisclosure model**

In `models.py`, add optional `caller_classes` field:
```python
class FailureDisclosure(BaseModel):
    detail_level: Literal["full", "reduced", "redacted", "policy"] = "redacted"
    caller_classes: list[str] | None = None
```

**Step 4: TypeScript — Same changes**

Mirror all changes in `service.ts` and `models.ts`:
- Add `disclosurePolicy?: Record<string, string>` to `ANIPServiceOpts`
- Wire `resolveDisclosureLevel` into invoke flow
- Update discovery posture
- Add `caller_classes` to `FailureDisclosure` Zod schema

**Step 5: Run full test suites**

Run: `cd packages/python && python -m pytest -v`
Run: `cd packages/typescript && npx vitest run`
Expected: PASS

**Step 6: Commit**

```bash
git add packages/python/anip-service/src/anip_service/service.py packages/python/anip-core/src/anip_core/models.py packages/typescript/service/src/service.ts packages/typescript/core/src/models.ts
git commit -m "feat: integrate caller-class disclosure into service and discovery posture"
```

---

## Task 11: `proof_unavailable` Client Semantics — Schema + Models

**Files:**
- Modify: `schema/anip.schema.json`
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/typescript/core/src/models.ts`
- Test: `packages/python/anip-core/tests/test_models.py`
- Test: `packages/typescript/core/tests/models.test.ts`

**Context:** Add `expires_hint` as an optional field on checkpoint responses. This is a best-effort, informational ISO 8601 timestamp indicating the earliest expected expiration of audit entries in the checkpoint's range.

**Step 1: Write failing tests (Python)**

Add to `test_models.py`:

```python
def test_checkpoint_body_expires_hint_optional():
    """expires_hint is optional on CheckpointBody."""
    body = CheckpointBody(
        service_id="svc-1",
        checkpoint_id="ckpt-1",
        range={"first_sequence": 1, "last_sequence": 10},
        merkle_root="sha256:abc",
        timestamp="2026-01-01T00:00:00Z",
        entry_count=10,
    )
    assert body.expires_hint is None


def test_checkpoint_body_expires_hint_set():
    """expires_hint can be set to an ISO 8601 timestamp."""
    body = CheckpointBody(
        service_id="svc-1",
        checkpoint_id="ckpt-1",
        range={"first_sequence": 1, "last_sequence": 10},
        merkle_root="sha256:abc",
        timestamp="2026-01-01T00:00:00Z",
        entry_count=10,
        expires_hint="2026-04-01T00:00:00Z",
    )
    assert body.expires_hint == "2026-04-01T00:00:00Z"
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/python/anip-core && python -m pytest tests/test_models.py::test_checkpoint_body_expires_hint_optional tests/test_models.py::test_checkpoint_body_expires_hint_set -v`
Expected: FAIL (no `expires_hint` field on CheckpointBody)

**Step 3: Add expires_hint to Python model**

In `models.py`, update `CheckpointBody`:
```python
class CheckpointBody(BaseModel):
    version: str = "1.0"
    service_id: str
    checkpoint_id: str
    range: dict[str, int]
    merkle_root: str
    previous_checkpoint: str | None = None
    timestamp: str
    entry_count: int
    expires_hint: str | None = None  # best-effort, informational
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/python/anip-core && python -m pytest tests/test_models.py -v`
Expected: PASS

**Step 5: Write failing tests (TypeScript)**

Add to `models.test.ts`:

```typescript
describe("CheckpointBody with expires_hint", () => {
  it("defaults expires_hint to null", () => {
    const body = CheckpointBody.parse({
      service_id: "svc-1",
      checkpoint_id: "ckpt-1",
      range: { first_sequence: 1, last_sequence: 10 },
      merkle_root: "sha256:abc",
      timestamp: "2026-01-01T00:00:00Z",
      entry_count: 10,
    });
    expect(body.expires_hint).toBeNull();
  });

  it("accepts expires_hint", () => {
    const body = CheckpointBody.parse({
      service_id: "svc-1",
      checkpoint_id: "ckpt-1",
      range: { first_sequence: 1, last_sequence: 10 },
      merkle_root: "sha256:abc",
      timestamp: "2026-01-01T00:00:00Z",
      entry_count: 10,
      expires_hint: "2026-04-01T00:00:00Z",
    });
    expect(body.expires_hint).toBe("2026-04-01T00:00:00Z");
  });
});
```

**Step 6: Run tests to verify they fail**

Run: `cd packages/typescript/core && npx vitest run tests/models.test.ts`
Expected: FAIL

**Step 7: Add expires_hint to TypeScript model**

In `models.ts`, update `CheckpointBody`:
```typescript
export const CheckpointBody = z.object({
  version: z.string().default("1.0"),
  service_id: z.string(),
  checkpoint_id: z.string(),
  range: z.object({
    first_sequence: z.number(),
    last_sequence: z.number(),
  }),
  merkle_root: z.string(),
  previous_checkpoint: z.string().nullable().default(null),
  timestamp: z.string(),
  entry_count: z.number(),
  expires_hint: z.string().nullable().default(null),
});
```

**Step 8: Run tests to verify they pass**

Run: `cd packages/typescript/core && npx vitest run tests/models.test.ts`
Expected: PASS

**Step 9: Update JSON schema**

In `schema/anip.schema.json`, add `expires_hint` to the `CheckpointResponse` definition:
```json
"expires_hint": {
  "type": ["string", "null"],
  "description": "Best-effort ISO 8601 timestamp of earliest expected audit entry expiration in this checkpoint's range. Informational, not contractual."
}
```

**Step 10: Commit**

```bash
git add schema/anip.schema.json packages/python/anip-core/src/anip_core/models.py packages/typescript/core/src/models.ts packages/python/anip-core/tests/test_models.py packages/typescript/core/tests/models.test.ts
git commit -m "feat: add expires_hint to checkpoint response schema and models"
```

---

## Task 12: `proof_unavailable` — Service-Side `expires_hint` Computation

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/typescript/service/src/service.ts`

**Context:** When building checkpoint responses, compute `expires_hint` from the earliest `expires_at` value of audit entries in the checkpoint's sequence range. This requires querying the storage for the minimum `expires_at` in the range.

**Step 1: Add storage method for min expires_at**

In both runtimes' storage backends:

Python (`packages/python/anip-server/src/anip_server/storage.py`):
```python
def get_earliest_expiry_in_range(self, first_seq: int, last_seq: int) -> str | None:
    """Return the earliest expires_at value for entries in [first_seq, last_seq]."""
```

TypeScript (`packages/typescript/server/src/storage.ts`):
```typescript
getEarliestExpiryInRange(firstSeq: number, lastSeq: number): Promise<string | null>;
```

**Step 2: Wire into checkpoint response**

In both runtimes' `getCheckpoint` / `get_checkpoint` methods:
- After fetching the checkpoint body, query `get_earliest_expiry_in_range(body.range.first_sequence, body.range.last_sequence)`
- If non-null, include `expires_hint` in the response
- If null (no entries have expiry), omit `expires_hint`

**Step 3: Run full test suites**

Run: `cd packages/python && python -m pytest -v`
Run: `cd packages/typescript && npx vitest run`
Expected: PASS

**Step 4: Commit**

```bash
git add packages/python/anip-service/src/anip_service/service.py packages/python/anip-server/src/anip_server/storage.py packages/typescript/service/src/service.ts packages/typescript/server/src/storage.ts
git commit -m "feat: compute and include expires_hint on checkpoint responses"
```

---

## Task 13: SPEC.md Updates

**Files:**
- Modify: `SPEC.md`

**Context:** Update the protocol spec to document all v0.9 additions. This is documentation work, no runtime changes.

**Step 1: Bump protocol version references from 0.8 to 0.9**

Update title, `PROTOCOL_VERSION` references, and manifest version throughout.

**Step 2: Add §6.9 Audit Aggregation section**

Document:
- Time-window bucketed aggregation for low-value denials
- Grouping key: `(actor_key, capability, failure_type)`
- `repeated_low_value_denial` event class activation
- `aggregate_only` retention tier with P1D duration
- Delayed emission semantics
- AggregatedAuditEntry shape

**Step 3: Add §6.10 Storage-Side Redaction section**

Document:
- Which event classes are redacted (low_risk_success, malformed_or_spam, repeated_low_value_denial)
- What is stripped (parameters)
- Placement in write path (after classification, before persistence)
- `storage_redacted` marker field
- Canonical form for checkpointing
- Explicit distinction from response-boundary redaction

**Step 4: Update §6.8 Failure Redaction for caller-class awareness**

Document:
- Two modes: fixed and policy
- Caller class resolution from token claims
- `anip:caller_class` claim semantics
- Disclosure policy mapping
- Resolution fallback chain
- Discovery posture `caller_classes` field
- Explicit: not trusted on its own, service policy is authority

**Step 5: Update §6.5 Checkpoint for proof_unavailable guidance**

Document:
- `expires_hint` field on checkpoint responses (best-effort, informational)
- SHOULD-level client guidance for proof caching
- `proof_unavailable` is permanent, not transient
- "Live audit entries needed for proof regeneration are no longer available"
- Explicit distinction: checkpoint validity vs proof regenerability

**Step 6: Update Explicit Deferrals section**

- Remove items 1-3 (now implemented)
- Keep selective checkpointing as the remaining deferral (now v0.10)
- Add any new observations from v0.9 work

**Step 7: Commit**

```bash
git add SPEC.md
git commit -m "docs: update SPEC.md for v0.9 protocol follow-up"
```

---

## Task 14: Schema Updates

**Files:**
- Modify: `schema/anip.schema.json`
- Modify: `schema/discovery.schema.json`

**Context:** Update JSON schemas to reflect all v0.9 additions.

**Step 1: Update anip.schema.json**

- Bump `$id` from v0.8 to v0.9
- Add `AggregatedAuditEntry` definition
- Add `storage_redacted` to `AuditEntry`
- Add `expires_hint` to `CheckpointResponse` (if not done in Task 11)

**Step 2: Update discovery.schema.json**

- Bump `$id` from v0.8 to v0.9
- Add optional `caller_classes` array to `failure_disclosure` in posture

**Step 3: Commit**

```bash
git add schema/anip.schema.json schema/discovery.schema.json
git commit -m "docs: update JSON schemas for v0.9"
```

---

## Task 15: Protocol Version Bump

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/constants.py` (or wherever PROTOCOL_VERSION lives)
- Modify: `packages/typescript/core/src/constants.ts`
- Modify: `packages/python/anip-core/src/anip_core/models.py` (ManifestMetadata default version)
- Modify: `packages/typescript/core/src/models.ts` (ManifestMetadata default version)
- Test: Update all tests that assert `"anip/0.8"` to `"anip/0.9"`

**Step 1: Update constants**

Python:
```python
PROTOCOL_VERSION = "anip/0.9"
MANIFEST_VERSION = "0.9.0"
```

TypeScript:
```typescript
export const PROTOCOL_VERSION = "anip/0.9";
export const MANIFEST_VERSION = "0.9.0";
```

**Step 2: Update model defaults**

Both runtimes: `ManifestMetadata.version` default → `"0.9.0"`, `ANIPManifest.protocol` default → `"anip/0.9"`

**Step 3: Update tests**

Find all tests asserting `"anip/0.8"` and update to `"anip/0.9"`.

**Step 4: Run full test suites**

Run: `cd packages/python && python -m pytest -v`
Run: `cd packages/typescript && npx vitest run`
Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: bump protocol version to anip/0.9"
```

---

## Task 16: Final Verification

**Files:** None (verification only)

**Step 1: Run all Python tests**

Run: `cd packages/python && python -m pytest -v`
Expected: All pass

**Step 2: Run all TypeScript tests**

Run: `cd packages/typescript && npx vitest run`
Expected: All pass

**Step 3: Verify schema validity**

Spot-check that `schema/anip.schema.json` and `schema/discovery.schema.json` are valid JSON Schema.

**Step 4: Verify cross-runtime consistency**

Check that:
- Both runtimes export the same new types (AuditAggregator, storageRedactEntry, resolveDisclosureLevel)
- Both runtimes use the same retention defaults (aggregate_only = P1D)
- Both runtimes produce the same aggregated entry shape
- Both runtimes include expires_hint on checkpoint responses
- Protocol version is "anip/0.9" in both runtimes
