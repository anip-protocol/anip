---
title: Configuration
description: Configure storage, authentication, trust level, and runtime options for your ANIP service.
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Configuration

Every ANIP service is configured through a service config object. This page covers the key configuration options: storage, authentication, trust level, and runtime behavior.

## Storage

ANIP manages its own storage for audit logs, delegation tokens, checkpoints, and internal coordination state. You configure it with a connection string — the runtime handles schema creation, migrations, and all database operations internally.

### Supported backends

| Backend | Connection string | Use case |
|---------|------------------|----------|
| **In-memory** | `"memory"` or `":memory:"` | Development, testing |
| **SQLite** | `"sqlite:///path/to/db"` | Single-instance production |
| **PostgreSQL** | `"postgres://user:pass@host:5432/db"` | Multi-replica production |

These are the three backends ANIP supports today. Other databases (MySQL, MongoDB, etc.) are not currently supported.

### ANIP storage is separate from your application database

ANIP's storage is for protocol state only — audit logs, tokens, checkpoints, and leases. It does **not** store your application data. Your capability handlers can use any database, ORM, or data layer you want (SQLAlchemy, Prisma, GORM, Hibernate, Entity Framework — anything). The ANIP storage configuration only affects the protocol runtime's own state.

```mermaid
graph LR
    subgraph Your Application
        H["Capability handlers"] -->|"any ORM, any DB"| YDB["Your database<br/>(MySQL, Mongo, Redis, etc.)"]
        R["ANIP runtime"] -->|"protocol state only"| ADB["ANIP storage<br/>(SQLite or PostgreSQL)"]
    end
```

### Using ORMs in your capability handlers

Your capability handlers are normal application code — they can use any ORM, database client, or data layer. ANIP doesn't interfere with your application's data access patterns.

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python (SQLAlchemy)" default>

```python
from sqlalchemy.orm import Session
from anip_service import Capability

def search_flights_handler(ctx, params):
    # Use your own database connection — ANIP doesn't touch it
    with Session(your_engine) as session:
        flights = session.query(Flight).filter(
            Flight.origin == params["origin"],
            Flight.destination == params["destination"],
        ).all()
        return {"flights": [f.to_dict() for f in flights]}

search_flights = Capability(
    name="search_flights",
    description="Search available flights",
    side_effect="read",
    scope=["travel.search"],
    handler=search_flights_handler,
)
```

</TabItem>
<TabItem value="typescript" label="TypeScript (Prisma)">

```typescript
import { PrismaClient } from "@prisma/client";
const prisma = new PrismaClient();

const searchFlights = defineCapability({
  name: "search_flights",
  description: "Search available flights",
  sideEffect: "read",
  scope: ["travel.search"],
  handler: async (ctx, params) => {
    // Use Prisma, Drizzle, TypeORM, Knex — whatever you want
    const flights = await prisma.flight.findMany({
      where: {
        origin: params.origin,
        destination: params.destination,
      },
    });
    return { flights };
  },
});
```

</TabItem>
<TabItem value="go" label="Go (GORM)">

```go
import "gorm.io/gorm"

func searchFlights(db *gorm.DB) service.CapabilityDef {
    return service.CapabilityDef{
        Name:       "search_flights",
        SideEffect: "read",
        Scope:      []string{"travel.search"},
        Handler: func(ctx service.InvokeContext, params map[string]any) (any, error) {
            var flights []Flight
            // Use GORM, sqlx, pgx — whatever you want
            db.Where("origin = ? AND destination = ?",
                params["origin"], params["destination"]).Find(&flights)
            return map[string]any{"flights": flights}, nil
        },
    }
}
```

</TabItem>
<TabItem value="java" label="Java (JPA/Hibernate)">

```java
@Component
public class SearchFlightsCapability {
    @PersistenceContext
    private EntityManager em;

    public CapabilityDef create() {
        return new CapabilityDef()
            .setName("search_flights")
            .setSideEffect("read")
            .setScope(List.of("travel.search"))
            .setHandler((ctx, params) -> {
                // Use JPA, Hibernate, jOOQ, JDBC — whatever you want
                var flights = em.createQuery(
                    "SELECT f FROM Flight f WHERE f.origin = :origin AND f.destination = :dest",
                    Flight.class)
                    .setParameter("origin", params.get("origin"))
                    .setParameter("dest", params.get("destination"))
                    .getResultList();
                return Map.of("flights", flights);
            });
    }
}
```

</TabItem>
<TabItem value="csharp" label="C# (Entity Framework)">

```csharp
public static CapabilityDef CreateSearchFlights(AppDbContext db) {
    return new CapabilityDef {
        Name = "search_flights",
        SideEffect = "read",
        Scope = ["travel.search"],
        Handler = async (ctx, parameters) => {
            // Use EF Core, Dapper, ADO.NET — whatever you want
            var flights = await db.Flights
                .Where(f => f.Origin == (string)parameters["origin"]
                          && f.Destination == (string)parameters["destination"])
                .ToListAsync();
            return new { flights };
        }
    };
}
```

</TabItem>
</Tabs>

The key point: **ANIP's `storage` config is for the protocol runtime only.** Your handlers talk to your own database with your own ORM. The two never mix.

### In-memory (development)

No persistence — data is lost when the process exits. Good for tests and development.

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

```python
service = ANIPService(
    service_id="my-service",
    capabilities=[...],
    storage="memory",  # or omit — memory is the default
    authenticate=...,
)
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

```typescript
const service = createANIPService({
  serviceId: "my-service",
  capabilities: [...],
  storage: { type: "memory" },  // default
  authenticate: ...,
});
```

</TabItem>
<TabItem value="go" label="Go">

```go
svc, _ := service.New(service.Config{
    ServiceID:    "my-service",
    Capabilities: capabilities,
    Storage:      "memory",  // default
    Authenticate: authenticate,
})
```

</TabItem>
<TabItem value="java" label="Java">

```java
new ANIPService(new ServiceConfig()
    .setServiceId("my-service")
    .setCapabilities(capabilities)
    .setStorage("memory")  // default
    .setAuthenticate(authenticate));
```

</TabItem>
<TabItem value="csharp" label="C#">

```csharp
var service = new AnipService(new ServiceConfig {
    ServiceId = "my-service",
    Capabilities = capabilities,
    Storage = "memory",  // default
    Authenticate = authenticate,
});
```

</TabItem>
</Tabs>

### SQLite (single-instance production)

Persistent local storage. Good for single-process deployments.

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

```python
service = ANIPService(
    service_id="my-service",
    capabilities=[...],
    storage="sqlite:///anip.db",
    authenticate=...,
)
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

```typescript
const service = createANIPService({
  serviceId: "my-service",
  capabilities: [...],
  storage: { type: "sqlite", path: "anip.db" },
  authenticate: ...,
});
```

</TabItem>
<TabItem value="go" label="Go">

```go
svc, _ := service.New(service.Config{
    ServiceID:    "my-service",
    Capabilities: capabilities,
    Storage:      "sqlite:///anip.db",
    Authenticate: authenticate,
})
```

</TabItem>
<TabItem value="java" label="Java">

```java
new ANIPService(new ServiceConfig()
    .setServiceId("my-service")
    .setCapabilities(capabilities)
    .setStorage("sqlite:///anip.db")
    .setAuthenticate(authenticate));
```

</TabItem>
<TabItem value="csharp" label="C#">

```csharp
var service = new AnipService(new ServiceConfig {
    ServiceId = "my-service",
    Capabilities = capabilities,
    Storage = "sqlite:///anip.db",
    Authenticate = authenticate,
});
```

</TabItem>
</Tabs>

### PostgreSQL (cluster production)

Shared storage for multi-replica deployments. Required for horizontal scaling.

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

```python
service = ANIPService(
    service_id="my-service",
    capabilities=[...],
    storage="postgres://user:pass@host:5432/anip",
    authenticate=...,
)
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

```typescript
const service = createANIPService({
  serviceId: "my-service",
  capabilities: [...],
  storage: { type: "postgres", connectionString: "postgres://user:pass@host:5432/anip" },
  authenticate: ...,
});
```

</TabItem>
<TabItem value="go" label="Go">

```go
svc, _ := service.New(service.Config{
    ServiceID:    "my-service",
    Capabilities: capabilities,
    Storage:      "postgres://user:pass@host:5432/anip",
    Authenticate: authenticate,
})
```

</TabItem>
<TabItem value="java" label="Java">

```java
new ANIPService(new ServiceConfig()
    .setServiceId("my-service")
    .setCapabilities(capabilities)
    .setStorage("postgres://user:pass@host:5432/anip")
    .setAuthenticate(authenticate));
```

</TabItem>
<TabItem value="csharp" label="C#">

```csharp
var service = new AnipService(new ServiceConfig {
    ServiceId = "my-service",
    Capabilities = capabilities,
    Storage = "postgres://user:pass@host:5432/anip",
    Authenticate = authenticate,
});
```

</TabItem>
</Tabs>

The runtime creates all required tables automatically on first connection — just point it at an empty PostgreSQL database. With PostgreSQL, multiple replicas can run behind a load balancer with automatic coordination. See [Horizontal Scaling](/docs/getting-started/scaling) for details.

## Authentication

ANIP supports multiple authentication methods that can be used simultaneously.

### API keys

The simplest path — map bearer strings to principal identities. See [Authentication](/docs/protocol/authentication) for examples in all languages.

### OIDC / OAuth2

Validate external JWTs from any OIDC-compliant identity provider (Keycloak, Auth0, Okta, Azure AD, etc.):

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

Set environment variables:

```bash
OIDC_ISSUER_URL=https://keycloak.example.com/realms/anip
OIDC_AUDIENCE=my-service         # defaults to service_id
# OIDC_JWKS_URL=...              # optional override
```

The service auto-discovers the OIDC configuration from the issuer URL, validates incoming JWTs, and maps claims to ANIP principals:
- `email` claim → `human:{email}`
- `sub` claim → `oidc:{sub}`

API keys continue to work alongside OIDC tokens.

</TabItem>
<TabItem value="typescript" label="TypeScript">

```bash
OIDC_ISSUER_URL=https://keycloak.example.com/realms/anip
OIDC_AUDIENCE=my-service
```

The TypeScript runtime reads these environment variables and configures OIDC validation automatically. The `authenticate` callback receives OIDC tokens alongside API keys.

</TabItem>
<TabItem value="go" label="Go">

```bash
OIDC_ISSUER_URL=https://keycloak.example.com/realms/anip
OIDC_AUDIENCE=my-service
```

The Go runtime reads these environment variables and validates OIDC tokens using the issuer's JWKS endpoint.

</TabItem>
<TabItem value="java" label="Java">

```bash
OIDC_ISSUER_URL=https://keycloak.example.com/realms/anip
OIDC_AUDIENCE=my-service
```

The Java runtime configures OIDC validation from environment variables. Works with both Spring Boot and Quarkus adapters.

</TabItem>
<TabItem value="csharp" label="C#">

```bash
OIDC_ISSUER_URL=https://keycloak.example.com/realms/anip
OIDC_AUDIENCE=my-service
```

The C# runtime reads OIDC configuration from environment variables and integrates with ASP.NET Core's authentication pipeline.

</TabItem>
</Tabs>

## Trust level

The `trust` setting controls the cryptographic trust posture of the service:

| Level | What it means | When to use |
|-------|--------------|-------------|
| `"declarative"` | No signing — capabilities are declared but not cryptographically verified | Development, testing |
| `"signed"` | Manifest and tokens are signed with the service's key pair, JWKS published | Production |
| `"anchored"` | Audit checkpoints are anchored to external trust sources | Compliance, regulated environments |

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

```python
service = ANIPService(
    service_id="my-service",
    capabilities=[...],
    trust="signed",
    key_path="keys/",  # directory for key storage
    authenticate=...,
)
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

```typescript
const service = createANIPService({
  serviceId: "my-service",
  capabilities: [...],
  trust: "signed",
  keyPath: "keys/",
  authenticate: ...,
});
```

</TabItem>
<TabItem value="go" label="Go">

```go
svc, _ := service.New(service.Config{
    ServiceID:    "my-service",
    Capabilities: capabilities,
    Trust:        "signed",
    KeyPath:      "keys/",
    Authenticate: authenticate,
})
```

</TabItem>
<TabItem value="java" label="Java">

```java
new ANIPService(new ServiceConfig()
    .setServiceId("my-service")
    .setCapabilities(capabilities)
    .setTrust("signed")
    .setKeyPath("keys/")
    .setAuthenticate(authenticate));
```

</TabItem>
<TabItem value="csharp" label="C#">

```csharp
var service = new AnipService(new ServiceConfig {
    ServiceId = "my-service",
    Capabilities = capabilities,
    Trust = "signed",
    KeyPath = "keys/",
    Authenticate = authenticate,
});
```

</TabItem>
</Tabs>

When `trust` is `"signed"` or higher, the runtime generates an Ed25519 key pair on first run (stored in `key_path`) and uses it to sign manifests, delegation tokens, and checkpoints.

## Key management

### How ANIP keys work (and how they differ from OIDC)

If you've worked with Keycloak, Auth0, or any OAuth2/OIDC identity provider, you're used to JWKS as part of an identity trust chain — the IdP's JWKS proves that tokens were issued by a trusted authority, and relying parties use it to verify identity claims.

ANIP JWKS is different. It's a **verification surface**, not a trust anchor.

| | OIDC / OAuth2 JWKS | ANIP JWKS |
|---|---|---|
| **Scope** | Organization-wide identity provider | Per-service |
| **What it verifies** | "This token was issued by our IdP" | "This manifest/token/checkpoint was signed by this service" |
| **Trust source** | The IdP is the trust anchor | Trust comes from deployment context, not the key itself |
| **Key management** | Centralized (IdP manages rotation) | Per-service (each service has its own key pair) |
| **Who rotates** | IdP admin or platform automation | Service operator or platform automation |

ANIP JWKS answers: *which public keys verify artifacts from this service?*

It does **not** answer: *should I trust this service at all?*

Trust comes from the wider deployment context — transport security, platform policy, service identity, and optionally anchored checkpoints that provide external verification.

### Zero-config for development

In development and local use, key management is invisible:

1. Service starts with `trust: "signed"` and a `key_path`
2. If no key exists at that path, the runtime generates an Ed25519 key pair automatically
3. The public key is published at `/.well-known/jwks.json`
4. The private key signs manifests, tokens, and checkpoints
5. Keys persist across restarts (same `key_path` = same keys = consistent verification)

You don't need to generate PEM files, configure certificates, or set up any key infrastructure. Just run the service.

### Production key management

In production, all replicas must use the same signing key (see [Horizontal Scaling](/docs/getting-started/scaling)). Options:

| Approach | How it works | Best for |
|----------|-------------|----------|
| **Shared file path** | All replicas mount the same key directory | Simple deployments |
| **Kubernetes Secret** | Mount a Secret at `key_path`, shared across the Deployment | Kubernetes |
| **KMS-backed** | Custom `KeyManager` delegates signing to AWS KMS, GCP Cloud KMS, or HashiCorp Vault | High-security / regulated |

### Key rotation

When rotating keys:

1. Deploy the new key material to all replicas
2. During the rollover window, the JWKS publishes **both** old and new public keys
3. New artifacts are signed with the new key
4. Old artifacts remain verifiable with the old key (matched by `kid`)
5. Remove the old key after the rollover/retention window

**Important:** Coordinate key rotation as an atomic configuration change (e.g., update the Kubernetes Secret, then trigger a rolling restart). A rolling deploy that updates one replica at a time creates a window where different replicas sign with different keys.

### Operational checklist

| Environment | Key setup | Rotation | Monitoring |
|-------------|-----------|----------|------------|
| **Development** | Automatic (zero config) | Not needed | Not needed |
| **Staging** | Shared file or Secret | Manual or automated | Verify JWKS endpoint returns expected `kid` |
| **Production** | Kubernetes Secret or KMS | Automated with rollover window | Alert on JWKS `kid` mismatch across replicas |

## Checkpoint policy

Control how often Merkle checkpoints are generated over the audit log:

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

```python
from anip_server import CheckpointPolicy

service = ANIPService(
    service_id="my-service",
    capabilities=[...],
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
    .setCheckpointPolicy(new CheckpointPolicy().setIntervalSeconds(60))
    .setAuthenticate(authenticate));
```

</TabItem>
<TabItem value="csharp" label="C#">

```csharp
var service = new AnipService(new ServiceConfig {
    ServiceId = "my-service",
    Capabilities = capabilities,
    CheckpointPolicy = new CheckpointPolicy { IntervalSeconds = 60 },
    Authenticate = authenticate,
});
```

</TabItem>
</Tabs>

## Next steps

- **[Quickstart](/docs/getting-started/quickstart)** — Build and run a service
- **[Authentication](/docs/protocol/authentication)** — Deep dive into the auth model
- **[Deployment guide](https://github.com/anip-protocol/anip/blob/main/docs/deployment-guide.md)** — Cluster deployment with PostgreSQL
