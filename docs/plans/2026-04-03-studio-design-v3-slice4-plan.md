# Design V3 Slice 4: Projects, Coherence, and Local Persistence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project-backed workspace model with PostgreSQL persistence, cross-artifact referential integrity, vocabulary grounding, and a project-first UI to ANIP Studio Design mode.

**Architecture:** Two-phase build — backend first (Python sidecar: PostgreSQL via Docker Compose, repository, REST API, seed), then frontend (Vue: API client, store transition, project views, vocabulary UI, grounding signals). Docker Compose adds a Postgres 16 service. The sidecar connects via `DATABASE_URL` env var using `psycopg` (v3) + `psycopg_pool`. 6 tables (projects, requirements_sets, scenarios, proposals, evaluations, vocabulary) with JSONB for artifact data, TIMESTAMPTZ for timestamps, and proper indexes. All CRUD goes through a thin `repository.py` that enforces referential integrity and project coherence. The Vue frontend transitions from static `packs.generated.ts` to API-backed project state while preserving existing guided flows unchanged.

**Tech Stack:** Python 3.12, FastAPI, psycopg (v3) + psycopg_pool, Pydantic, PostgreSQL 16; Vue 3, TypeScript, existing design store

**Reference:** Architecture design at `/Users/samirski/Development/ANIP/docs/plans/2026-04-03-studio-design-v3-slice4-design.md`

---

## State Ownership Rules

Two stores, one boundary. Workers must follow these rules exactly:

### `project-store.ts` owns:
- **Workspace navigation:** project list, active project, artifact record lists (requirements, scenarios, proposals, evaluations), vocabulary
- **Active design context:** `activeRequirementsId` and `activeProposalId` — the requirements/proposal pair currently selected for validation. These must be set before an evaluation can be saved.
- **Loading/error/availability state** for the project API

### `design/store.ts` owns:
- **Draft/edit state** for the currently opened artifact: `draftRequirements`, `draftScenario`, `draftDeclaredSurfaces`, `editState`, `validationErrors`
- **Guided mode state:** `requirementsMode`, `guidedAnswers`, `completenessHints`, `scenarioMode`, `guidedScenarioAnswers`, `scenarioHints`, `showFieldMappings`
- **Live validation state:** `liveEvaluation`, `validating`, `validationError`, `apiAvailable`

### Handoff: `openArtifactForEditing()`

When a user navigates to an artifact view, the project store provides the record. The view calls a handoff function that hydrates the design store from the record's `.data` field:

```typescript
// In project-store.ts
export function openArtifactForEditing(
  artifactType: 'requirements' | 'scenario' | 'proposal',
  record: ArtifactRecord | ProposalRecord,
): void {
  // Writes the record's .data into the design store so
  // existing draft/edit/guided/validation flows work unchanged.
  // The design store does NOT know about projects — it only
  // sees the artifact content.
}
```

The design store's `startEditing()`, `discardEdits()`, `validateDraft()`, and all guided flows remain **unchanged**. They operate on the draft data without knowing it came from a project record.

### Evaluation Context

Before a validation result can be saved to the project, the project store must have:
- `activeProject.id` — which project
- `activeRequirementsId` — which requirements set
- `activeProposalId` — which proposal (set when the user navigates to proposal or evaluation views)
- The scenario ID comes from the current scenario being evaluated

These are encoded in the project store, not in the route. The route identifies which artifact to view; the project store tracks the broader evaluation context.

### Active Context Reset Rules

`activeRequirementsId` and `activeProposalId` must be cleared or revalidated on these events:

| Event | Action |
|-------|--------|
| `loadProject(newId)` called (switching projects) | Clear both to `null`, then auto-select if exactly one active record exists |
| `clearProject()` called | Clear both to `null` |
| Requirements set deleted via API | If deleted ID matches `activeRequirementsId`, reset it to `null` |
| Proposal deleted via API | If deleted ID matches `activeProposalId`, reset it to `null` |
| Artifact list refreshed after any mutation | Revalidate: if the active ID no longer exists in the list, reset to `null` |

Workers must implement these resets in the project store functions. The Save to Project button in EvaluationView checks for `null` and shows "Select a requirements set and proposal first" instead of saving.

### Read-Only Fallback

When the sidecar is unavailable (`projectStore.dbAvailable === false`):

**Routing:** The router keeps the legacy pack-based routes alongside the new project routes. Both route sets exist at all times — the views decide which data source to use:

- `/design` — `ProjectListView` checks `projectStore.dbAvailable`. If true, loads from API. If false, renders `packs.generated.ts` as read-only demo cards.
- `/design/packs/:packId` — Legacy read-only route for pack-based artifact viewing. Always renders from `packs.generated.ts`. Used as navigation target when sidecar is down.
- `/design/projects/:pid/*` — Project routes. If sidecar is down, these redirect to `/design` with a "Sidecar unavailable" banner.

This means the router in Task 10 must keep `/design/packs/:packId` as a route (not redirect it away). The existing artifact views (`RequirementsView`, `ScenarioDetailView`, etc.) support both route shapes: when `route.params.projectId` exists, load from project API; when `route.params.packId` exists, load from `packs.generated.ts`.

**UI:** A banner shows "Sidecar unavailable — read-only mode" at the top of `ProjectListView` when in fallback mode. Guided flows and schema validation still work (client-side only). Editing and save are disabled.

### Import/Export Scope

Slice 4 implements:
- `GET /api/projects/{pid}/export` — returns the full project object graph as JSON (not a ZIP bundle)
- `POST /api/projects/{pid}/import` — imports individual artifacts into an existing project
- `POST /api/seed` — bootstraps from example packs

Full project-bundle round-trip (ZIP packaging, manifest, restore with preserved IDs) is deferred to a later slice.

---

## File Structure

### Phase 1: Backend (Python sidecar)

#### New Files

| File | Responsibility |
|------|---------------|
| `studio/server/db.py` | Postgres connection pool (`psycopg_pool`), migration runner |
| `studio/server/repository.py` | All SQL CRUD + referential integrity + project coherence checks |
| `studio/server/models.py` | Pydantic request/response models for all API endpoints |
| `studio/server/seed.py` | Import example packs into DB as seed projects |
| `studio/server/vocabulary_defaults.json` | Global canonical vocabulary entries |
| `studio/server/migrations/001_initial.sql` | Initial schema DDL |
| `studio/server/routers/__init__.py` | Empty package init |
| `studio/server/routers/projects.py` | `/api/projects/*` routes |
| `studio/server/routers/artifacts.py` | `/api/projects/{pid}/requirements/*`, `/scenarios/*`, `/proposals/*`, `/evaluations/*` routes |
| `studio/server/routers/vocabulary.py` | `/api/vocabulary/*` routes |
| `studio/server/routers/import_export.py` | `/api/projects/{pid}/import`, `/export`, `/seed` routes |
| `studio/server/test_projects.py` | Tests for project CRUD, referential integrity, coherence |
| `studio/server/test_artifacts.py` | Tests for artifact CRUD, delete semantics, evaluations |
| `studio/server/test_vocabulary.py` | Tests for vocabulary CRUD, merge, global+project |
| `studio/server/test_import_export.py` | Tests for import, export, seed, round-trip |

#### Modified Files

| File | Changes |
|------|---------|
| `studio/server/app.py` | Add router includes, DB init on startup via lifespan |

### Phase 2: Frontend (Vue)

#### New Files

| File | Responsibility |
|------|---------------|
| `studio/src/design/project-api.ts` | CRUD API functions for projects, artifacts, vocabulary, import/export |
| `studio/src/design/project-types.ts` | TypeScript types for project records, API responses |
| `studio/src/design/project-store.ts` | Project-oriented reactive state, active design context (requirements/proposal selection), artifact handoff to design store |
| `studio/src/views/ProjectListView.vue` | Design home: project list with create/seed |
| `studio/src/views/ProjectOverviewView.vue` | Project dashboard with artifact lists, counts, navigation |

#### Modified Files

| File | Changes |
|------|---------|
| `studio/src/App.vue` | Rewrite Design sidebar nav from pack-based to project-based paths; add active design context display |
| `studio/src/router.ts` | Add project routes, re-route artifact views under `/design/projects/:pid/` |
| `studio/src/design/store.ts` | Add artifact loading from project API |
| `studio/src/views/RequirementsView.vue` | Read project/artifact IDs from route params |
| `studio/src/views/ScenarioDetailView.vue` | Same route param transition |
| `studio/src/views/ProposalView.vue` | Same route param transition |
| `studio/src/views/EvaluationView.vue` | Add "Save to Project" button, live vs stored badges |
| `studio/src/design/components/SuggestionChips.vue` | Add origin badges (canonical/project/custom) |

---

## Phase 1: Backend

### Task 1: Database Module and Migration

Create the Postgres connection pool, migration runner, and initial schema migration. Also update Docker Compose and requirements.txt.

**Files:**
- Create: `studio/server/db.py`
- Create: `studio/server/migrations/001_initial.sql`
- Modify: `studio/docker-compose.yml` (this is the existing file — update in place)
- Modify: `studio/server/requirements.txt`

- [ ] **Step 1: Create the migrations directory**

```bash
mkdir -p /Users/samirski/Development/ANIP/studio/server/migrations
```

- [ ] **Step 2: Write the initial schema migration**

Write `studio/server/migrations/001_initial.sql` with Postgres DDL for all 6 domain tables: `projects`, `requirements_sets`, `scenarios`, `proposals`, `evaluations` (with `input_snapshot JSONB NOT NULL` and `source` columns), `vocabulary`. Use `JSONB` for data/labels/input_snapshot columns, `TIMESTAMPTZ` for timestamps, `SERIAL` for vocabulary IDs. Add indexes on all foreign keys and common query patterns. Add `CREATE UNIQUE INDEX idx_vocabulary_global_unique ON vocabulary(category, value) WHERE project_id IS NULL` for global vocabulary deduplication.

Full DDL is specified in the architecture design Section 2.

- [ ] **Step 3: Write the database module**

Write `studio/server/db.py` with:
- `DATABASE_URL` from env var, defaulting to `postgresql://anip:anip@localhost:5432/anip_studio`
- `MIGRATIONS_DIR` pointing to `migrations/` directory
- `get_pool()` returning a `psycopg_pool.ConnectionPool` (lazy singleton, `min_size=2`, `max_size=10`, `kwargs={"row_factory": dict_row}`)
- `init_db()` using `with get_pool().connection() as conn:` to create `schema_version` table if not exists, read migration files, apply unapplied ones in version order

Repository functions use `with get_pool().connection() as conn:` for automatic connection return.

- [ ] **Step 4: Update docker-compose.yml**

Update `studio/docker-compose.yml` (the existing file) to add:
- `studio-db` service: `postgres:16-alpine` with healthcheck (`pg_isready`), named volume
- `studio-api` service: `depends_on: studio-db: condition: service_healthy`, `DATABASE_URL` env var

Full Compose spec in architecture design Section 1.

- [ ] **Step 5: Update requirements.txt**

Add `psycopg[binary]>=3.1.0` and `psycopg_pool>=3.1.0` to `studio/server/requirements.txt`.

- [ ] **Step 6: Verify the DB module imports**

Run: `cd /Users/samirski/Development/ANIP && python3 -c "from studio.server.db import get_pool, init_db; print('OK')"`
Expected: `OK` (pool creation will fail without Postgres running — that's fine, just verifying imports)

- [ ] **Step 7: Commit**

```bash
git add studio/server/db.py studio/server/migrations/ studio/server/requirements.txt studio/docker-compose.yml
git commit -m "feat(studio-api): add Postgres database module, migration, and Docker Compose"
```

---

### Task 2: Pydantic Models

Define all request/response models for the API.

**Files:**
- Create: `studio/server/models.py`

- [ ] **Step 1: Write the models**

Write `studio/server/models.py` with Pydantic BaseModel classes:
- `CreateProject(id, name, summary='', domain='', labels=[])`
- `UpdateProject(name?, summary?, domain?, labels?)`
- `ProjectOut(id, name, summary, domain, labels, created_at, updated_at)`
- `ProjectDetail(ProjectOut + requirements_count, scenarios_count, proposals_count, evaluations_count)`
- `CreateArtifact(id, title, data: dict)`
- `UpdateArtifact(title?, status?, data?)`
- `ArtifactOut(id, project_id, title, status, data, created_at, updated_at)`
- `CreateProposal(id, title, requirements_id, data: dict)`
- `ProposalOut(ArtifactOut + requirements_id)`
- `CreateEvaluation(id, proposal_id, scenario_id, requirements_id, source='manual', data: dict, input_snapshot: dict)`
- `EvaluationOut(id, project_id, proposal_id, scenario_id, requirements_id, result, source, data, input_snapshot, created_at)`
- `CreateVocabulary(project_id?, category, value, origin='custom', description='')`
- `VocabularyOut(id, project_id, category, value, origin, description)`
- `ImportArtifact(type, data: dict)`, `ImportRequest(artifacts: list)`, `ImportResult(imported, errors)`

- [ ] **Step 2: Commit**

```bash
git add studio/server/models.py
git commit -m "feat(studio-api): add Pydantic models for workspace API"
```

---

### Task 3: Repository Layer

All SQL CRUD + referential integrity + project coherence. The largest backend task.

**Files:**
- Create: `studio/server/repository.py`

- [ ] **Step 1: Write the repository**

Write `studio/server/repository.py` with:

**Exceptions:** `NotFoundError(entity, entity_id)`, `ReferentialIntegrityError(entity, entity_id, blocked_by, refs)`, `ProjectCoherenceError(message)`

**Helpers:**
- `assert_same_project(conn, project_id, **refs)` — for each ref (requirements_id, scenario_id, proposal_id), looks up the record's project_id and raises `ProjectCoherenceError` if it doesn't match. This is repository-enforced in Slice 4; later slices may push this into DB-level composite constraints or triggers.

Note: With `psycopg` + `dict_row`, rows are already dicts and JSONB columns are auto-deserialized. No manual `_row_to_dict` conversion needed.

**Project CRUD:** `list_projects`, `get_project`, `get_project_detail` (with counts), `create_project`, `update_project`, `delete_project`

**Generic artifact CRUD** (shared for requirements_sets and scenarios): `_list_artifacts`, `_get_artifact`, `_create_artifact`, `_update_artifact`, `_delete_artifact` (with optional blocked-by check). Public wrappers: `list_requirements`/`get_requirements`/`create_requirements`/`update_requirements`/`delete_requirements` (blocked by proposals), same for scenarios (blocked by evaluations).

**Proposal CRUD:** `list_proposals`, `get_proposal`, `create_proposal` (calls `assert_same_project` for requirements_id), `update_proposal`, `delete_proposal` (blocked by evaluations)

**Evaluation CRUD:** `list_evaluations` (with optional scenario_id/proposal_id filters), `get_evaluation`, `create_evaluation` (calls `assert_same_project` for all three refs, extracts `result` from `data.evaluation.result`), `delete_evaluation`

**Vocabulary:** `list_vocabulary` (merges global NULL project_id + project-local), `create_vocabulary`, `delete_vocabulary`, `load_vocabulary_defaults(conn, defaults_path)` (loads from JSON file, skips duplicates)

Full implementation details and example code in the architecture design Section 2.1 and Section 3.

- [ ] **Step 2: Commit**

```bash
git add studio/server/repository.py
git commit -m "feat(studio-api): add repository layer with CRUD, referential integrity, and project coherence"
```

---

### Task 4: Vocabulary Defaults and Seed Module

**Files:**
- Create: `studio/server/vocabulary_defaults.json`
- Create: `studio/server/seed.py`

- [ ] **Step 1: Write vocabulary defaults**

Write `studio/server/vocabulary_defaults.json` with canonical entries for categories: `context_key` (capability, side_effect, expected_cost, budget_limit, permissions_state, task_id, risk, token_scope), `behavior` (do_not_execute, preserve_task_identity, preserve_parent_invocation_lineage, produce_audit_entry, explain_budget_conflict, explain_authority_gap, prefer_escalation_or_replan_over_blind_retry), `anip_support` (cost_visibility, side_effect_visibility, structured_failure, permission_discovery, task_id_support, parent_invocation_id_support, audit_queryability, resolution_guidance, cross_service_verification_guidance). Each with `origin: "canonical"` and a description.

- [ ] **Step 2: Write the seed module**

Write `studio/server/seed.py` with `seed_from_examples(conn)` that:
- Reads `tooling/examples/` directory
- Creates one project per pack directory (project ID = directory name)
- Derives project name from `requirements.system.name`, domain from `requirements.system.domain`
- Creates requirements, scenario, proposal, evaluation records with generated IDs (`req-{pack}`, `scn-{pack}`, `prop-{pack}`, `eval-{pack}`)
- Sets cross-references (proposal.requirements_id, evaluation refs)
- Evaluation records include `input_snapshot` frozen from imported artifacts and `source: 'imported'`
- Skips existing projects (idempotent)
- Returns `{created_projects, skipped}`

- [ ] **Step 3: Commit**

```bash
git add studio/server/vocabulary_defaults.json studio/server/seed.py
git commit -m "feat(studio-api): add canonical vocabulary defaults and seed module"
```

---

### Task 5: API Routers

Wire all REST endpoints.

**Files:**
- Create: `studio/server/routers/__init__.py`
- Create: `studio/server/routers/projects.py`
- Create: `studio/server/routers/artifacts.py`
- Create: `studio/server/routers/vocabulary.py`
- Create: `studio/server/routers/import_export.py`
- Modify: `studio/server/app.py`

- [ ] **Step 1: Create routers package and write all router files**

**`routers/projects.py`:** CRUD for `/api/projects` and `/api/projects/{id}`. Translates `NotFoundError` to 404, duplicate IDs to 409.

**`routers/artifacts.py`:** CRUD for requirements, scenarios, proposals, evaluations under `/api/projects/{pid}/*`. Uses a shared error-handling pattern that translates `NotFoundError` to 404, `ReferentialIntegrityError` to 409 (with blocking refs in body), `ProjectCoherenceError` to 422, and UNIQUE constraint violations to 409.

**`routers/vocabulary.py`:** GET (with category/project_id query filters), POST, DELETE for `/api/vocabulary`.

**`routers/import_export.py`:** POST `/api/projects/{pid}/import` (validates and inserts artifacts), GET `/api/projects/{pid}/export` (returns project object graph as JSON), POST `/api/seed` (calls `seed_from_examples`).

Full endpoint specs in architecture design Section 2.

- [ ] **Step 2: Update app.py**

Replace `studio/server/app.py` to:
- Add `lifespan` async context manager that calls `init_db()` and `load_vocabulary_defaults(...)` on startup using the connection pool
- Keep existing `/api/validate` and `/api/health` endpoints unchanged
- Include all 4 routers

- [ ] **Step 3: Verify the sidecar starts**

Requires Postgres running (via Docker Compose or locally):
Run: `cd /Users/samirski/Development/ANIP/studio && docker compose up studio-db -d`
Then: `cd /Users/samirski/Development/ANIP && DATABASE_URL=postgresql://anip:anip@localhost:5432/anip_studio python3 -m uvicorn studio.server.app:app --host 127.0.0.1 --port 9100 &`
Then: `curl -s http://127.0.0.1:9100/api/health && curl -s http://127.0.0.1:9100/api/projects`
Expected: `{"status":"ok"}` and `[]`
Cleanup: kill the server

- [ ] **Step 4: Commit**

```bash
git add studio/server/routers/ studio/server/app.py
git commit -m "feat(studio-api): add workspace API routers and wire into FastAPI app"
```

---

### Task 6: Backend Tests

Comprehensive tests for all backend functionality.

**Files:**
- Create: `studio/server/test_projects.py`
- Create: `studio/server/test_artifacts.py`
- Create: `studio/server/test_vocabulary.py`
- Create: `studio/server/test_import_export.py`

- [ ] **Step 1: Write project tests**

Test: list empty, create, get (with counts), update, duplicate 409, missing 404, cascade delete removes all child artifacts.

- [ ] **Step 2: Write artifact tests**

Test: CRUD for requirements/scenarios, create proposal with valid requirements_id, create proposal with cross-project requirements_id (422), delete requirements blocked by proposal (409), create evaluation with full refs, create evaluation with cross-project ref (422), delete evaluation succeeds (leaf), delete scenario blocked by evaluation (409), evaluation has input_snapshot.

- [ ] **Step 3: Write vocabulary tests**

Test: global canonical entries seeded on startup, create project-local entry, merged vocabulary returns both global and project, delete vocabulary entry.

- [ ] **Step 4: Write import/export tests**

Test: seed creates projects (one per pack), seed is idempotent, export returns project object graph as JSON, import artifacts into a project.

- [ ] **Step 5: Run all backend tests**

Tests require Postgres running. Ensure `studio-db` is up via Docker Compose first.
Run: `cd /Users/samirski/Development/ANIP/studio && docker compose up studio-db -d`
Then: `cd /Users/samirski/Development/ANIP && DATABASE_URL=postgresql://anip:anip@localhost:5432/anip_studio python3 -m pytest studio/server/ -v 2>&1 | tail -30`
Expected: All pass

Each test file should use a setup that creates a clean test schema or truncates tables before running, so tests are isolated.

- [ ] **Step 6: Fix any failures**

- [ ] **Step 7: Commit**

```bash
git add studio/server/test_projects.py studio/server/test_artifacts.py studio/server/test_vocabulary.py studio/server/test_import_export.py
git commit -m "test(studio-api): add comprehensive backend tests for workspace API"
```

---

## Phase 2: Frontend

### Task 7: Frontend Types and API Client

**Files:**
- Create: `studio/src/design/project-types.ts`
- Create: `studio/src/design/project-api.ts`

- [ ] **Step 1: Write project types**

TypeScript interfaces: `ProjectSummary`, `ProjectDetail` (extends with counts), `ArtifactRecord`, `ProposalRecord` (extends with requirements_id), `EvaluationRecord` (with source, input_snapshot), `VocabularyEntry` (with origin), `CreateProject`, `ImportResult`.

- [ ] **Step 2: Write the project API client**

Thin fetch wrapper `api<T>(path, options)` that handles JSON serialization, error responses, and 204 no-content. Export functions for all CRUD operations: `listProjects`, `getProject`, `createProject`, `updateProject`, `deleteProject`, `listRequirements`, `getRequirements`, `createRequirements`, `updateRequirements`, `deleteRequirements`, same for scenarios/proposals, `listEvaluations` (with filters), `createEvaluation`, `deleteEvaluation`, `listVocabulary` (with filters), `createVocabularyEntry`, `deleteVocabularyEntry`, `importArtifacts`, `exportProject`, `seedDatabase`.

- [ ] **Step 3: Verify**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`

- [ ] **Step 4: Commit**

```bash
git add studio/src/design/project-types.ts studio/src/design/project-api.ts
git commit -m "feat(studio): add project types and API client for workspace"
```

---

### Task 8: Project Store

Reactive project state that loads from the API.

**Files:**
- Create: `studio/src/design/project-store.ts`

- [ ] **Step 1: Write the project store**

Reactive state:
- `projects: ProjectSummary[]` — all projects
- `activeProject: ProjectDetail | null` — currently viewed project
- `artifacts: { requirements, scenarios, proposals, evaluations }` — artifact records for the active project
- `vocabulary: VocabularyEntry[]` — merged global + project vocabulary
- `activeRequirementsId: string | null` — currently selected requirements set for evaluation context
- `activeProposalId: string | null` — currently selected proposal for evaluation context
- `loading`, `error`, `dbAvailable`

Functions:
- `checkDbAvailable()` — tries `listProjects()`, sets `dbAvailable`
- `loadProjects()` — fetches all projects
- `loadProject(id)` — fetches project detail + all artifact lists in parallel. Auto-sets `activeRequirementsId` and `activeProposalId` to the first active record if exactly one exists.
- `loadVocabulary(projectId?)` — fetches merged vocabulary
- `setActiveRequirements(id)` — sets `activeRequirementsId`
- `setActiveProposal(id)` — sets `activeProposalId`
- `openArtifactForEditing(artifactType, record)` — hydrates the design store's draft state from a project record's `.data` field. See State Ownership Rules above.
- `seedDb()`, `clearProject()`
- All functions that mutate the artifact lists (delete, refresh after save) must revalidate `activeRequirementsId` and `activeProposalId` per the Active Context Reset Rules above.

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/project-store.ts
git commit -m "feat(studio): add project store for workspace state management"
```

---

### Task 9: Project List and Overview Views

**Files:**
- Create: `studio/src/views/ProjectListView.vue`
- Create: `studio/src/views/ProjectOverviewView.vue`

- [ ] **Step 1: Write ProjectListView**

Design mode landing page. On mount:
1. Call `checkDbAvailable()` to determine if the sidecar is up
2. If available: call `loadProjects()`, show project cards (name, domain badge, summary, artifact counts). "Create Project" button with inline form. "Seed from Examples" button when list is empty. Card click navigates to `/design/projects/:id`.
3. If unavailable: fall back to `packs.generated.ts` — show demo packs as read-only project cards with a banner "Sidecar unavailable — read-only mode". Card click navigates to legacy pack-based routes (or opens a read-only view). This preserves the current standalone experience.

The fallback logic lives in ProjectListView, not in the store. The view checks `projectStore.dbAvailable` and branches accordingly.

- [ ] **Step 2: Write ProjectOverviewView**

Single project dashboard. Shows project name/domain/summary, artifact counts, compact artifact lists with navigation links. Import/export buttons. Calls `loadProject(projectId)` and `loadVocabulary(projectId)` on mount. Reads `projectId` from route params.

- [ ] **Step 3: Commit**

```bash
git add studio/src/views/ProjectListView.vue studio/src/views/ProjectOverviewView.vue
git commit -m "feat(studio): add project list and overview views"
```

---

### Task 10: Router Transition

Re-route artifact views under project paths.

**Files:**
- Modify: `studio/src/router.ts`

- [ ] **Step 1: Update design routes**

Replace the `designRoutes` array with project-first routes plus legacy pack routes for read-only fallback:

**Project routes (primary):**
- `/design` → `ProjectListView`
- `/design/projects/:projectId` → `ProjectOverviewView`
- `/design/projects/:projectId/requirements/:id` → `RequirementsView`
- `/design/projects/:projectId/scenarios/:id` → `ScenarioDetailView`
- `/design/projects/:projectId/proposals/:id` → `ProposalView`
- `/design/projects/:projectId/evaluations/:id` → `EvaluationView`

**Legacy pack routes (read-only fallback, kept for sidecar-down mode):**
- `/design/packs/:packId` → `ScenarioDetailView` (read-only, loads from `packs.generated.ts`)
- `/design/packs/:packId/requirements` → `RequirementsView` (read-only)
- `/design/packs/:packId/proposal` → `ProposalView` (read-only)
- `/design/packs/:packId/evaluation` → `EvaluationView` (read-only)

The artifact views check which route shape they're in (`route.params.projectId` vs `route.params.packId`) and load data accordingly. See Task 12 for the view-level logic.

- [ ] **Step 2: Commit**

```bash
git add studio/src/router.ts
git commit -m "feat(studio): transition router to project-first design routes"
```

---

### Task 11: App Shell — Design Sidebar and Active Design Context

Update the Studio shell to support project-first Design navigation and the active design context chooser.

**Files:**
- Modify: `studio/src/App.vue`

- [ ] **Step 1: Rewrite `designNavItems` for project-first navigation**

The current `designNavItems` computed (lines 35-49 of `App.vue`) is hardwired to the old pack-based routes using `designStore.activePackId`. Replace it with project-aware navigation that reads from `projectStore`:

```typescript
import { projectStore } from './design/project-store'

const designNavItems = computed(() => {
  const project = projectStore.activeProject
  const items = [
    { name: 'project-list', label: 'Projects', icon: '\u{1F3E0}', path: '/design' },
  ]
  if (project) {
    const pid = project.id
    items.push(
      { name: 'project-overview', label: project.name, icon: '\u{1F4C1}', path: `/design/projects/${pid}` },
    )
    // Show artifact links when inside a project
    if (projectStore.activeRequirementsId) {
      items.push({ name: 'requirements', label: 'Requirements', icon: '\u{1F4CB}', path: `/design/projects/${pid}/requirements/${projectStore.activeRequirementsId}` })
    }
    if (projectStore.activeProposalId) {
      items.push({ name: 'proposal', label: 'Proposal', icon: '\u{1F4A1}', path: `/design/projects/${pid}/proposals/${projectStore.activeProposalId}` })
    }
  }
  return items
})
```

The sidebar shows: Projects (always) → Project Name (when inside a project) → Requirements/Proposal (when active context is set). Scenarios and evaluations are accessed through the project overview, not the sidebar — they vary per-scenario.

- [ ] **Step 2: Add active design context display to ProjectOverviewView**

In the ProjectOverviewView (Task 9), add an "Active Design Context" section at the top of the dashboard. This is where users choose the requirements/proposal pair:

- Show a dropdown or card selector for requirements sets (from `projectStore.artifacts.requirements`). Selecting one calls `setActiveRequirements(id)`.
- Show a dropdown or card selector for proposals (from `projectStore.artifacts.proposals`). Selecting one calls `setActiveProposal(id)`.
- When exactly one of each exists, auto-select (already done in `loadProject()`).
- When multiple exist, the user must choose. The current selection is shown in the sidebar (Step 1 above) and persisted in `projectStore` state.
- A "Run Validation" shortcut appears when both are selected + a scenario is available.

This is the UI path the second finding requires. Without it, the Save to Project flow in EvaluationView cannot know which proposal/requirements pair the evaluation is for.

- [ ] **Step 3: Verify**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`

- [ ] **Step 4: Commit**

```bash
git add studio/src/App.vue studio/src/views/ProjectOverviewView.vue
git commit -m "feat(studio): rewrite Design sidebar for project-first navigation and active design context"
```

---

### Task 12: Artifact View Transitions

Update all artifact views to read from project route params and load from the API.

**Files:**
- Modify: `studio/src/views/RequirementsView.vue`
- Modify: `studio/src/views/ScenarioDetailView.vue`
- Modify: `studio/src/views/ProposalView.vue`
- Modify: `studio/src/views/EvaluationView.vue`
- Modify: `studio/src/design/store.ts`

- [ ] **Step 1: Wire openArtifactForEditing() in project-store.ts**

This is the handoff function defined in the State Ownership Rules. It takes an `ArtifactRecord` from the project store, extracts `.data`, and writes it into the design store's state so existing draft/edit/guided/validation flows work unchanged. The design store does NOT gain any project awareness — it only sees artifact content.

For requirements: sets `designStore.draftRequirements` from `record.data`, calls existing hydration.
For scenarios: sets `designStore.draftScenario` from `record.data`, calls existing hydration.
For proposals: sets proposal-related state from `record.data`.

Also updates `activeRequirementsId`/`activeProposalId` in the project store when navigating to those artifact types.

- [ ] **Step 2: Update each artifact view to use the handoff**

Each view supports two route shapes (see Task 10):

**Project route** (`route.params.projectId` + `route.params.id`):
1. Look up the record from `projectStore.artifacts`
2. Call `openArtifactForEditing()` to hydrate the design store
3. Editing, guided flows, validation all work via `designStore`
4. Sidebar links use project-scoped paths

**Legacy pack route** (`route.params.packId`):
1. Look up the pack from `designStore.packs` (static `packs.generated.ts`)
2. Load artifact data directly from the pack object
3. Read-only mode — editing and save are disabled
4. Sidebar links use legacy pack paths

The view checks which params are present and branches. A shared helper like `useArtifactSource()` can encapsulate this logic to avoid duplicating it across all 4 views.

- [ ] **Step 3: Add Save to Project on EvaluationView**

When a live validation result exists, show "Save to Project" button. On click:
1. Read `projectStore.activeRequirementsId` and `projectStore.activeProposalId` — if either is null, show a warning "Select a requirements set and proposal before saving"
2. Build `input_snapshot` by reading the current `designStore.draftRequirements`, `composeDraftProposal()`, and `designStore.draftScenario`
3. Call `createEvaluation()` with the result, `projectStore.activeProject.id`, reference IDs, `source: 'live_validation'`, and the `input_snapshot`
4. Refresh the project's evaluation list
5. Show "Live" badge for unsaved results, "Stored" badge for saved evaluations (from `projectStore.artifacts.evaluations`)

- [ ] **Step 4: Verify**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -30`
Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run 2>&1 | tail -15`

- [ ] **Step 5: Commit**

```bash
git add studio/src/views/ studio/src/design/store.ts
git commit -m "feat(studio): transition artifact views to project-backed API loading"
```

---

### Task 13: Vocabulary Integration in SuggestionChips

**Files:**
- Modify: `studio/src/design/components/SuggestionChips.vue`

- [ ] **Step 1: Add origin badges**

Add an optional `vocabularyEntries?: VocabularyEntry[]` prop. When provided, chips show origin badges:
- Canonical: solid border, normal text
- Project: dashed border, small "project" label
- Custom (user-typed, not in vocabulary): muted, "custom" label

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/components/SuggestionChips.vue
git commit -m "feat(studio): add origin badges to SuggestionChips for vocabulary grounding"
```

---

### Task 14: Integration Verification

- [ ] **Step 1: Run all backend tests**

Run: `cd /Users/samirski/Development/ANIP && python3 -m pytest studio/server/ -v 2>&1 | tail -30`

- [ ] **Step 2: Run all frontend tests**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run 2>&1 | tail -15`

- [ ] **Step 3: Type-check and build**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit && npm run build 2>&1 | tail -15`

- [ ] **Step 4: Fix any issues**

- [ ] **Step 5: Commit fixes**

---

### Task 15: Sync Embedded Assets

- [ ] **Step 1: Run sync**

Run: `cd /Users/samirski/Development/ANIP/studio && bash sync.sh`

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "build(studio): sync embedded assets after V3 Slice 4"
```
