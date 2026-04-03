# Design V3 Slice 4: Architecture Design — Projects, Coherence, and Local Persistence

## Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | PostgreSQL via Docker Compose | Correctness, constraints, JSONB, query power, future extensibility |
| Where persistence lives | Python sidecar | Already exists, already owns validation, one backend |
| API surface | REST endpoints on the same sidecar | No new processes, no new ports |
| DB layer | `psycopg` (v3) + `psycopg_pool` + thin repository module | Modern Postgres driver; pooling via separate `psycopg_pool` package |
| Migration strategy | Schema-version table + forward-only SQL migrations | Simple, auditable, no framework dependency |
| Current packs | Become importable seed data | `packs.generated.ts` stays for inspect-only embedded builds; DB is the primary store for Design mode |
| Import/export format | JSON project export + single-artifact import (ZIP bundle deferred) | Artifacts remain the portable format; full bundle round-trip comes later |
| Vocabulary registry | Project-local table + global defaults | Simplest model that gives grounding |
| Frontend transition | New `api.ts` functions → same `/api/*` prefix → reactive store reads from API | Incremental — existing guided flows keep working |

---

## 1. Infrastructure

### Docker Compose

Studio's `docker-compose.yml` adds a Postgres service:

```yaml
version: '3.8'
services:
  studio-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: anip_studio
      POSTGRES_USER: anip
      POSTGRES_PASSWORD: anip
    ports:
      - "5432:5432"
    volumes:
      - studio-pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U anip -d anip_studio"]
      interval: 2s
      timeout: 5s
      retries: 10

  studio-api:
    build:
      context: ..
      dockerfile: studio/server/Dockerfile
    environment:
      DATABASE_URL: postgresql://anip:anip@studio-db:5432/anip_studio
    ports:
      - "8100:8100"
    depends_on:
      studio-db:
        condition: service_healthy

  studio-web:
    build:
      context: ..
      dockerfile: studio/Dockerfile.standalone
    ports:
      - "8080:8080"
    depends_on:
      - studio-api

volumes:
  studio-pgdata:
```

The sidecar reads `DATABASE_URL` from the environment. For local development: `DATABASE_URL=postgresql://anip:anip@localhost:5432/anip_studio`.

---

## 2. Database Schema

All tables live in the `anip_studio` Postgres database.

### Core Tables

```sql
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Projects
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    domain TEXT NOT NULL DEFAULT '',
    labels JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_projects_domain ON projects(domain);
CREATE INDEX idx_projects_updated ON projects(updated_at DESC);

-- Requirements sets
CREATE TABLE requirements_sets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_requirements_project ON requirements_sets(project_id);

-- Scenarios
CREATE TABLE scenarios (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_scenarios_project ON scenarios(project_id);

-- Proposals
CREATE TABLE proposals (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requirements_id TEXT NOT NULL REFERENCES requirements_sets(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_proposals_project ON proposals(project_id);
CREATE INDEX idx_proposals_requirements ON proposals(requirements_id);

-- Evaluations
CREATE TABLE evaluations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    proposal_id TEXT NOT NULL REFERENCES proposals(id),
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    requirements_id TEXT NOT NULL REFERENCES requirements_sets(id),
    result TEXT NOT NULL CHECK (result IN ('HANDLED', 'PARTIAL', 'REQUIRES_GLUE')),
    source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('live_validation', 'imported', 'manual')),
    data JSONB NOT NULL,
    input_snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_evaluations_project ON evaluations(project_id);
CREATE INDEX idx_evaluations_proposal ON evaluations(proposal_id);
CREATE INDEX idx_evaluations_scenario ON evaluations(scenario_id);

-- Vocabulary entries
CREATE TABLE vocabulary (
    id SERIAL PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    value TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'custom' CHECK (origin IN ('canonical', 'project', 'custom')),
    description TEXT NOT NULL DEFAULT '',
    UNIQUE(project_id, category, value)
);

-- Partial unique index for global vocabulary (project_id IS NULL).
-- Postgres UNIQUE constraints treat NULLs as distinct, so the table-level
-- UNIQUE(project_id, category, value) does not prevent duplicate global entries.
-- This index closes that gap.
CREATE UNIQUE INDEX idx_vocabulary_global_unique
    ON vocabulary(category, value) WHERE project_id IS NULL;

CREATE INDEX idx_vocabulary_category ON vocabulary(category);
CREATE INDEX idx_vocabulary_project ON vocabulary(project_id);
```

### Design Notes

- **JSONB for artifact data.** Postgres JSONB gives indexable, queryable JSON storage. The `data` and `input_snapshot` columns store full artifacts as JSONB. This enables future queries like "find all scenarios with side_effect = 'irreversible'" without repository changes.
- **JSONB for labels.** Project labels are stored as a JSONB array, queryable with `@>` operator.
- **TIMESTAMPTZ for timestamps.** Proper timezone-aware timestamps, not SQLite's text-based datetime.
- **SERIAL for vocabulary IDs.** Auto-incrementing integer, Postgres-native.
- **Indexes on all foreign keys and common query patterns.** Postgres does not auto-index FKs like some databases.
- **Foreign keys enforced by default.** Postgres always enforces FKs — no pragma needed.
- **Project coherence is enforced at the repository layer (Slice 4).** Every create and update operation must verify that all referenced records share the same `project_id`. See Section 3.1 for the full rules. This is a pragmatic choice for Slice 4 — later slices may push this guarantee into the DB itself via composite foreign keys (e.g. `REFERENCES proposals(id, project_id)`) or constraint triggers, if the repository-level check proves insufficient or too easy to bypass.
- **CASCADE on project delete** removes all child artifacts. Individual artifact deletion checks for dependent records first via repository logic.
- **`input_snapshot` on evaluations freezes the input artifacts.** Stored evaluations remain historically meaningful even after referenced artifacts are edited.
- **No revision table in Slice 4.** The `input_snapshot` approach is sufficient. Slice 5 can introduce proper revisions if automation needs them.
- **Vocabulary with NULL `project_id`** represents global canonical entries.

---

## 3. REST API Surface

All endpoints live under `/api/` on the existing sidecar (port 8100). Existing endpoints (`/api/health`, `/api/validate`) are unchanged.

### 3.1 Project Coherence Rules

The repository layer must enforce these rules on every create and update:

| Operation | Rule | Error |
|-----------|------|-------|
| Create proposal | `requirements_id` must belong to the same `project_id` | `422` |
| Update proposal | If `requirements_id` changes, new value must belong to the same `project_id` | `422` |
| Create evaluation | `proposal_id`, `scenario_id`, and `requirements_id` must all belong to the same `project_id` | `422` |
| Import artifacts | All referenced IDs must resolve within the target project | `422` with error list |

These are hard failures. The repository raises `ProjectCoherenceError`, the API returns `422 Unprocessable Entity`.

### Projects

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `GET` | `/api/projects` | — | `Project[]` |
| `POST` | `/api/projects` | `{id, name, summary?, domain?, labels?}` | `Project` |
| `GET` | `/api/projects/{id}` | — | `Project` with artifact counts |
| `PUT` | `/api/projects/{id}` | `{name?, summary?, domain?, labels?}` | `Project` |
| `DELETE` | `/api/projects/{id}` | — | `204` (cascades all artifacts) |

### Requirements Sets

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `GET` | `/api/projects/{pid}/requirements` | — | `RequirementsSet[]` |
| `POST` | `/api/projects/{pid}/requirements` | `{id, title, data}` | `RequirementsSet` |
| `GET` | `/api/projects/{pid}/requirements/{id}` | — | `RequirementsSet` |
| `PUT` | `/api/projects/{pid}/requirements/{id}` | `{title?, status?, data?}` | `RequirementsSet` |
| `DELETE` | `/api/projects/{pid}/requirements/{id}` | — | `204` or `409` if proposals reference it |

### Scenarios

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `GET` | `/api/projects/{pid}/scenarios` | — | `Scenario[]` |
| `POST` | `/api/projects/{pid}/scenarios` | `{id, title, data}` | `Scenario` |
| `GET` | `/api/projects/{pid}/scenarios/{id}` | — | `Scenario` |
| `PUT` | `/api/projects/{pid}/scenarios/{id}` | `{title?, status?, data?}` | `Scenario` |
| `DELETE` | `/api/projects/{pid}/scenarios/{id}` | — | `204` or `409` if evaluations reference it |

### Proposals

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `GET` | `/api/projects/{pid}/proposals` | — | `Proposal[]` |
| `POST` | `/api/projects/{pid}/proposals` | `{id, title, requirements_id, data}` | `Proposal` |
| `GET` | `/api/projects/{pid}/proposals/{id}` | — | `Proposal` |
| `PUT` | `/api/projects/{pid}/proposals/{id}` | `{title?, status?, data?}` | `Proposal` |
| `DELETE` | `/api/projects/{pid}/proposals/{id}` | — | `204` or `409` if evaluations reference it |

### Evaluations

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `GET` | `/api/projects/{pid}/evaluations` | `?scenario_id=&proposal_id=` | `Evaluation[]` |
| `POST` | `/api/projects/{pid}/evaluations` | `{id, proposal_id, scenario_id, requirements_id, source?, data, input_snapshot}` | `Evaluation` |
| `GET` | `/api/projects/{pid}/evaluations/{id}` | — | `Evaluation` |
| `DELETE` | `/api/projects/{pid}/evaluations/{id}` | — | `204` |

### Vocabulary

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `GET` | `/api/vocabulary` | `?category=&project_id=` | `VocabularyEntry[]` (merges global + project) |
| `POST` | `/api/vocabulary` | `{project_id?, category, value, origin?, description?}` | `VocabularyEntry` |
| `DELETE` | `/api/vocabulary/{id}` | — | `204` |

### Import / Export

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `POST` | `/api/projects/{pid}/import` | `{artifacts: [{type, data}]}` | `{imported: count, errors: [...]}` |
| `GET` | `/api/projects/{pid}/export` | — | `{project, requirements, scenarios, proposals, evaluations}` |
| `POST` | `/api/seed` | — | Seeds DB from example packs (dev/demo only) |

### Delete Semantics

- **Project delete**: Cascades everything (all artifacts under it removed).
- **Requirements delete**: Fails with `409 Conflict` if any proposal references it.
- **Scenario delete**: Fails with `409` if any evaluation references it.
- **Proposal delete**: Fails with `409` if any evaluation references it.
- **Evaluation delete**: Always succeeds (leaf node).

### Validation vs. Evaluation Persistence

**`POST /api/validate` remains stateless.** Takes requirements/proposal/scenario, returns evaluation result, does not write to the DB.

**Saving an evaluation is explicit:**

1. User clicks "Run Validation" → `POST /api/validate` → live result
2. UI shows live result with "Live" badge
3. User chooses "Save to Project" → `POST /api/projects/{pid}/evaluations` with result + reference IDs + `source: 'live_validation'` + `input_snapshot`
4. Stored evaluation appears with "Stored" badge

**UI distinguishes live vs. stored:**

| State | Badge | Source |
|-------|-------|--------|
| Ad-hoc validation result | **Live** | Not in DB |
| Saved from live validation | **Stored** | `source: 'live_validation'` |
| Imported from YAML | **Stored** | `source: 'imported'` |

---

## 4. Sidecar Code Structure

```
studio/server/
├── app.py                    # FastAPI app — adds routers, startup hooks
├── db.py                     # Postgres connection pool, migration runner
├── models.py                 # Pydantic models for API request/response
├── repository.py             # Thin CRUD layer over Postgres (all SQL lives here)
├── routers/
│   ├── projects.py           # /api/projects/* routes
│   ├── artifacts.py          # /api/projects/{pid}/requirements/scenarios/proposals/evaluations
│   ├── vocabulary.py         # /api/vocabulary/* routes
│   └── import_export.py      # /api/projects/{pid}/import, /export, /seed
├── seed.py                   # Imports example packs into DB as seed projects
├── vocabulary_defaults.json  # Global canonical vocabulary entries
├── migrations/
│   └── 001_initial.sql       # Initial schema DDL
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── test_api.py               # Extended tests
```

### `db.py` — Connection Pool

```python
import os
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pathlib import Path

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://anip:anip@localhost:5432/anip_studio"
)
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_pool: ConnectionPool | None = None

def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            DATABASE_URL,
            kwargs={"row_factory": dict_row},
            min_size=2,
            max_size=10,
        )
    return _pool

def init_db():
    """Run unapplied migrations."""
    with get_pool().connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            "  version INTEGER PRIMARY KEY,"
            "  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()"
            ")"
        )
        applied = {r["version"] for r in conn.execute("SELECT version FROM schema_version").fetchall()}
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = int(sql_file.stem.split("_")[0])
            if version not in applied:
                conn.execute(sql_file.read_text())
                conn.execute("INSERT INTO schema_version (version) VALUES (%s)", (version,))
        conn.commit()
```

Repository functions use `with get_pool().connection() as conn:` to get a connection from the pool with automatic return on exit. No manual `get_connection`/`put_connection` needed.

### `repository.py` — Thin CRUD Layer

All SQL lives here. Functions use `psycopg` parameterized queries (`%s` placeholders, not `?`). JSONB columns are passed as `psycopg.types.json.Json(data)` or read directly as Python dicts (psycopg auto-deserializes JSONB).

---

## 5. Frontend Integration Strategy

Unchanged from the previous design. See Sections 4-7 of the original design for:
- Phase 1: API client expansion
- Phase 2: Store transition (project-store owns workspace; design/store owns drafts)
- Phase 3: Router transition
- Phase 4: Vocabulary integration
- Backward compatibility (inspect-only mode, sidecar-down fallback)

---

## 6. Vocabulary Registry

Unchanged. Global canonical defaults loaded from `vocabulary_defaults.json` on DB init. Project-local extensions via API. Three-tier chip appearance: canonical / project / custom.

---

## 7. Import / Export Model

Unchanged. JSON project export, single-artifact import, seed from example packs (one project per pack).

---

## 8. What This Design Does NOT Cover

- **Revision history**: No revision table. `input_snapshot` on evaluations suffices.
- **Multi-user / collaboration**: Single-user workspace.
- **Authentication**: No auth on the sidecar.
- **Agent-assisted authoring**: Slice 5 scope.
- **Cloud deployment**: Local Docker Compose only.
- **ZIP bundle import/export**: Deferred.
