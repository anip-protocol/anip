---
title: Horizontal Scaling
description: Run multiple ANIP replicas behind a load balancer with PostgreSQL.
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Horizontal Scaling

ANIP services scale horizontally by running multiple stateless replicas behind a load balancer, sharing a PostgreSQL database. No cluster-wide reconfiguration is needed to add or remove replicas.

## Architecture

```mermaid
graph TD
    LB["Load Balancer"] --> R1["Replica 1"]
    LB --> R2["Replica 2"]
    LB --> RN["Replica N"]

    R1 --> PG["PostgreSQL<br/>(audit, tokens, checkpoints)"]
    R2 --> PG
    RN --> PG

    R1 --> Keys["Signing Keys<br/>(mounted secret or KMS)"]
    R2 --> Keys
    RN --> Keys
```

Any replica can handle any request. Coordination happens through lease tables in PostgreSQL:

- **Exclusive invocation locks** prevent duplicate execution of the same capability for the same principal across replicas
- **Leader election** ensures only one replica generates checkpoints at a time
- **Shared audit log** all replicas write to the same audit table

## Setup

The only change from single-instance to cluster is the storage DSN:

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

```python
service = ANIPService(
    service_id="my-service",
    capabilities=[...],
    storage="postgres://user:pass@host:5432/anip",
    trust="signed",
    key_path="/etc/anip-keys",
    checkpoint_policy=CheckpointPolicy(interval_seconds=60),
    authenticate=...,
)
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

```typescript
const service = createANIPService({
  serviceId: "my-service",
  capabilities: [...],
  storage: "postgres://user:pass@host:5432/anip",
  trust: "signed",
  keyPath: "/etc/anip-keys",
  checkpointPolicy: { intervalSeconds: 60 },
  authenticate: ...,
});
```

</TabItem>
<TabItem value="go" label="Go">

```go
svc, _ := service.New(service.Config{
    ServiceID:        "my-service",
    Capabilities:     capabilities,
    Storage:          "postgres://user:pass@host:5432/anip",
    Trust:            "signed",
    KeyPath:          "/etc/anip-keys",
    CheckpointPolicy: service.CheckpointPolicy{IntervalSeconds: 60},
    Authenticate:     authenticate,
})
```

</TabItem>
<TabItem value="java" label="Java">

```java
new ANIPService(new ServiceConfig()
    .setServiceId("my-service")
    .setCapabilities(capabilities)
    .setStorage("postgres://user:pass@host:5432/anip")
    .setTrust("signed")
    .setKeyPath("/etc/anip-keys")
    .setCheckpointPolicy(new CheckpointPolicy().setIntervalSeconds(60))
    .setAuthenticate(authenticate));
```

</TabItem>
<TabItem value="csharp" label="C#">

```csharp
var service = new AnipService(new ServiceConfig {
    ServiceId = "my-service",
    Capabilities = capabilities,
    Storage = "postgres://user:pass@host:5432/anip",
    Trust = "signed",
    KeyPath = "/etc/anip-keys",
    CheckpointPolicy = new CheckpointPolicy { IntervalSeconds = 60 },
    Authenticate = authenticate,
});
```

</TabItem>
</Tabs>

PostgreSQL creates all required tables on first connection: `audit_log`, `audit_append_head`, `tokens`, `checkpoints`, `exclusive_leases`, `leader_leases`, and related indexes.

## Signing key distribution

All replicas must use the same signing key material. Options:

### Kubernetes Secret (recommended)

```yaml
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
      - name: ANIP_STORAGE
        value: postgres://user:pass@postgres:5432/anip
```

### KMS-backed

For AWS KMS, GCP Cloud KMS, or HashiCorp Vault — the key material never leaves the KMS boundary. Custom `KeyManager` implementations can delegate signing to the external service.

## Background jobs in cluster mode

Three background jobs run on every replica. Each has a different coordination strategy:

| Job | Coordination | How it works |
|-----|-------------|--------------|
| **Checkpoint scheduler** | Leader-elected | Every tick, replicas compete for the leader lease. Winner builds the Merkle checkpoint. If leader crashes, another replica wins next tick. |
| **Retention enforcer** | None (idempotent) | `DELETE WHERE expires_at < now()` is safe to run on all replicas simultaneously. |
| **Aggregation flusher** | Per-replica | Each replica flushes its own in-memory aggregation buffer independently. |

### Exclusive invocation locks

When a capability is invoked, the runtime acquires an exclusive lease in PostgreSQL keyed on (capability, principal). This prevents duplicate execution if the same request hits multiple replicas. The lease expires after `exclusive_ttl` seconds (default: 60). Long-running handlers auto-renew at `ttl/2` intervals.

```python
# Increase TTL for long-running handlers
ANIPService(
    ...,
    storage="postgres://...",
    exclusive_ttl=120,  # seconds
)
```

## What stays the same

Scaling from one replica to many changes nothing about the protocol surface:

- Same 9 HTTP endpoints
- Same manifest, same signature
- Same delegation tokens (verified by any replica)
- Same audit log (shared in PostgreSQL)
- Same checkpoints (generated by elected leader)
- Same JWKS (same key material)

Clients and agents don't know or care how many replicas exist behind the load balancer.

## Next steps

- **[Configuration](/docs/getting-started/configuration)** — Storage, auth, and trust setup
- **[Observability](/docs/getting-started/observability)** — Logging, metrics, and tracing hooks
- **[Deployment guide](https://github.com/anip-protocol/anip/blob/main/docs/deployment-guide.md)** — Full deployment reference
