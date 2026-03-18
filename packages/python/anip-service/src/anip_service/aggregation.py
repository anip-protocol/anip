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
