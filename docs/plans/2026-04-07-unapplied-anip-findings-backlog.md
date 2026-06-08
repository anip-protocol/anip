# Unapplied ANIP Findings Backlog

Date: 2026-04-07

## Purpose

This note combines the ANIP findings that are still **not fully applied** after
the current Studio dogfooding rounds.

It intentionally excludes issues that were already fixed on the Python +
FastAPI + Studio path during Rounds 1-6.

The goal is to keep one backlog of what still remains, rather than scattering
unapplied findings across:

- individual dogfooding round notes
- runtime parity notes
- earlier Studio/ANIP opportunity notes

## Important Boundary

ANIP has progressed well.

The current situation is not:

- fundamental protocol failure

It is:

- strong Python-path proof
- incomplete parity across other runtimes
- a smaller set of consumer and authoring ergonomics that are still rough

## 1. Cross-Runtime Parity Is Still Not Done

This is the biggest unapplied item.

The following issues were found and fixed on the Python path, but have **not**
yet been verified or fixed across:

- TypeScript
- Go
- Java
- C#

### 1.1 Mounted service lifecycle integration

Still unapplied cross-runtime:

- mounted service start/stop behavior
- background task startup/shutdown
- checkpoint and timer cleanup during host shutdown

Why it matters:

- framework lifecycle bugs are runtime-specific
- Python proof is not parity proof

### 1.2 Checkpoint scheduling and retrieval behavior

Still unapplied cross-runtime:

- checkpoint cadence behavior
- latest-checkpoint retrieval semantics
- chronological slice correctness for proof generation

Why it matters:

- anchored trust is runtime behavior, not only protocol declaration

### 1.3 Consistency-proof serialization

Still unapplied cross-runtime:

- JSON-safe proof transport
- stable proof payload encoding
- signature-safe serialization behavior

Why it matters:

- proof payloads are easy to get wrong differently in each stack

### 1.4 Exclusive-lock holder identity

Still unapplied cross-runtime:

- same-process contention behavior in other runtimes
- per-invocation versus per-process holder identity

Why it matters:

- this is a horizontal-scaling/runtime concern, not a Python-only idea

### 1.5 Root issuance of explicit concurrency posture

Still unapplied cross-runtime:

- root token issuance for `concurrent_branches=exclusive`
- helper API support
- HTTP handler support

Why it matters:

- Round 5 only proved the Python path

## 2. Task Identity Reuse After Token Issuance Is Still Awkward

Observed in:

- Round 2
- Round 3

Current problem:

- the consumer does not naturally learn the token-purpose `task_id` after
  issuance
- audit verification therefore still leans on:
  - `client_reference_id`
  - `invocation_id`

Why this remains unapplied:

- no protocol or runtime improvement has been added yet to make task reuse
  cleaner

What still needs work:

- better consumer ergonomics around task identity after issuance
- possibly a clearer issuance response surface for task-bound tokens

## 3. Purpose-Binding Ergonomics Are Still Too Manual For Consumers

Observed in:

- Round 5

Current problem:

- permission availability does not imply purpose-safe token reuse
- a token can be scope-available but still invalid for the next call because
  its purpose is bound to another capability

Current status:

- fixed in the dogfood client
- not solved generically in ANIP ergonomics

Why this remains unapplied:

- the protocol/runtime still leaves the client doing local reasoning here

What still needs work:

- make purpose-binding easier to reason about explicitly for consumers
- reduce the amount of local “should I reuse this token?” inference

## 4. Capability Graph Still Depends Heavily On Service Authoring Quality

Observed in:

- Round 6

Current problem:

- graph planning only became useful after Studio was manually updated to publish
  meaningful `requires` and `composes_with` relationships

Why this remains unapplied:

- ANIP now has a live graph surface on the Python path
- but authoring good graph relationships is still relatively manual

What still needs work:

- better authoring guidance/helpers for publishing useful graph relationships
- parity across runtimes for graph exposure
- validation that graph declarations stay meaningful as services evolve

## 5. Continuation / Recovery Authoring Ergonomics Still Need Improvement

This is not a protocol gap in the same way it was before `v0.21`, but it is
still an unapplied refinement item.

Current problem:

- `cross_service_contract` and `recovery_target` work
- but authors still need help producing good structured continuation/recovery
  data consistently

Why this remains unapplied:

- semantics were strengthened
- authoring ergonomics/helpers were not yet built out

What still needs work:

- helpers/builders for continuation and recovery declarations
- easier service-author workflow for publishing high-quality semantics

## 6. Evaluator Explanation Quality Still Has Some Drift

Observed in earlier Studio dogfooding and follow-up notes.

Current problem:

- semantics improved faster than some explanation text
- some evaluator/explanation wording still lags behind actual protocol/runtime
  behavior

Why this remains unapplied:

- this is mostly explanation/copy quality, not protocol behavior

What still needs work:

- align explanation language with current semantics
- remove stale advisory-sounding language where behavior is now stronger

## 7. Broader Runtime / Consumer Surfaces Still Need Pressure Outside Studio

Studio has now exercised a lot, but it is still one product environment.

Why this remains unapplied:

- no broader consumer-adapter dogfooding exists yet
- parity and ergonomics outside Studio remain unproven

What still needs work:

- runtime parity review across all 5 runtimes
- future consumer adapter dogfooding
- additional non-Studio product environments where useful

## Priority Order

Recommended next order:

1. cross-runtime parity for the concrete Python-path fixes
2. task identity reuse after issuance
3. purpose-binding ergonomics for consumers
4. capability-graph authoring ergonomics
5. continuation/recovery authoring helpers
6. evaluator explanation cleanup

## Bottom Line

The unapplied backlog is now much smaller and clearer than before.

The major remaining work is:

- parity
- ergonomics
- authoring quality

not:

- rescue of the core ANIP model
