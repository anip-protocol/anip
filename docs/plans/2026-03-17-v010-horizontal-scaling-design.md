# ANIP v0.10: Horizontal Scaling Readiness — Design

**Goal:** Make ANIP's audit and trust guarantees remain correct when one logical service runs across multiple replicas with shared storage.

**Scope:** Full scope, tiered depth:
- **Tier 1 (deep implementation):** storage-atomic audit append, storage-derived checkpoint generation
- **Tier 2 (required but narrower):** distributed exclusivity, cluster-safe background job coordination
- **Tier 3 (documentation):** shared-backend deployment guidance

**Framing:** The protocol is already horizontally scalable. The reference runtimes are not yet cluster-safe. v0.10 fixes the runtimes.

---

## 1. StorageBackend Contract Refactor

### Problem

The current `StorageBackend` contract exposes `store_audit_entry()` where the caller (the `AuditLog` class) owns sequence allocation:

```
last = storage.get_last_audit_entry()
sequence_number = last.sequence_number + 1
previous_hash = compute_hash(last)
store_audit_entry(entry_with_sequence_and_hash)
```

This is race-prone across replicas. Two replicas reading the same `last` will both assign the same `sequence_number`.

### Solution

Shift sequencing and hash-chain responsibility into the storage layer.

### New contract methods

```
# Atomic audit append — storage owns sequence allocation and hash chain
append_audit_entry(entry_data) -> complete_entry
  # Entry arrives WITHOUT sequence_number or previous_hash
  # Storage assigns both atomically
  # Returns the fully populated entry

# Distributed exclusivity (lease-style)
try_acquire_exclusive(key: str, holder: str, ttl_seconds: int) -> bool
release_exclusive(key: str, holder: str) -> void

# Leader coordination for background jobs
try_acquire_leader(role: str, holder: str, ttl_seconds: int) -> bool
release_leader(role: str, holder: str) -> void

# Checkpoint support
get_max_audit_sequence() -> int | None
```

### AuditLog changes

- `log_entry()` stops doing `get_last_audit_entry()` + increment. Calls `append_audit_entry()` and receives the complete entry back.
- Process-local `MerkleTree` instance is removed from `AuditLog`. Merkle accumulation is no longer part of the append hot path — it moves to checkpoint generation (Section 2).
- `get_merkle_snapshot()` is removed from the checkpointing path.

### PostgresStorage implementation (new)

**Audit append:**
- `sequence_number` allocated by Postgres `GENERATED ALWAYS AS IDENTITY` — DB-guaranteed unique monotonic, no application-side `MAX()+1`.
- `previous_hash` maintained via a single-row `audit_append_head` table: `(last_sequence_number, last_hash)`.
- Transaction flow:
  1. `SELECT last_hash FROM audit_append_head FOR UPDATE` — locks the append head (held for microseconds, not the full invocation)
  2. `INSERT INTO audit_log (...) VALUES (...)` — sequence from identity column
  3. `UPDATE audit_append_head SET last_sequence_number = $seq, last_hash = $hash`
  4. `COMMIT`
- The `FOR UPDATE` on `audit_append_head` is a short-lived serialization point for append ordering. It does not hold a lock across the invocation.

**Important:** The canonical append order is the `audit_append_head` transaction order. The identity column provides uniqueness and monotonicity; the append-head transaction ties `sequence_number` and `previous_hash` together.

**Exclusivity:**
- `exclusive_leases` table: `(key TEXT PRIMARY KEY, holder TEXT, expires_at TIMESTAMPTZ)`
- Acquire: `INSERT ... ON CONFLICT (key) DO UPDATE SET holder=$holder, expires_at=now()+$ttl WHERE exclusive_leases.expires_at < now() OR exclusive_leases.holder = $holder` — returns affected rows to determine success
- Release: `DELETE WHERE key=$key AND holder=$holder`
- Crash recovery: expired leases are naturally reclaimable by any replica

**Leader coordination:**
- `pg_try_advisory_lock(role_hash)` — session-scoped, held for the lifetime of the checkpoint worker's connection
- Requires a dedicated connection for the leader role, not a pooled connection, so request traffic cannot accidentally release it

### SQLiteStorage implementation (updated)

- `append_audit_entry`: `INSERT` with `MAX(sequence_number) + 1` in a single statement — safe for single-process
- Exclusivity: in-memory `dict[str, (holder, expires)]` behind the new interface — current behavior, fine for dev/single-instance
- Leader: no-op, always returns true — single process is always leader
- `get_max_audit_sequence`: `SELECT MAX(sequence_number) FROM audit_log`

---

## 2. Storage-Derived Checkpoint Generation

### Problem

Each `AuditLog` instance keeps a process-local `MerkleTree` with an in-memory `_leaves[]` array. Checkpoints snapshot this local state. Multiple replicas produce divergent checkpoint roots.

### Solution

Checkpoint generation reconstructs the full cumulative Merkle tree from shared storage. One replica holds an advisory lock and does the work.

### Correctness model

ANIP checkpoint roots are cumulative — the root covers entries 1..N, not just new entries since the last checkpoint. Reconstructing from only `last_covered+1..current_max` would produce a delta root, breaking checkpoint continuity.

v0.10 takes the simple/correct approach: always rebuild from entry 1.

### Checkpoint generation flow

1. Checkpoint scheduler wakes on timer interval (runs on all replicas)
2. Calls `try_acquire_leader("checkpoint", holder, ttl)` — if false, skip this tick
3. If acquired, queries storage: `get_max_audit_sequence()` → `current_max`
4. Queries storage: `get_last_checkpoint()` → last checkpoint's `last_sequence_number`
5. If `current_max == last_covered`, release and skip — no new entries
6. Rebuilds full Merkle tree: `get_audit_entries_range(1, current_max)`
7. Computes `canonical_bytes` → `leaf_hash` for each entry in canonical order
8. Builds `CheckpointBody` with the cumulative Merkle root, signs, stores, publishes to sinks
9. Releases leadership (or lets advisory lock persist for next tick)

### Service layer changes

- `_entries_since_checkpoint` counter is removed — checkpoint decisions are based on storage state
- `CheckpointScheduler` callback changes to: query storage → full reconstruction → publish
- All replicas run the scheduler loop; each tick attempts leadership; only the current leader executes
- If the leader dies, the next tick on another replica acquires leadership naturally

### Proof generation

- Inclusion/consistency proofs reconstruct the full tree for the checkpoint's covered range (1..`last_sequence_number`)
- Same `MerkleTree` class, fed from storage entries instead of process-local memory
- Consistent with checkpoint generation — both derive from the same canonical storage order

### Cost and future optimization

- Full reconstruction reads all entries from storage each cycle
- Bounded in practice: for early adoption, audit logs in the thousands to low tens of thousands are well within a single indexed query
- **Deferred to post-v0.10:** Store Merkle frontier state with each checkpoint, enabling incremental reconstruction from `prior_frontier + new_entries`. v0.10 explicitly does not do this — correctness first.

---

## 3. Distributed Exclusivity

### Problem

`concurrent_branches=exclusive` enforcement is Python-only, backed by `threading.Lock` + `set[str]` in `DelegationEngine`. TypeScript has no equivalent. Both are process-local.

### Solution

Move exclusivity enforcement to the storage backend via the lease-based contract from Section 1. TypeScript gains exclusivity for the first time.

### Key format

`exclusive:{service_id}:{root_principal}`

### Holder identity

Replica identifier, e.g. `{hostname}:{pid}` — unique per process.

### TTL and renewal

- TTL is configurable (default conservative, e.g. 60s)
- For long-running invocations, the service layer heartbeats/renews the lease at `ttl/2` intervals during execution
- If a replica crashes, the lease expires naturally and another replica can acquire it

### Python changes

- `DelegationEngine.__init__` drops `_active_requests: set[str]` and `_active_requests_lock`
- `acquire_exclusive_lock` calls `self._storage.try_acquire_exclusive(key, holder, ttl)`
- `release_exclusive_lock` calls `self._storage.release_exclusive(key, holder)`
- Both methods are already async — the change is internal

### TypeScript changes

- `DelegationEngine` gains `acquireExclusiveLock()` and `releaseExclusiveLock()` — these don't exist today
- TypeScript gets exclusivity enforcement for the first time, with the same semantics as Python

### Postgres implementation

- Lease table approach (described in Section 1)
- No long-lived DB transaction held across the handler — acquire and release are separate, short operations

### SQLite implementation

- In-memory `dict[str, (holder, expires)]` — same single-process semantics as today, behind the new interface

---

## 4. Cluster-Safe Background Jobs

### Problem

Checkpoint scheduler, retention enforcer, and aggregator flush are all process-local timers. In a replicated deployment, some of these need coordination.

### Solution

No general-purpose cluster job framework. Each job gets its natural strategy:

| Job | Strategy | Coordination | Reason |
|-----|----------|-------------|--------|
| Checkpoint scheduler | Leader-coordinated | `try_acquire_leader` per tick | Duplicate checkpoint publication matters |
| Retention enforcer | Idempotent | None | `DELETE WHERE expires_at < now()` is safe from any replica |
| Aggregator flush | Per-replica | None | Flushes local in-memory buffer only |

### Checkpoint scheduler

- All replicas run the scheduler loop
- Each tick: attempt `try_acquire_leader("checkpoint", holder, ttl)`
- If acquired: run checkpoint generation (Section 2)
- If not acquired: no-op for this tick
- Leadership is per-tick, not per-startup — clean failover

### Retention enforcer

- Runs on all replicas — safe because `DELETE WHERE expires_at < now()` is idempotent
- Multiple replicas executing the same sweep is harmless — no coordination needed
- Document this explicitly as an intentionally concurrent job

### Aggregator flush

- Remains per-replica — each replica flushes its own in-memory aggregation buffer
- **Important: aggregation semantics are per-replica, not cluster-global.** Multiple replicas each maintain independent aggregation windows. This is acceptable for v0.10 but must be stated clearly so nobody assumes replicas contribute to one shared aggregation window.

---

## 5. Deployment Guidance

### Location

Standalone `docs/deployment-guide.md`. SPEC.md carries only a concise note pointing to it.

### Two deployment models

**Single-instance** (development, small deployments):
- SQLite storage backend
- All jobs run in-process
- Exclusivity is in-memory
- Current behavior, unchanged

**Cluster** (production, horizontal scaling):
- Postgres storage backend
- Stateless API replicas behind a load balancer
- Checkpoint leadership via advisory lock (automatic, per-tick)
- Retention runs on all replicas (idempotent)
- Aggregation is per-replica

### Cluster architecture

```
                    ┌─→ Replica 1 (API + retention + aggregator)
                    │
Load Balancer ──────┼─→ Replica 2 (API + retention + aggregator + checkpoint leader*)
                    │
                    └─→ Replica N (API + retention + aggregator)

                    * Advisory lock determines leader per tick; any replica can take over

Shared: PostgreSQL (audit, tokens, checkpoints, leases, append head)
Shared: Signing key material (mounted secret or KMS)
```

### Signing key distribution

All replicas need the same signing key for manifest signing and checkpoint signing. The deployment guide must cover:
- Mounted secret (Kubernetes secret volume)
- KMS / shared signer service
- This is operational, not protocol — but essential for correctness

### Monitoring guidance

- Which replica holds the checkpoint advisory lock
- Lease table state for exclusivity
- Audit append head progression

### Graceful shutdown

- Release advisory locks
- Release exclusive leases
- Flush aggregator buffer (existing `shutdown()` path)

---

## Package Impact

### Must-update packages

| Package | Changes |
|---------|---------|
| `anip-server` (Python) | `StorageBackend` contract refactor, `PostgresStorage` implementation, `AuditLog` changes (remove process-local Merkle), checkpoint reconstruction, exclusivity moved to storage |
| `@anip/server` (TypeScript) | Same as Python: contract refactor, `PostgresStorage`, `AuditLog` changes, checkpoint reconstruction, exclusivity added |
| `anip-service` (Python) | Service layer integration: remove `_entries_since_checkpoint`, wire new checkpoint flow, lease renewal for exclusivity, per-tick leader acquisition |
| `@anip/service` (TypeScript) | Same as Python service layer |

### Likely-update packages

| Package | Changes |
|---------|---------|
| `anip-core` / `@anip/core` | Minimal — only if discovery/manifest exposes deployment posture |
| `anip-fastapi` | Lifecycle wiring if service startup changes |
| `@anip/hono`, `@anip/express`, `@anip/fastify` | Same lifecycle wiring |

### No major changes expected

- `anip-crypto` / `@anip/crypto` — unless signing moves behind a shared signer abstraction (out of scope for v0.10)

---

## What v0.10 Explicitly Defers

- Merkle frontier state / incremental checkpoint reconstruction
- Cluster-global aggregation (aggregation stays per-replica)
- General-purpose distributed job framework
- Multi-region consensus
- Federation / cross-service delegation
- Shared signer service abstraction
