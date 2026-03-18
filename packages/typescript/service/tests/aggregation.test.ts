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
