# ANIP-MCP Adapter (TypeScript)

> Point it at any ANIP service. It discovers capabilities automatically and exposes them as MCP tools. Zero per-service code.

```
Agent (MCP-native)
       |
Generic ANIP-MCP Adapter
       |  (reads /.well-known/anip at startup)
Any ANIP service
```

This is the TypeScript implementation of the ANIP-MCP adapter. For full documentation on architecture, translation loss, and design decisions, see the [Python adapter README](../mcp-py/README.md) — both implementations share the same design.

## Quick Start

```bash
cd adapters/mcp-ts

# Install
npm install

# Start the ANIP reference server (in another terminal)
cd ../../examples/anip
uvicorn anip_server.main:app --port 8000

# Run the adapter
npx tsx src/index.ts --url http://localhost:8000
```

### With Claude Code

Add to your MCP config (`.claude/mcp.json` or Claude Desktop settings):

```json
{
  "mcpServers": {
    "flights": {
      "command": "npx",
      "args": ["tsx", "src/index.ts", "--url", "http://localhost:8000"]
    }
  }
}
```

## Architecture

```
adapters/mcp-ts/
├── src/
│   ├── index.ts          # MCP server + CLI entry point
│   ├── discovery.ts      # ANIP service auto-discovery
│   ├── translation.ts    # ANIP capability → MCP tool schema + descriptions
│   ├── invocation.ts     # Token request + ANIP invocation
│   └── config.ts         # Configuration loading
├── test-bridge.ts        # Integration tests
├── package.json
├── tsconfig.json
└── README.md
```

```mermaid
sequenceDiagram
    participant MCP as MCP Host
    participant Adapter as MCP Adapter
    participant ANIP as ANIP Service

    Note over Adapter,ANIP: Startup
    Adapter->>ANIP: GET /.well-known/anip
    ANIP-->>Adapter: discovery
    Adapter->>ANIP: GET /anip/manifest
    ANIP-->>Adapter: capabilities
    Note over Adapter: generate MCP tools from capabilities

    Note over MCP,ANIP: Tool Invocation
    MCP->>Adapter: tool call (search_flights, args)
    Adapter->>ANIP: POST /anip/tokens (+ API key, scoped)
    ANIP-->>Adapter: signed JWT
    Adapter->>ANIP: POST /anip/invoke/search_flights (+ JWT)
    ANIP-->>Adapter: {success, result, cost_actual}
    Adapter-->>MCP: MCP tool result (text)
```

## What Gets Lost in Translation

See the [Python adapter README](../mcp-py/README.md#what-gets-lost-in-translation) for the full translation loss table. Both implementations have the same trade-offs — ANIP's delegation chains, permission discovery, and structured failure recovery degrade when projected onto MCP's simpler tool model.
