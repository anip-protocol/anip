# v0.4 Lineage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add protocol-level lineage (`invocation_id` + `client_reference_id`) to ANIP invoke operations, collapse the legacy InvokeRequest/InvokeRequestV2 split, and bump all 13 packages to 0.4.0.

**Architecture:** Lineage fields are added to core models (anip-core / @anip-dev/core), threaded through the service runtime's invoke() → InvocationContext → audit → response pipeline, persisted in server storage with query support, and wired through all 5 framework bindings. The old embedded-token `InvokeRequest` is deleted; `InvokeRequestV2` is renamed to `InvokeRequest`.

**Tech Stack:** Python (Pydantic, SQLite, Flask, FastAPI), TypeScript (Zod, better-sqlite3, Hono, Express, Fastify), pytest, vitest.

**Design doc:** `docs/plans/2026-03-15-v04-lineage-design.md`

**Lineage boundary:** Lineage starts when `service.invoke()` is called. Bearer token authentication happens in the framework bindings *before* `invoke()` — unauthenticated requests (401) are transport-level rejections and do not receive an `invocation_id` or audit entry. This is correct: a 401 is not an invocation. Lineage covers all paths *inside* `invoke()`: unknown capability, delegation validation failure, handler errors, and success.

---

## Task 1: Python Core Models — Collapse InvokeRequest + Add Lineage Fields

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/python/anip-core/src/anip_core/__init__.py`
- Test: `packages/python/anip-core/tests/test_models.py`

**Context:** Currently `models.py` has two invoke request models:
- `InvokeRequestV2` (line 250): JWT-based — `token`, `parameters`, `budget`
- `InvokeRequest` (line 257): legacy embedded-token — `delegation_token`, `parameters`, `budget`

v0.4 collapses these. The JWT-based shape becomes the only `InvokeRequest`.

**Step 1: Write failing tests for the new model shapes**

Add to `packages/python/anip-core/tests/test_models.py` (extend the existing file — do not overwrite existing tests):

```python
"""Tests for v0.4 invoke model shapes."""
import re
import pytest
from anip_core import InvokeRequest, InvokeResponse


class TestInvokeRequest:
    def test_minimal_request(self):
        req = InvokeRequest(token="jwt.token.here")
        assert req.token == "jwt.token.here"
        assert req.parameters == {}
        assert req.budget is None
        assert req.client_reference_id is None

    def test_with_client_reference_id(self):
        req = InvokeRequest(
            token="jwt.token.here",
            client_reference_id="task:abc/step:3",
        )
        assert req.client_reference_id == "task:abc/step:3"

    def test_client_reference_id_max_length(self):
        # 256 chars should be fine
        req = InvokeRequest(token="t", client_reference_id="x" * 256)
        assert len(req.client_reference_id) == 256

        # 257 chars should fail
        with pytest.raises(Exception):
            InvokeRequest(token="t", client_reference_id="x" * 257)

    def test_no_delegation_token_field(self):
        """InvokeRequest should NOT have a delegation_token field (legacy removed)."""
        req = InvokeRequest(token="t")
        assert not hasattr(req, "delegation_token")


class TestInvokeResponse:
    def test_response_with_lineage(self):
        resp = InvokeResponse(
            success=True,
            invocation_id="inv-a1b2c3d4e5f6",
            result={"message": "ok"},
        )
        assert resp.invocation_id == "inv-a1b2c3d4e5f6"
        assert resp.client_reference_id is None

    def test_response_echoes_client_reference_id(self):
        resp = InvokeResponse(
            success=True,
            invocation_id="inv-a1b2c3d4e5f6",
            client_reference_id="my-ref",
            result={"message": "ok"},
        )
        assert resp.client_reference_id == "my-ref"

    def test_invocation_id_format(self):
        """invocation_id must match inv-{12 hex chars}."""
        # Valid
        resp = InvokeResponse(success=True, invocation_id="inv-a1b2c3d4e5f6")
        assert resp.invocation_id == "inv-a1b2c3d4e5f6"

        # Invalid format should fail
        with pytest.raises(Exception):
            InvokeResponse(success=True, invocation_id="bad-format")

    def test_invocation_id_required(self):
        """invocation_id is required on response."""
        with pytest.raises(Exception):
            InvokeResponse(success=True)
```

**Step 2: Run tests — verify they fail**

```bash
cd /path/to/repo && pytest packages/python/anip-core/tests/test_models.py -v
```

Expected: Multiple failures (no `client_reference_id` on InvokeRequest, no `invocation_id` on InvokeResponse, old `InvokeRequest` still has `delegation_token`).

**Step 3: Update models.py**

In `packages/python/anip-core/src/anip_core/models.py`:

1. Delete the old `InvokeRequest` class (lines 257-261):
```python
# DELETE THIS:
class InvokeRequest(BaseModel):
    delegation_token: DelegationToken
    parameters: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] | None = None
```

2. Rename `InvokeRequestV2` (lines 250-255) to `InvokeRequest` and add `client_reference_id`:
```python
class InvokeRequest(BaseModel):
    """Invoke request with JWT token and optional lineage reference."""
    token: str  # JWT string
    parameters: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] | None = None
    client_reference_id: str | None = Field(default=None, max_length=256)
```

3. Update `InvokeResponse` (lines 263-269) to add lineage fields:
```python
class InvokeResponse(BaseModel):
    success: bool
    invocation_id: str = Field(pattern=r"^inv-[0-9a-f]{12}$")
    client_reference_id: str | None = None
    result: dict[str, Any] | None = None
    cost_actual: CostActual | None = None
    failure: ANIPFailure | None = None
    session: dict[str, Any] | None = None
```

**Step 4: Update __init__.py**

In `packages/python/anip-core/src/anip_core/__init__.py`:

1. Remove the import of `InvokeRequestV2` (line 30):
```python
# DELETE: InvokeRequestV2,
```

2. Remove `"InvokeRequestV2"` from the `__all__` list (line 80):
```python
# DELETE: "InvokeRequestV2",
```

Keep `InvokeRequest` — it now refers to the renamed (JWT-based) model.

**Step 5: Run tests — verify they pass**

```bash
pytest packages/python/anip-core/tests/test_models.py -v
```

Expected: All pass.

**Step 6: Run existing core tests to check for regressions**

```bash
pytest packages/python/anip-core/tests/ -v
```

Expected: All pass.

**Step 7: Commit**

```bash
git add packages/python/anip-core/
git commit -m "feat(core): collapse InvokeRequest + add lineage fields (Python)"
```

---

## Task 2: TypeScript Core Models — Collapse InvokeRequest + Add Lineage Fields

**Files:**
- Modify: `packages/typescript/core/src/models.ts`
- Test: `packages/typescript/core/tests/models.test.ts`

**Context:** Currently `models.ts` has:
- `InvokeRequest` (lines 267-272): legacy embedded-token with `delegation_token`
- `InvokeRequestV2` (lines 301-306): JWT-based with `token`

Same collapse as Python.

**Step 1: Write failing tests**

Add to `packages/typescript/core/tests/models.test.ts` (extend the existing file — do not overwrite existing tests):

```typescript
import { describe, it, expect } from "vitest";
import { InvokeRequest, InvokeResponse } from "../src/models.js";

describe("InvokeRequest", () => {
  it("minimal request", () => {
    const req = InvokeRequest.parse({ token: "jwt.token.here" });
    expect(req.token).toBe("jwt.token.here");
    expect(req.parameters).toEqual({});
    expect(req.budget).toBeNull();
    expect(req.client_reference_id).toBeNull();
  });

  it("with client_reference_id", () => {
    const req = InvokeRequest.parse({
      token: "jwt.token.here",
      client_reference_id: "task:abc/step:3",
    });
    expect(req.client_reference_id).toBe("task:abc/step:3");
  });

  it("client_reference_id max length 256", () => {
    // 256 chars should parse
    const req = InvokeRequest.parse({
      token: "t",
      client_reference_id: "x".repeat(256),
    });
    expect(req.client_reference_id!.length).toBe(256);

    // 257 chars should fail
    expect(() =>
      InvokeRequest.parse({
        token: "t",
        client_reference_id: "x".repeat(257),
      }),
    ).toThrow();
  });

  it("no delegation_token field", () => {
    const req = InvokeRequest.parse({ token: "t" });
    expect((req as Record<string, unknown>).delegation_token).toBeUndefined();
  });
});

describe("InvokeResponse", () => {
  it("response with lineage", () => {
    const resp = InvokeResponse.parse({
      success: true,
      invocation_id: "inv-a1b2c3d4e5f6",
      result: { message: "ok" },
    });
    expect(resp.invocation_id).toBe("inv-a1b2c3d4e5f6");
    expect(resp.client_reference_id).toBeNull();
  });

  it("echoes client_reference_id", () => {
    const resp = InvokeResponse.parse({
      success: true,
      invocation_id: "inv-a1b2c3d4e5f6",
      client_reference_id: "my-ref",
    });
    expect(resp.client_reference_id).toBe("my-ref");
  });

  it("invocation_id format validated", () => {
    expect(() =>
      InvokeResponse.parse({ success: true, invocation_id: "bad-format" }),
    ).toThrow();
  });

  it("invocation_id required", () => {
    expect(() => InvokeResponse.parse({ success: true })).toThrow();
  });
});
```

**Step 2: Run tests — verify they fail**

```bash
cd packages/typescript && npx vitest run core/tests/models.test.ts
```

**Step 3: Update models.ts**

In `packages/typescript/core/src/models.ts`:

1. Delete the old `InvokeRequest` (lines 267-272):
```typescript
// DELETE:
export const InvokeRequest = z.object({
  delegation_token: DelegationToken,
  parameters: z.record(z.any()).default({}),
  budget: z.record(z.any()).nullable().default(null),
});
export type InvokeRequest = z.infer<typeof InvokeRequest>;
```

2. Rename `InvokeRequestV2` (lines 301-306) to `InvokeRequest` and add `client_reference_id`:
```typescript
export const InvokeRequest = z.object({
  token: z.string(),
  parameters: z.record(z.any()).default({}),
  budget: z.record(z.any()).nullable().default(null),
  client_reference_id: z.string().max(256).nullable().default(null),
});
export type InvokeRequest = z.infer<typeof InvokeRequest>;
```

3. Update `InvokeResponse` (lines 274-281) to add lineage fields:
```typescript
export const InvokeResponse = z.object({
  success: z.boolean(),
  invocation_id: z.string().regex(/^inv-[0-9a-f]{12}$/),
  client_reference_id: z.string().max(256).nullable().default(null),
  result: z.record(z.any()).nullable().default(null),
  cost_actual: CostActual.nullable().default(null),
  failure: ANIPFailure.nullable().default(null),
  session: z.record(z.any()).nullable().default(null),
});
export type InvokeResponse = z.infer<typeof InvokeResponse>;
```

**Step 4: Run tests — verify they pass**

```bash
cd packages/typescript && npx vitest run core/tests/models.test.ts
```

**Step 5: Run existing core tests**

```bash
cd packages/typescript && npm test --workspace=@anip-dev/core
```

**Step 6: Commit**

```bash
git add packages/typescript/core/
git commit -m "feat(core): collapse InvokeRequest + add lineage fields (TypeScript)"
```

---

## Task 3: Python Server — Storage Schema + Audit Lineage

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/storage.py`
- Modify: `packages/python/anip-server/src/anip_server/audit.py`
- Test: `packages/python/anip-server/tests/test_audit.py`

**Context:** The audit `log_entry()` method (audit.py:25-69) builds an entry dict from `entry_data`. Storage uses SQLite with `store_audit_entry()` (storage.py:171-202) and `query_audit_entries()` (storage.py:213-241). Both need to handle the new `invocation_id` and `client_reference_id` fields.

**Step 1: Write failing tests**

Create `packages/python/anip-server/tests/test_audit.py`:

```python
"""Tests for audit log lineage fields."""
from anip_server.audit import AuditLog
from anip_server.storage import SQLiteStorage


def _make_audit():
    storage = SQLiteStorage(":memory:")
    return AuditLog(storage), storage


def test_audit_entry_includes_lineage_fields():
    audit, storage = _make_audit()
    entry = audit.log_entry({
        "capability": "greet",
        "success": True,
        "invocation_id": "inv-a1b2c3d4e5f6",
        "client_reference_id": "my-ref-123",
    })
    assert entry["invocation_id"] == "inv-a1b2c3d4e5f6"
    assert entry["client_reference_id"] == "my-ref-123"


def test_audit_entry_lineage_fields_optional():
    audit, storage = _make_audit()
    entry = audit.log_entry({
        "capability": "greet",
        "success": True,
    })
    assert entry["invocation_id"] is None
    assert entry["client_reference_id"] is None


def test_audit_entry_persisted_with_lineage():
    audit, storage = _make_audit()
    audit.log_entry({
        "capability": "greet",
        "success": True,
        "invocation_id": "inv-a1b2c3d4e5f6",
        "client_reference_id": "task:42",
    })
    entries = storage.query_audit_entries()
    assert len(entries) == 1
    assert entries[0]["invocation_id"] == "inv-a1b2c3d4e5f6"
    assert entries[0]["client_reference_id"] == "task:42"


def test_query_audit_by_invocation_id():
    audit, storage = _make_audit()
    audit.log_entry({
        "capability": "greet",
        "success": True,
        "invocation_id": "inv-aaaaaaaaaaaa",
    })
    audit.log_entry({
        "capability": "greet",
        "success": True,
        "invocation_id": "inv-bbbbbbbbbbbb",
    })
    entries = storage.query_audit_entries(invocation_id="inv-aaaaaaaaaaaa")
    assert len(entries) == 1
    assert entries[0]["invocation_id"] == "inv-aaaaaaaaaaaa"


def test_query_audit_by_client_reference_id():
    audit, storage = _make_audit()
    audit.log_entry({
        "capability": "greet",
        "success": True,
        "invocation_id": "inv-aaaaaaaaaaaa",
        "client_reference_id": "task:42",
    })
    audit.log_entry({
        "capability": "search",
        "success": True,
        "invocation_id": "inv-bbbbbbbbbbbb",
        "client_reference_id": "task:42",
    })
    audit.log_entry({
        "capability": "greet",
        "success": True,
        "invocation_id": "inv-cccccccccccc",
        "client_reference_id": "task:99",
    })
    entries = storage.query_audit_entries(client_reference_id="task:42")
    assert len(entries) == 2
    assert all(e["client_reference_id"] == "task:42" for e in entries)
```

**Step 2: Run tests — verify they fail**

```bash
pytest packages/python/anip-server/tests/test_audit.py -v
```

**Step 3: Update storage.py**

In `packages/python/anip-server/src/anip_server/storage.py`:

1. Add columns to the `CREATE TABLE audit_log` statement (after `delegation_chain TEXT,`):
```sql
invocation_id TEXT,
client_reference_id TEXT,
```

2. Add indices after the existing index statements:
```sql
CREATE INDEX IF NOT EXISTS idx_audit_invocation_id ON audit_log(invocation_id);
CREATE INDEX IF NOT EXISTS idx_audit_client_reference_id ON audit_log(client_reference_id);
```

3. Update `store_audit_entry()` — add the two new columns to the INSERT statement:
```sql
INSERT INTO audit_log
    (sequence_number, timestamp, capability, token_id, issuer,
     subject, root_principal, parameters, success, result_summary,
     failure_type, cost_actual, delegation_chain, previous_hash,
     signature, invocation_id, client_reference_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```
Add to the values tuple:
```python
entry.get("invocation_id"),
entry.get("client_reference_id"),
```

4. Update `query_audit_entries()` — add two new optional parameters and filter conditions:
```python
def query_audit_entries(
    self,
    *,
    capability: str | None = None,
    root_principal: str | None = None,
    since: str | None = None,
    invocation_id: str | None = None,
    client_reference_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
```
Add filter conditions:
```python
if invocation_id is not None:
    conditions.append("invocation_id = ?")
    params.append(invocation_id)
if client_reference_id is not None:
    conditions.append("client_reference_id = ?")
    params.append(client_reference_id)
```

5. `_parse_audit_row()` uses `dict(row)` which automatically picks up new columns — **no change needed**.

6. Add migration support for existing v0.3 databases. After the `CREATE TABLE IF NOT EXISTS` block, add:
```python
# Migrate existing v0.3 databases: add lineage columns if missing
try:
    self._conn.execute("ALTER TABLE audit_log ADD COLUMN invocation_id TEXT")
except Exception:
    pass  # column already exists
try:
    self._conn.execute("ALTER TABLE audit_log ADD COLUMN client_reference_id TEXT")
except Exception:
    pass  # column already exists
```
This ensures both fresh and existing databases have the new columns.

**Step 4: Update audit.py**

In `packages/python/anip-server/src/anip_server/audit.py`, update `log_entry()`:

Add to the `entry` dict construction (after `"delegation_chain"` line):
```python
"invocation_id": entry_data.get("invocation_id"),
"client_reference_id": entry_data.get("client_reference_id"),
```

**Step 5: Run tests — verify they pass**

```bash
pytest packages/python/anip-server/tests/test_audit.py -v
```

**Step 6: Run all server tests**

```bash
pytest packages/python/anip-server/tests/ -v
```

**Step 7: Commit**

```bash
git add packages/python/anip-server/
git commit -m "feat(server): add lineage columns and query filters to audit (Python)"
```

---

## Task 4: TypeScript Server — Storage Schema + Audit Lineage

**Files:**
- Modify: `packages/typescript/server/src/storage.ts`
- Modify: `packages/typescript/server/src/audit.ts`
- Test: `packages/typescript/server/tests/audit.test.ts`

**Context:** Same changes as Task 3 but for TypeScript. `storeAuditEntry()` is at storage.ts:233-264, `queryAuditEntries()` at storage.ts:277-309, `logEntry()` at audit.ts:37-77.

**Step 1: Write failing tests**

Create `packages/typescript/server/tests/audit.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { AuditLog } from "../src/audit.js";
import { InMemoryStorage } from "../src/storage.js";

function makeAudit() {
  const storage = new InMemoryStorage();
  return { audit: new AuditLog(storage), storage };
}

describe("Audit lineage fields", () => {
  it("entry includes lineage fields", async () => {
    const { audit } = makeAudit();
    const entry = await audit.logEntry({
      capability: "greet",
      success: true,
      invocation_id: "inv-a1b2c3d4e5f6",
      client_reference_id: "my-ref-123",
    });
    expect(entry.invocation_id).toBe("inv-a1b2c3d4e5f6");
    expect(entry.client_reference_id).toBe("my-ref-123");
  });

  it("lineage fields default to null", async () => {
    const { audit } = makeAudit();
    const entry = await audit.logEntry({
      capability: "greet",
      success: true,
    });
    expect(entry.invocation_id).toBeNull();
    expect(entry.client_reference_id).toBeNull();
  });

  it("lineage fields persisted and queryable", async () => {
    const { audit, storage } = makeAudit();
    await audit.logEntry({
      capability: "greet",
      success: true,
      invocation_id: "inv-a1b2c3d4e5f6",
      client_reference_id: "task:42",
    });
    const entries = storage.queryAuditEntries();
    expect(entries).toHaveLength(1);
    expect(entries[0].invocation_id).toBe("inv-a1b2c3d4e5f6");
    expect(entries[0].client_reference_id).toBe("task:42");
  });

  it("query by invocation_id", async () => {
    const { audit, storage } = makeAudit();
    await audit.logEntry({
      capability: "greet",
      success: true,
      invocation_id: "inv-aaaaaaaaaaaa",
    });
    await audit.logEntry({
      capability: "greet",
      success: true,
      invocation_id: "inv-bbbbbbbbbbbb",
    });
    const entries = storage.queryAuditEntries({
      invocationId: "inv-aaaaaaaaaaaa",
    });
    expect(entries).toHaveLength(1);
    expect(entries[0].invocation_id).toBe("inv-aaaaaaaaaaaa");
  });

  it("query by client_reference_id", async () => {
    const { audit, storage } = makeAudit();
    await audit.logEntry({
      capability: "greet",
      success: true,
      invocation_id: "inv-aaaaaaaaaaaa",
      client_reference_id: "task:42",
    });
    await audit.logEntry({
      capability: "search",
      success: true,
      invocation_id: "inv-bbbbbbbbbbbb",
      client_reference_id: "task:42",
    });
    await audit.logEntry({
      capability: "greet",
      success: true,
      invocation_id: "inv-cccccccccccc",
      client_reference_id: "task:99",
    });
    const entries = storage.queryAuditEntries({
      clientReferenceId: "task:42",
    });
    expect(entries).toHaveLength(2);
    expect(entries.every((e) => e.client_reference_id === "task:42")).toBe(true);
  });
});
```

**Step 2: Run tests — verify they fail**

```bash
cd packages/typescript && npx vitest run server/tests/audit.test.ts
```

**Step 3: Update storage.ts**

In `packages/typescript/server/src/storage.ts`:

1. Add columns to `CREATE TABLE audit_log` (after `delegation_chain TEXT,`):
```sql
invocation_id TEXT,
client_reference_id TEXT,
```

2. Add indices:
```sql
CREATE INDEX IF NOT EXISTS idx_audit_invocation_id ON audit_log(invocation_id);
CREATE INDEX IF NOT EXISTS idx_audit_client_reference_id ON audit_log(client_reference_id);
```

3. Update `storeAuditEntry()` — add columns to INSERT and values.

4. Update `queryAuditEntries()` — add optional parameters:
```typescript
queryAuditEntries(opts?: {
  capability?: string;
  rootPrincipal?: string;
  since?: string;
  invocationId?: string;
  clientReferenceId?: string;
  limit?: number;
}): Record<string, unknown>[]
```
Add filter conditions:
```typescript
if (opts?.invocationId) {
  conditions.push("invocation_id = ?");
  params.push(opts.invocationId);
}
if (opts?.clientReferenceId) {
  conditions.push("client_reference_id = ?");
  params.push(opts.clientReferenceId);
}
```

5. Check `parseAuditRow()` — if it uses object spread or key-based access, new columns are picked up automatically. If it uses positional indices, add the new fields by name.

6. **Also update `InMemoryStorage`** — its `storeAuditEntry()` and `queryAuditEntries()` must handle the new fields too. The in-memory store should filter by `invocation_id` and `client_reference_id` when queried.

7. Add migration support for existing v0.3 SQLite databases. After the `CREATE TABLE IF NOT EXISTS` block, run `ALTER TABLE audit_log ADD COLUMN invocation_id TEXT` and `ALTER TABLE audit_log ADD COLUMN client_reference_id TEXT`, each wrapped in a try/catch (column may already exist).

**Step 4: Update audit.ts**

In `packages/typescript/server/src/audit.ts`, update `logEntry()`:

Add to the `entry` object (after `delegation_chain`):
```typescript
invocation_id: entryData.invocation_id ?? null,
client_reference_id: entryData.client_reference_id ?? null,
```

**Step 5: Run tests — verify they pass**

```bash
cd packages/typescript && npx vitest run server/tests/audit.test.ts
```

**Step 6: Run all server tests**

```bash
cd packages/typescript && npm test --workspace=@anip-dev/server
```

**Step 7: Commit**

```bash
git add packages/typescript/server/
git commit -m "feat(server): add lineage columns and query filters to audit (TypeScript)"
```

---

## Task 5: Python Service Runtime — Thread Lineage Through Invoke

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/types.py`
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/python/anip-service/tests/test_service_init.py`

**Context:** The `invoke()` method (service.py:374-498) currently takes `(capability_name, token, params)`. It needs a 4th parameter `client_reference_id`, must generate `invocation_id` early, thread both into `InvocationContext`, include both in audit and response. `InvocationContext` (types.py:10-23) is a dataclass.

**Step 1: Write failing tests**

Add to `packages/python/anip-service/tests/test_service_init.py`, inside `TestANIPServiceInvoke`:

```python
def test_invoke_response_includes_invocation_id(self):
    service = self._make_service()
    token = self._issue_test_token(service)
    result = service.invoke("greet", token, {"name": "World"})
    assert result["success"] is True
    assert "invocation_id" in result
    assert result["invocation_id"].startswith("inv-")
    assert len(result["invocation_id"]) == 16  # "inv-" + 12 hex

def test_invoke_response_echoes_client_reference_id(self):
    service = self._make_service()
    token = self._issue_test_token(service)
    result = service.invoke(
        "greet", token, {"name": "World"},
        client_reference_id="task:42",
    )
    assert result["client_reference_id"] == "task:42"

def test_invoke_response_client_reference_id_null_when_absent(self):
    service = self._make_service()
    token = self._issue_test_token(service)
    result = service.invoke("greet", token, {"name": "World"})
    assert result["client_reference_id"] is None

def test_invoke_failure_still_has_invocation_id(self):
    service = self._make_service()
    token = self._issue_test_token(service)
    result = service.invoke("nonexistent", token, {})
    assert result["success"] is False
    assert "invocation_id" in result
    assert result["invocation_id"].startswith("inv-")

def test_invocation_context_has_lineage(self):
    """Handler should see invocation_id and client_reference_id in context."""
    captured_ctx = {}

    def capturing_handler(ctx, params):
        captured_ctx["invocation_id"] = ctx.invocation_id
        captured_ctx["client_reference_id"] = ctx.client_reference_id
        return {"ok": True}

    from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SideEffect, SideEffectType
    from anip_service import Capability
    cap = Capability(
        declaration=CapabilityDeclaration(
            name="ctx_cap",
            description="Captures context",
            contract_version="1.0",
            inputs=[],
            output=CapabilityOutput(type="object", fields=[]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["test"],
        ),
        handler=capturing_handler,
    )
    service = self._make_service(caps=[cap])
    token = self._issue_test_token(service, scope=["test"], capability="ctx_cap")
    result = service.invoke("ctx_cap", token, {}, client_reference_id="ref-abc")
    assert captured_ctx["invocation_id"].startswith("inv-")
    assert captured_ctx["client_reference_id"] == "ref-abc"
```

**Step 2: Run tests — verify they fail**

```bash
pytest packages/python/anip-service/tests/test_service_init.py::TestANIPServiceInvoke -v
```

**Step 3: Update types.py — add lineage fields to InvocationContext**

In `packages/python/anip-service/src/anip_service/types.py`, update the `InvocationContext` dataclass:

```python
@dataclass
class InvocationContext:
    """Context passed to capability handlers during invocation."""
    token: DelegationToken
    root_principal: str
    subject: str
    scopes: list[str]
    delegation_chain: list[str]
    invocation_id: str = ""
    client_reference_id: str | None = None
    _cost_actual: dict[str, Any] | None = field(default=None, repr=False)

    def set_cost_actual(self, cost: dict[str, Any]) -> None:
        """Set actual cost for variance tracking against declared cost."""
        self._cost_actual = cost
```

**Step 4: Update service.py — widen invoke() and thread lineage**

In `packages/python/anip-service/src/anip_service/service.py`:

1. Add `import uuid` at the top of the file.

2. Update `invoke()` method signature (line 374):
```python
def invoke(
    self,
    capability_name: str,
    token: DelegationToken,
    params: dict[str, Any],
    *,
    client_reference_id: str | None = None,
) -> dict[str, Any]:
```

3. Generate `invocation_id` at the very top of the method body, before any validation:
```python
invocation_id = f"inv-{uuid.uuid4().hex[:12]}"
```

4. For the early-return failure paths (unknown capability, validation failure), include lineage in the response:
```python
return {
    "success": False,
    "invocation_id": invocation_id,
    "client_reference_id": client_reference_id,
    "failure": { ... },
}
```

5. Add lineage to the `InvocationContext` construction:
```python
ctx = InvocationContext(
    token=resolved_token,
    root_principal=self._engine.get_root_principal(resolved_token),
    subject=resolved_token.subject,
    scopes=resolved_token.scope or [],
    delegation_chain=[t.token_id for t in chain],
    invocation_id=invocation_id,
    client_reference_id=client_reference_id,
)
```

6. Add lineage to the success response:
```python
response = {
    "success": True,
    "invocation_id": invocation_id,
    "client_reference_id": client_reference_id,
    "result": result,
}
```

7. Add lineage to error responses (ANIPError catch, unexpected error catch):
```python
return {
    "success": False,
    "invocation_id": invocation_id,
    "client_reference_id": client_reference_id,
    "failure": { ... },
}
```

8. Update `_log_audit()` signature and body to accept and pass lineage:
```python
def _log_audit(
    self,
    capability: str,
    token: DelegationToken,
    *,
    success: bool,
    failure_type: str | None,
    result_summary: dict[str, Any] | None,
    cost_actual: dict[str, Any] | None,
    cost_variance: dict[str, Any] | None,
    invocation_id: str | None = None,
    client_reference_id: str | None = None,
) -> None:
```
Add to the `log_entry()` dict:
```python
"invocation_id": invocation_id,
"client_reference_id": client_reference_id,
```

9. Update all `_log_audit()` call sites in `invoke()` to pass `invocation_id=invocation_id, client_reference_id=client_reference_id`.

**Step 5: Run tests — verify they pass**

```bash
pytest packages/python/anip-service/tests/ -v
```

**Step 6: Commit**

```bash
git add packages/python/anip-service/
git commit -m "feat(service): thread lineage through invoke pipeline (Python)"
```

---

## Task 6: TypeScript Service Runtime — Thread Lineage Through Invoke

**Files:**
- Modify: `packages/typescript/service/src/service.ts`
- Modify: `packages/typescript/service/src/types.ts`
- Modify: `packages/typescript/service/tests/service.test.ts`

**Context:** The `invoke()` function (service.ts:635-738) currently takes `(capabilityName, token, params)`. The invocation context is an inline object (not a separate type). `logAudit()` (service.ts:258-287) takes a token and audit options.

**Step 1: Write failing tests**

Add to `packages/typescript/service/tests/service.test.ts`, inside `describe("ANIPService invoke")`:

```typescript
it("response includes invocation_id", async () => {
  const { service, storage } = makeService();
  const token = issueTestToken(storage);
  const result = await service.invoke("greet", token, { name: "World" });
  expect(result.success).toBe(true);
  expect(result.invocation_id).toBeDefined();
  expect((result.invocation_id as string).startsWith("inv-")).toBe(true);
  expect((result.invocation_id as string).length).toBe(16);
});

it("response echoes client_reference_id", async () => {
  const { service, storage } = makeService();
  const token = issueTestToken(storage);
  const result = await service.invoke("greet", token, { name: "World" }, {
    clientReferenceId: "task:42",
  });
  expect(result.client_reference_id).toBe("task:42");
});

it("client_reference_id null when absent", async () => {
  const { service, storage } = makeService();
  const token = issueTestToken(storage);
  const result = await service.invoke("greet", token, { name: "World" });
  expect(result.client_reference_id).toBeNull();
});

it("failure response still has invocation_id", async () => {
  const { service, storage } = makeService();
  const token = issueTestToken(storage);
  const result = await service.invoke("nonexistent", token, {});
  expect(result.success).toBe(false);
  expect(result.invocation_id).toBeDefined();
  expect((result.invocation_id as string).startsWith("inv-")).toBe(true);
});

it("handler context includes lineage", async () => {
  let capturedCtx: Record<string, unknown> = {};
  const ctxCap = defineCapability({
    declaration: {
      name: "ctx_cap",
      description: "Captures context",
      contract_version: "1.0",
      inputs: [],
      output: { type: "object", fields: [] },
      side_effect: { type: "read", rollback_window: null },
      minimum_scope: ["test"],
    } as CapabilityDeclaration,
    handler: (ctx, _params) => {
      capturedCtx = {
        invocationId: ctx.invocationId,
        clientReferenceId: ctx.clientReferenceId,
      };
      return { ok: true };
    },
  });
  const { service, storage } = makeService({ caps: [ctxCap] });
  const token = issueTestToken(storage, {
    scope: ["test"],
    capability: "ctx_cap",
  });
  await service.invoke("ctx_cap", token, {}, {
    clientReferenceId: "ref-abc",
  });
  expect((capturedCtx.invocationId as string).startsWith("inv-")).toBe(true);
  expect(capturedCtx.clientReferenceId).toBe("ref-abc");
});
```

**Step 2: Run tests — verify they fail**

```bash
cd packages/typescript && npx vitest run service/tests/service.test.ts
```

**Step 3: Update service.ts**

In `packages/typescript/service/src/service.ts`:

1. Add `import { randomUUID } from "node:crypto";` at the top (or use the existing crypto import pattern).

2. Update `invoke()` signature:
```typescript
async invoke(
  capabilityName: string,
  token: DelegationToken,
  params: Record<string, unknown>,
  opts?: { clientReferenceId?: string | null },
): Promise<Record<string, unknown>> {
```

3. Generate `invocation_id` at the top of invoke:
```typescript
const invocationId = `inv-${randomUUID().replace(/-/g, "").slice(0, 12)}`;
const clientReferenceId = opts?.clientReferenceId ?? null;
```

4. Add lineage to all return paths (success, failures, errors):
```typescript
invocation_id: invocationId,
client_reference_id: clientReferenceId,
```

5. Add lineage to the context object:
```typescript
const ctx = {
  token: resolvedToken,
  rootPrincipal: engine.getRootPrincipal(resolvedToken),
  subject: resolvedToken.subject,
  scopes: resolvedToken.scope ?? [],
  delegationChain: chain.map((t) => t.token_id),
  invocationId,
  clientReferenceId,
  setCostActual(cost: Record<string, unknown>): void {
    costActual = cost;
  },
};
```

6. Update `logAudit()` to accept and pass lineage:
```typescript
async function logAudit(
  capability: string,
  token: DelegationToken,
  auditOpts: {
    success: boolean;
    failureType?: string | null;
    resultSummary?: Record<string, unknown> | null;
    costActual?: Record<string, unknown> | null;
    invocationId?: string | null;
    clientReferenceId?: string | null;
  },
): Promise<void> {
```
Add to `audit.logEntry()` call:
```typescript
invocation_id: auditOpts.invocationId ?? null,
client_reference_id: auditOpts.clientReferenceId ?? null,
```

7. Update all `logAudit()` call sites to pass `invocationId` and `clientReferenceId`.

8. Update `InvocationContext` type export in `types.ts` if it exists, or ensure the context shape is documented.

**Step 4: Run tests — verify they pass**

```bash
cd packages/typescript && npx vitest run service/tests/service.test.ts
```

**Step 5: Run all service tests**

```bash
cd packages/typescript && npm test --workspace=@anip-dev/service
```

**Step 6: Commit**

```bash
git add packages/typescript/service/
git commit -m "feat(service): thread lineage through invoke pipeline (TypeScript)"
```

---

## Task 7: Python Framework Bindings — Wire Lineage

**Files:**
- Modify: `packages/python/anip-fastapi/src/anip_fastapi/routes.py`
- Modify: `packages/python/anip-flask/src/anip_flask/routes.py`
- Modify: `packages/python/anip-fastapi/tests/test_routes.py`
- Modify: `packages/python/anip-flask/tests/test_routes.py`

**Context:** Both bindings currently extract `params = body.get("parameters", body)` from the request body and call `service.invoke(capability, token, params)`. They need to also extract `client_reference_id` and pass it as a keyword argument.

**Step 1: Add failing tests to both bindings**

Add to FastAPI tests (`packages/python/anip-fastapi/tests/test_routes.py`):

```python
def test_invoke_response_has_invocation_id(self):
    """Invoke response should include invocation_id."""
    # (Use existing test setup pattern for authenticated invoke)
    response = client.post(
        "/anip/invoke/greet",
        headers={"Authorization": f"Bearer {token_jwt}"},
        json={"parameters": {"name": "World"}, "capability": "greet"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "invocation_id" in data
    assert data["invocation_id"].startswith("inv-")

def test_invoke_passes_client_reference_id(self):
    """Invoke should echo back client_reference_id when provided."""
    response = client.post(
        "/anip/invoke/greet",
        headers={"Authorization": f"Bearer {token_jwt}"},
        json={
            "parameters": {"name": "World"},
            "capability": "greet",
            "client_reference_id": "task:42",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["client_reference_id"] == "task:42"
```

Add equivalent tests to Flask tests (`packages/python/anip-flask/tests/test_routes.py`).

**Step 2: Run tests — verify they fail**

```bash
pytest packages/python/anip-fastapi/tests/ -v
pytest packages/python/anip-flask/tests/ -v
```

**Step 3: Update FastAPI routes.py**

In `packages/python/anip-fastapi/src/anip_fastapi/routes.py`, update the invoke handler (lines 84-98):

```python
@app.post(f"{prefix}/anip/invoke/{{capability}}")
async def invoke(capability: str, request: Request):
    token = _resolve_token(request, service)
    if token is None:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    body = await request.json()
    params = body.get("parameters", body)
    client_reference_id = body.get("client_reference_id")
    result = service.invoke(
        capability, token, params,
        client_reference_id=client_reference_id,
    )

    if not result.get("success"):
        status = _failure_status(result.get("failure", {}).get("type"))
        return JSONResponse(result, status_code=status)

    return result
```

**Step 4: Update Flask routes.py**

In `packages/python/anip-flask/src/anip_flask/routes.py`, update the invoke handler (lines 84-98):

```python
@bp.route("/anip/invoke/<capability>", methods=["POST"])
def invoke(capability: str):
    token = _resolve_token(request, service)
    if token is None:
        return jsonify({"error": "Authentication required"}), 401

    body = request.get_json(force=True)
    params = body.get("parameters", body)
    client_reference_id = body.get("client_reference_id")
    result = service.invoke(
        capability, token, params,
        client_reference_id=client_reference_id,
    )

    if not result.get("success"):
        status = _failure_status(result.get("failure", {}).get("type"))
        return jsonify(result), status

    return jsonify(result)
```

**Step 5: Run tests — verify they pass**

```bash
pytest packages/python/anip-fastapi/tests/ -v
pytest packages/python/anip-flask/tests/ -v
```

**Step 6: Commit**

```bash
git add packages/python/anip-fastapi/ packages/python/anip-flask/
git commit -m "feat(bindings): wire lineage through FastAPI and Flask invoke handlers"
```

---

## Task 8: TypeScript Framework Bindings — Wire Lineage

**Files:**
- Modify: `packages/typescript/hono/src/routes.ts`
- Modify: `packages/typescript/express/src/routes.ts`
- Modify: `packages/typescript/fastify/src/routes.ts`
- Modify: `packages/typescript/hono/tests/routes.test.ts`
- Modify: `packages/typescript/express/tests/routes.test.ts`
- Modify: `packages/typescript/fastify/tests/routes.test.ts`

**Context:** All three bindings extract `params = body.parameters ?? body` and call `service.invoke(capability, token, params)`. They need to also extract `client_reference_id` and pass it as an options argument.

**Step 1: Add failing tests to all three bindings**

For each binding's test file, add tests following the binding's test pattern:

```typescript
// Adapt to each binding's test client (supertest for Express, inject for Fastify, etc.)
it("invoke response has invocation_id", async () => {
  // Authenticated invoke request
  // Assert response body has invocation_id starting with "inv-"
});

it("invoke passes client_reference_id", async () => {
  // Authenticated invoke with client_reference_id in body
  // Assert response echoes it back
});
```

**Step 2: Run tests — verify they fail**

```bash
cd packages/typescript && npx vitest run hono/tests/ express/tests/ fastify/tests/
```

**Step 3: Update Hono routes.ts**

In `packages/typescript/hono/src/routes.ts`, update the invoke handler (lines 52-65):

```typescript
app.post(`${p}/anip/invoke/:capability`, async (c) => {
  const token = await resolveToken(c, service);
  if (!token) return c.json({ error: "Authentication required" }, 401);
  const capability = c.req.param("capability");
  const body = await c.req.json();
  const params = body.parameters ?? body;
  const clientReferenceId = body.client_reference_id ?? null;
  const result = await service.invoke(capability, token, params, {
    clientReferenceId,
  });
  if (!result.success) {
    const failure = result.failure as Record<string, unknown>;
    return c.json(result, failureStatus(failure?.type as string));
  }
  return c.json(result);
});
```

**Step 4: Update Express routes.ts**

In `packages/typescript/express/src/routes.ts`, update the invoke handler (lines 57-72):

```typescript
router.post("/anip/invoke/:capability", async (req, res, next) => {
  try {
    const token = await resolveToken(req, service);
    if (!token) { res.status(401).json({ error: "Authentication required" }); return; }
    const body = req.body;
    const params = body.parameters ?? body;
    const clientReferenceId = body.client_reference_id ?? null;
    const result = await service.invoke(req.params.capability, token, params, {
      clientReferenceId,
    });
    if (!result.success) {
      const failure = result.failure as Record<string, unknown>;
      res.status(failureStatus(failure?.type as string)).json(result);
      return;
    }
    res.json(result);
  } catch (e) { next(e); }
});
```

**Step 5: Update Fastify routes.ts**

In `packages/typescript/fastify/src/routes.ts`, update the invoke handler (lines 50-64):

```typescript
app.post<{ Params: { capability: string } }>(
  `${p}/anip/invoke/:capability`,
  async (req, reply) => {
    const token = await resolveToken(req, service);
    if (!token) return reply.status(401).send({ error: "Authentication required" });
    const body = req.body as Record<string, unknown>;
    const params = (body.parameters as Record<string, unknown>) ?? body;
    const clientReferenceId = (body.client_reference_id as string) ?? null;
    const result = await service.invoke(req.params.capability, token, params, {
      clientReferenceId,
    });
    if (!result.success) {
      const failure = result.failure as Record<string, unknown>;
      return reply.status(failureStatus(failure?.type as string)).send(result);
    }
    return result;
  },
);
```

**Step 6: Run tests — verify they pass**

```bash
cd packages/typescript && npx vitest run hono/tests/ express/tests/ fastify/tests/
```

**Step 7: Commit**

```bash
git add packages/typescript/hono/ packages/typescript/express/ packages/typescript/fastify/
git commit -m "feat(bindings): wire lineage through Hono, Express, and Fastify invoke handlers"
```

---

## Task 9: Version Bump + Schema Cleanup

**Files:**
- Modify: all 6 `packages/python/*/pyproject.toml`
- Modify: all 7 `packages/typescript/*/package.json`
- Modify: `packages/typescript/package.json` (root workspace)
- Modify: `schema/generate.py`

**Context:** All packages are at 0.3.0. Bump to 0.4.0 with lockstep versioning. Also clean up `schema/generate.py` which imports `InvokeRequest` from an old path.

**Step 1: Bump Python package versions**

For each of these files, change `version = "0.3.0"` to `version = "0.4.0"`:
- `packages/python/anip-core/pyproject.toml`
- `packages/python/anip-crypto/pyproject.toml`
- `packages/python/anip-server/pyproject.toml`
- `packages/python/anip-service/pyproject.toml`
- `packages/python/anip-fastapi/pyproject.toml`
- `packages/python/anip-flask/pyproject.toml`

Also update inter-package dependency versions:
- `anip-core>=0.3.0` → `anip-core>=0.4.0`
- `anip-crypto>=0.3.0` → `anip-crypto>=0.4.0`
- `anip-server>=0.3.0` → `anip-server>=0.4.0`
- `anip-service>=0.3.0` → `anip-service>=0.4.0`

**Step 2: Bump TypeScript package versions**

For each of these files, change `"version": "0.3.0"` to `"version": "0.4.0"`:
- `packages/typescript/core/package.json`
- `packages/typescript/crypto/package.json`
- `packages/typescript/server/package.json`
- `packages/typescript/service/package.json`
- `packages/typescript/hono/package.json`
- `packages/typescript/express/package.json`
- `packages/typescript/fastify/package.json`

Also update inter-package dependency versions:
- `"@anip-dev/core": "0.3.0"` → `"@anip-dev/core": "0.4.0"`
- `"@anip-dev/crypto": "0.3.0"` → `"@anip-dev/crypto": "0.4.0"`
- `"@anip-dev/server": "0.3.0"` → `"@anip-dev/server": "0.4.0"`
- `"@anip-dev/service": "0.3.0"` → `"@anip-dev/service": "0.4.0"`

**Step 3: Update schema/generate.py**

The script imports from `anip_server.primitives.models` (an old path). Update to import from `anip_core`:

```python
from anip_core import (
    ANIPFailure,
    ANIPManifest,
    AvailableCapability,
    CapabilityDeclaration,
    CostActual,
    DelegationToken,
    DeniedCapability,
    InvokeRequest,
    InvokeResponse,
    PermissionResponse,
    RestrictedCapability,
)
```

Remove the `sys.path.insert` hack (line 23).

Also update the `$id` version from `v0.1` to `v0.4`:
```python
"$id": "https://anip.dev/schema/v0.4/anip.schema.json",
```

**Step 4: Run full test suite**

```bash
# Python
pytest packages/python/anip-core/tests/ -v
pytest packages/python/anip-server/tests/ -v
pytest packages/python/anip-service/tests/ -v
pytest packages/python/anip-fastapi/tests/ -v
pytest packages/python/anip-flask/tests/ -v

# TypeScript
cd packages/typescript && npm ci && npx tsc -p core/tsconfig.json && npx tsc -p crypto/tsconfig.json && npx tsc -p server/tsconfig.json && npx tsc -p service/tsconfig.json && npx tsc -p hono/tsconfig.json && npx tsc -p express/tsconfig.json && npx tsc -p fastify/tsconfig.json
npm test --workspace=@anip-dev/core
npm test --workspace=@anip-dev/crypto
npm test --workspace=@anip-dev/server
npm test --workspace=@anip-dev/service
npm test --workspace=@anip-dev/hono
npm test --workspace=@anip-dev/express
npm test --workspace=@anip-dev/fastify
```

**Step 5: Commit**

```bash
git add packages/ schema/
git commit -m "chore: bump all packages to 0.4.0 + update schema imports"
```
