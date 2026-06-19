"""Database backend helpers for ANIP Studio."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote, urlparse


SUPPORTED_BACKENDS = {"postgres", "sqlite"}


def database_backend() -> str:
    value = os.getenv("STUDIO_DB_BACKEND", "postgres").strip().lower()
    if value not in SUPPORTED_BACKENDS:
        raise RuntimeError(
            f"Unsupported STUDIO_DB_BACKEND={value!r}; expected one of {sorted(SUPPORTED_BACKENDS)}"
        )
    return value


def default_database_url() -> str:
    backend = database_backend()
    if backend == "sqlite":
        sqlite_path = os.getenv("STUDIO_SQLITE_PATH", "").strip()
        if not sqlite_path:
            sqlite_path = str(Path.home() / ".anip" / "studio" / "studio.sqlite")
        return f"sqlite:///{sqlite_path}"
    return os.environ.get(
        "DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio"
    )


def migrations_dir(base_dir: Path) -> Path:
    backend = database_backend()
    candidate = base_dir / "migrations" / backend
    if candidate.is_dir():
        return candidate
    return base_dir / "migrations"


def sqlite_path_from_url(database_url: str) -> Path:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        raise RuntimeError(f"Expected sqlite URL, got {database_url!r}")
    if parsed.netloc:
        raise RuntimeError(f"SQLite URL must not include a host: {database_url!r}")
    raw_path = unquote(parsed.path)
    if not raw_path or raw_path in {"/", "//"}:
        raise RuntimeError(f"SQLite URL must include a database path: {database_url!r}")
    if raw_path.startswith("//"):
        raw_path = raw_path[1:]
    elif raw_path.startswith("/"):
        raw_path = raw_path[1:]
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


class SQLiteConnection:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection
        self._connection.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple | list | None = None):
        return self._connection.execute(sql, params or ())

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()

    @contextmanager
    def transaction(self):
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            yield self
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise


class SQLitePool:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.path = sqlite_path_from_url(database_url)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self):
        raw = sqlite3.connect(self.path)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON")
        raw.execute("PRAGMA journal_mode = WAL")
        conn = SQLiteConnection(raw)
        try:
            yield conn
        finally:
            conn.close()

    def close(self) -> None:
        return None
