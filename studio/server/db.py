"""Database connection pool and migration runner for ANIP Studio."""

import os
import sqlite3
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .db_backends import SQLitePool, database_backend, default_database_url

DATABASE_URL = os.environ["DATABASE_URL"] if "DATABASE_URL" in os.environ else default_database_url()
STUDIO_MIGRATION_ADVISORY_LOCK_ID = 2402402402

_pool: ConnectionPool | SQLitePool | None = None


def _is_sqlite_url() -> bool:
    return DATABASE_URL.startswith("sqlite://")


def _migrations_dir() -> Path:
    if _is_sqlite_url():
        return Path(__file__).parent / "migrations" / "sqlite"
    return Path(__file__).parent / "migrations"


def current_backend() -> str:
    return database_backend()


def get_pool() -> ConnectionPool | SQLitePool:
    """Return the global connection pool, creating it lazily."""
    global _pool
    if _pool is None:
        if DATABASE_URL.startswith("sqlite://"):
            _pool = SQLitePool(DATABASE_URL)
        else:
            _pool = ConnectionPool(
                DATABASE_URL,
                kwargs={"row_factory": dict_row},
                min_size=2,
                max_size=10,
                open=True,
            )
    return _pool


def set_database_url(database_url: str) -> None:
    """Switch the global runtime database URL and reset the pool."""
    global DATABASE_URL
    if database_url == DATABASE_URL:
        return
    close_pool()
    DATABASE_URL = database_url


def close_pool() -> None:
    """Close and clear the global connection pool.

    Tests recreate isolated schemas between modules, so any pooled
    connections pointing at a dropped schema must not be reused.
    """
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def init_db() -> None:
    """Create the schema_version table and run unapplied migrations."""
    with get_pool().connection() as conn:
        if _is_sqlite_url():
            _run_migrations(conn)
            conn.commit()
            return
        conn.execute("SELECT pg_advisory_lock(%s)", (STUDIO_MIGRATION_ADVISORY_LOCK_ID,))
        try:
            _run_migrations(conn)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (STUDIO_MIGRATION_ADVISORY_LOCK_ID,))
        conn.commit()


def _run_migrations(conn) -> None:
    """Run unapplied Studio migrations on an existing connection."""
    if _is_sqlite_url():
        _run_sqlite_migrations(conn)
        return

    with conn.transaction():
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            "  version INTEGER PRIMARY KEY,"
            "  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()"
            ")"
        )
        applied = {
            r["version"]
            for r in conn.execute("SELECT version FROM schema_version").fetchall()
        }
        for sql_file in sorted(_migrations_dir().glob("*.sql")):
            version = int(sql_file.stem.split("_")[0])
            if version not in applied:
                conn.execute(sql_file.read_text())
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (%s)", (version,)
                )


def _run_sqlite_migrations(conn) -> None:
    """Run SQLite migrations with each file and version insert atomically."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "  version INTEGER PRIMARY KEY,"
        "  applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
        ")"
    )
    conn.commit()

    applied = {
        r["version"]
        for r in conn.execute("SELECT version FROM schema_version").fetchall()
    }
    for sql_file in sorted(_migrations_dir().glob("*.sql")):
        version = int(sql_file.stem.split("_")[0])
        if version in applied:
            continue
        sql_text = sql_file.read_text()
        with conn.transaction():
            for statement in _sqlite_migration_statements(sql_text):
                conn.execute(statement)
            conn.execute("INSERT INTO schema_version (version) VALUES (%s)", (version,))


def _sqlite_migration_statements(sql_text: str) -> list[str]:
    """Split trusted migration files into single statements for sqlite3.execute."""
    statements: list[str] = []
    buffer: list[str] = []
    for line in sql_text.splitlines(keepends=True):
        buffer.append(line)
        candidate = "".join(buffer).strip()
        if candidate and sqlite3.complete_statement(candidate):
            statements.append(candidate)
            buffer = []
    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def expected_migration_versions() -> list[int]:
    return [int(sql_file.stem.split("_")[0]) for sql_file in sorted(_migrations_dir().glob("*.sql"))]


def migration_status() -> dict:
    expected = expected_migration_versions()
    with get_pool().connection() as conn:
        if _is_sqlite_url():
            table_exists = conn.execute(
                "SELECT EXISTS("
                "  SELECT 1 FROM sqlite_master"
                "  WHERE type = 'table' AND name = 'schema_version'"
                ") AS table_exists"
            ).fetchone()
        else:
            table_exists = conn.execute(
                "SELECT to_regclass('schema_version') IS NOT NULL AS exists"
            ).fetchone()
        exists_key = "table_exists" if _is_sqlite_url() else "exists"
        if not table_exists or not table_exists[exists_key]:
            return {
                "applied": False,
                "applied_count": 0,
                "expected_count": len(expected),
                "pending": expected,
            }
        applied = {
            r["version"]
            for r in conn.execute("SELECT version FROM schema_version").fetchall()
        }
    pending = [version for version in expected if version not in applied]
    return {
        "applied": len(pending) == 0,
        "applied_count": len(expected) - len(pending),
        "expected_count": len(expected),
        "pending": pending,
    }


def check_ready() -> dict:
    with get_pool().connection() as conn:
        conn.execute("SELECT 1")
    status = migration_status()
    if not status["applied"]:
        raise RuntimeError(f"Studio migrations pending: {status['pending']}")
    return status
