# ANIP v0.10: Horizontal Scaling Readiness — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make ANIP's audit and trust guarantees remain correct when one logical service runs across multiple replicas with shared storage.

**Architecture:** Refactor `StorageBackend` so it owns atomic audit append and cluster coordination primitives. Ship a PostgreSQL backend as the reference shared-storage implementation. Shift checkpoint generation from process-local Merkle snapshots to full storage-derived reconstruction with lease-based leader coordination. Add lease-based distributed exclusivity. All changes in both Python and TypeScript runtimes.

**Tech Stack:** Python (asyncpg, pytest, Pydantic), TypeScript (pg/node-postgres, vitest, Zod), PostgreSQL 15+, SQLite (unchanged for dev)

**Design doc:** `docs/plans/2026-03-17-v010-horizontal-scaling-design.md`

---

## Dependency Order

```
Tasks 1-2: StorageBackend contract (Python, TypeScript)
    ↓
Tasks 3-4: InMemoryStorage + SQLiteStorage (Python, TypeScript)
    ↓
Task 5: Extract canonical hash utility (both runtimes)
    ↓
Task 6: AuditLog refactor — use append_audit_entry (both runtimes)
    ↓
Tasks 7-8: PostgresStorage (Python, TypeScript)
    ↓
Tasks 9-10: Storage-derived checkpoint generation (Python, TypeScript)
    ↓
Tasks 11-12: Distributed exclusivity (Python, TypeScript)
    ↓
Tasks 13-14: Service layer integration (Python, TypeScript)
    ↓
Task 15: Framework bindings lifecycle updates (all)
    ↓
Task 16: Deployment guide
    ↓
Task 17: SPEC.md + schema + version bumps
    ↓
Task 18: README updates
```

---

### Task 1: Python StorageBackend Contract — Add New Methods

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/storage.py` (lines 18-59, StorageBackend Protocol)
- Modify: `packages/python/anip-server/src/anip_server/__init__.py` (no new exports needed — Protocol already exported)

**What to do:**

Add 7 new methods to the `StorageBackend` Protocol class (after existing methods, before the class closes):

```python
async def append_audit_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
    """Atomically append an audit entry, assigning sequence_number and previous_hash.

    The caller provides the entry WITHOUT sequence_number or previous_hash.
    The storage layer assigns both atomically and returns the complete entry (unsigned).
    """
    ...

async def update_audit_signature(self, sequence_number: int, signature: str) -> None:
    """Set the signature on an already-appended audit entry.

    Called after append_audit_entry to attach the cryptographic signature.
    The entry is briefly unsigned between append and this call.
    """
    ...

async def get_max_audit_sequence(self) -> int | None:
    """Return the highest sequence_number in the audit log, or None if empty."""
    ...

async def try_acquire_exclusive(self, key: str, holder: str, ttl_seconds: int) -> bool:
    """Attempt to acquire an exclusive lease. Returns True if acquired."""
    ...

async def release_exclusive(self, key: str, holder: str) -> None:
    """Release an exclusive lease if held by the given holder."""
    ...

async def try_acquire_leader(self, role: str, holder: str, ttl_seconds: int) -> bool:
    """Attempt to acquire a leader lease for a background role. Returns True if acquired."""
    ...

async def release_leader(self, role: str, holder: str) -> None:
    """Release a leader lease if held by the given holder."""
    ...
```

**Step 1:** Add the 7 method stubs to the `StorageBackend` Protocol.

**Step 2:** Run existing tests to confirm nothing breaks:
```bash
cd packages/python/anip-server && python -m pytest tests/ -v
```
Expected: All existing tests PASS (Protocol is structural, adding methods doesn't break existing implementations until we enforce them).

**Step 3:** Commit.
```bash
git add packages/python/anip-server/src/anip_server/storage.py
git commit -m "feat(server): add horizontal-scaling methods to Python StorageBackend protocol"
```

---

### Task 2: TypeScript StorageBackend Contract — Add New Methods

**Files:**
- Modify: `packages/typescript/server/src/storage.ts` (lines 16-36, StorageBackend interface)

**What to do:**

Add 7 new methods to the `StorageBackend` interface (after existing methods):

```typescript
appendAuditEntry(entryData: Record<string, unknown>): Promise<Record<string, unknown>>;
updateAuditSignature(sequenceNumber: number, signature: string): Promise<void>;
getMaxAuditSequence(): Promise<number | null>;
tryAcquireExclusive(key: string, holder: string, ttlSeconds: number): Promise<boolean>;
releaseExclusive(key: string, holder: string): Promise<void>;
tryAcquireLeader(role: string, holder: string, ttlSeconds: number): Promise<boolean>;
releaseLeader(role: string, holder: string): Promise<void>;
```

**Step 1:** Add the 7 method signatures to the `StorageBackend` interface.

**Step 2:** TypeScript will now error on `InMemoryStorage` and `SQLiteStorage` because they don't implement the new methods. That's expected — Task 4 will fix it. Verify the interface file itself has no syntax errors:
```bash
cd packages/typescript && npx tsc --noEmit --pretty server/src/storage.ts 2>&1 | head -5
```
Expected: Type errors on InMemoryStorage/SQLiteStorage missing implementations (not syntax errors).

**Step 3:** Commit.
```bash
git add packages/typescript/server/src/storage.ts
git commit -m "feat(server): add horizontal-scaling methods to TypeScript StorageBackend interface"
```

---

### Task 3: Python InMemoryStorage + SQLiteStorage — Implement New Methods

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/storage.py` (InMemoryStorage class ~line 62, SQLiteStorage class ~line 290)
- Create: `packages/python/anip-server/tests/test_horizontal.py`

**What to do:**

**InMemoryStorage** — add 7 methods:

```python
async def append_audit_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
    last = self._audit_entries[-1] if self._audit_entries else None
    if last is None:
        seq = 1
        prev_hash = "sha256:0"
    else:
        seq = last["sequence_number"] + 1
        prev_hash = compute_entry_hash(last)
    entry = {**entry_data, "sequence_number": seq, "previous_hash": prev_hash}
    self._audit_entries.append(entry)
    return entry

async def update_audit_signature(self, sequence_number: int, signature: str) -> None:
    for entry in self._audit_entries:
        if entry["sequence_number"] == sequence_number:
            entry["signature"] = signature
            return

async def get_max_audit_sequence(self) -> int | None:
    if not self._audit_entries:
        return None
    return max(e["sequence_number"] for e in self._audit_entries)

async def try_acquire_exclusive(self, key: str, holder: str, ttl_seconds: int) -> bool:
    now = datetime.now(timezone.utc)
    existing = self._exclusive_leases.get(key)
    if existing is None or existing[1] < now or existing[0] == holder:
        self._exclusive_leases[key] = (holder, now + timedelta(seconds=ttl_seconds))
        return True
    return False

async def release_exclusive(self, key: str, holder: str) -> None:
    existing = self._exclusive_leases.get(key)
    if existing is not None and existing[0] == holder:
        del self._exclusive_leases[key]

async def try_acquire_leader(self, role: str, holder: str, ttl_seconds: int) -> bool:
    return await self.try_acquire_exclusive(f"leader:{role}", holder, ttl_seconds)

async def release_leader(self, role: str, holder: str) -> None:
    await self.release_exclusive(f"leader:{role}", holder)
```

Add `_exclusive_leases: dict[str, tuple[str, datetime]]` to `InMemoryStorage.__init__`.

Note: `compute_entry_hash` is the static method currently on `AuditLog`. Task 5 will extract it. For now, inline or import from `audit.py`. Use `AuditLog._compute_entry_hash` as a temporary reference until Task 5 extracts it.

**SQLiteStorage** — add 7 methods:

```python
async def append_audit_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(self._sync_append_audit_entry, entry_data)

def _sync_append_audit_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
    with self._lock:
        last = self._sync_get_last_audit_entry()
        if last is None:
            seq = 1
            prev_hash = "sha256:0"
        else:
            seq = last["sequence_number"] + 1
            prev_hash = compute_entry_hash(last)
        entry = {**entry_data, "sequence_number": seq, "previous_hash": prev_hash}
        self._sync_store_audit_entry(entry)
        return entry

async def update_audit_signature(self, sequence_number: int, signature: str) -> None:
    await asyncio.to_thread(self._sync_update_audit_signature, sequence_number, signature)

def _sync_update_audit_signature(self, sequence_number: int, signature: str) -> None:
    with self._lock:
        self._conn.execute(
            "UPDATE audit_log SET signature = ? WHERE sequence_number = ?",
            (signature, sequence_number),
        )

async def get_max_audit_sequence(self) -> int | None:
    return await asyncio.to_thread(self._sync_get_max_audit_sequence)

def _sync_get_max_audit_sequence(self) -> int | None:
    with self._lock:
        row = self._conn.execute("SELECT MAX(sequence_number) FROM audit_log").fetchone()
        return row[0] if row and row[0] is not None else None
```

For exclusivity and leader methods on SQLiteStorage, use in-memory dicts (same as InMemoryStorage — single-process is fine for SQLite):

```python
# Add to __init__:
self._exclusive_leases: dict[str, tuple[str, datetime]] = {}
```

Then implement `try_acquire_exclusive`, `release_exclusive`, `try_acquire_leader`, `release_leader` identically to InMemoryStorage.

**Tests** (`test_horizontal.py`):

```python
"""Tests for v0.10 horizontal-scaling StorageBackend methods."""
import pytest
from anip_server import InMemoryStorage, SQLiteStorage

@pytest.fixture
def memory_store():
    return InMemoryStorage()

@pytest.fixture
def sqlite_store(tmp_path):
    return SQLiteStorage(str(tmp_path / "test.db"))

@pytest.fixture(params=["memory", "sqlite"])
def store(request, memory_store, sqlite_store):
    return memory_store if request.param == "memory" else sqlite_store

class TestAppendAuditEntry:
    async def test_first_entry_gets_sequence_1(self, store):
        entry = await store.append_audit_entry({
            "capability": "test", "success": True, "timestamp": "2026-01-01T00:00:00Z",
        })
        assert entry["sequence_number"] == 1
        assert entry["previous_hash"] == "sha256:0"

    async def test_sequential_entries_increment(self, store):
        e1 = await store.append_audit_entry({"capability": "a", "success": True, "timestamp": "2026-01-01T00:00:00Z"})
        e2 = await store.append_audit_entry({"capability": "b", "success": True, "timestamp": "2026-01-01T00:00:01Z"})
        assert e2["sequence_number"] == 2
        assert e2["previous_hash"] != "sha256:0"

    async def test_previous_hash_chains(self, store):
        e1 = await store.append_audit_entry({"capability": "a", "success": True, "timestamp": "2026-01-01T00:00:00Z"})
        e2 = await store.append_audit_entry({"capability": "b", "success": True, "timestamp": "2026-01-01T00:00:01Z"})
        # e2.previous_hash should be hash of e1
        assert e2["previous_hash"].startswith("sha256:")
        assert len(e2["previous_hash"]) > 10

class TestGetMaxAuditSequence:
    async def test_empty_returns_none(self, store):
        assert await store.get_max_audit_sequence() is None

    async def test_returns_highest(self, store):
        await store.append_audit_entry({"capability": "a", "success": True, "timestamp": "2026-01-01T00:00:00Z"})
        await store.append_audit_entry({"capability": "b", "success": True, "timestamp": "2026-01-01T00:00:01Z"})
        assert await store.get_max_audit_sequence() == 2

class TestExclusiveLeases:
    async def test_acquire_and_release(self, store):
        assert await store.try_acquire_exclusive("key1", "holder-a", 30) is True
        assert await store.try_acquire_exclusive("key1", "holder-b", 30) is False
        await store.release_exclusive("key1", "holder-a")
        assert await store.try_acquire_exclusive("key1", "holder-b", 30) is True

    async def test_same_holder_can_reacquire(self, store):
        assert await store.try_acquire_exclusive("key1", "holder-a", 30) is True
        assert await store.try_acquire_exclusive("key1", "holder-a", 30) is True

    async def test_wrong_holder_cannot_release(self, store):
        await store.try_acquire_exclusive("key1", "holder-a", 30)
        await store.release_exclusive("key1", "holder-b")  # wrong holder
        assert await store.try_acquire_exclusive("key1", "holder-b", 30) is False

class TestLeaderLeases:
    async def test_acquire_leader(self, store):
        assert await store.try_acquire_leader("checkpoint", "replica-1", 60) is True
        assert await store.try_acquire_leader("checkpoint", "replica-2", 60) is False

    async def test_release_and_reacquire(self, store):
        await store.try_acquire_leader("checkpoint", "replica-1", 60)
        await store.release_leader("checkpoint", "replica-1")
        assert await store.try_acquire_leader("checkpoint", "replica-2", 60) is True
```

**Step 1:** Write `test_horizontal.py`.

**Step 2:** Run tests — they should FAIL (methods not implemented):
```bash
cd packages/python/anip-server && python -m pytest tests/test_horizontal.py -v
```

**Step 3:** Implement all 6 methods on `InMemoryStorage` and `SQLiteStorage`.

**Step 4:** Run tests — all PASS:
```bash
cd packages/python/anip-server && python -m pytest tests/ -v
```

**Step 5:** Commit.
```bash
git add packages/python/anip-server/
git commit -m "feat(server): implement horizontal-scaling methods in Python InMemory + SQLite backends"
```

---

### Task 4: TypeScript InMemoryStorage + SQLiteStorage — Implement New Methods

**Files:**
- Modify: `packages/typescript/server/src/storage.ts` (InMemoryStorage ~line 44, SQLiteStorage ~line 156)
- Modify: `packages/typescript/server/src/sqlite-worker.ts` (add worker methods)
- Create: `packages/typescript/server/tests/horizontal.test.ts`

**What to do:**

Mirror Task 3 for TypeScript. Same logic, TypeScript idioms.

**InMemoryStorage** — add to the class:

```typescript
private _exclusiveLeases = new Map<string, { holder: string; expiresAt: Date }>();

async appendAuditEntry(entryData: Record<string, unknown>): Promise<Record<string, unknown>> {
  const last = this.auditEntries.length > 0
    ? this.auditEntries[this.auditEntries.length - 1]
    : null;
  const sequenceNumber = last === null ? 1 : (last.sequence_number as number) + 1;
  const previousHash = last === null ? "sha256:0" : computeEntryHash(last);
  const entry = { ...entryData, sequence_number: sequenceNumber, previous_hash: previousHash };
  this.auditEntries.push(entry);
  return entry;
}

async updateAuditSignature(sequenceNumber: number, signature: string): Promise<void> {
  const entry = this.auditEntries.find(e => e.sequence_number === sequenceNumber);
  if (entry) entry.signature = signature;
}

async getMaxAuditSequence(): Promise<number | null> {
  if (this.auditEntries.length === 0) return null;
  return Math.max(...this.auditEntries.map(e => e.sequence_number as number));
}

async tryAcquireExclusive(key: string, holder: string, ttlSeconds: number): Promise<boolean> {
  const now = new Date();
  const existing = this._exclusiveLeases.get(key);
  if (!existing || existing.expiresAt < now || existing.holder === holder) {
    this._exclusiveLeases.set(key, { holder, expiresAt: new Date(now.getTime() + ttlSeconds * 1000) });
    return true;
  }
  return false;
}

async releaseExclusive(key: string, holder: string): Promise<void> {
  const existing = this._exclusiveLeases.get(key);
  if (existing && existing.holder === holder) {
    this._exclusiveLeases.delete(key);
  }
}

async tryAcquireLeader(role: string, holder: string, ttlSeconds: number): Promise<boolean> {
  return this.tryAcquireExclusive(`leader:${role}`, holder, ttlSeconds);
}

async releaseLeader(role: string, holder: string): Promise<void> {
  return this.releaseExclusive(`leader:${role}`, holder);
}
```

**SQLiteStorage + sqlite-worker.ts** — add methods:

The SQLiteStorage class delegates via RPC to the worker. Add:

In `storage.ts` (SQLiteStorage class):
```typescript
async appendAuditEntry(entryData: Record<string, unknown>): Promise<Record<string, unknown>> {
  return (await this.call("appendAuditEntry", [entryData])) as Record<string, unknown>;
}
async getMaxAuditSequence(): Promise<number | null> {
  return (await this.call("getMaxAuditSequence", [])) as number | null;
}
```

For exclusivity on SQLiteStorage, use in-memory (same as InMemory — single-process for SQLite). Add the same `_exclusiveLeases` Map and methods directly on SQLiteStorage (these don't go through the worker).

In `sqlite-worker.ts`, add:
```typescript
function appendAuditEntry(entryData: Record<string, unknown>): Record<string, unknown> {
  const last = getLastAuditEntry();
  const sequenceNumber = last === null ? 1 : (last.sequence_number as number) + 1;
  const previousHash = last === null ? "sha256:0" : computeEntryHash(last);
  const entry = { ...entryData, sequence_number: sequenceNumber, previous_hash: previousHash };
  // Use existing storeAuditEntry logic for the INSERT
  storeAuditEntry(entry);
  return entry;
}

function getMaxAuditSequence(): number | null {
  const row = db.prepare("SELECT MAX(sequence_number) as max_seq FROM audit_log").get() as any;
  return row?.max_seq ?? null;
}
```

Add `appendAuditEntry` and `getMaxAuditSequence` to the worker's `methods` dispatch table.

**Tests** (`horizontal.test.ts`) — mirror the Python tests from Task 3 using vitest patterns:

```typescript
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { InMemoryStorage, SQLiteStorage } from "../src/storage.js";
import { unlinkSync } from "fs";
import { randomUUID } from "crypto";

describe.each([
  { name: "InMemoryStorage", factory: () => ({ store: new InMemoryStorage(), cleanup: async () => {} }) },
  { name: "SQLiteStorage", factory: () => {
    const path = `/tmp/anip-hz-${randomUUID()}.db`;
    const store = new SQLiteStorage(path);
    return { store, cleanup: async () => { await store.terminate(); try { unlinkSync(path); } catch {} } };
  }},
])("$name horizontal-scaling methods", ({ factory }) => {
  let store: InMemoryStorage | SQLiteStorage;
  let cleanup: () => Promise<void>;

  beforeEach(() => { ({ store, cleanup } = factory()); });
  afterEach(async () => { await cleanup(); });

  // Same test structure as Python Task 3
});
```

**Step 1:** Write `horizontal.test.ts`.

**Step 2:** Run tests — FAIL (methods not implemented).

**Step 3:** Implement all methods on InMemoryStorage, SQLiteStorage, and sqlite-worker.

**Step 4:** Build and run tests:
```bash
cd packages/typescript && npx tsc --build server && npx vitest run --project server
```

**Step 5:** Commit.
```bash
git add packages/typescript/server/
git commit -m "feat(server): implement horizontal-scaling methods in TypeScript InMemory + SQLite backends"
```

---

### Task 5: Extract Canonical Hash Utility (Both Runtimes)

**Files:**
- Create: `packages/python/anip-server/src/anip_server/hashing.py`
- Create: `packages/typescript/server/src/hashing.ts`
- Modify: `packages/python/anip-server/src/anip_server/audit.py` (import from hashing)
- Modify: `packages/typescript/server/src/audit.ts` (import from hashing)
- Modify: `packages/python/anip-server/src/anip_server/__init__.py` (export compute_entry_hash)
- Modify: `packages/typescript/server/src/index.ts` (export computeEntryHash)

**What to do:**

The `_compute_entry_hash` and `_canonical_bytes` static methods currently live on the `AuditLog` class. Both the `AuditLog` and the storage backends need them. Extract to a shared module.

**Python** (`hashing.py`):
```python
"""Canonical hashing utilities for ANIP audit entries."""
import hashlib
import json
from typing import Any


def compute_entry_hash(entry: dict[str, Any]) -> str:
    """Compute the canonical hash of an audit entry for hash-chain linking."""
    canonical = json.dumps(
        {k: v for k, v in sorted(entry.items()) if k not in ("signature", "id")},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def canonical_bytes(entry: dict[str, Any]) -> bytes:
    """Return canonical JSON bytes of an audit entry for Merkle leaf hashing."""
    return json.dumps(
        {k: v for k, v in sorted(entry.items()) if k not in ("signature", "id")},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
```

**TypeScript** (`hashing.ts`):
```typescript
import { createHash } from "crypto";

export function computeEntryHash(entry: Record<string, unknown>): string {
  const canonical = canonicalBytes(entry);
  const hash = createHash("sha256").update(canonical).digest("hex");
  return `sha256:${hash}`;
}

export function canonicalBytes(entry: Record<string, unknown>): string {
  const filtered: Record<string, unknown> = {};
  for (const key of Object.keys(entry).sort()) {
    if (key !== "signature" && key !== "id") {
      filtered[key] = entry[key];
    }
  }
  return JSON.stringify(filtered);
}
```

Update `AuditLog` in both runtimes to import from `hashing` instead of using private static methods. Keep the static methods as thin wrappers that delegate to the extracted functions (to avoid breaking any existing callers), or remove them if nothing outside the class calls them.

Update the storage implementations from Tasks 3-4 to import `compute_entry_hash` from `hashing` instead of the temporary reference to `AuditLog._compute_entry_hash`.

**Step 1:** Create `hashing.py` and `hashing.ts`.

**Step 2:** Update `AuditLog` in both runtimes to use the extracted functions.

**Step 3:** Update storage implementations to import from `hashing`.

**Step 4:** Update `__init__.py` and `index.ts` exports.

**Step 5:** Run all tests in both runtimes:
```bash
cd packages/python/anip-server && python -m pytest tests/ -v
cd packages/typescript && npx tsc --build server && npx vitest run --project server
```

**Step 6:** Commit.
```bash
git add packages/python/anip-server/ packages/typescript/server/
git commit -m "refactor(server): extract canonical hash utilities to shared module"
```

---

### Task 6: AuditLog Refactor — Use append_audit_entry (Both Runtimes)

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/audit.py` (log_entry method, lines 27-91)
- Modify: `packages/typescript/server/src/audit.ts` (logEntry method, lines 37-91)
- Modify: `packages/python/anip-server/tests/test_audit.py`
- Modify: `packages/typescript/server/tests/audit.test.ts`

**What to do:**

Refactor `log_entry` / `logEntry` to:
1. **Stop** calling `get_last_audit_entry()` + incrementing sequence
2. **Stop** calling `self._merkle.add_leaf()`
3. **Call** `self._storage.append_audit_entry(entry_data)` instead of `self._storage.store_audit_entry(entry)`
4. **Remove** the `_merkle` instance from AuditLog entirely
5. **Remove** `get_merkle_snapshot()` method

**Python `log_entry` becomes:**

```python
async def log_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
    """Log an audit entry. Storage handles sequence allocation and hash chain."""
    now = datetime.now(timezone.utc).isoformat()

    entry_for_storage = {
        "timestamp": now,
        "capability": entry_data["capability"],
        "token_id": entry_data.get("token_id"),
        "issuer": entry_data.get("issuer"),
        "subject": entry_data.get("subject"),
        "root_principal": entry_data.get("root_principal"),
        "parameters": entry_data.get("parameters"),
        "success": entry_data["success"],
        "result_summary": entry_data.get("result_summary"),
        "failure_type": entry_data.get("failure_type"),
        "cost_actual": entry_data.get("cost_actual"),
        "delegation_chain": entry_data.get("delegation_chain"),
        "invocation_id": entry_data.get("invocation_id"),
        "client_reference_id": entry_data.get("client_reference_id"),
        "stream_summary": entry_data.get("stream_summary"),
        "event_class": entry_data.get("event_class"),
        "retention_tier": entry_data.get("retention_tier"),
        "expires_at": entry_data.get("expires_at"),
        "storage_redacted": entry_data.get("storage_redacted", False),
        "entry_type": entry_data.get("entry_type"),
        "grouping_key": entry_data.get("grouping_key"),
        "aggregation_window": entry_data.get("aggregation_window"),
        "aggregation_count": entry_data.get("aggregation_count"),
        "first_seen": entry_data.get("first_seen"),
        "last_seen": entry_data.get("last_seen"),
        "representative_detail": entry_data.get("representative_detail"),
    }

    # Storage atomically assigns sequence_number and previous_hash
    entry = await self._storage.append_audit_entry(entry_for_storage)

    # Sign if signer is provided
    if self._signer:
        sig = self._signer(entry)
        if inspect.isawaitable(sig):
            sig = await sig
        entry["signature"] = sig
    else:
        entry["signature"] = None

    # Update the stored entry with signature
    # (signature is set after append because it can't be part of the hash chain)
    await self._storage.store_audit_entry(entry)
    return entry
```

**Important:** The signature is computed AFTER append because `previous_hash` must be set first, and the signature covers the entry including `previous_hash`. But `store_audit_entry` is called a second time to persist the signature. This is the existing pattern — the signature is not part of the hash chain (excluded by `_compute_entry_hash`).

Wait — actually, looking at the current code more carefully: the current `log_entry` builds the entry, computes the Merkle leaf, then signs, then stores ONCE. The signature is excluded from the hash chain. So the new flow should be:

1. Build entry_for_storage (without sequence_number, previous_hash, signature)
2. `append_audit_entry()` → returns entry with sequence_number + previous_hash (but no signature yet)
3. Sign the returned entry → get signature
4. Set `entry["signature"] = sig`
5. Need to update the stored row with the signature

This means we either:
- (a) Add an `update_audit_entry_signature(sequence_number, signature)` method, or
- (b) Have `append_audit_entry` not store the entry yet — just compute sequence+hash, and have the caller call `store_audit_entry` after signing, or
- (c) Accept that the entry is stored without signature initially and update it after signing

Option (b) is cleanest: split `append_audit_entry` into two responsibilities:
- `allocate_audit_sequence(entry_data) -> entry_with_sequence` — atomically assigns sequence_number and previous_hash but does NOT store
- `store_audit_entry(entry)` — stores the complete entry (including signature)

Actually, this is getting complex. The simplest correct approach: keep `append_audit_entry` as the atomic store, but the entry goes in without signature. Then add an `update_audit_entry_signature` method:

```python
async def update_audit_entry_signature(self, sequence_number: int, signature: str) -> None:
    """Update the signature on an already-stored audit entry."""
    ...
```

OR: have `append_audit_entry` accept the signer as part of the flow — but that pushes signing into storage, which is wrong.

**Revised approach:** The cleanest separation is:

1. `append_audit_entry(entry_data)` stores the entry atomically with sequence_number and previous_hash, signature=None
2. After the caller signs, call a new `update_audit_signature(sequence_number, signature)` to persist the signature
3. The entry returned from `append_audit_entry` is used as the base for signing

Add `update_audit_signature` to the `StorageBackend` protocol:

```python
async def update_audit_signature(self, sequence_number: int, signature: str) -> None:
    """Set the signature on an already-appended audit entry."""
    ...
```

**Python `AuditLog.log_entry` final form:**

```python
async def log_entry(self, entry_data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    entry_for_storage = {
        "timestamp": now,
        "capability": entry_data["capability"],
        # ... all fields except sequence_number, previous_hash, signature
    }

    entry = await self._storage.append_audit_entry(entry_for_storage)

    if self._signer:
        sig = self._signer(entry)
        if inspect.isawaitable(sig):
            sig = await sig
        entry["signature"] = sig
        await self._storage.update_audit_signature(entry["sequence_number"], sig)
    else:
        entry["signature"] = None

    return entry
```

**Remove from AuditLog:**
- `self._merkle` instance variable
- `get_merkle_snapshot()` method
- The Merkle `add_leaf()` call in `log_entry`
- Import of `MerkleTree` (keep `MerkleTree` in the package — it's still used for checkpoint reconstruction)

**TypeScript** — same refactoring pattern.

**Update existing tests** to remove any assertions on `get_merkle_snapshot()` from `AuditLog`. Tests that need Merkle behavior should test checkpoint reconstruction directly (Tasks 9-10).

**Step 1:** `update_audit_signature` is already in the `StorageBackend` protocol/interface and implemented in all backends (Tasks 1-4). Verify the method exists by checking imports compile.

**Step 2:** Refactor `AuditLog.log_entry` / `logEntry` to use `append_audit_entry` + `update_audit_signature`.

**Step 3:** Remove Merkle tree from AuditLog.

**Step 4:** Update existing audit tests.

**Step 5:** Run all tests:
```bash
cd packages/python/anip-server && python -m pytest tests/ -v
cd packages/typescript && npx tsc --build server && npx vitest run --project server
```

**Step 6:** Commit.
```bash
git add packages/python/anip-server/ packages/typescript/server/
git commit -m "refactor(server): AuditLog uses append_audit_entry, remove process-local Merkle"
```

---

### Task 7: Python PostgresStorage — New Backend

**Files:**
- Create: `packages/python/anip-server/src/anip_server/postgres.py`
- Create: `packages/python/anip-server/tests/test_postgres.py`
- Modify: `packages/python/anip-server/src/anip_server/__init__.py` (export PostgresStorage)
- Modify: `packages/python/anip-server/pyproject.toml` (add asyncpg optional dependency)

**What to do:**

Create `PostgresStorage` implementing the full `StorageBackend` protocol using `asyncpg`, including all 7 new methods (`append_audit_entry`, `update_audit_signature`, `get_max_audit_sequence`, `try_acquire_exclusive`, `release_exclusive`, `try_acquire_leader`, `release_leader`).

**Key design points:**
- Uses a connection pool (`asyncpg.create_pool`)
- Schema created via `CREATE TABLE IF NOT EXISTS` on init
- `update_audit_signature`: `UPDATE audit_log SET signature = $1 WHERE sequence_number = $2`
- `append_audit_entry` uses the transactional append-head pattern:
  1. `BEGIN`
  2. `SELECT last_hash FROM audit_append_head FOR UPDATE`
  3. `INSERT INTO audit_log (...) VALUES (...) RETURNING sequence_number`
  4. `UPDATE audit_append_head SET last_sequence_number=$seq, last_hash=$hash`
  5. `COMMIT`
- `sequence_number` column is `GENERATED ALWAYS AS IDENTITY`
- Exclusive leases use `exclusive_leases` table with TTL-based acquire/release
- Leader leases use `leader_leases` table (same pattern as exclusive leases)

**Tables:**

```sql
CREATE TABLE IF NOT EXISTS delegation_tokens (
    token_id TEXT PRIMARY KEY,
    -- same columns as SQLite
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL,  -- internal PK
    sequence_number BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    timestamp TEXT NOT NULL,
    capability TEXT NOT NULL,
    -- same columns as SQLite, except sequence_number is IDENTITY
);

CREATE TABLE IF NOT EXISTS audit_append_head (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_sequence_number BIGINT NOT NULL DEFAULT 0,
    last_hash TEXT NOT NULL DEFAULT 'sha256:0'
);
-- Seed the single row:
INSERT INTO audit_append_head (id, last_sequence_number, last_hash)
VALUES (1, 0, 'sha256:0')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS checkpoints (
    -- same as SQLite
);

CREATE TABLE IF NOT EXISTS exclusive_leases (
    key TEXT PRIMARY KEY,
    holder TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS leader_leases (
    role TEXT PRIMARY KEY,
    holder TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);
```

**Class skeleton:**

```python
class PostgresStorage:
    """PostgreSQL storage backend for horizontally-scaled ANIP deployments."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Create connection pool and ensure schema exists. Must be called before use."""
        self._pool = await asyncpg.create_pool(self._dsn)
        async with self._pool.acquire() as conn:
            await self._ensure_schema(conn)

    async def close(self) -> None:
        """Close all connections."""
        if self._pool:
            await self._pool.close()
```

**Test approach:** Tests require a running Postgres instance. Use `pytest.mark.skipif` with an environment variable (`ANIP_TEST_POSTGRES_DSN`). Tests mirror `test_horizontal.py` but run against Postgres. Add a CI note that these tests are optional and require Postgres.

```python
import os
import pytest

POSTGRES_DSN = os.environ.get("ANIP_TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(POSTGRES_DSN is None, reason="ANIP_TEST_POSTGRES_DSN not set")
```

**Step 1:** Add `asyncpg` as an optional dependency in `pyproject.toml`:
```toml
[project.optional-dependencies]
postgres = ["asyncpg>=0.29"]
```

**Step 2:** Write `test_postgres.py` with skip marker.

**Step 3:** Implement `PostgresStorage`.

**Step 4:** Export from `__init__.py`.

**Step 5:** Run tests (if Postgres available):
```bash
ANIP_TEST_POSTGRES_DSN="postgresql://localhost/anip_test" python -m pytest tests/test_postgres.py -v
```

**Step 6:** Run all other tests to confirm no regressions:
```bash
cd packages/python/anip-server && python -m pytest tests/ -v
```

**Step 7:** Commit.
```bash
git add packages/python/anip-server/
git commit -m "feat(server): add Python PostgresStorage backend for horizontal scaling"
```

---

### Task 8: TypeScript PostgresStorage — New Backend

**Files:**
- Create: `packages/typescript/server/src/postgres.ts`
- Create: `packages/typescript/server/tests/postgres.test.ts`
- Modify: `packages/typescript/server/src/index.ts` (export PostgresStorage)
- Modify: `packages/typescript/server/package.json` (add pg as optional peer dependency)

**What to do:**

Mirror Task 7 for TypeScript using `pg` (node-postgres). Implements all 7 new methods including `updateAuditSignature`.

**Key differences from Python:**
- Uses `pg.Pool` for connection pooling
- `appendAuditEntry` uses the same transactional append-head pattern
- Leader leases use `leader_leases` table (same pattern as exclusive leases)
- Exclusive leases use the same `exclusive_leases` table

**Test approach:** Same as Python — skip if `ANIP_TEST_POSTGRES_DSN` env var not set.

```typescript
import { describe, it, expect, beforeAll, afterAll } from "vitest";

const POSTGRES_DSN = process.env.ANIP_TEST_POSTGRES_DSN;
const describeIf = POSTGRES_DSN ? describe : describe.skip;

describeIf("PostgresStorage", () => {
  // ...
});
```

**Step 1:** Add `pg` and `@types/pg` as optional dependencies in `package.json`.

**Step 2:** Write `postgres.test.ts`.

**Step 3:** Implement `PostgresStorage`.

**Step 4:** Export from `index.ts`.

**Step 5:** Build and run tests:
```bash
cd packages/typescript && npx tsc --build server
ANIP_TEST_POSTGRES_DSN="postgresql://localhost/anip_test" npx vitest run --project server
```

**Step 6:** Commit.
```bash
git add packages/typescript/server/
git commit -m "feat(server): add TypeScript PostgresStorage backend for horizontal scaling"
```

---

### Task 9: Python Storage-Derived Checkpoint Generation

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/checkpoint.py`
- Create: `packages/python/anip-server/tests/test_checkpoint_reconstruction.py`

**What to do:**

Add a new function `reconstruct_and_create_checkpoint` that builds a checkpoint by reading all audit entries from storage and reconstructing the Merkle tree.

```python
async def reconstruct_and_create_checkpoint(
    *,
    storage: StorageBackend,
    service_id: str,
    sign_fn: Callable[[bytes], str] | None = None,
) -> tuple[dict[str, Any], str] | None:
    """Reconstruct Merkle tree from storage and create a checkpoint.

    Returns (body, signature) or None if no new entries since last checkpoint.
    """
    max_seq = await storage.get_max_audit_sequence()
    if max_seq is None:
        return None

    checkpoints = await storage.get_checkpoints(limit=1)
    last_cp = checkpoints[-1] if checkpoints else None
    last_covered = last_cp["last_sequence"] if last_cp else 0

    if max_seq <= last_covered:
        return None  # No new entries

    # Full reconstruction from entry 1
    entries = await storage.get_audit_entries_range(1, max_seq)

    # Rebuild Merkle tree
    tree = MerkleTree()
    for entry in entries:
        tree.add_leaf(canonical_bytes(entry))

    snapshot = tree.snapshot()
    return create_checkpoint(
        merkle_snapshot=snapshot,
        service_id=service_id,
        previous_checkpoint=last_cp,
        sign_fn=sign_fn,
    )
```

Also update `CheckpointScheduler` to support async create functions (currently it calls `_create_fn()` synchronously from a thread):

The scheduler needs reworking for the leader-coordinated model. Replace the threading.Thread approach with a model that supports:
- Async create function
- Per-tick leader acquisition attempt

```python
class CheckpointScheduler:
    """Background scheduler that coordinates checkpoint generation."""

    def __init__(
        self,
        interval_seconds: int,
        create_fn: Callable[[], Awaitable[None]],
    ):
        self._interval = interval_seconds
        self._create_fn = create_fn
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self._create_fn()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # Non-fatal
```

The leader acquisition and "has new entries" check move into the `create_fn` callback (provided by the service layer in Task 13).

**Tests:**

```python
async def test_reconstruct_creates_correct_merkle_root():
    store = InMemoryStorage()
    # Manually append entries
    e1 = await store.append_audit_entry({"capability": "a", "success": True, "timestamp": "2026-01-01T00:00:00Z"})
    e2 = await store.append_audit_entry({"capability": "b", "success": True, "timestamp": "2026-01-01T00:00:01Z"})

    result = await reconstruct_and_create_checkpoint(storage=store, service_id="test-svc")
    assert result is not None
    body, sig = result
    assert body["merkle_root"].startswith("sha256:")
    assert body["entry_count"] == 2

async def test_reconstruct_returns_none_if_no_entries():
    store = InMemoryStorage()
    result = await reconstruct_and_create_checkpoint(storage=store, service_id="test-svc")
    assert result is None

async def test_reconstruct_returns_none_if_no_new_entries():
    store = InMemoryStorage()
    await store.append_audit_entry({"capability": "a", "success": True, "timestamp": "2026-01-01T00:00:00Z"})

    # Create first checkpoint
    result = await reconstruct_and_create_checkpoint(storage=store, service_id="test-svc")
    body, sig = result
    await store.store_checkpoint(body, sig)

    # No new entries — should return None
    result2 = await reconstruct_and_create_checkpoint(storage=store, service_id="test-svc")
    assert result2 is None

async def test_cumulative_root_covers_all_entries():
    store = InMemoryStorage()
    await store.append_audit_entry({"capability": "a", "success": True, "timestamp": "2026-01-01T00:00:00Z"})
    r1 = await reconstruct_and_create_checkpoint(storage=store, service_id="test-svc")
    body1, _ = r1
    await store.store_checkpoint(body1, "")

    await store.append_audit_entry({"capability": "b", "success": True, "timestamp": "2026-01-01T00:00:01Z"})
    r2 = await reconstruct_and_create_checkpoint(storage=store, service_id="test-svc")
    body2, _ = r2

    # Second checkpoint root should cover entries 1+2, not just entry 2
    assert body2["entry_count"] == 2
    assert body2["merkle_root"] != body1["merkle_root"]  # Different because more entries
```

**Step 1:** Write tests.

**Step 2:** Implement `reconstruct_and_create_checkpoint`.

**Step 3:** Refactor `CheckpointScheduler` to async.

**Step 4:** Run tests:
```bash
cd packages/python/anip-server && python -m pytest tests/ -v
```

**Step 5:** Commit.
```bash
git add packages/python/anip-server/
git commit -m "feat(server): storage-derived checkpoint reconstruction (Python)"
```

---

### Task 10: TypeScript Storage-Derived Checkpoint Generation

**Files:**
- Modify: `packages/typescript/server/src/checkpoint.ts`
- Create: `packages/typescript/server/tests/checkpoint-reconstruction.test.ts`

**What to do:**

Mirror Task 9 for TypeScript.

Add `reconstructAndCreateCheckpoint()` function. Refactor `CheckpointScheduler` to use async callback + setInterval pattern (it already uses setInterval, so the change is mainly making the callback async).

**Step 1:** Write tests.

**Step 2:** Implement `reconstructAndCreateCheckpoint`.

**Step 3:** Refactor `CheckpointScheduler`.

**Step 4:** Build and run tests:
```bash
cd packages/typescript && npx tsc --build server && npx vitest run --project server
```

**Step 5:** Commit.
```bash
git add packages/typescript/server/
git commit -m "feat(server): storage-derived checkpoint reconstruction (TypeScript)"
```

---

### Task 11: Python DelegationEngine — Storage-Backed Exclusivity

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/delegation.py` (lines 39-42 init, lines 469-502 lock methods)
- Modify: `packages/python/anip-server/tests/test_delegation.py`

**What to do:**

Replace process-local exclusivity with storage-backed leases.

**Changes to `DelegationEngine.__init__`:**
- Remove: `self._active_requests: set[str] = set()`
- Remove: `self._active_requests_lock = threading.Lock()`
- Remove: `import threading`
- The `self._storage` reference is already there

**Changes to `acquire_exclusive_lock`:**

```python
async def acquire_exclusive_lock(self, token: DelegationToken) -> ANIPFailure | None:
    if token.constraints.concurrent_branches != ConcurrentBranches.EXCLUSIVE:
        return None
    root = await self.get_root_principal(token)
    key = f"exclusive:{self._service_id}:{root}"
    holder = self._get_holder_id()
    acquired = await self._storage.try_acquire_exclusive(key, holder, self._exclusive_ttl)
    if not acquired:
        return ANIPFailure(
            type="concurrent_request_rejected",
            detail=f"concurrent_branches is exclusive and another request from {root} is in progress",
            resolution=Resolution(action="wait_and_retry", grantable_by=root),
            retry=True,
        )
    return None
```

**Changes to `release_exclusive_lock`:**

```python
async def release_exclusive_lock(self, token: DelegationToken) -> None:
    if token.constraints.concurrent_branches == ConcurrentBranches.EXCLUSIVE:
        root = await self.get_root_principal(token)
        key = f"exclusive:{self._service_id}:{root}"
        holder = self._get_holder_id()
        await self._storage.release_exclusive(key, holder)
```

**Add helper:**
```python
def _get_holder_id(self) -> str:
    import os, socket
    return f"{socket.gethostname()}:{os.getpid()}"
```

**Add configurable TTL:**
```python
def __init__(self, storage, *, service_id, exclusive_ttl: int = 60):
    self._exclusive_ttl = exclusive_ttl
```

**Tests:** Update existing delegation tests that test exclusive locking to work with the storage-backed model. The tests should still pass since InMemoryStorage now supports the lease methods.

**Step 1:** Refactor `DelegationEngine`.

**Step 2:** Update tests.

**Step 3:** Run tests:
```bash
cd packages/python/anip-server && python -m pytest tests/ -v
```

**Step 4:** Commit.
```bash
git add packages/python/anip-server/
git commit -m "feat(server): storage-backed exclusivity in Python DelegationEngine"
```

---

### Task 12: TypeScript DelegationEngine — Add Exclusivity

**Files:**
- Modify: `packages/typescript/server/src/delegation.ts`
- Create: `packages/typescript/server/tests/exclusivity.test.ts`

**What to do:**

TypeScript `DelegationEngine` currently has NO exclusivity enforcement. Add it using the same storage-backed pattern as Python (Task 11).

**Add to `DelegationEngine`:**

```typescript
private _exclusiveTtl: number;

constructor(storage: StorageBackend, opts: { serviceId: string; exclusiveTtl?: number }) {
  this._storage = storage;
  this._serviceId = opts.serviceId;
  this._exclusiveTtl = opts.exclusiveTtl ?? 60;
}

private _getHolderId(): string {
  return `${require("os").hostname()}:${process.pid}`;
}

async acquireExclusiveLock(token: DelegationToken): Promise<ANIPFailure | null> {
  if (token.constraints?.concurrent_branches !== "exclusive") return null;
  const root = await this.getRootPrincipal(token);
  const key = `exclusive:${this._serviceId}:${root}`;
  const acquired = await this._storage.tryAcquireExclusive(key, this._getHolderId(), this._exclusiveTtl);
  if (!acquired) {
    return {
      type: "concurrent_request_rejected",
      detail: `concurrent_branches is exclusive and another request from ${root} is in progress`,
      resolution: { action: "wait_and_retry", grantable_by: root },
      retry: true,
    };
  }
  return null;
}

async releaseExclusiveLock(token: DelegationToken): Promise<void> {
  if (token.constraints?.concurrent_branches !== "exclusive") return;
  const root = await this.getRootPrincipal(token);
  const key = `exclusive:${this._serviceId}:${root}`;
  await this._storage.releaseExclusive(key, this._getHolderId());
}
```

**Tests:** Write tests that verify exclusive lock acquire/release behavior using InMemoryStorage.

**Step 1:** Write `exclusivity.test.ts`.

**Step 2:** Add exclusivity methods to `DelegationEngine`.

**Step 3:** Build and run tests:
```bash
cd packages/typescript && npx tsc --build server && npx vitest run --project server
```

**Step 4:** Commit.
```bash
git add packages/typescript/server/
git commit -m "feat(server): add storage-backed exclusivity to TypeScript DelegationEngine"
```

---

### Task 13: Python Service Layer Integration

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/python/anip-service/tests/test_service_init.py`

**What to do:**

Wire the v0.10 changes into `ANIPService`:

1. **Remove `_entries_since_checkpoint`** — checkpoint decisions now come from storage state
2. **Remove `should_checkpoint()` call** from the audit log path
3. **Replace checkpoint creation** with `reconstruct_and_create_checkpoint`
4. **Add leader coordination** to checkpoint scheduler callback
5. **Add holder identity** for lease management
6. **Wire exclusivity** through the `DelegationEngine` (it already calls `acquire_exclusive_lock` / `release_exclusive_lock` — just pass the `exclusive_ttl` config through)
7. **Guard audit entry retention in cluster mode** — when using PostgresStorage, `RetentionEnforcer` must skip audit entry deletion (cumulative checkpoint rebuilds from entry 1 require full prefix). Add a `skip_audit_retention` flag to `RetentionEnforcer`:
```python
class RetentionEnforcer:
    def __init__(self, storage, *, skip_audit_retention: bool = False):
        self._skip_audit_retention = skip_audit_retention

    async def sweep(self) -> int:
        if self._skip_audit_retention:
            return 0  # Cluster mode: audit retention disabled until Merkle frontier is implemented
        now = datetime.now(timezone.utc).isoformat()
        return await self._storage.delete_expired_audit_entries(now)
```
Set `skip_audit_retention=True` when `ANIPService` detects a Postgres backend.
8. **Add exclusive lease renewal** — for long-running invocations, start a background heartbeat that renews the exclusive lease at `ttl/2` intervals:
```python
async def _run_with_exclusive_heartbeat(self, token, handler_coro):
    """Run handler with periodic lease renewal for exclusive invocations."""
    if token.constraints.concurrent_branches != ConcurrentBranches.EXCLUSIVE:
        return await handler_coro

    root = await self._delegation.get_root_principal(token)
    key = f"exclusive:{self._service_id}:{root}"
    holder = self._delegation._get_holder_id()
    interval = self._exclusive_ttl / 2

    async def renew_loop():
        while True:
            await asyncio.sleep(interval)
            await self._storage.try_acquire_exclusive(key, holder, self._exclusive_ttl)

    renewal_task = asyncio.create_task(renew_loop())
    try:
        return await handler_coro
    finally:
        renewal_task.cancel()
```

**Checkpoint scheduler callback becomes:**

```python
async def _leader_checkpoint_tick(self) -> None:
    """One tick of the checkpoint scheduler. Attempts leadership, then generates if leader."""
    holder = self._get_holder_id()
    acquired = await self._storage.try_acquire_leader("checkpoint", holder, 120)
    if not acquired:
        return  # Another replica is leader this tick

    try:
        result = await reconstruct_and_create_checkpoint(
            storage=self._storage,
            service_id=self._service_id,
            sign_fn=self._keys.sign_jws_detached_audit if self._keys else None,
        )
        if result is not None:
            body, signature = result
            await self._storage.store_checkpoint(body, signature)
            for sink in self._sinks:
                sink.publish({"body": body, "signature": signature})
    finally:
        await self._storage.release_leader("checkpoint", holder)
```

**`_create_and_publish_checkpoint` is replaced** by the leader-coordinated tick above.

**`start()` changes:**
- `CheckpointScheduler` is instantiated with the async `_leader_checkpoint_tick` callback
- The scheduler runs on all replicas — leadership is per-tick

**Service init changes:**
- Add `exclusive_ttl` parameter (default 60)
- Pass to `DelegationEngine`
- Add `_get_holder_id()` helper

**Add `storage` parameter for Postgres:**
- Currently `storage` accepts `":memory:"` or `"sqlite:///path"`. Add support for `"postgres://..."` DSN strings.
- `PostgresStorage` is in `anip-server` (not `anip-service`), so import from `anip_server.postgres`:
```python
if isinstance(storage, str):
    if storage == ":memory:":
        self._storage = InMemoryStorage()
    elif storage.startswith("postgres"):
        from anip_server.postgres import PostgresStorage
        self._storage = PostgresStorage(storage)
    else:
        self._storage = SQLiteStorage(storage.replace("sqlite:///", ""))
```

**Make `start()` async** to handle `PostgresStorage.initialize()`:
- The current `start()` is sync but already calls `asyncio.get_event_loop().create_task()`, which assumes a running event loop. Making it async is the natural evolution.
- FastAPI's `on_startup` accepts both sync and async callables, so `app.router.on_startup.append(service.start)` works unchanged.
- `PostgresStorage.initialize()` (creates connection pool, ensures schema) is awaited at the top of `start()`:
```python
async def start(self) -> None:
    """Start background services. Must be called within a running event loop."""
    if hasattr(self._storage, 'initialize'):
        await self._storage.initialize()
    if self._scheduler:
        self._scheduler.start()
    self._retention_enforcer.start()
    # ... aggregator flush task setup (unchanged)
```
- Do NOT use `run_until_complete()` — it's unsafe under an already-running ASGI event loop.

**Tests:** Update service tests that reference `_entries_since_checkpoint` or `get_merkle_snapshot`.

**Step 1:** Refactor service layer checkpoint path.

**Step 2:** Remove `_entries_since_checkpoint`.

**Step 3:** Wire leader-coordinated checkpoint scheduler.

**Step 4:** Add Postgres storage detection.

**Step 5:** Update tests.

**Step 6:** Run tests:
```bash
cd packages/python/anip-service && python -m pytest tests/ -v
```

**Step 7:** Also run server tests to confirm no regressions:
```bash
cd packages/python/anip-server && python -m pytest tests/ -v
```

**Step 8:** Commit.
```bash
git add packages/python/anip-service/ packages/python/anip-server/
git commit -m "feat(service): wire v0.10 horizontal scaling into Python service layer"
```

---

### Task 14: TypeScript Service Layer Integration

**Files:**
- Modify: `packages/typescript/service/src/service.ts`
- Modify: `packages/typescript/service/tests/service.test.ts`

**What to do:**

Mirror Task 13 for TypeScript. Same changes:

1. Remove `entriesSinceCheckpoint` counter
2. Replace `createAndPublishCheckpoint` with leader-coordinated tick using `reconstructAndCreateCheckpoint`
3. Wire storage-backed exclusivity through `DelegationEngine`
4. Add Postgres storage detection. `PostgresStorage` is in `@anip/server` (Task 8 exports it), not in the service package:
```typescript
if (typeof storageOpt === "string" && storageOpt.startsWith("postgres")) {
  const { PostgresStorage } = await import("@anip/server");
  const pgStorage = new PostgresStorage(storageOpt);
  await pgStorage.initialize();
  // use pgStorage as the storage backend
}
```
5. **Guard audit entry retention in cluster mode** — same as Python Task 13: add `skipAuditRetention` option to retention enforcer, set `true` when Postgres backend detected
6. **Add exclusive lease renewal** — same heartbeat pattern as Python: `setInterval` at `ttl/2` that re-acquires the lease, cleared when handler completes:
```typescript
async function runWithExclusiveHeartbeat(
  storage: StorageBackend, key: string, holder: string, ttl: number,
  handler: () => Promise<unknown>
) {
  const interval = setInterval(async () => {
    await storage.tryAcquireExclusive(key, holder, ttl);
  }, (ttl / 2) * 1000);
  try {
    return await handler();
  } finally {
    clearInterval(interval);
  }
}
```
7. Update tests

**Step 1-6:** Same structure as Task 13.

**Step 7:** Build and run tests:
```bash
cd packages/typescript && npx tsc --build service && npx vitest run --project service
```

**Step 8:** Commit.
```bash
git add packages/typescript/service/ packages/typescript/server/
git commit -m "feat(service): wire v0.10 horizontal scaling into TypeScript service layer"
```

---

### Task 15: Framework Bindings Lifecycle Updates

**Files:**
- Modify: `packages/python/anip-fastapi/src/anip_fastapi/routes.py`
- Modify: `packages/typescript/hono/src/routes.ts`
- Modify: `packages/typescript/express/src/routes.ts`
- Modify: `packages/typescript/fastify/src/routes.ts`

**What to do:**

If `start()` now needs async initialization (for Postgres), the framework bindings need to handle this.

Check each binding's `on_startup` / lifecycle hook and ensure it calls `start()` correctly. The main change is ensuring `start()` can handle async storage initialization.

For Python (FastAPI):
- FastAPI's `on_startup` already supports async handlers, so `service.start()` can be made async if needed, or the binding can call `await service.initialize_storage()` before `service.start()`.

For TypeScript (Hono/Express/Fastify):
- The mount functions return `{ shutdown, stop }`. If `start()` becomes async, the bindings need to await it during setup.

This task is narrow — just ensure the lifecycle wiring is compatible with async storage init.

**Step 1:** Check each binding's startup path.

**Step 2:** Add async init support if needed.

**Step 3:** Run framework-specific tests if they exist:
```bash
cd packages/python/anip-fastapi && python -m pytest tests/ -v 2>/dev/null || echo "No tests"
cd packages/typescript && npx vitest run 2>/dev/null || echo "Check individual packages"
```

**Step 4:** Commit.
```bash
git add packages/python/anip-fastapi/ packages/typescript/hono/ packages/typescript/express/ packages/typescript/fastify/
git commit -m "feat(bindings): update lifecycle hooks for async storage initialization"
```

---

### Task 16: Deployment Guide

**Files:**
- Create: `docs/deployment-guide.md`
- Modify: `SPEC.md` (add one-line reference to deployment guide)

**What to do:**

Write `docs/deployment-guide.md` covering:

1. **Two deployment models:**
   - Single-instance (SQLite, all-in-one)
   - Cluster (Postgres, stateless replicas)

2. **Cluster architecture diagram** (ASCII art from design doc)

3. **Configuration:**
   - `storage: "postgres://..."` vs `storage: "sqlite:///..."`
   - Exclusive lease TTL configuration
   - Checkpoint interval configuration

4. **Signing key distribution:**
   - All replicas need the same key
   - Options: mounted Kubernetes secret, KMS
   - Shared signer service is out of scope for v0.10

5. **Background job strategies:**
   - Checkpoint scheduler: leader-coordinated (automatic via leader lease)
   - Retention enforcer: runs on all replicas (idempotent); **audit entry retention disabled in cluster mode** (requires Merkle frontier, deferred)
   - Aggregator flush: per-replica (explicitly not cluster-global)

6. **Monitoring guidance:**
   - Checkpoint leader identity (leader_leases table)
   - Exclusive lease table state
   - Audit append head progression

7. **Graceful shutdown:**
   - Release leader leases
   - Release exclusive leases
   - Flush aggregator buffer

Add a one-line note in SPEC.md pointing to the deployment guide.

**Step 1:** Write `docs/deployment-guide.md`.

**Step 2:** Add reference in SPEC.md.

**Step 3:** Commit.
```bash
git add docs/deployment-guide.md SPEC.md
git commit -m "docs: add horizontal-scaling deployment guide"
```

---

### Task 17: SPEC.md + Schema + Version Bumps

**Files:**
- Modify: `SPEC.md` (version bump to v0.10, add §6.11 Horizontal Scaling)
- Modify: `schema/anip.schema.json` (version bump)
- Modify: `schema/discovery.schema.json` (version bump)
- Modify: `packages/python/anip-core/src/anip_core/constants.py` (PROTOCOL_VERSION, MANIFEST_VERSION)
- Modify: `packages/typescript/core/src/constants.ts` (PROTOCOL_VERSION, MANIFEST_VERSION)

**What to do:**

1. **SPEC.md:** Bump version to v0.10. Add §6.11 "Horizontal Scaling" covering:
   - Storage-atomic audit append
   - Storage-derived checkpoint generation
   - Distributed exclusivity
   - Background job coordination categories
   - Recommended deployment architecture (brief, points to deployment guide)

2. **Schema:** Bump `version` field in both schema files from `"0.9.0"` to `"0.10.0"`.

3. **Constants:** Update `PROTOCOL_VERSION` to `"anip/0.10"` and `MANIFEST_VERSION` to `"0.10.0"` in both runtimes.

**Step 1:** Update SPEC.md.

**Step 2:** Update schema versions.

**Step 3:** Update constants.

**Step 4:** Run tests to confirm version changes don't break anything:
```bash
cd packages/python/anip-server && python -m pytest tests/ -v
cd packages/python/anip-service && python -m pytest tests/ -v
cd packages/typescript && npx tsc --build && npx vitest run
```

**Step 5:** Commit.
```bash
git add SPEC.md schema/ packages/python/anip-core/ packages/typescript/core/
git commit -m "feat: bump ANIP to v0.10, add horizontal scaling spec section"
```

---

### Task 18: README Updates

**Files:**
- Modify: `README.md`
- Modify: `schema/README.md`

**What to do:**

1. **README.md:**
   - Update Status section from v0.9 to v0.10
   - Update the v0.9 callout to v0.10 (horizontal scaling readiness)
   - Update Spec reference from v0.9 to v0.10
   - Add deployment guide to "What exists today" list
   - Add PostgresStorage mention to SDK packages list

2. **schema/README.md:**
   - Update version reference from v0.9 to v0.10

**Step 1:** Update README.md.

**Step 2:** Update schema/README.md.

**Step 3:** Run a final full test suite:
```bash
cd packages/python/anip-server && python -m pytest tests/ -v
cd packages/python/anip-service && python -m pytest tests/ -v
cd packages/typescript && npx tsc --build && npx vitest run
```

**Step 4:** Commit.
```bash
git add README.md schema/README.md
git commit -m "docs: update READMEs for v0.10"
```
