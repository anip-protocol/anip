# Dogfood Round 6: Capability Graph Findings

Date: 2026-04-06

## Goal

Pressure the ANIP capability-graph surface inside the same Studio dogfood app
so the agent reads graph data to determine what to do next instead of relying
only on hardcoded flow knowledge.

## What Was Exercised

- `GET /anip/graph/{capability}`
- discovery endpoint advertisement of the graph route
- graph-driven planning in the Studio stress agent
- graph relationships declared on:
  - `create_project`
  - `accept_first_design`
  - `draft_fix_from_change`
  - `generate_business_brief`
  - `generate_engineering_contract`
  - `start_design_review_session`

## Result

Round 6 succeeded.

The ANIP-only Studio stress agent completed successfully against a live
`STUDIO_DOGFOOD_PROFILE=round6` backend after graph support was added to the
Python path and the agent switched several transitions to graph-driven planning.

The live run confirmed:

- discovery advertised a real graph endpoint
- the agent used graph relationships to pick next capabilities
- the broader Studio loop still completed successfully with `HANDLED` outcomes

## What Round 6 Proved

Capability graph is now more than a declared profile field on the tested
Python/Studio path.

The graph surface is useful enough for a real client to:

- choose `accept_first_design` after `create_project`
- choose `stream_design_review` after `start_design_review_session`
- choose `evaluate_service_design` after `draft_fix_from_change`
- verify that shareable outputs depend on prior evaluation

That is the core proof Round 6 needed:

- graph semantics are reducing planning burden in the client
- not just existing as documentation-shaped metadata

## Adoption Gaps Round 6 Exposed

### 1. The Python graph endpoint was not actually mounted

The client already had a graph helper, but the Python FastAPI path was not
serving:

- `GET /anip/graph/{capability}`

Fix applied:

- graph route mounted on the Python FastAPI binding
- discovery now advertises the graph endpoint explicitly
- ANIP service now exposes graph data from capability declarations

Why it matters:

- a profile claim without a live route is not real dogfooding coverage

### 2. Round 6 initially did not inherit checkpoint cadence

The first live Round 6 run failed because the `round6` profile did not inherit
the faster checkpoint cadence used in earlier anchored-dogfood rounds.

That caused:

- no checkpoints being available during verification time

Fix applied:

- `round6` now inherits the fast checkpoint cadence

Why it matters:

- compound dogfood profiles need to inherit the prior operational posture they
  still depend on

### 3. Graph planning still depends on Studio publishing useful relationships

Round 6 worked because Studio was updated to publish meaningful graph
relationships. Without those relationships, the route would exist but would not
actually reduce planning burden.

Why it matters:

- capability graph usefulness depends on service authors declaring real
  relationships
- coverage requires both:
  - protocol/runtime support
  - product/service adoption

## Bottom Line

Round 6 is a success.

It proves that:

- the tested Python/Studio path now has a real graph surface
- the graph is usable by an agent in a live ANIP-only flow
- graph planning can remove some hardcoded next-step knowledge at the client

This was the last major round in the current Studio dogfooding expansion plan
for the Python path.
