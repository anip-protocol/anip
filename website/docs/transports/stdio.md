---
title: stdio
description: ANIP over JSON-RPC 2.0 on stdin/stdout for local agent communication.
---

# stdio Transport

The stdio binding carries ANIP over JSON-RPC 2.0 on stdin/stdout. An agent launches the ANIP service as a subprocess and communicates without opening a network port.

## When to use stdio

- Agent spawns a local service as a subprocess (like MCP's stdio transport)
- No network port is desirable (sandboxed environments, CLI tools)
- IDE integrations where the editor manages the process lifecycle

## Wire format

Messages are JSON-RPC 2.0 objects, one per line, on stdin (client→server) and stdout (server→client):

```json
{"jsonrpc": "2.0", "id": 1, "method": "anip.discovery", "params": {}}
```

```json
{"jsonrpc": "2.0", "id": 1, "result": {"anip_discovery": {"version": "0.11.0", ...}}}
```

## Method mapping

Each ANIP operation maps to a JSON-RPC method:

| ANIP Operation | JSON-RPC Method |
|---------------|-----------------|
| Discovery | `anip.discovery` |
| Manifest | `anip.manifest` |
| JWKS | `anip.jwks` |
| Issue token | `anip.tokens` |
| Permissions | `anip.permissions` |
| Invoke | `anip.invoke` |
| Audit | `anip.audit` |
| Checkpoints | `anip.checkpoints` |

## Authentication

Since there's no HTTP header in stdio, auth is passed in the request params:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "anip.invoke",
  "params": {
    "capability": "search_flights",
    "parameters": {"origin": "SEA", "destination": "SFO"},
    "auth": {"bearer": "demo-key"}
  }
}
```

## Runtime support

Available in all five runtimes: TypeScript (`@anip/stdio`), Python (`anip-stdio`), Java (`anip-stdio`), Go (`stdioapi`), C# (`Anip.Stdio`).
