---
title: Protocol Reference
description: Complete endpoint and schema reference for the ANIP protocol.
sidebar_position: 0
---

# Protocol Reference

This page defines every ANIP endpoint, request/response schema, and data type. It is the implementation reference — use it alongside the concept pages ([Capabilities](/docs/protocol/capabilities), [Delegation](/docs/protocol/delegation-permissions), [Failures](/docs/protocol/failures-cost-audit), [Trust](/docs/protocol/checkpoints-trust)) which explain the *why*.

## Endpoints

An ANIP HTTP service exposes 9 standard endpoints:

| Endpoint | Method | Auth | Section |
|----------|--------|------|---------|
| `/.well-known/anip` | GET | None | [Discovery](#discovery) |
| `/.well-known/jwks.json` | GET | None | [JWKS](#jwks) |
| `/anip/manifest` | GET | None | [Manifest](#manifest) |
| `/anip/tokens` | POST | Bearer | [Token Issuance](#token-issuance) |
| `/anip/permissions` | POST | Bearer | [Permission Discovery](#permission-discovery) |
| `/anip/invoke/{capability}` | POST | Bearer | [Invocation](#invocation) |
| `/anip/audit` | POST | Bearer | [Audit](#audit) |
| `/anip/checkpoints` | GET | None | [Checkpoints](#checkpoints) |
| `/anip/checkpoints/{id}` | GET | None | [Checkpoint Detail](#checkpoint-detail) |

---

## Discovery

`GET /.well-known/anip`

No authentication required. This is the entry point for any agent discovering the service.

### Response

```json
{
  "anip_discovery": {
    "version": "0.16.0",
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
      "level": "signed",
      "anchoring": { "cadence": "hourly" }
    },
    "metadata_disclosure": {
      "caller_class": "all",
      "failure_detail": "full"
    }
  }
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Protocol version (e.g., `"0.16.0"`) |
| `service_id` | string | Yes | Unique service identifier |
| `endpoints` | object | Yes | Map of operation names to URL paths |
| `capabilities` | object | Yes | Lightweight capability summaries (name → metadata) |
| `trust` | object | Yes | Trust posture: `level` (`declarative`, `signed`, `anchored`) and optional anchoring cadence |
| `metadata_disclosure` | object | No | Controls what metadata is disclosed to different caller classes |

Each capability summary in discovery includes `description`, `side_effect.type`, `minimum_scope[]`, and `financial` (boolean). The full declarations are in the manifest.

---

## JWKS

`GET /.well-known/jwks.json`

No authentication required. Returns the service's public signing keys in standard JWKS format.

### Response

```json
{
  "keys": [
    {
      "kty": "OKP",
      "crv": "Ed25519",
      "x": "dGhpcyBpcyBhIHB1YmxpYyBrZXk...",
      "kid": "primary-signing-key",
      "use": "sig"
    }
  ]
}
```

Used to verify: manifest signatures (`X-ANIP-Signature` header), delegation token JWTs, and checkpoint signatures.

---

## Manifest

`GET /anip/manifest`

No authentication required. Returns the full capability declarations with a cryptographic signature.

### Response headers

```
X-ANIP-Signature: eyJhbGciOiJFZERTQSJ9...
```

### Response body

```json
{
  "manifest_metadata": {
    "version": "0.16.0",
    "sha256": "a1b2c3d4...",
    "issued_at": "2026-03-28T10:00:00Z",
    "expires_at": "2026-03-29T10:00:00Z"
  },
  "service_identity": {
    "id": "travel-service",
    "jwks_uri": "/.well-known/jwks.json",
    "issuer_mode": "self"
  },
  "trust": {
    "level": "signed",
    "anchoring": { "cadence": "hourly" }
  },
  "capabilities": {
    "search_flights": {
      "description": "Search available flights between airports",
      "contract_version": "1.0",
      "inputs": [
        {
          "name": "origin",
          "type": "airport_code",
          "required": true,
          "description": "Departure airport (IATA code)"
        },
        {
          "name": "destination",
          "type": "airport_code",
          "required": true,
          "description": "Arrival airport (IATA code)"
        },
        {
          "name": "date",
          "type": "date",
          "required": false,
          "description": "Travel date (ISO 8601)"
        }
      ],
      "output": {
        "type": "flight_list",
        "fields": ["flight_number", "origin", "destination", "price"]
      },
      "side_effect": {
        "type": "read"
      },
      "minimum_scope": ["travel.search"],
      "cost": { "certainty": "fixed" },
      "response_modes": ["unary"],
      "observability": {
        "logged": true,
        "retention": "90d"
      }
    },
    "book_flight": {
      "description": "Book a flight reservation",
      "contract_version": "1.0",
      "inputs": [
        { "name": "flight_number", "type": "string", "required": true },
        { "name": "passengers", "type": "integer", "required": true, "default": 1 }
      ],
      "output": {
        "type": "booking_confirmation",
        "fields": ["booking_id", "status", "total_cost"]
      },
      "side_effect": {
        "type": "irreversible"
      },
      "minimum_scope": ["travel.book"],
      "cost": {
        "certainty": "estimated",
        "financial": {
          "currency": "USD",
          "range_min": 200,
          "range_max": 800,
          "typical": 420
        }
      },
      "requires": [
        { "capability": "search_flights", "reason": "must verify flight exists" }
      ],
      "response_modes": ["unary"],
      "observability": {
        "logged": true,
        "retention": "365d",
        "fields_logged": ["flight_number", "passengers"]
      }
    }
  }
}
```

### Capability declaration fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string | Yes | Human-readable description |
| `contract_version` | string | Yes | Semantic version of this capability's contract |
| `inputs` | array | Yes | Input parameter declarations (see below) |
| `output` | object | Yes | Output shape: `type` and `fields[]` |
| `side_effect` | object | Yes | Side-effect declaration (see below) |
| `minimum_scope` | string[] | Yes | Required scope strings for delegation |
| `cost` | object | No | Cost declaration (see below) |
| `requires` | array | No | Prerequisite capabilities |
| `response_modes` | string[] | No | `["unary"]`, `["streaming"]`, or `["unary", "streaming"]`. Default: `["unary"]` |
| `observability` | object | No | Logging and retention posture |

### Input field

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Parameter name |
| `type` | string | Yes | Semantic type hint (e.g., `"string"`, `"airport_code"`, `"integer"`) |
| `required` | boolean | No | Default: `true` |
| `default` | any | No | Default value if not provided |
| `description` | string | No | Human-readable description |

### Side-effect types

| Value | Meaning |
|-------|---------|
| `read` | No state change. Safe to call speculatively. |
| `write` | Reversible state change. |
| `transactional` | State change with a rollback window. Has optional `rollback_window` (duration) and `compensation` (capability name). |
| `irreversible` | Permanent state change. Cannot be undone. |

### Cost declaration

| Field | Type | Description |
|-------|------|-------------|
| `certainty` | string | `"fixed"`, `"estimated"`, or `"variable"` |
| `financial` | object | Optional: `currency`, `range_min`, `range_max`, `typical` |
| `compute` | object | Optional: `expected_duration`, resource hints |
| `determined_by` | string | Optional: what determines the cost (e.g., `"passenger_count"`) |

---

## Token Issuance

`POST /anip/tokens`

**Authentication:** Bearer token (API key for bootstrap, existing JWT for delegation).

### Request

```json
{
  "scope": ["travel.search", "travel.book"],
  "capability": "book_flight",
  "subject": "agent-007",
  "purpose_parameters": {
    "task_id": "trip-planning-2026",
    "budget_usd": 500
  },
  "ttl_hours": 2
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scope` | string[] | Yes | Requested scope strings |
| `capability` | string | No | Specific capability this token is for |
| `subject` | string | Yes (bootstrap) | Subject identifier for the delegated principal |
| `purpose_parameters` | object | No | Opaque purpose constraints (budget, task context) |
| `ttl_hours` | number | No | Token lifetime in hours. Default: 2 |

### Response

```json
{
  "issued": true,
  "token": "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9...",
  "scope": ["travel.search", "travel.book"],
  "capability": "book_flight",
  "expires_at": "2026-03-28T12:00:00Z"
}
```

### Budget constraints

The token issuance request can include a `budget` field, which the service stores as `constraints.budget` in the JWT claims:

```json
{
  "scope": ["travel.search", "travel.book"],
  "subject": "agent-007",
  "budget": {
    "currency": "USD",
    "max_amount": 500
  },
  "ttl_hours": 2
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `budget.currency` | string | Yes | ISO 4217 currency code |
| `budget.max_amount` | number | Yes | Maximum spend ceiling |

**Budget narrowing rule:** When delegating from a parent token, the child budget MUST NOT exceed the parent's budget. If the parent has `max_amount: 500`, the child cannot request `max_amount: 600`. Currency must match. If the parent has no budget, the child MAY introduce one.

### Delegation rules

- Scope can only **narrow**, never widen. A delegated token cannot have scope the parent doesn't have.
- Budget can only **narrow**, never widen. The token's `constraints.budget` is the enforceable ceiling.
- The service signs tokens with its Ed25519 key pair. Any replica with the same key material can verify them.

---

## Permission Discovery

`POST /anip/permissions`

**Authentication:** Bearer JWT delegation token.

### Request

```json
{}
```

### Response

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
      "grantable_by": "human:admin@company.com"
    }
  ],
  "denied": [
    {
      "capability": "admin_reset",
      "reason": "requires admin principal class"
    }
  ]
}
```

### Three-bucket model

| Bucket | Meaning |
|--------|---------|
| `available` | Token has sufficient scope. Fields: `capability`, `scope_match`, `constraints` |
| `restricted` | Missing a grantable scope. Fields: `capability`, `reason`, `reason_type`, `grantable_by`, `unmet_token_requirements`, `resolution_hint` |
| `denied` | Structurally impossible (wrong principal class). Fields: `capability`, `reason`, `reason_type` |

### Permission response fields — restricted entry (v0.15)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `capability` | string | Yes | Capability name |
| `reason` | string | Yes | Human-readable explanation of the restriction |
| `reason_type` | string | Yes | Machine-readable restriction category (see below) |
| `grantable_by` | string | No | Principal who can grant the missing authority |
| `unmet_token_requirements` | string[] | No | Unsatisfied `control_requirements` types |
| `resolution_hint` | string | No | Short actionable suggestion for resolving the restriction |

### Permission response fields — denied entry (v0.15)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `capability` | string | Yes | Capability name |
| `reason` | string | Yes | Human-readable explanation of the denial |
| `reason_type` | string | Yes | Machine-readable denial category (see below) |

### reason_type values

| Value | When used |
|-------|-----------|
| `insufficient_scope` | Token lacks one or more required scope strings |
| `insufficient_delegation_depth` | Delegation chain is too deep for this capability |
| `stronger_delegation_required` | Token needs explicit capability binding or tighter purpose constraints |
| `unmet_control_requirement` | Token does not satisfy a declared control requirement |
| `non_delegable` | Capability requires the direct (root) principal; delegated agents are blocked |

### Unmet token requirements (v0.14)

When a capability declares `control_requirements` with token-evaluable types (`cost_ceiling`, `stronger_delegation_required`), and the caller's token does not satisfy them, the capability appears in `restricted` with an `unmet_token_requirements` array listing the unsatisfied requirement types:

```json
{
  "restricted": [
    {
      "capability": "execute_trade",
      "reason": "missing control requirements: cost_ceiling",
      "grantable_by": "human:admin@company.com",
      "unmet_token_requirements": ["cost_ceiling"]
    }
  ]
}
```

All control requirements are token-evaluable and surfaced in permission discovery.

---

## Invocation

`POST /anip/invoke/{capability}`

**Authentication:** Bearer JWT delegation token.

### Request

```json
{
  "parameters": {
    "origin": "SEA",
    "destination": "SFO"
  },
  "client_reference_id": "task:abc/step-3",
  "task_id": "trip-planning-2026",
  "parent_invocation_id": "inv-a1b2c3d4e5f6",
  "stream": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `parameters` | object | Yes | Capability input parameters |
| `client_reference_id` | string | No | Caller-supplied correlation ID (max 256 chars), echoed in response |
| `task_id` | string | No | Task/workflow identity for grouping related invocations (max 256 chars). If the delegation token has `purpose.task_id`, must match or be omitted. |
| `parent_invocation_id` | string | No | Reference to the invocation that triggered this one (format: `inv-{hex12}`). Syntactically validated, not referentially. |
| `stream` | boolean | No | Request streaming response (SSE). Default: `false` |

### Success response (HTTP 200)

```json
{
  "success": true,
  "invocation_id": "inv-7f3a2b4c5d6e",
  "client_reference_id": "task:abc/step-3",
  "task_id": "trip-planning-2026",
  "parent_invocation_id": "inv-a1b2c3d4e5f6",
  "result": {
    "flights": [
      { "flight_number": "AA100", "price": 420 },
      { "flight_number": "DL310", "price": 280 }
    ]
  },
  "cost_actual": {
    "currency": "USD",
    "amount": 0
  }
}
```

### Failure response (HTTP 4xx)

```json
{
  "success": false,
  "invocation_id": "inv-8b2f4a7c9d0e",
  "task_id": "trip-planning-2026",
  "parent_invocation_id": "inv-a1b2c3d4e5f6",
  "client_reference_id": "task:abc/step-3",
  "failure": {
    "type": "budget_exceeded",
    "detail": "Requested booking costs $487.00 which exceeds the delegated budget of $200.00",
    "retry": false,
    "resolution": {
      "action": "request_budget_increase",
      "requires": "higher_budget_delegation",
      "grantable_by": "human:manager@company.com",
      "estimated_availability": "immediate"
    }
  }
}
```

### Response fields

| Field | Type | Always present | Description |
|-------|------|---------------|-------------|
| `success` | boolean | Yes | Whether the invocation succeeded |
| `invocation_id` | string | Yes | Server-generated unique ID (`inv_{hex12}`) |
| `client_reference_id` | string | If provided in request | Echoed caller correlation ID |
| `task_id` | string | If provided or from token purpose | Task/workflow identity |
| `parent_invocation_id` | string | If provided in request | Echoed parent invocation reference |
| `result` | object | On success | Capability-specific result data |
| `cost_actual` | object | If capability has financial cost | `currency` and `amount` |
| `failure` | object | On failure | Structured failure (see below) |

### Budget enforcement (v0.14)

The service enforces budget constraints from the delegation token's `constraints.budget` **before** executing the handler. Budget enforcement is pre-execution and deterministic — there is no post-execution "blessed overspend."

The check amount depends on cost certainty and whether a binding is present:

| Cost certainty | Binding present? | Check amount | Failure on exceed |
|----------------|-----------------|--------------|-------------------|
| `fixed` | N/A | `cost.financial.amount` | `budget_exceeded` |
| `estimated` | Yes (via `requires_binding`) | Bound price | `budget_exceeded` |
| `estimated` | No | N/A — reject immediately | `budget_not_enforceable` |
| `dynamic` | N/A | `cost.financial.upper_bound` | `budget_exceeded` |

If the token budget's currency does not match the capability's `cost.financial.currency`, the service rejects with `budget_currency_mismatch`.

When a budget was evaluated (success or failure), the response includes a `budget_context` object:

```json
{
  "budget_context": {
    "budget_max": 500,
    "budget_currency": "USD",
    "cost_check_amount": 280,
    "cost_certainty": "estimated"
  }
}
```

### ANIPFailure schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Machine-readable failure category (e.g., `insufficient_scope`, `budget_exceeded`, `rate_limited`) |
| `detail` | string | Yes | Human-readable explanation |
| `retry` | boolean | Yes | Whether retrying the same call might succeed. Default: `true` |
| `resolution` | object | Yes | Recovery guidance (see below) |

### Resolution schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | string | Yes | What to do (e.g., `request_broader_scope`, `request_budget_increase`, `wait_and_retry`) |
| `recovery_class` | string | Yes | Coarse recovery strategy (see vocabulary below). Advisory — does not override `retry`. |
| `requires` | string | No | What's needed to resolve |
| `grantable_by` | string | No | Who can grant what's needed (principal identifier) |
| `estimated_availability` | string | No | How soon resolution is possible (e.g., `immediate`, `24h`) |

#### recovery_class vocabulary (v0.16)

| `recovery_class` | Meaning |
|---|---|
| `retry_now` | Retry immediately — no external change required. |
| `wait_then_retry` | Wait for a time-bounded condition, then retry. |
| `refresh_then_retry` | Refresh a local artifact (binding, quote, token) and retry. |
| `redelegation_then_retry` | Obtain a new or modified delegation token, then retry. |
| `revalidate_then_retry` | Re-fetch and validate service-side state before retrying. |
| `terminal` | No automated recovery — requires human escalation. Always paired with `retry: false`. |

### Failure types — authority (v0.15)

| Type | When | Retry | Typical resolution | `recovery_class` |
|------|------|-------|--------------------|-----------------|
| `non_delegable_action` | Capability requires the root principal; a delegated agent attempted it | No | `invoke_as_root_principal` — the human must invoke directly | `terminal` |

### Canonical resolution actions (v0.16)

Five new canonical `resolution.action` values added in v0.16, completing the full action vocabulary:

| `resolution.action` | `recovery_class` | When used |
|---------------------|-----------------|-----------|
| `retry_now` | `retry_now` | Transient condition; safe to retry immediately without any change |
| `provide_credentials` | `retry_now` | Credentials are missing or need refreshing but no delegation change is required |
| `wait_and_retry` | `wait_then_retry` | Rate-limit, cooldown, or time-bounded unavailability |
| `revalidate_state` | `revalidate_then_retry` | Service-side state has changed; re-fetch and verify before retrying |
| `check_manifest` | `revalidate_then_retry` | Capability graph or manifest may be stale; re-fetch manifest and retry |

### Failure types — budget, binding, and control (v0.14)

| Type | When | Retry | Typical resolution | `recovery_class` |
|------|------|-------|--------------------|-----------------|
| `budget_exceeded` | Cost exceeds the delegated budget | No | `request_budget_increase` — obtain a higher budget delegation | `redelegation_then_retry` |
| `budget_currency_mismatch` | Budget and cost currencies differ | No | `obtain_matching_currency` — re-delegate with matching currency | `redelegation_then_retry` |
| `budget_not_enforceable` | Estimated cost with no binding to pin a price | No | `obtain_quote_first` — invoke the source capability to get a bound price | `refresh_then_retry` |
| `binding_missing` | Required binding field absent from parameters | No | `obtain_binding` — invoke the source capability first | `refresh_then_retry` |
| `binding_stale` | Binding exceeded `max_age` | Yes | `refresh_binding` — re-invoke the source capability for a fresh quote | `refresh_then_retry` |
| `control_requirement_unsatisfied` | A declared control requirement is not met | No | Depends on requirement type (e.g., obtain budget delegation for `cost_ceiling`) | `redelegation_then_retry` |

---

## Audit

`POST /anip/audit`

**Authentication:** Bearer token. Results are scoped to the root principal of the caller's delegation chain — a principal can only see its own audit trail.

### Request (query parameters)

| Parameter | Type | Description |
|-----------|------|-------------|
| `capability` | string | Filter by capability name |
| `since` | string | ISO 8601 timestamp — entries after this time |
| `invocation_id` | string | Filter by specific invocation |
| `client_reference_id` | string | Filter by caller correlation ID |
| `task_id` | string | Filter by task identity |
| `parent_invocation_id` | string | Filter by parent invocation |
| `limit` | integer | Maximum entries to return |

### Response

```json
{
  "entries": [
    {
      "invocation_id": "inv_7f3a2b4c5d6e",
      "capability": "search_flights",
      "actor_key": "agent:booking-bot",
      "root_principal": "human:demo@example.com",
      "event_class": "low_risk_success",
      "success": true,
      "client_reference_id": "task:abc/step-3",
      "task_id": "trip-planning-2026",
      "parent_invocation_id": "inv-a1b2c3d4e5f6",
      "timestamp": "2026-03-28T10:30:00Z"
    }
  ]
}
```

### Event classification

| Class | When used |
|-------|-----------|
| `low_risk_success` | Read capability succeeded |
| `high_risk_success` | Write/irreversible/financial capability succeeded |
| `low_risk_failure` | Read capability failed |
| `high_risk_failure` | Write/irreversible/financial capability failed |

---

## Checkpoints

`GET /anip/checkpoints`

No authentication required.

### Query parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Maximum checkpoints to return. Default: 20 |

### Response

```json
{
  "checkpoints": [
    {
      "checkpoint_id": "cp_a1b2c3",
      "sequence": 42,
      "merkle_root": "sha256:7d3f8a...",
      "entry_count": 150,
      "created_at": "2026-03-28T11:00:00Z",
      "signature": "eyJhbGciOi..."
    }
  ]
}
```

## Checkpoint Detail

`GET /anip/checkpoints/{id}`

Returns a single checkpoint with optional consistency proof fields.

### Response

```json
{
  "checkpoint_id": "cp_a1b2c3",
  "sequence": 42,
  "merkle_root": "sha256:7d3f8a...",
  "entry_count": 150,
  "created_at": "2026-03-28T11:00:00Z",
  "signature": "eyJhbGciOi...",
  "tree_size": 150,
  "tree_head": "sha256:7d3f8a..."
}
```

---

## JSON Schema

Machine-readable JSON Schema definitions are maintained alongside the spec:

- [`schema/anip.schema.json`](https://github.com/anip-protocol/anip/blob/main/schema/anip.schema.json) — All ANIP types: `DelegationToken`, `CapabilityDeclaration`, `PermissionResponse`, `InvokeRequest`, `InvokeResponse`, `CostActual`, `ANIPFailure`, `ResponseMode`, `StreamSummary`
- [`schema/discovery.schema.json`](https://github.com/anip-protocol/anip/blob/main/schema/discovery.schema.json) — Discovery document schema

The spec ([SPEC.md](https://github.com/anip-protocol/anip/blob/main/SPEC.md)) is authoritative for semantics. The schemas are authoritative for structure.
