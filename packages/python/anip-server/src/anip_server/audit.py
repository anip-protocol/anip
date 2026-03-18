"""Audit log manager for ANIP services."""
from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Awaitable
from datetime import datetime, timezone
from typing import Any, Callable

from .storage import StorageBackend
from .merkle import MerkleTree


class AuditLog:
    """Audit log backed by a StorageBackend with Merkle tree accumulation."""

    def __init__(
        self,
        storage: StorageBackend,
        signer: Callable[[dict[str, Any]], str | Awaitable[str]] | None = None,
    ) -> None:
        self._storage = storage
        self._signer = signer
        self._merkle = MerkleTree()

    async def log_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
        """Log an audit entry: compute hash chain, sign, accumulate into Merkle tree, store.

        entry_data should contain: capability, token_id, root_principal, success,
        and optionally: issuer, subject, parameters, result_summary, failure_type,
        cost_actual, delegation_chain.

        Returns the complete entry dict (with sequence_number, timestamp, previous_hash, signature).
        """
        last = await self._storage.get_last_audit_entry()
        if last is None:
            sequence_number = 1
            previous_hash = "sha256:0"
        else:
            sequence_number = last["sequence_number"] + 1
            previous_hash = self._compute_entry_hash(last)

        now = datetime.now(timezone.utc).isoformat()

        entry = {
            "sequence_number": sequence_number,
            "timestamp": now,
            "capability": entry_data["capability"],
            "token_id": entry_data.get("token_id"),
            "issuer": entry_data.get("issuer"),
            "subject": entry_data.get("subject"),
            "root_principal": entry_data.get("root_principal"),
            "parameters": entry_data.get("parameters"),
            "success": entry_data["success"],
            "result_summary": entry_data.get("result_summary"),
            "failure_type": entry_data.get("failure_type"),
            "cost_actual": entry_data.get("cost_actual"),
            "delegation_chain": entry_data.get("delegation_chain"),
            "invocation_id": entry_data.get("invocation_id"),
            "client_reference_id": entry_data.get("client_reference_id"),
            "stream_summary": entry_data.get("stream_summary"),
            "event_class": entry_data.get("event_class"),
            "retention_tier": entry_data.get("retention_tier"),
            "expires_at": entry_data.get("expires_at"),
            "storage_redacted": entry_data.get("storage_redacted", False),
            "entry_type": entry_data.get("entry_type"),
            "grouping_key": entry_data.get("grouping_key"),
            "aggregation_window": entry_data.get("aggregation_window"),
            "aggregation_count": entry_data.get("aggregation_count"),
            "first_seen": entry_data.get("first_seen"),
            "last_seen": entry_data.get("last_seen"),
            "representative_detail": entry_data.get("representative_detail"),
            "previous_hash": previous_hash,
        }

        # Accumulate into Merkle tree
        canonical_bytes = self._canonical_bytes(entry)
        self._merkle.add_leaf(canonical_bytes)

        # Sign if signer is provided (handle both sync and async signers)
        if self._signer:
            sig = self._signer(entry)
            if inspect.isawaitable(sig):
                sig = await sig
            entry["signature"] = sig
        else:
            entry["signature"] = None

        await self._storage.store_audit_entry(entry)
        return entry

    async def query(self, **filters: Any) -> list[dict[str, Any]]:
        """Query audit entries with optional filters."""
        return await self._storage.query_audit_entries(**filters)

    def get_merkle_snapshot(self) -> dict[str, Any]:
        """Return the current Merkle tree snapshot."""
        return self._merkle.snapshot()

    @staticmethod
    def _compute_entry_hash(entry: dict[str, Any]) -> str:
        canonical = json.dumps(
            {k: v for k, v in sorted(entry.items()) if k not in ("signature", "id")},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return f"sha256:{hashlib.sha256(canonical).hexdigest()}"

    @staticmethod
    def _canonical_bytes(entry: dict[str, Any]) -> bytes:
        return json.dumps(
            {k: v for k, v in sorted(entry.items()) if k not in ("signature", "id")},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
