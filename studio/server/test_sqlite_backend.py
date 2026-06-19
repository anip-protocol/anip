import pytest

from studio.server import db
from studio.server.db_backends import sqlite_path_from_url
from studio.server.repository import (
    create_project,
    create_workspace,
    list_projects,
    list_workspaces,
)


def _run_sqlite_migration_file(conn, sql_file):
    with conn.transaction():
        for statement in db._sqlite_migration_statements(sql_file.read_text()):
            conn.execute(statement)


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
            evaluation_columns = {
                row["name"]: row
                for row in conn.execute("PRAGMA table_info(evaluations)").fetchall()
            }
            project_columns = {
                row["name"]: row
                for row in conn.execute("PRAGMA table_info(projects)").fetchall()
            }
        assert expected_tables <= tables
        assert evaluation_columns["proposal_id"]["notnull"] == 0
        assert project_columns["workspace_id"]["notnull"] == 1
    finally:
        db.close_pool()


def test_sqlite_workspace_migration_preserves_seeded_upgrade_rows(
    monkeypatch, tmp_path
):
    sqlite_path = tmp_path / "studio.sqlite"
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDIO_SQLITE_PATH", str(sqlite_path))
    db.close_pool()
    db.set_database_url(f"sqlite:///{sqlite_path}")
    migrations_dir = db._migrations_dir()
    count_tables = [
        "projects",
        "requirements_sets",
        "scenarios",
        "proposals",
        "shapes",
        "evaluations",
        "vocabulary",
    ]
    try:
        with db.get_pool().connection() as conn:
            for migration_name in (
                "001_initial.sql",
                "002_slice5_hardening.sql",
                "003_shapes.sql",
            ):
                _run_sqlite_migration_file(conn, migrations_dir / migration_name)

            conn.execute(
                "INSERT INTO projects (id, name, summary, domain, labels) "
                "VALUES (%s, %s, %s, %s, %s)",
                ("proj-1", "Project One", "summary", "domain", '["seed"]'),
            )
            conn.execute(
                "INSERT INTO requirements_sets "
                "(id, project_id, title, status, data, content_hash, role) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                ("req-1", "proj-1", "Requirements", "active", '{"req":1}', "hr", "primary"),
            )
            conn.execute(
                "INSERT INTO scenarios "
                "(id, project_id, title, status, data, content_hash) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                ("scn-1", "proj-1", "Scenario", "active", '{"scn":1}', "hs"),
            )
            conn.execute(
                "INSERT INTO proposals "
                "(id, project_id, requirements_id, title, status, data, content_hash) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                ("prop-1", "proj-1", "req-1", "Proposal", "active", '{"prop":1}', "hp"),
            )
            conn.execute(
                "INSERT INTO shapes "
                "(id, project_id, requirements_id, title, status, data, content_hash) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                ("shape-1", "proj-1", "req-1", "Shape", "active", '{"shape":1}', "hsh"),
            )
            conn.execute(
                "INSERT INTO evaluations "
                "(id, project_id, proposal_id, scenario_id, requirements_id, result, "
                "data, input_snapshot, requirements_hash, proposal_hash, scenario_hash, "
                "shape_id, shape_hash, derived_expectations) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    "eval-1",
                    "proj-1",
                    "prop-1",
                    "scn-1",
                    "req-1",
                    "HANDLED",
                    '{"eval":1}',
                    '{"input":1}',
                    "hr",
                    "hp",
                    "hs",
                    "shape-1",
                    "hsh",
                    '{"expect":1}',
                ),
            )
            conn.execute(
                "INSERT INTO vocabulary "
                "(project_id, category, value, origin, description, evaluator_recognized) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                ("proj-1", "term", "value", "custom", "description", 1),
            )
            conn.commit()

            before_counts = {
                table: conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()[
                    "count"
                ]
                for table in count_tables
            }

            _run_sqlite_migration_file(conn, migrations_dir / "004_workspaces.sql")

            after_counts = {
                table: conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()[
                    "count"
                ]
                for table in count_tables
            }
            project = conn.execute(
                "SELECT name, workspace_id FROM projects WHERE id = %s", ("proj-1",)
            ).fetchone()
            evaluation = conn.execute(
                "SELECT proposal_id, shape_id FROM evaluations WHERE id = %s",
                ("eval-1",),
            ).fetchone()
            vocabulary = conn.execute(
                "SELECT description, evaluator_recognized "
                "FROM vocabulary WHERE project_id = %s",
                ("proj-1",),
            ).fetchone()
            foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
            project_foreign_keys = [
                dict(row) for row in conn.execute("PRAGMA foreign_key_list(projects)")
            ]
            dependent_foreign_keys = {
                table: [
                    dict(row)
                    for row in conn.execute(f"PRAGMA foreign_key_list({table})")
                ]
                for table in (
                    "requirements_sets",
                    "scenarios",
                    "proposals",
                    "shapes",
                    "evaluations",
                    "vocabulary",
                )
            }

        assert before_counts == {
            "projects": 1,
            "requirements_sets": 1,
            "scenarios": 1,
            "proposals": 1,
            "shapes": 1,
            "evaluations": 1,
            "vocabulary": 1,
        }
        assert after_counts == before_counts
        assert dict(project) == {"name": "Project One", "workspace_id": "default"}
        assert dict(evaluation) == {"proposal_id": "prop-1", "shape_id": "shape-1"}
        assert dict(vocabulary) == {
            "description": "description",
            "evaluator_recognized": 1,
        }
        assert foreign_key_errors == []
        assert any(
            row["from"] == "workspace_id"
            and row["table"] == "workspaces"
            and row["to"] == "id"
            and row["on_delete"] == "CASCADE"
            for row in project_foreign_keys
        )
        assert all(
            not row["table"].endswith("_old")
            for rows in dependent_foreign_keys.values()
            for row in rows
        )
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


def test_sqlite_json_fields_round_trip(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "studio.sqlite"
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDIO_SQLITE_PATH", str(sqlite_path))
    db.close_pool()
    db.set_database_url(f"sqlite:///{sqlite_path}")
    try:
        db.init_db()
        with db.get_pool().connection() as conn:
            create_workspace(
                conn,
                workspace_id="sqlite-workspace",
                name="SQLite Workspace",
                summary="Desktop workspace",
            )
            create_project(
                conn,
                project_id="sqlite-project",
                workspace_id="sqlite-workspace",
                name="SQLite Project",
                labels=["desktop", "sqlite"],
                integration_profile={
                    "kind": "native_api",
                    "systems": [{"system_id": "local"}],
                },
            )
            workspaces = list_workspaces(conn)
            projects = list_projects(conn, workspace_id="sqlite-workspace")

        workspace = next(item for item in workspaces if item["id"] == "sqlite-workspace")
        project = next(item for item in projects if item["id"] == "sqlite-project")
        assert workspace["projects_count"] == 1
        assert project["labels"] == ["desktop", "sqlite"]
        assert project["integration_profile"] == {
            "kind": "native_api",
            "systems": [{"system_id": "local"}],
        }
    finally:
        db.close_pool()
