# ANIP Implementation Guide

> For developers who want to understand how ANIP works by walking through a real implementation.

This guide walks through the [reference implementation](examples/anip/) — a flight booking service built with Python and FastAPI. Each section explains *what* the code does, *why* it's designed that way, and the design decisions behind it.

Read the [README](README.md) first for the big picture. Read this guide to understand how the pieces fit together. Read the [Spec](SPEC.md) when you need the formal contract.

---

## Project Structure

```
examples/anip/
├── anip_server/
│   ├── main.py                          # All endpoints — the entry point
│   ├── primitives/
│   │   ├── models.py                    # Every ANIP type as a Pydantic model
│   │   ├── manifest.py                  # Builds the service manifest
│   │   ├── delegation.py               # Token registration + chain validation
│   │   └── permissions.py              # Permission discovery logic
│   ├── capabilities/
│   │   ├── search_flights.py           # Read-only capability
│   │   └── book_flight.py             # Irreversible financial capability
│   └── data/
│       └── flights.py                  # In-memory stub data
├── demo.py                             # Full agent interaction demo
├── Dockerfile                          # Container deployment
└── pyproject.toml                      # Dependencies
```

The structure mirrors ANIP's conceptual layers: **primitives** (the protocol machinery), **capabilities** (what the service actually does), and **data** (the domain). This separation matters — the primitives are reusable across any ANIP service; only the capabilities and data change.

---

## 1. Models — The Type System

**File:** `anip_server/primitives/models.py`

This file defines every ANIP data structure as a Pydantic model. It's the foundation — everything else imports from here. If you're building an ANIP service in any language, start by defining these types.

### Side-effect Types

```python
class SideEffectType(str, Enum):
    READ = "read"
    WRITE = "write"
    IRREVERSIBLE = "irreversible"
    TRANSACTIONAL = "transactional"
```

Four types, ordered by severity. The distinction that matters most: **`read` and `write` are recoverable; `irreversible` is not.** This isn't just metadata — it changes how agents should behave. An agent can speculatively invoke a `read` capability. It should never speculatively invoke an `irreversible` one.

The `rollback_window` on `SideEffect` adds nuance: a `write` with `rollback_window: "PT24H"` means you have 24 hours to undo it. An `irreversible` with `rollback_window: "none"` means there's no going back. This combination — type + window — gives agents enough information to make risk-aware decisions without needing to understand the domain.

### The Delegation Token

```python
class DelegationToken(BaseModel):
    token_id: str
    issuer: str              # who created this token
    subject: str             # who can use it
    scope: list[str]         # what they're allowed to do
    purpose: Purpose         # what they're allowed to do it for
    parent: str | None       # link to parent token (DAG edge)
    expires: datetime        # when this authority expires
    constraints: DelegationConstraints
```

**Why a DAG instead of a simple chain?** Consider a human who delegates to an orchestrator agent, which then delegates to *two* specialist agents simultaneously — a search agent and a booking agent. That's a tree (a special case of DAG), not a list. The `parent` field creates the edges; the validation logic walks them.

**Why purpose binding?** Without it, a token issued for "search flights SEA→SFO" could be reused to "book flights JFK→LAX." Purpose binding ties the authority to the intent. This is more restrictive than OAuth2 scopes, and that's deliberate — agents are autonomous and the blast radius of a misused token is larger.

**Why `scope` is a list with constraint syntax?** A scope like `travel.book:max_$500` carries both the permission (`travel.book`) and the constraint (`max $500`). The `:` separator lets you attach arbitrary constraints to any scope without changing the schema. The service parses the constraint; the protocol just carries it.

### Cost Certainty

```python
class CostCertainty(str, Enum):
    FIXED = "fixed"
    ESTIMATED = "estimated"
    DYNAMIC = "dynamic"
```

Three levels, not two. The original design had just "known" and "unknown," but that collapsed two very different situations:

- **Fixed** — searching flights is free. Always. The cost is `$0.00` and that's a guarantee.
- **Estimated** — booking a flight costs approximately `$420 ±10%`. The exact cost depends on which flight you pick, but we can give you a range. And critically, `determined_by: "search_flights"` tells the agent *which capability resolves the estimate into an exact number.*
- **Dynamic** — surge pricing, market rates, auction-based services. The cost depends on factors the service can enumerate (`factors: ["time_of_day", "demand"]`) but can't predict. The best the service can do is declare an `upper_bound`.

The `determined_by` field on estimated costs is the subtle power move. It connects cost signaling to the capability graph — the agent knows it should invoke `search_flights` to get exact pricing before committing to `book_flight`. Without this, agents would either over-request (always assume worst-case) or under-request (be surprised by the bill).

### Failure Semantics

```python
class ANIPFailure(BaseModel):
    type: str           # machine-readable category
    detail: str         # human-readable explanation
    resolution: Resolution
    retry: bool = True

class Resolution(BaseModel):
    action: str                          # what to do
    requires: str | None                 # what's needed
    grantable_by: str | None             # who can help
    estimated_availability: str | None   # when it might be available
```

**Why not just HTTP status codes?** Because `403 Forbidden` tells an agent nothing actionable. ANIP failures answer three questions: What went wrong? What do I need to fix it? Who can give me what I need?

The `resolution.grantable_by` field is the key insight. When an agent lacks `travel.book` scope, the failure tells it: "You need `travel.book`, and `human:samir@example.com` can grant it." The agent doesn't guess — it can escalate to the right principal.

`retry: true` vs `retry: false` is the primary branching condition for agent recovery loops. If `retry: true`, the agent should fix the issue (request scope, refresh token, adjust parameters) and try again. If `retry: false`, this path is blocked — the agent needs a fundamentally different approach.

---

## 2. Capability Declarations

**Files:** `anip_server/capabilities/search_flights.py`, `anip_server/capabilities/book_flight.py`

Each capability has two parts: a `DECLARATION` (static metadata) and an `invoke` function (runtime behavior). This separation is intentional — the declaration can be served from the manifest without executing any code.

### Read-Only vs. Irreversible

Compare the two declarations side by side:

| Field | `search_flights` | `book_flight` |
|-------|-------------------|---------------|
| `side_effect` | `read`, `not_applicable` | `irreversible`, `none` |
| `cost.certainty` | `fixed` ($0.00) | `estimated` ($280–$500) |
| `required_scope` | `travel.search` | `travel.book` |
| `requires` | *(none)* | `search_flights` |
| `observability.fields_logged` | parameters, result_count | parameters, result, cost_actual, delegation_chain |

Notice the differences in observability: the irreversible capability logs *everything* including the full delegation chain and actual cost. The read-only capability logs just parameters and result count. This isn't incidental — it reflects the risk profile. Irreversible actions need full audit trails; read queries don't.

### The `requires` Field

```python
requires=[
    CapabilityRequirement(
        capability="search_flights",
        reason="must select from available flights before booking",
    ),
]
```

This creates a directed edge in the capability graph. It's not a suggestion — it's a dependency. The service enforces this: if you try to book a flight that doesn't exist in the search results, you'll get a `capability_unavailable` failure.

**Why declare it rather than just fail?** Because an agent can read the graph *before* attempting anything. Without this declaration, the agent would have to discover the dependency by trial and error — invoke `book_flight`, get a failure, read the failure, figure out it needs to search first. With the declaration, the agent never makes the failing call.

### The `invoke` Function

```python
def invoke(token: DelegationToken, parameters: dict) -> InvokeResponse:
```

Every capability's invoke function takes the same two arguments: the delegation token (for identity and authorization context) and the parameters (for the actual request). It returns an `InvokeResponse` — always. Never an exception, never a raw HTTP error. This uniformity is what makes ANIP capabilities composable.

The invoke function for `book_flight` follows a specific order:

1. Validate parameters
2. Look up the resource (flight)
3. Check budget authority against the delegation chain
4. Execute the action
5. Return result with `cost_actual`

Step 3 is where ANIP's delegation chain earns its keep. The function calls `check_budget_authority(token, total_cost)`, which walks the token's scope looking for a budget constraint. If the flight costs $420 but the token only authorizes up to $300, the function returns a structured failure — not an exception, not a 403, but an `ANIPFailure` with `type: "budget_exceeded"` and a `resolution` telling the agent exactly who can increase the budget.

Step 5 returns `cost_actual` — the real cost after execution. For estimated-certainty capabilities, this lets agents track `variance_from_estimate` over time, which feeds into the trust model.

---

## 3. Delegation Chain Validation

**File:** `anip_server/primitives/delegation.py`

This is the most important primitive — it's what makes ANIP more than just "REST with better error messages."

### The Validation Sequence

When a capability is invoked, `validate_delegation()` runs five checks in order:

1. **Token expiry** — is this token still valid?
2. **Scope matching** — does the token carry the required scope?
3. **Purpose binding** — was this token issued for this capability?
4. **Delegation depth** — is the chain too deep?
5. **Parent chain validation** — are all ancestor tokens valid and not expired?

The order matters. Expiry is cheapest to check, so it goes first. Parent chain validation requires walking the DAG, so it goes last.

### Scope Matching

```python
for scope in token.scope:
    scope_base = scope.split(":")[0]  # "travel.book:max_$500" → "travel.book"
    if scope_base == required_scope or required_scope.startswith(scope_base + "."):
        scope_matched = True
        break
```

The `:` splits scope from constraints. The prefix matching (`startswith`) allows hierarchical scopes — `travel` would match `travel.search` and `travel.book`. Note: wildcard syntax (`travel.*`) is deliberately not defined in v0.1 (see [Spec §12, Open Question 7](SPEC.md)).

### Budget Authority

```python
def check_budget_authority(token: DelegationToken, amount: float) -> ANIPFailure | None:
    for scope in token.scope:
        if ":max_$" in scope:
            max_budget = float(scope.split(":max_$")[1])
            if amount > max_budget:
                return ANIPFailure(...)
    return None
```

Budget constraints live inside scope strings (`travel.book:max_$500`). This keeps the token schema simple — no extra fields for every possible constraint type. The tradeoff is that constraint parsing is convention-based, not schema-enforced. For v0.1, this is acceptable; a formal constraint language is a v2 concern.

### The Token Store

```python
_token_store: dict[str, DelegationToken] = {}
```

The reference implementation uses an in-memory dict. In production, this would be a database, a JWT verification service, or a distributed cache. The token store is the one part of the delegation primitive that's explicitly not portable — it depends entirely on your deployment model.

**What ANIP defines:** the token *semantics* (fields, validation rules, chain structure).

**What ANIP does not define:** the token *format* (JWT, Verifiable Credentials, custom) or *storage* (database, cache, stateless verification). This is Open Question 5 in the spec.

---

## 4. The Discovery Endpoint

**File:** `anip_server/main.py`, lines 42–112

The discovery endpoint at `/.well-known/anip` is the single entry point to the protocol. It's designed to answer one question: *"Should I engage with this service, and if so, how?"*

### What Gets Computed at Request Time

```python
base_url = str(request.base_url).rstrip("/")
```

`base_url` is derived from the incoming request, not hardcoded. This matters for services behind load balancers, reverse proxies, or running on multiple domains. If you hardcode it, agents behind different network paths will construct broken URLs.

### Capability Summaries vs. Full Declarations

The discovery document includes a **summary** of each capability — not the full declaration. This is deliberate:

```python
capabilities_summary = {
    name: {
        "description": cap.description,
        "side_effect": cap.side_effect.type.value,
        "minimum_scope": [cap.required_scope],
        "financial": cap.cost.financial is not None and cap.cost.financial.get("amount", 0) > 0,
        "contract": cap.contract_version,
    }
    for name, cap in _manifest.capabilities.items()
}
```

Five fields per capability in discovery vs. 12+ in the manifest. An agent can make 90% of its decisions from just these five: Can I afford it? Is it dangerous? Do I have permission? Has the contract changed since I last cached the manifest?

The `minimum_scope` is always an array (AND semantics). Even when there's only one scope, it's `["travel.search"]`, not `"travel.search"`. This prevents a breaking change when a capability later requires compound authorization (e.g., `["travel.book", "payments.authorize"]`).

The `financial` flag is computed, not declared — it's `true` when the capability has a non-zero financial cost. This lets agents distinguish "irreversible and costs money" (booking a flight) from "irreversible but free" (sending a notification).

### Compliance Detection

```python
compliance = "anip-complete" if all([
    profiles.get("cost"),
    profiles.get("capability_graph"),
    profiles.get("state_session"),
    profiles.get("observability"),
]) else "anip-compliant"
```

Compliance is derived from the profile, not declared independently. This prevents the inconsistency where a service claims `anip-complete` but doesn't actually implement all 9 primitives.

---

## 5. Permission Discovery

**File:** `anip_server/primitives/permissions.py`

Permission discovery answers: *"Given my delegation token, what can I do here?"*

### Three Buckets

```python
available: list[AvailableCapability]    # you can do this
restricted: list[RestrictedCapability]  # you can't, but someone can grant it
denied: list[DeniedCapability]          # you can't, period
```

The distinction between `restricted` and `denied` is important. `restricted` means the agent is missing a scope that its root principal *could* grant. `denied` means no amount of scope escalation will help — the capability requires admin access and the agent's chain starts from a standard user.

This three-bucket model lets agents build recovery strategies. For `restricted` capabilities, the agent can escalate to `grantable_by`. For `denied` capabilities, the agent should not waste time trying.

---

## 6. The Invocation Flow

**File:** `anip_server/main.py`, lines 178–207

When an agent invokes a capability, four things happen in order:

```python
# 1. Check capability exists
if capability_name not in _capability_handlers:
    return InvokeResponse(success=False, failure=ANIPFailure(type="unknown_capability", ...))

# 2. Get the capability declaration for scope requirements
cap_declaration = _manifest.capabilities[capability_name]

# 3. Validate delegation chain
delegation_failure = validate_delegation(token=..., required_scope=..., capability_name=...)
if delegation_failure is not None:
    return InvokeResponse(success=False, failure=delegation_failure)

# 4. Invoke the capability
handler = _capability_handlers[capability_name]
return handler(request.delegation_token, request.parameters)
```

Notice: the endpoint doesn't know anything about flights. It doesn't validate parameters, check prices, or create bookings. It validates the *protocol layer* (does this capability exist? is the delegation valid?) and then hands off to the *capability layer* (the handler function). This separation means adding a new capability requires zero changes to the endpoint — you just add a handler to the registry and a declaration to the manifest.

---

## 7. The Demo — An Agent's Perspective

**File:** `examples/anip/demo.py`

The demo script simulates a complete agent interaction in 7 phases. It's the best way to understand ANIP from the consumer side.

### Phase 1: Discovery & Handshake

```python
resp = client.get("/.well-known/anip")
discovery = resp.json()["anip_discovery"]
endpoints = discovery["endpoints"]
```

One request. The agent now knows every endpoint, every capability, every profile version, and the service's compliance level. Compare this to REST, where the agent would need to read documentation (designed for humans), parse an OpenAPI spec (designed for code generators), or discover endpoints by trial and error.

### Phase 2: Delegation Chain as DAG

The demo constructs a two-level chain: human → orchestrator → booking agent.

```
root_token:    human:samir → agent:orchestrator-7x
                    ↓
booking_token: agent:orchestrator-7x → agent:booking-agent-3a
```

Each token narrows the scope. The human grants `travel.search` + `travel.book:max_$500`. The orchestrator passes the same scope to the booking agent. In a real system, the orchestrator might narrow further — granting only `travel.search` to a research sub-agent and both scopes to the booking sub-agent.

### Phase 7: Failure Scenarios

The demo's failure scenarios are the most important part. They show three cases:

**Insufficient scope** — the agent tries to book without `travel.book`. The failure tells it exactly what scope it needs and who can grant it.

**Budget exceeded** — the agent tries to book a $580 flight with a $500 budget limit. The failure tells it the gap and who can increase the budget.

**Purpose mismatch** — the agent reuses a `book_flight` token for `search_flights`. The failure explains the binding violation.

In each case, the agent gets a structured recovery path, not a status code. That's the ANIP difference.

---

## Design Decisions Worth Understanding

### Why Not Just Extend OpenAPI?

OpenAPI describes HTTP endpoints for human developers to build client libraries. ANIP describes *capabilities* for AI agents to reason about. The gap isn't syntax — it's semantics. OpenAPI has no concept of delegation chains, side-effect types, cost signaling, or capability prerequisites. You could encode these as OpenAPI extensions, but you'd be fighting the abstraction rather than building on it.

ANIP is complementary to OpenAPI, not competitive. A service can expose both an OpenAPI spec (for human developers) and an ANIP manifest (for agent consumers) over the same underlying functionality.

### Why Trust-on-Declaration?

Because the alternative — requiring cryptographic verification for every declaration — would make ANIP impossible to adopt. No service would implement it if the barrier to entry was "also build a certificate authority." Trust-on-declaration for v1 mirrors the web's early approach: `robots.txt` is trust-on-declaration, and it worked well enough to bootstrap an ecosystem. The spec is explicit about this tradeoff and defines the path to verification in v2 ([Spec §7](SPEC.md)).

### Why Separate Tokens Per Capability?

Purpose binding is more restrictive than OAuth2's scope-based model. An OAuth2 token with `travel:write` scope works for any write operation in the travel domain. An ANIP delegation token with `purpose.capability: "book_flight"` works only for booking flights.

The tradeoff is more tokens. The benefit is smaller blast radius — a compromised or misused token can only do what it was issued for, not everything its scope permits. For autonomous agents operating without real-time human oversight, this tradeoff is correct.

### Why `cost_actual` in the Response?

Because declared costs are estimates. The only way to build trust in cost signaling is to let agents compare `cost.estimated` (what the service said it would cost) against `cost_actual` (what it actually cost). Over time, services with consistently accurate estimates build reputation; services with consistently wrong estimates lose it. This is the seed of the runtime reputation system described in the v2 trust model.

---

## Running the Reference Implementation

```bash
cd examples/anip

# Option 1: Local
uv venv && source .venv/bin/activate
uv pip install -e .
uvicorn anip_server.main:app --reload

# Option 2: Docker
docker build -t anip-demo .
docker run -p 8000:8000 anip-demo

# Run the demo
python demo.py
```

The demo runs all 7 phases and prints annotated output showing the full protocol flow.

---

## Next Steps

- Read the [Spec](SPEC.md) for formal definitions of all primitives
- Read the [agent skills](skills/) for machine-optimized interaction guides
- Check [Open Questions](SPEC.md) §12 for areas where community input is needed
- See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get involved
