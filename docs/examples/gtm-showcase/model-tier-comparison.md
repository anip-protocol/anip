# GTM Showcase Model-Tier Comparison

This document records the current Phase 1 model-flexibility result for the GTM
showcase.

It is based on the saved regression runs under:

- [regression-runs/gpt-5.4-mini](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/regression-runs/gpt-5.4-mini)
- [regression-runs/gpt-5-nano](/Users/samirski/Development/ANIP/docs/examples/gtm-showcase/regression-runs/gpt-5-nano)

## Why This Matters

The goal is not just to show that one stronger model can make the demo work.

The goal is to show that the ANIP-shaped stack:

- stays effective with a stronger small model
- stays safe when model quality drops
- degrades in capability, not in control

That is a much stronger proof than “the agent answered a few questions.”

## Current Results

### `gpt-5.4-mini`

- regression result: `20 / 20`
- status: full current Phase 1 support

What passed:

- happy path reads
- clarification
- denied paths
- breakout resistance
- approval/write-preparation paths
- warehouse-backed data checks for:
  - risk summary
  - pipeline summary
  - stalled opportunity review
  - follow-up preview

### `gpt-5-nano`

- regression result: `17 / 20`
- status: partial current Phase 1 support

Important runtime note:

- `gpt-5-nano` rejected `temperature=0.1`
- the runtime had to be rerun with `temperature=1`

What passed:

- happy path reads: `6 / 6`
- clarification: `3 / 3`
- denied paths: `5 / 5`
- breakout resistance: `3 / 3`

What failed:

- approval/write-preparation paths: `0 / 3`

Failure pattern:

- the model selected the correct capability
- the model did not leak data
- the model did not bypass approval
- the model did not choose an out-of-scope capability
- the model invented unsupported `ranking_basis` values such as:
  - `highest_risk`
  - `at_risk`
- the generated ANIP service correctly denied those requests because Phase 1
  only supports:
  - `ranking_basis=risk_score`

## Interpretation

The current result is:

- `gpt-5.4-mini` proves the full Phase 1 GTM loop is solid
- `gpt-5-nano` proves the architecture stays safe even when model quality drops

The most important line is:

> As the model got smaller, the system degraded in capability, not in safety.

That is exactly what a governed system should do.

## What This Says About The Architecture

The result supports the intended ANIP architecture:

- thin prompting
- thin runtime
- minimal orchestration
- governed service as the enforcement point

The smaller model drifted on write-preparation planning, but the system still:

- denied unsupported parameterization
- prevented unsafe execution
- preserved the business boundary

That is a strength, not a weakness.

## Current Operating Guidance

Based on the current results:

- use `gpt-5.4-mini` for the full Phase 1 GTM loop
- use `gpt-5-nano` only for:
  - bounded reads
  - clarification
  - denied-path handling
  - breakout-resistant paths

Do not currently rely on `gpt-5-nano` for approval/write-preparation paths
unless one of these is added:

- stronger deterministic normalization for follow-up intents
- a tighter constrained planner output for write-preparation cases
- model-tier routing that uses a stronger model for approval/write-prep

## Next Technical Options

There are three reasonable next steps:

1. Keep the current result as-is and treat it as the intended model-tier split.
2. Strengthen normalization specifically for follow-up/write-preparation paths
   and rerun `gpt-5-nano`.
3. Add explicit model-tier routing in the showcase:
   - smaller model for read-heavy bounded paths
   - stronger model for approval/write-prep paths

Option 1 is already a credible story.
Options 2 and 3 would improve the operational story further.
