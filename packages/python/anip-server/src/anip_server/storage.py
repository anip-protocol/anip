"""Storage abstraction and implementations for ANIP server.

Provides a ``StorageBackend`` protocol, an in-memory implementation for
testing, and a concrete ``SQLiteStorage`` class that persists delegation
tokens, audit log entries, and checkpoints.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


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
        limit: int = 50,
    ) -> list[dict[str, Any]]: ...

    async def get_last_audit_entry(self) -> dict[str, Any] | None: ...

    async def get_audit_entries_range(
        self, first: int, last: int
    ) -> list[dict[str, Any]]: ...

    async def store_checkpoint(self, body: dict[str, Any], signature: str) -> None: ...

    async def get_checkpoints(self, limit: int = 10) -> list[dict[str, Any]]: ...

    async def get_checkpoint_by_id(
        self, checkpoint_id: str
    ) -> dict[str, Any] | None: ...


# ---------------------------------------------------------------------------
# In-memory implementation (for testing)
# ---------------------------------------------------------------------------


class InMemoryStorage:
    """In-memory implementation of :class:`StorageBackend` for testing."""

    def __init__(self) -> None:
        self._tokens: dict[str, dict[str, Any]] = {}
        self._audit_entries: list[dict[str, Any]] = []
        self._checkpoints: list[dict[str, Any]] = []

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

        # Sort by sequence_number descending
        results.sort(key=lambda e: e.get("sequence_number", 0), reverse=True)
        return [dict(e) for e in results[:limit]]

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
    previous_hash TEXT NOT NULL,
    signature TEXT
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
)


class SQLiteStorage:
    """SQLite-backed implementation of :class:`StorageBackend`.

    Synchronous sqlite3 calls are isolated in private ``_sync_*`` methods.
    The public async methods delegate to them via ``asyncio.to_thread`` so
    that database I/O never blocks the event loop.
    """

    def __init__(self, db_path: str = "anip.db") -> None:
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

    # -- sync internals (private) -------------------------------------------

    def _sync_store_token(self, token_data: dict[str, Any]) -> None:
        self._conn.execute(
            """INSERT INTO delegation_tokens
               (token_id, issuer, subject, scope, purpose, parent,
                expires, constraints, root_principal, registered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def _sync_load_token(self, token_id: str) -> dict[str, Any] | None:
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
        }

    def _sync_store_audit_entry(self, entry: dict[str, Any]) -> None:
        self._conn.execute(
            """INSERT INTO audit_log
               (sequence_number, timestamp, capability, token_id, issuer,
                subject, root_principal, parameters, success, result_summary,
                failure_type, cost_actual, delegation_chain, invocation_id,
                client_reference_id, previous_hash, signature)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                entry["previous_hash"],
                entry.get("signature"),
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
        return entry

    def _sync_query_audit_entries(
        self,
        *,
        capability: str | None = None,
        root_principal: str | None = None,
        since: str | None = None,
        invocation_id: str | None = None,
        client_reference_id: str | None = None,
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

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._conn.execute(
            f"SELECT * FROM audit_log {where} ORDER BY sequence_number DESC LIMIT ?",
            [*params, limit],
        ).fetchall()

        return [self._parse_audit_row(r) for r in rows]

    def _sync_get_last_audit_entry(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM audit_log ORDER BY sequence_number DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return self._parse_audit_row(row)

    def _sync_get_audit_entries_range(
        self, first: int, last: int
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM audit_log WHERE sequence_number BETWEEN ? AND ? "
            "ORDER BY sequence_number ASC",
            (first, last),
        ).fetchall()
        return [self._parse_audit_row(r) for r in rows]

    def _sync_store_checkpoint(self, body: dict[str, Any], signature: str) -> None:
        range_dict = body.get("range", {})
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
