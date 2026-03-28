---
title: Interface Adapters
description: Mount REST, GraphQL, and MCP alongside native ANIP on the same service.
---

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

```typescript
import { mountAnip } from "@anip/hono";
import { mountAnipRest } from "@anip/rest";
import { mountAnipGraphQL } from "@anip/graphql";
import { mountAnipMcpHono } from "@anip/mcp-hono";

mountAnip(app, service);
await mountAnipRest(app, service);
await mountAnipGraphQL(app, service);
await mountAnipMcpHono(app, service);
```

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
