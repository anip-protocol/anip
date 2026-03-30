"""Audit log manager for ANIP services."""
from __future__ import annotations

import inspect
from collections.abc import Awaitable
from datetime import datetime, timezone
from typing import Any, Callable

from .storage import StorageBackend


class AuditLog:
    """Audit log backed by a StorageBackend.

    Sequence numbers, hash chaining, and Merkle accumulation are now
    handled by the storage layer (``append_audit_entry``).
    """

    def __init__(
        self,
        storage: StorageBackend,
        signer: Callable[[dict[str, Any]], str | Awaitable[str]] | None = None,
    ) -> None:
        self._storage = storage
        self._signer = signer

    async def log_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
        """Log an audit entry via the storage backend.

        entry_data should contain: capability, token_id, root_principal, success,
        and optionally: issuer, subject, parameters, result_summary, failure_type,
        cost_actual, delegation_chain.

        Returns the complete entry dict (with sequence_number, timestamp, previous_hash, signature).
        """
        now = datetime.now(timezone.utc).isoformat()
        entry_for_storage = {
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
            "task_id": entry_data.get("task_id"),
            "parent_invocation_id": entry_data.get("parent_invocation_id"),
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
        }

        entry = await self._storage.append_audit_entry(entry_for_storage)

        if self._signer:
            sig = self._signer(entry)
            if inspect.isawaitable(sig):
                sig = await sig
            entry["signature"] = sig
            await self._storage.update_audit_signature(entry["sequence_number"], sig)
        else:
            entry["signature"] = None

        return entry

    async def query(self, **filters: Any) -> list[dict[str, Any]]:
        """Query audit entries with optional filters."""
        return await self._storage.query_audit_entries(**filters)
