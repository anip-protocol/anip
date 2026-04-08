---
title: Install
description: Install ANIP by ecosystem and understand what is already published today.
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Install

ANIP is available across multiple ecosystems. Pick your language to get started.

## Runtime packages

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

Published to **PyPI**. Install the service runtime and a framework adapter:

```bash
pip install anip-service anip-fastapi
```

**All published packages:**

| Package | Purpose |
|---------|---------|
| `anip-core` | Models, types, constants |
| `anip-crypto` | Key management, JWT, signing |
| `anip-server` | Protocol engine (delegation, audit, checkpoints) |
| `anip-service` | Service runtime (capabilities, handlers) |
| `anip-fastapi` | FastAPI framework adapter |
| `anip-rest` | REST / OpenAPI interface adapter |
| `anip-graphql` | GraphQL interface adapter |
| `anip-mcp` | MCP Streamable HTTP interface adapter |
| `anip-studio` | Studio embedded UI adapter |
| `anip-stdio` | stdio transport (JSON-RPC 2.0) |
| `anip-grpc` | gRPC transport |

</TabItem>
<TabItem value="typescript" label="TypeScript">

Published to **npm** under the `@anip` scope. Install the service runtime and a framework adapter:

```bash
npm install @anip-dev/service @anip-dev/hono
```

**All published packages:**

| Package | Purpose |
|---------|---------|
| `@anip-dev/core` | Models, types, constants |
| `@anip-dev/crypto` | Key management, JWT, signing |
| `@anip-dev/server` | Protocol engine |
| `@anip-dev/service` | Service runtime |
| `@anip-dev/hono` | Hono framework adapter |
| `@anip-dev/express` | Express framework adapter |
| `@anip-dev/fastify` | Fastify framework adapter |
| `@anip-dev/rest` | REST / OpenAPI interface adapter |
| `@anip-dev/graphql` | GraphQL interface adapter |
| `@anip-dev/mcp` | MCP shared core |
| `@anip-dev/mcp-hono` | MCP adapter for Hono |
| `@anip-dev/mcp-express` | MCP adapter for Express |
| `@anip-dev/mcp-fastify` | MCP adapter for Fastify |
| `@anip-dev/stdio` | stdio transport (JSON-RPC 2.0) |

</TabItem>
<TabItem value="go" label="Go">

Consumed as a **Go module** via version tags:

```bash
go get github.com/anip-protocol/anip/packages/go@vVERSION
```

**Packages in the module:**

`core`, `crypto`, `server`, `service`, `httpapi`, `ginapi`, `restapi`, `graphqlapi`, `mcpapi`, `stdioapi`, `grpcapi`

</TabItem>
<TabItem value="java" label="Java">

Published to **Maven Central** under group `dev.anip`:

```xml
<dependency>
  <groupId>dev.anip</groupId>
  <artifactId>anip-service</artifactId>
  <version>0.22.0</version>
</dependency>
```

**All published modules:**

| Module | Purpose |
|--------|---------|
| `anip-core` | Models, types |
| `anip-crypto` | Key management, JWT |
| `anip-server` | Protocol engine |
| `anip-service` | Service runtime |
| `anip-spring-boot` | Spring Boot adapter |
| `anip-quarkus` | Quarkus adapter |
| `anip-rest` / `anip-rest-spring` / `anip-rest-quarkus` | REST adapters |
| `anip-graphql` / `anip-graphql-spring` / `anip-graphql-quarkus` | GraphQL adapters |
| `anip-mcp` / `anip-mcp-spring` / `anip-mcp-quarkus` | MCP adapters |
| `anip-stdio` | stdio transport |

</TabItem>
<TabItem value="csharp" label="C#">

C# packages are available **in-repo** (NuGet publishing coming soon):

```bash
# From the ANIP repo root:
dotnet add reference packages/csharp/src/Anip.Service
dotnet add reference packages/csharp/src/Anip.AspNetCore
```

**All projects:** `Anip.Core`, `Anip.Crypto`, `Anip.Server`, `Anip.Service`, `Anip.AspNetCore`, `Anip.Rest`, `Anip.Rest.AspNetCore`, `Anip.GraphQL`, `Anip.GraphQL.AspNetCore`, `Anip.Mcp`, `Anip.Mcp.AspNetCore`, `Anip.Stdio`

</TabItem>
</Tabs>

## Studio

Studio runs in two modes — no language dependency for standalone:

```bash
# Standalone via Docker (connects to any ANIP service)
docker build -t anip-studio studio/
docker run -p 3000:8080 anip-studio
```

Or embedded inside a Python service:

```bash
pip install anip-studio
```

```python
from anip_studio import mount_anip_studio
mount_anip_studio(app, service)
# → http://localhost:9100/studio/
```

## Testing tools

```bash
# Conformance suite — validates protocol compliance
pip install -e ./conformance
pytest conformance/ --base-url=http://localhost:9100 --bootstrap-bearer=demo-human-key

# Contract testing — validates behavioral truthfulness
pip install -e ./contract-tests
anip-contract-tests --base-url=http://localhost:9100 --test-pack=contract-tests/packs/travel.json
```

For the full artifact story, see [What Ships Today](../releases/what-ships-today.md).
