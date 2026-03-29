# v0.5 Async Storage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace sync storage with fully async architecture in both languages — async `StorageBackend`, async runtimes, compliance test fixtures, no dual-mode logic.

**Architecture:** Bottom-up migration: storage interfaces first, then server internals (AuditLog, DelegationEngine), then service runtime, then bindings, then examples. Python and TypeScript proceed in parallel tracks within each layer. Flask binding dropped.

**Tech Stack:** Python (asyncio, asyncio.to_thread, sqlite3), TypeScript (worker_threads, better-sqlite3, Promises)

**Design doc:** `docs/plans/2026-03-15-v05-async-storage-design.md`

---

### Task 1: Python StorageBackend + InMemoryStorage → async

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/storage.py`
- Modify: `packages/python/anip-server/tests/test_storage.py` (if exists, otherwise create)

**Context:** The `StorageBackend` protocol defines 9 sync methods. `InMemoryStorage` is the test-oriented implementation. `SQLiteStorage` is handled in Task 4.

**Step 1: Convert `StorageBackend` protocol to async**

Every method in the `Protocol` class gets `async def` instead of `def`. The protocol stays `@runtime_checkable`. No logic changes — only signatures.

**Step 2: Convert `InMemoryStorage` to async**

All methods become `async def`. The internal logic (dict/list operations) stays identical — these are in-memory operations that happen to satisfy an async contract. No `await` needed internally since there's no real I/O.

**Step 3: Write tests for async InMemoryStorage**

```python
import pytest
from anip_server.storage import InMemoryStorage

@pytest.mark.asyncio
async def test_token_roundtrip():
    s = InMemoryStorage()
    await s.store_token({"token_id": "tok-1", "issuer": "svc", "subject": "agent"})
    loaded = await s.load_token("tok-1")
    assert loaded is not None
    assert loaded["token_id"] == "tok-1"

@pytest.mark.asyncio
async def test_token_not_found():
    s = InMemoryStorage()
    assert await s.load_token("nonexistent") is None

@pytest.mark.asyncio
async def test_audit_store_and_query():
    s = InMemoryStorage()
    await s.store_audit_entry({"sequence_number": 1, "capability": "search", "root_principal": "human:alice"})
    entries = await s.query_audit_entries(capability="search")
    assert len(entries) == 1
    assert entries[0]["capability"] == "search"
```

**Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest packages/python/anip-server/tests/ -x -q
```

Add `pytest-asyncio` to dev dependencies if not already present. The existing tests will break because they call sync methods — update them to use `await` and `@pytest.mark.asyncio`.

**Step 5: Commit**

```bash
git commit -m "feat(server/py): convert StorageBackend + InMemoryStorage to async"
```

---

### Task 2: Python AuditLog → async

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/audit.py`
- Modify: `packages/python/anip-server/tests/test_audit.py`

**Context:** `AuditLog` wraps `StorageBackend` with hash chaining and Merkle accumulation. Three methods to convert: `log_entry()`, `query()`. `get_merkle_snapshot()` stays sync (in-memory Merkle tree).

**Step 1: Convert `log_entry()` to async**

```python
async def log_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
    last = await self._storage.get_last_audit_entry()
    # ... same logic ...
    await self._storage.store_audit_entry(entry)
    return entry
```

The signer callback: if provided, it may be sync or async. Handle both:
```python
sig = self._signer(entry)
if asyncio.iscoroutine(sig):
    sig = await sig
entry["signature"] = sig
```

**Step 2: Convert `query()` to async**

```python
async def query(self, **filters: Any) -> list[dict[str, Any]]:
    return await self._storage.query_audit_entries(**filters)
```

**Step 3: Update tests**

All existing audit tests become `@pytest.mark.asyncio` and use `await`. The test fixtures create `InMemoryStorage()` (now async) and `AuditLog(storage)`.

**Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest packages/python/anip-server/tests/test_audit.py -x -q
```

**Step 5: Commit**

```bash
git commit -m "feat(server/py): convert AuditLog to async"
```

---

### Task 3: Python DelegationEngine → async

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/delegation.py`
- Modify: `packages/python/anip-server/tests/test_delegation.py` (if exists)

**Context:** `DelegationEngine` has ~15 methods. Every method that calls `storage.load_token()` or `storage.store_token()` becomes async. In-memory-only methods stay sync.

**Methods becoming async:**
- `issue_root_token()` — calls `_create_token()` → `register_token()` → `storage.store_token()`
- `delegate()` — calls `_create_token()` → `register_token()` → `storage.store_token()`; also calls `get_root_principal()` which may call `get_chain()` → `storage.load_token()`
- `validate_delegation()` — calls `resolve_registered_token()` → `storage.load_token()`; calls `get_chain()` → `storage.load_token()`; calls `get_root_principal()` which may chain-walk
- `resolve_registered_token()` — calls `get_token()` → `storage.load_token()`
- `get_token()` — calls `storage.load_token()`
- `get_chain()` — calls `get_token()` repeatedly
- `get_root_principal()` — may call `get_chain()` on fallback path
- `get_chain_token_ids()` — calls `get_chain()`
- `register_token()` — calls `storage.store_token()`
- `_create_token()` — calls `register_token()`

**Methods staying sync:**
- `acquire_exclusive_lock()` — Python `threading.Lock`, in-memory
- `release_exclusive_lock()` — in-memory
- `_narrow_scope()` — pure computation
- `_narrow_constraints()` — pure computation
- `_check_budget_authority()` — pure computation
- All scope/constraint validation helpers — pure computation

**Step 1: Convert storage-touching methods to async**

Add `async def` and `await` for every storage call. Chain-walking methods like `get_chain()` already loop calling `get_token()` — the loop body gets `await`.

**Step 2: Update tests**

All delegation tests become async. Create `InMemoryStorage()`, pass to `DelegationEngine(storage, service_id)`.

**Step 3: Run tests**

```bash
source .venv/bin/activate && python -m pytest packages/python/anip-server/tests/ -x -q
```

**Step 4: Commit**

```bash
git commit -m "feat(server/py): convert DelegationEngine to async"
```

---

### Task 4: Python SQLiteStorage → async via `asyncio.to_thread`

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/storage.py`

**Context:** `SQLiteStorage` uses synchronous `sqlite3`. Wrap each method with `asyncio.to_thread()` to move I/O off the event loop. Keep the sync SQLite logic intact internally.

**Step 1: Refactor SQLiteStorage**

Extract sync logic into private `_sync_*` methods. Public methods become async wrappers:

```python
class SQLiteStorage:
    def __init__(self, db_path: str = "anip.db") -> None:
        # Same init — creates tables, runs migrations

    # --- Sync internals (private) ---
    def _sync_store_token(self, token_data: dict[str, Any]) -> None:
        # existing store_token logic

    def _sync_load_token(self, token_id: str) -> dict[str, Any] | None:
        # existing load_token logic

    # ... same for all 9 methods

    # --- Async public interface ---
    async def store_token(self, token_data: dict[str, Any]) -> None:
        await asyncio.to_thread(self._sync_store_token, token_data)

    async def load_token(self, token_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._sync_load_token, token_id)

    # ... same for all 9 methods
```

**Step 2: Run all server tests**

```bash
source .venv/bin/activate && python -m pytest packages/python/anip-server/tests/ -x -q
```

**Step 3: Commit**

```bash
git commit -m "feat(server/py): wrap SQLiteStorage with asyncio.to_thread"
```

---

### Task 5: Python backend compliance test fixtures

**Files:**
- Create: `packages/python/anip-server/tests/compliance.py`
- Modify: `packages/python/anip-server/tests/test_storage.py` (run fixtures against InMemoryStorage)

**Context:** Reusable test suite any `StorageBackend` must pass. Tests are async functions that accept a storage instance.

**Step 1: Write compliance fixtures**

```python
"""Backend compliance test suite for StorageBackend implementations."""
import asyncio
from typing import Any

import pytest


async def compliance_token_roundtrip(storage) -> None:
    """Token store/load roundtrip."""
    token = {"token_id": "tok-c1", "issuer": "svc", "subject": "agent",
             "scope": ["a.b"], "purpose": {"capability": "c", "parameters": {}, "task_id": "t"},
             "parent": None, "expires": "2099-01-01T00:00:00Z",
             "constraints": {"max_delegation_depth": 3, "concurrent_branches": "allowed"},
             "root_principal": "human:alice"}
    await storage.store_token(token)
    loaded = await storage.load_token("tok-c1")
    assert loaded is not None
    assert loaded["token_id"] == "tok-c1"
    assert loaded["scope"] == ["a.b"]


async def compliance_token_not_found(storage) -> None:
    """load_token returns None for unknown ID."""
    assert await storage.load_token("nonexistent") is None


async def compliance_audit_roundtrip(storage) -> None:
    """Audit entry store and query."""
    entry = {"sequence_number": 1, "timestamp": "2026-01-01T00:00:00Z",
             "capability": "search", "token_id": "tok-1",
             "root_principal": "human:alice", "success": True,
             "invocation_id": "inv-aabbccddeeff", "client_reference_id": "ref-1",
             "previous_hash": "sha256:0", "signature": None}
    await storage.store_audit_entry(entry)
    results = await storage.query_audit_entries(capability="search")
    assert len(results) >= 1
    assert results[0]["capability"] == "search"


async def compliance_audit_lineage_filters(storage) -> None:
    """Audit query by invocation_id and client_reference_id."""
    for i in range(3):
        await storage.store_audit_entry({
            "sequence_number": i + 1, "timestamp": f"2026-01-0{i+1}T00:00:00Z",
            "capability": "cap", "root_principal": "human:a", "success": True,
            "invocation_id": f"inv-{'0' * 11}{i}", "client_reference_id": "ref-shared",
            "previous_hash": "sha256:0", "signature": None})
    by_inv = await storage.query_audit_entries(invocation_id="inv-000000000001")
    assert len(by_inv) == 1
    by_ref = await storage.query_audit_entries(client_reference_id="ref-shared")
    assert len(by_ref) == 3


async def compliance_audit_ordering(storage) -> None:
    """Audit entries maintain insertion order by sequence number."""
    for i in range(5):
        await storage.store_audit_entry({
            "sequence_number": i + 1, "timestamp": f"2026-01-0{i+1}T00:00:00Z",
            "capability": "cap", "root_principal": "human:a", "success": True,
            "previous_hash": "sha256:0", "signature": None})
    entries = await storage.query_audit_entries(root_principal="human:a", limit=10)
    seq_nums = [e["sequence_number"] for e in entries]
    # Descending order (most recent first)
    assert seq_nums == sorted(seq_nums, reverse=True)


async def compliance_audit_concurrent_ordering(storage) -> None:
    """Audit insertion ordering under concurrent calls."""
    async def insert(seq: int):
        await storage.store_audit_entry({
            "sequence_number": seq, "timestamp": "2026-01-01T00:00:00Z",
            "capability": "cap", "root_principal": "human:a", "success": True,
            "previous_hash": "sha256:0", "signature": None})

    await asyncio.gather(*[insert(i + 1) for i in range(20)])
    entries = await storage.query_audit_entries(root_principal="human:a", limit=100)
    assert len(entries) == 20


async def compliance_checkpoint_roundtrip(storage) -> None:
    """Checkpoint store/load roundtrip."""
    body = {"checkpoint_id": "cp-1", "merkle_root": "sha256:abc",
            "range": {"first_sequence": 1, "last_sequence": 5},
            "timestamp": "2026-01-01T00:00:00Z", "entry_count": 5}
    await storage.store_checkpoint(body, "sig-123")
    loaded = await storage.get_checkpoint_by_id("cp-1")
    assert loaded is not None
    assert loaded["checkpoint_id"] == "cp-1"
    assert loaded["merkle_root"] == "sha256:abc"


async def compliance_checkpoint_not_found(storage) -> None:
    """get_checkpoint_by_id returns None for unknown ID."""
    assert await storage.get_checkpoint_by_id("nonexistent") is None


async def compliance_checkpoint_listing(storage) -> None:
    """Checkpoint listing respects limit."""
    for i in range(5):
        await storage.store_checkpoint(
            {"checkpoint_id": f"cp-{i}", "merkle_root": f"sha256:{i}", "sequence_number": i + 1},
            f"sig-{i}")
    results = await storage.get_checkpoints(limit=3)
    assert len(results) == 3


async def compliance_audit_entries_range(storage) -> None:
    """get_audit_entries_range returns entries between sequence numbers."""
    for i in range(10):
        await storage.store_audit_entry({
            "sequence_number": i + 1, "timestamp": f"2026-01-{i+1:02d}T00:00:00Z",
            "capability": "cap", "root_principal": "human:a", "success": True,
            "previous_hash": "sha256:0", "signature": None})
    entries = await storage.get_audit_entries_range(3, 7)
    seq_nums = [e["sequence_number"] for e in entries]
    assert all(3 <= s <= 7 for s in seq_nums)


# Collected list for parametrize
ALL_COMPLIANCE_TESTS = [
    compliance_token_roundtrip,
    compliance_token_not_found,
    compliance_audit_roundtrip,
    compliance_audit_lineage_filters,
    compliance_audit_ordering,
    compliance_audit_concurrent_ordering,
    compliance_checkpoint_roundtrip,
    compliance_checkpoint_not_found,
    compliance_checkpoint_listing,
    compliance_audit_entries_range,
]
```

**Step 2: Run compliance tests against InMemoryStorage**

```python
# In test_storage.py
import pytest
from anip_server.storage import InMemoryStorage
from .compliance import ALL_COMPLIANCE_TESTS

@pytest.mark.asyncio
@pytest.mark.parametrize("test_fn", ALL_COMPLIANCE_TESTS, ids=lambda f: f.__name__)
async def test_in_memory_compliance(test_fn):
    storage = InMemoryStorage()
    await test_fn(storage)
```

**Step 3: Run compliance tests against SQLiteStorage**

```python
@pytest.mark.asyncio
@pytest.mark.parametrize("test_fn", ALL_COMPLIANCE_TESTS, ids=lambda f: f.__name__)
async def test_sqlite_compliance(test_fn, tmp_path):
    storage = SQLiteStorage(str(tmp_path / "test.db"))
    await test_fn(storage)
```

**Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest packages/python/anip-server/tests/ -x -q
```

**Step 5: Commit**

```bash
git commit -m "feat(server/py): add backend compliance test fixtures"
```

---

### Task 6: TypeScript StorageBackend + InMemoryStorage → async

**Files:**
- Modify: `packages/typescript/server/src/storage.ts`
- Modify: `packages/typescript/server/tests/` (update all storage tests)

**Context:** `StorageBackend` interface has 9 sync methods. `InMemoryStorage` uses plain arrays/Maps. All return types become `Promise<...>`.

**Step 1: Convert `StorageBackend` interface to Promise-based**

Every method return type wraps with `Promise<>`. Same method names.

**Step 2: Convert `InMemoryStorage` to async**

All methods become `async`. Internal logic unchanged — in-memory operations wrapped in async signatures.

**Step 3: Update tests**

All storage tests add `await` to storage method calls. Vitest already supports async test functions.

**Step 4: Run tests**

```bash
npx vitest run packages/typescript/server/tests/ --reporter=verbose
```

Note: This will break `SQLiteStorage`, `AuditLog`, `DelegationEngine`, and service tests since they call the old sync interface. Those are fixed in Tasks 7-9. Run only storage-specific tests for now if they exist separately, or fix forward.

**Step 5: Commit**

```bash
git commit -m "feat(server/ts): convert StorageBackend + InMemoryStorage to async"
```

---

### Task 7: TypeScript AuditLog → async

**Files:**
- Modify: `packages/typescript/server/src/audit.ts`
- Modify: `packages/typescript/server/tests/audit.test.ts`

**Context:** `logEntry()` is already async. `query()` is sync — becomes async. Internal storage calls get `await`.

**Step 1: Convert `query()` to async and add `await` to storage calls in `logEntry()`**

```typescript
async logEntry(entryData: Record<string, unknown>): Promise<Record<string, unknown>> {
    const last = await this._storage.getLastAuditEntry();  // was sync
    // ... same logic ...
    await this._storage.storeAuditEntry(entry);  // was sync
    return entry;
}

async query(opts?: { ... }): Promise<Record<string, unknown>[]> {
    return await this._storage.queryAuditEntries(opts);
}
```

**Step 2: Update tests — add `await` to `query()` calls**

**Step 3: Run tests**

```bash
npx vitest run packages/typescript/server/tests/audit.test.ts --reporter=verbose
```

**Step 4: Commit**

```bash
git commit -m "feat(server/ts): convert AuditLog to async"
```

---

### Task 8: TypeScript DelegationEngine → async

**Files:**
- Modify: `packages/typescript/server/src/delegation.ts`
- Modify: `packages/typescript/server/tests/` (delegation tests)

**Context:** Same pattern as Python Task 3. Every method touching `storage.loadToken()` or `storage.storeToken()` becomes async.

**Methods becoming async:**
- `issueRootToken()`, `delegate()`, `validateDelegation()`, `resolveRegisteredToken()`, `getToken()`, `getChain()`, `getRootPrincipal()`, `getChainTokenIds()`, `registerToken()`, `_createToken()`

**Methods staying sync:**
- `_isFailure()` — type guard
- Scope/constraint narrowing helpers

**Step 1: Convert methods to async, add `await` to storage calls**

`getChain()` loop becomes:
```typescript
async getChain(token: DelegationTokenType): Promise<DelegationTokenType[]> {
    const chain: DelegationTokenType[] = [token];
    let current = token;
    while (current.parent) {
        const parent = await this.getToken(current.parent);
        if (!parent) break;
        chain.unshift(parent);
        current = parent;
    }
    return chain;
}
```

**Step 2: Update tests**

**Step 3: Run tests**

```bash
npx vitest run packages/typescript/server/tests/ --reporter=verbose
```

**Step 4: Commit**

```bash
git commit -m "feat(server/ts): convert DelegationEngine to async"
```

---

### Task 9: TypeScript SQLiteStorage → async via worker thread

**Files:**
- Modify: `packages/typescript/server/src/storage.ts` (SQLiteStorage class → async proxy)
- Create: `packages/typescript/server/src/sqlite-worker.ts` (worker thread script with all SQL logic)

**Context:** `better-sqlite3` is synchronous and blocks the event loop. Wrap it in a `Worker` thread. The worker receives method name + args via `parentPort`, executes the sync SQLite call, and sends back the result.

**Build/test resolution strategy:**

The worker file must be runnable in both test (vitest running from source) and built (tsc → dist/) contexts:

1. **Source:** The worker imports `better-sqlite3` and uses `workerData` for config. It must be a standalone entry point — no re-exporting from `index.ts`. vitest resolves TypeScript natively via its transform pipeline, so `sqlite-worker.ts` works directly in tests.

2. **Build:** `tsc` compiles `sqlite-worker.ts` → `dist/sqlite-worker.js`. The proxy class resolves the worker path relative to `import.meta.url`, which works for both `src/` (test) and `dist/` (built) because the relative path `./sqlite-worker.js` stays the same.

3. **Worker instantiation:** Use `new URL("./sqlite-worker.js", import.meta.url)` in the built proxy. For tests, vitest's module resolution handles `.ts` → `.js` mapping. Add a `tsconfig.json` check: ensure `sqlite-worker.ts` is included in `include` so tsc compiles it. If vitest has trouble resolving the worker, add a small vitest plugin or use `fileURLToPath` + path resolution as a fallback.

4. **Package exports:** `sqlite-worker.ts` is NOT exported from `index.ts` — it is an internal implementation detail. But it must be included in the published package files. Add `"dist/sqlite-worker.js"` to the `files` array in `package.json` if one exists, or ensure `dist/` is fully included.

**Step 1: Create worker thread script**

`sqlite-worker.ts` — a standalone script that:
1. Reads `workerData.dbPath` on startup, creates the `better-sqlite3` database (with same schema/migration logic currently in `SQLiteStorage`)
2. Listens for `{ id, method, args }` messages from the parent via `parentPort`
3. Dispatches to the appropriate sync storage method
4. Posts back `{ id, result }` or `{ id, error }`

All the SQL logic (CREATE TABLE, INSERT, SELECT, migration) moves into this file. The `SQLiteStorage` class in `storage.ts` becomes a thin async proxy.

**Step 2: Refactor `SQLiteStorage` to proxy calls to the worker**

```typescript
import { Worker } from "node:worker_threads";
import { randomUUID } from "node:crypto";

class SQLiteStorage implements StorageBackend {
    private worker: Worker;
    private pending = new Map<string, { resolve: Function; reject: Function }>();

    constructor(dbPath: string = "anip.db") {
        this.worker = new Worker(
            new URL("./sqlite-worker.js", import.meta.url),
            { workerData: { dbPath } },
        );
        this.worker.on("message", (msg) => {
            const p = this.pending.get(msg.id);
            if (p) {
                this.pending.delete(msg.id);
                if (msg.error) p.reject(new Error(msg.error));
                else p.resolve(msg.result);
            }
        });
    }

    private call(method: string, args: unknown[]): Promise<unknown> {
        const id = randomUUID();
        return new Promise((resolve, reject) => {
            this.pending.set(id, { resolve, reject });
            this.worker.postMessage({ id, method, args });
        });
    }

    async storeToken(tokenData: Record<string, unknown>): Promise<void> {
        await this.call("storeToken", [tokenData]);
    }
    // ... same for all 9 methods
}
```

**Step 3: Run tests**

```bash
npx vitest run packages/typescript/server/tests/ --reporter=verbose
```

**Step 4: Commit**

```bash
git commit -m "feat(server/ts): wrap SQLiteStorage with worker thread for genuine async"
```

---

### Task 10: TypeScript backend compliance test fixtures

**Files:**
- Create: `packages/typescript/server/tests/compliance.ts`
- Modify: `packages/typescript/server/tests/storage.test.ts` (or create)

**Context:** Same compliance suite as Python Task 5, but in TypeScript. Reusable async test functions that accept a `StorageBackend`.

**Step 1: Write compliance fixtures**

Mirror the Python compliance tests: token roundtrip, not-found, audit roundtrip, lineage filters, ordering, concurrency, checkpoint roundtrip/listing, entries range.

**Step 2: Run against InMemoryStorage and SQLiteStorage**

```typescript
import { describe, it } from "vitest";
import { InMemoryStorage, SQLiteStorage } from "../src/storage.js";
import { ALL_COMPLIANCE_TESTS } from "./compliance.js";

describe("InMemoryStorage compliance", () => {
    for (const test of ALL_COMPLIANCE_TESTS) {
        it(test.name, async () => {
            const storage = new InMemoryStorage();
            await test.fn(storage);
        });
    }
});
```

**Step 3: Run tests**

```bash
npx vitest run packages/typescript/server/tests/ --reporter=verbose
```

**Step 4: Commit**

```bash
git commit -m "feat(server/ts): add backend compliance test fixtures"
```

---

### Task 11: Python ANIPService → async

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/python/anip-service/src/anip_service/types.py`
- Modify: `packages/python/anip-service/src/anip_service/__init__.py`
- Modify: `packages/python/anip-service/tests/test_service_init.py`

**Context:** This is the largest single task. Every service method that crosses a storage boundary becomes `async def`. The handler type becomes `Callable[..., dict | Awaitable[dict]]`.

**Step 1: Update handler type in `types.py`**

```python
from typing import Any, Awaitable, Callable
from anip_core import CapabilityDeclaration, DelegationToken

Handler = Callable[[InvocationContext, dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]
```

**Step 2: Convert service methods to async**

Methods becoming async:
- `invoke()` → `async def invoke()`
- `issue_token()` → `async def issue_token()`
- `query_audit()` → `async def query_audit()`
- `get_checkpoints()` → `async def get_checkpoints()`
- `get_checkpoint()` → `async def get_checkpoint()`
- `authenticate_bearer()` → `async def authenticate_bearer()`
- `resolve_bearer_token()` → `async def resolve_bearer_token()`
- `_log_audit()` → `async def _log_audit()` (internal)
- `_create_and_publish_checkpoint()` → `async def _create_and_publish_checkpoint()` (internal)
- `_rebuild_merkle_to()` → `async def _rebuild_merkle_to()` (internal)

Methods staying sync:
- `get_discovery()` — cached dict
- `get_signed_manifest()` — local CPU crypto
- `get_jwks()` — loaded keys
- `discover_permissions()` — in-memory scope evaluation
- `start()`, `stop()` — timer lifecycle

In `invoke()`, handle both sync and async handlers:
```python
result = handler(ctx, params)
if asyncio.iscoroutine(result) or asyncio.isfuture(result):
    result = await result
```

All internal calls to engine/audit methods get `await`:
```python
validation_result = await self._engine.validate_delegation(token, min_scope, capability_name)
chain = await self._engine.get_chain(token)
await self._log_audit(token, ...)
```

**Step 3: Update tests**

All service tests become `@pytest.mark.asyncio`. Test both sync and async handlers:

```python
@pytest.mark.asyncio
async def test_invoke_with_async_handler():
    async def handler(ctx, params):
        return {"result": "async"}
    # ... setup service with async handler, verify invoke works
```

**Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest packages/python/anip-service/tests/ -x -q
```

**Step 5: Commit**

```bash
git commit -m "feat(service/py): convert ANIPService to async runtime"
```

---

### Task 12: TypeScript service → async

**Files:**
- Modify: `packages/typescript/service/src/service.ts`
- Modify: `packages/typescript/service/src/types.ts`
- Modify: `packages/typescript/service/tests/service.test.ts`

**Context:** TypeScript service is already partially async. The remaining sync methods become async. Internal storage/engine/audit calls get `await`.

**Step 1: Convert remaining sync methods**

- `queryAudit()` → `async` (now awaits `audit.query()`)
- `getCheckpoints()` → `async` (now awaits `storage.getCheckpoints()`)
- `getCheckpoint()` → `async` (now awaits `storage.getCheckpointById()`, `storage.getAuditEntriesRange()`)
- `discoverPermissions()` → stays sync (pure in-memory)

Update the `ANIPService` interface type to match.

**Step 2: Add `await` to all internal storage/engine calls throughout the file**

Every call to:
- `engine.validateDelegation()` → `await engine.validateDelegation()`
- `engine.getChain()` → `await engine.getChain()`
- `engine.getRootPrincipal()` → `await engine.getRootPrincipal()`
- `engine.issueRootToken()` → `await engine.issueRootToken()`
- `engine.delegate()` → `await engine.delegate()`
- `engine.getToken()` → `await engine.getToken()`
- `audit.query()` → `await audit.query()`
- `audit.logEntry()` → already awaited
- `storage.getCheckpoints()` → `await storage.getCheckpoints()`
- `storage.getCheckpointById()` → `await storage.getCheckpointById()`
- `storage.getAuditEntriesRange()` → `await storage.getAuditEntriesRange()`

This is a careful grep-and-update pass. Every callsite must be checked.

**Step 3: Update tests**

Add `await` to newly-async method calls in tests.

**Step 4: Run tests**

```bash
npx vitest run packages/typescript/service/tests/ --reporter=verbose
```

**Step 5: Commit**

```bash
git commit -m "feat(service/ts): convert remaining service methods to async"
```

---

### Task 13: Python FastAPI binding → await async

**Files:**
- Modify: `packages/python/anip-fastapi/src/anip_fastapi/routes.py`
- Modify: `packages/python/anip-fastapi/tests/test_routes.py`

**Context:** FastAPI routes are already `async def`. They currently call sync service methods. Now they `await` the async ones.

**Step 1: Make `_resolve_token()` and `_extract_principal()` async**

```python
async def _resolve_token(request: Request, service: ANIPService):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    jwt_string = auth[7:].strip()
    try:
        return await service.resolve_bearer_token(jwt_string)
    except Exception:
        return None

async def _extract_principal(request: Request, service: ANIPService):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    bearer_value = auth[7:].strip()
    return await service.authenticate_bearer(bearer_value)
```

**Step 2: Add `await` to route handlers**

```python
@app.post(f"{prefix}/anip/tokens")
async def issue_token(request: Request):
    principal = await _extract_principal(request, service)
    ...
    result = await service.issue_token(principal, body)
    ...

@app.post(f"{prefix}/anip/invoke/{{capability}}")
async def invoke(capability: str, request: Request):
    token = await _resolve_token(request, service)
    ...
    result = await service.invoke(capability, token, params, ...)
    ...

@app.post(f"{prefix}/anip/audit")
async def audit(request: Request):
    token = await _resolve_token(request, service)
    ...
    return await service.query_audit(token, filters)

# Checkpoints
async def list_checkpoints(request: Request):
    return await service.get_checkpoints(limit)

async def get_checkpoint(checkpoint_id: str, ...):
    result = await service.get_checkpoint(checkpoint_id, ...)
```

Methods that stay sync (`get_discovery()`, `get_signed_manifest()`, `get_jwks()`, `discover_permissions()`) do not need `await`.

**Step 3: Update tests**

Tests use `httpx.AsyncClient` (via FastAPI `TestClient`). Most should work as-is since TestClient handles async routes. Verify.

**Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest packages/python/anip-fastapi/tests/ -x -q
```

**Step 5: Commit**

```bash
git commit -m "feat(fastapi): await async service methods in route handlers"
```

---

### Task 14: Drop Flask binding

**Files:**
- Remove: `packages/python/anip-flask/` (entire directory)
- Modify: Root-level CI/workflow files if they reference `anip-flask`

**Context:** Flask's sync-native runtime is incompatible with the fully async architecture. Clean removal.

**Step 1: Delete the `anip-flask` package directory**

```bash
rm -rf packages/python/anip-flask
```

**Step 2: Remove any CI/workflow references**

Search for `anip-flask` in `.github/workflows/`, `Makefile`, or other build scripts and remove references.

**Step 3: Run remaining Python tests to verify no cross-dependencies**

```bash
source .venv/bin/activate && python -m pytest packages/python/ -x -q
```

**Step 4: Commit**

```bash
git commit -m "chore: remove anip-flask binding (incompatible with async runtime)"
```

---

### Task 15: TypeScript bindings → await async

**Files:**
- Modify: `packages/typescript/hono/src/routes.ts`
- Modify: `packages/typescript/express/src/routes.ts`
- Modify: `packages/typescript/fastify/src/routes.ts`
- Modify: corresponding test files

**Context:** Handlers are already async. Add `await` to newly-async service calls: `queryAudit()`, `getCheckpoints()`, `getCheckpoint()`.

**Step 1: Update Hono routes**

```typescript
// Audit — was sync, now async
app.post(`${p}/anip/audit`, async (c) => {
    ...
    return c.json(await service.queryAudit(token, filters));  // add await
});

// Checkpoints — were sync, now async
app.get(`${p}/anip/checkpoints`, async (c) => {
    ...
    return c.json(await service.getCheckpoints(limit));  // add await
});

app.get(`${p}/anip/checkpoints/:id`, async (c) => {
    ...
    const result = await service.getCheckpoint(id, options);  // add await
    ...
});
```

**Step 2: Same changes for Express and Fastify routes**

**Step 3: Run tests**

```bash
npx vitest run packages/typescript/hono/tests/ packages/typescript/express/tests/ packages/typescript/fastify/tests/ --reporter=verbose
```

**Step 4: Commit**

```bash
git commit -m "feat(bindings/ts): await newly-async service methods in all bindings"
```

---

### Task 16: Update example apps

**Files:**
- Modify: `examples/anip-ts/src/app.ts`
- Modify: `examples/anip-ts/tests/flight-service.test.ts`

**Context:** The TypeScript example app uses `createANIPService()` with Hono. Since the Hono binding already handles async, the example app may not need changes. But verify handlers and test assertions still work with the async surface.

**Step 1: Verify example app compiles and tests pass**

```bash
cd examples/anip-ts && npm install && npx vitest run --reporter=verbose
```

**Step 2: Fix any issues**

If capability handlers need updating (they return sync dicts currently — should still work since TS awaits both sync and async returns).

**Step 3: Commit if changes needed**

```bash
git commit -m "fix(examples): update anip-ts for v0.5 async runtime"
```

---

### Task 17: Version bump 0.4.0 → 0.5.0

**Files:**
- Modify: All 12 `pyproject.toml` and `package.json` files
- Modify: `packages/python/anip-core/src/anip_core/constants.py` — do NOT change `PROTOCOL_VERSION`
- Modify: `packages/python/anip-server/src/anip_server/__init__.py` — update exports if needed
- Modify: `packages/typescript/server/src/index.ts` — update exports if needed

**Context:** Lockstep version bump across 12 packages (Flask removed). `PROTOCOL_VERSION` stays `anip/0.3`.

**Step 1: Bump all Python packages**

```
packages/python/anip-core/pyproject.toml         → version = "0.5.0"
packages/python/anip-crypto/pyproject.toml        → version = "0.5.0", deps >=0.5.0
packages/python/anip-server/pyproject.toml        → version = "0.5.0", deps >=0.5.0
packages/python/anip-service/pyproject.toml       → version = "0.5.0", deps >=0.5.0
packages/python/anip-fastapi/pyproject.toml       → version = "0.5.0", deps >=0.5.0
```

**Step 2: Bump all TypeScript packages**

```
packages/typescript/core/package.json             → "0.5.0"
packages/typescript/crypto/package.json           → "0.5.0", deps "0.5.0"
packages/typescript/server/package.json           → "0.5.0", deps "0.5.0"
packages/typescript/service/package.json          → "0.5.0", deps "0.5.0"
packages/typescript/hono/package.json             → "0.5.0", deps "0.5.0"
packages/typescript/express/package.json          → "0.5.0", deps "0.5.0"
packages/typescript/fastify/package.json          → "0.5.0", deps "0.5.0"
```

**Step 3: Bump example app and regenerate lockfile**

```
examples/anip-ts/package.json                     → "0.5.0"
```

Then regenerate the lockfile so CI's `npm ci` works:

```bash
cd examples/anip-ts && npm install --package-lock-only && cd ../..
```

This updates `package-lock.json` to reflect the new `@anip-dev/*` versions from the local `file:` dependencies. Without this, `npm ci` will fail because the lockfile references 0.4.0 versions that no longer match the on-disk packages.

**Step 4: Verify PROTOCOL_VERSION is unchanged**

```bash
grep -r "PROTOCOL_VERSION" packages/python/anip-core/src/anip_core/constants.py
# Should show: PROTOCOL_VERSION = "anip/0.3"
```

**Step 5: Run full test suite**

```bash
source .venv/bin/activate && python -m pytest packages/python/ -x -q
npx vitest run --reporter=verbose
```

All tests must pass: Python and TypeScript, 0 failures.

**Step 6: Commit**

```bash
git commit -m "chore: bump all packages from 0.4.0 to 0.5.0"
```

---

## Server exports update

**Important:** After Tasks 1-5 (Python server) and 6-10 (TypeScript server), verify that `__init__.py` / `index.ts` exports are correct. `InMemoryStorage` should still be exported (now async). `StorageBackend` should still be exported (now async protocol/interface). No new exports needed unless compliance fixtures are meant to be public.

## Task dependency graph

```
Tasks 1-5 (Python server)  ──→  Task 11 (Python service)  ──→  Task 13 (FastAPI binding)
                                                            ──→  Task 14 (Drop Flask)
Tasks 6-10 (TypeScript server) ──→  Task 12 (TS service)  ──→  Task 15 (TS bindings)

Tasks 13-15  ──→  Task 16 (Examples)  ──→  Task 17 (Version bump)
```

Python track (Tasks 1-5, 11, 13, 14) and TypeScript track (Tasks 6-10, 12, 15) can proceed in parallel within each track. Task 16 and 17 depend on both tracks completing.
