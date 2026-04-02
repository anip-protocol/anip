# ANIP v0.18: Cross-Service Continuity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add normative cross-service propagation rules for `task_id` and `parent_invocation_id`, plus one new optional field (`upstream_service`) for reconstruction hints across service boundaries.

**Architecture:** One new optional string field on invoke requests (`upstream_service`) — extracted from request body, echoed in response, included in audit entries. Same pattern as `task_id` and `parent_invocation_id`. Normative guidance added to SPEC.md. No new failure types, no new enforcement.

**Tech Stack:** Python, TypeScript, Go, Java, C# runtimes + JSON Schema + SPEC.md + Vue (Studio)

**Spec:** `docs/proposals/v0.18-phase4-slice1-cross-service-continuity-spec-draft.md`

---

## File Structure

```
# Spec and Schema
SPEC.md                                                        # MODIFY: §6.3 cross-service propagation rules + upstream_service field + reconstruction guidance
schema/anip.schema.json                                        # MODIFY: add upstream_service to InvokeRequest + InvokeResponse

# Python
packages/python/anip-core/src/anip_core/models.py              # MODIFY: add upstream_service to InvokeRequest/InvokeResponse if modeled
packages/python/anip-service/src/anip_service/service.py        # MODIFY: extract upstream_service, echo in response, pass to audit
packages/python/anip-fastapi/src/anip_fastapi/routes.py         # MODIFY: extract upstream_service from request body
packages/python/anip-grpc/src/anip_grpc/server.py               # MODIFY: extract upstream_service (if in proto or JSON params)
packages/python/anip-stdio/src/anip_stdio/server.py             # MODIFY: forward upstream_service
packages/python/anip-service/tests/test_upstream_service.py     # CREATE: upstream_service echo + audit tests

# TypeScript
packages/typescript/service/src/service.ts                      # MODIFY: extract + echo + audit
packages/typescript/express/src/routes.ts                       # MODIFY: extract from body
packages/typescript/fastify/src/routes.ts                       # MODIFY: extract from body
packages/typescript/hono/src/routes.ts                          # MODIFY: extract from body
packages/typescript/stdio/src/server.ts                         # MODIFY: forward

# Go
packages/go/service/invoke.go                                   # MODIFY: extract + echo + audit
packages/go/service/service.go                                  # MODIFY: add UpstreamService to InvokeOpts
packages/go/httpapi/handler.go                                  # MODIFY: extract from body
packages/go/ginapi/handler.go                                   # MODIFY: extract from body
packages/go/grpcapi/server.go                                   # MODIFY: extract
packages/go/stdioapi/server.go                                  # MODIFY: forward

# Java
packages/java/anip-service/src/main/java/dev/anip/service/InvokeOpts.java   # MODIFY: add upstreamService
packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java  # MODIFY: echo + audit
packages/java/anip-spring-boot/src/main/java/dev/anip/spring/AnipController.java  # MODIFY: extract
packages/java/anip-quarkus/src/main/java/dev/anip/quarkus/AnipResource.java      # MODIFY: extract

# C#
packages/csharp/src/Anip.Service/InvokeOpts.cs                 # MODIFY: add UpstreamService (or check if exists)
packages/csharp/src/Anip.Service/AnipService.cs                 # MODIFY: echo + audit
packages/csharp/src/Anip.AspNetCore/AnipController.cs           # MODIFY: extract (check actual file name)

# Conformance
conformance/test_cross_service.py                               # CREATE: upstream_service echo + audit tests

# Studio
studio/src/views/AuditView.vue                                  # MODIFY: display upstream_service in audit entries

# Website
website/docs/protocol/lineage.md                                # MODIFY: add cross-service propagation guidance + examples
website/docs/protocol/reference.md                              # MODIFY: add upstream_service to invoke request/response field tables
website/docs/feature-map.md                                     # MODIFY: add v0.18 entries
website/docs/releases/version-history.md                        # MODIFY: add v0.18 entry
```

---

## Task 1: Spec and Schema

**Files:**
- Modify: `SPEC.md`
- Modify: `schema/anip.schema.json`

- [ ] **Step 1: Update SPEC.md §6.3 (Invocation)**

Add after the existing `task_id`/`parent_invocation_id` documentation:

1. Cross-service `task_id` propagation rule: agents SHOULD propagate the same task_id when downstream work is part of the same logical task
2. Cross-service `parent_invocation_id` linkage rule: agents SHOULD set parent_invocation_id to the upstream invocation_id, even across services
3. `upstream_service` field definition: optional string, agent-supplied, unvalidated hint for reconstruction
4. Reconstruction guidance section (best-effort, not guarantee)
5. Examples: direct handoff, fan-out, async follow-up

Also update the invocation request/response field tables to include `upstream_service`.

- [ ] **Step 2: Update JSON Schema**

Add `upstream_service` (optional string, default null) to the InvokeRequest and InvokeResponse schemas.

- [ ] **Step 3: Commit**

```bash
git add SPEC.md schema/anip.schema.json
git commit -m "spec: add cross-service continuity rules and upstream_service field (v0.18)"
```

---

## Task 2: Python Reference Implementation

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/python/anip-fastapi/src/anip_fastapi/routes.py`
- Modify: `packages/python/anip-grpc/src/anip_grpc/server.py`
- Modify: `packages/python/anip-stdio/src/anip_stdio/server.py`
- Create: `packages/python/anip-service/tests/test_upstream_service.py`

- [ ] **Step 1: Extract upstream_service in FastAPI routes**

In `routes.py`, where `task_id` and `parent_invocation_id` are extracted from the body (~line 101), add:
```python
upstream_service = body.get("upstream_service")
```
Pass it through to `service.invoke()`.

- [ ] **Step 2: Accept upstream_service in service.invoke()**

In `service.py`, add `upstream_service: str | None = None` parameter to `invoke()` and `_invoke_body()`. Echo it in the response dict. Include it in audit entries.

- [ ] **Step 3: Forward in gRPC and stdio**

In `server.py` (gRPC) and `server.py` (stdio): extract `upstream_service` from the request and pass through.

- [ ] **Step 4: Write tests**

Create `test_upstream_service.py`:
- `test_upstream_service_echoed_in_response` — pass upstream_service in invoke, verify it appears in response
- `test_upstream_service_in_audit` — invoke with upstream_service, query audit, verify it's in the entry
- `test_upstream_service_optional` — invoke without upstream_service, verify response has null/absent

- [ ] **Step 5: Run tests**

```bash
cd /Users/samirski/Development/ANIP && python3 -m pytest packages/python/ -x -q 2>&1 | tail -10
```

- [ ] **Step 6: Commit**

```bash
git add packages/python/
git commit -m "feat(python): add upstream_service to invoke request/response/audit (v0.18)"
```

---

## Task 3: TypeScript Runtime

**Files:**
- Modify: `packages/typescript/service/src/service.ts`
- Modify: `packages/typescript/express/src/routes.ts`
- Modify: `packages/typescript/fastify/src/routes.ts`
- Modify: `packages/typescript/hono/src/routes.ts`
- Modify: `packages/typescript/stdio/src/server.ts`

- [ ] **Step 1: Extract upstream_service in all transport routes**

Same pattern as task_id/parent_invocation_id extraction. Add `upstream_service` to the fields extracted from the request body and passed to `service.invoke()`.

- [ ] **Step 2: Accept, echo, and audit in service.ts**

- [ ] **Step 3: Run tests**

```bash
cd /Users/samirski/Development/ANIP/packages/typescript && npx vitest run
```

- [ ] **Step 4: Commit**

```bash
git add packages/typescript/
git commit -m "feat(typescript): add upstream_service to invoke (v0.18)"
```

---

## Task 4: Go Runtime

**Files:**
- Modify: `packages/go/service/service.go` (InvokeOpts)
- Modify: `packages/go/service/invoke.go`
- Modify: `packages/go/httpapi/handler.go`
- Modify: `packages/go/ginapi/handler.go`
- Modify: `packages/go/grpcapi/server.go`
- Modify: `packages/go/stdioapi/server.go`

- [ ] **Step 1: Add UpstreamService to InvokeOpts**
- [ ] **Step 2: Extract in all handlers, echo in response, include in audit**
- [ ] **Step 3: Run tests**

```bash
cd /Users/samirski/Development/ANIP/packages/go && go test ./...
```

- [ ] **Step 4: Commit**

```bash
git add packages/go/
git commit -m "feat(go): add upstream_service to invoke (v0.18)"
```

---

## Task 5: Java Runtime

**Files:**
- Modify: `packages/java/anip-service/src/main/java/dev/anip/service/InvokeOpts.java`
- Modify: `packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java`
- Modify: `packages/java/anip-spring-boot/src/main/java/dev/anip/spring/AnipController.java`
- Modify: `packages/java/anip-quarkus/src/main/java/dev/anip/quarkus/AnipResource.java`

- [ ] **Step 1: Add upstreamService to InvokeOpts**
- [ ] **Step 2: Extract in Spring + Quarkus controllers, echo + audit in ANIPService**
- [ ] **Step 3: Run tests**

```bash
cd /Users/samirski/Development/ANIP/packages/java && mvn test -q
```

- [ ] **Step 4: Commit**

```bash
git add packages/java/
git commit -m "feat(java): add upstream_service to invoke (v0.18)"
```

---

## Task 6: C# Runtime

**Files:**
- Modify: `packages/csharp/src/Anip.Service/AnipService.cs` (or InvokeOpts if separate)
- Modify: `packages/csharp/src/Anip.AspNetCore/AnipController.cs` (check actual path)

- [ ] **Step 1: Add UpstreamService to InvokeOpts + extract + echo + audit**
- [ ] **Step 2: Run tests**

```bash
cd /Users/samirski/Development/ANIP/packages/csharp && dotnet test --verbosity minimal
```

- [ ] **Step 3: Commit**

```bash
git add packages/csharp/
git commit -m "feat(csharp): add upstream_service to invoke (v0.18)"
```

---

## Task 7: Conformance Suite

**Files:**
- Create: `conformance/test_cross_service.py`

- [ ] **Step 1: Write conformance tests**

- `test_upstream_service_echoed` — invoke with `upstream_service: "test-upstream"`, verify it appears in the response
- `test_upstream_service_optional` — invoke without upstream_service, verify response succeeds (field absent or null)
- `test_upstream_service_in_audit` — invoke with upstream_service, query audit, verify entry contains it
- `test_task_id_propagation_accepted` — invoke with a task_id that was not created by this service (simulates cross-service propagation), verify it's accepted and echoed

- [ ] **Step 2: Commit**

```bash
git add conformance/
git commit -m "test: add cross-service continuity conformance tests (v0.18)"
```

---

## Task 8: Studio UI

**Files:**
- Modify: `studio/src/views/AuditView.vue`

- [ ] **Step 1: Display upstream_service in audit entries**

When an audit entry has `upstream_service`, display it as a labeled field (e.g., "Upstream: travel-service") in the entry detail view.

- [ ] **Step 2: Build and sync**

```bash
cd /Users/samirski/Development/ANIP/studio && npm run build && cd .. && bash studio/sync.sh
```

- [ ] **Step 3: Commit**

```bash
git add studio/ packages/*/studio/
git commit -m "feat(studio): display upstream_service in audit entries (v0.18)"
```

---

## Task 9: Website Documentation

**Files:**
- Modify: `website/docs/protocol/lineage.md`
- Modify: `website/docs/protocol/reference.md`
- Modify: `website/docs/feature-map.md`
- Modify: `website/docs/releases/version-history.md`
- Modify: `website/docs/releases/what-ships-today.md`

- [ ] **Step 1: Update lineage page**

Add "Cross-service continuity (v0.18)" section with:
- task_id propagation rule
- parent_invocation_id linkage rule
- upstream_service field
- Reconstruction guidance (best-effort)
- Examples (direct handoff, fan-out)

- [ ] **Step 2: Update reference page**

Add `upstream_service` to invoke request/response field tables.

- [ ] **Step 3: Update feature map + version history + what-ships-today**

- [ ] **Step 4: Commit**

```bash
git add website/
git commit -m "docs(website): add cross-service continuity documentation (v0.18)"
```

---

## Task 10: Version Bump

- [ ] **Step 1: Bump to anip/0.18**

Update all 5 runtime constants + constant-verification tests + model defaults + SPEC.md title + schema `$id` + website version references (`0.17.0` → `0.18.0`).

- [ ] **Step 2: Commit**

```bash
git add SPEC.md schema/ packages/ website/
git commit -m "chore: bump protocol version to anip/0.18"
```
