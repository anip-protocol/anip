# ANIP Specification v0.2

> Agent-Native Interface Protocol — Draft

---

## 1. Motivation

An agent wants to book a flight.

Today, it reads an OpenAPI spec written for human developers. It guesses that `POST /bookings` is the right endpoint. It discovers auth requirements by getting a 401. It discovers insufficient permissions by getting a 403. It books the flight. It discovers the charge was $800, not the expected $420, because of an undeclared currency conversion. It cannot undo the booking because no rollback information was available. An audit log exists, but the agent didn't know to check it.

With ANIP, the agent queries a manifest and receives a profile handshake. It sees `book_flight` declared as irreversible, financial, with a cost of ~$420±10%. It checks that its delegation chain carries `travel.book` scope with $500 budget authority. It confirms there is no rollback window. It confirms the interaction is logged with 90-day retention. It decides to proceed and executes with full context.

The difference is not sophistication — it's design intent. ANIP interfaces are designed for agents from the ground up.

## 2. Design Philosophy

> *Make implicit assumptions explicit, typed, and negotiable.*

Every component of ANIP passes one test: does this take something agents currently have to guess, infer, or discover through failure, and make it declared, typed, and queryable?

ANIP is not a patch on REST. It is not a wrapper around existing APIs. It is a new interface paradigm for a new kind of consumer: AI agents that reason, plan, and act with delegated authority.

## 3. Compliance Levels

**ANIP-compliant** — An interface that implements the 5 core primitives (Section 4). An agent interacting with an ANIP-compliant service can operate safely: it knows what it can do, what will happen, who it's acting for, what it's allowed to do, and what went wrong if something fails.

**ANIP-complete** — An interface that implements all 9 primitives (Sections 4 and 5). An agent interacting with an ANIP-complete service can operate optimally: it additionally knows what things cost, how capabilities relate to each other, whether interactions are stateful, and what's being observed.

Services MUST implement all 5 core primitives to claim ANIP compliance. Services SHOULD implement contextual primitives using the standardized schemas defined in Section 5. Partial implementation of contextual primitives is permitted — a service MAY implement cost signaling without implementing observability contracts, for example — but each implemented primitive MUST conform to its standardized schema.

## 4. Core Primitives

The 5 core primitives are co-designed as a system. They reference each other by design:

- Permission Discovery is a function of Delegation Chain
- Failure Semantics references Delegation Chain scopes and cost constraints
- Capability Declaration includes Side-effect Typing
- Side-effect Typing informs Permission Discovery (irreversible actions may require higher authority)

Designing or implementing any one in isolation will produce seams.

### 4.1 Capability Declaration

A service declares what it can do as intent, not as endpoints. The unit of interaction is a **capability**, not a URL.

A capability declaration tells an agent: what this capability does, what inputs it requires, what side effects it has, and what outputs it produces. It does not expose implementation details like HTTP methods, URL paths, or serialization formats.

```yaml
capability:
  name: book_flight
  description: "Book a confirmed flight reservation"
  inputs:
    - name: origin
      type: airport_code
      required: true
    - name: destination
      type: airport_code
      required: true
    - name: date
      type: date
      required: true
    - name: passengers
      type: integer
      required: true
      default: 1
  output:
    type: booking_confirmation
    fields: [booking_id, flight_number, departure_time, total_cost]
  side_effect:
    type: irreversible
    rollback_window: none
```

A service MUST declare all capabilities in its manifest. Each capability MUST include a name, description, inputs with types, output shape, and side-effect type.

ANIP uses JSON Schema (draft 2020-12) for capability declarations. Canonical schemas are defined in Section 9 and validated across two reference implementations (Python/Pydantic and TypeScript/Zod).

### 4.2 Side-effect Typing

Every capability MUST declare its side-effect type. This tells the agent what will happen to the world when the capability is invoked.

**Side-effect types:**

| Type | Meaning |
|------|---------|
| `read` | No state change. Safe to call repeatedly. |
| `write` | State change, reversible within the rollback window. |
| `irreversible` | State change that cannot be undone. |
| `transactional` | State change with atomic guarantees — fully succeeds or fully rolls back. |

Each side-effect declaration MUST include a `rollback_window`:

```yaml
side_effect:
  type: write
  rollback_window: "PT24H"    # ISO 8601 duration — reversible for 24 hours
```

```yaml
side_effect:
  type: irreversible
  rollback_window: none
```

```yaml
side_effect:
  type: read
  rollback_window: not_applicable
```

The rollback window tells the agent: if you invoke this capability and want to undo it, you have this much time. After the window closes, the action becomes irreversible regardless of its declared type.

For `transactional` capabilities, the rollback window indicates how long the transaction can be held open before the service auto-rolls back.

### 4.3 Delegation Chain

Identity in ANIP is not a header. It is a first-class primitive that represents the full chain of authority from a root principal (typically a human) through one or more agents to the current request.

The delegation chain is structured as a **directed acyclic graph (DAG)**, not a linked list. This supports scenarios where an orchestrator delegates to multiple agents in parallel, all acting on behalf of the same root principal.

A delegation token carries:

```yaml
delegation_token:
  issuer: "human:samir@example.com"
  subject: "agent:orchestrator-7x"
  scope: ["travel.search", "travel.book:max_$500"]
  purpose:
    capability: "book_flight"
    parameters: { from: "SEA", to: "SFO", date: "2026-03-10" }
    task_id: "task_abc789"
  parent: "token_abc123"
  expires: "2026-03-07T18:00:00Z"
  constraints:
    max_delegation_depth: 3
    concurrent_branches: allowed
```

**Fields:**

- **issuer** — who created this token (the delegating entity)
- **subject** — who this token is for (the delegated entity)
- **scope** — what the subject is authorized to do, as a list of capability scopes with optional constraints
- **purpose** — machine-parseable binding to a specific task and capability. Enforces principle of least authority: even a validly scoped token can only be used for its stated purpose.
- **parent** — reference to the parent token in the DAG. The root token (issued by a human) has no parent.
- **expires** — when this delegation expires
- **constraints**:
  - `max_delegation_depth` — how many times this token can be further delegated
  - `concurrent_branches` — whether multiple agents can act under this token simultaneously (`allowed` or `exclusive`). When `exclusive`, a service receiving two concurrent requests from the same root principal MUST reject one.

**Design decisions:**

- **DAG, not list.** An orchestrator delegating to Agent A and Agent B in parallel creates two tokens with the same parent. The service can detect concurrent agents sharing a root principal.
- **Purpose-bound.** Prevents token reuse beyond the intended task. Agent B cannot use a token delegated for flight booking to access expense reports, even if the scope strings overlap.
- **JWT/ES256 in v0.2.** ANIP v0.2 defines JWT (JSON Web Token) with ES256 (ECDSA P-256) as the standard token format. The service is the sole token issuer — agents request tokens via `POST /anip/tokens` with Bearer authentication, and the service returns signed JWTs. The semantic model is inspired by W3C Verifiable Credentials. See [docs/trust-model-v0.2.md](docs/trust-model-v0.2.md) for the full cryptographic trust model.

Every request to an ANIP service MUST include a delegation token. The service MUST validate the token's scope, purpose, expiry, and constraints before processing the request.

### 4.4 Permission Discovery

An agent MUST be able to query its permission scope before attempting any action. The service responds with the agent's effective permissions given its delegation chain.

```yaml
# Agent queries: "What can I do here?"

permission_response:
  available:
    - capability: search_flights
      scope_match: "travel.search"
    - capability: book_flight
      scope_match: "travel.book:max_$500"
      constraints:
        budget_remaining: 500
        currency: "USD"
  restricted:
    - capability: cancel_booking
      reason: "delegation chain lacks scope: travel.cancel"
      grantable_by: "human:samir@example.com"
  denied:
    - capability: admin_override
      reason: "requires admin principal, current chain root is standard user"
```

The permission response MUST include three categories:

- **available** — capabilities the agent can invoke right now, with any relevant constraints
- **restricted** — capabilities the agent can see but cannot invoke, with the reason and who could grant the missing authority
- **denied** — capabilities that exist but are inaccessible to the agent's entire delegation chain

This eliminates trial-and-error permission discovery. The agent knows its full scope before making any decisions.

Permission Discovery is coupled to Delegation Chain by design: the permission surface is a function of the delegation token. Different tokens from the same root principal may have different effective permissions based on their scope and purpose.

### 4.5 Failure Semantics

When something goes wrong, the service MUST return a failure object that an agent can reason about and recover from. Failures reference other ANIP primitives — delegation chain, scope, cost — rather than using opaque codes.

```yaml
failure:
  type: insufficient_authority
  detail: "delegation chain lacks scope: travel.book"
  resolution:
    action: "request_scope_grant"
    requires: "delegation.scope += travel.book"
    grantable_by: "human:samir@example.com"
  retry: true
```

```yaml
failure:
  type: budget_exceeded
  detail: "principal samir@example.com has $200 remaining authority"
  resolution:
    action: "request_budget_increase"
    requires: "delegation.scope travel.book:max raised to $420"
    grantable_by: "human:samir@example.com"
  retry: true
```

```yaml
failure:
  type: capability_unavailable
  detail: "book_flight is temporarily unavailable"
  resolution:
    action: "wait_and_retry"
    estimated_availability: "2026-03-07T15:00:00Z"
  retry: true
```

```yaml
failure:
  type: purpose_mismatch
  detail: "delegation token purpose is book_flight:SEA-SFO but request is for book_flight:SEA-LAX"
  resolution:
    action: "request_new_delegation"
    grantable_by: "agent:orchestrator-7x"
  retry: true
```

**Failure object fields:**

- **type** — machine-readable failure category
- **detail** — human-readable explanation (for debugging and logging)
- **resolution** — what needs to happen to fix this, who can do it, and what action to take
- **retry** — whether the same request could succeed after the resolution is applied

Failure semantics are only meaningful because Delegation Chain is core. Without structured identity, failures collapse to "access denied." With it, failures become "here's exactly what's missing in the chain and who needs to grant it."

A service MUST return failure objects conforming to this schema. A service MUST NOT return failures that lack a `type` and `resolution` field.

---

## 5. Contextual Primitives

Contextual primitives have standardized schemas. A service MAY implement any combination of contextual primitives, but each implemented primitive MUST conform to the schema defined here.

### 5.1 Cost & Resource Signaling

Cost signaling is bidirectional. The service declares what a capability costs. The agent may declare budget constraints. The service responds with the feasible space.

#### Cost Certainty Levels

Not all costs are known upfront. A capability MUST declare how certain its cost information is using one of three certainty levels:

| Certainty | Meaning | Example |
|-----------|---------|---------|
| `fixed` | Exact cost, known before invocation. The manifest cost IS the actual cost. | API calls priced per-request ($0.01/call) |
| `estimated` | Cost falls within a known range. Actual cost is determined by a preceding read operation. | Flights — search returns actual prices, manifest gives a typical range |
| `dynamic` | Cost is unknown until invocation. May vary based on demand, timing, or availability. | Auction bids, market orders, surge-priced services |

```yaml
# Fixed — exact cost, known upfront
cost:
  certainty: fixed
  financial: { amount: 0.01, currency: "USD" }
  compute: { latency_p50: "200ms", tokens: 500 }
```

```yaml
# Estimated — range known, exact cost determined by another capability
cost:
  certainty: estimated
  financial:
    range_min: 280
    range_max: 500
    typical: 420
    currency: "USD"
  determined_by: "search_flights"    # which capability resolves the actual cost
  compute: { latency_p50: "2s", tokens: 1500 }
```

```yaml
# Dynamic — unknown until execution
cost:
  certainty: dynamic
  financial:
    currency: "USD"
    upper_bound: 10000               # worst-case for budget checking
  factors: ["demand", "time_of_day", "availability"]
  compute: { latency_p50: "5s", tokens: 3000 }
```

**Design rationale:**

- **`fixed`** lets the agent make immediate go/no-go decisions from the manifest alone.
- **`estimated`** with `determined_by` connects cost signaling to the capability graph — the agent knows which read operation will resolve the actual price before committing to a write.
- **`dynamic`** with `upper_bound` gives the agent a worst-case for delegation chain budget checking. Even when the exact cost is unknowable, the agent can verify "my authority covers the maximum possible cost."

#### Actual Cost in Responses

For `estimated` and `dynamic` capabilities, the invocation response MUST include the actual cost incurred:

```yaml
result:
  booking_id: "BK-0001"
  flight_number: "UA205"
  total_cost: 380.00
  cost_actual:
    financial: { amount: 380.00, currency: "USD" }
    variance_from_estimate: "-9.5%"
```

The `variance_from_estimate` field tracks how far the actual cost deviated from the manifest's typical estimate. Over time, consistent variance is a trust signal — services whose estimates are systematically inaccurate surface through the trust model (Section 7).

#### Budget Negotiation

Cost signaling is bidirectional. The agent may declare budget constraints in the invocation request:

```yaml
# Agent constrains (part of invocation request)
budget:
  financial: { max: 300, currency: "USD" }
```

```yaml
# Service responds with alternatives
alternatives:
  - cost: { amount: 280, currency: "USD" }
    tradeoffs: ["1 stop", "+3hrs travel time"]
  - cost: { amount: 310, currency: "USD" }
    tradeoffs: ["flexible date: -1 day"]
  - unavailable_within_budget: true
    closest: { amount: 350, currency: "USD" }
```

This subsumes negotiation as an emergent behavior. The agent doesn't negotiate through a special verb — it declares constraints, and the service responds with what's feasible. If nothing fits, the service explains why.

#### Rate Limits

Rate and resource constraints are declared alongside financial cost:

```yaml
rate_limit:
  requests_per_minute: 60
  remaining: 42
  reset_at: "2026-03-07T15:00:00Z"
```

Rate limits SHOULD be included in the manifest for each capability. The `remaining` field is dynamic and is most useful in invocation responses rather than the static manifest.

### 5.2 Capability Graph

Capabilities know their prerequisites and what they compose with. Agents can discover the relationships between capabilities without reading documentation.

```yaml
capability: book_flight
requires:
  - capability: search_flights
    reason: "must select from available flights before booking"
composes_with:
  - capability: add_seat_selection
    optional: true
  - capability: add_travel_insurance
    optional: true
depends_on:
  - capability: validate_passenger_info
    auto_invoked: true    # service handles this internally
```

The capability graph is the ANIP equivalent of hyperlinks in HTML — a navigable capability space. An agent landing on an unfamiliar service can traverse the graph to understand what's possible and in what order, without external documentation.

### 5.3 State & Session Semantics

Interactions may be stateless or stateful. ANIP requires this to be declared explicitly rather than inferred.

```yaml
# Stateless capability
session:
  type: stateless
```

```yaml
# Multi-step workflow
session:
  type: workflow
  steps: 4
  current_step: 2
  continuation_token: "wf_xyz789"
  resumable: true
  timeout: "PT30M"    # workflow expires if not continued within 30 minutes
```

```yaml
# Continuation (two-phase)
session:
  type: continuation
  continuation_token: "cont_abc123"
  resumable: true
```

A service implementing state & session semantics MUST declare the session type for every capability. If a capability is part of a workflow, the response MUST include the continuation token and current step.

### 5.4 Observability Contract

A service declares what it observes, logs, and retains about interactions. This is structured metadata, not a privacy policy written for humans.

```yaml
observability:
  logged: true
  retention: "P90D"                  # ISO 8601 duration
  fields_logged:
    - "capability"
    - "delegation_chain"
    - "parameters"
    - "result"
    - "cost_actual"
  audit_accessible_by:
    - "delegation.root_principal"    # the human at the top of the chain
  real_time_observable: false         # no live streaming of logs
```

A service implementing observability contracts MUST declare what fields are logged and for how long. The agent (or its orchestrator) can use this information to decide whether the service meets its compliance requirements before invoking any capability.

---

## 6. Discovery & Standard Endpoints

ANIP defines a standard set of endpoints that every implementation MUST or SHOULD expose. This ensures that any agent can interact with any ANIP service without out-of-band configuration — the protocol is self-describing from a single, predictable entry point.

This is analogous to OAuth2's `/.well-known/openid-configuration`, which made OpenID Connect discoverable without prior knowledge of a service's URL structure.

### 6.1 Discovery Document

Every ANIP service MUST expose a discovery document at:

```
GET /.well-known/anip
```

This is the **single entry point** to the entire protocol. An agent encountering any domain can check this URL and immediately determine whether the service speaks ANIP, what it supports, and where to find each endpoint.

The discovery document MUST conform to this schema:

```yaml
# GET /.well-known/anip
anip_discovery:
  protocol: "anip/1.0"
  compliance: "anip-complete"              # or "anip-compliant"
  base_url: "https://flights.example.com"
  profile:
    core: "1.0"
    cost: "1.0"
    capability_graph: "1.0"
    state_session: "1.0"
    observability: "1.0"
  auth:
    delegation_token_required: true
    supported_formats: ["anip-v1"]
    minimum_scope_for_discovery: "none"    # no token needed for discovery/manifest
  capabilities:
    search_flights:
      description: "Search available flights between two airports"
      side_effect: "read"
      minimum_scope: ["travel.search"]
      financial: false
      contract: "1.0"
    book_flight:
      description: "Book and confirm a flight reservation"
      side_effect: "irreversible"
      minimum_scope: ["travel.book"]
      financial: true
      contract: "1.0"
  endpoints:
    manifest: "/anip/manifest"
    handshake: "/anip/handshake"
    permissions: "/anip/permissions"
    invoke: "/anip/invoke/{capability}"
    tokens: "/anip/tokens"
    graph: "/anip/graph/{capability}"
    audit: "/anip/audit"
    test: "/anip/test/{capability}"
  metadata:
    service_name: "Flight Booking Service"
    service_description: "ANIP-compliant flight search and booking"
    service_category: "travel.booking"
    service_tags: ["flights", "booking", "irreversible-financial"]
    capability_side_effect_types_present: ["read", "irreversible"]  # informational, derivable from capabilities
    max_delegation_depth: 5
    concurrent_branches_supported: true
    test_mode_available: false
    test_mode_unavailable_policy: "require_explicit_authorization_for_irreversible"
    generated_at: "2026-03-07T10:00:00Z"
    ttl: "PT1H"
```

**Fields:**

- **protocol** (REQUIRED) — the ANIP protocol version this service implements
- **compliance** (REQUIRED) — `"anip-compliant"` (5 core primitives) or `"anip-complete"` (all 9). A service MUST NOT claim `anip-complete` unless all four contextual profile keys (`cost`, `capability_graph`, `state_session`, `observability`) are present in its `profile` block. Agents MUST NOT infer compliance level from counting profile keys — this field is the source of truth.
- **base_url** (REQUIRED) — the absolute base URL for resolving endpoint paths. Agents MUST NOT infer this from the request URL. Explicit over inferred.
- **profile** (REQUIRED) — which profile extensions are implemented, each independently versioned
- **auth** (REQUIRED) — what authentication the service requires, whether tokens are needed for discovery, and which token formats are supported. An agent MUST be able to determine from this field alone whether it can proceed without a delegation token.
- **capabilities** (REQUIRED) — map of capability names to lightweight metadata. Not full declarations — those live at the manifest endpoint. Each entry includes:
  - `description` — what this capability does (one sentence)
  - `side_effect` — the side-effect type (`read`, `write`, `irreversible`, `transactional`). Lets agents identify dangerous capabilities without fetching the manifest.
  - `minimum_scope` — array of delegation scopes REQUIRED to invoke this capability. ALL scopes in the array are required (AND semantics). This is a guarantee, not a hint: an agent whose delegation token lacks any of these scopes MUST NOT attempt invocation. Using an array from day one avoids a breaking change when compound authorization is needed (e.g., `["travel.book", "payments.authorize"]`).
  - `financial` — whether this capability involves financial cost. The `financial` flag MUST be `true` for any capability whose `cost.financial` field is non-null in the manifest, regardless of cost certainty level (`fixed`, `estimated`, or `dynamic`). Implementations MUST NOT use the presence or value of an `amount` key to determine this flag. Capabilities with no financial cost MUST set `cost.financial` to `null` (not a zero-amount object). Lets agents distinguish "irreversible and costs money" from "irreversible but free" — a distinction that matters for authorization handling. When `true`, agents should check cost signaling and budget authority before attempting invocation.
  - `contract` — the current contract version. An agent with a cached manifest can check whether contracts have changed without refetching.
- **endpoints** (REQUIRED) — URLs for each standard endpoint (see Section 6.2)
- **metadata** (RECOMMENDED) — service-level metadata that lets agents make decisions without fetching the full manifest

**Cache validity:**

- `generated_at` — ISO 8601 timestamp of when this discovery document was generated
- `ttl` — ISO 8601 duration for how long this document is valid. After expiry, agents MUST re-fetch. Without a TTL, agents should treat the document as valid for at most 1 hour (the default).

This prevents two failure modes: re-fetching on every interaction (wasteful at scale) and caching indefinitely (dangerous when contracts change).

**Auth field details:**

- `delegation_token_required` — whether the service requires a delegation token for capability invocation
- `supported_formats` — which token formats the service accepts
- `minimum_scope_for_discovery` — the minimum scope needed to access the discovery document and manifest. `"none"` means these are publicly accessible without a token. This is the RECOMMENDED default — capability declarations are not sensitive, and requiring auth for discovery defeats the purpose of zero-configuration entry.

**Capability contracts field:**

This field enables efficient caching. An agent that previously fetched the manifest can compare contract versions at the discovery level. If all versions match its cache, it skips the manifest fetch entirely. This matters at scale — an orchestrator agent interacting with dozens of services per task should not refetch full manifests on every interaction.

**Test mode unavailable policy:**

When `test_mode_available` is `false`, the `test_mode_unavailable_policy` field tells agents how to behave:

- `"proceed_with_caution"` — agent may invoke capabilities but should apply extra validation
- `"require_explicit_authorization_for_irreversible"` — agent MUST obtain explicit human authorization before invoking any capability with side-effect type `irreversible`
- `"block_irreversible"` — agent MUST NOT invoke `irreversible` capabilities without test mode

**Service category and tags (OPTIONAL):**

- `service_category` — machine-readable category for orchestrator-level service selection (e.g., `"travel.booking"`, `"finance.payments"`, `"healthcare.records"`)
- `service_tags` — machine-readable tags for more granular filtering

These are optional in v1 (which assumes the agent already knows the service URL) but become important when a global service registry exists (see Open Questions).

The discovery document is intentionally lightweight. Manifests can grow large as capabilities increase; the discovery document stays small and cacheable. An agent can often decide whether to proceed from the discovery document alone — and with the capability list, contract versions, and auth requirements, it frequently can.

### 6.2 Standard Endpoints

ANIP defines the following standard endpoints. Core endpoints MUST be implemented by every ANIP-compliant service. Contextual endpoints SHOULD be implemented when the corresponding primitive is supported.

#### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/anip` | GET | Discovery document — the single entry point |
| `{manifest}` | GET | Full capability declarations with schemas |
| `{handshake}` | POST | Profile compatibility check |
| `{permissions}` | POST | Permission surface given a delegation token |
| `{invoke}/{capability}` | POST | Invoke a capability with delegation chain and parameters |
| `{tokens}` | POST | Register or validate delegation tokens |

#### Contextual Endpoints

| Endpoint | Method | Profile | Description |
|----------|--------|---------|-------------|
| `{graph}/{capability}` | GET | capability_graph | Capability prerequisites and composition |
| `{audit}` | POST | observability | Audit log query, filtered by root principal |
| `{test}/{capability}` | POST | test | Contract testing sandbox (reserved, v2) |

Endpoint paths in the table above use `{name}` to reference the URL declared in the discovery document's `endpoints` field. Services MAY use any URL paths they choose — the discovery document is the source of truth for where each endpoint lives.

### 6.3 Endpoint Contracts

Each standard endpoint has a normative request/response contract.

#### Discovery — `GET /.well-known/anip`

**Request:** No body. No authentication required.

**Response:** The discovery document (Section 6.1).

An agent MUST be able to fetch this endpoint without a delegation token. This is the only unauthenticated endpoint in the protocol.

#### Manifest — `GET {manifest}`

**Request:** No body. No authentication required.

**Response:** The full ANIP manifest — all capability declarations with their inputs, outputs, side-effect types, cost signals, and observability contracts.

```yaml
anip_manifest:
  protocol: "anip/1.0"
  profile:
    core: "1.0"
    cost: "1.0"
    capability_graph: "1.0"
    state_session: "1.0"
    observability: "1.0"
  capabilities:
    search_flights:
      contract: "1.0"
      description: "Search available flights"
      # ...full capability declaration
    book_flight:
      contract: "1.0"
      description: "Book a confirmed flight reservation"
      # ...full capability declaration
```

The manifest is the full-detail complement to the lightweight discovery document. Each profile extension is independently versioned. An agent can require `core@1.x` and `observability@1.x` without caring about the others.

The manifest endpoint SHOULD be publicly accessible without authentication, as capability declarations are not sensitive. Services that require authentication for the manifest MUST document this in the discovery document's metadata.

#### Handshake — `POST {handshake}`

**Request:**

```yaml
required_profiles:
  core: "1.0"
  cost: "1.0"
  observability: "1.0"
```

**Response:**

```yaml
compatible: true
service_profiles:
  core: "1.0"
  cost: "1.0"
  capability_graph: "1.0"
  state_session: "1.0"
  observability: "1.0"
missing: null
```

Or, if incompatible:

```yaml
compatible: false
service_profiles:
  core: "1.0"
missing:
  cost: "not supported (required: 1.0)"
  observability: "version mismatch: have 0.9, need 1.0"
```

The handshake is the first substantive interaction. The agent declares what profiles it needs; the service responds with whether it can satisfy them. Tasks declare their own profile requirements — matching happens before any capability is invoked.

#### Token Registration — `POST {tokens}`

**Request:** A delegation token (see Section 4.3 for schema).

**Response:**

```yaml
registered: true
token_id: "tok_root_001"
```

In ANIP v0.2 (signed mode, default), the service issues JWT tokens and verifies their ES256 signatures at every protected endpoint. A trust boundary (`_resolve_jwt_token()`) compares all signed JWT claims against stored state, detecting both token forgery and store tampering. Legacy trust-on-declaration mode is available via `ANIP_TRUST_MODE=declaration` for backward compatibility.

#### Permission Discovery — `POST {permissions}`

**Request:** A delegation token.

**Response:** The permission response (see Section 4.4 for schema) — available, restricted, and denied capabilities given the token's scope.

#### Capability Invocation — `POST {invoke}/{capability}`

**Request:**

```yaml
delegation_token: { ... }
parameters: { ... }
budget: { ... }           # optional, for cost negotiation
```

**Response:** An invocation response containing either a result or a failure object (see Section 4.5 for failure schema).

The service MUST validate the delegation token before processing. The service MUST return an ANIP failure object (not an HTTP error) for any authorization, budget, or purpose-binding failure.

The service MUST enforce budget constraints carried in the delegation token's scope. If a scope string includes a budget constraint (e.g., `travel.book:max_$500`) and the capability's cost exceeds that constraint, the service MUST reject the invocation with a `budget_exceeded` failure before executing the capability. Budget enforcement is not optional — a service that accepts a delegation token with budget constraints and ignores them violates the delegation contract.

#### Capability Graph — `GET {graph}/{capability}`

**Request:** No body.

**Response:** The capability's prerequisites and composition relationships (see Section 5.2 for schema).

#### Audit Log — `POST {audit}`

**Request:** A delegation token in the body. Optional query parameters: `capability`, `since` (ISO 8601), `limit`.

**Response:** Audit log entries filtered to the root principal of the provided delegation token. A service MUST NOT return audit entries belonging to other principals. This enforces the observability contract: each principal can only see their own audit trail.

### 6.4 Agent Interaction Flow

The standard endpoints define a predictable interaction sequence:

```
1. Agent discovers service          →  GET /.well-known/anip
2. Agent checks compatibility       →  POST {handshake}
3. Agent fetches full manifest       →  GET {manifest}
4. Agent registers delegation token  →  POST {tokens}
5. Agent queries permissions         →  POST {permissions}
6. Agent explores capability graph   →  GET {graph}/{capability}
7. Agent invokes capability          →  POST {invoke}/{capability}
```

Not every interaction requires all steps. An agent that has previously interacted with a service may skip directly to step 4 if it has cached the manifest. An agent performing a read-only operation may skip the capability graph step. But the sequence above is the canonical flow for a first interaction.

---

## 7. Trust Model

### V1: Trust-on-Declaration

In ANIP v1, services declare their capabilities, side-effects, costs, and observability contracts. Agents trust those declarations.

This is explicitly acknowledged as insufficient for production use at scale. Unlike robots.txt violations (which are economically low-stakes for the violator), ANIP violations involving cost signaling or side-effect declarations have direct financial consequences. The trust-on-declaration model will face adversarial pressure faster than web crawling norms did.

V1 operates on trust-on-declaration with the expectation that verification mechanisms are a priority for v2.

### Path to Verification (v2+)

The solution space includes:

- **Signed manifests** — the service signs its manifest with a verifiable key. Agents can confirm the manifest hasn't been tampered with and was issued by the claimed service.
- **Third-party attestation** — a registry or auditor vouches for manifest accuracy, similar to certificate authorities for TLS.
- **Runtime reputation** — agents track declared vs. actual behavior over time and share reputation signals.
- **Contract testing** — a standardized sandbox where agents or auditors can invoke capabilities and verify that declared side-effects match actual behavior.

Contract testing schema:

```yaml
capability: book_flight
test_mode:
  available: true
  isolation: sandboxed        # vs. recorded, vs. dry-run
  side_effects: suppressed    # actual charges don't occur
  fidelity: behavioral        # responses reflect real logic, not stubs
```

The `fidelity` field matters: `behavioral` means the service runs real logic in a sandboxed context, not just stub responses. Behavioral fidelity is RECOMMENDED but not required. Services SHOULD support `behavioral` fidelity; services MAY start with `dry-run` fidelity as a stepping stone.

---

## 8. Conformance & Testability

ANIP's trust model (§7) relies on declaration in v1. But declaration without verification is aspiration, not a protocol. This section defines what conformance means and how it can be tested — laying the groundwork for the contract testing path described in §7.

### 8.1 Conformance Levels

An ANIP implementation can be validated at three levels of rigor:

1. **Structural conformance** — the implementation produces valid ANIP documents. Discovery, manifest, delegation tokens, failure objects, and invocation responses all conform to the defined schemas. This is fully testable from the outside with no service cooperation.

2. **Semantic conformance** — the implementation behaves consistently with its declarations. A capability declared as `read` produces no state changes. A capability declared as `irreversible` cannot be rolled back. Permission discovery matches actual invocation behavior. This requires either service cooperation (sandbox mode) or sustained observation.

3. **Behavioral conformance** — the implementation handles edge cases correctly. Expired tokens are rejected. Purpose-binding is enforced. Budget authority is checked. Delegation depth limits are respected. This is testable from the outside using adversarial inputs.

Services MUST pass structural conformance. Services SHOULD pass behavioral conformance. Semantic conformance is a SHOULD for v1, with the expectation that it becomes a MUST when contract testing infrastructure exists (v2+).

### 8.2 Conformance Test Categories

The following categories define the surface area of ANIP conformance testing:

**Category 1: Discovery Validation**
- `/.well-known/anip` returns a valid discovery document
- `compliance` field matches profile contents (if all 9 primitives are declared, compliance MUST be `anip-complete`)
- `capability_side_effect_types_present` is consistent with per-capability `side_effect` declarations
- All declared endpoints resolve (return non-404)
- `minimum_scope` arrays are consistent between discovery and manifest

**Category 2: Handshake Validation**
- Profile handshake correctly accepts matching profile requirements
- Profile handshake correctly rejects unsupported or version-mismatched profiles
- Response includes the full set of service profiles

**Category 3: Capability Contract Validation**
- Manifest capabilities match discovery capability summaries (names, side-effect types, contract versions)
- `financial` flag in discovery is consistent with cost signaling in manifest (`cost.financial` is non-null → `financial: true`)
- Capability inputs and outputs conform to declared schemas

**Category 4: Delegation Chain Validation**
- Tokens with expired TTL are rejected with `delegation_expired` failure type
- Purpose-binding is enforced: a token issued for `book_flight` cannot invoke `search_flights`
- `max_delegation_depth` is enforced: tokens exceeding depth are rejected
- Parent chain is validated: a token referencing an unregistered parent is rejected
- Scope narrowing: a child token cannot have broader scope than its parent

**Category 5: Failure Semantics Validation**
- All failures return structured failure objects conforming to Section 4.5, not raw HTTP error codes
- Failure objects include `type`, `detail`, `resolution`, and `retry` fields
- `resolution` includes actionable information (what's needed, who can grant it)
- Unknown capabilities return `unknown_capability` with `check_manifest` resolution

**Category 6: Behavioral Contract Testing**
- Sandbox invocations (when `test_mode_available: true`) match declared side-effect types
- Read capabilities produce no observable state changes
- Cost actuals fall within declared cost ranges (for `estimated` certainty)

> **Limitation:** Category 6 is not fully verifiable from the outside. A service declaring `side_effect: read` could still mutate state internally. Full semantic conformance requires either sandbox cooperation or third-party attestation. The spec acknowledges this gap — it is a core motivation for the v2 trust model work.

### 8.3 Conformance Test Suite

ANIP v0.2 defines the test categories and expected behaviors above. A reference conformance test suite is included in v0.2 at `tests/test_conformance.py`. It validates side-effect accuracy, scope enforcement, budget enforcement, failure semantics, and cost accuracy against any ANIP service.

The conformance test suite:

- Accepts a base URL via `--anip-url` and runs all tests without service cooperation
- Accepts optional API key via `--anip-api-key` for authenticated endpoints
- Outputs structured results indicating pass/fail per category with specific violations
- Is runnable by service implementers, agent developers, and third-party auditors

---

## 9. Schema Definitions

The YAML examples throughout this specification (Sections 4–6) define the semantic structure of each ANIP type. Machine-readable JSON Schema definitions that formalize these structures are maintained alongside the spec:

- **[`schema/anip.schema.json`](schema/anip.schema.json)** — Canonical schema for all ANIP types: `DelegationToken`, `CapabilityDeclaration`, `PermissionResponse`, `InvokeRequest`, `InvokeResponse`, `CostActual`, and `ANIPFailure`. Each type references the spec section that defines its semantics.
- **[`schema/discovery.schema.json`](schema/discovery.schema.json)** — Schema for the `/.well-known/anip` discovery document (Section 6.1), including `minimum_scope` array validation, `financial` boolean flag, and side-effect type enums.

**Relationship between spec and schemas:**

The spec is authoritative for *semantics* — what fields mean, how they interact, what invariants hold. The JSON Schemas are authoritative for *structure* — what fields exist, what types they have, which are required. When the spec adds or modifies a type, the corresponding schema MUST be updated. When the schemas validate a document, the spec's semantic constraints (e.g., "scope can only narrow, never widen") are not checked — those require runtime validation.

Implementations can use these schemas for:
- **Validation** — verify that discovery documents, tokens, and invocation payloads conform to the expected structure before processing
- **Code generation** — generate type definitions in any language from the canonical schema
- **Conformance testing** — Category 1 structural conformance (Section 8.2) can be automated using these schemas

---

## 10. Versioning

ANIP has three distinct versioning problems:

### 10.1 Protocol Version

"I speak ANIP v1.0." Declared in the manifest. Follows semantic versioning. A major version bump (v1 → v2) indicates breaking changes to core primitive schemas.

### 10.2 Capability Contract Version

"My `book_flight` capability changed." Each capability has a contract version. The contract includes the capability's inputs, outputs, side-effect type, cost shape, and permission requirements. Any change to these bumps the contract version.

An agent can query: "Do you still have `book_flight` at contract v2?" rather than discovering breaking changes at invocation time.

### 10.3 Capability Profile Version

Which extensions are implemented, independently versioned. Cost signaling might reach v3 while core is still at v1. Each profile extension declares its own version in the manifest.

An agent requiring specific profile versions can express this during the handshake: "I need `core@1.x` and `cost@2.x`."

---

## 11. Transport

ANIP v1 is defined over HTTP. The semantic layer — capability declarations, delegation tokens, permission queries, failure objects — is transport-agnostic by design.

Capability declarations say "invoke," not "POST." Failure objects are ANIP structures, not HTTP status codes. The HTTP binding maps ANIP semantics to HTTP mechanics, but the semantics do not depend on HTTP.

Future versions will define bindings for other transports (gRPC, NATS, WebSocket, etc.). The key constraint: no HTTP-isms leak into the semantic layer.

---

## 12. V1 Non-goals

The following are explicitly out of scope for ANIP v1:

- **Multi-agent distributed transactions.** The delegation chain is DAG-ready, but coordinating transactions across multiple ANIP services is not addressed. The primitives are designed not to preclude this in future versions.
- **Non-HTTP transport bindings.** V1 is HTTP-first. Other transports are a future concern.
- **Registry service.** How an agent *finds* ANIP services across the internet (like DNS for domains) is a separate problem. V1 defines service-level discovery via `/.well-known/anip` but does not define a global registry.
- **Trust verification enforcement.** ~~V1 is trust-on-declaration.~~ *Resolved in v0.2:* signed mode (default) uses JWT/ES256 with full cryptographic verification. Trust-on-declaration remains available for development via `ANIP_TRUST_MODE=declaration`.
- **Cryptographic token format mandate.** ~~V1 defines delegation token semantics, not cryptographic format.~~ *Resolved in v0.2:* JWT with ES256 is the standard format. JWKS endpoint at `/.well-known/jwks.json` for public key discovery.

---

## 13. Roadmap: v0.1 → v2

Not all gaps are equal. The critical distinction is between *protocol requirement level* (what the spec mandates), *reference implementation status* (what the code ships), and *future protocol work* (what requires interoperability design). Conflating these overpromises. Each feature below is categorized across all three dimensions — an empty cell means no claim is being made.

| Feature | Protocol Requirement Level | Reference Implementation Status | Future Protocol Work |
|---------|---------------------------|--------------------------------|---------------------|
| **Budget enforcement** | MUST — v0.1 core (§6.3) | Implemented | — |
| **Scope narrowing** | MUST — v0.1+ | Implemented: reference servers reject child tokens that widen parent scope | — |
| **Concurrent branch exclusivity** | SHOULD — v0.1+ | Implemented: reference servers enforce `concurrent_branches: "exclusive"` per root principal with atomic check-and-acquire (Python uses `threading.Lock`; TypeScript is single-threaded) | Distributed enforcement across replicas is a deployment concern |
| **Cost variance tracking** | MAY — v0.1+ | Implemented: reference servers record declared vs actual costs in audit log | — |
| **Signed delegation tokens** | MUST — v0.2 core | Implemented: server-issued JWT/ES256, JWKS discovery, trust boundary verification | Interoperable trust semantics: issuer trust, revocation, DAG-aware key discovery |
| **Signed manifests** | MUST — v0.2 core | Implemented: detached JWS (ES256) in `X-ANIP-Signature` header, manifest metadata with SHA-256 hash | Third-party manifest attestation |
| **Audit log integrity** | MUST — v0.2 core | Implemented: hash chain with per-entry signatures, separate audit signing key | Append-only infrastructure, third-party attestation, external timestamp anchoring |
| **Conformance test suite** | SHOULD — v0.2 | Implemented: portable test suite at `tests/test_conformance.py` with `--anip-url` flag | Side-effect contract testing (§7), sandbox infrastructure |
| **Cryptographic chain verification** | — | — | Authorization server, cryptographic DAG validation across services, federated trust |

The guiding principle: v0.1 declared the contracts. v0.2 adds cryptographic enforcement for delegation tokens, manifests, and audit logs. Future versions will extend trust guarantees across service boundaries. The distinction is not coding difficulty — it is protocol maturity. A "Protocol Requirement Level" of `—` means we are not claiming it as a guarantee. A "Reference Implementation Status" of `Implemented` means the code exists. A "Future Protocol Work" entry means we know what's needed and why it's hard.

**What solving these gaps unlocks.** When trust and verification become real — not declarative — agents can evaluate risk before acting. Delegated authority becomes expressible in ways current tool layers can't handle. Failures become operationally useful, not just descriptive. High-stakes actions — travel, procurement, finance ops, approvals, multi-step orchestration — become automatable with real control surfaces. At that point, ANIP solves one of the central coordination problems of agent deployment: how an agent knows what it's allowed to do, what will happen if it does it, and how to recover when something blocks it.

---

## 14. Open Questions

These are unresolved design questions where community input is needed:

1. **Relationship to existing standards.** How should ANIP relate to OpenAPI, JSON-LD, AsyncAPI, and other existing standards? Complement them? Replace them in agent contexts? Provide a mapping layer?

2. **Registry model.** Should there be a registry for ANIP-compliant services, similar to npm for packages or DNS for domains? What would discovery look like?

3. **Side-effect type completeness.** Is `eventually_consistent` a distinct side-effect type that belongs in v1? Are there other side-effect categories we're missing?

4. ~~**Delegation chain auth format.** What concrete token format should ANIP recommend?~~ *Resolved in v0.2:* JWT with ES256 (ECDSA P-256). The service is the sole token issuer. JWKS endpoint at `/.well-known/jwks.json` for public key discovery. See [SECURITY.md](SECURITY.md) and [docs/trust-model-v0.2.md](docs/trust-model-v0.2.md).

5. **Global service registry.** Service-level discovery is solved via `/.well-known/anip`. But should there be a global registry where agents can discover ANIP services by capability? (e.g., "find me services that can book flights")

6. **Wildcard scope matching.** Should ANIP define wildcard scope patterns (e.g., `travel.*` matching all `travel.` scopes)? If two services implement wildcards differently, agents will break. This needs either a formal definition or an explicit prohibition in v1.

**Resolved:**

- **Capability declaration format.** ANIP uses JSON Schema (draft 2020-12). Canonical schemas are defined in Section 9 and validated across two reference implementations (Python/Pydantic and TypeScript/Zod). *(Resolved in v0.1)*
- **Delegation chain auth format.** JWT with ES256 (ECDSA P-256). Server-issued tokens with JWKS discovery. *(Resolved in v0.2)*

---

*ANIP is an open specification under active development. This is v0.2 — cryptographic trust foundations are in place, with federated trust and cross-service delegation as future goals. If you see something missing, wrong, or underspecified, [open an issue](https://github.com/anip-protocol/anip/issues).*

---

*© 2026 ANIP Contributors. Licensed under [CC-BY 4.0](LICENSE-SPEC).*
