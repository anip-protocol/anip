# Studio Service-Shaping: Phase A+B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pivot ANIP Studio from "ANIP capability validation" to "service shaping and contract shaping" by (A) reframing evaluator output language and (B) introducing a first-class Shape artifact with services, capabilities, domain concepts, coordination edges, and derived contract expectations.

**Architecture:** Phase A is a text-only change — evaluator output strings and Vue view labels, no data model changes. Phase B adds a `shapes` table, shape JSON schema, shape-internal integrity validation, contract expectation derivation rules, a shape evaluator entry point, and a ShapeView in the frontend. Proposals are absorbed into shapes — the proposal table stays for backward compat but new projects use shapes.

**Tech Stack:** Python 3.12, FastAPI, psycopg, PostgreSQL 16; Vue 3, TypeScript; existing evaluator module at `tooling/bin/anip_evaluator/`

**Reference:** Design at `/Users/samirski/Development/ANIP/docs/plans/2026-04-04-studio-service-shaping-design.md`

---

## Shape-First Transition Rules

Shape replaces Proposal as the primary design artifact. Workers must follow these rules:

### New Projects Are Shape-First

- New projects create Shapes, not Proposals
- The "active design context" becomes: `activeRequirementsId` + `activeShapeId` + scenario (replacing `activeProposalId`)
- `activeProposalId` stays in the store for legacy projects only
- The sidebar shows Shape (not Proposal) for projects that have shapes
- ProjectOverviewView shows Shape as the primary design artifact; Proposal section appears only for legacy projects (those with proposals but no shapes)

### Evaluation Uses Shape When Available

- `EvaluationView` and the save-to-project flow check for `activeShapeId` first, then fall back to `activeProposalId`
- New evaluations on shape-first projects set `shape_id` (and `proposal_id = null`)
- Legacy evaluations with `proposal_id` still work and display correctly
- Staleness detection for shape-backed evaluations uses `shape_hash` alongside `requirements_hash` and `scenario_hash`
- The "Save to Project" button builds `derived_expectations` snapshot at save time

### Proposal UI Is Legacy-Only

- ProposalView stays in the codebase for reading existing proposals
- Proposal routes stay for backward compat
- But: new projects do not show "Create Proposal" — they show "Create Shape"
- The sidebar does not show Proposal for shape-first projects

### Frontend Type Updates Required

- `ProjectDetail` gains `shapes_count`
- `EvaluationRecord` gains optional `shape_id`, `shape_hash`, `derived_expectations`
- `EvaluationRecord.proposal_id` becomes optional (string | null)

---

## File Structure

### Phase A: Evaluator Language Reframing

#### Modified Files

| File | Changes |
|------|---------|
| `tooling/bin/anip_evaluator/categories.py` | Reword all "declare X surface" strings to "current design should expose X" |
| `tooling/bin/anip_evaluator/shared.py` | Reword shared output strings |
| `tooling/tests/test_evaluator.py` | Update expected strings in assertions |
| `studio/src/views/EvaluationView.vue` | Rename section headers: "Supported by Design", "Requires Custom Integration", "Design Changes Needed" |

### Phase B: Shape Model

#### New Files

| File | Responsibility |
|------|---------------|
| `studio/server/migrations/003_shapes.sql` | Shapes table + evaluation shape_id/shape_hash/derived_expectations columns |
| `tooling/schemas/shape.schema.json` | Shape JSON schema |
| `studio/server/shape_integrity.py` | Shape-internal reference validation (coordination → services, concepts → services, owns_concepts → concepts) |
| `studio/server/derivation.py` | Contract expectation derivation rules (shape + requirements → expected ANIP semantics) |
| `studio/server/routers/shapes.py` | CRUD API for shapes |
| `studio/server/test_shapes.py` | Tests for shape CRUD, integrity, derivation |
| `studio/src/design/shape-types.ts` | TypeScript types for shapes, services, concepts, coordination, derived expectations |
| `studio/src/views/ShapeView.vue` | Shape editor — services, capabilities, concepts, coordination, derived expectations panel |

#### Modified Files

| File | Changes |
|------|---------|
| `studio/server/repository.py` | Shape CRUD, shape_hash on evaluations, shapes_count in project detail |
| `studio/server/models.py` | Shape Pydantic models, evaluation shape fields (optional shape_id/shape_hash/derived_expectations), ProjectDetail gains shapes_count |
| `studio/server/app.py` | Include shapes router |
| `studio/src/design/project-api.ts` | Shape API functions + expectations endpoint |
| `studio/src/design/project-types.ts` | ShapeRecord, ProjectDetail.shapes_count, EvaluationRecord gains shape_id/shape_hash/derived_expectations (optional), proposal_id becomes optional |
| `studio/src/design/project-store.ts` | Shape state, activeShapeId replaces activeProposalId as primary, legacy proposal support kept |
| `studio/src/views/ProjectOverviewView.vue` | Shape as primary design artifact section; proposal section demoted to legacy-only |
| `studio/src/views/EvaluationView.vue` | Save-to-project uses shape_id when available; stale detection for shape_hash; derived_expectations snapshot on save |
| `studio/src/router.ts` | Shape route |
| `studio/src/App.vue` | Shape nav replaces Proposal nav for shape-first projects |

---

## Phase A: Evaluator Language Reframing

### Task 1: Reword Evaluator Output Strings

Reword all evaluator output to use "current design" language instead of "declare surface" language. No logic changes — same checks, same rules, different wording.

**Files:**
- Modify: `tooling/bin/anip_evaluator/categories.py`
- Modify: `tooling/bin/anip_evaluator/shared.py`
- Modify: `tooling/tests/test_evaluator.py`

- [ ] **Step 1: Reword categories.py**

In `categories.py`, find all strings containing "declare" or "approach does not declare" and reword:

| Before | After |
|--------|-------|
| `"declare budget_enforcement so over-budget blocking is visible..."` | `"the current design should expose budget enforcement so over-budget blocking is visible..."` |
| `"approach does not declare budget_enforcement for an over-budget path"` | `"the current design does not expose budget enforcement for an over-budget path"` |
| `"declare authority_posture or recovery_class when blocked..."` | `"the current design should expose authority posture or recovery class when blocked..."` |
| `"declare budget_enforcement surface for spending-possible system"` | `"the current design should expose budget enforcement for a spending-possible system"` |
| `"declare authority_posture surface for approval-expected system"` | `"the current design should expose authority posture for an approval-expected system"` |
| `"declare budget_enforcement surface for cost-visibility-required system"` | `"the current design should expose budget enforcement for a cost-visibility-required system"` |
| `"declare recovery_class surface for recovery-sensitive system"` | `"the current design should expose recovery class for a recovery-sensitive system"` |
| `"declare recovery_class surface for system with {posture} failure posture"` | `"the current design should expose recovery class for a system with {posture} failure posture"` |

Also reword any `handled` strings that say "surface" to say "design support":
| Before | After |
|--------|-------|
| `"budget enforcement for spending-possible system"` | `"budget enforcement for spending-possible system (design support)"` |

Do a full pass through `categories.py` — there may be other "surface"-centric strings in the orchestration, cross_service, and observability evaluators.

- [ ] **Step 2: Update test assertions**

In `tooling/tests/test_evaluator.py`, update all expected string matches to use the new wording. Search for "declare" and "surface" in assertions.

- [ ] **Step 3: Run evaluator tests**

Run: `cd /Users/samirski/Development/ANIP && python3 -m pytest tooling/tests/test_evaluator.py -v 2>&1 | tail -30`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add tooling/bin/anip_evaluator/ tooling/tests/test_evaluator.py
git commit -m "feat(evaluator): reword output from surface-declaration to design-support language (Phase A)"
```

---

### Task 2: Reword EvaluationView Labels

Rename section headers in Studio's evaluation display.

**Files:**
- Modify: `studio/src/views/EvaluationView.vue`

- [ ] **Step 1: Update section headers**

| Before | After |
|--------|-------|
| `Handled by ANIP` | `Supported by Design` |
| `Glue You Will Still Write` | `Requires Custom Integration` |
| `What Would Improve` | `Design Changes Needed` |

These are at lines 368, 376, 392 approximately. Also update any `title` attributes or aria labels.

- [ ] **Step 2: Verify**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -10`
Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run 2>&1 | tail -10`

- [ ] **Step 3: Commit**

```bash
git add studio/src/views/EvaluationView.vue
git commit -m "feat(studio): reword evaluation view from ANIP-surface to design-support language (Phase A)"
```

---

## Phase B: Shape Model

### Task 3: Shape JSON Schema

**Files:**
- Create: `tooling/schemas/shape.schema.json`

- [ ] **Step 1: Write the schema**

Create the shape JSON schema as specified in the design Section 8. Key structural rules:
- Root: `{ "shape": { ... } }`
- Required: `id`, `name`, `type` (single_service | multi_service), `services`
- Services: array of objects with `id`, `name`, `role` (required) + `responsibilities`, `capabilities`, `owns_concepts` (optional arrays)
- Coordination: optional array with `from`, `to`, `relationship` (handoff | verification | async_followup) + `description`
- Domain concepts: optional array with `id`, `name`, `meaning` (required) + `owner`, `sensitivity` (none | medium | high), `risk_note`
- Notes: optional string array (authored design rationale)

- [ ] **Step 2: Commit**

```bash
git add tooling/schemas/shape.schema.json
git commit -m "feat: add shape JSON schema"
```

---

### Task 4: Database Migration — Shapes Table

**Files:**
- Create: `studio/server/migrations/003_shapes.sql`

- [ ] **Step 1: Write the migration**

```sql
-- 003_shapes.sql — Shape artifact table + evaluation shape references

CREATE TABLE shapes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requirements_id TEXT NOT NULL REFERENCES requirements_sets(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    data JSONB NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_shapes_project ON shapes(project_id);
CREATE INDEX idx_shapes_requirements ON shapes(requirements_id);

-- Evaluation shape references (proposal_id becomes optional for backward compat)
ALTER TABLE evaluations ADD COLUMN shape_id TEXT REFERENCES shapes(id);
ALTER TABLE evaluations ADD COLUMN shape_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE evaluations ADD COLUMN derived_expectations JSONB;
ALTER TABLE evaluations ALTER COLUMN proposal_id DROP NOT NULL;
```

- [ ] **Step 2: Verify migration applies**

Run: `docker exec studio-studio-db-1 psql -U anip -c "DROP DATABASE anip_studio; CREATE DATABASE anip_studio;"`
Then: `cd /Users/samirski/Development/ANIP && DATABASE_URL=postgresql://anip:anip@localhost:5432/anip_studio /tmp/anip-venv/bin/python3 -c "from studio.server.db import init_db; init_db(); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add studio/server/migrations/003_shapes.sql
git commit -m "feat(studio-api): add shapes table and evaluation shape references"
```

---

### Task 5: Shape Integrity Validation

Validates shape-internal references: coordination edges → service IDs, concept ownership → service IDs, owns_concepts → concept IDs.

**Files:**
- Create: `studio/server/shape_integrity.py`

- [ ] **Step 1: Write the integrity validator**

```python
# studio/server/shape_integrity.py
"""Shape-internal reference validation."""


class ShapeIntegrityError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Shape integrity errors: {'; '.join(errors)}")


def validate_shape_integrity(shape_data: dict) -> None:
    """Validate all internal references within a shape artifact.
    Raises ShapeIntegrityError with a list of all violations.
    """
    shape = shape_data.get("shape", shape_data)
    errors: list[str] = []

    services = shape.get("services", [])
    service_ids = {s["id"] for s in services}
    concept_ids = {c["id"] for c in shape.get("domain_concepts", [])}

    # Enforce single_service / multi_service cardinality
    shape_type = shape.get("type")
    if shape_type == "single_service" and len(services) != 1:
        errors.append(f"single_service shape must have exactly 1 service, found {len(services)}")
    if shape_type == "multi_service" and len(services) < 2:
        errors.append(f"multi_service shape must have at least 2 services, found {len(services)}")

    # Check for duplicate IDs
    seen_services: set[str] = set()
    for s in shape.get("services", []):
        if s["id"] in seen_services:
            errors.append(f"duplicate service ID: {s['id']}")
        seen_services.add(s["id"])

    seen_concepts: set[str] = set()
    for c in shape.get("domain_concepts", []):
        if c["id"] in seen_concepts:
            errors.append(f"duplicate concept ID: {c['id']}")
        seen_concepts.add(c["id"])

    # Coordination edges must reference existing services
    for edge in shape.get("coordination", []):
        if edge["from"] not in service_ids:
            errors.append(f"coordination.from '{edge['from']}' is not a valid service ID")
        if edge["to"] not in service_ids:
            errors.append(f"coordination.to '{edge['to']}' is not a valid service ID")

    # Domain concept owners must reference services or "shared"
    for concept in shape.get("domain_concepts", []):
        owner = concept.get("owner")
        if owner and owner != "shared" and owner not in service_ids:
            errors.append(f"domain_concepts[{concept['id']}].owner '{owner}' is not a valid service ID")

    # owns_concepts must reference existing concept IDs
    for service in shape.get("services", []):
        for ref in service.get("owns_concepts", []):
            if ref not in concept_ids:
                errors.append(f"services[{service['id']}].owns_concepts '{ref}' is not a valid concept ID")

    if errors:
        raise ShapeIntegrityError(errors)
```

- [ ] **Step 2: Commit**

```bash
git add studio/server/shape_integrity.py
git commit -m "feat(studio-api): add shape-internal reference validation"
```

---

### Task 6: Contract Expectation Derivation

Deterministic rules that derive what ANIP semantics a shape + requirements combination implies.

**Files:**
- Create: `studio/server/derivation.py`

- [ ] **Step 1: Write the derivation engine**

```python
# studio/server/derivation.py
"""Deterministic contract expectation derivation from shape + requirements."""


def derive_contract_expectations(
    shape_data: dict,
    requirements_data: dict,
) -> list[dict]:
    """Derive expected ANIP semantics from shape + requirements.
    Returns a list of expectation dicts: {surface, reason, met: bool}
    """
    shape = shape_data.get("shape", shape_data)
    bc = requirements_data.get("business_constraints", {})
    audit = requirements_data.get("audit", {})
    permissions = requirements_data.get("permissions", {})
    expectations: list[dict] = []

    # Multi-service coordination implies cross-service surfaces
    coordination = shape.get("coordination", [])
    if coordination:
        expectations.append({
            "surface": "cross_service_handoff",
            "reason": "shape has coordination edges between services",
        })
        expectations.append({
            "surface": "cross_service_continuity",
            "reason": "cross-service coordination requires continuity",
        })

    # Verification coordination implies verify_via
    if any(e.get("relationship") == "verification" for e in coordination):
        expectations.append({
            "surface": "verify_via",
            "reason": "shape has a verification coordination edge",
        })

    # Async followup implies followup_via
    if any(e.get("relationship") == "async_followup" for e in coordination):
        expectations.append({
            "surface": "followup_via",
            "reason": "shape has an async followup coordination edge",
        })

    # Spending possible + shape has cost-bearing capabilities implies budget enforcement
    # This must inspect the shape, not just requirements — the design says derivation
    # comes from shape + requirements together, not requirements alone.
    all_capabilities = []
    for svc in shape.get("services", []):
        all_capabilities.extend(svc.get("capabilities", []))
    # NOTE: keyword matching is a first deterministic bridge. Later, capabilities
    # should gain an explicit cost_bearing: true classification on the shape service
    # so derivation is not name-sensitive. For now, this is acceptable.
    cost_bearing_keywords = {"book", "purchase", "pay", "deploy", "provision", "order"}
    has_cost_bearing = any(
        any(kw in cap.lower() for kw in cost_bearing_keywords)
        for cap in all_capabilities
    )

    if bc.get("spending_possible") and has_cost_bearing:
        expectations.append({
            "surface": "budget_enforcement",
            "reason": "requirements declare spending + shape has cost-bearing capabilities",
        })
    elif bc.get("cost_visibility_required") and has_cost_bearing:
        expectations.append({
            "surface": "budget_enforcement",
            "reason": "requirements declare cost visibility + shape has cost-bearing capabilities",
        })
    elif bc.get("spending_possible"):
        expectations.append({
            "surface": "budget_enforcement",
            "reason": "requirements declare spending (no cost-bearing capability found in shape — consider adding one)",
        })

    # Approval expected implies authority posture
    if bc.get("approval_expected_for_high_risk") or permissions.get("preflight_discovery"):
        expectations.append({
            "surface": "authority_posture",
            "reason": "requirements declare approval expectations or preflight discovery",
        })

    # Recovery sensitive implies recovery class
    if bc.get("recovery_sensitive") or bc.get("blocked_failure_posture"):
        posture = bc.get("blocked_failure_posture", "")
        if posture and posture != "not_specified":
            expectations.append({
                "surface": "recovery_class",
                "reason": f"requirements declare recovery sensitivity with {posture} posture",
            })
        else:
            expectations.append({
                "surface": "recovery_class",
                "reason": "requirements declare recovery sensitivity",
            })

    # High-sensitivity concepts imply authority posture
    concepts = shape.get("domain_concepts", [])
    high_sensitivity = [c for c in concepts if c.get("sensitivity") == "high"]
    if high_sensitivity and not any(e["surface"] == "authority_posture" for e in expectations):
        names = ", ".join(c["name"] for c in high_sensitivity)
        expectations.append({
            "surface": "authority_posture",
            "reason": f"high-sensitivity concepts: {names}",
        })

    # Cross-service reconstruction
    if audit.get("durable") and audit.get("cross_service_reconstruction_required"):
        expectations.append({
            "surface": "cross_service_reconstruction",
            "reason": "requirements declare durable audit with cross-service reconstruction",
        })

    return expectations
```

- [ ] **Step 2: Commit**

```bash
git add studio/server/derivation.py
git commit -m "feat(studio-api): add deterministic contract expectation derivation"
```

---

### Task 7: Repository — Shape CRUD

**Files:**
- Modify: `studio/server/repository.py`
- Modify: `studio/server/models.py`

- [ ] **Step 1: Add shape Pydantic models**

Add to `models.py`:
- `CreateShape(id, title, requirements_id, data: dict)`
- `UpdateShape(title?, status?, data?)`
- `ShapeOut(ArtifactOut + requirements_id)`
- Update `EvaluationOut` with optional `shape_id`, `shape_hash`, `derived_expectations`
- Update `CreateEvaluation` with optional `shape_id`

- [ ] **Step 2: Add shape repository functions**

Add to `repository.py`:
- `list_shapes(conn, project_id)` — list all shapes for a project
- `get_shape(conn, project_id, shape_id)` — get one shape
- `create_shape(conn, project_id, shape_id, requirements_id, title, data)` — validates shape integrity, computes content_hash, checks requirements_id coherence
- `update_shape(conn, project_id, shape_id, updates)` — revalidates integrity if data changes, recomputes content_hash
- `delete_shape(conn, project_id, shape_id)` — blocked if evaluations reference it (409)

Shape creation calls `validate_shape_integrity(data)` before insert. On integrity violation, raises 422.

Update `create_evaluation()` to optionally accept `shape_id` (and `shape_hash`, `derived_expectations`). When shape_id is provided, proposal_id can be null.

- [ ] **Step 3: Commit**

```bash
git add studio/server/repository.py studio/server/models.py
git commit -m "feat(studio-api): add shape CRUD to repository"
```

---

### Task 8: Shape API Router

**Files:**
- Create: `studio/server/routers/shapes.py`
- Modify: `studio/server/app.py`

- [ ] **Step 1: Write the shapes router**

CRUD for `/api/projects/{pid}/shapes`:
- `GET /api/projects/{pid}/shapes` → list
- `POST /api/projects/{pid}/shapes` → create (validates schema + integrity + coherence)
- `GET /api/projects/{pid}/shapes/{id}` → get
- `PUT /api/projects/{pid}/shapes/{id}` → update
- `DELETE /api/projects/{pid}/shapes/{id}` → delete (409 if evaluations reference it)

Add a derivation endpoint:
- `GET /api/projects/{pid}/shapes/{id}/expectations` → runs `derive_contract_expectations(shape.data, requirements.data)` and returns the list

Error handling: same pattern as artifacts router (404, 409, 422).

- [ ] **Step 2: Wire into app.py**

Add shapes router to app includes.

- [ ] **Step 3: Verify sidecar starts**

- [ ] **Step 4: Commit**

```bash
git add studio/server/routers/shapes.py studio/server/app.py
git commit -m "feat(studio-api): add shape API routes with derivation endpoint"
```

---

### Task 9: Backend Tests — Shapes, Integrity, Derivation

**Files:**
- Create: `studio/server/test_shapes.py`

- [ ] **Step 1: Write shape tests**

Test cases:
- Create shape with valid services and concepts → 201
- Create shape with broken coordination edge (references nonexistent service) → 422
- Create shape with broken owns_concepts (references nonexistent concept) → 422
- Create shape with broken domain_concepts owner (not a service ID or "shared") → 422
- Create shape with duplicate service IDs → 422
- Update shape data → content_hash changes
- Delete shape blocked by evaluation → 409
- List shapes returns all for project
- Create evaluation with shape_id (no proposal_id) → 201
- Derivation endpoint returns expected expectations based on shape + requirements
- Derivation: multi-service shape with coordination → cross_service_handoff expected
- Derivation: spending_possible requirement → budget_enforcement expected
- Derivation: high-sensitivity concept → authority_posture expected

- [ ] **Step 2: Run all backend tests**

Run: `cd /Users/samirski/Development/ANIP && DATABASE_URL=postgresql://anip:anip@localhost:5432/anip_studio /tmp/anip-venv/bin/python3 -m pytest studio/server/ -v 2>&1 | tail -40`

- [ ] **Step 3: Commit**

```bash
git add studio/server/test_shapes.py
git commit -m "test(studio-api): add shape CRUD, integrity, and derivation tests"
```

---

### Task 10: Frontend Types and API — Shapes

**Files:**
- Create: `studio/src/design/shape-types.ts`
- Modify: `studio/src/design/project-api.ts`
- Modify: `studio/src/design/project-types.ts`
- Modify: `studio/src/design/project-store.ts`

- [ ] **Step 1: Write shape types**

```typescript
// studio/src/design/shape-types.ts

export interface ShapeService {
  id: string
  name: string
  role: string
  responsibilities?: string[]
  capabilities?: string[]
  owns_concepts?: string[]
}

export interface CoordinationEdge {
  from: string
  to: string
  relationship: 'handoff' | 'verification' | 'async_followup'
  description?: string
}

export interface DomainConcept {
  id: string
  name: string
  meaning: string
  owner?: string
  sensitivity?: 'none' | 'medium' | 'high'
  risk_note?: string
}

export interface ShapeData {
  id: string
  name: string
  type: 'single_service' | 'multi_service'
  notes?: string[]
  services: ShapeService[]
  coordination?: CoordinationEdge[]
  domain_concepts?: DomainConcept[]
}

export interface DerivedExpectation {
  surface: string
  reason: string
}
```

- [ ] **Step 2: Update project-types.ts with all shape-related changes**

```typescript
// Add ShapeRecord
export interface ShapeRecord extends ArtifactRecord {
  requirements_id: string
}

// Update ProjectDetail — add shapes_count
export interface ProjectDetail extends ProjectSummary {
  requirements_count: number
  scenarios_count: number
  proposals_count: number
  evaluations_count: number
  shapes_count: number              // NEW
}

// Update EvaluationRecord — shape fields + optional proposal
export interface EvaluationRecord {
  id: string
  project_id: string
  proposal_id: string | null        // NOW OPTIONAL — null for shape-backed evaluations
  scenario_id: string
  requirements_id: string
  shape_id: string | null           // NEW — set for shape-backed evaluations
  result: string
  source: string
  data: Record<string, any>
  input_snapshot: Record<string, any>
  requirements_hash: string
  proposal_hash: string
  scenario_hash: string
  shape_hash: string                // NEW
  derived_expectations: Record<string, any> | null  // NEW — snapshot of derived expectations at eval time
  is_stale: boolean
  stale_artifacts: string[]
  created_at: string
}
```

- [ ] **Step 3: Add shape API functions**

Add to `project-api.ts`:
- `listShapes(pid)`, `getShape(pid, id)`, `createShape(pid, data)`, `updateShape(pid, id, data)`, `deleteShape(pid, id)`
- `getShapeExpectations(pid, id)` → `GET /api/projects/{pid}/shapes/{id}/expectations`

- [ ] **Step 4: Add shape state to project store — shape-first transition**

Add to `project-store.ts`:
- `artifacts.shapes: ShapeRecord[]` in state
- `activeShapeId: string | null`
- Load shapes in `loadProject()` (alongside other artifact lists)
- `setActiveShape(id)` function
- **Shape-first active context**: `loadProject()` auto-selects `activeShapeId` (if shapes exist) instead of `activeProposalId`. `activeProposalId` is only auto-selected if no shapes exist (legacy project).
- **Evaluation save path**: the store's evaluation-save helpers check `activeShapeId` first. If set, evaluation is saved with `shape_id` and `proposal_id = null`. If not set, falls back to `activeProposalId` (legacy).
- **Stale detection**: for shape-backed evaluations, staleness includes `shape_hash` comparison alongside requirements/scenario hashes.

- [ ] **Step 5: Verify**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`

- [ ] **Step 6: Commit**

```bash
git add studio/src/design/shape-types.ts studio/src/design/project-api.ts studio/src/design/project-types.ts studio/src/design/project-store.ts
git commit -m "feat(studio): add shape types, API client, and store state"
```

---

### Task 11: ShapeView, Evaluation Transition, and UI Shape-First Pivot

The primary design view + full transition of evaluation and navigation from proposal-centric to shape-centric.

**Files:**
- Create: `studio/src/views/ShapeView.vue`
- Modify: `studio/src/router.ts`
- Modify: `studio/src/App.vue`
- Modify: `studio/src/views/ProjectOverviewView.vue`
- Modify: `studio/src/views/EvaluationView.vue`

- [ ] **Step 1: Write ShapeView**

A Vue SFC that displays and edits a shape artifact:
- **Header**: shape name, type badge (single/multi), status
- **Notes section**: authored design rationale (editable string list)
- **Services section**: card per service showing name, role, responsibilities, capabilities, owned concepts. Editable in draft mode.
- **Coordination section**: edges between services (from → to, relationship type, description). Editable in draft mode.
- **Domain Concepts section**: table of concepts with name, meaning, owner, sensitivity, risk_note. Editable in draft mode.
- **Derived Contract Expectations panel**: read-only panel that calls the derivation endpoint and shows what ANIP semantics the shape implies. Each expectation shows the surface name and the reason it's needed.

Follow existing Studio design patterns (dark theme, CSS variables, EditorToolbar for draft management).

- [ ] **Step 2: Add shape route**

Add to `router.ts` in the project routes:
```typescript
{
  path: '/design/projects/:projectId/shapes/:id',
  name: 'shape',
  component: () => import('./views/ShapeView.vue'),
}
```

- [ ] **Step 3: Update sidebar — Shape replaces Proposal for shape-first projects**

In `App.vue`, update `designNavItems`:
- If the active project has shapes (`projectStore.artifacts.shapes.length > 0`): show Shape link, do NOT show Proposal link
- If the active project has proposals but no shapes (legacy): show Proposal link, do NOT show Shape link
- This ensures only one design artifact type appears in the nav at a time

```typescript
const hasShapes = projectStore.artifacts.shapes.length > 0
if (hasShapes && projectStore.activeShapeId) {
  items.push({ name: 'shape', label: 'Shape', icon: '\u{1F3D7}', path: `/design/projects/${pid}/shapes/${projectStore.activeShapeId}` })
} else if (!hasShapes && projectStore.activeProposalId) {
  items.push({ name: 'proposal', label: 'Proposal', icon: '\u{1F4A1}', path: `/design/projects/${pid}/proposals/${projectStore.activeProposalId}` })
}
```

- [ ] **Step 4: Update ProjectOverviewView — shape-first, proposal legacy**

- **Shape section** at top (if shapes exist or if creating a new project): show shape cards, "Create Shape" button
- **Proposal section** only shown if project has proposals but no shapes, labeled "Approach (Legacy)" with a note: "This project uses the legacy approach model. Create a Shape to use the new design workflow."
- For projects with shapes: do NOT show "Create Proposal" button

- [ ] **Step 5: Update EvaluationView — shape-backed save path**

Update the "Save to Project" flow in EvaluationView:
- If `projectStore.activeShapeId` is set: save evaluation with `shape_id`, `shape_hash` (from the shape's `content_hash`), `derived_expectations` (call derivation endpoint and snapshot the result), and `proposal_id = null`
- If `activeShapeId` is NOT set but `activeProposalId` IS set: legacy path (save with `proposal_id`, no shape fields)
- If neither is set: show "Select a shape or approach before saving"

Update staleness display:
- Shape-backed evaluations check staleness against `requirements_hash`, `scenario_hash`, and `shape_hash`
- `stale_artifacts` may include `"shape"` alongside `"requirements"` and `"scenario"`

- [ ] **Step 6: Verify**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit 2>&1 | head -20`
Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run 2>&1 | tail -10`
Run: `cd /Users/samirski/Development/ANIP/studio && npm run build 2>&1 | tail -10`

- [ ] **Step 7: Commit**

```bash
git add studio/src/views/ShapeView.vue studio/src/views/EvaluationView.vue studio/src/router.ts studio/src/App.vue studio/src/views/ProjectOverviewView.vue
git commit -m "feat(studio): add ShapeView, shape-first evaluation, and proposal demotion"
```

---

### Task 12: Integration Verification

- [ ] **Step 1: Run all backend tests**

Run: `cd /Users/samirski/Development/ANIP && DATABASE_URL=postgresql://anip:anip@localhost:5432/anip_studio /tmp/anip-venv/bin/python3 -m pytest studio/server/ tooling/tests/test_evaluator.py -v 2>&1 | tail -40`

- [ ] **Step 2: Run frontend tests**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vitest run 2>&1 | tail -10`

- [ ] **Step 3: Type-check and build**

Run: `cd /Users/samirski/Development/ANIP/studio && npx vue-tsc --noEmit && npm run build 2>&1 | tail -15`

- [ ] **Step 4: Fix any issues**

- [ ] **Step 5: Commit fixes**

---

### Task 13: Sync Embedded Assets

- [ ] **Step 1: Run sync**

Run: `cd /Users/samirski/Development/ANIP/studio && bash sync.sh`

- [ ] **Step 2: Commit if changed**

```bash
git add packages/
git commit -m "build(studio): sync embedded assets after service-shaping Phase A+B"
```
