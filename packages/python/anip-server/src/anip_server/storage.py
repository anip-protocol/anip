"""Storage abstraction and implementations for ANIP server.

Provides a ``StorageBackend`` protocol, an in-memory implementation for
testing, and a concrete ``SQLiteStorage`` class that persists delegation
tokens, audit log entries, and checkpoints.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, runtime_checkable

from .hashing import compute_entry_hash


@runtime_checkable
class StorageBackend(Protocol):
    """Abstract async storage interface for ANIP server components."""

    async def store_token(self, token_data: dict[str, Any]) -> None: ...

    async def load_token(self, token_id: str) -> dict[str, Any] | None: ...

    async def store_audit_entry(self, entry: dict[str, Any]) -> None: ...

    async def query_audit_entries(
        self,
        *,
        capability: str | None = None,
        root_principal: str | None = None,
        since: str | None = None,
        invocation_id: str | None = None,
        client_reference_id: str | None = None,
        event_class: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]: ...

    async def get_last_audit_entry(self) -> dict[str, Any] | None: ...

    async def delete_expired_audit_entries(self, now_iso: str) -> int: ...

    async def get_audit_entries_range(
        self, first: int, last: int
    ) -> list[dict[str, Any]]: ...

    async def store_checkpoint(self, body: dict[str, Any], signature: str) -> None: ...

    async def get_checkpoints(self, limit: int = 10) -> list[dict[str, Any]]: ...

    async def get_checkpoint_by_id(
        self, checkpoint_id: str
    ) -> dict[str, Any] | None: ...

    async def get_earliest_expiry_in_range(
        self, first_seq: int, last_seq: int
    ) -> str | None: ...

    async def append_audit_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
        """Atomically append an audit entry, assigning sequence_number and previous_hash.

        The caller provides the entry WITHOUT sequence_number or previous_hash.
        The storage layer assigns both atomically and returns the complete entry (unsigned).
        """
        ...

    async def update_audit_signature(self, sequence_number: int, signature: str) -> None:
        """Set the signature on an already-appended audit entry.

        Called after append_audit_entry to attach the cryptographic signature.
        The entry is briefly unsigned between append and this call.
        """
        ...

    async def get_max_audit_sequence(self) -> int | None:
        """Return the highest sequence_number in the audit log, or None if empty."""
        ...

    async def try_acquire_exclusive(self, key: str, holder: str, ttl_seconds: int) -> bool:
        """Attempt to acquire an exclusive lease. Returns True if acquired."""
        ...

    async def release_exclusive(self, key: str, holder: str) -> None:
        """Release an exclusive lease if held by the given holder."""
        ...

    async def try_acquire_leader(self, role: str, holder: str, ttl_seconds: int) -> bool:
        """Attempt to acquire a leader lease for a background role. Returns True if acquired."""
        ...

    async def release_leader(self, role: str, holder: str) -> None:
        """Release a leader lease if held by the given holder."""
        ...


# ---------------------------------------------------------------------------
# In-memory implementation (for testing)
# ---------------------------------------------------------------------------


class InMemoryStorage:
    """In-memory implementation of :class:`StorageBackend` for testing."""

    def __init__(self) -> None:
        self._tokens: dict[str, dict[str, Any]] = {}
        self._audit_entries: list[dict[str, Any]] = []
        self._checkpoints: list[dict[str, Any]] = []
        self._exclusive_leases: dict[str, tuple[str, datetime]] = {}

    # -- tokens -------------------------------------------------------------

    async def store_token(self, token_data: dict[str, Any]) -> None:
        """Store a delegation token."""
        self._tokens[token_data["token_id"]] = dict(token_data)

    async def load_token(self, token_id: str) -> dict[str, Any] | None:
        """Load a delegation token by ID."""
        token = self._tokens.get(token_id)
        if token is None:
            return None
        return dict(token)

    # -- audit log ----------------------------------------------------------

    async def store_audit_entry(self, entry: dict[str, Any]) -> None:
        """Store an already-complete audit entry."""
        self._audit_entries.append(dict(entry))

    async def query_audit_entries(
        self,
        *,
        capability: str | None = None,
        root_principal: str | None = None,
        since: str | None = None,
        invocation_id: str | None = None,
        client_reference_id: str | None = None,
        event_class: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query audit entries with optional filters."""
        results = list(self._audit_entries)

        if capability is not None:
            results = [e for e in results if e.get("capability") == capability]
        if root_principal is not None:
            results = [e for e in results if e.get("root_principal") == root_principal]
        if since is not None:
            results = [e for e in results if e.get("timestamp", "") >= since]
        if invocation_id is not None:
            results = [e for e in results if e.get("invocation_id") == invocation_id]
        if client_reference_id is not None:
            results = [
                e for e in results
                if e.get("client_reference_id") == client_reference_id
            ]
        if event_class is not None:
            results = [e for e in results if e.get("event_class") == event_class]

        # Sort by sequence_number descending
        results.sort(key=lambda e: e.get("sequence_number", 0), reverse=True)
        return [dict(e) for e in results[:limit]]

    async def delete_expired_audit_entries(self, now_iso: str) -> int:
        """Delete audit entries where expires_at is not None and < now_iso."""
        expired = [
            e for e in self._audit_entries
            if e.get("expires_at") is not None and e["expires_at"] < now_iso
        ]
        for e in expired:
            self._audit_entries.remove(e)
        return len(expired)

    async def get_last_audit_entry(self) -> dict[str, Any] | None:
        """Return the audit entry with the highest sequence_number."""
        if not self._audit_entries:
            return None
        return dict(max(self._audit_entries, key=lambda e: e.get("sequence_number", 0)))

    async def get_audit_entries_range(
        self, first: int, last: int
    ) -> list[dict[str, Any]]:
        """Return audit entries with sequence_number BETWEEN first AND last."""
        results = [
            e for e in self._audit_entries
            if first <= e.get("sequence_number", 0) <= last
        ]
        results.sort(key=lambda e: e.get("sequence_number", 0))
        return [dict(e) for e in results]

    # -- checkpoints --------------------------------------------------------

    async def store_checkpoint(self, body: dict[str, Any], signature: str) -> None:
        """Insert a checkpoint record."""
        record = dict(body)
        record["signature"] = signature
        self._checkpoints.append(record)

    async def get_checkpoints(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return checkpoints in insertion order, limited."""
        return [dict(ckpt) for ckpt in self._checkpoints[:limit]]

    async def get_checkpoint_by_id(
        self, checkpoint_id: str
    ) -> dict[str, Any] | None:
        """Return a single checkpoint by its checkpoint_id."""
        for ckpt in self._checkpoints:
            if ckpt.get("checkpoint_id") == checkpoint_id:
                return dict(ckpt)
        return None

    async def get_earliest_expiry_in_range(
        self, first_seq: int, last_seq: int
    ) -> str | None:
        """Return the earliest expires_at value for entries in [first_seq, last_seq]."""
        candidates = [
            e["expires_at"]
            for e in self._audit_entries
            if first_seq <= e.get("sequence_number", 0) <= last_seq
            and e.get("expires_at") is not None
        ]
        if not candidates:
            return None
        return min(candidates)

    # -- horizontal-scaling: audit append / signature / sequence -------------

    async def append_audit_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
        """Atomically append an audit entry, assigning sequence_number and previous_hash."""
        last = self._audit_entries[-1] if self._audit_entries else None
        if last is None:
            seq = 1
            prev_hash = "sha256:0"
        else:
            seq = last["sequence_number"] + 1
            prev_hash = compute_entry_hash(last)
        entry = {**entry_data, "sequence_number": seq, "previous_hash": prev_hash}
        self._audit_entries.append(entry)
        return entry

    async def update_audit_signature(self, sequence_number: int, signature: str) -> None:
        """Set the signature on an already-appended audit entry."""
        for entry in self._audit_entries:
            if entry["sequence_number"] == sequence_number:
                entry["signature"] = signature
                return

    async def get_max_audit_sequence(self) -> int | None:
        """Return the highest sequence_number in the audit log, or None if empty."""
        if not self._audit_entries:
            return None
        return max(e["sequence_number"] for e in self._audit_entries)

    # -- horizontal-scaling: exclusive leases --------------------------------

    async def try_acquire_exclusive(self, key: str, holder: str, ttl_seconds: int) -> bool:
        """Attempt to acquire an exclusive lease. Returns True if acquired."""
        now = datetime.now(timezone.utc)
        existing = self._exclusive_leases.get(key)
        if existing is None or existing[1] < now or existing[0] == holder:
            self._exclusive_leases[key] = (holder, now + timedelta(seconds=ttl_seconds))
            return True
        return False

    async def release_exclusive(self, key: str, holder: str) -> None:
        """Release an exclusive lease if held by the given holder."""
        existing = self._exclusive_leases.get(key)
        if existing is not None and existing[0] == holder:
            del self._exclusive_leases[key]

    async def try_acquire_leader(self, role: str, holder: str, ttl_seconds: int) -> bool:
        """Attempt to acquire a leader lease for a background role."""
        return await self.try_acquire_exclusive(f"leader:{role}", holder, ttl_seconds)

    async def release_leader(self, role: str, holder: str) -> None:
        """Release a leader lease if held by the given holder."""
        await self.release_exclusive(f"leader:{role}", holder)


# ---------------------------------------------------------------------------
# SQLite implementation
# ---------------------------------------------------------------------------

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS delegation_tokens (
    token_id TEXT PRIMARY KEY,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    scope TEXT NOT NULL,          -- JSON array
    purpose TEXT,                 -- JSON object
    parent TEXT,
    expires TEXT NOT NULL,        -- ISO 8601
    constraints TEXT,             -- JSON object
    root_principal TEXT,
    caller_class TEXT,
    registered_at TEXT NOT NULL,
    FOREIGN KEY (parent) REFERENCES delegation_tokens(token_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_number INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    capability TEXT NOT NULL,
    token_id TEXT,
    issuer TEXT,
    subject TEXT,
    root_principal TEXT,
    parameters TEXT,               -- JSON
    success INTEGER NOT NULL,
    result_summary TEXT,           -- JSON (truncated)
    failure_type TEXT,
    cost_actual TEXT,              -- JSON
    delegation_chain TEXT,         -- JSON array of token_ids
    invocation_id TEXT,
    client_reference_id TEXT,
    stream_summary TEXT,
    previous_hash TEXT NOT NULL,
    signature TEXT,
    event_class TEXT,
    retention_tier TEXT,
    expires_at TEXT,
    storage_redacted INTEGER DEFAULT 0,
    entry_type TEXT,
    grouping_key TEXT,
    aggregation_window TEXT,
    aggregation_count INTEGER,
    first_seen TEXT,
    last_seen TEXT,
    representative_detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_capability
    ON audit_log(capability);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp
    ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_root_principal
    ON audit_log(root_principal);
CREATE INDEX IF NOT EXISTS idx_audit_invocation_id
    ON audit_log(invocation_id);
CREATE INDEX IF NOT EXISTS idx_audit_client_reference_id
    ON audit_log(client_reference_id);
CREATE INDEX IF NOT EXISTS idx_audit_event_class
    ON audit_log(event_class);
CREATE INDEX IF NOT EXISTS idx_audit_expires_at
    ON audit_log(expires_at);

CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_id TEXT NOT NULL UNIQUE,
    first_sequence INTEGER,
    last_sequence INTEGER,
    merkle_root TEXT NOT NULL,
    previous_checkpoint TEXT,
    timestamp TEXT,
    entry_count INTEGER,
    signature TEXT NOT NULL
);
"""

_JSON_AUDIT_FIELDS = (
    "parameters",
    "result_summary",
    "cost_actual",
    "delegation_chain",
    "stream_summary",
    "grouping_key",
    "aggregation_window",
)


class SQLiteStorage:
    """SQLite-backed implementation of :class:`StorageBackend`.

    Synchronous sqlite3 calls are isolated in private ``_sync_*`` methods.
    The public async methods delegate to them via ``asyncio.to_thread`` so
    that database I/O never blocks the event loop.
    """

    def __init__(self, db_path: str = "anip.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)

        # Migrate existing v0.3 databases: add lineage columns if missing
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN invocation_id TEXT")
        except Exception:
            pass  # column already exists
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN client_reference_id TEXT")
        except Exception:
            pass  # column already exists
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN stream_summary TEXT")
        except Exception:
            pass  # column already exists
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN event_class TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN retention_tier TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN expires_at TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN storage_redacted INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN entry_type TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN grouping_key TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN aggregation_window TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN aggregation_count INTEGER")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN first_seen TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN last_seen TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN representative_detail TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE delegation_tokens ADD COLUMN caller_class TEXT")
        except Exception:
            pass

        # In-memory leases (single-process is fine for SQLite)
        self._exclusive_leases: dict[str, tuple[str, datetime]] = {}

    # -- sync internals (private) -------------------------------------------

    def _sync_store_token(self, token_data: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO delegation_tokens
                   (token_id, issuer, subject, scope, purpose, parent,
                    expires, constraints, root_principal, caller_class, registered_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    token_data["token_id"],
                    token_data["issuer"],
                    token_data["subject"],
                    json.dumps(token_data.get("scope", [])),
                    json.dumps(token_data.get("purpose")),
                    token_data.get("parent"),
                    token_data["expires"],
                    json.dumps(token_data.get("constraints")),
                    token_data.get("root_principal"),
                    token_data.get("caller_class"),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self._conn.commit()

    def _sync_load_token(self, token_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM delegation_tokens WHERE token_id = ?",
                (token_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "token_id": row["token_id"],
                "issuer": row["issuer"],
                "subject": row["subject"],
                "scope": json.loads(row["scope"]),
                "purpose": json.loads(row["purpose"]) if row["purpose"] else None,
                "parent": row["parent"],
                "expires": row["expires"],
                "constraints": json.loads(row["constraints"]) if row["constraints"] else None,
                "root_principal": row["root_principal"],
                "caller_class": row["caller_class"],
            }

    def _sync_store_audit_entry(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO audit_log
                   (sequence_number, timestamp, capability, token_id, issuer,
                    subject, root_principal, parameters, success, result_summary,
                    failure_type, cost_actual, delegation_chain, invocation_id,
                    client_reference_id, stream_summary, previous_hash, signature,
                    event_class, retention_tier, expires_at,
                    storage_redacted, entry_type, grouping_key,
                    aggregation_window, aggregation_count, first_seen,
                    last_seen, representative_detail)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry["sequence_number"],
                    entry["timestamp"],
                    entry["capability"],
                    entry.get("token_id"),
                    entry.get("issuer"),
                    entry.get("subject"),
                    entry.get("root_principal"),
                    json.dumps(entry["parameters"]) if entry.get("parameters") is not None else None,
                    1 if entry["success"] else 0,
                    json.dumps(entry["result_summary"]) if entry.get("result_summary") is not None else None,
                    entry.get("failure_type"),
                    json.dumps(entry["cost_actual"]) if entry.get("cost_actual") is not None else None,
                    json.dumps(entry["delegation_chain"]) if entry.get("delegation_chain") is not None else None,
                    entry.get("invocation_id"),
                    entry.get("client_reference_id"),
                    json.dumps(entry["stream_summary"]) if entry.get("stream_summary") is not None else None,
                    entry["previous_hash"],
                    entry.get("signature"),
                    entry.get("event_class"),
                    entry.get("retention_tier"),
                    entry.get("expires_at"),
                    1 if entry.get("storage_redacted") else 0,
                    entry.get("entry_type"),
                    json.dumps(entry["grouping_key"]) if entry.get("grouping_key") is not None else None,
                    json.dumps(entry["aggregation_window"]) if entry.get("aggregation_window") is not None else None,
                    entry.get("aggregation_count"),
                    entry.get("first_seen"),
                    entry.get("last_seen"),
                    entry.get("representative_detail"),
                ),
            )
            self._conn.commit()

    def _parse_audit_row(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a raw audit_log row into a dict with parsed JSON fields."""
        entry: dict[str, Any] = dict(row)
        for field in _JSON_AUDIT_FIELDS:
            if entry.get(field) is not None:
                entry[field] = json.loads(entry[field])
        entry["success"] = bool(entry["success"])
        entry["storage_redacted"] = bool(entry.get("storage_redacted"))
        return entry

    def _sync_query_audit_entries(
        self,
        *,
        capability: str | None = None,
        root_principal: str | None = None,
        since: str | None = None,
        invocation_id: str | None = None,
        client_reference_id: str | None = None,
        event_class: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []

        if capability is not None:
            conditions.append("capability = ?")
            params.append(capability)
        if root_principal is not None:
            conditions.append("root_principal = ?")
            params.append(root_principal)
        if since is not None:
            conditions.append("timestamp >= ?")
            params.append(since)
        if invocation_id is not None:
            conditions.append("invocation_id = ?")
            params.append(invocation_id)
        if client_reference_id is not None:
            conditions.append("client_reference_id = ?")
            params.append(client_reference_id)
        if event_class is not None:
            conditions.append("event_class = ?")
            params.append(event_class)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM audit_log {where} ORDER BY sequence_number DESC LIMIT ?",
                [*params, limit],
            ).fetchall()

        return [self._parse_audit_row(r) for r in rows]

    def _sync_get_last_audit_entry(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM audit_log ORDER BY sequence_number DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            return self._parse_audit_row(row)

    def _sync_get_audit_entries_range(
        self, first: int, last: int
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM audit_log WHERE sequence_number BETWEEN ? AND ? "
                "ORDER BY sequence_number ASC",
                (first, last),
            ).fetchall()
        return [self._parse_audit_row(r) for r in rows]

    def _sync_get_earliest_expiry_in_range(self, first_seq: int, last_seq: int) -> str | None:
        """Return the earliest expires_at value for entries in [first_seq, last_seq]."""
        with self._lock:
            row = self._conn.execute(
                "SELECT MIN(expires_at) as min_exp FROM audit_log "
                "WHERE sequence_number BETWEEN ? AND ? AND expires_at IS NOT NULL",
                (first_seq, last_seq),
            ).fetchone()
            if row is None:
                return None
            return row["min_exp"] if row["min_exp"] is not None else None

    def _sync_delete_expired_audit_entries(self, now_iso: str) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM audit_log WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now_iso,),
            )
            self._conn.commit()
            return cursor.rowcount

    def _sync_store_checkpoint(self, body: dict[str, Any], signature: str) -> None:
        range_dict = body.get("range", {})
        with self._lock:
            self._conn.execute(
                """INSERT INTO checkpoints
                   (checkpoint_id, first_sequence, last_sequence, merkle_root,
                    previous_checkpoint, timestamp, entry_count, signature)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    body["checkpoint_id"],
                    range_dict.get("first_sequence", body.get("first_sequence")),
                    range_dict.get("last_sequence", body.get("last_sequence")),
                    body["merkle_root"],
                    body.get("previous_checkpoint"),
                    body.get("timestamp"),
                    body.get("entry_count"),
                    signature,
                ),
            )
            self._conn.commit()

    def _sync_get_checkpoints(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM checkpoints ORDER BY id ASC LIMIT ?", (limit,)
            ).fetchall()
        results = []
        for row in rows:
            results.append({
                "checkpoint_id": row["checkpoint_id"],
                "range": {
                    "first_sequence": row["first_sequence"],
                    "last_sequence": row["last_sequence"],
                },
                "merkle_root": row["merkle_root"],
                "previous_checkpoint": row["previous_checkpoint"],
                "timestamp": row["timestamp"],
                "entry_count": row["entry_count"],
                "signature": row["signature"],
            })
        return results

    def _sync_get_checkpoint_by_id(
        self, checkpoint_id: str
    ) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "checkpoint_id": row["checkpoint_id"],
                "range": {
                    "first_sequence": row["first_sequence"],
                    "last_sequence": row["last_sequence"],
                },
                "merkle_root": row["merkle_root"],
                "previous_checkpoint": row["previous_checkpoint"],
                "timestamp": row["timestamp"],
                "entry_count": row["entry_count"],
                "signature": row["signature"],
            }

    # -- async public interface ---------------------------------------------

    async def store_token(self, token_data: dict[str, Any]) -> None:
        """Store a delegation token."""
        await asyncio.to_thread(self._sync_store_token, token_data)

    async def load_token(self, token_id: str) -> dict[str, Any] | None:
        """Load a delegation token by ID."""
        return await asyncio.to_thread(self._sync_load_token, token_id)

    async def store_audit_entry(self, entry: dict[str, Any]) -> None:
        """Store an already-complete audit entry.

        The caller is responsible for computing hashes, signatures, and
        sequence numbers before calling this method.
        """
        await asyncio.to_thread(self._sync_store_audit_entry, entry)

    async def query_audit_entries(
        self,
        *,
        capability: str | None = None,
        root_principal: str | None = None,
        since: str | None = None,
        invocation_id: str | None = None,
        client_reference_id: str | None = None,
        event_class: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query audit entries with optional filters."""
        return await asyncio.to_thread(
            self._sync_query_audit_entries,
            capability=capability,
            root_principal=root_principal,
            since=since,
            invocation_id=invocation_id,
            client_reference_id=client_reference_id,
            event_class=event_class,
            limit=limit,
        )

    async def get_last_audit_entry(self) -> dict[str, Any] | None:
        """Return the audit entry with the highest sequence_number."""
        return await asyncio.to_thread(self._sync_get_last_audit_entry)

    async def get_audit_entries_range(
        self, first: int, last: int
    ) -> list[dict[str, Any]]:
        """Return audit entries with sequence_number BETWEEN first AND last."""
        return await asyncio.to_thread(self._sync_get_audit_entries_range, first, last)

    async def get_earliest_expiry_in_range(self, first_seq: int, last_seq: int) -> str | None:
        """Return the earliest expires_at value for entries in [first_seq, last_seq]."""
        return await asyncio.to_thread(self._sync_get_earliest_expiry_in_range, first_seq, last_seq)

    async def delete_expired_audit_entries(self, now_iso: str) -> int:
        """Delete audit entries whose expires_at is before now_iso."""
        return await asyncio.to_thread(self._sync_delete_expired_audit_entries, now_iso)

    async def store_checkpoint(self, body: dict[str, Any], signature: str) -> None:
        """Insert a checkpoint record."""
        await asyncio.to_thread(self._sync_store_checkpoint, body, signature)

    async def get_checkpoints(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return checkpoints ordered by id ascending."""
        return await asyncio.to_thread(self._sync_get_checkpoints, limit)

    async def get_checkpoint_by_id(
        self, checkpoint_id: str
    ) -> dict[str, Any] | None:
        """Return a single checkpoint by its checkpoint_id."""
        return await asyncio.to_thread(self._sync_get_checkpoint_by_id, checkpoint_id)

    # -- horizontal-scaling: audit append / signature / sequence -------------

    async def append_audit_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
        """Atomically append an audit entry, assigning sequence_number and previous_hash."""
        return await asyncio.to_thread(self._sync_append_audit_entry, entry_data)

    def _sync_append_audit_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            # Inline last-entry lookup to avoid re-acquiring the lock
            row = self._conn.execute(
                "SELECT * FROM audit_log ORDER BY sequence_number DESC LIMIT 1"
            ).fetchone()
            if row is None:
                seq = 1
                prev_hash = "sha256:0"
            else:
                last = self._parse_audit_row(row)
                seq = last["sequence_number"] + 1
                prev_hash = compute_entry_hash(last)
            entry = {**entry_data, "sequence_number": seq, "previous_hash": prev_hash}
            # Inline store to avoid re-acquiring the lock
            self._conn.execute(
                """INSERT INTO audit_log
                   (sequence_number, timestamp, capability, token_id, issuer,
                    subject, root_principal, parameters, success, result_summary,
                    failure_type, cost_actual, delegation_chain, invocation_id,
                    client_reference_id, stream_summary, previous_hash, signature,
                    event_class, retention_tier, expires_at,
                    storage_redacted, entry_type, grouping_key,
                    aggregation_window, aggregation_count, first_seen,
                    last_seen, representative_detail)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry["sequence_number"],
                    entry.get("timestamp"),
                    entry.get("capability"),
                    entry.get("token_id"),
                    entry.get("issuer"),
                    entry.get("subject"),
                    entry.get("root_principal"),
                    json.dumps(entry["parameters"]) if entry.get("parameters") is not None else None,
                    1 if entry.get("success") else 0,
                    json.dumps(entry["result_summary"]) if entry.get("result_summary") is not None else None,
                    entry.get("failure_type"),
                    json.dumps(entry["cost_actual"]) if entry.get("cost_actual") is not None else None,
                    json.dumps(entry["delegation_chain"]) if entry.get("delegation_chain") is not None else None,
                    entry.get("invocation_id"),
                    entry.get("client_reference_id"),
                    json.dumps(entry["stream_summary"]) if entry.get("stream_summary") is not None else None,
                    entry["previous_hash"],
                    entry.get("signature"),
                    entry.get("event_class"),
                    entry.get("retention_tier"),
                    entry.get("expires_at"),
                    1 if entry.get("storage_redacted") else 0,
                    entry.get("entry_type"),
                    json.dumps(entry["grouping_key"]) if entry.get("grouping_key") is not None else None,
                    json.dumps(entry["aggregation_window"]) if entry.get("aggregation_window") is not None else None,
                    entry.get("aggregation_count"),
                    entry.get("first_seen"),
                    entry.get("last_seen"),
                    entry.get("representative_detail"),
                ),
            )
            self._conn.commit()
            return entry

    async def update_audit_signature(self, sequence_number: int, signature: str) -> None:
        """Set the signature on an already-appended audit entry."""
        await asyncio.to_thread(self._sync_update_audit_signature, sequence_number, signature)

    def _sync_update_audit_signature(self, sequence_number: int, signature: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE audit_log SET signature = ? WHERE sequence_number = ?",
                (signature, sequence_number),
            )
            self._conn.commit()

    async def get_max_audit_sequence(self) -> int | None:
        """Return the highest sequence_number in the audit log, or None if empty."""
        return await asyncio.to_thread(self._sync_get_max_audit_sequence)

    def _sync_get_max_audit_sequence(self) -> int | None:
        with self._lock:
            row = self._conn.execute("SELECT MAX(sequence_number) FROM audit_log").fetchone()
            return row[0] if row and row[0] is not None else None

    # -- horizontal-scaling: exclusive leases --------------------------------

    async def try_acquire_exclusive(self, key: str, holder: str, ttl_seconds: int) -> bool:
        """Attempt to acquire an exclusive lease. Returns True if acquired."""
        now = datetime.now(timezone.utc)
        existing = self._exclusive_leases.get(key)
        if existing is None or existing[1] < now or existing[0] == holder:
            self._exclusive_leases[key] = (holder, now + timedelta(seconds=ttl_seconds))
            return True
        return False

    async def release_exclusive(self, key: str, holder: str) -> None:
        """Release an exclusive lease if held by the given holder."""
        existing = self._exclusive_leases.get(key)
        if existing is not None and existing[0] == holder:
            del self._exclusive_leases[key]

    async def try_acquire_leader(self, role: str, holder: str, ttl_seconds: int) -> bool:
        """Attempt to acquire a leader lease for a background role."""
        return await self.try_acquire_exclusive(f"leader:{role}", holder, ttl_seconds)

    async def release_leader(self, role: str, holder: str) -> None:
        """Release a leader lease if held by the given holder."""
        await self.release_exclusive(f"leader:{role}", holder)
