# ANIP Reference Implementation — Flight Booking Service

A working demonstration of the Agent-Native Interface Protocol using the `anip-service` runtime.

See also: [TypeScript reference implementation](../anip-ts/) | [Go reference implementation](../../packages/go/examples/flights/)

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
python -m anip_flight_demo.main
```

## Test

```bash
pytest tests/ -v
```

## Additional Interfaces

The ANIP service can expose REST, GraphQL, and MCP interfaces alongside the native ANIP protocol — all auto-generated from the same capabilities, mounted on the same app.

To add these interfaces, install the corresponding packages (`anip-rest`, `anip-graphql`, `anip-mcp`) and mount them in `app.py`:

```python
from anip_rest import mount_anip_rest
from anip_graphql import mount_anip_graphql

mount_anip_rest(app, service)      # REST at /api/*
mount_anip_graphql(app, service)   # GraphQL at /graphql
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
