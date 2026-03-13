"""SQLite persistence layer for the ANIP reference implementation.

Stores delegation tokens, bookings, session state, and audit logs.
In production, swap SQLite for Postgres — the schema stays the same.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from anip_server.primitives.checkpoint import CheckpointPolicy
from anip_server.primitives.merkle import MerkleTree

# Database path — configurable via ANIP_DB_PATH environment variable
DB_PATH = Path(os.environ.get("ANIP_DB_PATH", str(Path(__file__).parent / "anip.db")))

_connection: sqlite3.Connection | None = None
_audit_signer = None
_merkle_tree = MerkleTree()
_checkpoint_policy: CheckpointPolicy | None = None
_entries_since_checkpoint: int = 0


def set_audit_signer(signer):
    """Set the audit entry signer (KeyManager instance)."""
    global _audit_signer
    _audit_signer = signer


def set_checkpoint_policy(policy: CheckpointPolicy | None) -> None:
    """Set the checkpoint policy for automatic checkpointing."""
    global _checkpoint_policy, _entries_since_checkpoint
    _checkpoint_policy = policy
    _entries_since_checkpoint = 0


def get_connection() -> sqlite3.Connection:
    """Get or create the database connection."""
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")
        _init_schema(_connection)
    return _connection


@contextmanager
def transaction() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database transactions."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS delegation_tokens (
            token_id TEXT PRIMARY KEY,
            issuer TEXT NOT NULL,
            subject TEXT NOT NULL,
            scope TEXT NOT NULL,          -- JSON array
            purpose TEXT NOT NULL,         -- JSON object
            parent TEXT,
            expires TEXT NOT NULL,         -- ISO 8601
            constraints TEXT NOT NULL,     -- JSON object
            root_principal TEXT,           -- Human at root of delegation chain
            registered_at TEXT NOT NULL,
            FOREIGN KEY (parent) REFERENCES delegation_tokens(token_id)
        );

        CREATE TABLE IF NOT EXISTS bookings (
            booking_id TEXT PRIMARY KEY,
            flight_number TEXT NOT NULL,
            flight_date TEXT NOT NULL,
            passengers INTEGER NOT NULL,
            total_cost REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            booked_by TEXT NOT NULL,
            on_behalf_of TEXT NOT NULL,
            booked_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            capability TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'active',  -- active, completed, expired
            data TEXT NOT NULL DEFAULT '{}',        -- JSON object
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT
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
            previous_hash TEXT NOT NULL,
            signature TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_audit_capability ON audit_log(capability);
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_root_principal ON audit_log(root_principal);
        CREATE INDEX IF NOT EXISTS idx_sessions_capability ON sessions(capability);

        CREATE TABLE IF NOT EXISTS checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checkpoint_id TEXT NOT NULL UNIQUE,
            first_sequence INTEGER NOT NULL,
            last_sequence INTEGER NOT NULL,
            merkle_root TEXT NOT NULL,
            previous_checkpoint TEXT,
            timestamp TEXT NOT NULL,
            entry_count INTEGER NOT NULL,
            signature TEXT NOT NULL
        );
    """)


# --- Delegation Token Persistence ---


def store_token(token_data: dict[str, Any]) -> None:
    """Store a delegation token."""
    with transaction() as conn:
        conn.execute(
            """INSERT INTO delegation_tokens
               (token_id, issuer, subject, scope, purpose, parent, expires, constraints, root_principal, registered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                token_data["token_id"],
                token_data["issuer"],
                token_data["subject"],
                json.dumps(token_data["scope"]),
                json.dumps(token_data["purpose"]),
                token_data.get("parent"),
                token_data["expires"],
                json.dumps(token_data["constraints"]),
                token_data.get("root_principal"),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def load_token(token_id: str) -> dict[str, Any] | None:
    """Load a delegation token by ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM delegation_tokens WHERE token_id = ?", (token_id,)
    ).fetchone()
    if row is None:
        return None
    return {
        "token_id": row["token_id"],
        "issuer": row["issuer"],
        "subject": row["subject"],
        "scope": json.loads(row["scope"]),
        "purpose": json.loads(row["purpose"]),
        "parent": row["parent"],
        "expires": row["expires"],
        "constraints": json.loads(row["constraints"]),
        "root_principal": row["root_principal"],
    }


# --- Booking Persistence ---


def store_booking(booking: dict[str, Any]) -> None:
    """Store a booking."""
    with transaction() as conn:
        conn.execute(
            """INSERT INTO bookings
               (booking_id, flight_number, flight_date, passengers, total_cost,
                currency, booked_by, on_behalf_of, booked_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                booking["booking_id"],
                booking["flight_number"],
                booking["flight_date"],
                booking["passengers"],
                booking["total_cost"],
                booking.get("currency", "USD"),
                booking["booked_by"],
                booking["on_behalf_of"],
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def load_booking(booking_id: str) -> dict[str, Any] | None:
    """Load a booking by ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def next_booking_id() -> str:
    """Generate the next booking ID."""
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as count FROM bookings").fetchone()
    return f"BK-{row['count'] + 1:04d}"


# --- Session Persistence ---


def create_session(
    session_id: str,
    capability: str,
    data: dict[str, Any] | None = None,
    expires_at: str | None = None,
) -> dict[str, Any]:
    """Create a new session."""
    now = datetime.now(timezone.utc).isoformat()
    with transaction() as conn:
        conn.execute(
            """INSERT INTO sessions (session_id, capability, data, created_at, updated_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, capability, json.dumps(data or {}), now, now, expires_at),
        )
    return {
        "session_id": session_id,
        "capability": capability,
        "state": "active",
        "data": data or {},
        "created_at": now,
        "updated_at": now,
    }


def update_session(session_id: str, data: dict[str, Any], state: str = "active") -> None:
    """Update session data and state."""
    with transaction() as conn:
        conn.execute(
            """UPDATE sessions SET data = ?, state = ?, updated_at = ? WHERE session_id = ?""",
            (json.dumps(data), state, datetime.now(timezone.utc).isoformat(), session_id),
        )


def load_session(session_id: str) -> dict[str, Any] | None:
    """Load a session by ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if row is None:
        return None
    return {
        "session_id": row["session_id"],
        "capability": row["capability"],
        "state": row["state"],
        "data": json.loads(row["data"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# --- Audit Log ---


def _compute_entry_hash(entry: dict[str, Any]) -> str:
    """Compute SHA-256 hash of an audit entry for the hash chain."""
    canonical = json.dumps(
        {k: v for k, v in sorted(entry.items()) if k not in ("signature", "id")},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def log_invocation(
    capability: str,
    token_id: str | None,
    issuer: str | None,
    subject: str | None,
    root_principal: str | None,
    parameters: dict[str, Any] | None,
    success: bool,
    result_summary: dict[str, Any] | None = None,
    failure_type: str | None = None,
    cost_actual: dict[str, Any] | None = None,
    delegation_chain: list[str] | None = None,
) -> None:
    """Log a capability invocation to the audit log."""
    with transaction() as conn:
        # Get last entry's hash and sequence number
        last_row = conn.execute(
            "SELECT sequence_number, previous_hash FROM audit_log ORDER BY sequence_number DESC LIMIT 1"
        ).fetchone()

        if last_row is None:
            sequence_number = 1
            # For the very first entry, use sentinel value
            previous_hash = "sha256:0"
        else:
            sequence_number = last_row["sequence_number"] + 1
            # Compute hash of the last entry to chain
            last_entry_row = conn.execute(
                "SELECT * FROM audit_log WHERE sequence_number = ?",
                (last_row["sequence_number"],),
            ).fetchone()
            last_entry = dict(last_entry_row)
            # Parse JSON fields for canonical hashing
            for field in ("parameters", "result_summary", "cost_actual", "delegation_chain"):
                if last_entry[field]:
                    last_entry[field] = json.loads(last_entry[field])
            last_entry["success"] = bool(last_entry["success"])
            previous_hash = _compute_entry_hash(last_entry)

        now = datetime.now(timezone.utc).isoformat()

        # Build entry dict for signing
        entry_dict = {
            "sequence_number": sequence_number,
            "timestamp": now,
            "capability": capability,
            "token_id": token_id,
            "issuer": issuer,
            "subject": subject,
            "root_principal": root_principal,
            "parameters": parameters,
            "success": success,
            "result_summary": result_summary,
            "failure_type": failure_type,
            "cost_actual": cost_actual,
            "delegation_chain": delegation_chain,
            "previous_hash": previous_hash,
        }

        # Accumulate into Merkle tree (canonical bytes match _compute_entry_hash)
        canonical_bytes = json.dumps(
            {k: v for k, v in sorted(entry_dict.items()) if k not in ("signature", "id")},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        _merkle_tree.add_leaf(canonical_bytes)

        # Sign audit entry with dedicated audit key
        signature = None
        if _audit_signer is not None:
            signature = _audit_signer.sign_audit_entry(entry_dict)

        conn.execute(
            """INSERT INTO audit_log
               (sequence_number, timestamp, capability, token_id, issuer, subject, root_principal,
                parameters, success, result_summary, failure_type, cost_actual, delegation_chain,
                previous_hash, signature)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sequence_number,
                now,
                capability,
                token_id,
                issuer,
                subject,
                root_principal,
                json.dumps(parameters) if parameters else None,
                1 if success else 0,
                json.dumps(result_summary) if result_summary else None,
                failure_type,
                json.dumps(cost_actual) if cost_actual else None,
                json.dumps(delegation_chain) if delegation_chain else None,
                previous_hash,
                signature,
            ),
        )

    # Auto-checkpoint based on entry count policy (outside the transaction)
    global _entries_since_checkpoint
    _entries_since_checkpoint += 1
    if _checkpoint_policy and _checkpoint_policy.should_checkpoint(
        entries_since_last=_entries_since_checkpoint
    ):
        create_checkpoint()
        _entries_since_checkpoint = 0


def query_audit_log(
    capability: str | None = None,
    root_principal: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query the audit log with optional filters."""
    conn = get_connection()
    conditions = []
    params: list[Any] = []

    if capability:
        conditions.append("capability = ?")
        params.append(capability)
    if root_principal:
        conditions.append("root_principal = ?")
        params.append(root_principal)
    if since:
        conditions.append("timestamp >= ?")
        params.append(since)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM audit_log {where} ORDER BY sequence_number DESC LIMIT ?",
        [*params, limit],
    ).fetchall()

    results = []
    for row in rows:
        entry = dict(row)
        # Parse JSON fields
        for field in ("parameters", "result_summary", "cost_actual", "delegation_chain"):
            if entry[field]:
                entry[field] = json.loads(entry[field])
        entry["success"] = bool(entry["success"])
        results.append(entry)

    return results


def get_merkle_snapshot() -> dict[str, Any]:
    """Return the current Merkle tree snapshot (root hash and leaf count)."""
    return _merkle_tree.snapshot()


def get_merkle_inclusion_proof(index: int) -> dict[str, Any]:
    """Return an inclusion proof for the leaf at *index*."""
    return {
        "path": _merkle_tree.inclusion_proof(index),
        "root": _merkle_tree.root,
        "leaf_count": _merkle_tree.leaf_count,
    }


# --- Checkpoints ---


def store_checkpoint(body: dict[str, Any], signature: str) -> None:
    """Insert a checkpoint record into the database."""
    with transaction() as conn:
        conn.execute(
            """INSERT INTO checkpoints
               (checkpoint_id, first_sequence, last_sequence, merkle_root,
                previous_checkpoint, timestamp, entry_count, signature)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body["checkpoint_id"],
                body["range"]["first_sequence"],
                body["range"]["last_sequence"],
                body["merkle_root"],
                body["previous_checkpoint"],
                body["timestamp"],
                body["entry_count"],
                signature,
            ),
        )


def get_checkpoints(limit: int = 10) -> list[dict[str, Any]]:
    """Return checkpoints ordered by id (ascending)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM checkpoints ORDER BY id ASC LIMIT ?", (limit,)
    ).fetchall()
    results = []
    for row in rows:
        results.append({
            "checkpoint_id": row["checkpoint_id"],
            "first_sequence": row["first_sequence"],
            "last_sequence": row["last_sequence"],
            "merkle_root": row["merkle_root"],
            "previous_checkpoint": row["previous_checkpoint"],
            "timestamp": row["timestamp"],
            "entry_count": row["entry_count"],
            "signature": row["signature"],
        })
    return results


def create_checkpoint() -> tuple[dict[str, Any], str]:
    """Create a checkpoint: snapshot Merkle state, sign, store, return.

    Returns ``(body_dict, detached_jws_signature)``.
    """
    snap = get_merkle_snapshot()
    conn = get_connection()

    # Determine previous checkpoint (if any)
    prev_row = conn.execute(
        "SELECT * FROM checkpoints ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if prev_row is None:
        first_sequence = 1
        previous_checkpoint = None
        checkpoint_number = 1
    else:
        first_sequence = prev_row["last_sequence"] + 1
        # Hash the previous checkpoint body (canonical JSON)
        prev_body = {
            "version": "0.3",
            "service_id": os.environ.get("ANIP_SERVICE_ID", "anip-reference-server"),
            "checkpoint_id": prev_row["checkpoint_id"],
            "range": {
                "first_sequence": prev_row["first_sequence"],
                "last_sequence": prev_row["last_sequence"],
            },
            "merkle_root": prev_row["merkle_root"],
            "previous_checkpoint": prev_row["previous_checkpoint"],
            "timestamp": prev_row["timestamp"],
            "entry_count": prev_row["entry_count"],
        }
        prev_canonical = json.dumps(prev_body, separators=(",", ":"), sort_keys=True).encode()
        previous_checkpoint = f"sha256:{hashlib.sha256(prev_canonical).hexdigest()}"
        # Extract number from previous checkpoint_id
        checkpoint_number = int(prev_row["checkpoint_id"].split("-")[1]) + 1

    last_sequence = snap["leaf_count"]
    entry_count = last_sequence - first_sequence + 1

    body = {
        "version": "0.3",
        "service_id": os.environ.get("ANIP_SERVICE_ID", "anip-reference-server"),
        "checkpoint_id": f"ckpt-{checkpoint_number}",
        "range": {
            "first_sequence": first_sequence,
            "last_sequence": last_sequence,
        },
        "merkle_root": snap["root"],
        "previous_checkpoint": previous_checkpoint,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entry_count": entry_count,
    }

    # Sign with detached JWS using the audit signer
    canonical_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    signature = ""
    if _audit_signer is not None:
        signature = _audit_signer.sign_jws_detached(canonical_bytes)

    store_checkpoint(body, signature)

    # Reset entry counter after checkpoint creation
    global _entries_since_checkpoint
    _entries_since_checkpoint = 0

    return body, signature


def get_anchoring_lag() -> dict[str, Any]:
    """Return metrics describing how far the audit log is from the last checkpoint."""
    checkpoints = get_checkpoints(limit=1)
    if checkpoints:
        last_ts = checkpoints[-1]["timestamp"]
        last_dt = datetime.fromisoformat(last_ts)
        seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
    else:
        seconds = 0.0
    return {
        "entries_since_last_checkpoint": _entries_since_checkpoint,
        "seconds_since_last_checkpoint": seconds,
        "pending_sink_publications": 0,  # placeholder for Task 13
        "max_lag_exceeded": False,  # placeholder
    }


def has_new_entries_since_checkpoint() -> bool:
    """Return True if there are audit entries since the last checkpoint."""
    return _entries_since_checkpoint > 0


def get_checkpoint_by_id(checkpoint_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)).fetchone()
    if row is None:
        return None
    return {
        "checkpoint_id": row["checkpoint_id"],
        "range": {"first_sequence": row["first_sequence"], "last_sequence": row["last_sequence"]},
        "merkle_root": row["merkle_root"],
        "previous_checkpoint": row["previous_checkpoint"],
        "timestamp": row["timestamp"],
        "entry_count": row["entry_count"],
        "signature": row["signature"],
    }


def rebuild_merkle_tree_to(sequence_number: int) -> MerkleTree:
    """Rebuild Merkle tree from audit entries up to sequence_number."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM audit_log WHERE sequence_number <= ? ORDER BY sequence_number ASC",
        (sequence_number,)
    ).fetchall()
    tree = MerkleTree()
    for row in rows:
        entry = dict(row)
        for field in ("parameters", "result_summary", "cost_actual", "delegation_chain"):
            if entry[field]:
                entry[field] = json.loads(entry[field])
        entry["success"] = bool(entry["success"])
        canonical = json.dumps(
            {k: v for k, v in sorted(entry.items()) if k not in ("signature", "id")},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        tree.add_leaf(canonical)
    return tree
