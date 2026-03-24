# ANIP Deployment Guide

This guide covers deploying ANIP services in single-instance and cluster configurations. It applies to the Python, TypeScript, Go, Java, and C# reference runtimes starting from v0.11.

---

## Deployment Models

ANIP supports two deployment models. The protocol guarantees (audit integrity, delegation chain verification, checkpoint consistency) hold in both models. The difference is operational: single-instance uses local storage and in-process coordination; cluster uses shared storage and lease-based coordination.

### Single-Instance

One process runs the ANIP service with SQLite or in-memory storage. All background jobs (checkpoint scheduling, retention enforcement, aggregation) run in-process. Exclusive invocation locks are held in memory.

This is the default mode and requires no additional infrastructure.

**When to use:** development, testing, low-traffic production deployments where a single process is sufficient.

### Cluster

Multiple stateless replicas run behind a load balancer, sharing a PostgreSQL database. Coordination happens through lease tables in Postgres. Any replica can handle any request. Leadership for checkpoint generation is elected per-tick via the leader lease.

**When to use:** production deployments requiring horizontal scaling, high availability, or zero-downtime deploys.

---

## Cluster Architecture

```
                    +---> Replica 1 (API + retention + aggregator)
                    |
Load Balancer ------+---> Replica 2 (API + retention + aggregator + checkpoint leader*)
                    |
                    +---> Replica N (API + retention + aggregator)

                    * Leader is elected per checkpoint tick via lease table.
                      Any replica can become leader if the current one fails.

Shared: PostgreSQL (audit log, tokens, checkpoints, leases, append head)
Shared: Signing key material (mounted secret or KMS)
```

Replicas are stateless with respect to audit data and coordination. Each replica maintains only a local aggregation buffer (see Background Jobs below). Adding or removing replicas requires no cluster-wide reconfiguration.

---

## Configuration

### Storage

The `storage` parameter on `ANIPService` (Python/Java) or `createANIPService` (TypeScript) selects the backend.

**Python:**

```python
# Single-instance — SQLite
ANIPService(service_id="my-service", storage="sqlite:///anip.db", ...)

# Single-instance — in-memory (testing)
ANIPService(service_id="my-service", storage=":memory:", ...)

# Cluster — PostgreSQL
ANIPService(service_id="my-service", storage="postgres://user:pass@host:5432/anip", ...)
```

**TypeScript:**

```typescript
// Single-instance — SQLite
createANIPService({ serviceId: "my-service", storage: { type: "sqlite", path: "anip.db" }, ... })

// Single-instance — in-memory (testing)
createANIPService({ serviceId: "my-service", storage: { type: "memory" }, ... })

// Cluster — PostgreSQL
createANIPService({ serviceId: "my-service", storage: "postgres://user:pass@host:5432/anip", ... })
```

**Java (Spring Boot):**

```java
// Single-instance — SQLite
new ANIPService(new ServiceConfig()
    .setServiceId("my-service")
    .setStorage("sqlite:///anip.db")
    ...);

// Single-instance — in-memory (testing)
new ANIPService(new ServiceConfig()
    .setServiceId("my-service")
    .setStorage(":memory:")
    ...);

// Cluster — PostgreSQL
new ANIPService(new ServiceConfig()
    .setServiceId("my-service")
    .setStorage("postgres://user:pass@host:5432/anip")
    ...);
```

**C# (ASP.NET Core):**

```csharp
// Single-instance — SQLite
new AnipService(new ServiceConfig { ServiceId = "my-service", Storage = "sqlite:///anip.db" });

// Single-instance — in-memory (testing)
new AnipService(new ServiceConfig { ServiceId = "my-service", Storage = ":memory:" });

// Cluster — PostgreSQL
new AnipService(new ServiceConfig { ServiceId = "my-service", Storage = "postgres://user:pass@host:5432/anip" });
```

The PostgreSQL backend (`PostgresStorage`) creates all required tables on first connection: `audit_log`, `audit_append_head`, `tokens`, `checkpoints`, `exclusive_leases`, `leader_leases`, and related indexes.

### Exclusive Lease TTL

The `exclusive_ttl` parameter (Python) controls how long an exclusive invocation lease is held before it expires. The default is 60 seconds. For long-running handlers, the runtime automatically renews the lease at `ttl/2` intervals.

```python
ANIPService(service_id="my-service", storage="postgres://...", exclusive_ttl=120, ...)
```

If a replica crashes mid-invocation, the lease expires naturally after the TTL, allowing another replica to accept invocations for the same principal.

### Checkpoint Interval

Checkpoint scheduling is configured via `CheckpointPolicy`. The `interval_seconds` field controls how often the checkpoint scheduler ticks. In cluster mode, each tick attempts leader election; only the leader generates a checkpoint.

```python
ANIPService(
    service_id="my-service",
    storage="postgres://...",
    trust="anchored",
    checkpoint_policy=CheckpointPolicy(interval_seconds=60),
    ...
)
```

Shorter intervals mean more frequent checkpoints and faster detection of audit tampering. Longer intervals reduce database load. The default depends on your anchoring policy's `max_lag` setting.

---

## Signing Key Distribution

All replicas must use the same signing key material. The `key_path` parameter points to a directory containing the service's private key (used for manifest signing, token signing, and audit checkpoint signing).

### Options

**Mounted Kubernetes secret (recommended for Kubernetes deployments):**

Mount a Secret as a volume at the `key_path` location. All replicas in the Deployment share the same Secret, so all replicas sign with the same key.

```yaml
# Kubernetes Deployment snippet
volumes:
  - name: anip-keys
    secret:
      secretName: anip-signing-key
containers:
  - name: anip
    volumeMounts:
      - name: anip-keys
        mountPath: /etc/anip-keys
        readOnly: true
    env:
      - name: ANIP_KEY_PATH
        value: /etc/anip-keys
```

**KMS-backed key management:**

For environments using AWS KMS, GCP Cloud KMS, or HashiCorp Vault, you can provide a custom `StorageBackend` or `KeyManager` that delegates signing to the KMS. The key material never leaves the KMS boundary.

**Shared signer service:**

A dedicated signing service that all replicas call for cryptographic operations. This is out of scope for v0.10 but is a natural extension for high-security deployments.

### Key Rotation

When rotating keys, deploy the new key material to all replicas before any replica begins using it. A rolling deploy that updates one replica at a time will produce a window where different replicas sign with different keys. Coordinate key rotation as a single atomic configuration change (e.g., update the Kubernetes Secret, then trigger a rolling restart).

---

## Background Jobs

ANIP runs three background jobs. Each has a different coordination strategy in cluster mode.

### Checkpoint Scheduler

**Strategy:** Leader-coordinated (automatic via leader lease).

All replicas run the checkpoint scheduler loop. On each tick, the scheduler calls `try_acquire_leader("checkpoint", holder, ttl)`. If the replica wins the lease, it generates a checkpoint by reconstructing the full Merkle tree from storage (entries 1 through the current maximum sequence number). If it loses, it skips the tick.

Leadership is per-tick, not per-startup. If the current leader crashes or is removed, another replica acquires the lease on its next tick. No manual intervention is required.

The leader lease TTL defaults to 120 seconds and is renewed at `ttl/2` intervals during checkpoint generation.

### Retention Enforcer

**Strategy:** Runs on all replicas (idempotent). No coordination required.

The retention enforcer periodically deletes expired tokens and (in single-instance mode) expired audit entries. The `DELETE WHERE expires_at < now()` operation is idempotent -- multiple replicas executing the same sweep simultaneously is harmless.

**Cluster constraint:** In cluster deployments, audit entry retention is disabled. Because v0.10 always rebuilds the full Merkle tree from entry 1, deleting audit entries would break checkpoint generation. Token and other non-audit data retention continues to operate normally. This limitation will be lifted in a future version that stores Merkle frontier state with each checkpoint, enabling incremental reconstruction.

### Aggregator Flush

**Strategy:** Per-replica (not cluster-global). No coordination required.

Each replica maintains its own in-memory aggregation buffer for low-value events (e.g., `malformed_or_spam` denials). The aggregator flushes closed windows to the audit log on a timer. Each replica's flush is independent.

This means aggregation counts are per-replica, not cluster-wide. If three replicas each see 10 spam requests in a window, the audit log will contain three separate aggregated entries (one per replica) rather than one entry with count 30. This is acceptable for v0.10 and is documented as a known limitation.

---

## Observability

v0.11 adds callback-based observability hooks and a pull-based health API. All hooks are optional — omitting them has near-zero overhead (conditional checks only, no object construction).

### Configuring Hooks

Pass a `hooks` object when creating the service. Each section (logging, metrics, tracing, diagnostics) is independently optional.

**Python:**

```python
from anip_service import ANIPService, ANIPHooks, LoggingHooks, MetricsHooks

ANIPService(
    service_id="my-service",
    storage="postgres://...",
    hooks=ANIPHooks(
        logging=LoggingHooks(
            on_invocation_start=lambda e: logger.info("invoke", extra=e),
            on_invocation_end=lambda e: logger.info("invoke_end", extra=e),
        ),
        metrics=MetricsHooks(
            on_invocation_duration=lambda e: histogram.observe(e["duration_ms"]),
            on_checkpoint_created=lambda e: gauge.set(e["lag_seconds"]),
        ),
    ),
    ...
)
```

**TypeScript:**

```typescript
createANIPService({
  serviceId: "my-service",
  storage: "postgres://...",
  hooks: {
    logging: {
      onInvocationStart: (e) => logger.info("invoke", e),
      onInvocationEnd: (e) => logger.info("invoke_end", e),
    },
    metrics: {
      onInvocationDuration: (e) => histogram.observe(e.durationMs),
      onCheckpointCreated: (e) => gauge.set(e.lagSeconds),
    },
  },
  ...
});
```

**Java (Spring Boot):**

```java
new ANIPService(new ServiceConfig()
    .setServiceId("my-service")
    .setStorage("postgres://...")
    .setHooks(new ANIPHooks()
        .setOnInvocationStart(e -> logger.info("invoke {}", e))
        .setOnInvocationEnd(e -> logger.info("invoke_end {}", e))
        .setOnInvocationDuration(e -> histogram.observe(e.get("duration_ms")))
        .setOnCheckpointCreated(e -> gauge.set(e.get("lag_seconds")))
    )
    ...);
```

**Hook isolation guarantee:** All hook invocations are wrapped in try/catch. A throwing hook never affects service correctness — no request fails, no background job stops, no audit entry is lost because a hook threw.

### Health Endpoint

Framework bindings (FastAPI, Hono, Express, Fastify, Spring Boot, Quarkus, ASP.NET Core) can expose `GET /-/health`, which returns the output of `service.getHealth()`. It is **disabled by default**.

**Python (FastAPI):**

```python
app = create_anip_app(service, health_endpoint=True)
```

**TypeScript (Hono):**

```typescript
const app = createANIPApp(service, { healthEndpoint: true });
```

The response is a JSON `HealthReport` with `status` (`"healthy"`, `"degraded"`, `"unhealthy"`) and subsystem details for storage, checkpoint, retention, and aggregation.

**Security note:** This endpoint exposes runtime and storage state. If enabled, place it behind authentication or restrict it to internal networks.

### Programmatic Health Checks

Call `service.getHealth()` / `service.get_health()` directly for readiness probes or custom monitoring:

```python
health = service.get_health()
if health["status"] == "unhealthy":
    alert(health)
```

The health report is a cached snapshot of last-known runtime state, not a live connectivity probe. Background workers update their status as a side effect of normal ticks.

---

## Monitoring

### Checkpoint Leader Identity

Query the `leader_leases` table to determine which replica currently holds the checkpoint leader lease:

```sql
SELECT role, holder, expires_at
FROM leader_leases
WHERE role = 'checkpoint' AND expires_at > now();
```

If no row is returned or the lease is expired, no replica is currently leading. The next checkpoint tick on any replica will acquire the lease.

### Exclusive Lease State

Query the `exclusive_leases` table to see active exclusive invocation locks:

```sql
SELECT key, holder, expires_at
FROM exclusive_leases
WHERE expires_at > now();
```

The `key` column follows the format `exclusive:{service_id}:{root_principal}`. A large number of active leases may indicate long-running handlers or stuck invocations.

### Audit Append Head Progression

The `audit_append_head` table tracks the latest audit entry:

```sql
SELECT last_sequence_number, last_hash
FROM audit_append_head;
```

Monitor `last_sequence_number` over time to verify that audit entries are being appended. A stalled sequence number with active traffic indicates a problem with audit logging.

### Health Check Indicators

- **`getHealth()` / `get_health()`:** The preferred way to check runtime health. Returns a cached `HealthReport` with subsystem status for storage, checkpoint, retention, and aggregation. Wire this to Kubernetes readiness probes or monitoring dashboards. See [Observability](#observability) above.
- **Checkpoint freshness:** Compare the latest checkpoint's `last_sequence_number` against the current `audit_append_head`. A growing gap suggests the checkpoint scheduler is not running or cannot acquire leadership. The `checkpoint.lagSeconds` field in the health report tracks this automatically.
- **Lease expiry backlog:** Expired rows in `exclusive_leases` that are not being reclaimed suggest replicas are not processing requests for the affected principals.
- **Replica count:** The number of distinct `holder` values appearing in recent lease acquisitions indicates how many replicas are actively participating.

---

## Graceful Shutdown

When stopping a replica, the runtime's `shutdown()` method performs three steps in order:

1. **Release leader leases.** If this replica holds the checkpoint leader lease, it is released so another replica can take over immediately rather than waiting for TTL expiry.

2. **Release exclusive leases.** Any active exclusive invocation leases held by this replica are released. Without this, other replicas would have to wait for the TTL to expire before accepting invocations for the affected principals.

3. **Flush aggregator buffer.** Any pending aggregated events in the local buffer are flushed to the audit log. Without this, events in open aggregation windows would be lost.

### Framework Integration

The ANIP framework bindings (FastAPI, Hono, Express, Fastify, Spring Boot, Quarkus, ASP.NET Core) wire `shutdown()` into the application server's shutdown lifecycle. If you are using a framework binding, graceful shutdown happens automatically when the server receives a termination signal. The Java Spring Boot binding uses `SmartLifecycle`, Quarkus uses `StartupEvent`/`ShutdownEvent`, and C# uses `IHostedService`.

If you are using `ANIPService` directly, call `shutdown()` before process exit:

**Python:**

```python
# In your shutdown handler
await service.shutdown()
service.stop()
```

**TypeScript:**

```typescript
// In your shutdown handler
await service.shutdown();
service.stop();
```

### Kubernetes Considerations

Set a `terminationGracePeriodSeconds` long enough for in-flight requests to complete and for `shutdown()` to flush the aggregator. The default of 30 seconds is typically sufficient. If your handlers are long-running, increase it to match your `exclusive_ttl`.

```yaml
spec:
  terminationGracePeriodSeconds: 60
```

---

## PostgreSQL Requirements

### Version

PostgreSQL 14 or later is recommended. The runtime uses `GENERATED ALWAYS AS IDENTITY` for audit sequence allocation, which requires PostgreSQL 10+. Advisory locking and `FOR UPDATE` row locking are used for append-head serialization.

### Connection Pooling

Each replica maintains its own connection pool to PostgreSQL. For large replica counts, use an external connection pooler (e.g., PgBouncer in transaction mode) to avoid exhausting PostgreSQL's `max_connections`.

### Schema Migrations

The `PostgresStorage` backend creates tables automatically on initialization using `CREATE TABLE IF NOT EXISTS`. There is no separate migration step. Schema changes in future ANIP versions will be documented in release notes.

---

## Quick Start: Cluster Deployment

1. Provision a PostgreSQL database.
2. Set the connection string as an environment variable (e.g., `ANIP_DATABASE_URL`).
3. Deploy replicas with identical configuration:
   - Same `service_id`
   - Same `storage` connection string
   - Same `key_path` pointing to shared signing key material
   - Same `trust`, `checkpoint_policy`, and `retention_policy` settings
4. Place replicas behind a load balancer. Any replica can handle any request.
5. Verify: query `audit_append_head` to confirm entries are being appended; query `leader_leases` to confirm a checkpoint leader is elected.

---

## Stdio Transport (Local Deployments)

For local agent-to-service communication without HTTP, ANIP supports a stdio transport binding (JSON-RPC 2.0 over stdin/stdout). An agent spawns the ANIP service as a subprocess and communicates all 9 protocol operations — including discovery, manifest, JWKS, token issuance, permissions, invoke (with streaming), audit query, and checkpoints — over stdin/stdout.

This is useful for:
- Local agent-to-tool execution
- Desktop or CLI agents
- Sandboxed single-host deployments

All 5 runtimes include stdio packages: `anip-stdio` (Python), `stdioapi` (Go), `anip-stdio` (Java), `Anip.Stdio` (C#), `@anip/stdio` (TypeScript).

See the [stdio transport spec](specs/2026-03-22-anip-stdio-transport-design.md) for the full protocol definition.

---

## gRPC Transport (Internal Service-to-Service)

For internal platforms, service meshes, and high-throughput deployments, ANIP supports a gRPC transport binding using a shared protobuf service definition (`proto/anip/v1/anip.proto`).

This is useful for:
- Internal service-to-service agent communication
- Enterprise infrastructure with existing gRPC tooling
- High-throughput or streaming-heavy deployments
- Environments with mTLS and service mesh

Currently implemented in Python (`anip-grpc`) and Go (`grpcapi`). Java, C#, and TypeScript implementations will generate stubs from the same shared proto.

Auth uses standard gRPC metadata (`authorization: Bearer <token>`). ANIP protocol failures stay in response messages — gRPC status codes are reserved for transport errors only (UNAUTHENTICATED, INTERNAL).

See the [gRPC transport spec](specs/2026-03-23-anip-grpc-transport-design.md) for the full protocol definition.

---

## ANIP Studio (Inspection UI)

ANIP Studio is an embedded inspection UI. Currently available as a Python/FastAPI adapter (`anip-studio`) that mounts at `/studio`. Adapters for other runtimes are a future addition. It provides read-only views for discovery, manifest, JWKS, audit, and checkpoints.

To mount Studio on a Python FastAPI service:

```python
from anip_studio import mount_anip_studio
mount_anip_studio(app, service)
# → Open http://localhost:8000/studio/
```

Studio is available as the `anip-studio` Python package. Adapters for other runtimes are a future addition.
