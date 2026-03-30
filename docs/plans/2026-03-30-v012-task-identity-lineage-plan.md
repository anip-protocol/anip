# ANIP v0.12: Task Identity and Invocation Lineage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `task_id` and `parent_invocation_id` fields to the ANIP invocation surface, audit storage, and audit queries across all 5 runtimes — reducing workflow glue for task correlation and lineage reconstruction.

**Architecture:** Two optional fields flow through invoke request → service runtime → audit storage → audit query. The `task_id` has a precedence rule respecting delegation token `purpose.task_id`. Both fields are transport-neutral (HTTP, stdio, gRPC). No execution semantics — pure metadata.

**Tech Stack:** Python, TypeScript, Go, Java, C# runtimes + Protobuf + JSON Schema + Vue (Studio)

**Spec:** `docs/proposals/v0.12-task-identity-and-invocation-lineage.md`

---

## File Structure

```
SPEC.md                                         # MODIFY: §6.3 invocation + audit query params
schema/anip.schema.json                         # MODIFY: add fields to InvokeRequest + audit
proto/anip/v1/anip.proto                        # MODIFY: InvokeRequest, InvokeResponse, CompletedEvent, FailedEvent, QueryAuditRequest

# Python
packages/python/anip-core/src/anip_core/models.py          # MODIFY: add fields to InvokeRequest + InvokeResponse
packages/python/anip-service/src/anip_service/service.py   # MODIFY: accept + propagate fields
packages/python/anip-server/src/anip_server/storage.py     # MODIFY: persist + query fields
packages/python/anip-server/src/anip_server/postgres.py    # MODIFY: persist + query fields
packages/python/anip-fastapi/src/anip_fastapi/routes.py    # MODIFY: extract fields from request body

# TypeScript
packages/typescript/service/src/service.ts                 # MODIFY: accept + propagate fields
packages/typescript/server/src/audit.ts (or storage)       # MODIFY: persist + query fields
packages/typescript/hono/src/routes.ts                     # MODIFY: extract fields from request body

# Go
packages/go/server/audit.go (or storage.go)               # MODIFY: persist + query fields
packages/go/service/service.go                             # MODIFY: accept + propagate fields
packages/go/httpapi/handler.go                             # MODIFY: extract fields from request body

# Java
packages/java/anip-service/...                             # MODIFY: accept + propagate fields
packages/java/anip-server/...                              # MODIFY: persist + query fields
packages/java/anip-spring-boot/...                         # MODIFY: extract fields from request body

# C#
packages/csharp/src/Anip.Service/...                       # MODIFY: accept + propagate fields
packages/csharp/src/Anip.Server/...                        # MODIFY: persist + query fields
packages/csharp/src/Anip.AspNetCore/...                    # MODIFY: extract fields from request body

# Transport adapters
packages/python/anip-stdio/...                             # MODIFY: pass fields through
packages/python/anip-grpc/...                              # MODIFY: map proto fields
packages/go/stdioapi/...                                   # MODIFY: pass fields through
packages/go/grpcapi/...                                    # MODIFY: map proto fields

# Testing
conformance/                                               # MODIFY: add field echo + audit query tests

# Studio
studio/src/views/InvokeView.vue                            # MODIFY: show task_id + parent in result
studio/src/views/AuditView.vue                             # MODIFY: show fields + filter support
```

---

## Task 1: Spec and Schema Updates

**Files:**
- Modify: `SPEC.md`
- Modify: `schema/anip.schema.json`
- Modify: `proto/anip/v1/anip.proto`

- [ ] **Step 1: Update SPEC.md §6.3 Invocation request**

Add `task_id` and `parent_invocation_id` to the invocation request YAML:

```yaml
parameters: { ... }
budget: { ... }
client_reference_id: "task:abc/3"
task_id: "trip-planning-2026"          # NEW — optional, max 256 chars
parent_invocation_id: "inv-a1b2c3..."  # NEW — optional, inv-{hex12} format
stream: false
```

Add the `task_id` precedence rule text after the request schema.

Add both fields to the invocation response YAML (echoed when provided).

Add both fields to the audit query parameters list in §6.3.

- [ ] **Step 2: Update JSON Schema**

In `schema/anip.schema.json`, add to the `InvokeRequest` definition:

```json
"task_id": {
  "type": "string",
  "maxLength": 256,
  "description": "Caller-supplied task/workflow identity for grouping related invocations"
},
"parent_invocation_id": {
  "type": "string",
  "pattern": "^inv-[0-9a-f]{12}$",
  "description": "Reference to the invocation that triggered this one"
}
```

Add the same fields to the `InvokeResponse` and audit entry definitions.

- [ ] **Step 3: Update gRPC proto**

In `proto/anip/v1/anip.proto`, add to `InvokeRequest`:

```protobuf
message InvokeRequest {
  string capability = 1;
  string parameters_json = 2;
  string client_reference_id = 3;
  string task_id = 4;                  // NEW
  string parent_invocation_id = 5;     // NEW
}
```

Add to `InvokeResponse` (unary):

```protobuf
message InvokeResponse {
  bool success = 1;
  string invocation_id = 2;
  string client_reference_id = 3;
  string result_json = 4;
  AnipFailure failure = 5;
  string cost_actual_json = 6;
  string task_id = 7;                  // NEW
  string parent_invocation_id = 8;     // NEW
}
```

Add to `CompletedEvent` and `FailedEvent` (streaming — transport parity):

```protobuf
message CompletedEvent {
  string invocation_id = 1;
  string client_reference_id = 2;
  string result_json = 3;
  string cost_actual_json = 4;
  string task_id = 5;                  // NEW
  string parent_invocation_id = 6;     // NEW
}

message FailedEvent {
  string invocation_id = 1;
  string client_reference_id = 2;
  AnipFailure failure = 3;
  string task_id = 4;                  // NEW
  string parent_invocation_id = 5;     // NEW
}
```

Add to `QueryAuditRequest`:

```protobuf
message QueryAuditRequest {
  string capability = 1;
  string since = 2;
  string invocation_id = 3;
  string client_reference_id = 4;
  string event_class = 5;
  int32 limit = 6;
  string task_id = 7;                  // NEW
  string parent_invocation_id = 8;     // NEW
}
```

- [ ] **Step 4: Commit**

```bash
git add SPEC.md schema/anip.schema.json proto/anip/v1/anip.proto
git commit -m "spec: add task_id and parent_invocation_id to invocation and audit (v0.12)"
```

---

## Task 2: Python Runtime Implementation

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/python/anip-server/src/anip_server/storage.py`
- Modify: `packages/python/anip-server/src/anip_server/postgres.py`
- Modify: `packages/python/anip-fastapi/src/anip_fastapi/routes.py`

- [ ] **Step 1: Update shared models in `anip_core/models.py`**

Add fields to `InvokeRequest`:

```python
class InvokeRequest(BaseModel):
    token: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] | None = None
    client_reference_id: str | None = Field(default=None, max_length=256)
    task_id: str | None = Field(default=None, max_length=256)
    parent_invocation_id: str | None = Field(default=None, pattern=r"^inv-[0-9a-f]{12}$")
    stream: bool = False
```

Add fields to `InvokeResponse`:

```python
class InvokeResponse(BaseModel):
    success: bool
    invocation_id: str = Field(pattern=r"^inv-[0-9a-f]{12}$")
    client_reference_id: str | None = None
    task_id: str | None = None
    parent_invocation_id: str | None = None
    result: dict[str, Any] | None = None
    cost_actual: CostActual | None = None
    failure: ANIPFailure | None = None
    session: dict[str, Any] | None = None
    stream_summary: StreamSummary | None = None
```

- [ ] **Step 2: Update `service.py` invoke method**

Add `task_id` and `parent_invocation_id` parameters to both `invoke()` and `_invoke_body()`. Implement the precedence rule inside `_invoke_body()` using the existing inline failure pattern (NOT a helper — match the current style at service.py:587):

```python
# task_id precedence: token purpose > request > none
token_task_id = getattr(token.purpose, 'task_id', None) if token.purpose else None
if token_task_id and task_id and task_id != token_task_id:
    _duration_ms = int((time.monotonic() - invoke_start) * 1000)
    return {
        "success": False,
        "failure": {"type": "purpose_mismatch",
                    "detail": f"Request task_id '{task_id}' does not match token purpose task_id '{token_task_id}'"},
        "invocation_id": invocation_id,
        "client_reference_id": client_reference_id,
        "task_id": task_id,
        "parent_invocation_id": parent_invocation_id,
    }
effective_task_id = task_id or token_task_id
```

Include `effective_task_id` and `parent_invocation_id` in all response dicts and audit entries throughout the method (follow the same pattern used for `client_reference_id`).

- [ ] **Step 2: Update storage `query_audit_entries` signature**

Add `task_id` and `parent_invocation_id` filter parameters to the `StorageBackend` abstract method, `InMemoryStorage`, `SQLiteStorage`, and `PostgresStorage` implementations.

- [ ] **Step 3: Update `routes.py` to extract new fields from request body**

```python
body = await request.json()
params = body.get("parameters", body)
client_reference_id = body.get("client_reference_id")
task_id = body.get("task_id")
parent_invocation_id = body.get("parent_invocation_id")
stream = body.get("stream", False)

result = await service.invoke(
    capability, token, params,
    client_reference_id=client_reference_id,
    task_id=task_id,
    parent_invocation_id=parent_invocation_id,
)
```

Update the audit endpoint to accept `task_id` and `parent_invocation_id` query params.

- [ ] **Step 4: Update stdio and gRPC transports**

Pass `task_id` and `parent_invocation_id` through the stdio JSON-RPC invoke handler and gRPC invoke handler to `service.invoke()`.

Update audit query handlers to pass the new filter params.

- [ ] **Step 5: Run existing Python tests**

Run: `pytest packages/python/ -x -v`
Expected: all existing tests pass (new fields are optional, no breaking changes)

- [ ] **Step 6: Add Python tests for new fields**

Add tests to `packages/python/anip-service/tests/`:
- `test_invoke_with_task_id` — verify `task_id` echoed in response and recorded in audit
- `test_invoke_with_parent_invocation_id` — verify field echoed and recorded
- `test_task_id_precedence_from_token` — token purpose.task_id used when request omits it
- `test_task_id_mismatch_rejected` — request task_id != token purpose.task_id → purpose_mismatch failure
- `test_audit_query_by_task_id` — filter audit entries by task_id
- `test_audit_query_by_parent_invocation_id` — filter audit by parent

- [ ] **Step 7: Run all Python tests**

Run: `pytest packages/python/ -x -v`
Expected: all tests pass including new ones

- [ ] **Step 8: Commit**

```bash
git add packages/python/
git commit -m "feat(python): add task_id and parent_invocation_id to invoke + audit (v0.12)"
```

---

## Task 3: TypeScript Runtime Implementation

Same pattern as Python — add fields to service invoke, storage query, HTTP route extraction, stdio/transport pass-through. Add tests.

**Files:**
- Modify: `packages/typescript/service/src/service.ts`
- Modify: `packages/typescript/server/` (storage/audit files)
- Modify: `packages/typescript/hono/src/routes.ts`
- Modify: `packages/typescript/express/src/routes.ts`
- Modify: `packages/typescript/fastify/src/routes.ts`
- Modify: `packages/typescript/stdio/src/server.ts`

- [ ] **Step 1:** Add `taskId` and `parentInvocationId` to the invoke method and propagate through audit
- [ ] **Step 2:** Add `task_id` precedence rule matching Python implementation
- [ ] **Step 3:** Extract new fields from request body in all framework adapters
- [ ] **Step 4:** Add audit query filter support
- [ ] **Step 5:** Pass fields through stdio transport
- [ ] **Step 6:** Add tests
- [ ] **Step 7:** Run: `cd packages/typescript && npm test --workspaces`
- [ ] **Step 8:** Commit

---

## Task 4: Go Runtime Implementation

**Files:**
- Modify: `packages/go/service/` (invoke method)
- Modify: `packages/go/server/` (storage, audit)
- Modify: `packages/go/httpapi/handler.go`
- Modify: `packages/go/stdioapi/`
- Modify: `packages/go/grpcapi/`

- [ ] **Step 1:** Add `TaskID` and `ParentInvocationID` to invoke context and propagate
- [ ] **Step 2:** Add `task_id` precedence rule
- [ ] **Step 3:** Extract fields from HTTP request body
- [ ] **Step 4:** Add audit query filter support
- [ ] **Step 5:** Pass fields through stdio and gRPC transports (gRPC uses updated proto)
- [ ] **Step 6:** Regenerate gRPC Go code from updated proto
- [ ] **Step 7:** Add tests
- [ ] **Step 8:** Run: `cd packages/go && go test ./...`
- [ ] **Step 9:** Commit

---

## Task 5: Java Runtime Implementation

**Files:**
- Modify: `packages/java/anip-service/` (invoke method)
- Modify: `packages/java/anip-server/` (storage, audit)
- Modify: `packages/java/anip-spring-boot/` (controller)
- Modify: `packages/java/anip-stdio/`

- [ ] **Step 1:** Add `taskId` and `parentInvocationId` to invoke and propagate
- [ ] **Step 2:** Add `task_id` precedence rule
- [ ] **Step 3:** Extract fields from Spring controller request body
- [ ] **Step 4:** Add audit query filter support
- [ ] **Step 5:** Pass fields through stdio transport
- [ ] **Step 6:** Add tests
- [ ] **Step 7:** Run: `cd packages/java && mvn test`
- [ ] **Step 8:** Commit

---

## Task 6: C# Runtime Implementation

**Files:**
- Modify: `packages/csharp/src/Anip.Service/`
- Modify: `packages/csharp/src/Anip.Server/`
- Modify: `packages/csharp/src/Anip.AspNetCore/`
- Modify: `packages/csharp/src/Anip.Stdio/`

- [ ] **Step 1:** Add `TaskId` and `ParentInvocationId` to invoke and propagate
- [ ] **Step 2:** Add `task_id` precedence rule
- [ ] **Step 3:** Extract fields from ASP.NET controller request body
- [ ] **Step 4:** Add audit query filter support
- [ ] **Step 5:** Pass fields through stdio transport
- [ ] **Step 6:** Add tests
- [ ] **Step 7:** Run: `cd packages/csharp && dotnet test`
- [ ] **Step 8:** Commit

---

## Task 7: Conformance Suite

**Files:**
- Modify: `conformance/`

- [ ] **Step 1: Add field echo tests**

Test that when `task_id` and `parent_invocation_id` are provided in an invocation request, they are echoed in the response.

- [ ] **Step 2: Add audit recording tests**

Test that invocations with `task_id` and `parent_invocation_id` produce audit entries containing those fields.

- [ ] **Step 3: Add audit query filter tests**

Test that `?task_id=X` and `?parent_invocation_id=Y` query params filter audit entries correctly.

- [ ] **Step 4: Add task_id precedence test**

Test that when a delegation token has `purpose.task_id`, the invocation response uses it even when the request omits `task_id`. Test that a mismatch is rejected.

- [ ] **Step 5:** Run: `pytest conformance/ --base-url=http://localhost:9100 --bootstrap-bearer=demo-human-key`
- [ ] **Step 6:** Commit

---

## Task 8: Studio Updates

**Files:**
- Modify: `studio/src/views/AuditView.vue`
- Modify: `studio/src/components/InvokeResult.vue`
- Modify: `studio/src/api.ts`

- [ ] **Step 1: Show `task_id` and `parent_invocation_id` in InvokeResult**

Display both fields in the success and failure result panels (alongside `invocation_id` and `client_reference_id`).

- [ ] **Step 2: Show fields in AuditView entries**

Display `task_id` and `parent_invocation_id` in audit entry cards when present.

- [ ] **Step 3: Add task_id filter to AuditView**

Add a `task_id` filter input to the audit view, passed as a query parameter to the audit API call.

- [ ] **Step 4: Build, test, sync**

```bash
cd studio && npx vitest run && bash sync.sh
```

- [ ] **Step 5:** Commit

---

## Task 9: Website Documentation Updates

**Files:**
- Modify: `website/docs/protocol/reference.md`
- Modify: `website/docs/protocol/lineage.md`
- Modify: `website/docs/getting-started/quickstart.md` (optionally)

- [ ] **Step 1: Update protocol reference**

Add `task_id` and `parent_invocation_id` to the invocation request table, response fields, and audit query parameters table.

- [ ] **Step 2: Update lineage page**

Add examples showing how `task_id` groups invocations and `parent_invocation_id` forms invocation trees. Show the audit query by task_id.

- [ ] **Step 3:** Commit

---

## Task 10: Version Bump and Release Prep

- [ ] **Step 1:** Update protocol version references from `0.11` to `0.12` in SPEC.md, discovery document defaults, and docs
- [ ] **Step 2:** Commit: `chore: prepare v0.12.0 release`
- [ ] **Step 3:** Trigger release workflow with version `0.12.0`
