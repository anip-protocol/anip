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
    "version": "0.11.0",
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

## Next steps

- **[Delegation & Permissions](/docs/protocol/delegation-permissions)** — How authority and scope work
- **[Failures, Cost & Audit](/docs/protocol/failures-cost-audit)** — Structured failures and audit logging
