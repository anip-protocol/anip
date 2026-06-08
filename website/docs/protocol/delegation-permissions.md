---
title: Delegation and Permissions
description: How ANIP handles authority, scoped delegation, and pre-invoke permission discovery.
---

# Delegation and Permissions

ANIP separates authentication from authorization, and makes both explicit. Instead of treating bearer tokens as opaque blobs, ANIP uses structured delegation: a chain of authority from human to agent to service, with explicit scopes, budgets, capability binding, purpose constraints, and approval continuations.

The short version:

```text
authentication proves who is calling
delegation defines what authority was granted
permission discovery shows what the current token can do
approval grants authorize one bounded continuation
audit links the whole chain
```

## How delegation works

A typical delegation chain:

1. **Human** authenticates with an API key or OIDC token
2. Human requests a **delegation token** scoped to specific capabilities and budgets
3. The delegation token is passed to an **agent**
4. The agent checks **permission discovery** before acting
5. The agent invokes a capability only when the token, purpose, controls, and approval state allow it
6. The service records audit entries tied to the delegation chain

Scopes and capabilities are related but not the same:

```text
capability: book_flight
minimum_scope: ["travel.book"]
```

Callers must request explicit scopes. ANIP does not infer scope strings from capability names.

### Issuing a token

```bash
curl -X POST https://service.example/anip/tokens \
  -H "Authorization: Bearer demo-human-key" \
  -H "Content-Type: application/json" \
  -d '{
    "scope": ["travel.search", "travel.book"],
    "capability": "book_flight",
    "purpose_parameters": {
      "task_id": "trip-planning-2026"
    },
    "budget": {
      "currency": "USD",
      "max_amount": 500
    }
  }'
```

```json
{
  "token_id": "tok_root_001",
  "token": "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...",
  "task_id": "trip-planning-2026",
  "budget": {
    "currency": "USD",
    "max_amount": 500
  },
  "expires": "2026-06-27T12:00:00Z"
}
```

The resulting JWT encodes:
- **Who** issued it (the human principal)
- **What scope** was granted
- **What capability** it's for
- **When** it expires
- **Purpose constraints** (task context, caller class, budget, concurrency posture)

### Root and delegated issuance

The same `/anip/tokens` endpoint supports two issuance paths:

| Path | Authenticates with | Request shape | Use case |
|------|--------------------|---------------|----------|
| Root issuance | Bootstrap credential | Omits `parent_token` | Human or app grants initial authority. |
| Delegated issuance | Existing ANIP JWT | Includes `parent_token` | Agent delegates narrower authority to a child agent or subtask. |

`parent_token` is a token ID string returned by token issuance, not a JWT. The service looks up that parent token in storage, then checks that the child request narrows authority.

Delegated tokens must not widen:

- Scope.
- Budget.
- Capability binding.
- Expiry.
- Purpose.
- Delegation depth.

Runtime helpers such as capability-targeted root issuance and delegated capability-targeted issuance are convenience APIs. They do not change the protocol endpoint; they assemble token requests correctly and prevent common `purpose_mismatch` mistakes.

### Token structure

ANIP delegation tokens are standard JWTs signed by the service's ES256 key pair:

```json
{
  "iss": "travel-service",
  "sub": "human:demo@example.com",
  "scope": ["travel.search", "travel.book"],
  "capability": "book_flight",
  "purpose": { "task_id": "trip-planning-2026" },
  "constraints": {
    "budget": {
      "currency": "USD",
      "max_amount": 500
    }
  },
  "anip:caller_class": "automated_agent",
  "iat": 1781532000,
  "exp": 1781539200
}
```

The service validates the token's signature against its own JWKS before allowing any invocation.

If a token carries `purpose.task_id`, invocation requests must either omit `task_id` or match it. A mismatch is a purpose failure, not a best-effort hint.

## Permission discovery

Permission discovery is a first-class ANIP primitive. Before invoking a capability, an agent can ask "what am I allowed to do with this token?" and get a structured answer:

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
  "denied": [
    {
      "capability": "admin_reset",
      "reason": "requires admin principal class",
      "reason_type": "non_delegable"
    }
  ]
}
```

### Three-bucket model

The response separates capabilities into three buckets:

| Bucket | Meaning | Agent action |
|--------|---------|--------------|
| **available** | Token has sufficient declared authority | Authorized to attempt invocation |
| **restricted** | Missing a grantable scope | Request additional authority from the specified grantor |
| **denied** | Structurally impossible (wrong principal class, etc.) | Do not attempt — explain to user |

This is fundamentally different from REST APIs, where the agent discovers permissions only by attempting actions and interpreting error codes. With ANIP, the agent can plan before acting and explain blockers to its user.

Permission discovery is token-scoped. It does not mean every possible mutation is safe to perform. It means the service can classify the current token's authority against declared capabilities before invocation. The actual invocation still validates input resolution, purpose binding, budget, approval requirements, and service policy at execution time.

### reason_type vocabulary (v0.15)

Starting in v0.15, every `restricted` and `denied` entry includes a machine-readable `reason_type` field. Agents use this to distinguish between restriction categories without parsing the human-readable `reason` string.

| `reason_type` | Determined by | Meaning |
|---------------|--------------|---------|
| `insufficient_scope` | Token scope vs. capability `minimum_scope` | The delegation token lacks one or more required scope strings |
| `insufficient_delegation_depth` | Delegation chain depth vs. service limit | The delegation chain is too deep for this capability |
| `stronger_delegation_required` | Capability requires explicit binding | The token needs explicit capability binding or tighter purpose constraints |
| `unmet_control_requirement` | `control_requirements` token-evaluable checks | The token does not satisfy a declared control requirement (e.g., `cost_ceiling`) |
| `non_delegable` | Capability handler or service policy | The capability requires the direct (root) principal — delegated agents are blocked |

Example `restricted` entry with `reason_type` and `resolution_hint`:

```json
{
  "restricted": [
    {
      "capability": "book_flight",
      "reason": "missing scope: travel.book",
      "reason_type": "insufficient_scope",
      "grantable_by": "human:admin@company.com",
      "resolution_hint": "request_broader_scope"
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
      "reason_type": "non_delegable"
    }
  ]
}
```

### resolution_hint field (v0.15)

Restricted entries may include a `resolution_hint` string — a canonical `resolution.action` value that tells the agent what recovery step to take. The value must be one of the canonical resolution action strings (e.g., `request_broader_scope`, `request_budget_bound_delegation`, `request_capability_binding`). When the agent later invokes the capability and gets a failure, the failure's `resolution.action` will match the `resolution_hint` value from permission discovery.

## Control requirements

Capabilities can declare token-evaluable preconditions through `control_requirements`.

Example:

```json
{
  "control_requirements": [
    { "type": "cost_ceiling", "enforcement": "reject" },
    { "type": "stronger_delegation_required", "enforcement": "reject" }
  ]
}
```

When the current token does not satisfy those requirements, permission discovery should place the capability in `restricted` with `reason_type: "unmet_control_requirement"` and `unmet_token_requirements`.

```json
{
  "restricted": [
    {
      "capability": "execute_trade",
      "reason": "token lacks required budget constraint",
      "reason_type": "unmet_control_requirement",
      "unmet_token_requirements": ["cost_ceiling"],
      "grantable_by": "human:manager@company.com",
      "resolution_hint": "request_budget_bound_delegation"
    }
  ]
}
```

This is how a service tells an agent that the operation might be grantable, but not under the current delegation token.

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
  "iat": 1781532000,
  "exp": 1781539200
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
      "reason_type": "unmet_control_requirement",
      "unmet_token_requirements": ["cost_ceiling"],
      "grantable_by": "human:manager@company.com",
      "resolution_hint": "request_budget_bound_delegation"
    }
  ]
}
```

This lets agents understand exactly why a capability is restricted and what kind of re-delegation is needed before attempting the invocation.

## Approval grants

Delegation tokens grant authority to attempt a capability. Approval grants authorize a specific continuation after the service has stopped at `approval_required`.

These are different controls:

| Control | Purpose |
|---------|---------|
| Delegation token | Defines the caller's available authority. |
| Permission discovery | Classifies what the current token can, cannot, or might be able to do. |
| Approval request | Records a proposed risky/write-adjacent action and preview. |
| Approval grant | Authorizes the exact continuation under a grant policy. |

Initial invocation can stop before mutation:

```json
{
  "success": false,
  "failure": {
    "type": "approval_required",
    "detail": "slack.message.send requires approval before posting to this channel",
    "resolution": {
      "action": "request_approval",
      "recovery_class": "wait_then_retry"
    },
    "retry": false,
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

The continuation must present a valid grant:

```json
{
  "parameters": {
    "channel_id": "C0123456789",
    "text": "Approved incident update"
  },
  "approval_grant": {
    "grant_id": "grant_456",
    "approval_request_id": "apr_123",
    "capability": "slack.message.send",
    "parameters_digest": "sha256:...",
    "grant_type": "one_time",
    "signature": "..."
  }
}
```

The runtime validates signature, expiry, capability binding, parameter digest, session binding when applicable, and use count before executing the side effect.

This is why ANIP approval is not "pass `approved=true`". It is a persisted, signed, bounded continuation record.

## Fronting and organization policy

For fronting services, delegation is where organization policy becomes enforceable before raw backend access.

Examples:

- Slack may allow `chat.postMessage`, but ANIP can require channel allow-list, preview, approval grant, and audit before posting.
- Jira may allow issue transitions, but ANIP can require actor/project scope and approval before workflow mutation.
- Superset may allow analytics access, but ANIP can restrict capability scope to governed metrics, datasets, and preview-first chart creation.

The downstream system still enforces its own authentication and authorization. ANIP adds the service-owned business authority layer that agents can discover, verify, and invoke safely.

## Why this matters for agents

Permission discovery enables agent behaviors that are impossible with traditional APIs:

- **Pre-flight planning**: Agent checks what it can do before constructing a multi-step plan
- **Informed escalation**: Agent tells the user "I can search flights but need your approval to book. Shall I request access from the configured grantor?"
- **Budget-aware decisions**: Agent knows its delegation budget before committing to expensive operations
- **Graceful degradation**: Agent falls back to read-only operations when write access is restricted, rather than failing mid-workflow
- **Safe continuation**: Agent can pause at `approval_required`, obtain a bounded grant, then continue without changing the original request
- **Portable policy**: The same permission and approval semantics travel with packages and generated services instead of living only in prompts or workflow code

## Next steps

- [Capabilities](/docs/protocol/capabilities) — How capabilities declare scopes, controls, inputs, and side effects.
- [Failures, Cost & Audit](/docs/protocol/failures-cost-audit) — What happens when invocations fail.
- [Checkpoints & Trust](/docs/protocol/checkpoints-trust) — Verification and trust posture.
