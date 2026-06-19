"""Database backend helpers for ANIP Studio."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from psycopg.types.json import Json, Jsonb


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
        sqlite_sql = _sqlite_sql(sql)
        sqlite_params = tuple(_sqlite_param(value) for value in (params or ()))
        json_fields = _sqlite_json_fields(sqlite_sql)
        return SQLiteCursor(
            self._connection.execute(sqlite_sql, sqlite_params),
            json_fields=json_fields,
        )

    def executescript(self, sql: str) -> None:
        self._connection.executescript(sql)

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
        raw.create_function("now", 0, _sqlite_now)
        raw.execute("PRAGMA foreign_keys = ON")
        raw.execute("PRAGMA journal_mode = WAL")
        conn = SQLiteConnection(raw)
        try:
            yield conn
        finally:
            conn.close()

    def close(self) -> None:
        return None


class SQLiteCursor:
    def __init__(self, cursor: sqlite3.Cursor, *, json_fields: set[str] | None = None):
        self._cursor = cursor
        self._json_fields = json_fields or set()

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self) -> dict | None:
        return _sqlite_row(self._cursor.fetchone(), self._json_fields)

    def fetchall(self) -> list[dict]:
        return [_sqlite_row(row, self._json_fields) for row in self._cursor.fetchall()]

    def __iter__(self):
        for row in self._cursor:
            yield _sqlite_row(row, self._json_fields)

    def __getattr__(self, name: str):
        return getattr(self._cursor, name)


def _sqlite_row(row: sqlite3.Row | None, json_fields: set[str] | None = None) -> dict | None:
    if row is None:
        return None
    result = dict(row)
    for field in json_fields or set():
        if field in result and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except json.JSONDecodeError:
                pass
    return result


def _sqlite_param(value):
    if isinstance(value, (Json, Jsonb)):
        dumps = getattr(value, "dumps", None)
        if callable(dumps):
            return dumps(value.obj)
        return json.dumps(value.obj)
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def _sqlite_sql(sql: str) -> str:
    sqlite_sql = sql.replace("%s", "?")
    sqlite_sql = re.sub(r"(\?|'[^']*')::[a-zA-Z_][a-zA-Z0-9_]*", r"\1", sqlite_sql)
    return sqlite_sql


def _sqlite_json_fields(sql: str) -> set[str]:
    normalized = sql.lower()
    if "studio_settings" in normalized:
        return {"value"}
    return set()


def _sqlite_now() -> str:
    return datetime.now(timezone.utc).isoformat()
