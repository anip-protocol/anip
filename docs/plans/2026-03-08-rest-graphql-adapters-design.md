# REST/OpenAPI & GraphQL Adapters — Design Document

**Date:** 2026-03-08
**Status:** Approved

## Goal

Build REST/OpenAPI and GraphQL adapters that auto-discover any ANIP service and expose its capabilities through standard REST endpoints (with OpenAPI spec) and GraphQL schema. Both adapters in both Python and TypeScript (4 implementations total).

This removes the "one-way door" objection: enterprises can adopt ANIP for agent-native interfaces while keeping REST/GraphQL access for existing tooling. The adapters prove the concept; embedding the same logic as middleware is the production path.

## Key Decisions

| Decision | Answer |
|----------|--------|
| REST endpoint paths | ANIP-style by default (`/api/search_flights`), configurable semantic paths (`/flights/search`) |
| OpenAPI metadata | `x-anip-*` extensions for structured ANIP metadata |
| GraphQL Query vs Mutation | `read` → Query, everything else → Mutation |
| Languages | Both Python and TypeScript for both adapters |
| Architecture | Remote proxy (like MCP adapters), with docs noting SDK/middleware is the production path |

## Architecture

All adapters follow the same 3-stage pattern as the MCP adapters:

```
Traditional Client (REST/GraphQL)
        |
ANIP Adapter (discovers + translates + proxies)
        |  HTTP
Any ANIP Service
```

**Startup:** discover → fetch manifest → register root token → generate surface (routes or schema).

**Per-request:** receive request → create purpose-bound token → register → invoke ANIP capability → translate response.

### "Reference Adapter, Not Production Architecture"

Each README will clearly state: this adapter runs as a separate proxy process for demonstration. The same translation logic can be embedded as middleware directly in the ANIP service, eliminating the second process. The adapter proves interoperability; the SDK/middleware approach is the production deployment path.

## REST/OpenAPI Adapter

### Endpoints

Default (zero config):
```
POST /api/search_flights    → invokes search_flights
POST /api/book_flight       → invokes book_flight
```

With path overrides:
```
GET  /flights/search        → invokes search_flights
POST /flights/book          → invokes book_flight
```

Routing rule: `read` capabilities default to `GET` (query params), everything else to `POST` (JSON body). Overridable in config.

### OpenAPI Generation

Auto-served at `GET /openapi.json` and Swagger UI at `GET /docs`.

ANIP metadata via `x-anip-*` extensions on each operation:

```yaml
paths:
  /api/book_flight:
    post:
      summary: "Book a confirmed flight reservation"
      x-anip-side-effect: "irreversible"
      x-anip-rollback-window: "none"
      x-anip-minimum-scope: ["travel.book"]
      x-anip-financial: true
      x-anip-cost:
        certainty: "estimated"
        range_min: 280
        range_max: 500
        currency: "USD"
      x-anip-requires: ["search_flights"]
      x-anip-contract-version: "1.0"
```

### Response Format

Success:
```json
{
  "success": true,
  "result": { "booking_id": "BK-001", "total_cost": 420 },
  "cost_actual": { "amount": 420, "currency": "USD" },
  "warnings": ["IRREVERSIBLE: this action cannot be undone"]
}
```

### Failure Mapping

| ANIP Failure | HTTP Status | Body |
|---|---|---|
| `unknown_capability` | 404 | ANIPFailure object |
| `insufficient_authority` | 403 | ANIPFailure with resolution |
| `budget_exceeded` | 403 | ANIPFailure with resolution |
| `purpose_mismatch` | 403 | ANIPFailure with resolution |
| `invalid_parameters` | 400 | ANIPFailure with detail |
| `delegation_expired` | 401 | ANIPFailure with resolution |

Full ANIPFailure (including `resolution` and `retry`) always in the response body.

### Translation Loss

| ANIP Primitive | REST Adapter | What's Lost |
|---|---|---|
| Capability Declaration | Full — endpoint + OpenAPI | Nothing |
| Side-effect Typing | `x-anip-side-effect` extension | Standard clients don't read extensions |
| Delegation Chain | Simplified — single identity | Multi-hop, concurrent branches |
| Permission Discovery | Absent | Can't query before calling |
| Failure Semantics | HTTP status + ANIPFailure body | Status codes conflate failure types |
| Cost Signaling | `x-anip-cost` + `cost_actual` | Standard clients don't read extensions |
| Capability Graph | Absent | Not discoverable from spec |
| State & Session | Absent | No continuity |
| Observability | Absent | No audit access |

**When to use native ANIP instead:** These adapters simplify the delegation chain to a single identity. For read and write capabilities this is sufficient. For irreversible financial operations, native ANIP is strongly recommended — it provides purpose-bound authority, multi-hop delegation, and the ability for the service to verify *why* an action is being invoked and on whose behalf.

## GraphQL Adapter

### Schema Generation

```graphql
type Query {
  searchFlights(origin: String!, destination: String!, date: String!): SearchFlightsResult
    @anipSideEffect(type: "read", rollbackWindow: "not_applicable")
    @anipScope(scopes: ["travel.search"])
}

type Mutation {
  bookFlight(flightNumber: String!, date: String!, passengers: Int = 1): BookFlightResult
    @anipSideEffect(type: "irreversible", rollbackWindow: "none")
    @anipCost(certainty: "estimated", currency: "USD", rangeMin: 280, rangeMax: 500)
    @anipRequires(capabilities: ["searchFlights"])
    @anipScope(scopes: ["travel.book"])
}
```

Naming: `search_flights` → `searchFlights` (camelCase).
Rule: `read` → Query, everything else → Mutation.

### Custom Directives

```graphql
directive @anipSideEffect(type: String!, rollbackWindow: String) on FIELD_DEFINITION
directive @anipCost(certainty: String!, currency: String, rangeMin: Float, rangeMax: Float) on FIELD_DEFINITION
directive @anipRequires(capabilities: [String!]!) on FIELD_DEFINITION
directive @anipScope(scopes: [String!]!) on FIELD_DEFINITION
```

Visible via introspection. Standard clients ignore them, ANIP-aware clients use them.

### Result Types

Per-capability envelope:
```graphql
type BookFlightResult {
  success: Boolean!
  result: JSON
  costActual: CostActual
  failure: ANIPFailure
}
```

Shared types:
```graphql
type CostActual {
  financial: FinancialCost
  varianceFromEstimate: String
}

type ANIPFailure {
  type: String!
  detail: String!
  resolution: Resolution
  retry: Boolean!
}

type Resolution {
  action: String!
  requires: String
  grantableBy: String
}
```

### Error Handling

ANIP failures → GraphQL errors with extensions:
```json
{
  "errors": [{
    "message": "delegation chain lacks scope: travel.book",
    "path": ["bookFlight"],
    "extensions": {
      "anipType": "insufficient_authority",
      "resolution": {
        "action": "request_scope_grant",
        "requires": "travel.book",
        "grantableBy": "human:samir@anip.dev"
      },
      "retry": true
    }
  }]
}
```

### Translation Loss

| ANIP Primitive | GraphQL Adapter | What's Lost |
|---|---|---|
| Capability Declaration | Full — Query/Mutation | Nothing |
| Side-effect Typing | `@anipSideEffect` directive | Standard clients don't read directives |
| Delegation Chain | Simplified — single identity | Multi-hop, concurrent branches |
| Permission Discovery | Absent | Can't query before calling |
| Failure Semantics | `extensions.anipType` + resolution | No HTTP status semantics |
| Cost Signaling | `@anipCost` + `costActual` field | Standard clients don't read directives |
| Capability Graph | `@anipRequires` directive | Not programmatically traversable |
| State & Session | Absent | No continuity |
| Observability | Absent | No audit access |

**When to use native ANIP instead:** These adapters simplify the delegation chain to a single identity. For read and write capabilities this is sufficient. For irreversible financial operations, native ANIP is strongly recommended — it provides purpose-bound authority, multi-hop delegation, and the ability for the service to verify *why* an action is being invoked and on whose behalf.

## Project Structure

```
adapters/
├── mcp-py/            # existing
├── mcp-ts/            # existing
├── rest-py/           # FastAPI + auto-generated OpenAPI
│   ├── anip_rest_adapter/
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── discovery.py
│   │   ├── translation.py
│   │   ├── invocation.py
│   │   └── config.py
│   ├── adapter.example.yaml
│   ├── pyproject.toml
│   ├── test_adapter.py
│   └── README.md
├── rest-ts/           # Hono + openapi3-ts
│   ├── src/
│   │   ├── index.ts
│   │   ├── discovery.ts
│   │   ├── translation.ts
│   │   ├── invocation.ts
│   │   └── config.ts
│   ├── adapter.example.yaml
│   ├── package.json
│   ├── test-adapter.ts
│   └── README.md
├── graphql-py/        # FastAPI + ariadne
│   ├── anip_graphql_adapter/
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── discovery.py
│   │   ├── translation.py
│   │   ├── invocation.py
│   │   └── config.py
│   ├── adapter.example.yaml
│   ├── pyproject.toml
│   ├── test_adapter.py
│   └── README.md
└── graphql-ts/        # Hono + graphql-js
    ├── src/
    │   ├── index.ts
    │   ├── discovery.ts
    │   ├── translation.ts
    │   ├── invocation.ts
    │   └── config.ts
    ├── adapter.example.yaml
    ├── package.json
    ├── test-adapter.ts
    └── README.md
```

## Config (shared across all adapters)

```yaml
anip_service_url: "http://localhost:8000"
port: 3001

delegation:
  issuer: "human:user@example.com"
  scope: ["travel.search", "travel.book:max_$500"]
  token_ttl_minutes: 60

# REST-specific (optional)
routes:
  search_flights:
    path: "/flights/search"
    method: "GET"
  book_flight:
    path: "/flights/book"
    method: "POST"

# GraphQL-specific (optional)
graphql:
  path: "/graphql"
  playground: true
  introspection: true
```

## Testing Strategy

Each adapter includes a `test_adapter.py` / `test-adapter.ts` that:
1. Discovers the ANIP service
2. Verifies translation (routes/schema generated correctly)
3. Invokes capabilities through the adapter surface
4. Validates response format matches the adapter's contract

Cross-validation: run each adapter against both Python and TypeScript ANIP reference implementations (same as MCP adapter validation).
