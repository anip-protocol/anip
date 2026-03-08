"""SQLite persistence layer for the ANIP reference implementation.

Stores delegation tokens, bookings, session state, and audit logs.
In production, swap SQLite for Postgres — the schema stays the same.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

# Default database path — can be overridden via environment variable
DB_PATH = Path(__file__).parent / "anip.db"

_connection: sqlite3.Connection | None = None


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
            delegation_chain TEXT          -- JSON array of token_ids
        );

        CREATE INDEX IF NOT EXISTS idx_audit_capability ON audit_log(capability);
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_root_principal ON audit_log(root_principal);
        CREATE INDEX IF NOT EXISTS idx_sessions_capability ON sessions(capability);
    """)


# --- Delegation Token Persistence ---


def store_token(token_data: dict[str, Any]) -> None:
    """Store a delegation token."""
    with transaction() as conn:
        conn.execute(
            """INSERT INTO delegation_tokens
               (token_id, issuer, subject, scope, purpose, parent, expires, constraints, registered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                token_data["token_id"],
                token_data["issuer"],
                token_data["subject"],
                json.dumps(token_data["scope"]),
                json.dumps(token_data["purpose"]),
                token_data.get("parent"),
                token_data["expires"],
                json.dumps(token_data["constraints"]),
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
        conn.execute(
            """INSERT INTO audit_log
               (timestamp, capability, token_id, issuer, subject, root_principal,
                parameters, success, result_summary, failure_type, cost_actual, delegation_chain)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
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
            ),
        )


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
        f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT ?",
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
