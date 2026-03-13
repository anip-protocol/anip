"""Checkpoint policy for the ANIP audit log."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CheckpointPolicy:
    """Defines when a checkpoint should be created.

    At least one trigger must be set for ``should_checkpoint`` to ever
    return ``True``.
    """

    entry_count: int | None = None
    interval_seconds: int | None = None

    def should_checkpoint(
        self, entries_since_last: int, seconds_since_last: float = 0
    ) -> bool:
        """Return ``True`` when any configured threshold is met."""
        if self.entry_count is not None and entries_since_last >= self.entry_count:
            return True
        if (
            self.interval_seconds is not None
            and seconds_since_last >= self.interval_seconds
        ):
            return True
        return False
