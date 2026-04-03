# ANIP Tooling Process And Flow

## Purpose

This tooling exists to answer one practical question:

> Given this design and this scenario, what glue is still required?

It does not assume ANIP is complete.

It evaluates the current state of a design or interface and reports:

- what is already handled
- what is only partially handled
- what still requires bespoke glue

User-facing terminology note:

- `Approach` is the preferred Studio/product name for the candidate system answer
- current schema/file compatibility still uses `proposal`, `proposal.yaml`, and `proposal.schema.json`

## Current Scope

The first implemented slice is:

- `ANIP Validation Mode`

Current entrypoint:

- [tooling/bin/anip_design_validate.py](/Users/samirski/Development/codex/ANIP/tooling/bin/anip_design_validate.py)

Compatibility wrapper:

- [scripts/anip_design_validate.py](/Users/samirski/Development/codex/ANIP/scripts/anip_design_validate.py)

## Core Flow

The current flow is:

1. define the system requirements
2. define the proposed structure
3. define the scenario
4. run validation
5. read the Glue Gap Analysis

This is the underlying method:

- `requirements -> approach -> scenario -> evaluation`

This is the **truth-layer flow**.

The longer-term user-facing flow should add one more optional step:

- `requirements -> approach -> scenario -> evaluation -> starter pack`

That last step exists for one reason:

> users should be able to leave Design Mode with something tangible, not just a
> good explanation.

The intended outcome is:

> start from a validated, ANIP-shaped foundation

For protocol evolution checkpoints, use:

- [VALIDATION_GATE.md](/Users/samirski/Development/codex/ANIP/tooling/VALIDATION_GATE.md)
- [VALIDATION_REPORT_TEMPLATE.md](/Users/samirski/Development/codex/ANIP/tooling/VALIDATION_REPORT_TEMPLATE.md)

## Required Inputs

The validator currently expects three YAML files:

1. `requirements.yaml`
2. `proposal.yaml` (current file name for the Approach artifact)
3. `scenario.yaml`

These are validated against the schemas in:

- [tooling/schemas/requirements.schema.json](/Users/samirski/Development/codex/ANIP/tooling/schemas/requirements.schema.json)
- [tooling/schemas/proposal.schema.json](/Users/samirski/Development/codex/ANIP/tooling/schemas/proposal.schema.json) (`Approach` artifact schema in current compatibility form)
- [tooling/schemas/scenario.schema.json](/Users/samirski/Development/codex/ANIP/tooling/schemas/scenario.schema.json)

The output is validated against:

- [tooling/schemas/evaluation.schema.json](/Users/samirski/Development/codex/ANIP/tooling/schemas/evaluation.schema.json)

## What Each Input Means

### `requirements.yaml`

This describes the system constraints and expectations.

Typical contents:

- transports
- trust posture
- permission posture
- audit and lineage requirements
- scale shape
- business constraints
- whether the design is single-service or multi-service

This file answers:

> What kind of system are we trying to support?

### `proposal.yaml` (`Approach` artifact)

This describes the candidate ANIP system approach for that system.

Typical contents:

- recommended deployment shape
- required components
- key surfaces present
- optional capabilities
- assumptions about authority, audit, lineage, and control

This file answers:

> What ANIP-based approach are we taking?

### `scenario.yaml`

This describes one concrete situation the system must handle.

Typical contents:

- name
- category
- narrative
- execution context
- expected behavior
- expected ANIP support

This file answers:

> What real thing must the system do correctly?

## Output

The validator produces a structured evaluation and a readable report.

The result state is one of:

- `HANDLED`
- `PARTIAL`
- `REQUIRES_GLUE`

The most important output is:

- `glue_you_will_still_write`

That is the core product value.

The evaluator also reports:

- `handled_by_anip`
- `glue_category`
- `why`
- `what_would_improve`

## Future Design Mode Output

Design Mode should eventually produce **two** outputs:

### 1. Approach Output

This is the design answer:

- recommended shape
- required components
- required ANIP surfaces
- likely glue gaps
- rationale

### 2. Starter Pack Output

This is the tangible follow-up:

- conformance-shaped starter artifacts
- scenario pack
- validator wiring
- placeholders for required ANIP surfaces

This should help answer the practical reaction:

> this looks right, now how do I start?

## What A Starter Pack Should Include

For a single-service design, a starter pack should usually contain:

- manifest skeleton
- invoke handler stub
- permission discovery stub
- structured failure stub
- audit interface stub
- lineage propagation placeholders
- scenario files
- validator configuration or wiring

For a multi-service design, a starter pack should usually contain:

- per-service folders
- per-service manifest skeletons
- cross-service handoff placeholders
- lineage propagation hooks
- per-service audit stubs
- shared scenario pack
- validator wiring for the whole design

## What A Starter Pack Should Not Try To Do

The starter pack should **not** try to generate:

- fake business logic
- fake workflow implementations
- fake policy engines
- “finished” production services

The right output is:

- the right shape
- the right interfaces
- the right required surfaces
- clear TODOs for the parts humans still need to design and implement

## Why This Matters

Without a tangible output, Design Mode can feel like:

- good theory
- good evaluation
- unclear next step

With a starter pack, the system can say:

- here is the design
- here is the Glue Gap Analysis
- here is the minimum honest starting point

That is how the tooling lowers the adoption threshold without pretending to
generate finished systems.

That is a much stronger product experience.

## Command

Current usage:

```bash
python3 tooling/bin/anip_design_validate.py \
  --requirements tooling/examples/travel-multiservice/requirements.yaml \
  --proposal tooling/examples/travel-multiservice/proposal.yaml \
  --scenario tooling/examples/travel-multiservice/scenario.yaml
```

Optional output files:

```bash
python3 tooling/bin/anip_design_validate.py \
  --requirements tooling/examples/travel-multiservice/requirements.yaml \
  --proposal tooling/examples/travel-multiservice/proposal.yaml \
  --scenario tooling/examples/travel-multiservice/scenario.yaml \
  --evaluation-out /tmp/evaluation.yaml \
  --markdown-out /tmp/evaluation.md
```

## Current Example Packs

The current example packs are:

- [tooling/examples/travel-single](/Users/samirski/Development/codex/ANIP/tooling/examples/travel-single)
- [tooling/examples/devops-single](/Users/samirski/Development/codex/ANIP/tooling/examples/devops-single)
- [tooling/examples/travel-multiservice](/Users/samirski/Development/codex/ANIP/tooling/examples/travel-multiservice)

These are the best starting points for learning the flow.

## When To Use It

Use this tooling when you want to:

- evaluate an ANIP design against a real scenario
- compare scenario outcomes across example designs
- see whether a scenario is already handled or still requires glue
- make future protocol work evidence-driven

Do not treat it as:

- a code generator
- a workflow engine
- a replacement for reading the ANIP spec

## What Is Required For Good Results

The tool only helps if the inputs are honest and concrete.

You need:

- realistic requirements
- a defensible approach
- a concrete scenario

Bad inputs produce vague output.

Good inputs produce a credible Glue Gap Analysis.

## Current Limitations

The current validator is still small and rules-based.

That means:

- it does not yet inspect live services directly
- it does not yet support Legacy Validation Mode
- it does not yet generate approaches automatically
- it does not yet cover every protocol nuance

That is acceptable for the current phase.

The goal right now is:

- stable artifact contracts
- repeatable evaluation flow
- useful scenario-driven output

## Planned Modes

The intended product progression is:

1. `ANIP Validation Mode`
2. `Legacy Validation Mode`
3. `Design Mode`

### `ANIP Validation Mode`

Input:

- ANIP-aligned design artifacts or eventually live ANIP services
- scenarios

Output:

- scenario result
- Glue Gap Analysis

### `Legacy Validation Mode`

Input:

- REST / GraphQL / MCP surfaces
- the same scenarios

Output:

- Glue Gap Analysis
- missing control surfaces
- comparison against ANIP handling

### `Design Mode`

Input:

- requirements
- scenarios

Output:

- proposal
- likely glue reduction
- likely weak spots
- optional starter pack

The key rule is:

- validation remains the truth layer
- scaffolding is a derived convenience layer

## Practical Usage Pattern

The recommended workflow is:

1. start from an existing example pack
2. copy it to a new folder
3. edit `requirements.yaml`
4. edit `proposal.yaml`
5. edit `scenario.yaml`
6. run the validator
7. read the markdown output first
8. use the structured YAML output for comparison or automation later

The longer-term Design Mode workflow should become:

1. start from a scenario or template
2. confirm requirements
3. generate or refine an approach
4. run validation
5. review Glue Gap Analysis
6. optionally generate a starter pack

That keeps “tangible output” attached to validation instead of replacing it.

## The Right Interpretation Of Results

If the result is:

### `HANDLED`

The core scenario behavior is already covered by ANIP-visible semantics and the
proposed runtime structure.

### `PARTIAL`

The design is meaningfully better than a weak interface, but some glue is still
required.

This is often the most useful result right now.

### `REQUIRES_GLUE`

The design still leaves too much of the scenario outside the interface or
outside the current ANIP control surfaces.

## Design Principle

This tooling is an accelerator, not a prerequisite.

ANIP must remain understandable and implementable without the tool.

The tool should help answer:

> what glue is still required?

It should not become the thing that makes ANIP intelligible.

## Near-Term Next Steps

The concrete post-Phase-4 work order now lives in:

- [NEXT_STEPS_PLAN.md](/Users/samirski/Development/codex/ANIP/tooling/NEXT_STEPS_PLAN.md)

The first priority in that plan is:

1. harden the evaluator
2. expand glue categories
3. formalize scenario suites
4. standardize reports
5. lock the tooling object model
