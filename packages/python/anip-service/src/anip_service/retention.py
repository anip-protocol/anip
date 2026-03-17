"""Retention policy for v0.8 security hardening.

Two-layer policy model:
  1. EventClass -> RetentionTier
  2. RetentionTier -> Duration
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

DEFAULT_CLASS_TO_TIER: dict[str, str] = {
    "high_risk_success": "long",
    "high_risk_denial": "medium",
    "low_risk_success": "short",
    "repeated_low_value_denial": "short",
    "malformed_or_spam": "short",
}

DEFAULT_TIER_TO_DURATION: dict[str, str | None] = {
    "long": "P365D",
    "medium": "P90D",
    "short": "P7D",
    "aggregate_only": "P7D",  # v0.8 placeholder
}

_DURATION_RE = re.compile(r"^P(\d+)D$")


def _parse_iso_duration_days(duration: str) -> int:
    m = _DURATION_RE.match(duration)
    if not m:
        raise ValueError(f"Unsupported ISO 8601 duration: {duration!r}")
    return int(m.group(1))


class RetentionPolicy:
    def __init__(
        self,
        *,
        class_to_tier: dict[str, str] | None = None,
        tier_to_duration: dict[str, str | None] | None = None,
    ):
        self._class_to_tier = {**DEFAULT_CLASS_TO_TIER, **(class_to_tier or {})}
        self._tier_to_duration = {**DEFAULT_TIER_TO_DURATION, **(tier_to_duration or {})}

    @property
    def default_retention(self) -> str | None:
        """The medium-tier duration, used as the representative retention for discovery."""
        return self._tier_to_duration.get("medium")

    def resolve_tier(self, event_class: str) -> str:
        return self._class_to_tier.get(event_class, "short")

    def compute_expires_at(self, tier: str, now: datetime | None = None) -> str | None:
        now = now or datetime.now(timezone.utc)
        duration = self._tier_to_duration.get(tier)
        if duration is None:
            return None
        days = _parse_iso_duration_days(duration)
        expires = now + timedelta(days=days)
        return expires.isoformat()
