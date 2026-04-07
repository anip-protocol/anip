# Dogfood Round 3 Findings: Streaming and Session Semantics

Date: 2026-04-06
Branch: `feat/dogfood-round3-streaming-session`

## Goal
Exercise ANIP streaming and session semantics inside the same Studio dogfood flow that already pressures:
- permission discovery
- delegated issuance
- audit
- posture-aware consumption

## What Was Added
- Dogfood-only assistant capabilities for Round 3:
  - `start_design_review_session`
  - `stream_design_review`
- Continuation-style session declarations on the assistant manifest
- Streaming invocation over ANIP SSE
- Streaming audit verification through persisted `stream_summary`

## Live Dogfooding Result
A live ANIP-only Studio stress run completed successfully with Round 3 enabled.

The agent now:
1. starts a bounded design review session
2. continues that session through a streaming assistant capability
3. consumes SSE events over `/anip/invoke/{capability}`
4. verifies that audit persisted the streaming summary

## What Worked
- `response_modes = streaming` worked in the real Studio dogfood flow
- `session.type = continuation` was published and consumed as a real signal
- streaming audit entries persisted `stream_summary`
- the agent could verify the streaming invocation using:
  - `client_reference_id`
  - `invocation_id`

## Main Pressure Point Exposed
Round 3 surfaced a real consumer ergonomics gap around task identity:

- `task_id` reuse after token issuance is still awkward
- the consumer does not know the token-purpose task id after issuance
- so the cleanest live verification path still relied on:
  - `client_reference_id`
  - `invocation_id`

This is not a Round 3 failure. Streaming and session semantics worked. But it is a strong signal that task identity reuse remains harder than it should be for real consumers.

## Conclusion
Round 3 is a success.

For the exercised Studio path:
- streaming works over real ANIP invoke
- continuation-style session semantics are usable
- audit can verify streaming behavior

The biggest follow-on opportunity from this round is:
- make token-purpose task identity easier for consumers to reuse after token issuance
