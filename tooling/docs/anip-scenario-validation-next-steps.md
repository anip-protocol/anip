# ANIP Scenario Validation: What Comes Next

## Purpose

This document turns the current ANIP Scenario-Driven Execution Design work into
a concrete next-step roadmap.

The goal is not to stay in theory.
The goal is to define what needs to happen next so this becomes:

- tangible
- testable
- demoable
- eventually toolable

## The Core Goal

The next major milestone should be:

> a first tangible system that can take requirements and scenarios, evaluate a proposed design, and output the glue that would still need to be written.

That is the first product-worthy outcome.

Not:

- more abstract positioning
- more architecture notes
- more protocol-only discussion

But:

- a usable validation flow

## What “Tangible” Means

The first tangible version does **not** need to be:

- a polished web app
- a full Studio redesign
- a production-grade planner

The first tangible version **does** need to be:

- something runnable
- something repeatable
- something that produces concrete outputs
- something people can react to

That means the first target should be:

- text-based
- schema-backed
- prompt-driven or rules-driven
- CLI-friendly

## The Right Near-Term Deliverable

The best first tangible deliverable is:

> a minimal Execution Scenario Validation runner

This runner should accept:

- `requirements.yaml`
- `proposal.yaml`
- one or more `scenario.yaml`

And it should output:

- `HANDLED`, `PARTIAL`, or `REQUIRES_GLUE`
- `Handled by ANIP`
- `Glue you will still write`
- `Glue category`
- `Why`
- `What would improve the result`

That is enough to make the whole direction real.

## Recommended Build Order

The next steps should be done in this order.

### Phase 1: Freeze the truth layer

This phase defines the stable concepts the future tool must use.

Deliverables:

1. naming
   - `Scenario-Driven Execution Design`
   - `Execution Scenario Validation`
   - `Glue Gap Analysis`
2. rubric
3. evaluator prompt
4. 3 worked examples
5. scenario categories:
   - safety
   - orchestration
   - observability

Status:

- mostly done already

### Phase 2: Define the structured artifacts

This phase turns the method into machine-usable inputs and outputs.

Deliverables:

1. `requirements.schema.json`
2. `proposal.schema.json`
3. `scenario.schema.json`
4. `evaluation.schema.json`
5. canonical example files:
   - `examples/travel-single/`
   - `examples/devops-single/`
   - `examples/travel-multiservice/`

Success criteria:

- all worked examples can be represented as structured files
- the schemas are strict enough to keep the evaluator consistent

### Phase 3: Build the first manual runner

This is the first truly tangible stage.

Deliverable:

- a small CLI or script that:
  - reads structured files
  - renders an evaluator prompt
  - runs the evaluation
  - emits markdown and/or YAML output

Suggested command shape:

```bash
anip-design validate \
  --requirements requirements.yaml \
  --proposal proposal.yaml \
  --scenario scenarios/book_flight_over_budget.yaml
```

Suggested outputs:

- `evaluation.md`
- `evaluation.yaml`

Success criteria:

- one command can produce a full Glue Gap Analysis
- the output is stable enough to use in demos

### Phase 4: Add the proposal helper

Only after validation is working should the structure proposer become real.

Deliverable:

- a rules-based proposal generator

Suggested command:

```bash
anip-design propose --requirements requirements.yaml
```

Output:

- `proposal.yaml`
- optional diagram output

Success criteria:

- requirements produce a useful starting proposal
- proposal can immediately be passed to validation

### Phase 5: Turn it into a real experience

This is where the system becomes more widely usable.

Deliverables:

- a lightweight web interface or Studio extension
- worked-example gallery
- scenario library browser
- Glue Gap Analysis output cards

Success criteria:

- users can explore scenarios without reading long docs
- the system feels interactive and compelling

## What Should Be Built First

If the goal is to make fast, real progress, the next concrete build should be:

### 1. Schemas

Build:

- `requirements.schema.json`
- `scenario.schema.json`
- `evaluation.schema.json`

Why:

- they define the contract for everything else

### 2. One end-to-end validator

Build:

- one script or CLI command

Why:

- this is the first thing people can actually use

### 3. One polished multi-service example

Use:

- `search_then_book_across_services_with_budget_constraint`

Why:

- this is the killer demo
- it shows the strongest ANIP value
- it makes the glue story real

That is the first tangible wedge.

## The First Real Product Slice

If we reduce all of this to the smallest believable product, it is:

> “Can your system handle this scenario without glue?”

That product slice should contain:

1. one multi-service scenario
2. one requirements file
3. one proposal file
4. one evaluation result
5. one clear “glue you will still write” section

This could exist first as:

- a CLI
- a markdown report
- a page on `anip.dev`

That would already be real.

## What Studio Might Become

Studio should not absorb this immediately.

But it is probably the right long-term home.

### Short term

Studio remains:

- discovery
- manifest
- invoke
- permissions
- audit

### Mid term

Studio adds:

- a design workspace
- requirements entry
- scenario library
- validation result view

### Long term

Studio becomes:

- ANIP design cockpit
- validation runner
- Glue Gap Analysis workspace
- system modeling surface

That is a major evolution, but it should happen only after the truth layer and
CLI-style runner are stable.

## Recommended Immediate Deliverables

These are the next concrete things to build.

### Deliverable 1

`requirements.schema.json`

### Deliverable 2

`scenario.schema.json`

### Deliverable 3

`evaluation.schema.json`

### Deliverable 4

`anip-design validate` prototype

Even if it is just:

- Python
- local
- prompt-driven

that is enough.

### Deliverable 5

One polished public-facing page:

- `Can your system handle this without glue?`

Use the multi-service travel example as the lead artifact.

## What This Gives You

If the next phase is executed well, ANIP will move from:

- protocol
- implementation guidance
- scenarios in docs

to:

- a repeatable validation method
- a tangible evaluator
- a compelling public demo

That is the point where people stop just reading and start trying it.

## Recommended 3-Step Plan

If this needs to be compressed into the shortest possible plan:

1. **Formalize the artifacts**
   - schemas for requirements, scenarios, and evaluations

2. **Build the first validator**
   - one command
   - one multi-service example
   - one Glue Gap Analysis output

3. **Turn it into the first public experience**
   - page or lightweight UI
   - later Studio integration

That is the cleanest path from idea to product.

## Final Summary

The next step is not more speculation.

It is:

- structured artifacts
- a first validator
- a multi-service killer example
- a simple but real user-facing flow

That is how this becomes tangible.
