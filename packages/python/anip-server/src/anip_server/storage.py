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
        task_id: str | None = None,
        parent_invocation_id: str | None = None,
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

    # --- v0.23: approval requests + grants ---------------------------------

    async def store_approval_request(self, request: dict[str, Any]) -> None:
        """Persist a freshly created ApprovalRequest with status='pending'.

        Idempotent on approval_request_id when content is identical;
        conflicting re-store with the same id is an error. v0.23. See SPEC.md §4.7.
        """
        ...

    async def get_approval_request(self, approval_request_id: str) -> dict[str, Any] | None:
        """Read-only fetch of an ApprovalRequest. Returns the row regardless
        of status so callers can distinguish pending/approved/denied/expired.
        MUST NOT mutate state. v0.23.
        """
        ...

    async def approve_request_and_store_grant(
        self,
        approval_request_id: str,
        grant: dict[str, Any],
        approver: dict[str, Any],
        decided_at_iso: str,
        now_iso: str,
    ) -> dict[str, Any]:
        """Atomic state transition: approval_request pending → approved AND
        insert grant. The conditional check is `status='pending' AND
        expires_at > now`.

        Returns a dict with one of:
        - {"ok": True, "grant": <inserted grant dict>}
        - {"ok": False, "reason": "approval_request_not_found"}
        - {"ok": False, "reason": "approval_request_already_decided"}
        - {"ok": False, "reason": "approval_request_expired"}

        Implementations MUST guarantee atomicity per Decision 0.9a.
        v0.23. See SPEC.md §4.9.
        """
        ...

    async def store_grant(self, grant: dict[str, Any]) -> None:
        """Internal/test-only. The issuance helper MUST use
        approve_request_and_store_grant. Exposed only for storage tests
        that don't exercise the approval-request flow. v0.23.
        """
        ...

    async def get_grant(self, grant_id: str) -> dict[str, Any] | None:
        """Read-only fetch. MUST NOT mutate use_count. v0.23. See SPEC.md §4.8."""
        ...

    async def try_reserve_grant(
        self, grant_id: str, now_iso: str
    ) -> dict[str, Any]:
        """Atomic check-and-increment: increment use_count by 1 only if the
        grant exists, has not expired, and use_count < max_uses.

        Returns a dict with one of:
        - {"ok": True, "grant": <updated grant dict>}
        - {"ok": False, "reason": "grant_not_found"}
        - {"ok": False, "reason": "grant_expired"}
        - {"ok": False, "reason": "grant_consumed"}

        v0.23. See SPEC.md §4.8 Phase B.
        """
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
        # v0.23
        self._approval_requests: dict[str, dict[str, Any]] = {}
        self._grants: dict[str, dict[str, Any]] = {}
        # Single mutex covering BOTH approval_requests and grants because
        # approve_request_and_store_grant must mutate them atomically.
        self._approval_lock = threading.Lock()

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
        task_id: str | None = None,
        parent_invocation_id: str | None = None,
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
        if task_id is not None:
            results = [e for e in results if e.get("task_id") == task_id]
        if parent_invocation_id is not None:
            results = [
                e for e in results
                if e.get("parent_invocation_id") == parent_invocation_id
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
        """Return the most recent checkpoints in chronological order."""
        if limit <= 0:
            return []
        return [dict(ckpt) for ckpt in self._checkpoints[-limit:]]

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

    # --- v0.23: approval requests + grants ---------------------------------

    async def store_approval_request(self, request: dict[str, Any]) -> None:
        with self._approval_lock:
            req_id = request["approval_request_id"]
            existing = self._approval_requests.get(req_id)
            if existing is not None and existing != request:
                raise ValueError(
                    f"approval_request_id {req_id!r} already stored with different content"
                )
            self._approval_requests[req_id] = dict(request)

    async def get_approval_request(self, approval_request_id: str) -> dict[str, Any] | None:
        with self._approval_lock:
            row = self._approval_requests.get(approval_request_id)
            return dict(row) if row is not None else None

    async def approve_request_and_store_grant(
        self,
        approval_request_id: str,
        grant: dict[str, Any],
        approver: dict[str, Any],
        decided_at_iso: str,
        now_iso: str,
    ) -> dict[str, Any]:
        with self._approval_lock:
            req = self._approval_requests.get(approval_request_id)
            if req is None:
                return {"ok": False, "reason": "approval_request_not_found"}
            if req.get("status") != "pending":
                return {"ok": False, "reason": "approval_request_already_decided"}
            if req.get("expires_at", "") <= now_iso:
                return {"ok": False, "reason": "approval_request_expired"}
            # Defense-in-depth: enforce UNIQUE on grants.approval_request_id.
            for existing_grant in self._grants.values():
                if existing_grant.get("approval_request_id") == approval_request_id:
                    return {"ok": False, "reason": "approval_request_already_decided"}
            req["status"] = "approved"
            req["approver"] = dict(approver)
            req["decided_at"] = decided_at_iso
            self._grants[grant["grant_id"]] = dict(grant)
            return {"ok": True, "grant": dict(grant)}

    async def store_grant(self, grant: dict[str, Any]) -> None:
        with self._approval_lock:
            self._grants[grant["grant_id"]] = dict(grant)

    async def get_grant(self, grant_id: str) -> dict[str, Any] | None:
        with self._approval_lock:
            row = self._grants.get(grant_id)
            return dict(row) if row is not None else None

    async def try_reserve_grant(
        self, grant_id: str, now_iso: str
    ) -> dict[str, Any]:
        with self._approval_lock:
            grant = self._grants.get(grant_id)
            if grant is None:
                return {"ok": False, "reason": "grant_not_found"}
            if grant.get("expires_at", "") <= now_iso:
                return {"ok": False, "reason": "grant_expired"}
            if grant.get("use_count", 0) >= grant.get("max_uses", 1):
                return {"ok": False, "reason": "grant_consumed"}
            grant["use_count"] = grant.get("use_count", 0) + 1
            return {"ok": True, "grant": dict(grant)}


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
    task_id TEXT,
    parent_invocation_id TEXT,
    upstream_service TEXT,
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
    representative_detail TEXT,
    -- v0.23: approval flow linkage. See SPEC.md §4.7–§4.9.
    approval_request_id TEXT,
    approval_grant_id TEXT
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
CREATE INDEX IF NOT EXISTS idx_audit_task_id
    ON audit_log(task_id);
CREATE INDEX IF NOT EXISTS idx_audit_parent_invocation_id
    ON audit_log(parent_invocation_id);
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

-- v0.23: approval requests
CREATE TABLE IF NOT EXISTS approval_requests (
    approval_request_id TEXT PRIMARY KEY,
    capability TEXT NOT NULL,
    scope TEXT NOT NULL,                        -- JSON array
    requester TEXT NOT NULL,                    -- JSON
    parent_invocation_id TEXT,
    preview TEXT NOT NULL,                      -- JSON
    preview_digest TEXT NOT NULL,
    requested_parameters TEXT NOT NULL,         -- JSON
    requested_parameters_digest TEXT NOT NULL,
    grant_policy TEXT NOT NULL,                 -- JSON
    status TEXT NOT NULL CHECK (status IN ('pending','approved','denied','expired')),
    approver TEXT,                              -- JSON, null until decided
    decided_at TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_approval_requests_expires ON approval_requests(expires_at);

-- v0.23: approval grants
CREATE TABLE IF NOT EXISTS approval_grants (
    grant_id TEXT PRIMARY KEY,
    approval_request_id TEXT NOT NULL UNIQUE,   -- defense-in-depth: at most one grant per request
    grant_type TEXT NOT NULL CHECK (grant_type IN ('one_time','session_bound')),
    capability TEXT NOT NULL,
    scope TEXT NOT NULL,                        -- JSON array
    approved_parameters_digest TEXT NOT NULL,
    preview_digest TEXT NOT NULL,
    requester TEXT NOT NULL,                    -- JSON
    approver TEXT NOT NULL,                     -- JSON
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    max_uses INTEGER NOT NULL CHECK (max_uses >= 1),
    use_count INTEGER NOT NULL DEFAULT 0,
    session_id TEXT,
    signature TEXT NOT NULL,
    FOREIGN KEY (approval_request_id) REFERENCES approval_requests(approval_request_id)
);
CREATE INDEX IF NOT EXISTS idx_grants_approval_request_id ON approval_grants(approval_request_id);
CREATE INDEX IF NOT EXISTS idx_grants_expires ON approval_grants(expires_at);
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
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN task_id TEXT")
        except Exception:
            pass  # column already exists
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN parent_invocation_id TEXT")
        except Exception:
            pass  # column already exists
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN upstream_service TEXT")
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
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN approval_request_id TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE audit_log ADD COLUMN approval_grant_id TEXT")
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
                    client_reference_id, task_id, parent_invocation_id, upstream_service,
                    stream_summary, previous_hash, signature,
                    event_class, retention_tier, expires_at,
                    storage_redacted, entry_type, grouping_key,
                    aggregation_window, aggregation_count, first_seen,
                    last_seen, representative_detail,
                    approval_request_id, approval_grant_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    entry.get("task_id"),
                    entry.get("parent_invocation_id"),
                    entry.get("upstream_service"),
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
                    entry.get("approval_request_id"),  # v0.23
                    entry.get("approval_grant_id"),  # v0.23
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
        task_id: str | None = None,
        parent_invocation_id: str | None = None,
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
        if task_id is not None:
            conditions.append("task_id = ?")
            params.append(task_id)
        if parent_invocation_id is not None:
            conditions.append("parent_invocation_id = ?")
            params.append(parent_invocation_id)
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
        if limit <= 0:
            return []
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM checkpoints ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        rows = list(reversed(rows))
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
        task_id: str | None = None,
        parent_invocation_id: str | None = None,
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
            task_id=task_id,
            parent_invocation_id=parent_invocation_id,
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
        """Return the most recent checkpoints in chronological order."""
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
                    client_reference_id, task_id, parent_invocation_id, upstream_service,
                    stream_summary, previous_hash, signature,
                    event_class, retention_tier, expires_at,
                    storage_redacted, entry_type, grouping_key,
                    aggregation_window, aggregation_count, first_seen,
                    last_seen, representative_detail,
                    approval_request_id, approval_grant_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    entry.get("task_id"),
                    entry.get("parent_invocation_id"),
                    entry.get("upstream_service"),
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
                    entry.get("approval_request_id"),  # v0.23
                    entry.get("approval_grant_id"),  # v0.23
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

    # --- v0.23: approval requests + grants ---------------------------------

    async def store_approval_request(self, request: dict[str, Any]) -> None:
        await asyncio.to_thread(self._sync_store_approval_request, request)

    def _sync_store_approval_request(self, request: dict[str, Any]) -> None:
        # SPEC.md §4.7 + StorageBackend.store_approval_request: idempotent on
        # approval_request_id when content is identical; conflicting re-store
        # with the same id is an error. Mirrors InMemoryStorage semantics.
        req_id = request["approval_request_id"]
        with self._lock:
            existing_row = self._conn.execute(
                "SELECT * FROM approval_requests WHERE approval_request_id = ?",
                (req_id,),
            ).fetchone()
            if existing_row is not None:
                existing = self._parse_approval_request_row(existing_row)
                if existing != request:
                    raise ValueError(
                        f"approval_request_id {req_id!r} already stored with different content"
                    )
                return  # idempotent: identical content, no write needed
            self._conn.execute(
                """INSERT INTO approval_requests
                   (approval_request_id, capability, scope, requester, parent_invocation_id,
                    preview, preview_digest, requested_parameters, requested_parameters_digest,
                    grant_policy, status, approver, decided_at, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    req_id,
                    request["capability"],
                    json.dumps(request["scope"]),
                    json.dumps(request["requester"]),
                    request.get("parent_invocation_id"),
                    json.dumps(request["preview"]),
                    request["preview_digest"],
                    json.dumps(request["requested_parameters"]),
                    request["requested_parameters_digest"],
                    json.dumps(request["grant_policy"]),
                    request["status"],
                    json.dumps(request["approver"]) if request.get("approver") is not None else None,
                    request.get("decided_at"),
                    request["created_at"],
                    request["expires_at"],
                ),
            )
            self._conn.commit()

    async def get_approval_request(self, approval_request_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._sync_get_approval_request, approval_request_id)

    def _sync_get_approval_request(self, approval_request_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM approval_requests WHERE approval_request_id = ?",
                (approval_request_id,),
            ).fetchone()
            return self._parse_approval_request_row(row) if row else None

    @staticmethod
    def _parse_approval_request_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for f in ("scope", "requester", "preview", "requested_parameters", "grant_policy"):
            if d.get(f):
                d[f] = json.loads(d[f])
        if d.get("approver"):
            d["approver"] = json.loads(d["approver"])
        return d

    async def approve_request_and_store_grant(
        self,
        approval_request_id: str,
        grant: dict[str, Any],
        approver: dict[str, Any],
        decided_at_iso: str,
        now_iso: str,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._sync_approve_and_store, approval_request_id, grant, approver, decided_at_iso, now_iso
        )

    def _sync_approve_and_store(
        self,
        approval_request_id: str,
        grant: dict[str, Any],
        approver: dict[str, Any],
        decided_at_iso: str,
        now_iso: str,
    ) -> dict[str, Any]:
        # Atomic per Decision 0.9a: BEGIN, conditional UPDATE with status='pending'
        # AND expires_at > now() guard, INSERT into grants. ROLLBACK on any failure.
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                cursor = self._conn.execute(
                    """UPDATE approval_requests
                       SET status = 'approved', approver = ?, decided_at = ?
                       WHERE approval_request_id = ?
                         AND status = 'pending'
                         AND expires_at > ?""",
                    (json.dumps(approver), decided_at_iso, approval_request_id, now_iso),
                )
                if cursor.rowcount == 0:
                    self._conn.execute("ROLLBACK")
                    row = self._conn.execute(
                        "SELECT status, expires_at FROM approval_requests WHERE approval_request_id = ?",
                        (approval_request_id,),
                    ).fetchone()
                    if row is None:
                        return {"ok": False, "reason": "approval_request_not_found"}
                    if row[1] <= now_iso:
                        return {"ok": False, "reason": "approval_request_expired"}
                    return {"ok": False, "reason": "approval_request_already_decided"}
                try:
                    self._conn.execute(
                        """INSERT INTO approval_grants
                           (grant_id, approval_request_id, grant_type, capability, scope,
                            approved_parameters_digest, preview_digest, requester, approver,
                            issued_at, expires_at, max_uses, use_count, session_id, signature)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            grant["grant_id"],
                            grant["approval_request_id"],
                            grant["grant_type"],
                            grant["capability"],
                            json.dumps(grant["scope"]),
                            grant["approved_parameters_digest"],
                            grant["preview_digest"],
                            json.dumps(grant["requester"]),
                            json.dumps(grant["approver"]),
                            grant["issued_at"],
                            grant["expires_at"],
                            grant["max_uses"],
                            grant.get("use_count", 0),
                            grant.get("session_id"),
                            grant["signature"],
                        ),
                    )
                except sqlite3.IntegrityError:
                    self._conn.execute("ROLLBACK")
                    return {"ok": False, "reason": "approval_request_already_decided"}
                self._conn.commit()
                return {"ok": True, "grant": dict(grant)}
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise

    async def store_grant(self, grant: dict[str, Any]) -> None:
        await asyncio.to_thread(self._sync_store_grant, grant)

    def _sync_store_grant(self, grant: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO approval_grants
                   (grant_id, approval_request_id, grant_type, capability, scope,
                    approved_parameters_digest, preview_digest, requester, approver,
                    issued_at, expires_at, max_uses, use_count, session_id, signature)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    grant["grant_id"],
                    grant["approval_request_id"],
                    grant["grant_type"],
                    grant["capability"],
                    json.dumps(grant["scope"]),
                    grant["approved_parameters_digest"],
                    grant["preview_digest"],
                    json.dumps(grant["requester"]),
                    json.dumps(grant["approver"]),
                    grant["issued_at"],
                    grant["expires_at"],
                    grant["max_uses"],
                    grant.get("use_count", 0),
                    grant.get("session_id"),
                    grant["signature"],
                ),
            )
            self._conn.commit()

    async def get_grant(self, grant_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._sync_get_grant, grant_id)

    def _sync_get_grant(self, grant_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM approval_grants WHERE grant_id = ?", (grant_id,)
            ).fetchone()
            return self._parse_grant_row(row) if row else None

    @staticmethod
    def _parse_grant_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for f in ("scope", "requester", "approver"):
            if d.get(f):
                d[f] = json.loads(d[f])
        return d

    async def try_reserve_grant(
        self, grant_id: str, now_iso: str
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync_try_reserve_grant, grant_id, now_iso)

    def _sync_try_reserve_grant(self, grant_id: str, now_iso: str) -> dict[str, Any]:
        # Atomic check-and-increment per Phase 7.3 Phase B.
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                cursor = self._conn.execute(
                    """UPDATE approval_grants
                       SET use_count = use_count + 1
                       WHERE grant_id = ?
                         AND use_count < max_uses
                         AND expires_at > ?""",
                    (grant_id, now_iso),
                )
                if cursor.rowcount == 0:
                    self._conn.execute("ROLLBACK")
                    row = self._conn.execute(
                        "SELECT use_count, max_uses, expires_at FROM approval_grants WHERE grant_id = ?",
                        (grant_id,),
                    ).fetchone()
                    if row is None:
                        return {"ok": False, "reason": "grant_not_found"}
                    if row[2] <= now_iso:
                        return {"ok": False, "reason": "grant_expired"}
                    if row[0] >= row[1]:
                        return {"ok": False, "reason": "grant_consumed"}
                    return {"ok": False, "reason": "grant_not_found"}
                self._conn.commit()
                row = self._conn.execute(
                    "SELECT * FROM approval_grants WHERE grant_id = ?", (grant_id,)
                ).fetchone()
                return {"ok": True, "grant": self._parse_grant_row(row) if row else None}
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
