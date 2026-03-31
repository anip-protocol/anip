# ANIP v0.15: Authority and Blocked-Action Clarity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make authority failures machine-readable and actionable — structured `reason_type` on permission responses, canonical authority-specific `resolution.action` values, `resolution_hint` on restricted capabilities, and a new `non_delegable_action` failure type.

**Architecture:** Additive changes only: (1) `reason_type` enum on RestrictedCapability/DeniedCapability classifies WHY authority is blocked (4 token-verifiable + 1 service-declared), (2) `resolution_hint` on RestrictedCapability tells agents what to do before invoking, (3) 3 new + 1 reused canonical `resolution.action` values for authority recovery, (4) `non_delegable_action` failure type for terminal blocks, (5) deprecate `request_scope_grant` in favor of `request_broader_scope`.

**Tech Stack:** Python, TypeScript, Go, Java, C# runtimes + JSON Schema + SPEC.md + Vue (Studio)

**Spec:** `docs/proposals/v0.15-slice2-authority-blocked-action-spec-draft.md`

---

## File Structure

```
# Spec and Schema
SPEC.md                                                        # MODIFY: §4.4 reason_type + resolution_hint; §4.5 non_delegable_action + canonical actions + deprecate request_scope_grant
schema/anip.schema.json                                        # MODIFY: add ReasonType enum; add fields to RestrictedCapability, DeniedCapability

# Python (reference implementation)
packages/python/anip-core/src/anip_core/models.py              # MODIFY: add reason_type, resolution_hint to RestrictedCapability; reason_type to DeniedCapability
packages/python/anip-server/src/anip_server/permissions.py     # MODIFY: populate reason_type + resolution_hint
packages/python/anip-service/src/anip_service/service.py       # MODIFY: add non_delegable_action failure; use canonical resolution.action; deprecate request_scope_grant
packages/python/anip-graphql/src/anip_graphql/translation.py   # MODIFY: add reasonType, resolutionHint to GraphQL SDL
packages/python/anip-service/tests/test_authority.py           # CREATE: reason_type + resolution_hint + non_delegable tests

# TypeScript
packages/typescript/core/src/models.ts                         # MODIFY: add fields to Zod schemas
packages/typescript/server/src/permissions.ts                   # MODIFY: populate reason_type (update PermissionResult interface too)
packages/typescript/service/src/service.ts                     # MODIFY: canonical actions + non_delegable_action
packages/typescript/graphql/src/translation.ts                 # MODIFY: add reasonType to GraphQL SDL

# Go
packages/go/core/models.go                                    # MODIFY: add fields to RestrictedCapability, DeniedCapability
packages/go/core/constants.go                                  # MODIFY: add FailureNonDelegableAction constant
packages/go/service/permissions.go                             # MODIFY: populate reason_type
packages/go/service/invoke.go                                  # MODIFY: canonical actions
packages/go/graphqlapi/translation.go                          # MODIFY: add reasonType to GraphQL SDL

# Java
packages/java/anip-core/src/main/java/dev/anip/core/PermissionResponse.java  # MODIFY: add fields to nested RestrictedCapability + DeniedCapability
packages/java/anip-core/src/main/java/dev/anip/core/Constants.java           # MODIFY: add FAILURE_NON_DELEGABLE_ACTION constant
packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java   # MODIFY: permissions + canonical actions
packages/java/anip-graphql/src/main/java/dev/anip/graphql/SchemaBuilder.java # MODIFY: add reasonType to GraphQL SDL

# C#
packages/csharp/src/Anip.Core/RestrictedCapability.cs          # MODIFY: add reason_type, resolution_hint
packages/csharp/src/Anip.Core/DeniedCapability.cs              # MODIFY: add reason_type (check if standalone or nested)
packages/csharp/src/Anip.Core/Constants.cs                     # MODIFY: add FailureNonDelegableAction constant
packages/csharp/src/Anip.Service/AnipService.cs                # MODIFY: permissions + canonical actions
packages/csharp/src/Anip.GraphQL/SchemaBuilder.cs              # MODIFY: add reasonType to GraphQL SDL

# Conformance
conformance/test_authority.py                                  # CREATE: reason_type + non_delegable conformance tests

# Showcase
examples/showcase/devops/capabilities.py                       # MODIFY: add non-delegable action scenario

# Studio
studio/src/components/CapabilityCard.vue                       # MODIFY: show reason_type badge on restricted/denied

# Website
website/docs/protocol/delegation-permissions.md                # MODIFY: add reason_type docs
website/docs/protocol/failures-cost-audit.md                   # MODIFY: add non_delegable_action + canonical actions
website/docs/protocol/reference.md                             # MODIFY: add new fields to response tables
website/docs/feature-map.md                                    # MODIFY: add v0.15 entries
website/docs/releases/version-history.md                       # MODIFY: add v0.15 entry
```

---

## Task 1: Spec and Schema

**Files:**
- Modify: `SPEC.md`
- Modify: `schema/anip.schema.json`

- [ ] **Step 1: Update SPEC.md §4.4 (Permission Discovery)**

Add `reason_type` vocabulary table (5 values):

| Value | Meaning | Where | Determined by |
|-------|---------|-------|--------------|
| `insufficient_scope` | Chain lacks required scope(s) | `restricted` | Token vs capability `minimum_scope` |
| `insufficient_delegation_depth` | Token at max depth | `restricted` | Token `constraints.max_delegation_depth` |
| `stronger_delegation_required` | Needs explicit capability binding | `restricted` | Token-evaluable control requirement |
| `unmet_control_requirement` | Token-evaluable control req not satisfied | `restricted` | Token vs capability `control_requirements` |
| `non_delegable` | Cannot be delegated — direct principal required | `denied` | Service-declared |

Add new fields:
- RestrictedCapability: `reason_type` (required string), `resolution_hint` (optional string)
- DeniedCapability: `reason_type` (required string)

Update permission discovery examples to include `reason_type` and `resolution_hint`.

- [ ] **Step 2: Update SPEC.md §4.5 (Failure Semantics)**

Add `non_delegable_action` failure type with `retry: false` and `resolution.action: "stop"`.

Add canonical authority-specific `resolution.action` values (table with Status column):

| Action | Status | When to use |
|--------|--------|------------|
| `request_broader_scope` | New | `insufficient_scope` |
| `request_new_delegation` | Existing (now canonical for depth) | `insufficient_delegation_depth` |
| `request_capability_binding` | New | `stronger_delegation_required` |
| `request_budget_bound_delegation` | Existing (from v0.14) | `unmet_control_requirement` (cost_ceiling) |
| `stop` | New | `non_delegable` |

Add deprecation note: `request_scope_grant` is DEPRECATED in favor of `request_broader_scope`.

State consistency rule: `resolution_hint` in permissions SHOULD match `resolution.action` in the invoke failure.

- [ ] **Step 3: Update JSON Schema**

Add `ReasonType` enum to `$defs` with the 5 values. Add `reason_type` (required) and `resolution_hint` (optional) to `RestrictedCapability`. Add `reason_type` (required) to `DeniedCapability`.

- [ ] **Step 4: Commit**

```bash
git add SPEC.md schema/anip.schema.json
git commit -m "spec: add reason_type, resolution_hint, non_delegable_action, canonical authority actions (v0.15)"
```

---

## Task 2: Python Reference Implementation

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/python/anip-server/src/anip_server/permissions.py`
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/python/anip-graphql/src/anip_graphql/translation.py`
- Create: `packages/python/anip-service/tests/test_authority.py`

- [ ] **Step 1: Add fields to models**

```python
class RestrictedCapability(BaseModel):
    capability: str
    reason: str
    grantable_by: str
    unmet_token_requirements: list[str] = Field(default_factory=list)
    reason_type: str  # REQUIRED — one of: insufficient_scope, insufficient_delegation_depth, stronger_delegation_required, unmet_control_requirement
    resolution_hint: str | None = None

class DeniedCapability(BaseModel):
    capability: str
    reason: str
    reason_type: str  # REQUIRED — currently: non_delegable
```

**No defaults for `reason_type`.** Every creation site MUST explicitly set the correct value. This prevents silent fallback to a plausible-but-wrong classifier.

- [ ] **Step 2: Populate reason_type in permissions.py**

Read `permissions.py` first. Find where RestrictedCapability and DeniedCapability are created. Set `reason_type` and `resolution_hint`:

- Missing scope → `reason_type="insufficient_scope"`, `resolution_hint="request_broader_scope"`
- Unmet control requirement (cost_ceiling) → `reason_type="unmet_control_requirement"`, `resolution_hint="request_budget_bound_delegation"`
- Unmet control requirement (stronger_delegation_required) → `reason_type="stronger_delegation_required"`, `resolution_hint="request_capability_binding"`
- Denied → `reason_type="non_delegable"`

- [ ] **Step 3: Add non_delegable_action failure type + canonical actions in service.py**

Add a constant or inline check. When a service wants to signal non-delegable, it returns:
```python
{
    "type": "non_delegable_action",
    "detail": "...",
    "resolution": {"action": "stop", "requires": "direct principal invocation"},
    "retry": False,
}
```

Update existing `resolution.action` values in scope-related failures from `request_scope_grant` to `request_broader_scope`. Keep both working but prefer the new canonical value.

- [ ] **Step 4: Update GraphQL SDL**

In `translation.py`, add `reasonType: String` and `resolutionHint: String` to the `RestrictedCapability` GraphQL type, and `reasonType: String` to `DeniedCapability`.

- [ ] **Step 5: Write tests**

Create `test_authority.py`:
- `test_restricted_has_reason_type` — permissions returns `reason_type` on restricted capabilities
- `test_reason_type_insufficient_scope` — missing scope → `reason_type="insufficient_scope"`
- `test_resolution_hint_on_restricted` — restricted capability has `resolution_hint`
- `test_denied_has_reason_type` — denied capabilities have `reason_type="non_delegable"`
- `test_resolution_hint_matches_invoke_action` — `resolution_hint` matches `resolution.action` on invoke failure
- `test_canonical_action_request_broader_scope` — scope failure uses `request_broader_scope`
- `test_non_delegable_action_not_used_yet` — verify new failure type exists as a constant (actual non-delegable scenarios depend on service config, tested via showcase)

- [ ] **Step 6: Run tests**

```bash
cd /Users/samirski/Development/ANIP && python -m pytest packages/python/ -x -v --timeout=30 2>&1 | tail -30
```

- [ ] **Step 7: Commit**

```bash
git add packages/python/
git commit -m "feat(python): add reason_type, resolution_hint, non_delegable_action, canonical actions (v0.15)"
```

---

## Task 3: TypeScript Runtime

**Files:**
- Modify: `packages/typescript/core/src/models.ts` — add `reasonType`, `resolutionHint` to RestrictedCapability Zod schema; `reasonType` to DeniedCapability
- Modify: `packages/typescript/server/src/permissions.ts` — populate reason_type (update PermissionResult interface AND Zod schemas)
- Modify: `packages/typescript/service/src/service.ts` — canonical actions + non_delegable_action failure
- Modify: `packages/typescript/graphql/src/translation.ts` — add reasonType to GraphQL SDL

- [ ] **Step 1: Add fields to models + permissions interface**
- [ ] **Step 2: Populate reason_type in permissions**
- [ ] **Step 3: Use canonical actions + add non_delegable_action**
- [ ] **Step 4: Update GraphQL SDL**
- [ ] **Step 5: Run tests**
```bash
cd /Users/samirski/Development/ANIP/packages/typescript && npx vitest run
```
- [ ] **Step 6: Commit**
```bash
git add packages/typescript/
git commit -m "feat(typescript): add reason_type, resolution_hint, canonical actions (v0.15)"
```

---

## Task 4: Go Runtime

**Files:**
- Modify: `packages/go/core/models.go` — add ReasonType, ResolutionHint to RestrictedCapability; ReasonType to DeniedCapability
- Modify: `packages/go/core/constants.go` — add `FailureNonDelegableAction` constant
- Modify: `packages/go/service/permissions.go` — populate reason_type
- Modify: `packages/go/service/invoke.go` — canonical actions
- Modify: `packages/go/graphqlapi/translation.go` — add reasonType to GraphQL SDL

- [ ] **Step 1: Add fields to models + constant**
- [ ] **Step 2: Populate reason_type in permissions**
- [ ] **Step 3: Use canonical actions**
- [ ] **Step 4: Update GraphQL SDL**
- [ ] **Step 5: Run tests**
```bash
cd /Users/samirski/Development/ANIP/packages/go && go test ./...
```
- [ ] **Step 6: Commit**
```bash
git add packages/go/
git commit -m "feat(go): add reason_type, resolution_hint, canonical actions (v0.15)"
```

---

## Task 5: Java Runtime

**Files:**
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/PermissionResponse.java` — add fields to nested RestrictedCapability + DeniedCapability
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/Constants.java` — add `FAILURE_NON_DELEGABLE_ACTION`
- Modify: `packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java` — permissions reason_type + canonical actions
- Modify: `packages/java/anip-graphql/src/main/java/dev/anip/graphql/SchemaBuilder.java` — add reasonType to SDL

- [ ] **Step 1: Add fields to nested permission classes + constant**
- [ ] **Step 2: Populate reason_type in permissions**
- [ ] **Step 3: Use canonical actions**
- [ ] **Step 4: Update GraphQL SDL**
- [ ] **Step 5: Run tests**
```bash
cd /Users/samirski/Development/ANIP/packages/java && mvn test -q
```
- [ ] **Step 6: Commit**
```bash
git add packages/java/
git commit -m "feat(java): add reason_type, resolution_hint, canonical actions (v0.15)"
```

---

## Task 6: C# Runtime

**Files:**
- Modify: `packages/csharp/src/Anip.Core/RestrictedCapability.cs` — add ReasonType, ResolutionHint
- Modify: `packages/csharp/src/Anip.Core/DeniedCapability.cs` — add ReasonType (check if standalone or create)
- Modify: `packages/csharp/src/Anip.Core/Constants.cs` — add FailureNonDelegableAction
- Modify: `packages/csharp/src/Anip.Service/AnipService.cs` — permissions reason_type + canonical actions
- Modify: `packages/csharp/src/Anip.GraphQL/SchemaBuilder.cs` — add reasonType to SDL

- [ ] **Step 1: Add fields to models + constant**
- [ ] **Step 2: Populate reason_type in permissions**
- [ ] **Step 3: Use canonical actions**
- [ ] **Step 4: Update GraphQL SDL**
- [ ] **Step 5: Run tests**
```bash
cd /Users/samirski/Development/ANIP/packages/csharp && dotnet test --verbosity minimal
```
- [ ] **Step 6: Commit**
```bash
git add packages/csharp/
git commit -m "feat(csharp): add reason_type, resolution_hint, canonical actions (v0.15)"
```

---

## Task 7: Conformance Suite

**Files:**
- Create: `conformance/test_authority.py`

- [ ] **Step 1: Write conformance tests**

- `test_restricted_has_reason_type` — restricted capabilities include `reason_type`
- `test_denied_has_reason_type` — denied capabilities include `reason_type`
- `test_scope_failure_uses_canonical_action` — scope failure's `resolution.action` MUST be `request_broader_scope` (conformance requires the canonical value; deprecated `request_scope_grant` is only tolerated in non-conformance contexts)
- `test_resolution_hint_present_on_restricted` — restricted capabilities with `reason_type` also have `resolution_hint`
- `test_non_delegable_failure_type` — if a non-delegable capability exists, invoking it returns `non_delegable_action` with `resolution.action: "stop"`

- [ ] **Step 2: Commit**
```bash
git add conformance/
git commit -m "test: add authority reason_type and non_delegable conformance tests (v0.15)"
```

---

## Task 8: Showcase — DevOps Non-Delegable

**Files:**
- Modify: `examples/showcase/devops/capabilities.py`

- [ ] **Step 1: Add non-delegable action**

Read `capabilities.py` first. Add a capability (e.g., `destroy_environment`) that is non-delegable: the handler checks if the caller is a delegated agent and returns `non_delegable_action` failure if so.

```python
# In the handler:
if ctx.subject != ctx.root_principal:
    raise ANIPError("non_delegable_action", "destroy_environment requires direct principal action and cannot be delegated")
```

- [ ] **Step 2: Commit**
```bash
git add examples/showcase/
git commit -m "feat(showcase): add non-delegable action to devops example (v0.15)"
```

---

## Task 9: Studio UI

**Files:**
- Modify: `studio/src/components/CapabilityCard.vue`

- [ ] **Step 1: Show reason_type on restricted/denied capabilities**

In the permissions display section of CapabilityCard (or wherever restricted/denied are rendered), add a `reason_type` badge. Use existing badge styling.

- [ ] **Step 2: Build and sync**
```bash
cd /Users/samirski/Development/ANIP/studio && npm run build && cd .. && bash studio/sync.sh
```
- [ ] **Step 3: Commit**
```bash
git add studio/ packages/*/studio/
git commit -m "feat(studio): show reason_type badge on restricted/denied capabilities (v0.15)"
```

---

## Task 10: Website Documentation

**Files:**
- Modify: `website/docs/protocol/delegation-permissions.md`
- Modify: `website/docs/protocol/failures-cost-audit.md`
- Modify: `website/docs/protocol/reference.md`
- Modify: `website/docs/feature-map.md`
- Modify: `website/docs/releases/version-history.md`

- [ ] **Step 1: Update delegation-permissions page**

Add `reason_type` vocabulary table (5 values with "Determined by" column), `resolution_hint` field, examples.

- [ ] **Step 2: Update failures page**

Add `non_delegable_action` failure type. Add canonical authority-specific `resolution.action` table (with Status column). Add deprecation note for `request_scope_grant`.

- [ ] **Step 3: Update reference page**

Add `reason_type` and `resolution_hint` to the permission response field table. Add `non_delegable_action` to the failure types list.

- [ ] **Step 4: Update feature map and version history**

Add v0.15 entries: reason_type vocabulary, resolution_hint, non_delegable_action, canonical authority actions, request_scope_grant deprecation.

- [ ] **Step 5: Commit**
```bash
git add website/
git commit -m "docs(website): add reason_type, resolution_hint, non_delegable_action documentation (v0.15)"
```

---

## Task 11: Version Bump

- [ ] **Step 1: Bump to anip/0.15**

Update all 5 runtime constants, constant-verification tests, model defaults, SPEC.md title, schema `$id`, website version references (`0.14.0` → `0.15.0`). Add v0.15 entry to version history.

- [ ] **Step 2: Commit**
```bash
git add SPEC.md schema/ packages/ website/
git commit -m "chore: bump protocol version to anip/0.15"
```
