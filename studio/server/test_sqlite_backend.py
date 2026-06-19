from studio.server import db


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
