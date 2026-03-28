---
title: Configuration
description: Configure storage, authentication, trust level, and runtime options for your ANIP service.
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Configuration

Every ANIP service is configured through a service config object. This page covers the key configuration options: storage, authentication, trust level, and runtime behavior.

## Storage

ANIP supports three storage backends. Storage holds audit logs, delegation tokens, checkpoints, and internal state.

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

With PostgreSQL, multiple replicas can run behind a load balancer. Coordination happens through lease tables — any replica can handle any request. See the [deployment guide](https://github.com/anip-protocol/anip/blob/main/docs/deployment-guide.md) for cluster setup details.

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
