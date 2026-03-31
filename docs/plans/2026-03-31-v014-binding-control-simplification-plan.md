# ANIP v0.14: Binding/Control Simplification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `bound_reference` and `freshness_window` from `control_requirements` — `requires_binding` is the sole home for binding semantics, `control_requirements` keeps only non-binding controls (`cost_ceiling`, `stronger_delegation_required`).

**Architecture:** Pure removal. Delete the two overlapping control requirement types from the schema, spec, all 5 runtime enforcement paths, tests, and docs. No new features. `requires_binding` already handles binding presence and staleness — the duplicate paths in `control_requirements` are deleted.

**Tech Stack:** Python, TypeScript, Go, Java, C# runtimes + JSON Schema + SPEC.md + Website docs

**Spec:** `/Users/samirski/Development/codex/ANIP/docs/anip-v014-binding-control-simplification-note.md`

---

## File Structure

```
# Spec and Schema
SPEC.md                                                        # MODIFY: remove bound_reference/freshness_window from control_requirements
schema/anip.schema.json                                        # MODIFY: remove from ControlRequirementType enum, update descriptions

# Python
packages/python/anip-core/src/anip_core/models.py             # MODIFY: update ControlRequirement type comment
packages/python/anip-service/src/anip_service/service.py       # MODIFY: remove bound_reference/freshness_window cases
packages/python/anip-service/tests/test_control_requirements.py # MODIFY: remove 4 tests

# TypeScript
packages/typescript/core/src/models.ts                         # MODIFY: update ControlRequirement comment
packages/typescript/service/src/service.ts                     # MODIFY: remove bound_reference/freshness_window cases

# Go
packages/go/service/invoke.go                                  # MODIFY: remove bound_reference/freshness_window cases

# Java
packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java  # MODIFY: remove cases

# C#
packages/csharp/src/Anip.Service/AnipService.cs                # MODIFY: remove cases

# Website
website/docs/protocol/capabilities.md                          # MODIFY: remove from control_requirements table/examples
website/docs/protocol/reference.md                             # MODIFY: remove invoke-evaluable mention
website/docs/protocol/failures-cost-audit.md                   # MODIFY: update control_requirement_unsatisfied description
website/docs/feature-map.md                                    # MODIFY: update control requirements row

# Studio
studio/src/components/CapabilityCard.vue                       # MODIFY: remove field/max_age rendering from control_requirements
```

---

## Task 1: Spec and Schema

**Files:**
- Modify: `SPEC.md`
- Modify: `schema/anip.schema.json`

- [ ] **Step 1: Update SPEC.md**

Remove `bound_reference` and `freshness_window` from §4.1 (Capability Declaration) control_requirements.

In the control_requirements section (~lines 80-133), remove:
- The `bound_reference` YAML example and description line
- The `freshness_window` YAML example and description line
- The table rows for `bound_reference` and `freshness_window`
- The `field` column note "For `bound_reference`, `freshness_window`" → just remove the field/max_age rows since they're only needed for those types
- The invoke-evaluable category mention — control_requirements are now ALL token-evaluable

Update the type enum to only: `cost_ceiling`, `stronger_delegation_required`.

Update the `ControlRequirement` field table:
- `type`: "One of: `cost_ceiling`, `stronger_delegation_required`"
- Remove `field` and `max_age` rows (no longer needed — those were only for bound_reference/freshness_window)

Update §4.4 (Permission Discovery) text that mentions invoke-evaluable controls — since all control requirements are now token-evaluable, remove the "Invoke-evaluable controls (`bound_reference`, `freshness_window`) are NOT included" caveat (~line 254).

Also update the feature status table (~line 1911) — remove "invoke-evaluable" mention, update to say all control requirements are token-evaluable and surfaced in `/anip/permissions`.

- [ ] **Step 2: Update JSON Schema**

In `schema/anip.schema.json`, modify the `ControlRequirementType` enum (~lines 113-118):

Remove `"bound_reference"` and `"freshness_window"` from the enum array, leaving only:
```json
"enum": ["cost_ceiling", "stronger_delegation_required"]
```

Update the `ControlRequirementType` description to remove the invoke-evaluable mention.

Remove `field` and `max_age` from the `ControlRequirement` properties (they were only used by the removed types). Update `required` to just `["type", "enforcement"]`.

- [ ] **Step 3: Commit**

```bash
git add SPEC.md schema/anip.schema.json
git commit -m "spec: remove bound_reference and freshness_window from control_requirements (v0.14)"
```

---

## Task 2: Python Runtime

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/python/anip-service/tests/test_control_requirements.py`

- [ ] **Step 1: Remove `field` and `max_age` from ControlRequirement model**

In `models.py` (~line 161), strip the model down to just `type` and `enforcement`. Remove `field` and `max_age` entirely — they only existed for `bound_reference`/`freshness_window`:

```python
class ControlRequirement(BaseModel):
    type: str  # "cost_ceiling", "stronger_delegation_required"
    enforcement: str = "reject"
```

- [ ] **Step 2: Remove enforcement cases in service.py**

In `service.py` (~lines 934-942), find the control requirement enforcement loop. Remove the `elif req.type == "bound_reference"` and `elif req.type == "freshness_window"` branches entirely. The loop should only handle `cost_ceiling` and `stronger_delegation_required`.

Before:
```python
if req.type == "cost_ceiling":
    satisfied = effective_budget is not None
elif req.type == "bound_reference":
    satisfied = req.field is not None and req.field in params and params[req.field] is not None
elif req.type == "freshness_window":
    if req.field and req.field in params:
        age = _resolve_binding_age(params[req.field])
        max_age = _parse_iso8601_duration(req.max_age) if req.max_age else None
        satisfied = age is None or max_age is None or age <= max_age
    else:
        satisfied = False
elif req.type == "stronger_delegation_required":
    ...
```

After:
```python
if req.type == "cost_ceiling":
    satisfied = effective_budget is not None
elif req.type == "stronger_delegation_required":
    ...
```

- [ ] **Step 3: Remove 4 tests from test_control_requirements.py**

Remove these test functions:
- `test_bound_reference_required_present`
- `test_bound_reference_required_missing`
- `test_freshness_window_within`
- `test_freshness_window_exceeded`

Keep the remaining tests:
- `test_cost_ceiling_required_with_budget`
- `test_cost_ceiling_required_without_budget`
- `test_unmet_token_requirements_in_permissions`

- [ ] **Step 4: Add `stronger_delegation_required` test**

Add a test that verifies `stronger_delegation_required` control requirement enforcement:
- `test_stronger_delegation_required_satisfied` — token has explicit capability binding → success
- `test_stronger_delegation_required_unsatisfied` — token purpose.capability doesn't match → `control_requirement_unsatisfied`

This is the other surviving control requirement type and needs direct coverage.

- [ ] **Step 4: Run Python tests**

```bash
cd /Users/samirski/Development/ANIP && python -m pytest packages/python/anip-service/tests/test_control_requirements.py -x -v --timeout=30
```

- [ ] **Step 5: Commit**

```bash
git add packages/python/
git commit -m "feat(python): remove bound_reference/freshness_window from control_requirements (v0.14)"
```

---

## Task 3: TypeScript Runtime

**Files:**
- Modify: `packages/typescript/core/src/models.ts`
- Modify: `packages/typescript/service/src/service.ts`

- [ ] **Step 1: Remove `field` and `max_age` from ControlRequirement in models.ts**

Strip the Zod schema to just `type` and `enforcement`. Remove `field` and `max_age` properties. Update the type comment:
```typescript
type: z.string(),        // "cost_ceiling", "stronger_delegation_required"
enforcement: z.string().default("reject"),
```

- [ ] **Step 2: Remove enforcement cases in service.ts**

Find the control requirement enforcement loop (~lines 1324-1327). Remove the `bound_reference` and `freshness_window` branches.

- [ ] **Step 3: Run TypeScript tests**

```bash
cd /Users/samirski/Development/ANIP/packages/typescript && npx vitest run
```

- [ ] **Step 4: Commit**

```bash
git add packages/typescript/
git commit -m "feat(typescript): remove bound_reference/freshness_window from control_requirements (v0.14)"
```

---

## Task 4: Go Runtime

**Files:**
- Modify: `packages/go/core/models.go`
- Modify: `packages/go/service/invoke.go`

- [ ] **Step 1: Remove `Field` and `MaxAge` from ControlRequirement struct in models.go**

Strip the struct to just `Type` and `Enforcement`. Remove `Field` and `MaxAge` fields.

- [ ] **Step 2: Remove enforcement cases in invoke.go**

Find the control requirement switch statement (~lines 546-553). Remove the `case "bound_reference"` and `case "freshness_window"` branches.

- [ ] **Step 3: Run Go tests**

```bash
cd /Users/samirski/Development/ANIP/packages/go && go test ./... -count=1
```

- [ ] **Step 4: Commit**

```bash
git add packages/go/
git commit -m "feat(go): remove bound_reference/freshness_window from control_requirements (v0.14)"
```

---

## Task 5: Java Runtime

**Files:**
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/ControlRequirement.java`
- Modify: `packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java`

- [ ] **Step 1: Remove `field` and `maxAge` from ControlRequirement.java**

Remove the `field` and `maxAge` properties, their getters, setters, and constructor parameters. Keep only `type` and `enforcement`.

- [ ] **Step 2: Remove enforcement cases in ANIPService.java**

Find the control requirement switch (~lines 553-561). Remove the `case "bound_reference"` and `case "freshness_window"` branches.

- [ ] **Step 2: Run Java tests**

```bash
cd /Users/samirski/Development/ANIP/packages/java && mvn test -q
```

- [ ] **Step 3: Commit**

```bash
git add packages/java/
git commit -m "feat(java): remove bound_reference/freshness_window from control_requirements (v0.14)"
```

---

## Task 6: C# Runtime

**Files:**
- Modify: `packages/csharp/src/Anip.Core/ControlRequirement.cs`
- Modify: `packages/csharp/src/Anip.Service/AnipService.cs`

- [ ] **Step 1: Remove `Field` and `MaxAge` from ControlRequirement.cs**

Remove the `Field` and `MaxAge` properties. Keep only `Type` and `Enforcement`.

- [ ] **Step 2: Remove enforcement cases in AnipService.cs**

Find the control requirement switch (~lines 747-757). Remove the `case "bound_reference"` and `case "freshness_window"` branches.

- [ ] **Step 2: Run C# tests**

```bash
cd /Users/samirski/Development/ANIP/packages/csharp && dotnet test --verbosity minimal
```

- [ ] **Step 3: Commit**

```bash
git add packages/csharp/
git commit -m "feat(csharp): remove bound_reference/freshness_window from control_requirements (v0.14)"
```

---

## Task 7: Website Documentation

**Files:**
- Modify: `website/docs/protocol/capabilities.md`
- Modify: `website/docs/protocol/reference.md`
- Modify: `website/docs/protocol/failures-cost-audit.md`
- Modify: `website/docs/feature-map.md`

- [ ] **Step 1: Update capabilities.md**

Remove `bound_reference` and `freshness_window` from the control requirements table and JSON example. The table should only list `cost_ceiling` and `stronger_delegation_required`. Remove the `field` and `max_age` columns/rows that were specific to those types.

Remove the "invoke-evaluable" vs "token-evaluable" distinction — all control requirements are now token-evaluable.

- [ ] **Step 2: Update reference.md**

Remove the text (~line 406) that says "Invoke-evaluable requirements (`bound_reference`, `freshness_window`) cannot be checked without actual invocation parameters and are never surfaced in permission discovery."

Since all control requirements are now token-evaluable, update to say something like: "All control requirements are token-evaluable and are surfaced in permission discovery."

- [ ] **Step 3: Update failures-cost-audit.md**

Update the `control_requirement_unsatisfied` description (~line 63) to remove `bound_reference` and `freshness_window` from the example list:
```
e.g. `cost_ceiling`, `stronger_delegation_required`
```

Update the `binding_stale` description to remove the `freshness_window` reference.

- [ ] **Step 4: Update feature-map.md**

Update the control requirements row (~line 28) to only list `cost_ceiling` and `stronger_delegation_required`.

- [ ] **Step 5: Commit**

```bash
git add website/
git commit -m "docs(website): remove bound_reference/freshness_window from control_requirements docs (v0.14)"
```

---

## Task 8: Studio UI

**Files:**
- Modify: `studio/src/components/CapabilityCard.vue`

- [ ] **Step 1: Remove `field` and `max_age` rendering from control requirements**

In `CapabilityCard.vue` (~line 184), the control requirements section renders `req.field` and `req.max_age`. Since these fields no longer exist on ControlRequirement, remove those `v-if` spans. The type badge is the only remaining display element.

- [ ] **Step 2: Build and sync**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build && cd .. && bash studio/sync.sh
```

- [ ] **Step 3: Commit**

```bash
git add studio/ packages/*/studio/
git commit -m "feat(studio): remove field/max_age from control_requirements display (v0.14)"
```

---

## Task 9: Version Bump

- [ ] **Step 1: Bump protocol version to 0.14**

Update the `PROTOCOL_VERSION` constant in all 5 runtimes:
- `packages/python/anip-core/src/anip_core/constants.py`: `"anip/0.13"` → `"anip/0.14"`
- `packages/typescript/core/src/constants.ts`: `"anip/0.13"` → `"anip/0.14"`
- `packages/go/core/constants.go`: `"anip/0.13"` → `"anip/0.14"`
- `packages/java/anip-core/src/main/java/dev/anip/core/Constants.java`: `"anip/0.13"` → `"anip/0.14"`
- `packages/csharp/src/Anip.Core/Constants.cs`: `"anip/0.13"` → `"anip/0.14"`

Update the intentional constant-verification test in each runtime:
- `packages/python/anip-core/tests/test_models.py`: `"anip/0.13"` → `"anip/0.14"`
- `packages/typescript/core/tests/models.test.ts`: `"anip/0.13"` → `"anip/0.14"`
- `packages/go/core/models_test.go`: `"anip/0.13"` → `"anip/0.14"`
- `packages/java/anip-core/src/test/java/dev/anip/core/ConstantsTest.java`: `"anip/0.13"` → `"anip/0.14"`
- `packages/csharp/test/Anip.Core.Tests/ConstantsTests.cs`: `"anip/0.13"` → `"anip/0.14"`

Update the default in:
- `packages/python/anip-core/src/anip_core/models.py`: ANIPManifest default `"anip/0.13"` → `"anip/0.14"`
- `packages/typescript/core/src/models.ts`: Manifest default `"anip/0.13"` → `"anip/0.14"`

Update canonical protocol artifacts:
- `SPEC.md`: update spec title/header version reference to v0.14
- `schema/anip.schema.json`: update schema description/title to reference v0.14
- `schema/anip.schema.json`: update `$id` from `https://anip.dev/schema/v0.13/anip.schema.json` to `https://anip.dev/schema/v0.14/anip.schema.json`

Update website version references:
- All `0.13.0` → `0.14.0` in website docs (install, quickstart, transports, reference, capabilities)
- `website/docs/releases/version-history.md`: add v0.14 entry (simplification: removed bound_reference/freshness_window overlap from control_requirements)

- [ ] **Step 2: Commit**

```bash
git add SPEC.md schema/ packages/ website/
git commit -m "chore: bump protocol version to anip/0.14"
```
