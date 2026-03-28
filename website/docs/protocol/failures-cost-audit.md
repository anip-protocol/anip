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
