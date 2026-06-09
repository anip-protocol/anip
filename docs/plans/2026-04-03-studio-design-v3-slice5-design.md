# Design V3 Slice 5: Workspace Hardening — Design Proposal

This proposal locks the open product decisions for Slice 5. Mechanical hardening work (DB constraints, import validation, operational reliability) is deferred to the implementation plan.

---

## 1. Evaluation Provenance and Staleness

### Per-Artifact Content Hashes

Every artifact record gains a `content_hash` column — a SHA-256 of its canonical JSON data, recomputed on every create and update:

```sql
ALTER TABLE requirements_sets ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE scenarios ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE proposals ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';
```

`content_hash = SHA-256(canonical_json(data))` where `canonical_json` = `json.dumps(data, sort_keys=True, separators=(',', ':'))`.

### Evaluation Input Hashes

Every stored evaluation records **three separate per-artifact hashes** captured at save time:

```sql
ALTER TABLE evaluations ADD COLUMN requirements_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE evaluations ADD COLUMN proposal_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE evaluations ADD COLUMN scenario_hash TEXT NOT NULL DEFAULT '';
```

These are copied from the linked artifacts' `content_hash` values at the moment the evaluation is saved. They live alongside the existing `input_snapshot` (which preserves the full artifact content).

### Staleness Detection

A stored evaluation is **stale** when any of its per-artifact hashes no longer matches the linked artifact's current `content_hash`. Staleness is per-artifact — the API reports exactly which artifacts changed.

**Both list and detail endpoints return staleness state:**

```
GET /api/projects/{pid}/evaluations
→ [{ ..., "is_stale": false, "stale_artifacts": [] }, ...]

GET /api/projects/{pid}/evaluations/{id}
→ { ..., "is_stale": true, "stale_artifacts": ["requirements", "scenario"] }
```

Implementation: when returning evaluations, join against the linked artifacts' current `content_hash` and compare:

```python
stale = []
if eval_row["requirements_hash"] != req_row["content_hash"]:
    stale.append("requirements")
if eval_row["proposal_hash"] != prop_row["content_hash"]:
    stale.append("proposal")
if eval_row["scenario_hash"] != scn_row["content_hash"]:
    stale.append("scenario")
is_stale = len(stale) > 0
```

This is a read-time computation — no background jobs or triggers needed.

### Reevaluation

Reevaluation always creates a **new** evaluation record. It never overwrites the previous one. The UI shows a "Re-evaluate" button on stale evaluations that:

1. Runs `POST /api/validate` with the current artifact state
2. Saves the result as a new evaluation with `source: 'live_validation'`, fresh per-artifact hashes, and fresh `input_snapshot`

The old evaluation remains in the project history.

### UI Badges

| State | Badge | Color | Meaning |
|-------|-------|-------|---------|
| Live validation result (not saved) | **Live** | Blue | Transient, not persisted |
| Stored, all hashes match | **Stored** | Green | Persisted, still current |
| Stored, at least one hash differs | **Stale** | Amber | Persisted but inputs have changed since |

Stale badges appear in:
- Project overview evaluation list
- Evaluation detail view header
- Evaluation detail shows which specific artifacts changed

---

## 2. Workspace Semantics — Primary vs Alternative Requirements

### Data Model

Add a `role` column to `requirements_sets`:

```sql
ALTER TABLE requirements_sets ADD COLUMN role TEXT NOT NULL DEFAULT 'primary'
    CHECK (role IN ('primary', 'alternative'));
```

**Constraint:** At most one `primary` requirements set per project. Enforced via:

```sql
CREATE UNIQUE INDEX idx_requirements_primary_per_project
    ON requirements_sets(project_id) WHERE role = 'primary';
```

When a project is created with its first requirements set, it's automatically `primary`. Additional requirements sets are `alternative` by default. The user can promote an alternative to primary (which demotes the current primary to alternative).

### Active Context Model

The active design context becomes more structured:

```
activeContext = {
  requirementsId: string | null    // selected requirements set
  proposalId: string | null        // selected proposal (tied to requirements)
  scenarioId: string | null        // currently viewed/evaluated scenario
}
```

**Auto-selection rule:** When a project has exactly one primary requirements set and exactly one proposal for that requirements set, both are auto-selected. The user only needs to choose a scenario.

**UI:**
- Project overview shows the primary requirements set prominently at the top
- Alternative requirements sets appear in a collapsible "Alternatives" section below
- The active context bar (in the sidebar or project header) always shows the current selection: Requirements → Proposal → Scenario
- No hidden context — if something is null, it shows "Not selected"

### Scenario Role

Scenarios don't need a `role` column — multiple scenarios per project is the normal case. They're evaluated one at a time against the active requirements + proposal pair.

---

## 3. Vocabulary Grounding — Evaluator Recognition

### Recognition Flag

Add an `evaluator_recognized` boolean to the vocabulary table:

```sql
ALTER TABLE vocabulary ADD COLUMN evaluator_recognized BOOLEAN NOT NULL DEFAULT FALSE;
```

Canonical vocabulary entries that the evaluator actually consumes are marked `evaluator_recognized = TRUE`. The vocabulary defaults JSON gains this field:

```json
{ "category": "anip_support", "value": "cost_visibility", "origin": "canonical", "evaluator_recognized": true }
{ "category": "behavior", "value": "custom_something", "origin": "project", "evaluator_recognized": false }
```

### UI Treatment

| Origin | Evaluator Recognized | Chip Appearance |
|--------|---------------------|-----------------|
| Canonical + recognized | Yes | Solid border, normal text |
| Canonical + NOT recognized | No | Solid border, subtle "not evaluated" indicator |
| Project | No (always) | Dashed border, "project" badge |
| Custom | No (always) | Muted, "custom" badge |

When a user adds a custom `expected_anip_support` entry that the evaluator doesn't recognize, the hints engine shows:

> "1 custom ANIP support entry may not affect evaluation results."

This is advisory — the entry is still valid and stored. But the user knows the evaluator won't use it.

### What Changes for the User

Today, all canonical suggestions look equally important. After Slice 5:
- A PM can see which entries actually feed into validation results
- Custom entries are clearly labeled as "stored but not evaluated"
- No false confidence that writing something in the UI means it gets validated

---

## 4. Evaluator Alignment — First Consumption Set

### Fields to Add to the Evaluator

These 5 `business_constraints` fields from the guided requirements flow should become evaluator-consumed in Slice 5. **All checks are against structured fields only** — the evaluator must NOT interpret free-text `expected_behavior` or `expected_anip_support` strings for these rules. Checks run against `declared_surfaces`, `scenario.context`, and the structured `business_constraints` fields themselves.

| Field | How the Evaluator Should Use It |
|-------|-------------------------------|
| `spending_possible` | In safety evaluation: if `true` and `scenario.context.expected_cost` or `scenario.context.budget_limit` is present, check that `declared_surfaces.budget_enforcement` is `true`. If `spending_possible` but no cost/budget context in the scenario, add to `what_would_improve`. |
| `approval_expected_for_high_risk` | In safety evaluation: if `true`, check that `declared_surfaces.authority_posture` is `true`. If not declared, add to `what_would_improve`. |
| `recovery_sensitive` | In recovery evaluation: if `true`, check that `declared_surfaces.recovery_class` is `true`. If not declared, add to `what_would_improve`. |
| `blocked_failure_posture` | In recovery evaluation: if value is `retry_with_backoff` / `escalate_to_human` / `fail_safe`, check that `declared_surfaces.recovery_class` is `true`. The specific posture value is noted in the evaluation output but NOT matched against free-text entries. |
| `cost_visibility_required` | In safety evaluation: if `true`, check that `declared_surfaces.budget_enforcement` is `true` (budget enforcement implies cost visibility). Do NOT check for a `cost_visibility` surface — it doesn't exist in the current schema. |

### Fields NOT Added Yet

These fields remain stored but not evaluator-consumed in Slice 5:

| Field | Reason |
|-------|--------|
| `irreversible_actions_present` | Already captured via `risk_profile.*.side_effect` which the evaluator does consume indirectly through declared_surfaces. Adding it would duplicate logic. |
| `restricted_vs_denied` | Permission model nuance — evaluator currently checks `preflight_discovery` and `grantable_requirements`. Adding restricted/denied distinction requires deeper permission-model evaluation that's better suited for Slice 6. |
| `delegation_tokens` | Auth mechanism detail — evaluator doesn't currently model token delegation flows. |
| `service_to_service_handoffs` | Already covered by cross-service evaluation category. The flag is redundant with the scenario category. |

### Implementation Approach

The evaluator changes are in `tooling/bin/anip_design_validate.py`. Each category evaluator gains a small block that reads the new `business_constraints` fields:

```python
# In evaluate_safety():
bc = requirements.get("business_constraints", {})
if bc.get("spending_possible"):
    # Check budget-related surfaces and scenario context
    ...
if bc.get("approval_expected_for_high_risk"):
    # Check authority-posture surfaces
    ...
```

The evaluator output should note when a business constraint is declared but the scenario/proposal don't fully address it — this becomes a `what_would_improve` entry, not a hard failure.

### Vocabulary Update

After the evaluator gains these consumption rules, the canonical vocabulary defaults update their `evaluator_recognized` flags:

```json
{ "category": "context_key", "value": "expected_cost", "evaluator_recognized": true }
{ "category": "behavior", "value": "do_not_execute", "evaluator_recognized": true }
```

The evaluator alignment and vocabulary recognition flags should be kept in sync by convention — when the evaluator gains a new consumption rule, the vocabulary defaults are updated in the same commit.

---

## 5. Decision Summary

| Decision | Choice |
|----------|--------|
| Hash algorithm | SHA-256 of canonical JSON (`sort_keys=True, separators=(',',':')`) |
| Hash storage | Per-artifact: `content_hash` on each artifact record + `requirements_hash`/`proposal_hash`/`scenario_hash` on each evaluation |
| Staleness trigger | Any evaluation's per-artifact hash differs from the linked artifact's current `content_hash` |
| Staleness API | `is_stale` + `stale_artifacts` returned on both list and detail evaluation endpoints |
| Reevaluation behavior | New record, never overwrite |
| Requirements role model | `primary` / `alternative` with partial unique index |
| Active context structure | requirementsId + proposalId + scenarioId, all visible |
| Vocabulary recognition | `evaluator_recognized` boolean column |
| First evaluator alignment set | `spending_possible`, `approval_expected_for_high_risk`, `recovery_sensitive`, `blocked_failure_posture`, `cost_visibility_required` |
| Evaluator check constraint | Structured fields only — no free-text `expected_behavior` / `expected_anip_support` interpretation |
| Fields deferred | `irreversible_actions_present`, `restricted_vs_denied`, `delegation_tokens`, `service_to_service_handoffs` |
