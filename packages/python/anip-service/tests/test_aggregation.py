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
