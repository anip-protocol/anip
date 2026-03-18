"""Checkpoint policy and scheduling for ANIP audit logs."""
from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .hashing import canonical_bytes as _canonical_bytes
from .merkle import MerkleTree
from .storage import StorageBackend


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
    """Background scheduler that coordinates checkpoint generation."""

    def __init__(
        self,
        interval_seconds: int,
        create_fn: Callable[[], Awaitable[None]],
    ):
        self._interval = interval_seconds
        self._create_fn = create_fn
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self._create_fn()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # Non-fatal


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


async def reconstruct_and_create_checkpoint(
    *,
    storage: StorageBackend,
    service_id: str,
    sign_fn: Callable[[bytes], str] | None = None,
) -> tuple[dict[str, Any], str] | None:
    """Reconstruct Merkle tree from storage and create a checkpoint.

    Reads ALL audit entries from storage, rebuilds the cumulative Merkle
    tree, and produces a new checkpoint covering everything up to the
    current max sequence number.

    Returns (body, signature) or None if no new entries since last checkpoint.
    """
    max_seq = await storage.get_max_audit_sequence()
    if max_seq is None:
        return None

    checkpoints = await storage.get_checkpoints(limit=1)
    last_cp = checkpoints[-1] if checkpoints else None
    last_covered = last_cp["range"]["last_sequence"] if last_cp else 0

    if max_seq <= last_covered:
        return None  # No new entries

    # Full reconstruction from entry 1
    entries = await storage.get_audit_entries_range(1, max_seq)

    # Rebuild Merkle tree
    tree = MerkleTree()
    for entry in entries:
        tree.add_leaf(_canonical_bytes(entry))

    snapshot = tree.snapshot()

    # For cumulative checkpoints the range always starts at 1 because the
    # Merkle tree is rebuilt from the very first entry.  create_checkpoint
    # would normally compute first_sequence from the previous checkpoint's
    # last_sequence, so we pass a synthetic copy with last_sequence=0 to
    # force first_sequence=1 while keeping checkpoint_id for numbering.
    synthetic_prev: dict[str, Any] | None = None
    if last_cp is not None:
        synthetic_prev = {
            **last_cp,
            "range": {**last_cp["range"], "last_sequence": 0},
        }

    body, signature = create_checkpoint(
        merkle_snapshot=snapshot,
        service_id=service_id,
        previous_checkpoint=synthetic_prev,
        sign_fn=sign_fn,
    )

    # Restore the correct previous_checkpoint hash (computed from the
    # real stored checkpoint, not the synthetic copy).
    if last_cp is not None:
        prev_body_canonical = json.dumps(
            last_cp, separators=(",", ":"), sort_keys=True
        ).encode()
        body["previous_checkpoint"] = (
            f"sha256:{hashlib.sha256(prev_body_canonical).hexdigest()}"
        )

    # Re-sign with the corrected body if a sign_fn was provided.
    if last_cp is not None and sign_fn is not None:
        cb = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
        signature = sign_fn(cb)

    return body, signature
