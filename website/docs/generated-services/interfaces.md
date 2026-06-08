---
title: Derived Interfaces
description: Expose ANIP capabilities through REST, GraphQL, or MCP without changing the governed ANIP contract.
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Derived Interfaces

Native ANIP is the authoritative service interface. It exposes discovery, manifest, permissions, token issuance, invocation, audit, checkpoints, and structured failure behavior as one governed protocol surface.

Derived interfaces let the same ANIP capability service be consumed by clients that expect REST, GraphQL, or MCP.

```text
client-facing derived interface -> ANIP capability service -> backend implementation
```

They are projections of the ANIP contract. They are not the contract authority, and they are not backend adapters.

## What derived interfaces are

Use derived interfaces when a client cannot or should not speak native ANIP directly:

- REST/OpenAPI for conventional HTTP clients and Swagger-based inspection.
- GraphQL for GraphQL-oriented application clients.
- MCP for MCP clients that should see governed ANIP capabilities rather than raw backend tools.

Where mounted, these interfaces resolve auth, invoke the same ANIP capability handlers, and return the same governed outcomes: available, clarification required, approval required, restricted, denied, or unavailable.

## What they are not

Derived interfaces are not downstream integration adapters.

Do not read this page as:

```text
ANIP service -> REST adapter -> Jira
ANIP service -> GraphQL adapter -> Linear
ANIP service -> MCP adapter -> Slack MCP
```

Backend integration belongs in generated implementation seams or custom code bundles. For example, a Slack fronting service may call the Slack Web API internally, but its MCP derived interface, if enabled, exposes ANIP capabilities to MCP clients. It does not make MCP the backend behavior authority.

## Available surfaces

| Surface | What it exposes | Typical endpoint |
| --- | --- | --- |
| REST/OpenAPI | Capability-specific HTTP routes plus OpenAPI and Swagger UI | `/rest/openapi.json`, `/rest/docs`, generated capability routes |
| GraphQL | Capability fields/mutations plus SDL | `/graphql`, `/schema.graphql` |
| MCP | ANIP capabilities as MCP tools for MCP clients | `/mcp` for Streamable HTTP; stdio support is transport/runtime-specific |

The exact mounting API varies by language and framework. The native ANIP service remains the baseline output; derived interfaces are added where the target/runtime supports them.

## What carries through

Because derived interfaces call the ANIP service, important enforcement still happens server-side:

| Behavior | Derived interface posture |
| --- | --- |
| Capability handler | Same service handler is invoked. |
| Authentication | Bearer/JWT or API-key fallback is resolved by the interface package where supported. |
| Scope checks | Enforced by the ANIP service before execution. |
| Clarification and denial | Returned as structured failure outcomes, sometimes adapted to REST/GraphQL/MCP response conventions. |
| Approval boundary | Preserved as `approval_required` when the capability requires a grant. |
| Audit and checkpoints | Preserved when the service invocation path records audit/checkpoint state and durable storage is configured. |

## What is only partial

Derived interfaces cannot fully replace native ANIP for agents that need complete execution governance.

| Native ANIP feature | Derived REST/GraphQL/MCP projection |
| --- | --- |
| Full signed manifest | Usually projected into route/schema/tool descriptions, not carried as the protocol authority. |
| Permission discovery | Usually not a first-class REST/GraphQL/MCP operation unless separately exposed. |
| Delegation chain inspection | Enforced by the service, but not necessarily visible as native ANIP metadata. |
| Side-effect posture | Projected as docs/schema/tool hints; native ANIP keeps the enforceable contract field. |
| Cost and recovery metadata | May be included in responses or descriptions, but native ANIP has the complete structured shape. |
| Audit/checkpoint query APIs | Native ANIP exposes the protocol-level audit/checkpoint surfaces. |

For MCP specifically, tool annotations and descriptions are useful hints. They are not a substitute for ANIP's service-owned permission, approval, denial, audit, and verification model.

## When to use which surface

| Client need | Recommended surface |
| --- | --- |
| Agent needs full governed execution context | Native ANIP |
| Existing app needs simple HTTP routes | REST/OpenAPI derived interface |
| Existing app or dashboard is GraphQL-native | GraphQL derived interface |
| MCP client needs access to governed capabilities | MCP derived interface |
| Service implementation needs to call Jira, Slack, Linear, Superset, dbt, Cube, Snowflake, or an MCP server | Custom bundle or implementation seam, not a derived interface |

## Mounting examples

These examples show the shape of explicit mounting APIs. Generated application templates may already include some surfaces for a target, but the safe mental model is: native ANIP is required; derived interfaces are optional projections.

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

```python
from anip_fastapi import mount_anip
from anip_rest import mount_anip_rest
from anip_graphql import mount_anip_graphql
from anip_mcp import mount_anip_mcp_http

mount_anip(app, service)              # Native ANIP at /anip/*
mount_anip_rest(app, service)         # REST routes + /rest/openapi.json
mount_anip_graphql(app, service)      # GraphQL at /graphql
mount_anip_mcp_http(app, service)     # MCP Streamable HTTP at /mcp
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
httpapi.MountANIP(mux, svc, httpapi.MountANIPOpts{HealthEndpoint: true})
restapi.MountANIPRest(mux, svc, nil)
graphqlapi.MountANIPGraphQL(mux, svc, nil)
mcpapi.MountAnipMcpHTTP(mux, svc, nil)
```

</TabItem>
<TabItem value="java" label="Java (Spring)">

```java
@Bean public AnipController anip(ANIPService service) {
    return new AnipController(service);
}

@Bean public AnipRestController rest(ANIPService service) {
    return new AnipRestController(service);
}

@Bean public AnipGraphQLController graphql(ANIPService service) {
    return new AnipGraphQLController(service);
}

// MCP uses the matching Spring MCP package/registration.
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

## Release rule

Do not publish or document a derived interface as if it were the canonical package contract.

The signed package, service definition, manifest digest, and contract signature remain the source of truth. REST, GraphQL, and MCP surfaces are compatibility projections of that truth.
