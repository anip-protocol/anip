---
title: Transport Overview
description: ANIP supports HTTP, stdio, and gRPC — same capabilities, multiple wire formats.
---

# Transport Bindings

ANIP is transport-agnostic. The same capabilities, permissions, and audit model work across multiple wire formats. You write capabilities once; the runtime handles the protocol over whichever transport you choose.

## Available transports

| Transport | Wire format | Runtimes | Best for |
|-----------|------------|----------|----------|
| [HTTP](/docs/transports/http) | REST-like endpoints | All 5 | Web services, browsers, Studio |
| [stdio](/docs/transports/stdio) | JSON-RPC 2.0 on stdin/stdout | All 5 | CLI tools, local agents, subprocess communication |
| [gRPC](/docs/transports/grpc) | Protobuf over HTTP/2 | Python, Go | High-performance services, polyglot environments |

All transports share the same semantic model — discovery, manifest, tokens, permissions, invoke, audit, checkpoints. The transport layer only changes how messages are framed and delivered.

## Choosing a transport

**HTTP** is the default. Start here. It works with browsers, Studio, curl, and any HTTP client. All runtimes support it, and all interface adapters (REST, GraphQL, MCP) mount on HTTP.

**stdio** is for local process communication — when an agent launches the service as a subprocess and communicates over stdin/stdout. Common in CLI tools and IDE integrations.

**gRPC** is for performance-sensitive environments where protobuf serialization and HTTP/2 multiplexing matter. Currently available in Python and Go, with Java, C#, and TypeScript planned.

## Transport and adapters are different things

Transports (HTTP, stdio, gRPC) are how the ANIP protocol itself is carried. Interface adapters (REST, GraphQL, MCP) are additional surfaces mounted alongside ANIP on the same service.

A single service can expose:
- Native ANIP over HTTP
- Native ANIP over stdio
- REST adapter (auto-generated OpenAPI + Swagger UI)
- GraphQL adapter (auto-generated SDL)
- MCP adapter (Streamable HTTP)

All from the same capability definitions.
