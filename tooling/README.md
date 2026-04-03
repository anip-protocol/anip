# ANIP Tooling

This folder is the first real home for the ANIP scenario-design and
scenario-validation tooling.

It is intentionally separate from the broader strategy notes under `docs/`.

The goal is to let the tool evolve as a product surface while keeping the
protocol, positioning, and roadmap writing in the main documentation area.

## What Lives Here

User-facing terminology note:

- `Approach` is now the preferred Studio/PM-facing name for the candidate system answer
- low-level artifact/schema compatibility still uses `proposal` / `proposal.yaml` / `proposal.schema.json` for now

- `bin/`
  - runnable tooling entrypoints
- `schemas/`
  - truth-layer contracts for:
    - requirements
    - approach (`proposal` in current schema/file compatibility)
    - scenario
    - evaluation
- `examples/`
  - worked example packs
- `prompts/`
  - evaluator and analysis prompts
- `docs/`
  - tool-adjacent reference notes that directly support the runnable artifacts

## Current State

The first runnable piece is:

- `bin/anip_design_validate.py`

It supports the first version of `Execution Scenario Validation`:

- input:
  - `requirements.yaml`
  - `proposal.yaml` (the current file name for the Approach artifact)
  - `scenario.yaml`
- output:
  - structured evaluation
  - markdown Glue Gap Analysis

## Current Product Direction

The tooling is expected to grow in three modes:

1. `ANIP Validation Mode`
2. `Legacy Validation Mode`
3. `Design Mode`

Design Mode should eventually have two outputs:

1. approach output
2. optional starter-pack output

That starter pack should be:

- conformance-shaped
- scaffold-oriented
- correctness-oriented

It should generate:

- the right structure
- the right interfaces
- the right required ANIP surfaces
- scenario and validation wiring

It should **not** pretend to generate finished business logic.

The practical promise is simple:

> start from a validated, ANIP-shaped foundation

The intended build order is:

1. `ANIP Validation Mode`
2. `Legacy Validation Mode`
3. `Design Mode`

## Important Constraint

This tooling is an accelerator, not a prerequisite for ANIP itself.

ANIP must remain understandable and implementable without the tool.

The tool should help answer:

> what glue is still required for this scenario?

It should not become the thing that makes ANIP intelligible.

The same rule applies to future scaffold generation:

> generated starter artifacts should give teams a correct starting shape, not
> pretend to solve the hard parts of system behavior automatically.

## Current Sources Of Truth

The core artifact contracts in this folder are:

- `schemas/requirements.schema.json`
- `schemas/proposal.schema.json` (`Approach` artifact schema in current compatibility form)
- `schemas/scenario.schema.json`
- `schemas/evaluation.schema.json`

The current example packs are:

- `examples/travel-single`
- `examples/devops-single`
- `examples/travel-multiservice`

## Slice Review

Use these docs when validating a completed ANIP slice before implementing the
next one:

- [VALIDATION_GATE.md](/Users/samirski/Development/codex/ANIP/tooling/VALIDATION_GATE.md)
- [VALIDATION_REPORT_TEMPLATE.md](/Users/samirski/Development/codex/ANIP/tooling/VALIDATION_REPORT_TEMPLATE.md)

Current example report:

- [2026-03-31-v014-validation-report.md](/Users/samirski/Development/codex/ANIP/tooling/reports/2026-03-31-v014-validation-report.md)

## Post-Phase-4 Direction

For the concrete tooling-first work order after the aggressive ANIP protocol
build-out, use:

- [NEXT_STEPS_PLAN.md](/Users/samirski/Development/codex/ANIP/tooling/NEXT_STEPS_PLAN.md)

## Compatibility

The old script path still exists:

- `scripts/anip_design_validate.py`

It now acts as a thin wrapper that forwards to:

- `tooling/bin/anip_design_validate.py`
