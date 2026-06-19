# Studio Desktop SQLite Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ANIP Studio API run locally against SQLite so a future desktop app can launch without Docker or Postgres.

**Architecture:** Add a small database backend layer under `studio/server` that preserves the existing Postgres path and introduces a SQLite path for desktop mode. Keep router/repository behavior stable, add SQLite migrations, and prove parity through API-level tests and snapshot import smoke coverage.

**Tech Stack:** Python, FastAPI, psycopg, sqlite3, pytest, Studio migration SQL, Studio showcase snapshots.

---

## Scope

This plan implements Milestone 1 from [docs/specs/2026-06-18-studio-desktop-design.md](../specs/2026-06-18-studio-desktop-design.md):

- `STUDIO_DB_BACKEND=postgres|sqlite`
- SQLite connection adapter
- SQLite migrations
- backend-neutral migration/init path
- SQLite test lane for core Studio API flows
- dev command for local desktop API startup

This plan does not create the Tauri/Electron shell. The shell depends on the API being able to run without Postgres first.

## Files

- Create: `studio/server/db_backends.py`
- Create: `studio/server/migrations/sqlite/001_initial.sql`
- Create: `studio/server/migrations/sqlite/002_slice5_hardening.sql`
- Create: `studio/server/migrations/sqlite/003_shapes.sql`
- Create: `studio/server/migrations/sqlite/004_workspaces.sql`
- Create: `studio/server/migrations/sqlite/005_data_access_projects.sql`
- Create: `studio/server/migrations/sqlite/006_application_integration_projects.sql`
- Create: `studio/server/migrations/sqlite/007_service_metadata_artifacts.sql`
- Create: `studio/server/migrations/sqlite/008_project_documents.sql`
- Create: `studio/server/migrations/sqlite/009_pm_artifacts.sql`
- Create: `studio/server/migrations/sqlite/010_link_saved_developer_drafts_to_projects.sql`
- Create: `studio/server/migrations/sqlite/011_studio_settings.sql`
- Create: `studio/server/migrations/sqlite/012_integration_fronting_foundation.sql`
- Create: `studio/server/migrations/sqlite/013_local_publications.sql`
- Create: `studio/server/test_sqlite_backend.py`
- Create: `studio/scripts/start-desktop-api.sh`
- Modify: `studio/server/db.py`
- Modify: `studio/server/app.py`
- Modify: `studio/server/requirements.txt`
- Modify: `studio/README.md`
- Modify: `.github/workflows/ci-studio.yml`

## Task 1: Add Backend Configuration And Adapter Skeleton

**Files:**
- Create: `studio/server/db_backends.py`
- Modify: `studio/server/db.py`
- Test: `studio/server/test_sqlite_backend.py`

- [ ] **Step 1: Write failing backend-selection tests**

Create `studio/server/test_sqlite_backend.py`:

```python
import os
from pathlib import Path

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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py -q
```

Expected: failure because `database_backend()` and `default_database_url()` do not exist.

- [ ] **Step 3: Create adapter skeleton**

Create `studio/server/db_backends.py`:

```python
"""Database backend helpers for ANIP Studio."""

from __future__ import annotations

import os
from pathlib import Path


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
    return os.environ.get("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")


def migrations_dir(base_dir: Path) -> Path:
    backend = database_backend()
    candidate = base_dir / "migrations" / backend
    if candidate.exists():
        return candidate
    return base_dir / "migrations"
```

- [ ] **Step 4: Wire backend helpers into `db.py` without changing behavior**

Modify the top of `studio/server/db.py`:

```python
"""Database connection pool and migration runner for ANIP Studio."""

import os
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .db_backends import database_backend, default_database_url, migrations_dir

DATABASE_URL = os.environ.get("DATABASE_URL", default_database_url())
MIGRATIONS_DIR = migrations_dir(Path(__file__).parent)
STUDIO_MIGRATION_ADVISORY_LOCK_ID = 2402402402
```

Add these exports near the top-level functions in `studio/server/db.py`:

```python
def current_backend() -> str:
    return database_backend()
```

- [ ] **Step 5: Run backend-selection tests**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Run existing Studio health smoke**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_project_documents.py::test_read_only_database_url_only_applies_in_read_only_mode -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add studio/server/db_backends.py studio/server/db.py studio/server/test_sqlite_backend.py
git commit -m "Add Studio database backend selection"
```

## Task 2: Add SQLite Connection Wrapper

**Files:**
- Modify: `studio/server/db_backends.py`
- Modify: `studio/server/db.py`
- Test: `studio/server/test_sqlite_backend.py`

- [ ] **Step 1: Add failing SQLite connection test**

Append to `studio/server/test_sqlite_backend.py`:

```python
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
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py::test_sqlite_pool_creates_parent_directory -q
```

Expected: failure because `get_pool()` always creates a psycopg `ConnectionPool`.

- [ ] **Step 3: Implement SQLite pool shim**

Add to `studio/server/db_backends.py`:

```python
import sqlite3
from contextlib import contextmanager
from urllib.parse import unquote, urlparse


def sqlite_path_from_url(database_url: str) -> Path:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        raise RuntimeError(f"Expected sqlite URL, got {database_url!r}")
    raw_path = unquote(parsed.path)
    if raw_path.startswith("/") and parsed.netloc:
        raw_path = f"/{parsed.netloc}{raw_path}"
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
```

- [ ] **Step 4: Use SQLitePool in `db.py`**

Modify `get_pool()` in `studio/server/db.py`:

```python
from .db_backends import SQLitePool, database_backend, default_database_url, migrations_dir


def get_pool():
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
```

- [ ] **Step 5: Run SQLite connection test**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py::test_sqlite_pool_creates_parent_directory -q
```

Expected: pass.

- [ ] **Step 6: Run Postgres smoke test**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_api.py::test_readyz_returns_migration_status -q
```

Expected: pass against existing Postgres test setup.

- [ ] **Step 7: Commit**

```bash
git add studio/server/db_backends.py studio/server/db.py studio/server/test_sqlite_backend.py
git commit -m "Add SQLite pool for Studio desktop mode"
```

## Task 3: Add SQLite Migration Runner

**Files:**
- Modify: `studio/server/db.py`
- Create: `studio/server/migrations/sqlite/001_initial.sql`
- Test: `studio/server/test_sqlite_backend.py`

- [ ] **Step 1: Add failing migration test**

Append to `studio/server/test_sqlite_backend.py`:

```python
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
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py::test_sqlite_init_db_runs_migrations -q
```

Expected: failure because Postgres advisory locks and Postgres SQL do not run on SQLite.

- [ ] **Step 3: Create first SQLite migration**

Create `studio/server/migrations/sqlite/001_initial.sql` with the SQLite version of `projects`, `requirements_sets`, `scenarios`, `proposals`, `evaluations`, and `vocabulary`:

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    domain TEXT NOT NULL DEFAULT '',
    labels TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_projects_domain ON projects(domain);
CREATE INDEX idx_projects_updated ON projects(updated_at DESC);

CREATE TABLE requirements_sets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_requirements_project ON requirements_sets(project_id);

CREATE TABLE scenarios (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_scenarios_project ON scenarios(project_id);

CREATE TABLE proposals (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requirements_id TEXT NOT NULL REFERENCES requirements_sets(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_proposals_project ON proposals(project_id);
CREATE INDEX idx_proposals_requirements ON proposals(requirements_id);

CREATE TABLE evaluations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    proposal_id TEXT NOT NULL REFERENCES proposals(id),
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    requirements_id TEXT NOT NULL REFERENCES requirements_sets(id),
    result TEXT NOT NULL CHECK (result IN ('HANDLED', 'PARTIAL', 'REQUIRES_GLUE')),
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('live_validation', 'imported', 'manual')),
    data TEXT NOT NULL,
    input_snapshot TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_evaluations_project ON evaluations(project_id);
CREATE INDEX idx_evaluations_proposal ON evaluations(proposal_id);
CREATE INDEX idx_evaluations_scenario ON evaluations(scenario_id);

CREATE TABLE vocabulary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    value TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'custom' CHECK (origin IN ('canonical', 'project', 'custom')),
    description TEXT NOT NULL DEFAULT '',
    UNIQUE(project_id, category, value)
);

CREATE UNIQUE INDEX idx_vocabulary_global_unique
    ON vocabulary(category, value) WHERE project_id IS NULL;

CREATE INDEX idx_vocabulary_category ON vocabulary(category);
CREATE INDEX idx_vocabulary_project ON vocabulary(project_id);
```

- [ ] **Step 4: Split migration runner by backend**

Modify `init_db()` in `studio/server/db.py`:

```python
def init_db() -> None:
    """Create the schema_version table and run unapplied migrations."""
    with get_pool().connection() as conn:
        if DATABASE_URL.startswith("sqlite://"):
            _run_migrations(conn)
            conn.commit()
            return
        conn.execute("SELECT pg_advisory_lock(%s)", (STUDIO_MIGRATION_ADVISORY_LOCK_ID,))
        try:
            _run_migrations(conn)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (STUDIO_MIGRATION_ADVISORY_LOCK_ID,))
        conn.commit()
```

Modify `_run_migrations()` in `studio/server/db.py` to use SQLite-compatible schema-version SQL when needed:

```python
def _run_migrations(conn) -> None:
    """Run unapplied Studio migrations on an existing connection."""
    with conn.transaction():
        if DATABASE_URL.startswith("sqlite://"):
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version ("
                "  version INTEGER PRIMARY KEY,"
                "  applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
                ")"
            )
        else:
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
                sql_text = sql_file.read_text()
                if DATABASE_URL.startswith("sqlite://"):
                    conn.executescript(sql_text)
                else:
                    conn.execute(sql_text)
                conn.execute("INSERT INTO schema_version (version) VALUES (%s)", (version,))
```

- [ ] **Step 5: Add `executescript()` to SQLiteConnection**

Add to `SQLiteConnection` in `studio/server/db_backends.py`:

```python
def executescript(self, sql: str) -> None:
    self._connection.executescript(sql)
```

- [ ] **Step 6: Normalize parameter placeholders for SQLite inserts**

Add to `SQLiteConnection.execute()` in `studio/server/db_backends.py`:

```python
def execute(self, sql: str, params: tuple | list | None = None):
    sqlite_sql = sql.replace("%s", "?")
    return self._connection.execute(sqlite_sql, params or ())
```

- [ ] **Step 7: Run SQLite migration test**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py::test_sqlite_init_db_runs_migrations -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add studio/server/db.py studio/server/db_backends.py studio/server/migrations/sqlite/001_initial.sql studio/server/test_sqlite_backend.py
git commit -m "Add SQLite migration runner for Studio"
```

## Task 4: Port Remaining Studio Migrations To SQLite

**Files:**
- Create remaining files under `studio/server/migrations/sqlite/`
- Test: `studio/server/test_sqlite_backend.py`

- [ ] **Step 1: Add failing schema parity test**

Append to `studio/server/test_sqlite_backend.py`:

```python
def test_sqlite_migrations_create_all_core_tables(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "studio.sqlite"
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDIO_SQLITE_PATH", str(sqlite_path))
    db.close_pool()
    db.set_database_url(f"sqlite:///{sqlite_path}")
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
    try:
        db.init_db()
        with db.get_pool().connection() as conn:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = {row["name"] for row in rows}
        assert expected_tables <= table_names
    finally:
        db.close_pool()
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py::test_sqlite_migrations_create_all_core_tables -q
```

Expected: failure listing tables not yet created by SQLite migrations.

- [ ] **Step 3: Port each Postgres migration to SQLite**

For each file `studio/server/migrations/00N_*.sql`, create `studio/server/migrations/sqlite/00N_*.sql` with these conversions:

```text
JSONB -> TEXT
TIMESTAMPTZ NOT NULL DEFAULT now() -> TEXT NOT NULL DEFAULT (datetime('now'))
SERIAL PRIMARY KEY -> INTEGER PRIMARY KEY AUTOINCREMENT
UUID/text stays TEXT
CREATE INDEX ... DESC stays valid
ALTER TABLE ... ADD COLUMN ... JSONB -> ALTER TABLE ... ADD COLUMN ... TEXT
```

When a Postgres migration uses syntax SQLite does not support directly, replace it with equivalent SQLite-safe SQL. Example:

```sql
CREATE TABLE IF NOT EXISTS studio_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 4: Run full SQLite schema test**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py::test_sqlite_migrations_create_all_core_tables -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add studio/server/migrations/sqlite studio/server/test_sqlite_backend.py
git commit -m "Port Studio migrations to SQLite"
```

## Task 5: Add JSON Compatibility For SQLite Rows And Inserts

**Files:**
- Modify: `studio/server/db_backends.py`
- Modify: `studio/server/repository.py`
- Test: `studio/server/test_sqlite_backend.py`

- [ ] **Step 1: Add failing repository JSON round-trip test**

Append to `studio/server/test_sqlite_backend.py`:

```python
from studio.server.repository import create_workspace, list_workspaces


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
                id="sqlite-workspace",
                name="SQLite Workspace",
                summary="Desktop workspace",
                tags=["desktop", "sqlite"],
            )
            conn.commit()
            workspaces = list_workspaces(conn)
        workspace = next(item for item in workspaces if item["id"] == "sqlite-workspace")
        assert workspace["tags"] == ["desktop", "sqlite"]
    finally:
        db.close_pool()
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py::test_sqlite_json_fields_round_trip -q
```

Expected: failure because psycopg `Json` wrappers and SQLite row handling are not normalized.

- [ ] **Step 3: Normalize SQLite parameters**

Modify `SQLiteConnection.execute()` in `studio/server/db_backends.py`:

```python
import json


def _sqlite_param(value):
    if value.__class__.__name__ == "Json":
        return json.dumps(value.obj)
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def execute(self, sql: str, params: tuple | list | None = None):
    sqlite_sql = sql.replace("%s", "?")
    sqlite_params = tuple(_sqlite_param(value) for value in (params or ()))
    return self._connection.execute(sqlite_sql, sqlite_params)
```

- [ ] **Step 4: Return dict-like rows**

Modify `SQLiteConnection.execute()` to return cursors with `sqlite3.Row`; then add helper in `studio/server/repository.py` if repository code expects plain dict mutation:

```python
def _plain_row(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)
```

Use `_plain_row(row)` only at repository boundaries where rows are mutated before returning.

- [ ] **Step 5: Decode JSON text on read paths that expect lists/dicts**

Add to `studio/server/repository.py`:

```python
import json


def _json_value(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return fallback
```

Use `_json_value(row.get("tags"), [])`, `_json_value(row.get("data"), {})`, and equivalent calls in existing row-shaping helpers instead of returning raw text.

- [ ] **Step 6: Run JSON round-trip test**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py::test_sqlite_json_fields_round_trip -q
```

Expected: pass.

- [ ] **Step 7: Run focused Postgres repository tests**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_workspaces.py studio/server/test_projects.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add studio/server/db_backends.py studio/server/repository.py studio/server/test_sqlite_backend.py
git commit -m "Normalize Studio JSON fields across database backends"
```

## Task 6: Prove SQLite API Startup And Snapshot Import

**Files:**
- Modify: `studio/server/test_sqlite_backend.py`
- Test: `studio/server/test_project_snapshots.py`

- [ ] **Step 1: Add SQLite TestClient smoke test**

Append to `studio/server/test_sqlite_backend.py`:

```python
from fastapi.testclient import TestClient
from studio.server.app import app


def test_sqlite_api_starts_and_lists_projects(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "studio.sqlite"
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDIO_SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv("STUDIO_SEED_SHOWCASES", "1")
    db.close_pool()
    db.set_database_url(f"sqlite:///{sqlite_path}")
    try:
        with TestClient(app) as client:
            health = client.get("/api/health")
            assert health.status_code == 200
            projects = client.get("/api/projects")
            assert projects.status_code == 200
            assert isinstance(projects.json(), list)
            assert any(project["id"] for project in projects.json())
    finally:
        db.close_pool()
```

- [ ] **Step 2: Run test and verify failure or pass**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py::test_sqlite_api_starts_and_lists_projects -q
```

Expected: pass after Tasks 1-5. If it fails, fix only backend portability issues surfaced by the traceback, then rerun this exact test.

- [ ] **Step 3: Add snapshot import assertion**

Append to `studio/server/test_sqlite_backend.py`:

```python
def test_sqlite_showcase_snapshot_import_is_idempotent(monkeypatch, tmp_path):
    sqlite_path = tmp_path / "studio.sqlite"
    monkeypatch.setenv("STUDIO_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDIO_SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv("STUDIO_SEED_SHOWCASES", "1")
    db.close_pool()
    db.set_database_url(f"sqlite:///{sqlite_path}")
    try:
        with TestClient(app) as client:
            first = client.get("/api/projects").json()
        db.close_pool()
        with TestClient(app) as client:
            second = client.get("/api/projects").json()
        assert sorted(project["id"] for project in first) == sorted(project["id"] for project in second)
    finally:
        db.close_pool()
```

- [ ] **Step 4: Run SQLite API smoke tests**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py -q
```

Expected: pass.

- [ ] **Step 5: Run existing snapshot tests against Postgres**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_project_snapshots.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add studio/server/test_sqlite_backend.py
git commit -m "Verify Studio SQLite API startup and snapshots"
```

## Task 7: Add Desktop API Dev Command And Documentation

**Files:**
- Create: `studio/scripts/start-desktop-api.sh`
- Modify: `studio/README.md`

- [ ] **Step 1: Add desktop API launcher script**

Create `studio/scripts/start-desktop-api.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="${ANIP_STUDIO_DESKTOP_DATA_DIR:-$HOME/.anip/studio}"
SQLITE_PATH="${STUDIO_SQLITE_PATH:-$DATA_DIR/studio.sqlite}"
PORT="${STUDIO_DESKTOP_API_PORT:-8100}"

mkdir -p "$DATA_DIR"

export STUDIO_MODE=desktop
export STUDIO_DB_BACKEND=sqlite
export STUDIO_SQLITE_PATH="$SQLITE_PATH"
export STUDIO_SEED_SHOWCASES="${STUDIO_SEED_SHOWCASES:-1}"
export STUDIO_READ_ONLY="${STUDIO_READ_ONLY:-0}"
export STUDIO_RUN_MIGRATIONS="${STUDIO_RUN_MIGRATIONS:-1}"

cd "$REPO_ROOT"
exec ./.venv/bin/uvicorn studio.server.app:app --host 127.0.0.1 --port "$PORT"
```

- [ ] **Step 2: Make script executable**

Run:

```bash
cd /Users/samirski/Development/ANIP
chmod +x studio/scripts/start-desktop-api.sh
```

Expected: command exits with status 0.

- [ ] **Step 3: Document desktop API preview**

Add this section to `studio/README.md` after “Full Studio Product (Docker Compose)”:

```markdown
## Desktop API Preview

The desktop storage foundation can run Studio API with a local SQLite database.
This is the backend mode intended for the future macOS desktop app.

```bash
studio/scripts/start-desktop-api.sh

# API: http://127.0.0.1:8100
# Data: ~/.anip/studio/studio.sqlite
```

This preview starts only the API. The desktop shell and packaged web UI are a
separate milestone. Docker Compose remains the supported full-product local
mode until the desktop shell is released.
```
```

- [ ] **Step 4: Run launcher smoke**

Run:

```bash
cd /Users/samirski/Development/ANIP
ANIP_STUDIO_DESKTOP_DATA_DIR=/tmp/anip-studio-desktop-smoke STUDIO_DESKTOP_API_PORT=8118 studio/scripts/start-desktop-api.sh
```

Expected: uvicorn starts and logs that it is listening on `http://127.0.0.1:8118`. Stop it with `Ctrl-C`.

- [ ] **Step 5: Run README command path check**

Run:

```bash
cd /Users/samirski/Development/ANIP
test -x studio/scripts/start-desktop-api.sh
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add studio/scripts/start-desktop-api.sh studio/README.md
git commit -m "Document Studio desktop API preview"
```

## Task 8: Add CI SQLite Lane

**Files:**
- Modify: `.github/workflows/ci-studio.yml`
- Test: GitHub Actions plus local command

- [ ] **Step 1: Add local command to verify SQLite lane**

Run locally first:

```bash
cd /Users/samirski/Development/ANIP
STUDIO_DB_BACKEND=sqlite STUDIO_SQLITE_PATH=/tmp/anip-studio-ci.sqlite ./.venv/bin/pytest studio/server/test_sqlite_backend.py -q
```

Expected: pass.

- [ ] **Step 2: Add CI job step**

In `.github/workflows/ci-studio.yml`, add this step after backend dependency installation and before Docker image build:

```yaml
      - name: Run Studio SQLite backend tests
        env:
          STUDIO_DB_BACKEND: sqlite
          STUDIO_SQLITE_PATH: /tmp/anip-studio-ci.sqlite
        run: ./.venv/bin/pytest studio/server/test_sqlite_backend.py -q
```

If the workflow installs backend dependencies in a path-specific virtualenv, use the exact pytest command already used by the workflow and add only the environment variables above.

- [ ] **Step 3: Run workflow-equivalent local tests**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py studio/server/test_project_snapshots.py -q
npm --prefix studio run build
```

Expected: tests pass and Studio frontend builds.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci-studio.yml
git commit -m "Add Studio SQLite backend CI coverage"
```

## Task 9: Final Verification And PR

**Files:**
- All files changed by Tasks 1-8

- [ ] **Step 1: Run focused backend verification**

Run:

```bash
cd /Users/samirski/Development/ANIP
./.venv/bin/pytest studio/server/test_sqlite_backend.py studio/server/test_project_snapshots.py studio/server/test_workspaces.py studio/server/test_projects.py -q
```

Expected: pass.

- [ ] **Step 2: Run Studio frontend build**

Run:

```bash
cd /Users/samirski/Development/ANIP/studio
npm run build
```

Expected: build completes successfully.

- [ ] **Step 3: Run Docker/Postgres smoke**

Run:

```bash
cd /Users/samirski/Development/ANIP
studio/scripts/smoke-compose.sh
```

Expected: smoke passes and confirms read-only Docker/Postgres behavior is unchanged.

- [ ] **Step 4: Check git status**

Run:

```bash
cd /Users/samirski/Development/ANIP
git status --short
```

Expected: only intentional files are modified. `.playwright-mcp/` may appear untracked and must not be committed.

- [ ] **Step 5: Push branch**

```bash
git push -u origin studio-desktop-sqlite-foundation
```

- [ ] **Step 6: Open PR**

```bash
gh pr create \
  --base main \
  --head studio-desktop-sqlite-foundation \
  --title "Add Studio SQLite desktop storage foundation" \
  --body "## Summary
- Add SQLite database backend mode for Studio API
- Add SQLite migrations and backend compatibility helpers
- Add desktop API preview script
- Add SQLite test coverage for startup and showcase snapshots

## Verification
- ./.venv/bin/pytest studio/server/test_sqlite_backend.py studio/server/test_project_snapshots.py studio/server/test_workspaces.py studio/server/test_projects.py -q
- npm run build (studio)
- studio/scripts/smoke-compose.sh

Refs #218"
```

- [ ] **Step 7: Watch PR checks**

```bash
gh pr checks --watch
```

Expected: all required checks pass.

## Self-Review

Spec coverage:

- SQLite/local storage mode: Tasks 1-6.
- Showcase snapshot preload: Task 6.
- Dev startup command: Task 7.
- CI coverage: Task 8.
- Docker/Postgres preservation: Tasks 6 and 9.

Deferred by design:

- Tauri/Electron desktop shell.
- macOS signing/notarization.
- first-run desktop setup UI.
- platform secure secret storage.

Those require the SQLite API foundation delivered by this plan.
