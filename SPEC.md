# ANIP Specification v0.1

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

The concrete format for capability declarations (JSON Schema, a purpose-built IDL, or another approach) is an open design question. The schema above represents the semantic structure that any format must express.

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
- **Format-agnostic.** ANIP v1 defines the semantic structure above. Implementations MAY use JWTs, signed payloads, or other token formats that can express this structure. The semantic model is inspired by W3C Verifiable Credentials, and future versions may define a standard cryptographic binding.

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

```yaml
# Service declares (part of capability manifest)
cost:
  financial: { amount: 420, currency: "USD", variance: "±10%" }
  compute: { latency_p50: "2s", tokens: 1500 }
  rate_limit: { requests_per_minute: 60, remaining: 42 }
```

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

## 6. Manifest & Profile Handshake

Every ANIP service exposes a **manifest** — a machine-readable declaration of what the service supports.

```yaml
anip_manifest:
  protocol: "anip/1.0"
  profile:
    core: "1.0"
    cost: "1.0"
    capability-graph: "1.0"
    observability: "1.0"
  capabilities:
    search_flights:
      contract: "1.0"
      description: "Search available flights"
      # ...full capability declaration
    book_flight:
      contract: "2.1"
      description: "Book a confirmed flight reservation"
      # ...full capability declaration
```

Each profile extension is independently versioned. An agent can require `core@1.x` and `observability@1.x` without caring about the others. Extensions evolve at different rates.

### Profile Handshake

The first interaction between an agent and an ANIP service is a **profile handshake**:

```
Agent → Service:  "What profiles do you speak?"
Service → Agent:  { core: "1.0", cost: "1.0", capability-graph: "1.0" }
Agent:            [checks against task requirements]
                  [proceeds if requirements met, bails if not]
```

Tasks declare their own profile requirements. Matching happens before any capability is invoked. An agent whose task requires observability contracts can bail immediately if the service doesn't support them, rather than discovering this mid-interaction.

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

## 8. Versioning

ANIP has three distinct versioning problems:

### 8.1 Protocol Version

"I speak ANIP v1.0." Declared in the manifest. Follows semantic versioning. A major version bump (v1 → v2) indicates breaking changes to core primitive schemas.

### 8.2 Capability Contract Version

"My `book_flight` capability changed." Each capability has a contract version. The contract includes the capability's inputs, outputs, side-effect type, cost shape, and permission requirements. Any change to these bumps the contract version.

An agent can query: "Do you still have `book_flight` at contract v2?" rather than discovering breaking changes at invocation time.

### 8.3 Capability Profile Version

Which extensions are implemented, independently versioned. Cost signaling might reach v3 while core is still at v1. Each profile extension declares its own version in the manifest.

An agent requiring specific profile versions can express this during the handshake: "I need `core@1.x` and `cost@2.x`."

---

## 9. Transport

ANIP v1 is defined over HTTP. The semantic layer — capability declarations, delegation tokens, permission queries, failure objects — is transport-agnostic by design.

Capability declarations say "invoke," not "POST." Failure objects are ANIP structures, not HTTP status codes. The HTTP binding maps ANIP semantics to HTTP mechanics, but the semantics do not depend on HTTP.

Future versions will define bindings for other transports (gRPC, NATS, WebSocket, etc.). The key constraint: no HTTP-isms leak into the semantic layer.

---

## 10. V1 Non-goals

The following are explicitly out of scope for ANIP v1:

- **Multi-agent distributed transactions.** The delegation chain is DAG-ready, but coordinating transactions across multiple ANIP services is not addressed. The primitives are designed not to preclude this in future versions.
- **Non-HTTP transport bindings.** V1 is HTTP-first. Other transports are a future concern.
- **Registry or discovery service.** How an agent *finds* ANIP services is a separate problem. V1 assumes the agent already knows where the service is.
- **Trust verification enforcement.** V1 is trust-on-declaration. Verification is a v2 priority.
- **Cryptographic token format mandate.** V1 defines delegation token semantics, not cryptographic format.

---

## 11. Open Questions

These are unresolved design questions where community input is needed:

1. **Capability declaration format.** Should ANIP use JSON Schema, a purpose-built IDL, an extension of OpenAPI, or something else entirely? The semantic structure is defined; the concrete syntax is not.

2. **Relationship to existing standards.** How should ANIP relate to OpenAPI, JSON-LD, AsyncAPI, and other existing standards? Complement them? Replace them in agent contexts? Provide a mapping layer?

3. **Registry model.** Should there be a registry for ANIP-compliant services, similar to npm for packages or DNS for domains? What would discovery look like?

4. **Side-effect type completeness.** Is `eventually_consistent` a distinct side-effect type that belongs in v1? Are there other side-effect categories we're missing?

5. **Delegation chain auth format.** What concrete token format should ANIP recommend? JWT is familiar but has limitations for DAG delegation. W3C Verifiable Credentials are semantically richer but have adoption barriers. Should v1 recommend one, or remain format-agnostic?

6. **Service advertisement.** How does a service advertise that it supports ANIP? A well-known URL (`/.well-known/anip`)? A DNS record? An HTTP header? All of the above?

---

*ANIP is an open specification under active development. This is v0.1 — the foundation, not the finished product. If you see something missing, wrong, or underspecified, [open an issue](https://github.com/anthropics/anip/issues).*
