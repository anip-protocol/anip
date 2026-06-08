---
title: Failures, Cost, and Audit
description: Structured failures with recovery guidance, cost signaling, and protocol-level audit logging.
---

# Failures, Cost, and Audit

ANIP does not stop at "success or error." It makes failures actionable, costs bounded before execution, and execution evidence queryable after the fact.

These three pieces are connected:

```text
failure semantics tell the agent what happened and how to recover
cost signaling tells the agent what an action may cost
budget enforcement prevents execution outside delegated authority
audit records what happened, who authorized it, and how it can be verified
```

## Structured Failures

When an ANIP invocation fails, the service returns a failure object the agent can act on. The response still includes an `invocation_id` when the request reached the service invocation boundary.

```json
{
  "success": false,
  "invocation_id": "inv-8b2f4a9c1e2f",
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

Transport-level authentication failures can still be HTTP 401. Once the request reaches the ANIP invocation boundary, authorization, budget, purpose, approval, and capability failures should be returned as structured ANIP failure objects.

### Failure Fields

| Field | Purpose |
|-------|---------|
| `failure.type` | Machine-readable failure category |
| `failure.detail` | Human-readable explanation, subject to disclosure policy |
| `failure.retry` | Whether the same request might succeed after the resolution is applied |
| `failure.resolution.action` | Canonical next action |
| `failure.resolution.recovery_class` | Coarse routing class for the recovery strategy |
| `failure.resolution.requires` | What is needed, such as scope, budget, binding, approval, or credentials |
| `failure.resolution.grantable_by` | Who can grant or perform the needed recovery, when known |
| `failure.resolution.estimated_availability` | When recovery may become possible |
| `failure.resolution.recovery_target` | Optional v0.21 structured target for refresh, revalidation, redelegation, or escalation |
| `failure.approval_required` | Optional v0.23 metadata, present only for `approval_required` failures |

## Recovery Actions

`resolution.action` uses canonical values. Services must not invent ad-hoc recovery strings.

| `resolution.action` | `recovery_class` | Meaning |
|---------------------|------------------|---------|
| `retry_now` | `retry_now` | Retry immediately without an external change |
| `provide_credentials` | `retry_now` | Provide or refresh required credentials |
| `wait_and_retry` | `wait_then_retry` | Wait for a time-bound condition |
| `request_approval` | `wait_then_retry` | Wait for a persisted approval request to be approved |
| `obtain_binding` | `refresh_then_retry` | Invoke the source capability first to get a binding |
| `refresh_binding` | `refresh_then_retry` | Refresh an expired or stale binding |
| `obtain_quote_first` | `refresh_then_retry` | Get a bound price before invoking an estimated-cost capability |
| `revalidate_state` | `revalidate_then_retry` | Re-fetch service-side state before retrying |
| `check_manifest` | `revalidate_then_retry` | Re-fetch the manifest and verify capability declarations |
| `request_broader_scope` | `redelegation_then_retry` | Obtain a token with wider scope |
| `request_budget_increase` | `redelegation_then_retry` | Obtain a higher-budget token |
| `request_budget_bound_delegation` | `redelegation_then_retry` | Obtain a token with an explicit budget constraint |
| `request_matching_currency_delegation` | `redelegation_then_retry` | Obtain a token whose budget currency matches the capability cost |
| `request_new_delegation` | `redelegation_then_retry` | Obtain a fresh delegation token |
| `request_capability_binding` | `redelegation_then_retry` | Obtain a token bound to the required capability |
| `request_deeper_delegation` | `redelegation_then_retry` | Obtain a token with more remaining delegation depth |
| `escalate_to_root_principal` | `terminal` | The root principal must act directly |
| `contact_service_owner` | `terminal` | Service-owner intervention is required |

`request_scope_grant` is deprecated. Use `request_broader_scope`.

The `terminal` invariant is strict: a failure with `recovery_class: "terminal"` must have `retry: false`.

### Structured Recovery Target

`recovery_target` is optional but useful when the agent can recover by invoking another capability or revalidating a specific service.

```json
{
  "type": "binding_stale",
  "detail": "Binding quote_id has exceeded max_age of 15 minutes",
  "retry": false,
  "resolution": {
    "action": "refresh_binding",
    "recovery_class": "refresh_then_retry",
    "requires": "invoke search_flights again for a fresh quote_id",
    "recovery_target": {
      "kind": "refresh",
      "target": {
        "service": "travel-search",
        "capability": "search_flights"
      },
      "continuity": "same_task",
      "retry_after_target": true
    }
  }
}
```

`recovery_target` is not a workflow language. It points to one recovery step; it does not encode a multi-step plan.

## Approval-Required Failures

Some capabilities should stop before mutation and return `approval_required`. v0.23 makes this a persisted, signed continuation flow rather than a boolean parameter.

```json
{
  "success": false,
  "invocation_id": "inv-9c1e2f3a4b5d",
  "failure": {
    "type": "approval_required",
    "detail": "Posting to the incident channel requires approval.",
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

The continuation invocation supplies the grant ID:

```json
{
  "approval_grant": "grant_456",
  "parameters": {
    "channel_id": "C0123456789",
    "text": "Approved incident update"
  }
}
```

The runtime validates the grant before executing: signature, expiry, capability binding, parameter digest, session binding when applicable, and use count. If the grant is reserved and the handler later fails, the grant remains consumed; the audit trail records the failed attempt.

## Cost Signaling

Services declare expected cost in the manifest before invocation.

```json
{
  "cost": {
    "certainty": "estimated",
    "financial": {
      "currency": "USD",
      "range_min": 280,
      "range_max": 500,
      "typical": 420
    },
    "determined_by": "search_flights"
  }
}
```

ANIP cost certainty has three levels:

| Certainty | Budget check |
|-----------|--------------|
| `fixed` | Use `cost.financial.amount` |
| `estimated` with binding | Use the bound price returned by the source capability |
| `estimated` without binding | Reject with `budget_not_enforceable` |
| `dynamic` | Use `cost.financial.upper_bound` |

For estimated and dynamic capabilities, successful responses should include actual cost:

```json
{
  "success": true,
  "invocation_id": "inv-a1b2c3d4e5f6",
  "result": { "booking_id": "BK-7291" },
  "cost_actual": {
    "financial": {
      "currency": "USD",
      "amount": 487
    },
    "variance_from_estimate": "+16.0%"
  }
}
```

## Budget Enforcement

Budget constraints in delegation tokens are enforceable ceilings. Invocation-request budgets are only negotiation hints and may narrow, never widen, the token budget.

When budget is evaluated, the response includes `budget_context` on both success and failure:

```json
{
  "success": true,
  "result": { "booking_id": "BK-7291" },
  "cost_actual": {
    "financial": {
      "currency": "USD",
      "amount": 487
    }
  },
  "budget_context": {
    "budget_currency": "USD",
    "budget_max": 500,
    "cost_check_amount": 487,
    "cost_certainty": "fixed",
    "cost_actual": 487,
    "within_budget": true
  }
}
```

Failure example:

```json
{
  "success": false,
  "failure": {
    "type": "budget_exceeded",
    "detail": "Capability cost $800 exceeds delegated budget of $500",
    "retry": false,
    "resolution": {
      "action": "request_budget_increase",
      "recovery_class": "redelegation_then_retry",
      "requires": "delegation token with higher budget"
    }
  },
  "budget_context": {
    "budget_currency": "USD",
    "budget_max": 500,
    "cost_check_amount": 800,
    "cost_certainty": "dynamic",
    "within_budget": false
  }
}
```

If the token budget currency does not match the capability cost currency, the service must reject with `budget_currency_mismatch`.

## Audit Logging

ANIP audit logs are protocol-level execution evidence. They are not just application logs.

Every invocation that reaches the service invocation boundary is recorded with:

- Capability name and `invocation_id`.
- Caller identity and delegation context.
- `task_id`, `client_reference_id`, `parent_invocation_id`, and `upstream_service` when present.
- Success/failure status and `failure_type` when applicable.
- Event classification.
- Retention tier and expiration.
- Budget, binding, approval, and lineage context when applicable.

### Querying Audit

```bash
curl -X POST "https://service.example/anip/audit?capability=book_flight&limit=5" \
  -H "Authorization: Bearer <delegation-token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

```json
{
  "entries": [
    {
      "sequence_number": 42,
      "invocation_id": "inv-8b2f4a9c1e2f",
      "capability": "book_flight",
      "actor_key": "human:demo@example.com",
      "root_principal": "human:demo@example.com",
      "event_class": "high_risk_denial",
      "retention_tier": "medium",
      "expires_at": "2026-09-27T10:30:00Z",
      "success": false,
      "failure_type": "budget_exceeded",
      "task_id": "trip-2026",
      "timestamp": "2026-06-27T10:30:00Z"
    }
  ]
}
```

Audit queries are scoped to the root principal of the caller's delegation token. A service must not return entries that belong to another principal.

Supported filters include `capability`, `since`, `invocation_id`, `client_reference_id`, `task_id`, `parent_invocation_id`, and `limit`.

### Audit Hardening

ANIP audit includes several security and operations features:

| Feature | Purpose |
|---------|---------|
| Event classification | Classifies entries as `high_risk_success`, `high_risk_denial`, `low_risk_success`, `malformed_or_spam`, or `repeated_low_value_denial` |
| Retention enforcement | Assigns `retention_tier` and `expires_at`; services that claim enforced retention must run cleanup |
| Response-boundary redaction | Redacts failure responses based on disclosure policy before returning to caller |
| Caller-class-aware disclosure | Uses `anip:caller_class` and service policy to choose full, reduced, or redacted failure detail |
| Audit aggregation | Collapses repeated low-value denials into summary records |
| Storage-side redaction | Strips request parameters from low-value persisted entries while keeping enough evidence for audit |
| Checkpoint interaction | Checkpoints remain valid after retention, but inclusion proof regeneration can become unavailable after rows expire |

The redaction layers are intentionally separate:

```text
request -> classify -> optional aggregation -> storage redaction -> persist
persist -> response-boundary redaction -> caller
```

Storage-side redaction controls what is saved. Response-boundary redaction controls what a caller sees. Neither replaces the other.

## Why This Matters

Without structured failures, an agent sees "403" and guesses.

Without cost signaling, an agent can spend outside the user's expectations.

Without budget enforcement, a declared budget is just advisory.

Without audit lineage and retention, operators cannot reconstruct what happened or prove that records were not silently changed.

ANIP ties these together: the same capability contract that tells an agent what can happen also tells the service how to fail, how to enforce budget, and how to preserve execution evidence.

## Next Steps

- [Capabilities](/docs/protocol/capabilities) — How capabilities declare side effects, controls, approval posture, and input resolution.
- [Delegation & Permissions](/docs/protocol/delegation-permissions) — How authority and permission discovery interact with failures.
- [Lineage](/docs/protocol/lineage) — How invocation, approval, and composition evidence is connected.
- [Checkpoints & Trust](/docs/protocol/checkpoints-trust) — How audit evidence is verified.
