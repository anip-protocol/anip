# ANIP Consumer Skill

> Spec version: ANIP v0.6 | Skill version: 1.1 | Last validated: 2026-03-08

> For agents that need to discover, negotiate with, and invoke ANIP-compliant services.

## When to Use This Skill

Use this when you need to interact with a service that exposes `/.well-known/anip`. This skill gives you the canonical interaction flow, field-by-field guidance for every response you'll encounter, and the decision points where you must stop and reason before proceeding.

## The 8-Step Interaction Flow

```
1. Discovery     GET /.well-known/anip
2. Handshake     POST /anip/handshake
3. Manifest      GET /anip/manifest
4. Delegation    POST /anip/tokens
5. Permissions   POST /anip/permissions
6. Graph         GET /anip/graph/{capability}
7. Invocation    POST /anip/invoke/{capability}
8. Audit         GET /anip/audit
```

Steps 1-3 are always sequential. Steps 4-7 may repeat as you invoke multiple capabilities. Step 8 is optional — use it post-invocation to verify what happened.

---

## Step 1: Discovery

**Request:** `GET /.well-known/anip`

**What you get back:** A lightweight document describing the service, its capabilities, and where everything lives. This is your single entry point — never hardcode other endpoints.

**Fields you must read:**

| Field | What it tells you | Action |
|-------|-------------------|--------|
| `protocol` | ANIP version (e.g., `anip/1.0`) | Verify you support this version. Stop if you don't. |
| `compliance` | `anip-compliant` or `anip-complete` | Compliant = 5 core primitives only. Complete = all 9. Adjust expectations accordingly. |
| `profile` | Which primitives are implemented and their versions | Use this to decide what to require in the handshake. |
| `capabilities` | Map of capability names → summary metadata | **This is your decision surface.** See below. |
| `endpoints` | URL map for all standard endpoints | Store these. Never construct URLs yourself. |
| `auth.delegation_token_required` | Whether you need a delegation token | If `true`, you must construct a delegation chain before invoking anything. |
| `metadata.ttl` | How long to cache this document | Respect this. Don't re-fetch on every interaction. |

**Reading capability summaries:**

Each capability in the discovery document has:

```yaml
search_flights:
  description: "Search available flights between two airports"
  side_effect: "read"           # read | write | irreversible | transactional
  minimum_scope: ["travel.search"]  # ALL required (AND semantics)
  financial: false              # does this cost money?
  contract: "1.0"               # contract version
```

**Decision points at discovery:**

1. **Side-effect check:** If `side_effect` is `irreversible`, you MUST have explicit authorization before invoking. Never invoke an irreversible capability speculatively.
2. **Financial check:** If `financial: true`, check your budget authority before proceeding.
3. **Scope check:** Compare `minimum_scope` against your delegation token's scope. If you lack any scope in the array, do not attempt invocation — it will fail.
4. **Contract version:** If you have a cached manifest, compare contract versions. If they differ, re-fetch the manifest.

---

## Step 2: Profile Handshake

**Request:** `POST {endpoints.handshake}`

```json
{
  "required_profiles": {
    "core": "1.0",
    "cost": "1.0"
  }
}
```

**Purpose:** Verify the service supports the primitives you need before doing any real work.

**Rules:**
- Only require profiles you actually need. Don't require `observability` if you won't use audit logs.
- If `compatible: false`, stop. The service cannot meet your requirements.
- If `compatible: true`, proceed with confidence that all declared profiles are available.

---

## Step 3: Manifest

**Request:** `GET {endpoints.manifest}`

**What you get back:** Full capability declarations — inputs, outputs, side-effect details, cost models, session info, observability contracts.

**When to fetch:** After a successful handshake. Cache the result and use `contract` versions from discovery to detect staleness.

**What to extract per capability:**

- `inputs` — what parameters the capability accepts (name, type, required, default)
- `output` — what the response contains (type, fields)
- `side_effect.type` + `side_effect.rollback_window` — severity and reversibility
- `cost` — see Cost Model section below
- `minimum_scope` — the delegation scopes needed (array)
- `requires` — prerequisites (other capabilities you must invoke first)
- `composes_with` — capabilities that work well together

---

## Step 4: Delegation Chain Construction

**Request:** `POST {endpoints.tokens}`

You must register delegation tokens before invoking capabilities. Tokens form a DAG (directed acyclic graph), not a simple chain.

**Token structure:**

```json
{
  "token_id": "tok_unique_id",
  "issuer": "human:user@example.com",
  "subject": "agent:your-agent-id",
  "scope": ["travel.search", "travel.book:max_$500"],
  "purpose": {
    "capability": "book_flight",
    "parameters": {"from": "SEA", "to": "SFO"},
    "task_id": "task_001"
  },
  "parent": null,
  "expires": "2026-03-07T20:00:00Z",
  "constraints": {
    "max_delegation_depth": 3,
    "concurrent_branches": "allowed"
  }
}
```

**Rules:**

1. **Scope narrowing only.** A child token's scope MUST be equal to or narrower than its parent's. You cannot escalate privileges.
2. **Purpose binding.** The `purpose.capability` field binds this token to a specific capability. The service will reject the token if used for a different capability.
3. **Separate tokens for separate capabilities.** If you need to invoke `search_flights` and then `book_flight`, create separate tokens with appropriate purpose binding for each.
4. **Expiry.** Always set a reasonable `expires`. Shorter is safer.
5. **Parent chain.** If you're a sub-agent, your token's `parent` must reference a registered token from your delegator.

---

## Step 5: Permission Discovery

**Request:** `POST {endpoints.permissions}` with your delegation token as the body.

**What you get back:** Three lists:

- `available` — capabilities you can invoke right now, with any constraints
- `restricted` — capabilities that exist but your scope doesn't cover
- `denied` — capabilities you explicitly cannot access

**Why this matters:** Always check permissions before attempting invocation. This prevents wasted calls and gives you actionable information about what you're missing.

---

## Step 6: Capability Graph

**Request:** `GET {endpoints.graph}/{capability_name}`

**What you get back:** Prerequisites and composition relationships.

```json
{
  "capability": "book_flight",
  "requires": [
    {"capability": "search_flights", "reason": "must select from available flights"}
  ],
  "composes_with": []
}
```

**Rule:** If a capability has `requires`, you MUST invoke the prerequisites first. This is not a suggestion — it's a dependency declaration.

---

## Step 7: Invocation

**Request:** `POST {endpoints.invoke}/{capability_name}`

```json
{
  "delegation_token": { ... },
  "parameters": {
    "origin": "SEA",
    "destination": "SFO",
    "date": "2026-03-10"
  }
}
```

**Success response:**

```json
{
  "success": true,
  "result": { ... },
  "cost_actual": {
    "financial": {"amount": 420.0, "currency": "USD"},
    "variance_from_estimate": "+0.0%"
  }
}
```

**Failure response:**

```json
{
  "success": false,
  "failure": {
    "type": "insufficient_scope",
    "detail": "token lacks travel.book scope",
    "resolution": {
      "action": "request_scope_upgrade",
      "requires": "travel.book",
      "grantable_by": "human:user@example.com"
    },
    "retry": true
  }
}
```

---

## Step 8: Audit Log

**Request:** `GET {endpoints.audit}`

**Optional query parameters:**
- `capability` — filter by capability name (e.g., `book_flight`)
- `since` — ISO 8601 timestamp to filter entries after (e.g., `2026-03-07T00:00:00Z`)
- `limit` — max entries to return (default: 100, max: 1000)

**What you get back:**

```json
{
  "entries": [
    {
      "capability": "book_flight",
      "timestamp": "2026-03-07T15:30:00Z",
      "root_principal": "human:user@example.com",
      "success": true,
      "result_summary": {"booking_id": "BK-001", "total_cost": 420.0}
    }
  ],
  "count": 1
}
```

**When to use this:**

1. **Post-invocation verification** — after an irreversible action, confirm it was logged correctly
2. **Cost reconciliation** — compare `cost_actual` from invocation with what's in the audit trail
3. **Debugging** — when a sub-agent reports a failure, query the audit log to see what actually happened
4. **Compliance** — verify that the service's observability contract is being honored (retention period, fields logged)

**Access control:** The audit endpoint should restrict access based on your delegation chain — you can only see records for invocations where your root principal was in the chain. If the service doesn't support audit (no `audit` in `endpoints`), fall back to the observability contract in the manifest to understand what's being logged.

---

## Handling Failures

ANIP failures are structured and actionable. Never treat them as opaque errors.

| Failure Type | What It Means | What to Do |
|-------------|---------------|------------|
| `unknown_capability` | Capability doesn't exist | Re-fetch manifest, check spelling |
| `insufficient_scope` | Your delegation token lacks required scope | Request scope upgrade from `resolution.grantable_by` |
| `delegation_expired` | Token TTL has passed | Request a new token from your delegator |
| `purpose_mismatch` | Token was issued for a different capability | Create a new token with correct `purpose.capability` |
| `delegation_depth_exceeded` | Too many hops in the delegation chain | Request delegation directly from a closer ancestor |
| `budget_exceeded` | Cost exceeds your authorized budget | Request budget increase from `resolution.grantable_by` |
| `invalid_parameters` | Missing or malformed input | Fix parameters per `detail` and retry |
| `capability_unavailable` | Valid capability but can't execute now | Check `detail` for reason (e.g., resource not found) |

**Key principle:** `retry: true` means you can fix the issue and try again. `retry: false` means this invocation path is permanently blocked — you need a different approach.

---

## Cost Model

ANIP uses three levels of cost certainty (see https://github.com/anip-protocol/anip/blob/main/SPEC.md §5.1):

| Certainty | Meaning | What to Check |
|-----------|---------|---------------|
| `fixed` | Cost is known exactly | `cost.financial.amount` is the exact cost |
| `estimated` | Cost is approximate | Check `range_min`, `range_max`, `typical`. Use `determined_by` to find which capability provides exact pricing. |
| `dynamic` | Cost depends on runtime factors | Check `factors` for what affects cost, `upper_bound` for the maximum possible cost |

**Rule:** For `estimated` and `dynamic` costs, always invoke the `determined_by` capability first to get exact pricing before committing to an irreversible action.

---

## Handling Partial Implementations

A service may be `anip-compliant` (5 core primitives) but not `anip-complete` (all 9). Early in the ecosystem, this will be common. Apply these fallback postures:

| Missing Profile | Fallback Posture |
|----------------|-----------------|
| Cost signaling | Treat all `financial: true` capabilities as dynamic cost. Require explicit human authorization before any irreversible financial action. |
| Capability graph | Assume no prerequisites. Proceed with caution — if an invocation fails with a resolution pointing to another capability, treat that as a discovered prerequisite. |
| State & session | Assume stateless. Do not rely on server-side session continuity between invocations. |
| Observability | Assume the interaction is logged and act accordingly. Do not assume audit access is available. |

**Key principle:** When a contextual primitive is missing, adopt the most conservative interpretation. The cost of over-caution is one extra confirmation prompt. The cost of under-caution is an irreversible action without proper authorization.

---

## Common Mistakes

1. **Hardcoding endpoint URLs.** Always use the `endpoints` map from discovery. URLs may change.
2. **Reusing tokens across capabilities.** Purpose-binding means each capability needs its own token.
3. **Ignoring prerequisites.** If `book_flight` requires `search_flights`, invoke search first. The service will reject a booking without a prior search.
4. **Skipping permission discovery.** Don't guess what you can do — ask the service.
5. **Treating failures as HTTP errors.** ANIP failures are structured objects with resolution guidance. Parse them, don't just log the status code.
6. **Invoking irreversible capabilities without checking cost.** Always verify budget authority and cost certainty before irreversible actions.

---

## Quick Reference

```
Discovery:    GET  /.well-known/anip           → service overview + endpoint map
Handshake:    POST /anip/handshake             → profile compatibility check
Manifest:     GET  /anip/manifest              → full capability declarations
Tokens:       POST /anip/tokens                → register delegation tokens
Permissions:  POST /anip/permissions           → what can I do with my token?
Graph:        GET  /anip/graph/{capability}    → prerequisites and composition
Invoke:       POST /anip/invoke/{capability}   → execute a capability
Audit:        GET  /anip/audit                 → query invocation audit log
```

## References

- **Spec:** https://github.com/anip-protocol/anip/blob/main/SPEC.md
- **Schema (all types):** https://github.com/anip-protocol/anip/blob/main/schema/anip.schema.json
- **Schema (discovery):** https://github.com/anip-protocol/anip/blob/main/schema/discovery.schema.json
- **Guide:** https://github.com/anip-protocol/anip/blob/main/GUIDE.md
