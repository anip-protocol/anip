---
title: Failures, Cost, and Audit
description: Structured failures with recovery guidance, cost signaling, and protocol-level audit logging.
---

# Failures, Cost, and Audit

ANIP does not stop at "success or error." It makes failures actionable, costs predictable, and execution verifiable.

## Structured failures

When an ANIP invocation fails, the response includes structured information the agent can act on — not just an HTTP status code:

```json
{
  "success": false,
  "invocation_id": "inv_8b2f4a",
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

### Failure fields

| Field | Purpose |
|-------|---------|
| `failure.type` | Machine-readable failure category |
| `failure.detail` | Human-readable explanation |
| `failure.retry` | Whether retrying the same call might succeed |
| `failure.resolution.action` | What to do to resolve the failure |
| `failure.resolution.requires` | What's needed (scope, budget, approval) |
| `failure.resolution.grantable_by` | Who can grant what's needed |
| `failure.resolution.estimated_availability` | How soon resolution is possible |

### Why this matters

Compare these two failure experiences:

**REST API**: Agent gets `403 Forbidden`. What does that mean? Missing auth? Wrong scope? Expired token? Rate limited? The agent has to guess.

**ANIP**: Agent gets a structured failure that says "you need a higher budget, your manager can grant it, and it's available immediately." The agent can report this to the user and take specific action to resolve the block.

### v0.15 failure types

v0.15 adds `non_delegable_action` for capabilities that require the direct (root) principal:

| Failure type | Description |
|-------------|-------------|
| `non_delegable_action` | The capability requires the direct principal (root of the delegation chain) and cannot be invoked by a delegated agent. The human must invoke this capability directly. |

Example:

```json
{
  "success": false,
  "invocation_id": "inv-9c1e2f3a4b5d",
  "failure": {
    "type": "non_delegable_action",
    "detail": "destroy_environment requires direct principal action and cannot be delegated",
    "retry": false,
    "resolution": {
      "action": "invoke_as_root_principal",
      "requires": "direct_principal_invocation"
    }
  }
}
```

### v0.16 recovery_class — coarse recovery strategy

v0.16 adds `recovery_class` to every `resolution` object. It is a coarser classification of the recovery strategy implied by `resolution.action`, enabling agents to route failures without pattern-matching on individual action strings.

> **Advisory:** `recovery_class` is advisory. It does **not** override or replace the `retry` boolean. `retry` retains its meaning — whether the same request could succeed after the resolution is applied. `recovery_class` conveys *how* to recover, not *whether* to retry.

**`recovery_class` vocabulary:**

| `recovery_class` | Meaning |
|---|---|
| `retry_now` | Retry immediately — no external change required. |
| `wait_then_retry` | Wait for a time-bounded condition (e.g. rate-limit window, service cooldown), then retry. |
| `refresh_then_retry` | Refresh a local artifact (binding, quote, token) and retry. |
| `redelegation_then_retry` | Obtain a new or modified delegation token from an authority, then retry. |
| `revalidate_then_retry` | Re-fetch and validate service-side state (manifest, capability graph) before retrying. |
| `terminal` | No automated recovery path — requires human escalation or service-owner intervention. |

**`terminal` invariant:** a failure with `recovery_class: "terminal"` MUST have `retry: false`. All other classes are compatible with either `retry` value.

Example failure response with `recovery_class`:

```json
{
  "success": false,
  "invocation_id": "inv-9c1e2f3a4b5d",
  "failure": {
    "type": "insufficient_scope",
    "detail": "Token lacks travel.book scope required by book_flight",
    "retry": false,
    "resolution": {
      "action": "request_broader_scope",
      "requires": "travel.book",
      "grantable_by": "human:admin@company.com",
      "recovery_class": "redelegation_then_retry"
    }
  }
}
```

### Canonical authority resolution actions (v0.15)

The `resolution.action` field uses canonical string values. The table below lists all authority-related resolution actions, including five new ones added in v0.16:

| `resolution.action` | `recovery_class` | Meaning |
|--------------------|-----------------|---------|
| `request_broader_scope` | `redelegation_then_retry` | Obtain a delegation token with wider scope |
| `request_budget_increase` | `redelegation_then_retry` | Obtain a higher-budget delegation |
| `invoke_as_root_principal` | `terminal` | The human must invoke directly (non-delegable) |
| `obtain_binding` | `refresh_then_retry` | Invoke the source capability first to get a binding |
| `refresh_binding` | `refresh_then_retry` | Re-invoke the source capability for a fresh quote |
| `obtain_quote_first` | `refresh_then_retry` | Get a bound price before invoking an estimated-cost capability |
| `obtain_matching_currency` | `redelegation_then_retry` | Re-delegate with matching budget currency |
| `retry_now` | `retry_now` | Retry immediately — transient condition resolved |
| `provide_credentials` | `retry_now` | Provide or refresh credentials and retry |
| `wait_and_retry` | `wait_then_retry` | Wait for a time-bounded window, then retry |
| `revalidate_state` | `revalidate_then_retry` | Re-fetch service-side state before retrying |
| `check_manifest` | `revalidate_then_retry` | Re-fetch the manifest and verify capability declarations |
| `request_budget_bound_delegation` | `redelegation_then_retry` | Request a delegation with an explicit budget bound |
| `request_matching_currency_delegation` | `redelegation_then_retry` | Re-delegate with a currency that matches the capability cost |
| `request_new_delegation` | `redelegation_then_retry` | Obtain a fresh delegation token (existing token expired or revoked) |
| `request_capability_binding` | `redelegation_then_retry` | Obtain a delegation that binds to a specific capability |
| `request_deeper_delegation` | `redelegation_then_retry` | Obtain a delegation from a principal higher in the chain |
| `escalate_to_root_principal` | `terminal` | Escalate to the root principal; no automated recovery |
| `contact_service_owner` | `terminal` | The service owner must intervene; no automated recovery |

> **Deprecation:** The `request_scope_grant` value for `resolution.action` was removed in v0.15. All conformant implementations must use `request_broader_scope` instead. Clients that check for `request_scope_grant` should be updated.

### v0.14 failure types

v0.14 adds six failure types for budget, binding, and control scenarios:

| Failure type | Description |
|-------------|-------------|
| `budget_exceeded` | The invocation cost exceeds the token's budget constraint. When cost certainty is `exact`, the check compares the exact amount; when `estimated`, the check uses `range_max`. |
| `budget_currency_mismatch` | The token's budget currency does not match the capability's cost currency. |
| `budget_not_enforceable` | The capability declares cost but the token lacks a budget constraint required by the service's control requirements. |
| `binding_missing` | The capability has `requires_binding: true` but no binding reference was provided in the invocation request. |
| `binding_stale` | A binding reference was provided but has expired or is no longer valid. |
| `control_requirement_unsatisfied` | A `control_requirements` entry (e.g. `cost_ceiling`, `stronger_delegation_required`) was not met. |

### Budget context

v0.14 invoke responses include a `budget_context` object on both success and failure, giving agents visibility into budget consumption:

```json
{
  "success": true,
  "result": { "booking_id": "BK-7291" },
  "cost_actual": { "currency": "USD", "amount": 487.00 },
  "budget_context": {
    "budget_currency": "USD",
    "budget_max": 500.00,
    "budget_consumed": 487.00,
    "budget_remaining": 13.00
  }
}
```

On failure, `budget_context` shows why the budget check failed:

```json
{
  "success": false,
  "failure": {
    "type": "budget_exceeded",
    "detail": "Estimated max cost $800.00 exceeds budget of $500.00"
  },
  "budget_context": {
    "budget_currency": "USD",
    "budget_max": 500.00,
    "check_amount": 800.00,
    "check_basis": "range_max"
  }
}
```

The `check_basis` field indicates how the enforcement amount was determined: `exact` when cost certainty is exact, or `range_max` when cost certainty is estimated (the service uses the worst-case amount to protect the budget).

## Cost signaling

ANIP lets services declare cost expectations before invocation and return actual costs after:

### Before invoke (from manifest)

```json
{
  "cost": {
    "certainty": "estimated",
    "financial": {
      "currency": "USD",
      "range_min": 200,
      "range_max": 800,
      "typical": 420
    }
  }
}
```

### After invoke (in response)

```json
{
  "success": true,
  "cost_actual": { "currency": "USD", "amount": 487.00 },
  "result": { "booking_id": "BK-7291" }
}
```

This lets agents:
- Compare alternatives before committing (search multiple options, pick the cheapest)
- Stay within budget constraints from their delegation chain
- Report cost to the user before and after execution

## Audit logging

Every ANIP invocation is automatically logged with:

- Capability name and invocation ID
- Caller identity (from the delegation chain)
- Event classification (`low_risk_success`, `high_risk_success`, `low_risk_failure`, etc.)
- Timestamp
- Retention policy compliance

### Querying audit

```bash
curl -X POST https://service.example/anip/audit \
  -H "Authorization: Bearer <bootstrap-token>" \
  -H "Content-Type: application/json" \
  -d '{"capability": "book_flight", "limit": 5}'
```

```json
{
  "entries": [
    {
      "invocation_id": "inv_8b2f4a",
      "capability": "book_flight",
      "actor_key": "human:demo@example.com",
      "event_class": "high_risk_failure",
      "success": false,
      "timestamp": "2026-03-27T10:30:00Z"
    }
  ]
}
```

### Security features

ANIP audit includes several hardening features:

- **Event classification**: Separates low-risk (reads) from high-risk (writes, financial) events for different retention and alerting
- **Retention policy**: Services declare how long audit entries are kept, with separate policies for different risk levels
- **Failure redaction**: Sensitive details can be redacted from audit entries based on caller class
- **Aggregation**: High-volume read operations can be aggregated to manage storage without losing audit coverage

## Next steps

- **[Checkpoints & Trust](/docs/protocol/checkpoints-trust)** — Merkle checkpoints and verification
- **[Quickstart](/docs/getting-started/quickstart)** — See failures and audit in action
