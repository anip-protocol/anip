---
title: Delegation and Permissions
description: How ANIP handles authority, scoped delegation, and pre-invoke permission discovery.
---

# Delegation and Permissions

ANIP separates authentication from authorization, and makes both explicit. Instead of treating bearer tokens as opaque blobs, ANIP uses structured delegation — a chain of authority from human to agent to service, with explicit scopes, budgets, and purpose constraints at each link.

## How delegation works

A typical delegation chain:

1. **Human** authenticates with an API key or OIDC token
2. Human requests a **delegation token** scoped to specific capabilities and budgets
3. The delegation token is passed to an **agent**
4. The agent uses the token to invoke capabilities — the service validates the chain

### Issuing a token

```bash
curl -X POST https://service.example/anip/tokens \
  -H "Authorization: Bearer demo-human-key" \
  -H "Content-Type: application/json" \
  -d '{
    "scope": ["travel.search", "travel.book"],
    "capability": "book_flight",
    "purpose_parameters": {
      "task_id": "trip-planning-2026",
      "budget_usd": 500
    }
  }'
```

```json
{
  "issued": true,
  "token": "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9...",
  "scope": ["travel.search", "travel.book"],
  "capability": "book_flight",
  "expires_at": "2026-03-27T12:00:00Z"
}
```

The resulting JWT encodes:
- **Who** issued it (the human principal)
- **What scope** was granted
- **What capability** it's for
- **When** it expires
- **Purpose constraints** (budget, task context)

### Token structure

ANIP delegation tokens are standard JWTs signed by the service's key pair:

```json
{
  "iss": "travel-service",
  "sub": "human:demo@example.com",
  "scope": ["travel.search", "travel.book"],
  "capability": "book_flight",
  "purpose_parameters": { "task_id": "trip-planning-2026", "budget_usd": 500 },
  "iat": 1711526400,
  "exp": 1711569600
}
```

The service validates the token's signature against its own JWKS before allowing any invocation.

## Permission discovery

Permission discovery is a first-class ANIP primitive. Before invoking a capability, an agent can ask "what am I allowed to do?" and get a structured answer:

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

The response separates capabilities into three buckets:

| Bucket | Meaning | Agent action |
|--------|---------|--------------|
| **available** | Token has sufficient scope | Safe to invoke |
| **restricted** | Missing a grantable scope | Request additional authority from the specified grantor |
| **denied** | Structurally impossible (wrong principal class, etc.) | Do not attempt — explain to user |

This is fundamentally different from REST APIs, where the agent discovers permissions only by attempting actions and interpreting error codes. With ANIP, the agent can plan before acting and explain blockers to its user.

### reason_type vocabulary (v0.15)

Starting in v0.15, every `restricted` and `denied` entry includes a machine-readable `reason_type` field. Agents use this to distinguish between restriction categories without parsing the human-readable `reason` string.

| `reason_type` | Determined by | Meaning |
|---------------|--------------|---------|
| `scope_insufficient` | Token scope vs. capability `minimum_scope` | The delegation token lacks one or more required scope strings |
| `non_delegable_action` | Capability handler or service policy | The capability requires the direct (root) principal — delegated agents are blocked |
| `principal_class` | Caller identity class vs. service policy | Wrong principal class (e.g., agent attempting an admin-only action) |
| `token_requirement` | `control_requirements` token-evaluable checks | The token does not satisfy a declared control requirement (e.g., `cost_ceiling`) |
| `policy_blocked` | Service-side runtime policy | A server-side policy blocks the caller regardless of scope or token shape |

Example `restricted` entry with `reason_type` and `resolution_hint`:

```json
{
  "restricted": [
    {
      "capability": "book_flight",
      "reason": "missing scope: travel.book",
      "reason_type": "scope_insufficient",
      "grantable_by": "human:admin@company.com",
      "resolution_hint": "Request the 'travel.book' scope from your delegation grantor"
    }
  ]
}
```

Example `denied` entry for a non-delegable action:

```json
{
  "denied": [
    {
      "capability": "destroy_environment",
      "reason": "destroy_environment requires direct principal action and cannot be delegated",
      "reason_type": "non_delegable_action"
    }
  ]
}
```

### resolution_hint field (v0.15)

Restricted entries may include a `resolution_hint` string — a short, human-readable suggestion for how to resolve the restriction. Unlike `reason` (which explains *why*), `resolution_hint` explains *what to do next*. Agents can surface this directly to users without custom handling per failure type.

## Budget constraints in delegation

Starting in v0.14, delegation tokens can carry enforceable budget constraints via `constraints.budget`:

```json
{
  "iss": "travel-service",
  "sub": "human:demo@example.com",
  "scope": ["travel.search", "travel.book"],
  "capability": "book_flight",
  "constraints": {
    "budget": {
      "currency": "USD",
      "max_amount": 500.00
    }
  },
  "iat": 1711526400,
  "exp": 1711569600
}
```

### Budget narrowing rule

When an agent sub-delegates authority, the child token's budget must be less than or equal to the parent token's budget. A delegation request that attempts to set a higher budget than the parent will be rejected. This ensures that authority can only be narrowed, never expanded, as it flows through the delegation chain.

### Budget and permission discovery

Permission discovery surfaces unmet budget requirements through the `unmet_token_requirements` field. When a capability requires a budget constraint that the current token does not satisfy, the response includes:

```json
{
  "restricted": [
    {
      "capability": "book_flight",
      "reason": "token lacks required budget constraint",
      "unmet_token_requirements": ["budget"],
      "grantable_by": "human:manager@company.com"
    }
  ]
}
```

This lets agents understand exactly why a capability is restricted and what kind of re-delegation is needed before attempting the invocation.

## Why this matters for agents

Permission discovery enables agent behaviors that are impossible with traditional APIs:

- **Pre-flight planning**: Agent checks what it can do before constructing a multi-step plan
- **Informed escalation**: Agent tells the user "I can search flights but need your approval to book — shall I request access from admin@company.com?"
- **Budget-aware decisions**: Agent knows its delegation budget before committing to expensive operations
- **Graceful degradation**: Agent falls back to read-only operations when write access is restricted, rather than failing mid-workflow

## Next steps

- **[Failures, Cost & Audit](/docs/protocol/failures-cost-audit)** — What happens when invocations fail
- **[Checkpoints & Trust](/docs/protocol/checkpoints-trust)** — Verification and trust posture
