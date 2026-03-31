# ANIP v0.15: Authority and Blocked-Action Clarity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make authority failures machine-readable and actionable — structured `reason_type` on permission responses, canonical `resolution.action` vocabulary, and `block_class` on failures distinguishing terminal/resolvable/externally-resolvable blocks.

**Architecture:** Three additive changes: (1) `reason_type` vocabulary on RestrictedCapability and DeniedCapability classifies WHY authority is blocked, (2) `block_class` on failure responses classifies the block's recoverability, (3) canonical `resolution.action` vocabulary gives agents a deterministic switch target for next steps. No breaking changes — all new fields are additive.

**Tech Stack:** Python, TypeScript, Go, Java, C# runtimes + Protobuf + JSON Schema + SPEC.md + Vue (Studio)

**Spec:** `docs/proposals/v0.15-slice2-authority-blocked-action-spec-draft.md`

---

## File Structure

```
# Spec, Schema, and Proto
SPEC.md                                                        # MODIFY: §4.4 reason_type + resolution_hint + terminal + escalation_target; §4.5 block_class + canonical resolution.action vocabulary
schema/anip.schema.json                                        # MODIFY: add ReasonType, BlockClass enums; add fields to RestrictedCapability, DeniedCapability, ANIPFailure
proto/anip/v1/anip.proto                                       # MODIFY: add block_class to AnipFailure message

# Python (reference implementation)
packages/python/anip-core/src/anip_core/models.py              # MODIFY: add new fields to RestrictedCapability, DeniedCapability, ANIPFailure
packages/python/anip-server/src/anip_server/permissions.py     # MODIFY: populate reason_type + resolution_hint
packages/python/anip-service/src/anip_service/service.py       # MODIFY: populate block_class, canonical resolution.action
packages/python/anip-graphql/src/anip_graphql/translation.py   # MODIFY: add block_class to GraphQL SDL
packages/python/anip-grpc/src/anip_grpc/server.py              # MODIFY: populate block_class in gRPC responses
packages/python/anip-service/tests/test_authority.py           # CREATE: authority posture + block_class tests

# TypeScript
packages/typescript/core/src/models.ts                         # MODIFY: add fields to Zod schemas
packages/typescript/server/src/permissions.ts                   # MODIFY: populate reason_type (update PermissionResult interface too)
packages/typescript/service/src/service.ts                     # MODIFY: populate block_class
packages/typescript/graphql/src/translation.ts                 # MODIFY: add block_class to GraphQL SDL
packages/typescript/rest/src/translation.ts                    # MODIFY: add block_class to OpenAPI schema

# Go
packages/go/core/models.go                                    # MODIFY: add fields to RestrictedCapability, DeniedCapability
packages/go/core/failure.go                                    # MODIFY: add BlockClass to ANIPError (NOT models.go)
packages/go/service/permissions.go                             # MODIFY: populate reason_type
packages/go/service/invoke.go                                  # MODIFY: populate block_class
packages/go/service/redaction.go                               # MODIFY: whitelist block_class in redaction
packages/go/graphqlapi/translation.go                          # MODIFY: add block_class to GraphQL SDL
packages/go/restapi/openapi.go                                 # MODIFY: add block_class to OpenAPI schema
packages/go/grpcapi/server.go                                  # MODIFY: populate block_class in gRPC responses

# Java
packages/java/anip-core/src/main/java/dev/anip/core/PermissionResponse.java  # MODIFY: add fields to nested RestrictedCapability + DeniedCapability
packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java   # MODIFY: permissions + failures
packages/java/anip-graphql/src/main/java/dev/anip/graphql/SchemaBuilder.java # MODIFY: add block_class to GraphQL SDL
packages/java/anip-rest/src/main/java/dev/anip/rest/OpenApiGenerator.java    # MODIFY: add block_class to OpenAPI schema

# C#
packages/csharp/src/Anip.Core/RestrictedCapability.cs          # MODIFY: add new fields
packages/csharp/src/Anip.Core/DeniedCapability.cs              # MODIFY: add new fields (check if exists, create if not)
packages/csharp/src/Anip.Service/AnipService.cs                # MODIFY: permissions + failures
packages/csharp/src/Anip.Service/FailureRedaction.cs           # MODIFY: whitelist block_class
packages/csharp/src/Anip.GraphQL/SchemaBuilder.cs              # MODIFY: add block_class to GraphQL SDL
packages/csharp/src/Anip.Rest/OpenApiGenerator.cs              # MODIFY: add block_class to OpenAPI schema

# Conformance
conformance/test_authority.py                                  # CREATE: reason_type + block_class conformance tests

# Showcase
examples/showcase/travel/capabilities.py                       # MODIFY: demonstrate scope restriction → reason_type
examples/showcase/devops/capabilities.py                       # MODIFY: add non-delegable action scenario
examples/showcase/finance/capabilities.py                      # MODIFY: add external-approval scenario

# Studio
studio/src/components/CapabilityCard.vue                       # MODIFY: show reason_type on restricted/denied
studio/src/components/InvokeResult.vue                         # MODIFY: show block_class on failures

# Website
website/docs/protocol/delegation-permissions.md                # MODIFY: add reason_type docs
website/docs/protocol/failures-cost-audit.md                   # MODIFY: add block_class + canonical resolution.action
website/docs/protocol/reference.md                             # MODIFY: add new fields to response tables
website/docs/feature-map.md                                    # MODIFY: add v0.15 entries
website/docs/releases/version-history.md                       # MODIFY: add v0.15 entry
```

---

## Task 1: Spec, Schema, and Proto

**Files:**
- Modify: `SPEC.md`
- Modify: `schema/anip.schema.json`
- Modify: `proto/anip/v1/anip.proto`

- [ ] **Step 1: Update SPEC.md §4.4 (Permission Discovery)**

Add `reason_type` vocabulary table (7 values: `insufficient_scope`, `insufficient_delegation_depth`, `stronger_delegation_required`, `unmet_control_requirement`, `non_delegable`, `requires_external_approval`, `principal_class_insufficient`).

Add new fields:
- RestrictedCapability: `reason_type` (required string), `resolution_hint` (optional string)
- DeniedCapability: `reason_type` (required string), `terminal` (required boolean), `escalation_target` (optional string)

Update examples to show the new fields.

- [ ] **Step 2: Update SPEC.md §4.5 (Failure Semantics)**

Add `block_class` field to failure objects. Vocabulary: `transient`, `resolvable`, `externally_resolvable`, `terminal`.

Add canonical `resolution.action` vocabulary table (12 values): `retry`, `retry_after_change`, `request_broader_delegation`, `request_budget_increase`, `request_budget_bound_delegation`, `request_capability_binding`, `obtain_binding`, `refresh_binding`, `escalate_to_human`, `escalate_to_principal`, `stop`, `replan`.

Add 3 new failure types: `insufficient_authority` (resolvable), `delegation_depth_exceeded` (resolvable), `non_delegable_action` (terminal).

Add mapping table from existing failure types to default `block_class`.

State the consistency rule: `resolution_hint` in permissions SHOULD match `resolution.action` in the invoke failure for the same capability.

- [ ] **Step 3: Update JSON Schema**

Add `ReasonType` and `BlockClass` enums to `$defs`. Add new fields to `RestrictedCapability`, `DeniedCapability`, and `ANIPFailure` schemas.

- [ ] **Step 4: Update Proto**

Add `string block_class = 5;` to the `AnipFailure` message. Regenerate Python gRPC stubs.

- [ ] **Step 5: Commit**

```bash
git add SPEC.md schema/anip.schema.json proto/anip/v1/anip.proto packages/python/anip-grpc/src/anip_grpc/generated/
git commit -m "spec: add authority posture, block_class, and canonical resolution.action vocabulary (v0.15)"
```

---

## Task 2: Python Core Models + Permissions + Failures

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/python/anip-server/src/anip_server/permissions.py`
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/python/anip-graphql/src/anip_graphql/translation.py`
- Modify: `packages/python/anip-grpc/src/anip_grpc/server.py`
- Create: `packages/python/anip-service/tests/test_authority.py`

- [ ] **Step 1: Add fields to models**

RestrictedCapability: add `reason_type: str = "insufficient_scope"`, `resolution_hint: str | None = None`
DeniedCapability: add `reason_type: str = "non_delegable"`, `terminal: bool = True`, `escalation_target: str | None = None`
ANIPFailure: add `block_class: str | None = None`

- [ ] **Step 2: Create _block_class_for_failure() helper**

In service.py, add a mapping function used by BOTH the failure construction path AND the permissions path (for consistency):

```python
_BLOCK_CLASS_MAP = {
    "capability_unavailable": "transient",
    "internal_error": "transient",
    "rate_limited": "transient",
    "non_delegable_action": "terminal",
}

def _block_class_for_failure(failure_type: str) -> str:
    return _BLOCK_CLASS_MAP.get(failure_type, "resolvable")
```

- [ ] **Step 3: Populate reason_type in permissions.py**

In `discover_permissions()`, when creating RestrictedCapability/DeniedCapability instances, set `reason_type` based on the restriction reason:
- Missing scope → `reason_type="insufficient_scope"`, `resolution_hint="request_broader_delegation"`
- Unmet control requirement → `reason_type="unmet_control_requirement"`, `resolution_hint` based on requirement type
- Denied entirely → `reason_type` based on why (non-delegable, principal class, etc.)

- [ ] **Step 4: Populate block_class on ALL failure responses in service.py**

Find every failure dict in service.py. Add `"block_class": _block_class_for_failure(failure_type)`. Use canonical `resolution.action` vocabulary.

- [ ] **Step 5: Update GraphQL SDL**

In `translation.py`, add `blockClass: String` to the `ANIPFailure` GraphQL type.

- [ ] **Step 6: Populate block_class in gRPC responses**

In `server.py`, map `block_class` from the service result to the proto `AnipFailure.block_class` field.

- [ ] **Step 7: Write tests**

Create `test_authority.py` with:
- `test_restricted_has_reason_type` — permissions returns `reason_type` on restricted
- `test_denied_has_reason_type_and_terminal` — denied has `reason_type` + `terminal`
- `test_reason_type_insufficient_scope` — scope gap → `reason_type="insufficient_scope"`
- `test_resolution_hint_matches_invoke_failure` — permissions `resolution_hint` matches invoke `resolution.action`
- `test_block_class_resolvable_for_scope` — scope failure → `block_class="resolvable"`
- `test_block_class_transient_for_unavailable` — transient failure → `block_class="transient"`
- `test_block_class_present_on_all_failure_types` — every failure includes `block_class`
- `test_delegation_depth_exceeded` — max depth → `delegation_depth_exceeded` failure
- `test_canonical_resolution_action` — resolution.action uses canonical vocabulary

- [ ] **Step 8: Run tests**

```bash
cd /Users/samirski/Development/ANIP && python -m pytest packages/python/ -x -v --timeout=30 2>&1 | tail -30
```

- [ ] **Step 9: Commit**

```bash
git add packages/python/
git commit -m "feat(python): add authority posture, block_class, canonical resolution.action (v0.15)"
```

---

## Task 3: TypeScript Runtime

**Files:**
- Modify: `packages/typescript/core/src/models.ts` — add fields to Zod schemas for RestrictedCapability, DeniedCapability, ANIPFailure
- Modify: `packages/typescript/server/src/permissions.ts` — populate reason_type (update BOTH PermissionResult interface AND Zod schemas)
- Modify: `packages/typescript/service/src/service.ts` — populate block_class + canonical resolution.action
- Modify: `packages/typescript/graphql/src/translation.ts` — add `blockClass` to GraphQL SDL
- Modify: `packages/typescript/rest/src/translation.ts` — add `block_class` to OpenAPI schema

- [ ] **Step 1: Add fields to models + permissions interface**
- [ ] **Step 2: Populate reason_type in permissions**
- [ ] **Step 3: Populate block_class on failures + canonical actions**
- [ ] **Step 4: Update GraphQL SDL and OpenAPI schema**
- [ ] **Step 5: Run tests**
```bash
cd /Users/samirski/Development/ANIP/packages/typescript && npx vitest run
```
- [ ] **Step 6: Commit**
```bash
git add packages/typescript/
git commit -m "feat(typescript): add authority posture and block_class (v0.15)"
```

---

## Task 4: Go Runtime

**Files:**
- Modify: `packages/go/core/models.go` — add fields to RestrictedCapability, DeniedCapability
- Modify: `packages/go/core/failure.go` — add BlockClass to ANIPError struct
- Modify: `packages/go/service/permissions.go` — populate reason_type
- Modify: `packages/go/service/invoke.go` — populate block_class
- Modify: `packages/go/service/redaction.go` — whitelist block_class field
- Modify: `packages/go/graphqlapi/translation.go` — add blockClass to GraphQL SDL
- Modify: `packages/go/restapi/openapi.go` — add block_class to OpenAPI schema
- Modify: `packages/go/grpcapi/server.go` — populate block_class in gRPC responses

- [ ] **Step 1: Add fields to models + failure struct**
- [ ] **Step 2: Populate reason_type in permissions**
- [ ] **Step 3: Populate block_class on failures + whitelist in redaction**
- [ ] **Step 4: Update GraphQL SDL, OpenAPI schema, gRPC responses**
- [ ] **Step 5: Run tests**
```bash
cd /Users/samirski/Development/ANIP/packages/go && go test ./...
```
- [ ] **Step 6: Commit**
```bash
git add packages/go/
git commit -m "feat(go): add authority posture and block_class (v0.15)"
```

---

## Task 5: Java Runtime

**Files:**
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/PermissionResponse.java` — add fields to nested RestrictedCapability + DeniedCapability classes
- Modify: `packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java` — permissions reason_type + failure block_class
- Modify: `packages/java/anip-graphql/src/main/java/dev/anip/graphql/SchemaBuilder.java` — add blockClass to SDL
- Modify: `packages/java/anip-rest/src/main/java/dev/anip/rest/OpenApiGenerator.java` — add block_class to OpenAPI

Note: Java has no standalone ANIPFailure class — failures are `Map<String, Object>`. Add `block_class` to the inline map construction in ANIPService.java.

- [ ] **Step 1-4: Models, permissions, failures, transports**
- [ ] **Step 5: Run tests**
```bash
cd /Users/samirski/Development/ANIP/packages/java && mvn test -q
```
- [ ] **Step 6: Commit**
```bash
git add packages/java/
git commit -m "feat(java): add authority posture and block_class (v0.15)"
```

---

## Task 6: C# Runtime

**Files:**
- Modify: `packages/csharp/src/Anip.Core/RestrictedCapability.cs` — add new fields
- Modify: `packages/csharp/src/Anip.Core/DeniedCapability.cs` — add new fields (create file if it doesn't exist as standalone)
- Modify: `packages/csharp/src/Anip.Service/AnipService.cs` — permissions reason_type + failure block_class
- Modify: `packages/csharp/src/Anip.Service/FailureRedaction.cs` — whitelist block_class
- Modify: `packages/csharp/src/Anip.GraphQL/SchemaBuilder.cs` — add blockClass to SDL
- Modify: `packages/csharp/src/Anip.Rest/OpenApiGenerator.cs` — add block_class to OpenAPI

- [ ] **Step 1-4: Models, permissions, failures, transports, redaction**
- [ ] **Step 5: Run tests**
```bash
cd /Users/samirski/Development/ANIP/packages/csharp && dotnet test --verbosity minimal
```
- [ ] **Step 6: Commit**
```bash
git add packages/csharp/
git commit -m "feat(csharp): add authority posture and block_class (v0.15)"
```

---

## Task 7: Conformance Suite

**Files:**
- Create: `conformance/test_authority.py`

- [ ] **Step 1: Write conformance tests**

- `test_restricted_has_reason_type` — restricted capabilities include `reason_type`
- `test_denied_has_reason_type_and_terminal` — denied capabilities include `reason_type` + `terminal`
- `test_scope_failure_has_block_class` — invoke failure for scope issue includes `block_class`
- `test_block_class_is_resolvable_for_scope` — `block_class` is `"resolvable"` for scope failures
- `test_resolution_action_is_canonical` — `resolution.action` uses canonical vocabulary
- `test_terminal_denied_is_terminal_block_class` — denied with `terminal=true` gives `block_class="terminal"` on invoke
- `test_externally_resolvable_block_class` — external approval scenario gives `block_class="externally_resolvable"`

- [ ] **Step 2: Commit**
```bash
git add conformance/
git commit -m "test: add authority and block_class conformance tests (v0.15)"
```

---

## Task 8: Showcase Apps

**Files:**
- Modify: `examples/showcase/devops/capabilities.py`
- Modify: `examples/showcase/finance/capabilities.py`

- [ ] **Step 1: Add non-delegable action to devops showcase**

Add a capability (e.g., `destroy_cluster`) that is marked as non-delegable. When invoked by any agent, it should return `block_class: "terminal"`, `resolution.action: "stop"`.

This can be done by adding a `control_requirements` entry for `stronger_delegation_required` or by checking the principal class in the handler.

- [ ] **Step 2: Add external-approval scenario to finance showcase**

Add or modify a capability (e.g., `execute_large_trade` above a threshold) that requires external approval. When invoked, it returns `block_class: "externally_resolvable"`, `resolution.action: "escalate_to_principal"`, `escalation_target`.

- [ ] **Step 3: Commit**
```bash
git add examples/showcase/
git commit -m "feat(showcase): add non-delegable and external-approval scenarios (v0.15)"
```

---

## Task 9: Studio UI

**Files:**
- Modify: `studio/src/components/CapabilityCard.vue`
- Modify: `studio/src/components/InvokeResult.vue`

- [ ] **Step 1: Show reason_type on restricted/denied capabilities**

Display `reason_type` as a badge. Show `terminal` as a red indicator on denied capabilities. Show `escalation_target` when present.

- [ ] **Step 2: Show block_class on failure responses**

Display `block_class` badge with color coding: green=transient, yellow=resolvable, orange=externally_resolvable, red=terminal.

- [ ] **Step 3: Build and sync**
```bash
cd /Users/samirski/Development/ANIP/studio && npm run build && cd .. && bash studio/sync.sh
```
- [ ] **Step 4: Commit**
```bash
git add studio/ packages/*/studio/
git commit -m "feat(studio): show reason_type, block_class, terminal in UI (v0.15)"
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
Add `reason_type` vocabulary table, new fields on restricted/denied, examples.

- [ ] **Step 2: Update failures page**
Add `block_class` vocabulary, canonical `resolution.action` table, 3 new failure types, examples.

- [ ] **Step 3: Update reference page**
Add new fields to permission response and failure response tables.

- [ ] **Step 4: Update feature map and version history**
Add v0.15 entries.

- [ ] **Step 5: Commit**
```bash
git add website/
git commit -m "docs(website): add authority posture and block_class documentation (v0.15)"
```

---

## Task 11: Version Bump

- [ ] **Step 1: Bump to anip/0.15**

Update all 5 runtime constants, constant-verification tests, model defaults, SPEC.md title, schema `$id`, website version references. Add v0.15 entry to version history.

- [ ] **Step 2: Commit**
```bash
git add SPEC.md schema/ packages/ website/
git commit -m "chore: bump protocol version to anip/0.15"
```
