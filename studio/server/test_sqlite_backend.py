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


def test_sqlite_migration_status_after_init_db_is_applied(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "studio.sqlite"
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDIO_SQLITE_PATH", str(sqlite_path))
    db.close_pool()
    db.set_database_url(f"sqlite:///{sqlite_path}")
    try:
        db.init_db()
        status = db.migration_status()
        assert status["applied"] is True
        assert status["pending"] == []
        assert status["applied_count"] == status["expected_count"] >= 1
    finally:
        db.close_pool()


def test_sqlite_migrations_create_all_core_tables(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "studio.sqlite"
    expected_tables = {
        "projects",
        "workspaces",
        "workspace_connections",
        "requirements_sets",
        "scenarios",
        "proposals",
        "shapes",
        "evaluations",
        "project_documents",
        "pm_artifacts",
        "studio_settings",
        "local_publications",
        "integration_discovery_records",
        "application_integration_projects",
        "data_access_projects",
        "service_metadata_artifacts",
    }
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDIO_SQLITE_PATH", str(sqlite_path))
    db.close_pool()
    db.set_database_url(f"sqlite:///{sqlite_path}")
    try:
        db.init_db()
        with db.get_pool().connection() as conn:
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        assert expected_tables <= tables
    finally:
        db.close_pool()


def test_sqlite_failed_migration_does_not_record_schema_version(
    monkeypatch, tmp_path
):
    sqlite_path = tmp_path / "studio.sqlite"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_ok.sql").write_text(
        "CREATE TABLE ok_table (id TEXT PRIMARY KEY);"
    )
    (migrations_dir / "002_fail.sql").write_text(
        "CREATE TABLE rolled_back_table (id TEXT PRIMARY KEY);"
        "INSERT INTO missing_table (id) VALUES ('boom');"
    )
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDIO_SQLITE_PATH", str(sqlite_path))
    monkeypatch.setattr(db, "_migrations_dir", lambda: migrations_dir)
    db.close_pool()
    db.set_database_url(f"sqlite:///{sqlite_path}")
    try:
        with pytest.raises(Exception):
            db.init_db()
        with db.get_pool().connection() as conn:
            versions = [
                row["version"]
                for row in conn.execute(
                    "SELECT version FROM schema_version ORDER BY version"
                ).fetchall()
            ]
            assert versions == [1]
            rolled_back = conn.execute(
                "SELECT EXISTS("
                "  SELECT 1 FROM sqlite_master"
                "  WHERE type = 'table' AND name = 'rolled_back_table'"
                ") AS table_exists"
            ).fetchone()
            assert rolled_back["table_exists"] == 0
    finally:
        db.close_pool()


def test_postgres_url_uses_postgres_migrations_when_backend_env_is_sqlite(
    monkeypatch,
):
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    db.close_pool()
    db.set_database_url("postgresql://anip:anip@localhost:5432/anip_studio")
    try:
        versions = db.expected_migration_versions()
        assert len(versions) > 1
        assert 13 in versions
    finally:
        db.close_pool()
