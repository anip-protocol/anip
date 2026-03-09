# ANIP Reference Implementation — Flight Booking Service

A working demonstration of the Agent-Native Interface Protocol.

## Setup

```bash
cd examples/anip
pip install -e .
```

## Run

Start the server:

```bash
uvicorn anip_server.main:app --reload
```

Run the demo (in a separate terminal):

```bash
python demo.py
```

## What the Demo Shows

The demo script acts as an AI agent interacting with an ANIP-compliant flight booking service. It walks through the full protocol:

1. **Profile handshake** — agent checks service compatibility before interacting
2. **Delegation chain** — human delegates to orchestrator, orchestrator delegates to booking agent (DAG structure)
3. **Permission discovery** — agent queries what it can do before trying anything
4. **Capability graph** — agent discovers prerequisites (must search before booking)
5. **Capability invocation** — search flights (read), then book (irreversible)
6. **Failure scenarios** — insufficient scope, budget exceeded, purpose mismatch — each with actionable resolution

## Adapter Surfaces

The ANIP server can be accessed through REST, GraphQL, and MCP adapters — all auto-generated, zero per-service code. This example uses **custom semantic REST routes** to demonstrate configurable path mapping.

### Start the adapters (each in a separate terminal)

```bash
# REST adapter — semantic routes: GET /flights/search, POST /flights/book
cd adapters/rest-py
pip install -e .
anip-rest-adapter --config ../../examples/anip/rest-adapter.yaml
# → http://localhost:3001/docs (Swagger UI)
# → http://localhost:3001/openapi.json

# GraphQL adapter
cd adapters/graphql-py
pip install -e .
anip-graphql-adapter --config ../../examples/anip/graphql-adapter.yaml
# → http://localhost:3002/graphql
# → http://localhost:3002/schema.graphql
```

### Try it

```bash
# REST — search flights via semantic route
curl "http://localhost:3001/flights/search?origin=SEA&destination=SFO&date=2026-03-10"

# REST — book flight
curl -X POST http://localhost:3001/flights/book \
  -H "Content-Type: application/json" \
  -d '{"flight_number": "AA100", "date": "2026-03-10", "passengers": 1}'

# GraphQL — search flights
curl -L -X POST http://localhost:3002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ searchFlights(origin: \"SEA\", destination: \"SFO\", date: \"2026-03-10\") { success result } }"}'

# GraphQL — book flight
curl -L -X POST http://localhost:3002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { bookFlight(flightNumber: \"AA100\", date: \"2026-03-10\", passengers: 1) { success result costActual { financial { amount currency } } } }"}'
```

The REST adapter's OpenAPI spec includes `x-anip-*` extensions preserving ANIP metadata. The GraphQL schema includes custom `@anipSideEffect`, `@anipCost`, `@anipRequires`, and `@anipScope` directives. Standard clients ignore these; ANIP-aware clients use them.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/anip/manifest` | GET | Full ANIP manifest with all capability declarations |
| `/anip/handshake` | POST | Profile compatibility check |
| `/anip/tokens` | POST | Register a delegation token |
| `/anip/permissions` | POST | Permission discovery given a delegation token |
| `/anip/invoke/{capability}` | POST | Invoke a capability with delegation chain |
| `/anip/graph/{capability}` | GET | Capability prerequisite graph |
| `/anip/audit` | POST | Audit log (requires delegation token, filtered by root principal) |
