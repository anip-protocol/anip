---
title: Interface Adapters
description: Mount REST, GraphQL, and MCP alongside native ANIP on the same service.
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Interface Adapters

ANIP does not force you to choose between an agent-native interface and the rest of your API ecosystem. The same capability definitions that power ANIP can auto-generate REST, GraphQL, and MCP interfaces — all mounted on the same service.

## Available adapters

| Adapter | What it generates | Endpoint |
|---------|------------------|----------|
| **REST** | OpenAPI spec + Swagger UI | `/api/*` |
| **GraphQL** | SDL schema + playground | `/graphql` |
| **MCP** | Streamable HTTP tools | `/mcp` |

## Mounting adapters

All adapters mount with one line alongside native ANIP:

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

```python
from anip_fastapi import mount_anip
from anip_rest import mount_anip_rest
from anip_graphql import mount_anip_graphql
from anip_mcp import mount_anip_mcp_http

mount_anip(app, service)              # Native ANIP at /anip/*
mount_anip_rest(app, service)         # REST at /api/*
mount_anip_graphql(app, service)      # GraphQL at /graphql
mount_anip_mcp_http(app, service)     # MCP at /mcp
```

</TabItem>
<TabItem value="typescript" label="TypeScript">

```typescript
import { mountAnip } from "@anip-dev/hono";
import { mountAnipRest } from "@anip-dev/rest";
import { mountAnipGraphQL } from "@anip-dev/graphql";
import { mountAnipMcpHono } from "@anip-dev/mcp-hono";

mountAnip(app, service);
await mountAnipRest(app, service);
await mountAnipGraphQL(app, service);
await mountAnipMcpHono(app, service);
```

</TabItem>
<TabItem value="go" label="Go">

```go
httpapi.MountANIP(mux, svc)              // Native ANIP
restapi.MountANIPRest(mux, svc, nil)     // REST at /api/*
graphqlapi.MountANIPGraphQL(mux, svc, nil) // GraphQL at /graphql
mcpapi.MountAnipMcpHTTP(mux, svc, nil)   // MCP at /mcp
```

</TabItem>
<TabItem value="java" label="Java (Spring)">

```java
// Spring auto-wires controllers as beans:
@Bean public AnipController anip(ANIPService s) { return new AnipController(s); }
@Bean public AnipRestController rest(ANIPService s) { return new AnipRestController(s); }
@Bean public AnipGraphQLController gql(ANIPService s) { return new AnipGraphQLController(s); }
// MCP via servlet registration
```

</TabItem>
<TabItem value="csharp" label="C#">

```csharp
builder.Services.AddAnip(service);
builder.Services.AddAnipMcp(service);
builder.Services.AddControllers()
    .AddApplicationPart(typeof(AnipRestController).Assembly)
    .AddApplicationPart(typeof(AnipGraphQLController).Assembly);

app.MapControllers();
app.MapAnipMcp();
```

</TabItem>
</Tabs>

## What adapters provide vs. native ANIP

Adapters give conventional clients familiar interfaces, but the native ANIP surface remains the strongest path for agents that need:

| Feature | REST/GraphQL/MCP | Native ANIP |
|---------|-----------------|-------------|
| Invoke capabilities | Yes | Yes |
| Side-effect declaration | No | Yes |
| Permission discovery | No | Yes |
| Delegation chains | No | Yes |
| Cost signaling | No | Yes |
| Structured failure recovery | Partial | Full |
| Audit + checkpoints | No | Yes |

The adapters reduce the "build it twice" problem — your conventional API consumers get OpenAPI/GraphQL/MCP, while agents get the full ANIP execution context.
