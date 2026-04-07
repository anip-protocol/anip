# ANIP Dogfooding Coverage Map and Next-Pressure Plan

This note maps **what ANIP surfaces are actually being exercised today** by Studio dogfooding and the ANIP-only stress agent, and then identifies what should be pressured next.

The goal is simple:

- avoid overestimating ANIP maturity just because some surfaces are working well
- identify which protocol areas are proven, partially proven, or still mostly theoretical
- create deliberate next-round pressure instead of hoping unused protocol areas somehow validate themselves

## Current Dogfooding Baseline

The current Studio dogfooding path is now materially real.

It includes:

- Studio as a real product harness
- ANIP-only agent interaction with Studio services
- bounded assistant capabilities
- deterministic evaluation
- root capability issuance (`v0.20`)
- delegated capability issuance (`v0.22`)
- continuation and recovery semantics (`v0.21`)
- Ollama-backed local model assistance

That is a strong base.

But it is not the whole protocol.

## Coverage Categories

This note uses three buckets:

- **Well Exercised**: real dogfooding has meaningfully pressured this surface
- **Partially Exercised**: touched, but not under strong or varied pressure
- **Weakly Exercised / Untouched**: either barely touched or not meaningfully used yet

## Coverage Map

### 1. Capability Declaration

Status:
- **Well Exercised**

Why:
- Studio assistant and workbench both publish real bounded capabilities
- the stress agent consumes those capabilities through manifests and invocation
- product behavior depends heavily on those declarations being coherent

Conclusion:
- ANIP’s bounded-capability model is holding up well in real use

### 2. Side-effect Typing

Status:
- **Partially Exercised**

Why:
- Studio capabilities do declare read/write behavior
- rollback windows are present on write-like capabilities
- but current dogfooding is not strongly testing side-effect differences in a way that creates pressure

What is missing:
- stronger use of irreversible vs rollbackable behavior
- stronger post-write verification expectations tied to side-effect class

### 3. Delegation Chain

Status:
- **Well Exercised**

Why:
- root issuance was pressured in `v0.20`
- delegated issuance is now pressured in `v0.22`
- real ANIP-only Studio stress runs now use parent -> child token flows
- dogfooding exposed a real delegated-auth bug and that bug was fixed

Conclusion:
- this is now one of the stronger validated ANIP surfaces

### 4. Permission Discovery

Status:
- **Weakly Exercised**

Why:
- current Studio stress runs do not meaningfully rely on `/anip/permissions`
- the agent mostly operates by already knowing which capability it wants and asking for the right token

What is missing:
- a consumer that uses permission discovery to decide what it can do next
- blocked/restricted/denied flows driven by permission discovery rather than hand-coded expectation

This is one of the clearest under-tested core surfaces.

### 5. Failure Semantics

Status:
- **Partially Exercised**

Why:
- we exercised enough failure semantics to uncover real issues during `v0.20` and `v0.22`
- the evaluator produces structured failure-adjacent guidance
- recovery targets are now exercised

What is missing:
- broader blocked-action classes
- more diverse failure families
- stronger comparison of how agents behave when failures drive the next step

### 6. Cost & Resource Signaling

Status:
- **Weakly Exercised**

Why:
- Studio does not currently pressure ANIP cost semantics very hard
- there is little real use of:
  - declared financial ranges
  - budget-bound delegation
  - cost-aware refusal or planning

This is a major under-tested contextual primitive.

### 7. Capability Graph

Status:
- **Weakly Exercised**

Why:
- current Studio dogfooding does not really use capability graph planning
- the stress agent already knows its high-level flow

What is missing:
- consumer behavior that reads graph data to determine the next move
- proof that graph semantics reduce planning burden in a real client

### 8. State & Session Semantics

Status:
- **Weakly Exercised**

Why:
- Studio capabilities used in the current loop are mostly stateless/unary in practice
- the current stress path does not really test stateful or session-carrying capabilities

This is still mostly unproven in real product dogfooding.

### 9. Observability Contract

Status:
- **Weakly Exercised**

Why:
- current dogfooding does not meaningfully use observability declarations or hooks
- logging/metrics/tracing integration points are not part of the current pressure loop

This surface exists, but it is not really being validated by current Studio use.

### 10. Discovery Document

Status:
- **Partially Exercised**

Why:
- we have inspected discovery in other work
- but the current Studio stress agent mostly relies on manifest and direct capability knowledge

What is missing:
- a consumer path that starts from discovery and derives its behavior from it
- stronger reliance on discovery posture and endpoint metadata

### 11. Manifest

Status:
- **Well Exercised**

Why:
- the Studio stress loop reads manifests
- `v0.21` improvements required manifest-level semantic correctness
- the dogfooding loop depends on capability metadata being coherent

Conclusion:
- manifest-driven consumption is one of the strongest parts of ANIP so far

### 12. Token Endpoint

Status:
- **Well Exercised**

Why:
- root issuance pressure in `v0.20`
- delegated issuance pressure in `v0.22`
- real consumer-edge misuse and runtime-path bugs were found and fixed here

Conclusion:
- this endpoint is now meaningfully dogfooded

### 13. Invoke Endpoint

Status:
- **Well Exercised**

Why:
- the ANIP-only Studio loop depends on invoke
- both assistant and workbench flows run through invoke repeatedly
- continuation/recovery semantics are only meaningful because invoke is under real use

### 14. Permissions Endpoint

Status:
- **Weakly Exercised**

This is the endpoint-level restatement of the earlier protocol point:
- the service may support it well
- but the current Studio harness is not leaning on it

### 15. Audit Endpoint

Status:
- **Weakly Exercised**

Why:
- current Studio stress runs do not query audit as part of the main loop
- durable audit exists, but it is not yet a pressure-bearing part of the consumer path

This is a major gap because audit is one of ANIP’s core claims.

### 16. Checkpoints / Anchored Trust / Merkle Proofs

Status:
- **Untouched**

Why:
- current Studio dogfooding runs in signed mode, not anchored mode
- checkpoint endpoints, proofs, and sink publishing are not meaningfully exercised

This is one of the biggest currently unproven areas of ANIP.

### 17. Streaming Invocations

Status:
- **Untouched**

Why:
- Studio does not currently pressure ANIP streaming semantics
- the current agent loop is unary

This is still mostly theoretical in Studio dogfooding.

### 18. Discovery Posture / Security Hardening / Aggregation / Storage Redaction

Status:
- **Weakly Exercised**

Why:
- some of these exist in implementation
- but current Studio dogfooding does not explicitly pressure:
  - posture-aware client decisions
  - audit aggregation
  - storage-side redaction
  - failure disclosure variation by caller class

These are real ANIP surfaces, but not yet strongly validated by current use.

### 19. Horizontal Scaling

Status:
- **Untouched**

Why:
- Studio dogfooding so far is not multi-replica or lease-contention pressure
- leader election, distributed exclusivity, and storage-derived checkpoint behavior are not being stressed

### 20. Observability Hooks

Status:
- **Untouched**

Why:
- the current Studio loop is not validating real hook integrations
- they exist, but are not part of the dogfooding proof yet

## Overall Read

The current dogfooding has already validated some of the most important ANIP areas:

- bounded capabilities
- manifest-driven consumption
- root issuance
- delegated issuance
- invocation
- continuation/recovery semantics in real product evaluation loops

That is a strong result.

But it also means the next protocol-confidence gains will not come from repeating the same Studio loop forever.

They will come from deliberately pressuring the surfaces that are still barely touched.

## Next Pressure Order

The best next order is:

1. permission discovery
2. cost and budget-aware delegation
3. audit and posture-aware consumption
4. streaming and state/session semantics
5. anchored trust, checkpoints, proofs, and sink publication
6. horizontal scaling and observability hooks

That order is deliberate:

- first pressure the still-weak **core consumer surfaces**
- then pressure the still-weak **contextual consumer surfaces**
- then pressure the deeper **trust and deployment surfaces**

## Proposed Pressure Rounds

### Round 1: Permission Discovery and Budget Pressure

Goal:
- make the consumer rely on `/anip/permissions` instead of pre-knowing what it can do

Add scenarios that force:
- restricted capability visibility
- denied capability visibility
- blocked-action explanation from permission data
- budget-constrained delegation and redelegation

Success looks like:
- the agent discovers what is possible instead of assuming it
- the agent chooses next moves from permission output

### Round 2: Audit as a First-Class Consumer Surface

Goal:
- make audit query part of the real loop

Add scenarios that require:
- looking up prior invocation lineage
- confirming that a follow-up occurred
- reconstructing what happened after a delayed or failed path

Success looks like:
- the agent uses audit, not just invoke results, to reason about continuity

### Round 3: Streaming and Stateful Paths

Goal:
- pressure streaming and state/session semantics directly

Add a Studio-adjacent or separate service path with:
- streaming progress
- resumable or stateful interaction
- session continuity expectations

Success looks like:
- agents can consume ANIP streaming/state semantics without custom glue explosions

### Round 4: Anchored Trust and Proof Consumption

Goal:
- stop leaving the trust model untested

Add a run that uses:
- anchored trust
- checkpoint generation
- inclusion or consistency proof retrieval
- maybe sink publication where practical

Success looks like:
- ANIP trust claims are not just documented, but exercised

### Round 5: Horizontal Scaling and Hooks

Goal:
- pressure the production/deployment surfaces

Add runs that validate:
- multi-replica safety
- distributed exclusivity behavior
- leader-elected checkpointing behavior
- observability-hook integration points

Success looks like:
- ANIP’s production posture is better proven, not just its single-instance semantics

## Strongest Immediate Gap

If we only pick one next pressure target, it should be:

- **permission discovery plus budget-aware delegation**

Why:
- it is still a core surface
- it is under-tested
- it is consumer-facing
- it directly affects the “less glue at the edge” story

That is the highest-signal next gap to close.

## Final Read

The good news is that ANIP no longer looks broadly unproven.

The current situation is better:

- some core surfaces are now strongly validated
- some contextual and trust surfaces are still weakly validated
- the next work is not to “save the protocol”
- it is to make the coverage map more complete

That is exactly where ANIP should want to be.
