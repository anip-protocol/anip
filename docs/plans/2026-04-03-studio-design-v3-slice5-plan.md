# Design V3 Slice 5: Workspace Hardening and Integrity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the Slice 4 workspace model with content hashes, staleness detection, evaluation provenance, requirements roles, vocabulary recognition flags, evaluator alignment for business-facing fields, tighter import/export validation, and operational reliability.

**Architecture:** Three phases — (1) Backend DB migration + repository changes for hashes, roles, vocabulary recognition, (2) Evaluator alignment for 5 business_constraints fields, (3) Frontend type/API/UI updates for staleness badges, requirements roles, and vocabulary recognition. All hash computation is SHA-256 of canonical JSON. Staleness is computed at read time by comparing per-artifact hashes.

**Tech Stack:** Python 3.12, FastAPI, psycopg (v3), PostgreSQL 16; Python evaluator; Vue 3, TypeScript

**Reference:** Design proposal at `/Users/samirski/Development/ANIP/docs/plans/2026-04-03-studio-design-v3-slice5-design.md`

---

## File Structure

### Phase 1: Backend Schema + Repository

#### New Files

| File | Responsibility |
|------|---------------|
| `studio/server/migrations/002_slice5_hardening.sql` | Schema migration: content_hash columns, per-artifact eval hashes, requirements role, vocabulary evaluator_recognized |
| `studio/server/hashing.py` | `canonical_json()` and `content_hash()` utility functions |

#### Modified Files

| File | Changes |
|------|---------|
| `studio/server/repository.py` | Compute content_hash on artifact create/update; store per-artifact hashes on evaluation create; add staleness computation to evaluation list/detail; add requirements role support; add vocabulary evaluator_recognized support |
| `studio/server/models.py` | Add content_hash to ArtifactOut, per-artifact hashes + is_stale + stale_artifacts to EvaluationOut, role to requirements models, evaluator_recognized to vocabulary models |
| `studio/server/seed.py` | Compute content_hash on seed create; compute per-artifact hashes on evaluation seed |
| `studio/server/vocabulary_defaults.json` | Add evaluator_recognized field to all entries |
| `studio/server/routers/artifacts.py` | Pass staleness data through evaluation endpoints; add PUT requirements role endpoint |

### Phase 2: Evaluator Alignment

#### Modified Files

| File | Changes |
|------|---------|
| `tooling/bin/anip_design_validate.py` | Add business_constraints consumption in evaluate_safety and evaluate_recovery |

### Phase 3: Frontend

#### Modified Files

| File | Changes |
|------|---------|
| `studio/src/design/project-types.ts` | Add content_hash, role, evaluator_recognized, staleness fields |
| `studio/src/design/project-store.ts` | Surface staleness state, handle requirements role |
| `studio/src/views/ProjectOverviewView.vue` | Stale badges on evaluations, primary/alternative requirements display |
| `studio/src/views/EvaluationView.vue` | Stale badge, stale_artifacts detail, re-evaluate button |
| `studio/src/design/components/SuggestionChips.vue` | Show evaluator_recognized indicator |

### Tests

| File | Changes |
|------|---------|
| `studio/server/test_hashing.py` | Tests for canonical_json and content_hash |
| `studio/server/test_staleness.py` | Tests for staleness detection across artifact updates |
| `studio/server/test_roles.py` | Tests for requirements primary/alternative role enforcement |
| `tooling/tests/test_evaluator.py` | Tests for new business_constraints consumption |

---

## Phase 1: Backend

### Task 1: Hashing Utility Module

**Files:**
- Create: `studio/server/hashing.py`
- Create: `studio/server/test_hashing.py`

- [ ] **Step 1: Write the hashing module**

```python
# studio/server/hashing.py
"""Deterministic content hashing for artifact staleness detection."""

import hashlib
import json


def canonical_json(data: dict) -> str:
    """Produce a deterministic JSON string for hashing.
    Keys are sorted, separators are compact, no trailing whitespace.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def content_hash(data: dict) -> str:
    """SHA-256 hex digest of the canonical JSON representation."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
```

- [ ] **Step 2: Write tests**

```python
# studio/server/test_hashing.py
import os
os.environ.setdefault("DATABASE_URL", "postgresql://anip:anip@localhost:5432/anip_studio")

from studio.server.hashing import canonical_json, content_hash


def test_canonical_json_sorts_keys():
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonical_json_deterministic():
    d1 = {"x": {"b": 2, "a": 1}, "y": [3, 1]}
    d2 = {"y": [3, 1], "x": {"a": 1, "b": 2}}
    assert canonical_json(d1) == canonical_json(d2)


def test_content_hash_is_sha256():
    h = content_hash({"test": True})
    assert len(h) == 64  # SHA-256 hex = 64 chars
    assert h == content_hash({"test": True})  # deterministic


def test_content_hash_changes_on_different_data():
    assert content_hash({"a": 1}) != content_hash({"a": 2})
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/samirski/Development/ANIP && DATABASE_URL=postgresql://anip:anip@localhost:5432/anip_studio /tmp/anip-venv/bin/python3 -m pytest studio/server/test_hashing.py -v`
Expected: 4 pass

- [ ] **Step 4: Commit**

```bash
git add studio/server/hashing.py studio/server/test_hashing.py
git commit -m "feat(studio-api): add canonical JSON hashing utility for staleness detection"
```

---

### Task 2: Database Migration — Content Hashes, Roles, Vocabulary Recognition

**Files:**
- Create: `studio/server/migrations/002_slice5_hardening.sql`

- [ ] **Step 1: Write the migration**

```sql
-- 002_slice5_hardening.sql — Slice 5: hashes, roles, evaluator_recognized

-- Per-artifact content hashes (recomputed on every create/update)
ALTER TABLE requirements_sets ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE scenarios ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE proposals ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';

-- Per-artifact hashes on evaluations (frozen at evaluation save time)
ALTER TABLE evaluations ADD COLUMN requirements_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE evaluations ADD COLUMN proposal_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE evaluations ADD COLUMN scenario_hash TEXT NOT NULL DEFAULT '';

-- Requirements role: safe migration for existing data.
-- Step 1: Add nullable column first (no constraint yet)
ALTER TABLE requirements_sets ADD COLUMN role TEXT;

-- Step 2: Backfill — mark the oldest requirements set per project as primary, rest as alternative
UPDATE requirements_sets SET role = 'alternative';
UPDATE requirements_sets SET role = 'primary'
    WHERE id IN (
        SELECT DISTINCT ON (project_id) id
        FROM requirements_sets
        ORDER BY project_id, created_at ASC
    );

-- Step 3: Now enforce NOT NULL + CHECK
ALTER TABLE requirements_sets ALTER COLUMN role SET NOT NULL;
ALTER TABLE requirements_sets ALTER COLUMN role SET DEFAULT 'alternative';
ALTER TABLE requirements_sets ADD CONSTRAINT requirements_role_check
    CHECK (role IN ('primary', 'alternative'));

-- Step 4: Partial unique index — at most one primary per project
CREATE UNIQUE INDEX idx_requirements_primary_per_project
    ON requirements_sets(project_id) WHERE role = 'primary';

-- Vocabulary: evaluator_recognized flag
ALTER TABLE vocabulary ADD COLUMN evaluator_recognized BOOLEAN NOT NULL DEFAULT FALSE;
```

- [ ] **Step 2: Verify migration applies**

Start Postgres: `cd /Users/samirski/Development/ANIP/studio && docker compose up studio-db -d`
Run: `cd /Users/samirski/Development/ANIP && DATABASE_URL=postgresql://anip:anip@localhost:5432/anip_studio /tmp/anip-venv/bin/python3 -c "from studio.server.db import init_db; init_db(); print('Migration applied')"`
Expected: `Migration applied`

- [ ] **Step 3: Commit**

```bash
git add studio/server/migrations/002_slice5_hardening.sql
git commit -m "feat(studio-api): add Slice 5 migration — hashes, roles, evaluator_recognized"
```

---

### Task 3: Repository — Content Hash on Artifact Create/Update

Wire `content_hash()` into every artifact create and update operation. Wire per-artifact hash capture into evaluation create. Add staleness computation to evaluation list/detail.

**Files:**
- Modify: `studio/server/repository.py`
- Modify: `studio/server/models.py`

- [ ] **Step 1: Update repository artifact create/update to compute content_hash**

In `repository.py`, import `content_hash` from `hashing`. Update all artifact INSERT and UPDATE statements to include `content_hash`:

- `create_requirements()` / `update_requirements()` — compute `content_hash(data)` on write
- `create_scenario()` / `update_scenario()` — same
- `create_proposal()` / `update_proposal()` — same
- Generic `_create_artifact()` / `_update_artifact()` helpers — add `content_hash` to the INSERT/UPDATE SQL

- [ ] **Step 2: Update evaluation create to capture per-artifact hashes**

In `create_evaluation()`, after the coherence check, look up the current `content_hash` of each linked artifact and store them:

```python
req_row = get_requirements(conn, project_id, requirements_id)
prop_row = get_proposal(conn, project_id, proposal_id)
scn_row = get_scenario(conn, project_id, scenario_id)

requirements_hash = req_row["content_hash"]
proposal_hash = prop_row["content_hash"]
scenario_hash = scn_row["content_hash"]
```

Add these to the INSERT statement.

- [ ] **Step 3: Add staleness computation to evaluation queries**

Add a helper function `_compute_staleness(conn, eval_row)` that:
1. Looks up each linked artifact's current `content_hash`
2. Compares against the stored per-artifact hashes
3. Returns `(is_stale: bool, stale_artifacts: list[str])`

Wire this into `get_evaluation()` and `list_evaluations()` so they return `is_stale` and `stale_artifacts` in every evaluation dict.

For list queries, use a single SQL JOIN to avoid N+1:

```sql
SELECT e.*,
    rs.content_hash AS current_req_hash,
    p.content_hash AS current_prop_hash,
    s.content_hash AS current_scn_hash
FROM evaluations e
JOIN requirements_sets rs ON e.requirements_id = rs.id
JOIN proposals p ON e.proposal_id = p.id
JOIN scenarios s ON e.scenario_id = s.id
WHERE e.project_id = %s
ORDER BY e.created_at DESC
```

Then compute staleness in Python from the joined result.

- [ ] **Step 4: Add requirements role support**

Update `create_requirements()` to auto-assign role:
- Check if the project already has a primary requirements set
- If no primary exists → set `role = 'primary'` (first requirements set becomes primary automatically)
- If a primary already exists → set `role = 'alternative'`
- The DB column default is `'alternative'` so the safe path is always alternative unless explicitly promoted

Add `set_requirements_role(conn, project_id, req_id, role)` function that:
- If promoting to `'primary'`, first demote the current primary to `'alternative'` (UPDATE WHERE project_id = ? AND role = 'primary')
- Then set the new role on the target record
- The partial unique index enforces at most one primary per project — the demote-then-promote must happen in the same transaction

- [ ] **Step 5: Update Pydantic models**

In `models.py`:
- Add `content_hash: str = ''` to `ArtifactOut`
- Add `requirements_hash: str`, `proposal_hash: str`, `scenario_hash: str`, `is_stale: bool = False`, `stale_artifacts: list[str] = []` to `EvaluationOut`
- Add `role: str = 'primary'` to `ArtifactOut` (or create `RequirementsOut(ArtifactOut)` with `role`)
- Add `evaluator_recognized: bool = False` to `VocabularyOut`

- [ ] **Step 6: Update vocabulary defaults JSON**

Add `"evaluator_recognized": true/false` to every entry in `studio/server/vocabulary_defaults.json`. Mark as `true` the entries whose values the evaluator actually consumes. Use the gap analysis from the design doc to determine which are `true`.

Update `load_vocabulary_defaults()` in repository to handle the new field.

- [ ] **Step 7: Update seed.py to compute hashes**

In `seed_from_examples()`, after creating each artifact, the `content_hash` is now computed by the repository. For evaluations, the per-artifact hashes are now captured automatically by `create_evaluation()`.

- [ ] **Step 8: Commit**

```bash
git add studio/server/repository.py studio/server/models.py studio/server/seed.py studio/server/vocabulary_defaults.json
git commit -m "feat(studio-api): add content hashes, staleness detection, requirements roles, and vocabulary recognition"
```

---

### Task 4: Backend Tests — Staleness, Roles, Import/Export Tightening

**Files:**
- Create: `studio/server/test_staleness.py`
- Create: `studio/server/test_roles.py`

- [ ] **Step 1: Write staleness tests**

Test cases:
- Create project with artifacts and evaluation → `is_stale = false`, `stale_artifacts = []`
- Update the requirements data → re-fetch evaluation → `is_stale = true`, `"requirements" in stale_artifacts`
- Update the scenario data → re-fetch evaluation → `"scenario" in stale_artifacts`
- List evaluations returns staleness for each
- New evaluation after updates → `is_stale = false` (fresh hashes)

- [ ] **Step 2: Write role tests**

Test cases:
- First requirements set in a project is `role = 'primary'`
- Second requirements set defaults to `role = 'alternative'`
- Cannot create two primary requirements sets in the same project (409 from unique index)
- Promoting alternative to primary demotes the current primary
- Delete primary requirements set is still blocked by proposal refs

- [ ] **Step 3: Run all backend tests**

Run: `cd /Users/samirski/Development/ANIP && DATABASE_URL=postgresql://anip:anip@localhost:5432/anip_studio /tmp/anip-venv/bin/python3 -m pytest studio/server/ -v 2>&1 | tail -40`
Expected: All pass (including existing Slice 4 tests + new tests)

- [ ] **Step 4: Fix any failures**

- [ ] **Step 5: Commit**

```bash
git add studio/server/test_staleness.py studio/server/test_roles.py
git commit -m "test(studio-api): add staleness detection and requirements role tests"
```

---

## Phase 2: Evaluator Alignment

### Task 5: Evaluator — Consume Business Constraints

Add consumption of 5 `business_constraints` fields to the evaluator. All checks are against structured fields only — no free-text interpretation.

**Files:**
- Modify: `tooling/bin/anip_design_validate.py`
- Modify: `tooling/tests/test_evaluator.py`

- [ ] **Step 1: Add business_constraints consumption to evaluate_safety()**

Read `business_constraints` from the requirements dict. Add checks:

```python
bc = req.get("business_constraints", {})
psurfaces = proposal.get("proposal", {}).get("declared_surfaces", {})

# spending_possible: check budget_enforcement surface
if bc.get("spending_possible"):
    if context.get("expected_cost") is not None or context.get("budget_limit") is not None:
        if psurfaces.get("budget_enforcement"):
            append_unique(handled, "budget enforcement for spending-possible system")
        else:
            improve.append("declare budget_enforcement surface for spending-possible system")

# approval_expected_for_high_risk: check authority_posture surface
if bc.get("approval_expected_for_high_risk"):
    if psurfaces.get("authority_posture"):
        append_unique(handled, "authority posture for high-risk approval expectations")
    else:
        improve.append("declare authority_posture surface for approval-expected system")

# cost_visibility_required: check budget_enforcement surface (implies cost visibility)
if bc.get("cost_visibility_required"):
    if psurfaces.get("budget_enforcement"):
        append_unique(handled, "cost visibility via budget enforcement")
    else:
        improve.append("declare budget_enforcement surface for cost-visibility-required system")
```

- [ ] **Step 2: Add business_constraints consumption to evaluate_recovery()**

```python
bc = req.get("business_constraints", {})
psurfaces = proposal.get("proposal", {}).get("declared_surfaces", {})

# recovery_sensitive: check recovery_class surface
if bc.get("recovery_sensitive"):
    if psurfaces.get("recovery_class"):
        append_unique(handled, "recovery class guidance for recovery-sensitive system")
    else:
        improve.append("declare recovery_class surface for recovery-sensitive system")

# blocked_failure_posture: check recovery_class surface
posture = bc.get("blocked_failure_posture")
if posture and posture != "not_specified":
    if psurfaces.get("recovery_class"):
        append_unique(handled, f"recovery class aligns with declared failure posture ({posture})")
    else:
        improve.append(f"declare recovery_class surface for system with {posture} failure posture")
```

- [ ] **Step 3: Add evaluator tests**

In `tooling/tests/test_evaluator.py`, add tests verifying:
- `spending_possible=true` + `budget_enforcement` surface → handled
- `spending_possible=true` without surface → appears in `what_would_improve`
- `approval_expected_for_high_risk=true` + `authority_posture` surface → handled
- `recovery_sensitive=true` + `recovery_class` surface → handled
- `recovery_sensitive=true` without surface → appears in `what_would_improve`
- `blocked_failure_posture='escalate_to_human'` + `recovery_class` → handled

- [ ] **Step 4: Run evaluator tests**

Run: `cd /Users/samirski/Development/ANIP && python3 -m pytest tooling/tests/test_evaluator.py -v 2>&1 | tail -20`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add tooling/bin/anip_design_validate.py tooling/tests/test_evaluator.py
git commit -m "feat(evaluator): consume business_constraints fields — spending, approval, recovery, cost visibility"
```

---

## Phase 3: Frontend

### Task 6: Frontend Types — Staleness, Roles, Vocabulary Recognition

**Files:**
- Modify: `studio/src/design/project-types.ts`

- [ ] **Step 1: Update types**

```typescript
// Add to ArtifactRecord:
export interface ArtifactRecord {
  id: string
  project_id: string
  title: string
  status: string
  data: Record<string, any>
  content_hash: string          // NEW
  created_at: string
  updated_at: string
}

// Add RequirementsRecord with role:
export interface RequirementsRecord extends ArtifactRecord {
  role: 'primary' | 'alternative'
}

// Update EvaluationRecord:
export interface EvaluationRecord {
  id: string
  project_id: string
  proposal_id: string
  scenario_id: string
  requirements_id: string
  result: string
  source: string
  data: Record<string, any>
  input_snapshot: Record<string, any>
  requirements_hash: string     // NEW
  proposal_hash: string         // NEW
  scenario_hash: string         // NEW
  is_stale: boolean             // NEW
  stale_artifacts: string[]     // NEW
  created_at: string
}

// Update VocabularyEntry:
export interface VocabularyEntry {
  id: number
  project_id: string | null
  category: string
  value: string
  origin: 'canonical' | 'project' | 'custom'
  evaluator_recognized: boolean  // NEW
  description: string
}
```

- [ ] **Step 2: Update project store to use RequirementsRecord**

In `studio/src/design/project-store.ts`, update the `artifacts.requirements` type from `ArtifactRecord[]` to `RequirementsRecord[]`.

- [ ] **Step 3: Verify**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`

- [ ] **Step 4: Commit**

```bash
git add studio/src/design/project-types.ts studio/src/design/project-store.ts
git commit -m "feat(studio): add staleness, role, and vocabulary recognition types"
```

---

### Task 7: Evaluation View — Stale Badges and Re-evaluate

**Files:**
- Modify: `studio/src/views/EvaluationView.vue`

- [ ] **Step 1: Add staleness UI**

In EvaluationView, when displaying a stored evaluation from `projectStore.artifacts.evaluations`:

- Show **Stored** (green badge) when `is_stale === false`
- Show **Stale** (amber badge) when `is_stale === true`
- When stale, show which artifacts changed: "Requirements changed", "Scenario changed", etc.
- Add a **Re-evaluate** button on stale evaluations that:
  1. Runs `POST /api/validate` with current artifact state
  2. On success, calls `createEvaluation()` with the new result + fresh hashes + `source: 'live_validation'`
  3. Refreshes the evaluation list
  4. **Navigates to the new evaluation record** (`router.push(/design/projects/${pid}/evaluations/${newId})`) so the user sees the fresh result immediately
  5. The old stale evaluation remains in the project's evaluation list (visible from the project overview)

- [ ] **Step 2: Commit**

```bash
git add studio/src/views/EvaluationView.vue
git commit -m "feat(studio): add stale badge and re-evaluate button on EvaluationView"
```

---

### Task 8: Project Overview — Primary Requirements, Promote-to-Primary, and Stale Evaluations

**Files:**
- Modify: `studio/server/routers/artifacts.py` (add promote-to-primary endpoint)
- Modify: `studio/src/design/project-api.ts` (add `setRequirementsRole` API call)
- Modify: `studio/src/views/ProjectOverviewView.vue`

- [ ] **Step 1: Add promote-to-primary API route**

Add a new endpoint to `studio/server/routers/artifacts.py`:

```
PUT /api/projects/{pid}/requirements/{rid}/role
Body: { "role": "primary" | "alternative" }
```

This calls `set_requirements_role(conn, pid, rid, role)` from the repository. Returns the updated requirements record. Errors: 404 if not found, 422 if the role value is invalid.

- [ ] **Step 2: Add frontend API call**

Add to `studio/src/design/project-api.ts`:

```typescript
export const setRequirementsRole = (pid: string, rid: string, role: 'primary' | 'alternative') =>
  api<ArtifactRecord>(`/api/projects/${pid}/requirements/${rid}/role`, {
    method: 'PUT',
    body: JSON.stringify({ role }),
  })
```

- [ ] **Step 3: Show primary vs alternative requirements with promote action**

In the requirements section of ProjectOverviewView:
- Show the primary requirements set prominently at top with a "Primary" badge
- Show alternative requirements sets below in a collapsible "Alternatives" section
- Each alternative requirements set has a "Promote to Primary" button that:
  1. Calls `setRequirementsRole(pid, rid, 'primary')`
  2. Refreshes the artifact list (`loadProject(pid)`)
  3. The old primary is automatically demoted to alternative by the repository
- Auto-select the primary requirements set in the active context

- [ ] **Step 4: Show stale badges on evaluation list**

In the evaluations section of ProjectOverviewView:
- Each evaluation row shows its result badge (HANDLED/PARTIAL/REQUIRES_GLUE)
- Additionally show a **Stale** amber badge when `is_stale === true`
- Stale evaluations are not hidden — they remain visible with clear staleness indication

- [ ] **Step 5: Commit**

```bash
git add studio/server/routers/artifacts.py studio/src/design/project-api.ts studio/src/views/ProjectOverviewView.vue
git commit -m "feat(studio): add promote-to-primary workflow, primary/alternative display, stale evaluation badges"
```

---

### Task 9: Vocabulary — Evaluator Recognition in SuggestionChips

**Files:**
- Modify: `studio/src/design/components/SuggestionChips.vue`

- [ ] **Step 1: Add evaluator-recognized indicator**

The `vocabularyEntries` prop already exists on SuggestionChips. Update the chip rendering:

- For canonical + `evaluator_recognized === true`: normal appearance (no change)
- For canonical + `evaluator_recognized === false`: add a subtle "not evaluated" indicator (e.g., small strikethrough icon or muted "(not evaluated)" text)
- For project and custom entries: existing badges already communicate non-recognition

The hints engine should also add a warning when custom `expected_anip_support` entries exist:
> "N custom ANIP support entries are stored but not recognized by the evaluator."

- [ ] **Step 2: Commit**

```bash
git add studio/src/design/components/SuggestionChips.vue
git commit -m "feat(studio): show evaluator-recognized indicator on vocabulary chips"
```

---

### Task 10: Import/Export Tightening

**Files:**
- Modify: `studio/server/routers/import_export.py`
- Modify: `studio/server/repository.py`

- [ ] **Step 1: Tighten import validation**

In the import endpoint (`POST /api/projects/{pid}/import`):
- Validate each artifact against its JSON schema before inserting (requirements, scenario, proposal, evaluation)
- For evaluation imports: additionally validate the evaluation data against the evaluation JSON schema (`tooling/schemas/evaluation.schema.json`), and validate that `proposal_id`, `scenario_id`, and `requirements_id` all exist in the target project. Imported evaluations must include `input_snapshot` and the per-artifact hashes (`requirements_hash`, `proposal_hash`, `scenario_hash`) — if hashes are missing, compute them from the snapshot content.
- Reject duplicate IDs with a clear error message instead of a generic 500
- For proposal imports: validate that `requirements_id` exists in the target project
- Return per-artifact error details in the `errors` array

- [ ] **Step 2: Tighten export guarantees**

In the export endpoint (`GET /api/projects/{pid}/export`):
- Include `content_hash` on every artifact record
- Include stored per-artifact hashes (`requirements_hash`, `proposal_hash`, `scenario_hash`) on every evaluation — these are durable provenance data
- Do NOT include `is_stale` in the portable payload — staleness is an environment-relative observation computed at read time, not durable export truth. Importers can recompute staleness from the hashes after import.
- Add a `metadata` section with export timestamp

- [ ] **Step 3: Add import/export tightening tests**

Test:
- Import artifact with duplicate ID → rejected with clear error
- Import proposal with missing requirements_id → rejected
- Import evaluation with cross-project refs → rejected
- Export includes content_hash on artifacts and per-artifact hashes on evaluations (no is_stale)

- [ ] **Step 4: Commit**

```bash
git add studio/server/routers/import_export.py studio/server/repository.py studio/server/test_import_export.py
git commit -m "feat(studio-api): tighten import validation and export guarantees"
```

---

### Task 11: Operational Hardening

**Files:**
- Modify: `studio/server/db.py`
- Modify: `studio/server/conftest.py`

- [ ] **Step 1: Add connection pool open parameter**

Fix the psycopg_pool deprecation warning by explicitly passing `open=True`:

```python
_pool = ConnectionPool(
    DATABASE_URL,
    kwargs={"row_factory": dict_row},
    min_size=2,
    max_size=10,
    open=True,
)
```

- [ ] **Step 2: Improve test isolation**

Update `conftest.py` to ensure each test module gets a fully clean database state. Add a `clean_db` fixture that truncates all data tables in dependency order and re-seeds vocabulary defaults.

- [ ] **Step 3: Commit**

```bash
git add studio/server/db.py studio/server/conftest.py
git commit -m "fix(studio-api): fix pool deprecation warning and improve test isolation"
```

---

### Task 12: Integration Verification

- [ ] **Step 1: Run all backend tests**

Run: `cd /Users/samirski/Development/ANIP && DATABASE_URL=postgresql://anip:anip@localhost:5432/anip_studio /tmp/anip-venv/bin/python3 -m pytest studio/server/ tooling/tests/test_evaluator.py -v 2>&1 | tail -40`
Expected: All pass

- [ ] **Step 2: Run frontend tests**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run 2>&1 | tail -15`
Expected: All pass

- [ ] **Step 3: Type-check and build**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit && npm run build 2>&1 | tail -15`
Expected: Clean

- [ ] **Step 4: Fix any issues**

- [ ] **Step 5: Commit fixes**

---

### Task 13: Sync Embedded Assets

- [ ] **Step 1: Run sync**

Run: `cd /Users/samirski/Development/ANIP/studio && bash sync.sh`

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "build(studio): sync embedded assets after V3 Slice 5"
```
