# ANIP Reference Implementation — Flight Booking Service (TypeScript)

A working demonstration of the Agent-Native Interface Protocol using the `@anip/service` runtime.

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

## Adapter Surfaces

The ANIP server can be accessed through REST, GraphQL, and MCP adapters — all auto-generated, zero per-service code. This example uses **default routes** with no overrides, proving the adapters work generically against any ANIP service.

### Start the adapters (each in a separate terminal)

```bash
# REST adapter — generic routes: GET /api/search_flights, POST /api/book_flight
cd adapters/rest-ts
npm install
ANIP_ADAPTER_CONFIG=../../examples/anip-ts/rest-adapter.yaml npx tsx src/index.ts
# → http://localhost:3003/openapi.json

# GraphQL adapter
cd adapters/graphql-ts
npm install
ANIP_ADAPTER_CONFIG=../../examples/anip-ts/graphql-adapter.yaml npx tsx src/index.ts
# → http://localhost:3004/graphql
# → http://localhost:3004/schema.graphql
```

### Try it

```bash
# REST — search flights via default generic route
curl "http://localhost:3003/api/search_flights?origin=SEA&destination=SFO&date=2026-03-10"

# REST — book flight
curl -X POST http://localhost:3003/api/book_flight \
  -H "Content-Type: application/json" \
  -d '{"flight_number": "AA100", "date": "2026-03-10", "passengers": 1}'

# GraphQL — search flights
curl -X POST http://localhost:3004/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ searchFlights(origin: \"SEA\", destination: \"SFO\", date: \"2026-03-10\") { success result } }"}'
```

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
