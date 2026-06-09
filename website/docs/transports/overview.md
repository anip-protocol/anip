---
title: Transport Overview
description: ANIP supports HTTP, stdio, and gRPC — same contract, multiple wire formats.
---

# Transport Overview

ANIP separates the governed capability contract from the wire format used to reach it. HTTP and stdio are the complete generated transport paths across all five runtimes. gRPC is a functional Python/Go core binding for protobuf-first environments, but it currently trails the newest approval-grant workflow.

That distinction matters:

```text
ANIP capability contract = what the agent is allowed to do and how execution is governed
transport binding = how protocol messages move between client and service
interface adapter = optional derived surface such as REST, GraphQL, or MCP
```

Changing transport should not change the service's public capability semantics.

## Available transports

| Transport | Wire format | Runtimes | Best for |
|-----------|------------|----------|----------|
| [HTTP](/docs/transports/http) | REST-like endpoints | All 5 | Web services, browsers, Studio |
| [stdio](/docs/transports/stdio) | JSON-RPC 2.0 on stdin/stdout | All 5 | CLI tools, local agents, subprocess communication |
| [gRPC](/docs/transports/grpc) | Protobuf over HTTP/2 | Python, Go | High-performance internal services where core transport coverage is sufficient |

The native transports expose the same core protocol operations:

| Operation | Purpose |
|-----------|---------|
| Discovery | Find service metadata and endpoint/method locations. |
| JWKS | Fetch public verification keys. |
| Manifest | Fetch signed capability declarations. |
| Token issuance | Mint scoped delegation tokens. |
| Permission discovery | Ask what is available, restricted, or denied before invocation. |
| Invoke | Execute one bounded capability. |
| Audit | Query protocol-level execution evidence. |
| Checkpoints | Verify tamper-evident audit history. |

## Choosing a transport

**HTTP** is the default. Start here for deployed services, browser access, Studio integration, Registry examples, and service-to-service calls. All five runtimes support it, and the generated REST, GraphQL, and MCP interface adapters mount on HTTP.

**stdio** is for local process communication. Use it when an agent or developer tool launches the ANIP service as a subprocess and communicates over stdin/stdout without opening a network port. This is useful for local agent clients, IDE integrations, and sandboxed environments.

**gRPC** is for internal platform environments where protobuf, HTTP/2, typed generated clients, or service-mesh conventions matter. It is currently implemented in Python and Go for the core transport operations. Use HTTP or stdio for full current generated-service parity.

## Support Matrix

| Target | HTTP | stdio | gRPC |
|--------|------|-------|------|
| Python | Yes | Yes | Yes |
| TypeScript | Yes | Yes | Planned |
| Go | Yes | Yes | Yes |
| Java | Yes | Yes | Planned |
| C# | Yes | Yes | Planned |

The generator can emit HTTP and stdio runners from the same package or service definition:

```bash
anip generate \
  --package my-service@0.2.0 \
  --target typescript \
  --transport http,stdio \
  --output ./generated/my-service
```

Framework selection is independent from transport selection. For example, TypeScript can generate Hono, Express, or Fastify HTTP hosts while preserving the same ANIP contract.

## Auth by Transport

| Transport | Auth carrier | Notes |
|-----------|--------------|-------|
| HTTP | `Authorization: Bearer <token>` header | Best fit for deployed services, OIDC/API-key bootstrap, and browser/tooling integration. |
| stdio | `auth` object in JSON-RPC params | There are no HTTP headers, so generated stdio bindings carry auth inside the request payload. |
| gRPC | `authorization` metadata | Same bearer-token model, carried through gRPC metadata. |

The token semantics are the same regardless of carrier. API keys or OIDC tokens can bootstrap a principal; ANIP delegation tokens are used for bounded agent execution.

## Native Transports vs Interface Adapters

Transports are how native ANIP protocol messages are carried:

- Native ANIP over HTTP.
- Native ANIP over stdio.
- Native ANIP over gRPC.

Interface adapters are derived product surfaces generated from ANIP capabilities:

- REST/OpenAPI.
- GraphQL.
- MCP.

Adapters are useful for interoperability, but they are not the source of governance. The ANIP capability contract remains the authority for permissions, approvals, failures, cost, lineage, audit, and verification.

## Practical Patterns

| Pattern | Recommended surface |
|---------|---------------------|
| Public or internal deployed service | Native ANIP HTTP |
| Local tool launched by an agent | Native ANIP stdio |
| Existing MCP client needs access | MCP adapter derived from ANIP capabilities |
| Existing application wants OpenAPI | REST adapter derived from ANIP capabilities |
| Internal platform with protobuf standards | Native ANIP gRPC where supported |
| Studio project design and testing | Native ANIP HTTP |

## Next Steps

- [HTTP transport](/docs/transports/http)
- [stdio transport](/docs/transports/stdio)
- [gRPC transport](/docs/transports/grpc)
- [Generated interfaces](/docs/generated-services/interfaces)
- [Generate a service](/docs/getting-started/generate-service)
