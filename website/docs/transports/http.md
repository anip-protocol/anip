---
title: HTTP
description: The HTTP binding is ANIP's default transport, implemented across all five runtimes.
---

# HTTP Transport

HTTP is the default ANIP transport binding, implemented across all five runtimes: Python, TypeScript, Go, Java, and C#.

It maps native ANIP protocol operations to standard HTTP endpoints. The HTTP binding does not change ANIP semantics: capabilities, permissions, approval grants, structured failures, budget enforcement, lineage, audit, and checkpoints are carried directly as protocol operations. HTTP and stdio are the complete generated transport paths today; gRPC currently covers the Python/Go core binding and trails the newest approval-grant workflow.

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
| `/anip/approval_grants` | POST | Bearer | Issue approval grant for an approved continuation |
| `/anip/audit` | POST | Bearer | Query audit log |
| `/anip/checkpoints` | GET | No | List checkpoints |
| `/anip/checkpoints/{id}` | GET | No | Get checkpoint detail |

`/anip/approval_grants` is required only for services that can emit `approval_required` failures.

Some implementations may expose optional development, health, or adapter endpoints. A service should only advertise endpoints it actually implements in discovery.

## Discovery

```bash
curl https://service.example/.well-known/anip
```

```json
{
  "anip_discovery": {
    "version": "0.24.4",
    "service_id": "travel-service",
    "endpoints": {
      "manifest": "/anip/manifest",
      "tokens": "/anip/tokens",
      "permissions": "/anip/permissions",
      "invoke": "/anip/invoke/{capability}",
      "approval_grants": "/anip/approval_grants",
      "audit": "/anip/audit",
      "checkpoints": "/anip/checkpoints"
    },
    "capabilities": {
      "search_flights": {
        "description": "Search available flights",
        "side_effect": { "type": "read" },
        "minimum_scope": ["travel.search"],
        "financial": false
      },
      "book_flight": {
        "description": "Book a flight reservation",
        "side_effect": { "type": "irreversible" },
        "minimum_scope": ["travel.book"],
        "financial": true
      }
    },
    "trust": {
      "level": "signed"
    }
  }
}
```

Discovery is intentionally lightweight. Agents fetch `/anip/manifest` for the full signed capability declarations.

## Token issuance

```bash
curl -X POST https://service.example/anip/tokens \
  -H "Authorization: Bearer <api-key-or-oidc-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "scope": ["travel.search"],
    "capability": "search_flights",
    "subject": "agent-007",
    "purpose_parameters": { "task_id": "planning-trip" }
  }'
```

Returns a signed JWT delegation token scoped to the requested capability, scope, purpose, and optional budget.

```json
{
  "issued": true,
  "token_id": "tok_root_001",
  "token": "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9...",
  "scope": ["travel.search"],
  "capability": "search_flights",
  "task_id": "planning-trip",
  "expires_at": "2026-03-28T12:00:00Z"
}
```

Root issuance uses a bootstrap credential such as an API key or OIDC token. Delegated issuance uses an existing ANIP delegation token and includes `parent_token`.

## Permission discovery

Before invoking, an agent can ask what its token is allowed to do:

```bash
curl -X POST https://service.example/anip/permissions \
  -H "Authorization: Bearer <delegation-token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

```json
{
  "available": [
    {
      "capability": "search_flights",
      "scope_match": "travel.search",
      "constraints": {}
    }
  ],
  "restricted": [
    {
      "capability": "book_flight",
      "reason": "missing scope: travel.book",
      "reason_type": "insufficient_scope",
      "grantable_by": "human:admin@company.com",
      "resolution_hint": "request_broader_scope"
    }
  ],
  "denied": []
}
```

Permission discovery is not a substitute for invocation-time checks. Invocation still validates inputs, purpose, budget, approval grants, bindings, and runtime policy.

## Invocation

```bash
curl -X POST https://service.example/anip/invoke/search_flights \
  -H "Authorization: Bearer <delegation-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "origin": "SEA",
      "destination": "SFO"
    },
    "client_reference_id": "task:abc/step-3",
    "task_id": "planning-trip",
    "stream": false
  }'
```

### Success response (HTTP 200)

```json
{
  "success": true,
  "invocation_id": "inv-7f3a2b4c5d6e",
  "client_reference_id": "task:abc/step-3",
  "task_id": "planning-trip",
  "result": {
    "flights": [
      { "flight_number": "AA100", "price": 420 },
      { "flight_number": "DL310", "price": 280 }
    ]
  },
  "cost_actual": {
    "financial": {
      "currency": "USD",
      "amount": 0
    }
  }
}
```

### Failure response (HTTP 4xx)

Transport-level authentication failures can still be HTTP `401`. Once a request reaches the ANIP invocation boundary, authorization, budget, purpose, approval, and capability failures are returned as structured ANIP failure objects:

```json
{
  "success": false,
  "invocation_id": "inv-8b2f4a7c9d0e",
  "client_reference_id": "task:abc/step-3",
  "task_id": "planning-trip",
  "failure": {
    "type": "budget_exceeded",
    "detail": "Capability cost $487 exceeds delegated budget of $200",
    "retry": false,
    "resolution": {
      "action": "request_budget_increase",
      "recovery_class": "redelegation_then_retry",
      "requires": "delegation token with higher budget",
      "grantable_by": "human:manager@company.com",
      "estimated_availability": "immediate"
    }
  },
  "budget_context": {
    "budget_currency": "USD",
    "budget_max": 200,
    "cost_check_amount": 487,
    "cost_certainty": "fixed",
    "within_budget": false
  }
}
```

### Approval continuation

Capabilities that require confirmation before mutation return `approval_required` instead of performing the side effect.

```json
{
  "success": false,
  "invocation_id": "inv-9c1e2f3a4b5d",
  "failure": {
    "type": "approval_required",
    "detail": "Posting this message requires approval.",
    "retry": false,
    "resolution": {
      "action": "request_approval",
      "recovery_class": "wait_then_retry"
    },
    "approval_required": {
      "approval_request_id": "apr_123",
      "preview_digest": "sha256:...",
      "requested_parameters_digest": "sha256:...",
      "grant_policy": {
        "allowed_grant_types": ["one_time", "session_bound"],
        "default_grant_type": "one_time",
        "expires_in_seconds": 900,
        "max_uses": 1
      }
    }
  }
}
```

After an authorized approver issues a grant through `/anip/approval_grants`, the agent continues by invoking the same capability with the grant ID:

```json
{
  "approval_grant": "grant_456",
  "parameters": {
    "channel_id": "C0123456789",
    "text": "Approved incident update"
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

The manifest response includes a cryptographic signature. Clients verify this signature using the service JWKS:

```
GET /anip/manifest

HTTP/1.1 200 OK
Content-Type: application/json
X-ANIP-Signature: eyJhbGciOiJFZERTQSJ9...

{ "manifest_metadata": { ... }, "capabilities": { ... } }
```

The manifest is the signed source of capability truth. Generated REST, GraphQL, and MCP surfaces should be treated as derived interfaces, not as replacements for the manifest.

## Audit and checkpoints

HTTP audit queries use `POST /anip/audit` with bearer auth and optional query parameters:

```bash
curl -X POST "https://service.example/anip/audit?task_id=planning-trip&limit=10" \
  -H "Authorization: Bearer <delegation-token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Checkpoints are public verification endpoints:

```bash
curl https://service.example/anip/checkpoints
curl https://service.example/anip/checkpoints/chk-2026-05-23T00:00:00Z
```

Audit answers what happened. Checkpoints help prove that audit history was not silently rewritten.

## Generated HTTP hosts

`anip generate` emits HTTP runners for all five targets by default:

```bash
anip generate \
  --package my-service@0.2.0 \
  --target python \
  --transport http \
  --output ./generated/my-service
```

Framework variants are generation-time choices:

| Target | HTTP frameworks |
|--------|-----------------|
| Python | FastAPI |
| TypeScript | Hono, Express, Fastify |
| Go | `net/http`, Gin |
| Java | Spring Boot, Quarkus |
| C# | ASP.NET Core |

The framework affects host code, not capability semantics.

## CORS

When ANIP Studio or other browser-based clients access the service from a different origin, the service must enable CORS:

```python
from starlette.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://studio.example.com"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-ANIP-Signature"],
)
```

## Next steps

- [Transport overview](/docs/transports/overview)
- [stdio transport](/docs/transports/stdio)
- [gRPC transport](/docs/transports/grpc)
- [Protocol reference](/docs/protocol/reference)
- [Authentication](/docs/protocol/authentication)
