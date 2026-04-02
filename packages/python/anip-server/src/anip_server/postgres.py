"""PostgreSQL storage backend for horizontally-scaled ANIP deployments.

Uses ``asyncpg`` for async connection pooling and leverages PostgreSQL
row-level locking to guarantee serialisable audit-log appends across
multiple server replicas.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg  # pyright: ignore[reportMissingImports]

from .hashing import compute_entry_hash

_JSON_AUDIT_FIELDS = (
    "parameters",
    "result_summary",
    "cost_actual",
    "delegation_chain",
    "stream_summary",
    "grouping_key",
    "aggregation_window",
)

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS delegation_tokens (
    token_id TEXT PRIMARY KEY,
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    scope TEXT NOT NULL,
    purpose TEXT,
    parent TEXT,
    expires TEXT NOT NULL,
    constraints TEXT,
    root_principal TEXT,
    caller_class TEXT,
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    sequence_number BIGINT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL,
    capability TEXT NOT NULL,
    token_id TEXT,
    issuer TEXT,
    subject TEXT,
    root_principal TEXT,
    parameters TEXT,
    success BOOLEAN NOT NULL,
    result_summary TEXT,
    failure_type TEXT,
    cost_actual TEXT,
    delegation_chain TEXT,
    invocation_id TEXT,
    client_reference_id TEXT,
    task_id TEXT,
    parent_invocation_id TEXT,
    upstream_service TEXT,
    stream_summary TEXT,
    previous_hash TEXT NOT NULL,
    signature TEXT,
    event_class TEXT,
    retention_tier TEXT,
    expires_at TEXT,
    storage_redacted BOOLEAN DEFAULT FALSE,
    entry_type TEXT,
    grouping_key TEXT,
    aggregation_window TEXT,
    aggregation_count INTEGER,
    first_seen TEXT,
    last_seen TEXT,
    representative_detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_capability ON audit_log(capability);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_root_principal ON audit_log(root_principal);
CREATE INDEX IF NOT EXISTS idx_audit_invocation_id ON audit_log(invocation_id);
CREATE INDEX IF NOT EXISTS idx_audit_client_reference_id ON audit_log(client_reference_id);
CREATE INDEX IF NOT EXISTS idx_audit_task_id ON audit_log(task_id);
CREATE INDEX IF NOT EXISTS idx_audit_parent_invocation_id ON audit_log(parent_invocation_id);
CREATE INDEX IF NOT EXISTS idx_audit_event_class ON audit_log(event_class);
CREATE INDEX IF NOT EXISTS idx_audit_expires_at ON audit_log(expires_at);

CREATE TABLE IF NOT EXISTS audit_append_head (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_sequence_number BIGINT NOT NULL DEFAULT 0,
    last_hash TEXT NOT NULL DEFAULT 'sha256:0'
);

INSERT INTO audit_append_head (id, last_sequence_number, last_hash)
VALUES (1, 0, 'sha256:0')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS checkpoints (
    id SERIAL PRIMARY KEY,
    checkpoint_id TEXT NOT NULL UNIQUE,
    first_sequence INTEGER,
    last_sequence INTEGER,
    merkle_root TEXT NOT NULL,
    previous_checkpoint TEXT,
    timestamp TEXT,
    entry_count INTEGER,
    signature TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exclusive_leases (
    key TEXT PRIMARY KEY,
    holder TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS leader_leases (
    role TEXT PRIMARY KEY,
    holder TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);
"""


def _parse_audit_row(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record from audit_log into a dict with parsed JSON fields."""
    entry: dict[str, Any] = dict(row)
    # Remove the auto-increment id from the returned dict
    entry.pop("id", None)
    for field in _JSON_AUDIT_FIELDS:
        if entry.get(field) is not None:
            entry[field] = json.loads(entry[field])
    entry["success"] = bool(entry["success"])
    entry["storage_redacted"] = bool(entry.get("storage_redacted"))
    return entry


def _json_or_none(value: Any) -> str | None:
    """Serialize a value to JSON if not None."""
    if value is None:
        return None
    return json.dumps(value)


class PostgresStorage:
    """PostgreSQL storage backend for horizontally-scaled ANIP deployments."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Create connection pool and ensure schema exists."""
        self._pool = await asyncpg.create_pool(self._dsn)
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await self._ensure_schema(conn)

    async def _ensure_schema(self, conn: asyncpg.Connection) -> None:
        """Execute schema DDL statements."""
        await conn.execute(_SCHEMA)

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("PostgresStorage not initialized; call initialize() first")
        return self._pool

    # -- tokens -------------------------------------------------------------

    async def store_token(self, token_data: dict[str, Any]) -> None:
        """Store a delegation token."""
        pool = self._get_pool()
        await pool.execute(
            """INSERT INTO delegation_tokens
               (token_id, issuer, subject, scope, purpose, parent,
                expires, constraints, root_principal, caller_class, registered_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
               ON CONFLICT (token_id) DO UPDATE SET
                   issuer = EXCLUDED.issuer,
                   subject = EXCLUDED.subject,
                   scope = EXCLUDED.scope,
                   purpose = EXCLUDED.purpose,
                   parent = EXCLUDED.parent,
                   expires = EXCLUDED.expires,
                   constraints = EXCLUDED.constraints,
                   root_principal = EXCLUDED.root_principal,
                   caller_class = EXCLUDED.caller_class,
                   registered_at = EXCLUDED.registered_at""",
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
        )

    async def load_token(self, token_id: str) -> dict[str, Any] | None:
        """Load a delegation token by ID."""
        pool = self._get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM delegation_tokens WHERE token_id = $1",
            token_id,
        )
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

    # -- audit log ----------------------------------------------------------

    async def store_audit_entry(self, entry: dict[str, Any]) -> None:
        """Store an already-complete audit entry."""
        pool = self._get_pool()
        await pool.execute(
            """INSERT INTO audit_log
               (sequence_number, timestamp, capability, token_id, issuer,
                subject, root_principal, parameters, success, result_summary,
                failure_type, cost_actual, delegation_chain, invocation_id,
                client_reference_id, task_id, parent_invocation_id, upstream_service,
                stream_summary, previous_hash, signature,
                event_class, retention_tier, expires_at,
                storage_redacted, entry_type, grouping_key,
                aggregation_window, aggregation_count, first_seen,
                last_seen, representative_detail)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                       $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                       $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32)""",
            entry["sequence_number"],
            entry["timestamp"],
            entry["capability"],
            entry.get("token_id"),
            entry.get("issuer"),
            entry.get("subject"),
            entry.get("root_principal"),
            _json_or_none(entry.get("parameters")),
            bool(entry["success"]),
            _json_or_none(entry.get("result_summary")),
            entry.get("failure_type"),
            _json_or_none(entry.get("cost_actual")),
            _json_or_none(entry.get("delegation_chain")),
            entry.get("invocation_id"),
            entry.get("client_reference_id"),
            entry.get("task_id"),
            entry.get("parent_invocation_id"),
            entry.get("upstream_service"),
            _json_or_none(entry.get("stream_summary")),
            entry["previous_hash"],
            entry.get("signature"),
            entry.get("event_class"),
            entry.get("retention_tier"),
            entry.get("expires_at"),
            bool(entry.get("storage_redacted")),
            entry.get("entry_type"),
            _json_or_none(entry.get("grouping_key")),
            _json_or_none(entry.get("aggregation_window")),
            entry.get("aggregation_count"),
            entry.get("first_seen"),
            entry.get("last_seen"),
            entry.get("representative_detail"),
        )

    async def query_audit_entries(
        self,
        *,
        capability: str | None = None,
        root_principal: str | None = None,
        since: str | None = None,
        invocation_id: str | None = None,
        client_reference_id: str | None = None,
        task_id: str | None = None,
        parent_invocation_id: str | None = None,
        event_class: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query audit entries with optional filters."""
        pool = self._get_pool()
        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if capability is not None:
            conditions.append(f"capability = ${idx}")
            params.append(capability)
            idx += 1
        if root_principal is not None:
            conditions.append(f"root_principal = ${idx}")
            params.append(root_principal)
            idx += 1
        if since is not None:
            conditions.append(f"timestamp >= ${idx}")
            params.append(since)
            idx += 1
        if invocation_id is not None:
            conditions.append(f"invocation_id = ${idx}")
            params.append(invocation_id)
            idx += 1
        if client_reference_id is not None:
            conditions.append(f"client_reference_id = ${idx}")
            params.append(client_reference_id)
            idx += 1
        if task_id is not None:
            conditions.append(f"task_id = ${idx}")
            params.append(task_id)
            idx += 1
        if parent_invocation_id is not None:
            conditions.append(f"parent_invocation_id = ${idx}")
            params.append(parent_invocation_id)
            idx += 1
        if event_class is not None:
            conditions.append(f"event_class = ${idx}")
            params.append(event_class)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        query = f"SELECT * FROM audit_log {where} ORDER BY sequence_number DESC LIMIT ${idx}"

        rows = await pool.fetch(query, *params)
        return [_parse_audit_row(r) for r in rows]

    async def get_last_audit_entry(self) -> dict[str, Any] | None:
        """Return the audit entry with the highest sequence_number."""
        pool = self._get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM audit_log ORDER BY sequence_number DESC LIMIT 1"
        )
        if row is None:
            return None
        return _parse_audit_row(row)

    async def get_audit_entries_range(
        self, first: int, last: int
    ) -> list[dict[str, Any]]:
        """Return audit entries with sequence_number BETWEEN first AND last."""
        pool = self._get_pool()
        rows = await pool.fetch(
            "SELECT * FROM audit_log WHERE sequence_number BETWEEN $1 AND $2 "
            "ORDER BY sequence_number ASC",
            first,
            last,
        )
        return [_parse_audit_row(r) for r in rows]

    async def get_earliest_expiry_in_range(
        self, first_seq: int, last_seq: int
    ) -> str | None:
        """Return the earliest expires_at value for entries in [first_seq, last_seq]."""
        pool = self._get_pool()
        row = await pool.fetchrow(
            "SELECT MIN(expires_at) AS min_exp FROM audit_log "
            "WHERE sequence_number BETWEEN $1 AND $2 AND expires_at IS NOT NULL",
            first_seq,
            last_seq,
        )
        if row is None:
            return None
        return row["min_exp"]

    async def delete_expired_audit_entries(self, now_iso: str) -> int:
        """Delete audit entries whose expires_at is before now_iso."""
        pool = self._get_pool()
        result = await pool.execute(
            "DELETE FROM audit_log WHERE expires_at IS NOT NULL AND expires_at < $1",
            now_iso,
        )
        # asyncpg returns e.g. "DELETE 3"
        return int(result.split()[-1])

    # -- horizontal-scaling: audit append / signature / sequence -------------

    async def append_audit_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
        """Atomically append an audit entry, assigning sequence_number and previous_hash.

        Uses a transactional append-head pattern with row-level locking to
        guarantee serialisable ordering across concurrent replicas.
        """
        pool = self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Lock the append-head row
                head = await conn.fetchrow(
                    "SELECT last_sequence_number, last_hash FROM audit_append_head "
                    "WHERE id = 1 FOR UPDATE"
                )
                seq = head["last_sequence_number"] + 1
                prev_hash = head["last_hash"]

                entry = {**entry_data, "sequence_number": seq, "previous_hash": prev_hash}

                # Compute the new hash for this entry
                new_hash = compute_entry_hash(entry)

                # Insert the audit entry
                await conn.execute(
                    """INSERT INTO audit_log
                       (sequence_number, timestamp, capability, token_id, issuer,
                        subject, root_principal, parameters, success, result_summary,
                        failure_type, cost_actual, delegation_chain, invocation_id,
                        client_reference_id, task_id, parent_invocation_id, upstream_service,
                        stream_summary, previous_hash, signature,
                        event_class, retention_tier, expires_at,
                        storage_redacted, entry_type, grouping_key,
                        aggregation_window, aggregation_count, first_seen,
                        last_seen, representative_detail)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                               $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                               $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32)""",
                    entry["sequence_number"],
                    entry.get("timestamp"),
                    entry.get("capability"),
                    entry.get("token_id"),
                    entry.get("issuer"),
                    entry.get("subject"),
                    entry.get("root_principal"),
                    _json_or_none(entry.get("parameters")),
                    bool(entry.get("success")),
                    _json_or_none(entry.get("result_summary")),
                    entry.get("failure_type"),
                    _json_or_none(entry.get("cost_actual")),
                    _json_or_none(entry.get("delegation_chain")),
                    entry.get("invocation_id"),
                    entry.get("client_reference_id"),
                    entry.get("task_id"),
                    entry.get("parent_invocation_id"),
                    entry.get("upstream_service"),
                    _json_or_none(entry.get("stream_summary")),
                    entry["previous_hash"],
                    entry.get("signature"),
                    entry.get("event_class"),
                    entry.get("retention_tier"),
                    entry.get("expires_at"),
                    bool(entry.get("storage_redacted")),
                    entry.get("entry_type"),
                    _json_or_none(entry.get("grouping_key")),
                    _json_or_none(entry.get("aggregation_window")),
                    entry.get("aggregation_count"),
                    entry.get("first_seen"),
                    entry.get("last_seen"),
                    entry.get("representative_detail"),
                )

                # Update the append-head
                await conn.execute(
                    "UPDATE audit_append_head SET last_sequence_number = $1, last_hash = $2 "
                    "WHERE id = 1",
                    seq,
                    new_hash,
                )

                return entry

    async def update_audit_signature(self, sequence_number: int, signature: str) -> None:
        """Set the signature on an already-appended audit entry."""
        pool = self._get_pool()
        await pool.execute(
            "UPDATE audit_log SET signature = $1 WHERE sequence_number = $2",
            signature,
            sequence_number,
        )

    async def get_max_audit_sequence(self) -> int | None:
        """Return the highest sequence_number in the audit log, or None if empty."""
        pool = self._get_pool()
        row = await pool.fetchrow("SELECT MAX(sequence_number) AS max_seq FROM audit_log")
        if row is None or row["max_seq"] is None:
            return None
        return row["max_seq"]

    # -- checkpoints --------------------------------------------------------

    async def store_checkpoint(self, body: dict[str, Any], signature: str) -> None:
        """Insert a checkpoint record."""
        pool = self._get_pool()
        range_dict = body.get("range", {})
        await pool.execute(
            """INSERT INTO checkpoints
               (checkpoint_id, first_sequence, last_sequence, merkle_root,
                previous_checkpoint, timestamp, entry_count, signature)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            body["checkpoint_id"],
            range_dict.get("first_sequence", body.get("first_sequence")),
            range_dict.get("last_sequence", body.get("last_sequence")),
            body["merkle_root"],
            body.get("previous_checkpoint"),
            body.get("timestamp"),
            body.get("entry_count"),
            signature,
        )

    async def get_checkpoints(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return checkpoints ordered by id ascending."""
        pool = self._get_pool()
        rows = await pool.fetch(
            "SELECT * FROM checkpoints ORDER BY id ASC LIMIT $1", limit
        )
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

    async def get_checkpoint_by_id(
        self, checkpoint_id: str
    ) -> dict[str, Any] | None:
        """Return a single checkpoint by its checkpoint_id."""
        pool = self._get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM checkpoints WHERE checkpoint_id = $1",
            checkpoint_id,
        )
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

    # -- horizontal-scaling: exclusive leases --------------------------------

    async def try_acquire_exclusive(self, key: str, holder: str, ttl_seconds: int) -> bool:
        """Attempt to acquire an exclusive lease. Returns True if acquired."""
        pool = self._get_pool()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        result = await pool.execute(
            """INSERT INTO exclusive_leases (key, holder, expires_at)
               VALUES ($1, $2, $3)
               ON CONFLICT (key) DO UPDATE
                   SET holder = EXCLUDED.holder, expires_at = EXCLUDED.expires_at
                   WHERE exclusive_leases.expires_at < $4
                      OR exclusive_leases.holder = $5""",
            key,
            holder,
            expires,
            now,
            holder,
        )
        # asyncpg returns e.g. "INSERT 0 1" on success, "INSERT 0 0" on conflict-no-update
        return result.endswith(" 1")

    async def release_exclusive(self, key: str, holder: str) -> None:
        """Release an exclusive lease if held by the given holder."""
        pool = self._get_pool()
        await pool.execute(
            "DELETE FROM exclusive_leases WHERE key = $1 AND holder = $2",
            key,
            holder,
        )

    async def try_acquire_leader(self, role: str, holder: str, ttl_seconds: int) -> bool:
        """Attempt to acquire a leader lease for a background role. Returns True if acquired."""
        pool = self._get_pool()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        result = await pool.execute(
            """INSERT INTO leader_leases (role, holder, expires_at)
               VALUES ($1, $2, $3)
               ON CONFLICT (role) DO UPDATE
                   SET holder = EXCLUDED.holder, expires_at = EXCLUDED.expires_at
                   WHERE leader_leases.expires_at < $4
                      OR leader_leases.holder = $5""",
            role,
            holder,
            expires,
            now,
            holder,
        )
        return result.endswith(" 1")

    async def release_leader(self, role: str, holder: str) -> None:
        """Release a leader lease if held by the given holder."""
        pool = self._get_pool()
        await pool.execute(
            "DELETE FROM leader_leases WHERE role = $1 AND holder = $2",
            role,
            holder,
        )
