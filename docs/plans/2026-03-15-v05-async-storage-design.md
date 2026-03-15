# v0.5 Async Storage Design

**Goal:** Replace the sync storage foundation with a fully async architecture in both languages. One canonical async `StorageBackend` contract, fully async runtimes, compliance test fixtures, no dual-mode runtime logic.

**Architecture:** Storage goes async. Everything that touches storage becomes async. Everything that doesn't stays sync. No shims, no dual-mode dispatch, no backward compatibility with v0.4 sync contracts. Pre-1.0 clean break.

**Scope:** Runtime/SDK architecture change. Wire protocol unchanged (`anip/0.3`).

---

## 1. StorageBackend Interface

Both languages get a single async storage contract. The sync `StorageBackend` is removed — not deprecated, removed. Same name `StorageBackend`, same method names. The only change is sync→async signatures.

### Python (`anip-server`)

```python
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class StorageBackend(Protocol):
    async def store_token(self, token_data: dict[str, Any]) -> None: ...
    async def load_token(self, token_id: str) -> dict[str, Any] | None: ...
    async def store_audit_entry(self, entry: dict[str, Any]) -> None: ...
    async def query_audit_entries(
        self, *,
        capability: str | None = None,
        root_principal: str | None = None,
        since: str | None = None,
        invocation_id: str | None = None,
        client_reference_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]: ...
    async def get_last_audit_entry(self) -> dict[str, Any] | None: ...
    async def get_audit_entries_range(self, first: int, last: int) -> list[dict[str, Any]]: ...
    async def store_checkpoint(self, body: dict[str, Any], signature: str) -> None: ...
    async def get_checkpoints(self, limit: int = 10) -> list[dict[str, Any]]: ...
    async def get_checkpoint_by_id(self, checkpoint_id: str) -> dict[str, Any] | None: ...
```

### TypeScript (`@anip/server`)

```typescript
export interface StorageBackend {
  storeToken(tokenData: Record<string, unknown>): Promise<void>;
  loadToken(tokenId: string): Promise<Record<string, unknown> | null>;
  storeAuditEntry(entry: Record<string, unknown>): Promise<void>;
  queryAuditEntries(opts?: {
    capability?: string;
    rootPrincipal?: string;
    since?: string;
    invocationId?: string;
    clientReferenceId?: string;
    limit?: number;
  }): Promise<Record<string, unknown>[]>;
  getLastAuditEntry(): Promise<Record<string, unknown> | null>;
  getAuditEntriesRange(first: number, last: number): Promise<Record<string, unknown>[]>;
  storeCheckpoint(body: Record<string, unknown>, signature: string): Promise<void>;
  getCheckpoints(limit?: number): Promise<Record<string, unknown>[]>;
  getCheckpointById(checkpointId: string): Promise<Record<string, unknown> | null>;
}
```

## 2. Async Ripple — DelegationEngine, AuditLog, MerkleTree

Storage going async means everything that touches storage becomes async.

**DelegationEngine** (both languages) — all methods that call `storage.load_token()` or `storage.store_token()` become async:

- `issue_root_token()` → async
- `delegate()` → async
- `validate_delegation()` → async
- `resolve_registered_token()` → async
- `get_token()` → async
- `get_chain()` → async
- `get_root_principal()` → async (fallback path calls `get_chain()` which hits storage)
- `get_chain_token_ids()` → async (calls `get_chain()`)
- `register_token()` → async (internal)

Methods that are purely in-memory stay sync:

- `acquire_exclusive_lock()` / `release_exclusive_lock()` — Python `threading.Lock`
- Scope/constraint validation helpers that operate on already-loaded token data

**AuditLog** (both languages):

- `log_entry()` → async (calls `storage.get_last_audit_entry()` and `storage.store_audit_entry()`)
- `query()` → async (calls `storage.query_audit_entries()`)
- `get_merkle_snapshot()` → stays sync (in-memory Merkle tree, no storage call)

**MerkleTree** — no change. Purely in-memory computation.

**Principle:** Async only where storage I/O happens. In-memory operations stay sync. A method stays sync only if it is guaranteed storage-free across all code paths.

## 3. Service Runtime — Full Async

### Python `ANIPService`

Methods that cross storage/network boundaries become async:

| Method | v0.4 | v0.5 | Reason |
|--------|------|------|--------|
| `invoke()` | sync | async | storage (token, audit, checkpoint) |
| `issue_token()` | sync | async | storage (load parent, store token) |
| `query_audit()` | sync | async | storage (query audit entries) |
| `get_checkpoints()` | sync | async | storage |
| `get_checkpoint()` | sync | async | storage (checkpoint + merkle rebuild) |
| `authenticate_bearer()` | sync | async | fallback calls `resolve_bearer_token()` → storage |

Methods that are pure in-memory stay sync:

| Method | v0.4 | v0.5 | Reason |
|--------|------|------|--------|
| `discover_permissions()` | sync | sync | evaluates resolved token against manifest in memory |
| `get_signed_manifest()` | sync | sync | local CPU crypto, no I/O |
| `get_jwks()` | sync | sync | returns already-loaded keys from memory |
| `get_discovery()` | sync | sync | returns cached dict |
| `start()` | sync | sync | timer setup |
| `stop()` | sync | sync | timer teardown |

### TypeScript service

Already partially async. Changes:

| Method | v0.4 | v0.5 | Reason |
|--------|------|------|--------|
| `queryAudit()` | sync | async | storage |
| `getCheckpoints()` | sync | async | storage |
| `getCheckpoint()` | sync | async | storage |
| `discoverPermissions()` | sync | sync | in-memory scope check, no change |
| `getSignedManifest()` | async | async | already async (jose), no change |
| `getJwks()` | async | async | already async, no change |
| `authenticateBearer()` | async | async | already async, no change |
| `invoke()` | async | async | no change (but now awaits storage internally) |
| `issueToken()` | async | async | no change |

The full TypeScript ripple through engine/audit/storage calls must be audited carefully during implementation — the table above captures the public surface but internal helper methods will also need async conversion wherever they cross storage boundaries.

### Handler type

Handlers become async-capable:

- **Python:** `Handler = Callable[[InvocationContext, dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]`
- **TypeScript:** `Handler = (ctx: InvocationContext, params: Record<string, unknown>) => Record<string, unknown> | Promise<Record<string, unknown>>` (already works since TS awaits both)

The runtime awaits the handler result regardless — sync handlers return immediately, async handlers are awaited.

## 4. Framework Bindings

### Python: Drop Flask, keep FastAPI

`anip-flask` is removed. Flask's async support is bolted on, not native. Maintaining a sync→async bridge binding contradicts the "no ugly shims" principle.

If `anip-flask` has already been published, it gets an explicit deprecation notice in release notes explaining the removal rationale.

`anip-fastapi` routes already use `async def`. The change is that they now `await` service methods that were previously sync:

- `_resolve_token()` → async (calls `service.resolve_bearer_token()` → storage)
- `_extract_principal()` → async (calls `service.authenticate_bearer()` → may hit storage)
- Route handlers `await service.invoke(...)`, `await service.query_audit(...)`, etc.

### TypeScript: Keep Hono, Express, Fastify

Handlers are already async. The change is that `queryAudit()`, `getCheckpoints()`, `getCheckpoint()` calls that were previously sync now need `await`. Small wiring change across all three bindings.

## 5. Default Backends and Test Infrastructure

### In-memory backend

`InMemoryStorage` becomes the async reference implementation. Same logic, `async` method signatures. No real I/O — `await` is effectively a no-op, but it satisfies the contract. This is the backend used by all unit tests.

### SQLite backend

Stays as the default persistent backend for local development and examples.

- **Python:** `sqlite3` calls wrapped in `asyncio.to_thread()`. Each storage method does `return await asyncio.to_thread(self._sync_impl, ...)`. The sync SQLite logic stays intact internally — `to_thread` moves it off the event loop.
- **TypeScript:** `better-sqlite3` calls run in a `Worker` thread via `worker_threads`. A wrapper sends method name + args to a dedicated worker, receives the result via `Promise`. Genuine off-thread execution, not fake `Promise.resolve()` wrapping. This is the most implementation-sensitive piece — must be genuinely robust, not a brittle shim.

### Backend compliance test fixtures

A reusable test suite that any `StorageBackend` implementation must pass. Exported so adopters can run them against their own adapters.

Tests cover:

- Token store/load roundtrip
- Token load returns `None`/`null` for unknown ID
- Audit entry store + query (all filter combinations including lineage fields)
- Audit ordering (sequence numbers monotonically increase)
- Audit entries range retrieval
- Checkpoint store/load roundtrip
- Checkpoint listing with limit
- Concurrency: audit insertion ordering under concurrent calls (verifies no broken sequence/order behavior)

### Required storage semantics

Any `StorageBackend` implementation must provide these behavioral guarantees:

- **Ordering:** Audit entries must be retrievable in insertion order by sequence number.
- **Atomicity:** Each storage method is a single atomic operation. ANIP does not require cross-method transactionality — there is no multi-method transaction boundary.
- **Durability:** After a store method returns, the data must survive process restart (for persistent backends; in-memory is exempt).
- **Consistency:** `get_last_audit_entry()` must reflect the most recently stored entry — no stale reads.
- **Nullability:** `load_token()` and `get_checkpoint_by_id()` return `None`/`null` for unknown IDs, never throw.

## 6. Package Changes and Version Bump

### Packages removed

- `anip-flask` — removed. Flask's sync-native runtime is incompatible with the fully async architecture. Explicitly noted as deprecated/removed in release notes.

### Packages changed (12 remaining, lockstep 0.5.0)

| Layer | Python | TypeScript |
|-------|--------|------------|
| Core | anip-core | @anip/core |
| Crypto | anip-crypto | @anip/crypto |
| Server | anip-server | @anip/server |
| Service | anip-service | @anip/service |
| Binding | anip-fastapi | @anip/hono, @anip/express, @anip/fastify |

### Change summary by package

| Package | Change |
|---------|--------|
| `anip-server` (Python) | `StorageBackend` → async. `AuditLog` → async. `DelegationEngine` → async. `InMemoryStorage` → async. `SQLiteStorage` → async via `to_thread`. Compliance test fixtures added. |
| `@anip/server` (TypeScript) | Same: `StorageBackend` → Promise-based. `AuditLog.query()` → async. `DelegationEngine` → async. `InMemoryStorage` → async. `SQLiteStorage` → async via worker thread. Compliance fixtures added. |
| `anip-service` (Python) | `ANIPService` methods → async where storage-bound. Handler type accepts `Awaitable`. |
| `@anip/service` (TypeScript) | `queryAudit`, `getCheckpoints`, `getCheckpoint` → async. Full internal audit of engine/storage call sites. |
| `anip-fastapi` | Routes `await` async service methods. `_resolve_token` / `_extract_principal` → async. |
| `@anip/hono`, `@anip/express`, `@anip/fastify` | `await` newly-async service calls. |
| `anip-core`, `@anip/core` | No changes. Version bump only. |
| `anip-crypto`, `@anip/crypto` | No changes. Version bump only. |

Inter-package deps updated to `>=0.5.0` / `"0.5.0"`.

`PROTOCOL_VERSION` stays `anip/0.3` — this is a runtime/SDK architecture change, not a wire protocol change.

## 7. What v0.5 Does NOT Do

- Ship a bundled production backend (Postgres, Prisma, etc.)
- Add async SQLite as a first-class "async backend" — the SQLite wrappers are pragmatic defaults, not the architecture's showcase
- Change wire protocol semantics — `PROTOCOL_VERSION` stays `anip/0.3`, request/response shapes unchanged
- Add new protocol features (no new fields, no new endpoints)
- Introduce ORM dependencies into any ANIP package
- Maintain backward compatibility with v0.4 sync `StorageBackend` — this is a clean break
- Add connection pooling, retry logic, or other production DB concerns — those belong in adopter adapters
- Deprecate sync SQLite as a local development tool — it remains the default, just behind an async wrapper
