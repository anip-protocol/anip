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
        )
    return _pool


def init_db() -> None:
    """Create the schema_version table and run unapplied migrations."""
    with get_pool().connection() as conn:
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
        conn.commit()
