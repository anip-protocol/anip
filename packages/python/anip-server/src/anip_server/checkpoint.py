"""Checkpoint policy and scheduling for ANIP audit logs."""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass
class CheckpointPolicy:
    """Defines when a checkpoint should be created."""

    entry_count: int | None = None
    interval_seconds: int | None = None

    def should_checkpoint(
        self, entries_since_last: int, seconds_since_last: float = 0
    ) -> bool:
        if self.entry_count is not None and entries_since_last >= self.entry_count:
            return True
        if (
            self.interval_seconds is not None
            and seconds_since_last >= self.interval_seconds
        ):
            return True
        return False


class CheckpointScheduler:
    """Background timer that triggers checkpoints on a time interval."""

    def __init__(
        self,
        interval_seconds: int,
        create_fn: Callable[[], object],
        has_new_entries_fn: Callable[[], bool],
    ):
        self._interval = interval_seconds
        self._create_fn = create_fn
        self._has_new_entries = has_new_entries_fn
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            if self._has_new_entries():
                self._create_fn()


def create_checkpoint(
    *,
    merkle_snapshot: dict[str, Any],
    service_id: str,
    previous_checkpoint: dict[str, Any] | None,
    sign_fn: Callable[[bytes], str] | None = None,
) -> tuple[dict[str, Any], str]:
    """Create a checkpoint body and sign it.

    Returns (body_dict, signature_string).
    """
    if previous_checkpoint is None:
        first_sequence = 1
        prev_hash = None
        checkpoint_number = 1
    else:
        first_sequence = (
            previous_checkpoint.get("range", {}).get("last_sequence", 0) + 1
        )
        prev_body_canonical = json.dumps(
            previous_checkpoint, separators=(",", ":"), sort_keys=True
        ).encode()
        prev_hash = f"sha256:{hashlib.sha256(prev_body_canonical).hexdigest()}"
        prev_id = previous_checkpoint.get("checkpoint_id", "ckpt-0")
        checkpoint_number = int(prev_id.split("-")[1]) + 1

    last_sequence = merkle_snapshot["leaf_count"]
    entry_count = last_sequence - first_sequence + 1

    body = {
        "version": "0.3",
        "service_id": service_id,
        "checkpoint_id": f"ckpt-{checkpoint_number}",
        "range": {
            "first_sequence": first_sequence,
            "last_sequence": last_sequence,
        },
        "merkle_root": merkle_snapshot["root"],
        "previous_checkpoint": prev_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entry_count": entry_count,
    }

    canonical_bytes = json.dumps(
        body, separators=(",", ":"), sort_keys=True
    ).encode()
    signature = sign_fn(canonical_bytes) if sign_fn else ""

    return body, signature
