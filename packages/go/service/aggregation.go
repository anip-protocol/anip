package service

import (
	"sync"
	"time"
)

// groupingKey is the tuple used to group events in an aggregation window.
type groupingKey struct {
	ActorKey    string
	Capability  string
	FailureType string
}

// bucket tracks events within a single aggregation window for one grouping key.
type bucket struct {
	events               []map[string]any
	firstSeen            time.Time
	lastSeen             time.Time
	representativeDetail string
}

// AggregatedEntry is emitted when a window closes with >1 event for a grouping key.
type AggregatedEntry struct {
	EventClass           string
	RetentionTier        string
	GroupingKey           map[string]string
	WindowStart          string
	WindowEnd            string
	Count                int
	FirstSeen            string
	LastSeen             string
	RepresentativeDetail string
}

// ToAuditDict converts an AggregatedEntry to a map suitable for audit persistence.
func (ae *AggregatedEntry) ToAuditDict() map[string]any {
	return map[string]any{
		"entry_type":            "aggregated",
		"event_class":           ae.EventClass,
		"retention_tier":        ae.RetentionTier,
		"grouping_key":          ae.GroupingKey,
		"aggregation_window":    map[string]string{"start": ae.WindowStart, "end": ae.WindowEnd},
		"aggregation_count":     ae.Count,
		"count":                 ae.Count,
		"first_seen":            ae.FirstSeen,
		"last_seen":             ae.LastSeen,
		"representative_detail": ae.RepresentativeDetail,
		"capability":            ae.GroupingKey["capability"],
		"failure_type":          ae.GroupingKey["failure_type"],
		"success":               false,
	}
}

// windowKey combines a grouping key with a window epoch for map indexing.
type windowKey struct {
	gk    groupingKey
	epoch int64
}

// AuditAggregator buckets low-value denial events by time window.
// Implements SPEC §6.9.
type AuditAggregator struct {
	windowSeconds int64
	mu            sync.Mutex
	windows       map[windowKey]*bucket
}

// NewAuditAggregator creates an aggregator with the given window size in seconds.
func NewAuditAggregator(windowSeconds int) *AuditAggregator {
	return &AuditAggregator{
		windowSeconds: int64(windowSeconds),
		windows:       make(map[windowKey]*bucket),
	}
}

// Submit adds an event to the aggregator.
func (a *AuditAggregator) Submit(event map[string]any) {
	a.mu.Lock()
	defer a.mu.Unlock()

	actorKey, _ := event["actor_key"].(string)
	if actorKey == "" {
		actorKey = "anonymous"
	}
	capability, _ := event["capability"].(string)
	if capability == "" {
		capability = "_pre_auth"
	}
	failureType, _ := event["failure_type"].(string)
	if failureType == "" {
		failureType = "unknown"
	}

	ts := parseTimestamp(event)
	epoch := ts.Unix() - (ts.Unix() % a.windowSeconds)

	gk := groupingKey{ActorKey: actorKey, Capability: capability, FailureType: failureType}
	wk := windowKey{gk: gk, epoch: epoch}

	b, ok := a.windows[wk]
	if !ok {
		detail, _ := event["detail"].(string)
		if len(detail) > 200 {
			detail = detail[:200]
		}
		b = &bucket{
			firstSeen:            ts,
			lastSeen:             ts,
			representativeDetail: detail,
		}
		a.windows[wk] = b
	}
	b.events = append(b.events, event)
	if ts.After(b.lastSeen) {
		b.lastSeen = ts
	}
}

// Flush closes all windows whose end time <= now and returns the results.
// Single-event buckets pass through as map[string]any.
// Multi-event buckets produce *AggregatedEntry.
func (a *AuditAggregator) Flush(now time.Time) []any {
	a.mu.Lock()
	defer a.mu.Unlock()

	var results []any
	nowUnix := now.Unix()

	for wk, b := range a.windows {
		windowEnd := wk.epoch + a.windowSeconds
		if windowEnd > nowUnix {
			continue // window still open
		}

		windowStartStr := time.Unix(wk.epoch, 0).UTC().Format(time.RFC3339)
		windowEndStr := time.Unix(windowEnd, 0).UTC().Format(time.RFC3339)

		if len(b.events) == 1 {
			results = append(results, b.events[0])
		} else {
			results = append(results, &AggregatedEntry{
				EventClass:    "repeated_low_value_denial",
				RetentionTier: "aggregate_only",
				GroupingKey: map[string]string{
					"actor_key":    wk.gk.ActorKey,
					"capability":   wk.gk.Capability,
					"failure_type": wk.gk.FailureType,
				},
				WindowStart:          windowStartStr,
				WindowEnd:            windowEndStr,
				Count:                len(b.events),
				FirstSeen:            b.firstSeen.UTC().Format(time.RFC3339),
				LastSeen:             b.lastSeen.UTC().Format(time.RFC3339),
				RepresentativeDetail: b.representativeDetail,
			})
		}
		delete(a.windows, wk)
	}

	return results
}

func parseTimestamp(event map[string]any) time.Time {
	if ts, ok := event["timestamp"].(string); ok {
		if t, err := time.Parse(time.RFC3339, ts); err == nil {
			return t
		}
	}
	return time.Now().UTC()
}
