"""Postgres connection pool and migration runner for ANIP Studio."""

import os
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://anip:anip@localhost:5432/anip_studio",
)
MIGRATIONS_DIR = Path(__file__).parent / "migrations"
STUDIO_MIGRATION_ADVISORY_LOCK_ID = 2402402402

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Return the global connection pool, creating it lazily."""
    global _pool
    if _pool is None:
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
        conn.execute("SELECT pg_advisory_lock(%s)", (STUDIO_MIGRATION_ADVISORY_LOCK_ID,))
        try:
            _run_migrations(conn)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (STUDIO_MIGRATION_ADVISORY_LOCK_ID,))
        conn.commit()


def _run_migrations(conn) -> None:
    """Run unapplied Studio migrations on an existing connection."""
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
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = int(sql_file.stem.split("_")[0])
            if version not in applied:
                conn.execute(sql_file.read_text())
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (%s)", (version,)
                )


def expected_migration_versions() -> list[int]:
    return [int(sql_file.stem.split("_")[0]) for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql"))]


def migration_status() -> dict:
    expected = expected_migration_versions()
    with get_pool().connection() as conn:
        table_exists = conn.execute(
            "SELECT to_regclass('schema_version') IS NOT NULL AS exists"
        ).fetchone()
        if not table_exists or not table_exists["exists"]:
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
