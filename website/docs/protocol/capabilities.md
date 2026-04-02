---
title: Capability Declaration
description: How ANIP capabilities define the execution contract between agents and services.
---

# Capability Declaration

ANIP is capability-first, not endpoint-first. Instead of documenting HTTP routes and hoping agents figure out what they do, ANIP services declare capabilities with their full execution context — what they do, what they cost, what authority they require, and what side effects they produce.

## What a capability declares

Every capability in the manifest includes:

| Field | Purpose | Example |
|-------|---------|---------|
| `name` | Unique identifier | `"search_flights"` |
| `description` | What it does (for agents and humans) | `"Search available flights"` |
| `inputs` | Required and optional parameters | `[{ name: "origin", type: "airport_code" }]` |
| `output` | Return shape | `{ type: "flight_list", fields: ["number", "price"] }` |
| `side_effect` | Read, write, transactional, or irreversible | `{ type: "read" }` |
| `minimum_scope` | Required delegation scope | `["travel.search"]` |
| `cost` | Financial and compute cost hints | `{ certainty: "estimated", financial: { currency: "USD", range_min: 200, range_max: 800 } }` |
| `contract_version` | Capability contract version | `"1.0"` |

## Full manifest example

The manifest is served at `GET /anip/manifest` with a cryptographic signature in the `X-ANIP-Signature` header:

```json
{
  "manifest_metadata": {
    "version": "0.16.0",
    "sha256": "a1b2c3...",
    "issued_at": "2026-03-27T10:00:00Z"
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
        { "name": "origin", "type": "airport_code", "required": true, "description": "Departure airport" },
        { "name": "destination", "type": "airport_code", "required": true, "description": "Arrival airport" },
        { "name": "date", "type": "date", "required": false, "description": "Travel date" }
      ],
      "output": { "type": "flight_list", "fields": ["flight_number", "origin", "destination", "price"] },
      "side_effect": { "type": "read" },
      "minimum_scope": ["travel.search"],
      "cost": { "certainty": "fixed" }
    },
    "book_flight": {
      "description": "Book a flight reservation",
      "contract_version": "1.0",
      "inputs": [
        { "name": "flight_number", "type": "string", "required": true },
        { "name": "passengers", "type": "integer", "required": true, "default": 1 }
      ],
      "output": { "type": "booking_confirmation", "fields": ["booking_id", "status"] },
      "side_effect": { "type": "irreversible" },
      "minimum_scope": ["travel.book"],
      "cost": {
        "certainty": "estimated",
        "financial": { "currency": "USD", "range_min": 200, "range_max": 800, "typical": 420 }
      }
    }
  }
}
```

## Side-effect types

Side-effect declaration is one of ANIP's most important features. It tells the agent what kind of change a capability produces before it acts:

| Type | Meaning | Agent behavior |
|------|---------|----------------|
| `read` | No state change | Safe to call speculatively |
| `write` | Produces reversible state change | Agent should confirm intent |
| `transactional` | State change with rollback window | Agent can undo within time limit |
| `irreversible` | Permanent state change | Agent must have explicit authorization |

This is fundamentally different from REST, where an agent must infer from HTTP methods (GET/POST/PUT/DELETE) what side effects might occur — and those conventions aren't enforced.

## Cost declaration

Capabilities can declare expected costs before invocation:

```json
{
  "cost": {
    "certainty": "estimated",
    "financial": {
      "currency": "USD",
      "range_min": 200,
      "range_max": 800,
      "typical": 420
    },
    "compute": {
      "expected_duration": "2s"
    }
  }
}
```

After invocation, the actual cost is returned in the response:

```json
{
  "success": true,
  "cost_actual": { "currency": "USD", "amount": 487.00 },
  "result": { "booking_id": "BK-7291" }
}
```

This lets agents compare alternatives and stay within budget constraints before committing to an action.

## Capability graph

Capabilities can declare prerequisites and compensation paths:

```json
{
  "book_flight": {
    "requires": [
      { "capability": "check_availability", "reason": "must verify seat availability" }
    ],
    "side_effect": {
      "type": "transactional",
      "rollback_window": "24h",
      "compensation": "cancel_booking"
    }
  }
}
```

This helps agents navigate multi-step workflows without hand-authored instructions — the service itself declares the dependency graph.

## Binding requirements (v0.14)

Binding requirements declare that a capability needs a **bound reference** from a prior invocation before it can execute. This is the protocol mechanism for multi-step workflows like search, quote, then book — where the booking price should be locked to what the agent was quoted.

### When to use binding

Binding is useful when a capability's cost depends on a prior step's output. Without binding, a capability with `estimated` cost and a budget constraint cannot be enforced — the service has no deterministic price to check against the budget. With binding, the quoted price becomes the check amount.

### Declaration

A capability declares `requires_binding` in the manifest:

```json
{
  "book_flight": {
    "description": "Book a flight reservation",
    "requires_binding": [
      {
        "type": "quote",
        "field": "quote_id",
        "source_capability": "search_flights",
        "max_age": "PT15M"
      }
    ]
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Binding type (e.g., `"quote"`, `"reservation"`) |
| `field` | string | Yes | Parameter name that must be present at invocation |
| `source_capability` | string | No | Informational — which capability produces this binding |
| `max_age` | string (ISO 8601 duration) | No | Maximum age before the binding is stale |

`source_capability` is informational only — the service does not validate it. It helps agents understand the expected workflow sequence.

### Enforcement

When a capability declares `requires_binding`, the service enforces at invocation time:

1. **Missing binding:** If the required `field` is absent from parameters, the service rejects with `binding_missing`.
2. **Stale binding:** If `max_age` is declared and the binding has expired, the service rejects with `binding_stale`.

### How binding reinforces budget enforcement

Binding and budget work together. For a capability with `estimated` cost:

- **Without binding:** The service cannot reliably check the budget (the actual price is unknown). The service rejects with `budget_not_enforceable`.
- **With binding:** The quoted/bound price becomes the check amount. If the bound price exceeds the budget, the service rejects with `budget_exceeded`. This makes estimated-cost capabilities budget-enforceable.

## Control requirements (v0.14)

Control requirements are explicit pre-execution conditions that a capability declares. They tell both agents and services what must be true before invocation can proceed.

All control requirements are token-evaluable — they can be checked from the delegation token alone and are surfaced in `/anip/permissions`:

| Type | Condition |
|------|-----------|
| `cost_ceiling` | The delegation token must carry `constraints.budget` |
| `stronger_delegation_required` | The token must have explicit capability binding |

### Declaration

```json
{
  "execute_trade": {
    "description": "Execute a securities trade",
    "control_requirements": [
      { "type": "cost_ceiling", "enforcement": "reject" },
      { "type": "stronger_delegation_required", "enforcement": "reject" }
    ]
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Requirement type |
| `enforcement` | string | Yes | `"reject"` in v0.14 (reject invocation if not satisfied) |

When `enforcement` is `"reject"`, the service rejects invocations that do not satisfy the requirement, returning a `control_requirement_unsatisfied` failure.

### Complete flow example

A travel service with budget-enforced booking through binding:

```
1. Agent obtains delegation token with budget: { currency: "USD", max_amount: 500 }

2. Agent invokes search_flights (read, no budget impact)
   -> Returns flights with prices, including quote_id: "q-abc123"

3. Agent invokes book_flight with parameters: { quote_id: "q-abc123" }
   -> Service checks: binding present? Yes (quote_id)
   -> Service checks: binding fresh? Yes (within PT15M)
   -> Service checks: bound price ($280) <= budget ($500)? Yes
   -> Booking succeeds, cost_actual: { currency: "USD", amount: 280 }

4. Response includes budget_context:
   { budget_max: 500, budget_currency: "USD", cost_check_amount: 280, cost_certainty: "estimated" }
```

If the bound price had been $600, the service would reject with `budget_exceeded` before executing the booking. If the quote had expired, the service would reject with `binding_stale`.

## Advisory composition hints (v0.17)

Advisory composition hints let a capability declare which other capabilities in the same manifest are naturally paired with it — without enforcing any ordering at the protocol level. These are hints for agents, not protocol constraints.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `refresh_via` | string[] | Capabilities the agent should invoke to refresh a stale or expired artifact before retrying this capability |
| `verify_via` | string[] | Capabilities the agent should invoke to verify current state before executing this capability (especially useful for irreversible actions) |

Both fields are optional, default to absent (not `[]`), and every name in either list MUST refer to a capability declared in the same manifest.

### When to use each hint

**`refresh_via`** — Use when the capability's success depends on a fresh artifact (quote, price lock, binding) that can become stale. An agent receiving `binding_stale` or `budget_not_enforceable` can use `refresh_via` to know exactly which capability to re-invoke for a fresh value.

```json
{
  "book_flight": {
    "refresh_via": ["search_flights"]
  }
}
```

**`verify_via`** — Use on capabilities with irreversible side effects, where an agent should read current state before committing. The hint guides the agent to check preconditions without encoding them as hard protocol requirements.

```json
{
  "delete_resource": {
    "verify_via": ["list_deployments"]
  }
}
```

### Same-manifest rule

All capability names in `refresh_via` and `verify_via` MUST be declared in the same manifest. References to capabilities on other services are not permitted — the hints are local to a single service's declaration graph.

### Complete example

```json
{
  "search_flights": {
    "description": "Search available flights",
    "side_effect": { "type": "read" }
  },
  "book_flight": {
    "description": "Book a confirmed flight reservation",
    "side_effect": { "type": "irreversible" },
    "refresh_via": ["search_flights"]
  }
}
```

In this example: if `book_flight` fails with `binding_stale`, an agent reading `refresh_via` knows to re-invoke `search_flights` to get a fresh quote before retrying.

## Next steps

- **[Delegation & Permissions](/docs/protocol/delegation-permissions)** — How authority and scope work
- **[Failures, Cost & Audit](/docs/protocol/failures-cost-audit)** — Structured failures and audit logging
