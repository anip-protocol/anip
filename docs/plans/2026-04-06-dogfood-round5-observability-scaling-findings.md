# Dogfood Round 5: Observability + Scaling Findings

Date: 2026-04-06

## Goal

Pressure ANIP observability and horizontal-scaling-style surfaces inside the
same Studio dogfood app by exercising:

- runtime observability hooks
- checkpoint visibility during live execution
- exclusive lock contention
- ANIP-only consumer behavior over discovery, tokens, permissions, invoke, and audit

## What Was Exercised

- `hold_exclusive_probe`
- `read_runtime_observability`
- live `/anip/tokens`
- live `/anip/invoke/{capability}`
- live `/anip/checkpoints`
- live audit verification after the same stress flow

## Result

Round 5 succeeded.

The ANIP-only Studio stress agent completed successfully against a live
`STUDIO_DOGFOOD_PROFILE=round5` backend.

The run verified:

- exclusive contention was enforced
- runtime hook counts were visible to the consumer
- recent checkpoints were visible to the consumer
- the broader Studio stress loop still completed with `HANDLED` outcomes

## What Round 5 Proved

ANIP observability and scaling-oriented surfaces are useful enough to be
consumed by an agent in a real product loop, not only by test harnesses or
operator tooling.

The important behavioral proof is:

- the client can trigger a real exclusive contention path
- the client can observe the resulting runtime state through ANIP-exposed
  observability data
- the client can verify checkpoints without leaving the ANIP-facing surface

That means these protocol/runtime features are now under real dogfooding
pressure.

## Bugs Round 5 Exposed

### 1. Exclusive lock holder identity was too coarse

The Python runtime keyed exclusive lease ownership to:

- `hostname:pid`

That allowed concurrent requests in the same process to re-enter the lock,
because they appeared to be the same holder.

Fix applied:

- exclusive lock acquisition, renewal, and release now use a per-invocation
  holder identity

Why it matters:

- same-process concurrency is common in real framework integrations
- process-level holder identity is not sufficient for ANIP exclusive-lock
  semantics

### 2. Root token issuance could not request exclusive concurrency

The Python `/anip/tokens` path accepted budget data but not
`concurrent_branches`, which meant the Round 5 probe token could not activate
the exclusive-lock path through the real token route.

Fix applied:

- Python token issuance now accepts `concurrent_branches`
- the dogfood client uses that field for the Round 5 exclusive probe token

Why it matters:

- the lock path must be reachable through real ANIP token issuance
- otherwise horizontal-scaling pressure is only theoretical

### 3. Scope-available did not imply purpose-safe reuse

The consumer initially reused the broad parent token for
`read_runtime_observability` because permissions showed it as available.

That failed at invoke time with:

- `purpose_mismatch`

because the token purpose was still bound to `create_workspace`.

Fix applied:

- the dogfood client now treats parent-purpose mismatch as a reason to issue a
  capability-bound child token instead of reusing the parent token

Why it matters:

- permission availability and purpose binding are different concerns
- consumers need a clean way to avoid invalid parent-token reuse

## ANIP Follow-On Candidates Exposed By Round 5

These are not blockers for the successful run, but they are good follow-on
improvement candidates:

1. Make purpose-binding ergonomics easier for consumers
   - today the consumer had to carry local knowledge of the parent token's
     bound capability
   - ANIP could make this easier to reason about explicitly

2. Verify cross-runtime parity for exclusive-lock holder identity
   - the bug was fixed on the Python runtime path
   - parity across other runtimes/framework integrations still needs explicit
     validation

3. Verify cross-runtime parity for `concurrent_branches` issuance handling
   - Round 5 proved the Python path
   - not all runtimes are proven by this dogfood round

## Bottom Line

Round 5 is a success.

It proves that:

- ANIP observability/scaling surfaces are usable in a real dogfood loop
- the tested Python runtime path is now materially stronger
- dogfooding continues to uncover concrete runtime/adoption issues rather than
  invalidating the protocol direction
