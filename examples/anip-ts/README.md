# ANIP Reference Implementation — Flight Booking Service (TypeScript)

A working demonstration of the Agent-Native Interface Protocol using the `@anip-dev/service` runtime.

See also: [Python reference implementation](../anip/) | [Go reference implementation](../../packages/go/examples/flights/)

## What's Here

The entire ANIP service is ~150 lines of business logic. All protocol plumbing — delegation, audit, signing, checkpoints — is handled by the service runtime.

```
src/
  app.ts                        # createANIPService + mountAnip (26 lines)
  main.ts                       # Hono server bootstrap (11 lines)
  domain/flights.ts             # ANIP-free business logic
  capabilities/search-flights.ts  # defineCapability declaration + handler
  capabilities/book-flight.ts     # defineCapability declaration + handler
tests/
  flight-service.test.ts        # Integration tests (11 tests)
```

## Setup

```bash
cd examples/anip-ts
npm install
```

## Run

```bash
npx tsx src/main.ts
```

## Test

```bash
npx vitest run
```

## Additional Interfaces

The ANIP service can expose REST, GraphQL, and MCP interfaces alongside the native ANIP protocol — all auto-generated from the same capabilities, mounted on the same app.

```typescript
import { mountAnipRest } from "@anip-dev/rest";
import { mountAnipGraphQL } from "@anip-dev/graphql";
import { mountAnipMcpHono } from "@anip-dev/mcp-hono";

await mountAnipRest(app, service);          // REST at /api/*
await mountAnipGraphQL(app, service);       // GraphQL at /graphql
await mountAnipMcpHono(app, service);       // MCP Streamable HTTP at /mcp
```

### Try it

```bash
# REST — search flights (GET for read capabilities)
curl "http://localhost:9100/api/search_flights?origin=SEA&destination=SFO&date=2026-03-10" \
  -H "Authorization: Bearer demo-human-key"

# GraphQL — search flights
curl -X POST http://localhost:9100/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo-human-key" \
  -d '{"query": "{ searchFlights(origin: \"SEA\", destination: \"SFO\", date: \"2026-03-10\") { success result } }"}'
```

## OIDC Authentication

The example app supports optional OIDC/OAuth2 authentication alongside API keys. Set the following environment variables to enable:

```bash
OIDC_ISSUER_URL=https://keycloak.example.com/realms/anip
OIDC_AUDIENCE=anip-flight-service  # defaults to service ID
# OIDC_JWKS_URL=...               # optional override
```

When configured, the service validates external OIDC JWTs and maps claims to ANIP principals (`email` → `human:{email}`, `sub` → `oidc:{sub}`). API keys continue to work alongside OIDC tokens.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/anip` | GET | Discovery document |
| `/.well-known/jwks.json` | GET | JSON Web Key Set |
| `/anip/manifest` | GET | Signed manifest (X-ANIP-Signature header) |
| `/anip/tokens` | POST | Issue delegation token |
| `/anip/permissions` | POST | Permission discovery |
| `/anip/invoke/{capability}` | POST | Invoke a capability |
| `/anip/audit` | POST | Query audit log |
| `/anip/checkpoints` | GET | List checkpoints |
| `/anip/checkpoints/{id}` | GET | Get checkpoint with proofs |

> Invocation responses from `/anip/invoke/{capability}` include `invocation_id` and `client_reference_id` fields for lineage tracking across delegation chains.
