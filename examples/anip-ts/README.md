# ANIP Reference Implementation — Flight Booking Service (TypeScript)

A working demonstration of the Agent-Native Interface Protocol, built with Hono + Zod.

## Setup

```bash
cd examples/anip-ts
npm install
```

## Run

Start the server:

```bash
PORT=8001 npx tsx src/server.ts
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

# GraphQL — book flight
curl -X POST http://localhost:3004/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { bookFlight(flightNumber: \"AA100\", date: \"2026-03-10\", passengers: 1) { success result costActual { financial { amount currency } } } }"}'
```

The REST adapter auto-generates endpoints and an OpenAPI 3.1 spec with `x-anip-*` extensions. The GraphQL adapter auto-generates a schema with custom `@anip*` directives. No per-service code required — point any adapter at any ANIP service URL.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/anip/manifest` | GET | Full ANIP manifest with all capability declarations |
| `/anip/handshake` | POST | Profile compatibility check |
| `/anip/tokens` | POST | Issue or register a delegation token |
| `/anip/permissions` | POST | Permission discovery given a delegation token |
| `/anip/invoke/{capability}` | POST | Invoke a capability with delegation chain |
| `/anip/graph/{capability}` | GET | Capability prerequisite graph |
| `/anip/audit` | POST | Audit log (requires delegation token, filtered by root principal) |
