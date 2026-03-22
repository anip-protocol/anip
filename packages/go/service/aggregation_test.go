package service

import (
	"testing"
	"time"
)

func TestAggregator_SingleEventPassesThrough(t *testing.T) {
	agg := NewAuditAggregator(60)
	now := time.Date(2026, 1, 1, 0, 0, 30, 0, time.UTC)

	agg.Submit(map[string]any{
		"actor_key":    "agent:test",
		"capability":   "search",
		"failure_type": "scope_insufficient",
		"timestamp":    now.Format(time.RFC3339),
	})

	flushTime := time.Date(2026, 1, 1, 0, 1, 1, 0, time.UTC)
	results := agg.Flush(flushTime)
	if len(results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(results))
	}
	entry, ok := results[0].(map[string]any)
	if !ok {
		t.Fatal("single event should pass through as map[string]any")
	}
	if entry["actor_key"] != "agent:test" {
		t.Error("entry should preserve original fields")
	}
}

func TestAggregator_MultipleEventsAggregate(t *testing.T) {
	agg := NewAuditAggregator(60)
	base := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)

	for i := 0; i < 5; i++ {
		agg.Submit(map[string]any{
			"actor_key":    "agent:spam",
			"capability":   "search",
			"failure_type": "scope_insufficient",
			"timestamp":    base.Add(time.Duration(i) * time.Second).Format(time.RFC3339),
			"detail":       "first detail",
		})
	}

	flushTime := base.Add(61 * time.Second)
	results := agg.Flush(flushTime)
	if len(results) != 1 {
		t.Fatalf("expected 1 aggregated result, got %d", len(results))
	}

	aggEntry, ok := results[0].(*AggregatedEntry)
	if !ok {
		t.Fatal("multiple events should produce *AggregatedEntry")
	}
	if aggEntry.Count != 5 {
		t.Errorf("count = %d, want 5", aggEntry.Count)
	}
	if aggEntry.EventClass != "repeated_low_value_denial" {
		t.Errorf("event_class = %q, want repeated_low_value_denial", aggEntry.EventClass)
	}
	if aggEntry.RetentionTier != "aggregate_only" {
		t.Errorf("retention_tier = %q, want aggregate_only", aggEntry.RetentionTier)
	}
}

func TestAggregator_DifferentKeysNotMerged(t *testing.T) {
	agg := NewAuditAggregator(60)
	base := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)

	agg.Submit(map[string]any{
		"actor_key": "agent:a", "capability": "search",
		"failure_type": "scope_insufficient", "timestamp": base.Format(time.RFC3339),
	})
	agg.Submit(map[string]any{
		"actor_key": "agent:b", "capability": "search",
		"failure_type": "scope_insufficient", "timestamp": base.Format(time.RFC3339),
	})

	results := agg.Flush(base.Add(61 * time.Second))
	if len(results) != 2 {
		t.Fatalf("different actor_keys should produce 2 results, got %d", len(results))
	}
}

func TestAggregator_FlushDoesNotEmitOpenWindows(t *testing.T) {
	agg := NewAuditAggregator(60)
	now := time.Date(2026, 1, 1, 0, 0, 30, 0, time.UTC)

	agg.Submit(map[string]any{
		"actor_key": "agent:test", "capability": "search",
		"failure_type": "scope_insufficient", "timestamp": now.Format(time.RFC3339),
	})

	results := agg.Flush(now.Add(10 * time.Second))
	if len(results) != 0 {
		t.Fatalf("should not flush open windows, got %d results", len(results))
	}
}

func TestAggregatedEntry_ToAuditDict(t *testing.T) {
	ae := &AggregatedEntry{
		EventClass:    "repeated_low_value_denial",
		RetentionTier: "aggregate_only",
		GroupingKey: map[string]string{
			"actor_key": "agent:test", "capability": "search", "failure_type": "scope_insufficient",
		},
		WindowStart:          "2026-01-01T00:00:00Z",
		WindowEnd:            "2026-01-01T00:01:00Z",
		Count:                10,
		FirstSeen:            "2026-01-01T00:00:05Z",
		LastSeen:             "2026-01-01T00:00:55Z",
		RepresentativeDetail: "Insufficient scope",
	}
	d := ae.ToAuditDict()
	if d["entry_type"] != "aggregated" {
		t.Errorf("entry_type = %q, want aggregated", d["entry_type"])
	}
	if d["count"] != 10 {
		t.Errorf("count = %v, want 10", d["count"])
	}
	if d["capability"] != "search" {
		t.Errorf("capability = %v, want search", d["capability"])
	}
}
