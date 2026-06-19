import pytest

from studio.server import db
from studio.server.db_backends import sqlite_path_from_url


def test_database_backend_defaults_to_postgres(monkeypatch):
    monkeypatch.delenv("STUDIO_DB_BACKEND", raising=False)
    assert db.database_backend() == "postgres"


def test_database_backend_accepts_sqlite(monkeypatch):
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    assert db.database_backend() == "sqlite"


def test_sqlite_database_url_uses_explicit_path(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "studio.sqlite"
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDIO_SQLITE_PATH", str(sqlite_path))
    assert db.default_database_url() == f"sqlite:///{sqlite_path}"


def test_sqlite_path_from_url_supports_absolute_path(tmp_path):
    sqlite_path = tmp_path / "studio.sqlite"
    assert sqlite_path_from_url(f"sqlite:///{sqlite_path}") == sqlite_path


def test_sqlite_path_from_url_supports_relative_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert sqlite_path_from_url("sqlite:///relative/path.db") == (
        tmp_path / "relative" / "path.db"
    )


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite://relative.db",
        "sqlite://localhost/tmp.db",
    ],
)
def test_sqlite_path_from_url_rejects_netloc(database_url):
    with pytest.raises(RuntimeError, match="must not include a host"):
        sqlite_path_from_url(database_url)


@pytest.mark.parametrize("database_url", ["sqlite://", "sqlite:///", "sqlite:////"])
def test_sqlite_path_from_url_rejects_empty_path(database_url):
    with pytest.raises(RuntimeError, match="must include a database path"):
        sqlite_path_from_url(database_url)


def test_sqlite_pool_creates_parent_directory(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "nested" / "studio.sqlite"
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDIO_SQLITE_PATH", str(sqlite_path))
    db.close_pool()
    db.set_database_url(f"sqlite:///{sqlite_path}")
    try:
        with db.get_pool().connection() as conn:
            conn.execute("SELECT 1")
        assert sqlite_path.exists()
    finally:
        db.close_pool()


def test_sqlite_init_db_runs_migrations(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "studio.sqlite"
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDIO_SQLITE_PATH", str(sqlite_path))
    db.close_pool()
    db.set_database_url(f"sqlite:///{sqlite_path}")
    try:
        db.init_db()
        with db.get_pool().connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM schema_version").fetchone()
            assert row["count"] >= 1
            conn.execute("SELECT id, name FROM projects")
    finally:
        db.close_pool()
