# ANIP v0.16: Recovery Posture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `resolution.recovery_class` to failure responses — a 6-value advisory grouping that tells agents the category of recovery without changing existing `retry` semantics.

**Architecture:** One new required field on the `Resolution` object (`recovery_class`) with mandatory action→class mapping. Five new canonical actions (`retry_now`, `revalidate_state`, `provide_credentials`, `check_manifest`, `contact_service_owner`). Transport-layer ad-hoc actions (`provide_api_key`) replaced with canonical equivalents. All actions in the mapping table — no defaulting loophole. No new failure types, no permission discovery changes, no `retry` semantics changes.

**Tech Stack:** Python, TypeScript, Go, Java, C# runtimes + JSON Schema + SPEC.md + Vue (Studio)

**Spec:** `docs/proposals/v0.16-phase3-slice1-recovery-posture-spec-draft.md`

**Note:** Java and C# do NOT have gRPC transport layers — only Python and Go have gRPC.

---

## File Structure

```
# Spec and Schema
SPEC.md                                                        # MODIFY: §4.5 add recovery_class to Resolution, mapping table, retry_now + revalidate_state actions
schema/anip.schema.json                                        # MODIFY: add RecoveryClass enum, add recovery_class (required) to Resolution

# Python
packages/python/anip-core/src/anip_core/models.py              # MODIFY: add recovery_class to Resolution model
packages/python/anip-core/src/anip_core/constants.py            # MODIFY: add ACTION_RETRY_NOW, ACTION_REVALIDATE_STATE, RECOVERY_CLASS_MAP
packages/python/anip-server/src/anip_server/delegation.py       # MODIFY: add recovery_class to delegation failure responses
packages/python/anip-service/src/anip_service/service.py        # MODIFY: add recovery_class to all service failure responses
packages/python/anip-fastapi/src/anip_fastapi/routes.py         # MODIFY: add recovery_class to transport-layer auth/error responses
packages/python/anip-rest/src/anip_rest/routes.py               # MODIFY: add recovery_class to transport-layer responses
packages/python/anip-graphql/src/anip_graphql/routes.py         # MODIFY: add recovery_class to transport-layer responses
packages/python/anip-graphql/src/anip_graphql/translation.py    # MODIFY: add recoveryClass to Resolution GraphQL SDL + response construction
packages/python/anip-grpc/src/anip_grpc/server.py               # MODIFY: populate recovery_class in gRPC failure responses
packages/python/anip-service/tests/test_recovery_class.py       # CREATE: recovery_class tests

# TypeScript
packages/typescript/core/src/models.ts                          # MODIFY: add recovery_class to Resolution Zod schema
packages/typescript/core/src/constants.ts                       # MODIFY: add action + recovery class constants/mapping
packages/typescript/server/src/delegation.ts                    # MODIFY: add recovery_class to delegation failures
packages/typescript/service/src/service.ts                      # MODIFY: add recovery_class to all service failures
packages/typescript/express/src/routes.ts                       # MODIFY: add recovery_class to transport-layer auth/error responses
packages/typescript/fastify/src/routes.ts                       # MODIFY: same
packages/typescript/hono/src/routes.ts                          # MODIFY: same
packages/typescript/rest/src/routes.ts                          # MODIFY: same
packages/typescript/graphql/src/routes.ts                       # MODIFY: same
packages/typescript/graphql/src/translation.ts                  # MODIFY: add recoveryClass to GraphQL SDL

# Go
packages/go/core/failure.go                                     # MODIFY: add RecoveryClass to Resolution struct + mapping function
packages/go/core/constants.go                                   # MODIFY: add action + recovery class constants
packages/go/internal/httputil/helpers.go                         # MODIFY: add RecoveryClass to BuildFailureBody() + DefaultResolution()
packages/go/server/delegation.go                                # MODIFY: add recovery_class to delegation failures
packages/go/service/invoke.go                                   # MODIFY: add recovery_class to all service failures
packages/go/restapi/http.go                                     # MODIFY: add recovery_class to transport-layer responses
packages/go/graphqlapi/http.go                                  # MODIFY: add recovery_class to transport-layer responses
packages/go/graphqlapi/translation.go                           # MODIFY: add recoveryClass to GraphQL SDL
packages/go/grpcapi/server.go                                   # MODIFY: populate recovery_class in gRPC responses

# Java (NO gRPC layer)
packages/java/anip-core/src/main/java/dev/anip/core/Resolution.java       # MODIFY: add recoveryClass field
packages/java/anip-core/src/main/java/dev/anip/core/Constants.java         # MODIFY: add action + recovery class constants + mapping
packages/java/anip-server/src/main/java/dev/anip/server/DelegationEngine.java  # MODIFY: add recovery_class
packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java     # MODIFY: add recovery_class to all failures
packages/java/anip-spring-boot/src/main/java/dev/anip/spring/AnipController.java  # MODIFY: add recovery_class to transport-layer responses
packages/java/anip-graphql/src/main/java/dev/anip/graphql/SchemaBuilder.java   # MODIFY: add recoveryClass to SDL + response construction (~line 222)

# C# (NO gRPC layer)
packages/csharp/src/Anip.Core/AnipError.cs                     # MODIFY: add RecoveryClass to Resolution class (line 41)
packages/csharp/src/Anip.Core/Constants.cs                      # MODIFY: add constants + mapping
packages/csharp/src/Anip.Server/DelegationEngine.cs             # MODIFY: add recovery_class
packages/csharp/src/Anip.Service/AnipService.cs                 # MODIFY: add recovery_class to all failures
packages/csharp/src/Anip.GraphQL/SchemaBuilder.cs               # MODIFY: add recoveryClass to SDL + response construction (~line 398)

# Conformance
conformance/test_recovery_class.py                              # CREATE: recovery_class conformance tests

# Studio
studio/src/components/InvokeResult.vue                          # MODIFY: show recovery_class badge on failures

# Website
website/docs/protocol/failures-cost-audit.md                    # MODIFY: add recovery_class docs + mapping table
website/docs/protocol/reference.md                              # MODIFY: add recovery_class to Resolution field table
website/docs/feature-map.md                                     # MODIFY: add v0.16 entries
website/docs/releases/version-history.md                        # MODIFY: add v0.16 entry
```

---

## Task 1: Spec and Schema

**Files:**
- Modify: `SPEC.md`
- Modify: `schema/anip.schema.json`

- [ ] **Step 1: Update SPEC.md §4.5**

Add `recovery_class` to Resolution definition. Add vocabulary table (6 values), advisory nature note, mandatory action→class mapping table (15 entries: 13 existing + 2 new), two new canonical actions (`retry_now`, `revalidate_state`). Update existing failure examples to include `recovery_class`. All canonical actions MUST appear in the mapping table — no fallback for unmapped actions.

- [ ] **Step 2: Update JSON Schema**

Add `RecoveryClass` enum (6 values) to `$defs`. Add `recovery_class` (required, ref to RecoveryClass) to the Resolution schema.

- [ ] **Step 3: Commit**

```bash
git add SPEC.md schema/anip.schema.json
git commit -m "spec: add recovery_class to Resolution, retry_now + revalidate_state actions (v0.16)"
```

---

## Task 2: Python Reference Implementation

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/python/anip-core/src/anip_core/constants.py`
- Modify: `packages/python/anip-server/src/anip_server/delegation.py`
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/python/anip-fastapi/src/anip_fastapi/routes.py`
- Modify: `packages/python/anip-rest/src/anip_rest/routes.py`
- Modify: `packages/python/anip-graphql/src/anip_graphql/routes.py`
- Modify: `packages/python/anip-graphql/src/anip_graphql/translation.py`
- Modify: `packages/python/anip-grpc/src/anip_grpc/server.py`
- Create: `packages/python/anip-service/tests/test_recovery_class.py`

- [ ] **Step 1: Add recovery_class to Resolution model + constants**

In `models.py`, add `recovery_class: str` to Resolution (required, no default).

In `constants.py`, add mapping function + constants:

```python
RECOVERY_CLASS_MAP = {
    "retry_now": "retry_now",
    "wait_and_retry": "wait_then_retry",
    "obtain_binding": "refresh_then_retry",
    "refresh_binding": "refresh_then_retry",
    "obtain_quote_first": "refresh_then_retry",
    "revalidate_state": "revalidate_then_retry",
    "request_broader_scope": "redelegation_then_retry",
    "request_budget_increase": "redelegation_then_retry",
    "request_budget_bound_delegation": "redelegation_then_retry",
    "request_matching_currency_delegation": "redelegation_then_retry",
    "request_new_delegation": "redelegation_then_retry",
    "request_capability_binding": "redelegation_then_retry",
    "request_deeper_delegation": "redelegation_then_retry",
    "escalate_to_root_principal": "terminal",
    "provide_credentials": "retry_now",
    "check_manifest": "revalidate_then_retry",
    "contact_service_owner": "terminal",
}

def recovery_class_for_action(action: str) -> str:
    """All canonical actions are in the map. KeyError for non-canonical actions."""
    return RECOVERY_CLASS_MAP[action]
```

Export from `__init__.py`.

- [ ] **Step 2: Add recovery_class to ALL failure responses in service.py**

Search for every `"action":` in resolution dicts and add `"recovery_class": recovery_class_for_action(action)`.

- [ ] **Step 3: Add recovery_class to delegation.py failures**

Same pattern — find resolution dicts in delegation failure responses, add recovery_class.

- [ ] **Step 4: Add recovery_class to ALL transport-layer responses**

These files have hardcoded resolution dicts for auth/error responses that bypass the service layer. Replace ALL non-canonical action strings with canonical equivalents AND add `recovery_class`:

- `packages/python/anip-fastapi/src/anip_fastapi/routes.py` (~lines 339, 352, 377)
- `packages/python/anip-rest/src/anip_rest/routes.py` (~line 167)
- `packages/python/anip-graphql/src/anip_graphql/routes.py` (~line 79)

Replacements:
- `provide_api_key` → `provide_credentials`
- `provide_credentials` → keep (now canonical)
- `check_manifest` → keep (now canonical)
- `contact_service_owner` → keep (now canonical)
- `obtain_delegation_token` → `request_new_delegation` (already canonical)

Then add `"recovery_class": recovery_class_for_action(action)` to each resolution dict.

- [ ] **Step 5: Update GraphQL SDL + response construction**

In `translation.py`, add `recoveryClass: String!` to the Resolution GraphQL type. Also check if resolution response objects are constructed manually (as dicts) — if so, add `recovery_class` to those dicts too.

- [ ] **Step 6: Populate recovery_class in gRPC responses**

In `server.py`, include `recovery_class` when mapping resolution to proto.

- [ ] **Step 7: Write tests**

Create `test_recovery_class.py`:
- `test_scope_failure_recovery_class` — scope failure → `redelegation_then_retry`
- `test_budget_failure_recovery_class` — budget → `redelegation_then_retry`
- `test_binding_stale_recovery_class` — binding stale → `refresh_then_retry`
- `test_recovery_class_consistent_with_action` — verify mapping for each canonical action
- `test_recovery_class_present_on_all_failures` — every failure includes recovery_class
- `test_retry_now_action` — `retry_now` action → `retry_now` class
- `test_revalidate_state_action` — `revalidate_state` → `revalidate_then_retry`
- `test_all_canonical_actions_have_mapping` — every action in the mapping table resolves without error

- [ ] **Step 8: Run tests**

```bash
cd /Users/samirski/Development/ANIP && python3 -m pytest packages/python/ -x -v 2>&1 | tail -20
```

- [ ] **Step 9: Commit**

```bash
git add packages/python/
git commit -m "feat(python): add recovery_class to Resolution, retry_now + revalidate_state actions (v0.16)"
```

---

## Task 3: TypeScript Runtime

**Files:**
- Modify: `packages/typescript/core/src/models.ts`
- Modify: `packages/typescript/core/src/constants.ts`
- Modify: `packages/typescript/server/src/delegation.ts`
- Modify: `packages/typescript/service/src/service.ts`
- Modify: `packages/typescript/express/src/routes.ts`
- Modify: `packages/typescript/fastify/src/routes.ts`
- Modify: `packages/typescript/hono/src/routes.ts`
- Modify: `packages/typescript/rest/src/routes.ts`
- Modify: `packages/typescript/graphql/src/routes.ts`
- Modify: `packages/typescript/graphql/src/translation.ts`

- [ ] **Step 1: Add to models + constants + mapping function**
- [ ] **Step 2: Add recovery_class to delegation + service failures**
- [ ] **Step 3: Add recovery_class to ALL transport-layer routes (express, fastify, hono, rest, graphql)**
- [ ] **Step 4: Update GraphQL SDL**
- [ ] **Step 5: Run tests**
```bash
cd /Users/samirski/Development/ANIP/packages/typescript && npx vitest run
```
- [ ] **Step 6: Commit**
```bash
git add packages/typescript/
git commit -m "feat(typescript): add recovery_class to Resolution (v0.16)"
```

---

## Task 4: Go Runtime

**Files:**
- Modify: `packages/go/core/failure.go`
- Modify: `packages/go/core/constants.go`
- Modify: `packages/go/internal/httputil/helpers.go` — **CRITICAL**: add RecoveryClass to `BuildFailureBody()` + `DefaultResolution()`
- Modify: `packages/go/server/delegation.go`
- Modify: `packages/go/service/invoke.go`
- Modify: `packages/go/restapi/http.go`
- Modify: `packages/go/graphqlapi/http.go`
- Modify: `packages/go/graphqlapi/translation.go`
- Modify: `packages/go/grpcapi/server.go`

- [ ] **Step 1: Add RecoveryClass to Resolution struct + mapping function in failure.go**
- [ ] **Step 2: Add constants in constants.go**
- [ ] **Step 3: Update `BuildFailureBody()` and `DefaultResolution()` in httputil/helpers.go** — this is the central serialization path for ALL Go HTTP failures
- [ ] **Step 4: Add recovery_class to delegation + service failures**
- [ ] **Step 5: Add recovery_class to transport-layer responses (restapi, graphqlapi)**
- [ ] **Step 6: Update GraphQL SDL + gRPC responses**
- [ ] **Step 7: Run tests**
```bash
cd /Users/samirski/Development/ANIP/packages/go && go test ./...
```
- [ ] **Step 8: Commit**
```bash
git add packages/go/
git commit -m "feat(go): add recovery_class to Resolution (v0.16)"
```

---

## Task 5: Java Runtime (NO gRPC)

**Files:**
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/Resolution.java`
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/Constants.java`
- Modify: `packages/java/anip-server/src/main/java/dev/anip/server/DelegationEngine.java`
- Modify: `packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java`
- Modify: `packages/java/anip-spring-boot/src/main/java/dev/anip/spring/AnipController.java`
- Modify: `packages/java/anip-graphql/src/main/java/dev/anip/graphql/SchemaBuilder.java` — SDL + response construction (~line 222)

- [ ] **Step 1: Add recoveryClass to Resolution + constants + mapping**
- [ ] **Step 2: Add recovery_class to delegation + service failures**
- [ ] **Step 3: Add recovery_class to Spring controller transport-layer responses**
- [ ] **Step 4: Update GraphQL SDL AND response construction (SchemaBuilder ~line 222 builds resolution as Map.of — add recoveryClass)**
- [ ] **Step 5: Run tests**
```bash
cd /Users/samirski/Development/ANIP/packages/java && mvn test -q
```
- [ ] **Step 6: Commit**
```bash
git add packages/java/
git commit -m "feat(java): add recovery_class to Resolution (v0.16)"
```

---

## Task 6: C# Runtime (NO gRPC)

**Files:**
- Modify: `packages/csharp/src/Anip.Core/AnipError.cs` — Resolution class at line 41 (NOT Resolution.cs — that file does not exist)
- Modify: `packages/csharp/src/Anip.Core/Constants.cs`
- Modify: `packages/csharp/src/Anip.Server/DelegationEngine.cs`
- Modify: `packages/csharp/src/Anip.Service/AnipService.cs`
- Modify: `packages/csharp/src/Anip.GraphQL/SchemaBuilder.cs` — SDL + response construction (~line 398 builds resolution as Dictionary — add recovery_class)

- [ ] **Step 1: Add RecoveryClass to Resolution in AnipError.cs + constants + mapping**
- [ ] **Step 2: Add recovery_class to delegation + service failures**
- [ ] **Step 3: Update GraphQL SDL AND response construction (SchemaBuilder ~line 398 builds resolution as Dictionary — add RecoveryClass)**
- [ ] **Step 4: Run tests**
```bash
cd /Users/samirski/Development/ANIP/packages/csharp && dotnet test --verbosity minimal
```
- [ ] **Step 5: Commit**
```bash
git add packages/csharp/
git commit -m "feat(csharp): add recovery_class to Resolution (v0.16)"
```

---

## Task 7: Conformance Suite

**Files:**
- Create: `conformance/test_recovery_class.py`

- [ ] **Step 1: Write conformance tests**

- `test_failure_resolution_has_recovery_class` — every failure response's resolution includes `recovery_class`
- `test_recovery_class_is_canonical` — every `recovery_class` value must be one of the 6 vocabulary values
- `test_action_recovery_class_consistency` — `recovery_class` matches expected value for the given `resolution.action` per mapping table
- `test_scope_failure_is_redelegation` — scope failure → `recovery_class: "redelegation_then_retry"`
- `test_retry_now_action_gives_retry_now_class` — `retry_now` action → `retry_now` class
- `test_terminal_action_gives_terminal_class` — `escalate_to_root_principal` → `terminal` class (if non-delegable capability exists)
- `test_retry_false_preserved_with_recovery_class` — failures that have `retry: false` (e.g., budget_exceeded) keep `retry: false` even with a non-terminal `recovery_class` like `redelegation_then_retry`
- `test_terminal_requires_retry_false` — `recovery_class: "terminal"` always has `retry: false`

- [ ] **Step 2: Commit**
```bash
git add conformance/
git commit -m "test: add recovery_class conformance tests (v0.16)"
```

---

## Task 8: Studio UI

**Files:**
- Modify: `studio/src/components/InvokeResult.vue`

- [ ] **Step 1: Show recovery_class badge on failures**

Add colored badge: retry_now=blue, wait_then_retry=yellow, refresh_then_retry=orange, redelegation_then_retry=purple, revalidate_then_retry=cyan, terminal=red.

- [ ] **Step 2: Build and sync**
```bash
cd /Users/samirski/Development/ANIP/studio && npm run build && cd .. && bash studio/sync.sh
```
- [ ] **Step 3: Commit**
```bash
git add studio/ packages/*/studio/
git commit -m "feat(studio): show recovery_class badge on failure responses (v0.16)"
```

---

## Task 9: Website Documentation

**Files:**
- Modify: `website/docs/protocol/failures-cost-audit.md`
- Modify: `website/docs/protocol/reference.md`
- Modify: `website/docs/feature-map.md`
- Modify: `website/docs/releases/version-history.md`

- [ ] **Step 1: Update failures page** — recovery_class vocabulary, mapping table, advisory note, examples
- [ ] **Step 2: Update reference page** — add recovery_class to Resolution field table, add retry_now + revalidate_state to actions
- [ ] **Step 3: Update feature map + version history**
- [ ] **Step 4: Commit**
```bash
git add website/
git commit -m "docs(website): add recovery_class documentation (v0.16)"
```

---

## Task 10: Version Bump

- [ ] **Step 1: Bump to anip/0.16**

Update all 5 runtime constants + constant-verification tests + model defaults + SPEC.md title + schema `$id` + website version references. Add v0.16 entry to version history.

- [ ] **Step 2: Commit**
```bash
git add SPEC.md schema/ packages/ website/
git commit -m "chore: bump protocol version to anip/0.16"
```
