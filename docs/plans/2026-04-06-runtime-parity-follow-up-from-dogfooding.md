# Runtime Parity Follow-Up From Dogfooding

Date: 2026-04-06

## Why This Note Exists

Recent Studio dogfooding rounds have surfaced real issues and produced real
fixes on the Python runtime and FastAPI integration path.

That is good progress, but it is not the same thing as cross-runtime parity.

The protocol direction is being validated, and the Python path is being
hardened under real pressure. The same issues may still exist in:

- TypeScript
- Go
- Java
- C#

This note exists so those follow-up obligations are tracked explicitly instead
of being lost in the success of the Python dogfood loop.

## Proven So Far

The following is strongly proven on the Python + FastAPI + Studio path:

- root capability-token issuance ergonomics
- delegated capability-token issuance
- continuation and recovery semantics
- permission discovery with:
  - `available`
  - `restricted`
  - `denied`
- audit and posture-aware consumption
- streaming and session semantics
- checkpoints and proof consumption
- exclusive-lock contention
- runtime observability consumption

## Important Boundary

The items below are **not** protocol failures.

They are primarily:

- runtime implementation bugs
- framework integration bugs
- consumer ergonomics gaps

And many of them are only fixed on the Python path so far.

## Follow-Up Issues That Need Cross-Runtime Review

### 1. Mounted service lifecycle integration

Observed on:

- Studio Python app integration

Issue:

- mounted ANIP services needed explicit start/stop handling inside the host app

Why parity matters:

- every framework binding can get lifecycle wiring wrong in slightly different
  ways

Cross-runtime follow-up:

- verify mounted service lifecycle expectations for all framework integrations
- confirm background tasks, checkpoints, timers, and shutdown flushing behave
  correctly

### 2. Checkpoint scheduling and retrieval behavior

Observed on:

- Python runtime/storage path

Issue:

- checkpoint cadence, ordering, and retrieval behavior needed fixes for real
  dogfood use

Why parity matters:

- checkpoint scheduling and retrieval are runtime behaviors, not just protocol
  declarations

Cross-runtime follow-up:

- verify checkpoint ordering semantics
- verify “latest checkpoint” retrieval logic
- verify proof generation against chronological slices

### 3. Consistency-proof serialization

Observed on:

- Python HTTP/runtime path

Issue:

- consistency proof output needed normalization so it was safe and stable over
  JSON transport

Why parity matters:

- proof transport issues often vary by runtime serializer and framework defaults

Cross-runtime follow-up:

- verify proof payload shape across all runtimes
- verify JSON-safe and signature-safe transport behavior

### 4. Exclusive-lock holder identity

Observed on:

- Python runtime path

Issue:

- exclusive lease ownership was keyed too coarsely (`hostname:pid`)
- same-process concurrent requests could re-enter the lock

Fix on Python:

- holder identity is now per invocation

Why parity matters:

- same-process concurrency exists in every runtime
- process-level holder identity is not sufficient if the runtime can multiplex
  requests inside one process

Cross-runtime follow-up:

- verify exclusive lock identity strategy in:
  - TypeScript
  - Go
  - Java
  - C#
- confirm same-process contention is rejected correctly

### 5. Root token issuance for exclusive concurrency

Observed on:

- Python `/anip/tokens` path

Issue:

- root issuance could not request `concurrent_branches=exclusive`

Fix on Python:

- token issuance now accepts `concurrent_branches`

Why parity matters:

- horizontal-scaling and contention pressure must be reachable through the real
  token issuance path on every runtime

Cross-runtime follow-up:

- verify root issuance can request concurrency posture explicitly
- verify helper APIs and HTTP handlers both support it

### 6. Permission availability vs purpose-safe reuse

Observed on:

- ANIP consumer path during Round 5

Issue:

- a token can be scope-available for a capability but still be invalid to reuse
  because its purpose is bound to a different capability

Fix in dogfood client:

- the client now avoids reusing a parent token when purpose binding does not
  match the target capability

Why parity matters:

- this is a broader ANIP consumer ergonomics issue, not just a Python bug

Cross-runtime follow-up:

- review consumer helpers and examples in all language ecosystems
- decide whether additional runtime/client ergonomics are needed so consumers do
  not have to infer this locally

### 7. Task identity reuse after token issuance

Observed on:

- Round 2 and Round 3 dogfooding

Issue:

- the consumer does not naturally learn the token-purpose task id after issuance
- audit verification therefore leaned on:
  - `client_reference_id`
  - `invocation_id`

Why parity matters:

- this is not Python-only
- it affects every consumer and runtime surface that expects clean audit/task
  correlation

Cross-runtime follow-up:

- track as a protocol/consumer ergonomics candidate across all runtimes, not
  only the Python path

## What Needs To Happen Next

For each item above:

1. inspect the corresponding runtime implementation
2. determine whether the issue exists there
3. fix it if it does
4. add regression coverage in that runtime’s tests
5. avoid calling parity complete until all runtimes have been reviewed

## Bottom Line

Dogfooding is doing its job:

- it is validating ANIP direction
- it is hardening the Python path
- and it is revealing exactly where runtime parity still needs explicit work

The mistake would be to treat Python fixes as automatic cross-runtime proof.
This note exists to prevent that.
