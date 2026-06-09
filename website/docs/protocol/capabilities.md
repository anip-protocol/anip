---
title: Capability Declaration
description: How ANIP capabilities define the execution contract between agents and services.
---

# Capability Declaration

ANIP is capability-first, not endpoint-first. Instead of documenting HTTP routes and hoping agents figure out what they do, ANIP services declare capabilities with their full execution context — what they do, what they cost, what authority they require, and what side effects they produce.

## What a capability declares

Every capability in the manifest declares the behavior surface that agents and generated services should trust. In current ANIP, that means more than a name and JSON schema:

| Field | Purpose | Example |
|-------|---------|---------|
| `name` | Unique identifier | `"search_flights"` |
| `kind` | Whether the capability is directly executed or service-composed | `"atomic"` or `"composed"` |
| `description` | What it does (for agents and humans) | `"Search available flights"` |
| `inputs` | Required and optional parameters, including resolution behavior | `[{ name: "origin", type: "airport_code", required: true }]` |
| `output` | Return shape | `{ type: "flight_list", fields: ["number", "price"] }` |
| `side_effect` | Read, write, transactional, or irreversible | `{ type: "read" }` |
| `minimum_scope` | Required delegation scope | `["travel.search"]` |
| `cost` | Financial and compute cost hints | `{ certainty: "estimated", financial: { currency: "USD", range_min: 200, range_max: 800 } }` |
| `business_effects` | What the capability produces and explicitly does not produce | `{ produces: ["content.summary"], does_not_produce: ["raw_data_export"] }` |
| `requires_binding` | Bound reference required from a prior invocation | `[{ type: "quote", field: "quote_id" }]` |
| `control_requirements` | Token-evaluable preconditions | `[{ type: "cost_ceiling", enforcement: "reject" }]` |
| `refresh_via` / `verify_via` | Same-service advisory workflow hints | `["search_flights"]` |
| `cross_service` | Cross-service handoff, refresh, verify, and follow-up hints | `{ handoff_to: [{ service: "booking", capability: "book_flight" }] }` |
| `composition` | Internal step graph for composed capabilities | `{ steps: [...], failure_policy: "stop_on_failure" }` |
| `contract_version` | Capability contract version | `"1.0"` |

The manifest may also carry implementation and consumption metadata used by Studio, Registry, generators, and runtime adapters. That metadata can help consumers, but it must not contradict the signed capability declaration.

## Business effect vocabulary

`business_effects` is a closed vocabulary for the current ANIP spec version. Studio, package build, Registry publish, and code generation reject unknown IDs instead of silently accepting model-invented synonyms.

| Effect ID | Meaning |
|-----------|---------|
| `content.draft` | Produces editable draft material. |
| `content.summary` | Produces a bounded explanation or summary. |
| `content.recommendation` | Produces ranked or suggested options. |
| `data.read` | Reads data within the declared scope. |
| `data.aggregate` | Computes grouped or summarized data. |
| `data.export` | Produces a governed data export. |
| `raw_data_export` | Exposes raw or underlying records. Usually listed in `does_not_produce` for bounded capabilities. |
| `raw_model_features` | Exposes raw model inputs, features, scoring internals, or feature-level evidence. Usually listed in `does_not_produce` for bounded scoring or ranking capabilities. |
| `system.preview_mutation` | Previews a system change without executing it. |
| `system.mutation` | Changes state in an internal system. |
| `external_dispatch` | Sends, publishes, dispatches, or contacts externally. |
| `approval.request` | Creates or requires an approval request. |
| `approval.execute` | Executes the governed action after approval. |

Use canonical IDs only. For example, use `external_dispatch`, not `external_send`; use `raw_data_export`, not `raw_conversation_export`.

## Input declarations

Inputs are part of the behavior contract. They should describe how a value is supplied, resolved, omitted, clarified, denied, or bounded.

| Field | Purpose | Example |
|-------|---------|---------|
| `name` | Parameter name | `"account_ref"` |
| `type` | Basic or domain type hint | `"string"` |
| `required` | Whether the caller must supply or resolve the value | `true` |
| `default` | Default value, if omission is allowed | `"summary"` |
| `description` | Human-readable meaning | `"Account name or account identifier"` |
| `semantic_type` | Portable planner/runtime hint | `"entity_reference"` |
| `entity_reference` | Whether this input names a concrete entity | `true` |
| `allowed_values` | Closed value list | `["summary", "stage_breakdown"]` |
| `catalog_ref` | Catalog or resolver identity, not inline data | `"gtm.account_catalog"` |
| `input_meanings` | Optional explanation for consumers | `{ business_scope: "account selection" }` |
| `resolution` | v0.24 resolution policy | `{ mode: "backend_resolved", resolver_ref: "gtm.account_catalog" }` |

Example:

```json
{
  "name": "account_ref",
  "type": "string",
  "required": true,
  "description": "Account name or account identifier",
  "semantic_type": "entity_reference",
  "entity_reference": true,
  "catalog_ref": "gtm.account_catalog",
  "resolution": {
    "mode": "backend_resolved",
    "resolver_ref": "gtm.account_catalog",
    "on_missing": "clarify",
    "on_ambiguous": "clarify",
    "on_unresolved": "deny"
  }
}
```

This is what prevents contracts from drifting into either fake hardcoded catalogs or unsafe open-text guessing.

## Capability outcomes

The declaration should make it possible for a consumer to predict the allowed outcomes before invoking:

| Outcome posture | How it appears |
|-----------------|----------------|
| Available execution | Permission discovery says the token has sufficient scope and controls are satisfied. |
| Clarification | Inputs declare `resolution` behavior such as `on_missing: "clarify"` or `on_ambiguous: "clarify"`. |
| Approval required | The service returns an `approval_required` continuation before mutation. |
| Restricted | Permission discovery or invocation returns a recoverable restriction with structured resolution guidance. |
| Denied | The service refuses execution because the action is structurally disallowed. |
| Verification | `verify_via`, audit, and scenario validation define how consumers can check what happened. |

Approval is not just a string parameter. In ANIP, write-adjacent or risky behavior should stop with an approval request and continue only with a valid approval grant.

## Full manifest example

The manifest is served at `GET /anip/manifest` with a cryptographic signature in the `X-ANIP-Signature` header:

```json
{
  "manifest_metadata": {
    "version": "0.24.4",
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
      "kind": "atomic",
      "description": "Search available flights between airports",
      "contract_version": "1.0",
      "inputs": [
        {
          "name": "origin",
          "type": "airport_code",
          "required": true,
          "description": "Departure airport",
          "semantic_type": "location_reference",
          "entity_reference": true,
          "resolution": {
            "mode": "backend_resolved",
            "resolver_ref": "travel.airport_catalog",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "name": "destination",
          "type": "airport_code",
          "required": true,
          "description": "Arrival airport",
          "semantic_type": "location_reference",
          "entity_reference": true,
          "resolution": {
            "mode": "backend_resolved",
            "resolver_ref": "travel.airport_catalog",
            "on_missing": "clarify",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        },
        {
          "name": "date",
          "type": "date",
          "required": false,
          "description": "Travel date",
          "semantic_type": "time_scope",
          "resolution": {
            "mode": "clarify",
            "on_missing": "omit",
            "on_ambiguous": "clarify",
            "on_unresolved": "clarify"
          }
        }
      ],
      "output": { "type": "flight_list", "fields": ["flight_number", "origin", "destination", "price"] },
      "side_effect": { "type": "read" },
      "minimum_scope": ["travel.search"],
      "cost": { "certainty": "fixed" },
      "response_modes": ["unary"],
      "business_effects": {
        "produces": ["data.read", "content.summary"],
        "does_not_produce": ["system.mutation", "external_dispatch", "raw_data_export"]
      }
    },
    "book_flight": {
      "kind": "atomic",
      "description": "Book a flight reservation",
      "contract_version": "1.0",
      "inputs": [
        {
          "name": "quote_id",
          "type": "string",
          "required": true,
          "description": "Bound quote returned by search_flights",
          "semantic_type": "binding_reference",
          "resolution": { "mode": "explicit_only", "on_missing": "clarify" }
        },
        {
          "name": "passengers",
          "type": "integer",
          "required": false,
          "default": 1,
          "resolution": { "mode": "closed_values", "on_missing": "use_default" },
          "allowed_values": [1, 2, 3, 4, 5]
        }
      ],
      "output": { "type": "booking_confirmation", "fields": ["booking_id", "status"] },
      "side_effect": { "type": "irreversible" },
      "minimum_scope": ["travel.book"],
      "requires_binding": [
        {
          "type": "quote",
          "field": "quote_id",
          "source_capability": "search_flights",
          "max_age": "PT15M"
        }
      ],
      "control_requirements": [
        { "type": "cost_ceiling", "enforcement": "reject" },
        { "type": "stronger_delegation_required", "enforcement": "reject" }
      ],
      "cost": {
        "certainty": "estimated",
        "financial": { "currency": "USD", "range_min": 200, "range_max": 800, "typical": 420 }
      },
      "response_modes": ["unary"],
      "business_effects": {
        "produces": ["system.mutation"],
        "does_not_produce": ["raw_data_export"]
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

Cost certainty values:

| Value | Meaning |
|-------|---------|
| `fixed` | Known before invocation. |
| `estimated` | Requires a binding or quote to make budget enforcement deterministic. |
| `dynamic` | Requires an upper bound for pre-execution budget checks. |

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
| `verify_via` | string[] | Capabilities the agent should invoke to verify side effects after executing this capability (especially useful for irreversible actions) |

Both fields are optional, default to `[]`, and every name in either list MUST refer to a capability declared in the same manifest.

### When to use each hint

**`refresh_via`** — Use when the capability's success depends on a fresh artifact (quote, price lock, binding) that can become stale. An agent receiving `binding_stale` or `budget_not_enforceable` can use `refresh_via` to know exactly which capability to re-invoke for a fresh value.

```json
{
  "book_flight": {
    "refresh_via": ["search_flights"]
  }
}
```

**`verify_via`** — Use on capabilities with irreversible side effects, where an agent should verify what actually changed after execution. The hint guides the agent to confirm side effects without encoding them as hard protocol requirements.

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

## Cross-service handoff hints (v0.19)

Cross-service handoff hints extend the advisory composition model across service boundaries. Where `refresh_via` and `verify_via` reference capabilities in the same manifest, `cross_service` references capabilities on other services.

### Fields

The `cross_service` object on a capability declaration carries four optional arrays:

| Array | Type | Description |
|-------|------|-------------|
| `handoff_to` | ServiceCapabilityRef[] | Capabilities on other services this capability naturally leads into |
| `refresh_via` | ServiceCapabilityRef[] | Capabilities on other services that can refresh a stale artifact before retrying this capability |
| `verify_via` | ServiceCapabilityRef[] | Capabilities on other services that can verify side effects after executing this capability |
| `followup_via` | ServiceCapabilityRef[] | Capabilities on other services that are useful follow-up steps after this capability completes |

Each entry is a `ServiceCapabilityRef` with two required fields:

| Field | Type | Description |
|-------|------|-------------|
| `service` | string | The service identifier of the target service |
| `capability` | string | The capability name on that service |

### When to use cross_service hints

**`handoff_to`** — Use when this capability produces output that is intended as input to a capability on another service. For example, a search service that produces quotes intended for a booking service on a different ANIP endpoint.

**`refresh_via`** — Use when the capability depends on a fresh artifact (quote, price lock) that may be produced by a capability on another service. An agent receiving `binding_stale` can follow this hint to refresh from the upstream service.

**`verify_via`** — Use on capabilities with irreversible side effects where a capability on another service can confirm the side effect occurred correctly.

**`followup_via`** — Use when this capability naturally triggers a subsequent step on another service as part of a multi-service workflow.

### Example

```json
{
  "search_flights": {
    "description": "Search available flights",
    "side_effect": { "type": "read" },
    "cross_service": {
      "handoff_to": [
        { "service": "travel-booking", "capability": "book_flight" }
      ]
    }
  },
  "book_flight": {
    "description": "Book a confirmed flight reservation",
    "side_effect": { "type": "irreversible" },
    "cross_service": {
      "refresh_via": [
        { "service": "travel-search", "capability": "search_flights" }
      ]
    }
  }
}
```

These hints are advisory only — the protocol does not enforce cross-service ordering. They guide agents in multi-service workflows without encoding hard protocol constraints.

## Capability composition (v0.23)

v0.23 adds protocol-visible composed capabilities. A composed capability is still one agent-facing capability, but the service declares that it owns a bounded internal step graph.

This is different from asking the agent to call several raw tools in order. The agent selects the business capability; the service owns the orchestration, empty-result policy, failure policy, and audit behavior.

```json
{
  "name": "gtm.at_risk_account_enrichment_summary",
  "kind": "composed",
  "composition": {
    "steps": [
      {
        "id": "risk",
        "capability": "gtm.account_risk_summary"
      },
      {
        "id": "enrichment",
        "capability": "gtm.account_enrichment_summary"
      }
    ],
    "input_mapping": {
      "risk": { "quarter": "$.input.quarter" },
      "enrichment": { "account_set": "$.steps.risk.output.accounts" }
    },
    "output_mapping": {
      "accounts": "$.steps.enrichment.output.accounts"
    },
    "authority_boundary": "same_service",
    "failure_policy": "stop_on_failure",
    "empty_result_policy": "return_success_no_results",
    "empty_result_output": { "accounts": [] },
    "audit_policy": {
      "link_child_invocations": true,
      "parent_task_lineage": true
    }
  }
}
```

For v0.23, composed capabilities are intentionally bounded: a composed capability invokes declared steps and records child invocation linkage. Custom implementation code may optimize execution, but it must not change the public manifest shape.

## Input resolution (v0.24)

v0.24 adds portable input-resolution metadata. This lets contracts distinguish between values that must be explicit, values that can be resolved by the backend, values derived from actor policy, and values that require clarification.

```json
{
  "name": "account_ref",
  "type": "string",
  "required": true,
  "semantic_type": "account_reference",
  "entity_reference": true,
  "resolution": {
    "mode": "backend_resolved",
    "resolver_ref": "gtm.account_catalog",
    "on_missing": "clarify",
    "on_ambiguous": "clarify",
    "on_unresolved": "clarify"
  }
}
```

Common modes:

| Mode | Meaning |
| --- | --- |
| `closed_values` | Value must be one of the declared allowed values. |
| `backend_resolved` | Service resolves the value through a declared resolver. |
| `app_selected` | Consuming application selects before invoking ANIP. |
| `actor_policy` | Value is derived from actor, tenant, or policy context. |
| `actor_policy_or_explicit` | Actor policy may derive the value, but explicit caller values are allowed when policy permits. |
| `explicit_only` | Caller must provide the value directly; runtime should not infer it. |
| `clarify` | Missing or ambiguous value should trigger clarification. |

This avoids two bad extremes: hardcoding every possible business reference in the manifest, or accepting arbitrary open text with no declared resolution behavior.

Resolution behavior values:

| Value | Meaning |
| --- | --- |
| `clarify` | Ask the caller/user for the missing or ambiguous value. |
| `use_default` | Use the declared input `default`. |
| `use_actor_scope` | Derive from actor, session, tenant, or policy scope. |
| `app_select_or_clarify` | Let the consuming app select within bounds, otherwise clarify. |
| `deny` | Deny the request. |
| `deny_or_clarify` | Deny when unsafe; clarify when recoverable. |
| `omit` | Omit an optional value when omission is safe and declared. |

Cross-field validation:

- `closed_values` requires `allowed_values`.
- `use_default` requires `default`.
- `catalog_ref` and `resolver_ref` are identifiers; they must not contain secrets.
- Runtime implementations should honor `resolution` before fallback heuristics.

## Service and package boundary

A capability declaration is portable only if the public manifest stays aligned with the signed package and service definition.

Custom code may:

- Implement declared capabilities.
- Resolve backend data through declared resolvers.
- Optimize internal execution.
- Connect to native APIs, MCP servers, databases, or semantic layers.

Custom code must not:

- Add hidden capabilities.
- Remove required inputs.
- Change `resolution.mode`.
- Change side-effect posture.
- Weaken approval policy.
- Rewrite composed capabilities as atomic in the public manifest.

For generated services, this boundary is what makes language parity and package verification meaningful.

### Same-service vs cross-service hints

| Hint type | Scope | Field |
|-----------|-------|-------|
| `refresh_via` (capability-level) | Same manifest | String array of capability names |
| `verify_via` (capability-level) | Same manifest | String array of capability names |
| `cross_service.handoff_to` | Other services | Array of `ServiceCapabilityRef` |
| `cross_service.refresh_via` | Other services | Array of `ServiceCapabilityRef` |
| `cross_service.verify_via` | Other services | Array of `ServiceCapabilityRef` |
| `cross_service.followup_via` | Other services | Array of `ServiceCapabilityRef` |

## Next steps

- **[Delegation & Permissions](/docs/protocol/delegation-permissions)** — How authority and scope work
- **[Failures, Cost & Audit](/docs/protocol/failures-cost-audit)** — Structured failures and audit logging
