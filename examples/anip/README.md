# ANIP Reference Implementation — Flight Booking Service

A working demonstration of the Agent-Native Interface Protocol using the `anip-service` runtime.

## What's Here

The entire ANIP service is ~150 lines of business logic. All protocol plumbing — delegation, audit, signing, checkpoints — is handled by the service runtime.

```
app.py                          # ANIPService + mount_anip (26 lines)
anip_flight_demo/
  main.py                       # uvicorn bootstrap (10 lines)
  domain/flights.py             # ANIP-free business logic
  capabilities/search_flights.py  # Capability declaration + handler
  capabilities/book_flight.py     # Capability declaration + handler
tests/
  test_flight_service.py        # Integration tests (11 tests)
```

## Setup

```bash
cd examples/anip
pip install -e ".[dev]"
```

## Run

```bash
uvicorn anip_flight_demo.main:run --reload
```

## Test

```bash
pytest tests/ -v
```

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
