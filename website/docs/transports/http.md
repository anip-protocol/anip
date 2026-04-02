---
title: HTTP
description: The HTTP binding is ANIP's default transport, implemented across all five runtimes.
---

# HTTP Transport

HTTP is the default ANIP transport binding, implemented across all five runtimes (TypeScript, Python, Java, Go, C#). It maps ANIP's protocol operations to standard HTTP endpoints.

## Endpoint reference

An ANIP HTTP service exposes the following endpoints:

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/.well-known/anip` | GET | No | Discovery document |
| `/.well-known/jwks.json` | GET | No | JSON Web Key Set |
| `/anip/manifest` | GET | No | Signed capability manifest |
| `/anip/tokens` | POST | Bearer | Issue delegation token |
| `/anip/permissions` | POST | Bearer | Discover permissions |
| `/anip/invoke/{capability}` | POST | Bearer | Invoke a capability |
| `/anip/audit` | POST | Bearer | Query audit log |
| `/anip/checkpoints` | GET | No | List checkpoints |
| `/anip/checkpoints/{id}` | GET | No | Get checkpoint detail |

## Discovery

```bash
curl https://service.example/.well-known/anip
```

```json
{
  "anip_discovery": {
    "version": "0.19.0",
    "service_id": "travel-service",
    "endpoints": {
      "manifest": "/anip/manifest",
      "tokens": "/anip/tokens",
      "permissions": "/anip/permissions",
      "invoke": "/anip/invoke/{capability}",
      "audit": "/anip/audit",
      "checkpoints": "/anip/checkpoints"
    },
    "capabilities": {
      "search_flights": {
        "side_effect": { "type": "read" },
        "minimum_scope": ["travel.search"]
      }
    },
    "trust": { "level": "signed" }
  }
}
```

## Token issuance

```bash
curl -X POST https://service.example/anip/tokens \
  -H "Authorization: Bearer <api-key-or-oidc-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "scope": ["travel.search"],
    "capability": "search_flights",
    "purpose_parameters": { "task_id": "planning-trip" }
  }'
```

Returns a signed JWT delegation token scoped to the requested capability and scope.

## Invocation

```bash
curl -X POST https://service.example/anip/invoke/search_flights \
  -H "Authorization: Bearer <delegation-token>" \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"origin": "SEA", "destination": "SFO"}}'
```

### Success response (HTTP 200)

```json
{
  "success": true,
  "invocation_id": "inv_7f3a2b",
  "result": {
    "flights": [
      { "flight_number": "AA100", "price": 420 },
      { "flight_number": "DL310", "price": 280 }
    ]
  }
}
```

### Failure response (HTTP 4xx)

ANIP returns structured failures as JSON bodies with non-2xx status codes. The body always contains the full failure object:

```json
{
  "success": false,
  "invocation_id": "inv_8b2f4a",
  "failure": {
    "type": "budget_exceeded",
    "detail": "Exceeds delegated budget of $200.00",
    "retry": false,
    "resolution": {
      "action": "request_budget_increase",
      "grantable_by": "human:manager@company.com"
    }
  }
}
```

## Authentication

ANIP HTTP uses bearer token authentication via the `Authorization` header:

```
Authorization: Bearer <token>
```

The token can be:
- An API key (for bootstrap/human access)
- An OIDC/OAuth2 JWT (for federated identity)
- An ANIP delegation token (for agent access)

The service's `authenticate` function resolves the bearer to a principal identity.

## Manifest signature

The manifest response includes a cryptographic signature:

```
GET /anip/manifest

HTTP/1.1 200 OK
Content-Type: application/json
X-ANIP-Signature: eyJhbGciOiJFZERTQSJ9...

{ "manifest_metadata": { ... }, "capabilities": { ... } }
```

## CORS

When ANIP Studio or other browser-based clients access the service from a different origin, the service must enable CORS:

```python
from starlette.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-ANIP-Signature"],
)
```

## Next steps

- **[stdio Transport](/docs/transports/stdio)** — JSON-RPC 2.0 over stdin/stdout
- **[gRPC Transport](/docs/transports/grpc)** — Shared proto, Python + Go
