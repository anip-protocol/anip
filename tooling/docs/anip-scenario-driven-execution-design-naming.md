# ANIP Naming: Scenario-Driven Execution Design

## Purpose

This note stabilizes the naming for the new ANIP direction around
scenario-based design, validation, and glue-gap detection.

The goal is to use the same language consistently across:

- docs
- website copy
- demos
- future tooling
- talks and posts

## Primary Terms

### 1. Scenario-Driven Execution Design

This is the name of the overall method.

It refers to the full loop:

- requirements
- proposed structure
- scenarios
- evaluation
- refinement

It should be used when describing the broader ANIP approach.

**Definition:**

> Scenario-Driven Execution Design is a way to design agent systems around real execution scenarios instead of abstract architecture alone.

**Longer definition:**

> ANIP uses Scenario-Driven Execution Design to move from requirements to a proposed execution structure, then validate that structure against realistic scenarios to expose where bespoke glue still remains.

### 2. Execution Scenario Validation

This is the name of the validation layer.

It refers to the act of testing a proposed design against one or more
execution scenarios.

It should be used for:

- evaluator logic
- tooling
- validation passes
- scenario runs

**Definition:**

> Execution Scenario Validation tests whether a proposed design can handle a real execution scenario without bespoke glue.

**Shorter definition:**

> Execution Scenario Validation shows whether the design passes, partially passes, or still requires glue.

### 3. Glue Gap Analysis

This is the name of the output/report layer.

It refers to the result of evaluation.

It should be used for:

- reports
- summaries
- evaluation output sections
- CLI or tool result naming

**Definition:**

> Glue Gap Analysis identifies what custom safety, orchestration, or observability logic a system would still require after ANIP is applied.

## Recommended Usage Hierarchy

These terms should be used in a clean stack:

- **Method:** `Scenario-Driven Execution Design`
- **Validation process:** `Execution Scenario Validation`
- **Output:** `Glue Gap Analysis`

That gives ANIP a consistent language model:

- the method
- the evaluation
- the result

## Best One-Sentence Explanation

> ANIP introduces Scenario-Driven Execution Design: a way to propose and validate agent-system designs against real execution scenarios, then expose the glue gaps that remain.

## Website-Ready Version

> ANIP uses Scenario-Driven Execution Design to test whether a system can handle real execution scenarios without bespoke glue.

## Tooling-Ready Version

> Run Execution Scenario Validation on a proposed design to generate a Glue Gap Analysis.

## Strong Short Variants

- Design the system around scenarios, not assumptions.
- Validate execution, not just architecture.
- See where glue still remains.
- ANIP should not only propose designs. It should show where they still fail.

## Recommended Use By Surface

### Docs

Use:

- `Scenario-Driven Execution Design`

This is the right term for roadmap notes, methodology docs, and implementation
thinking.

### Tooling

Use:

- `Execution Scenario Validation`

This is the right term for CLI commands, evaluators, validation runs, and
future Studio workflow names.

### Output / Reports

Use:

- `Glue Gap Analysis`

This is the right term for evaluation reports and summaries.

### Homepage / Messaging

Use:

- `Scenario-Driven Execution Design`

And then quickly explain:

- “does this system still need glue?”

That keeps the homepage language sharper and more grounded.

## Example Stack In Practice

Example phrasing:

> ANIP introduces Scenario-Driven Execution Design. Start from requirements, propose a structure, then run Execution Scenario Validation to see whether the design still requires glue. The result is a Glue Gap Analysis that shows what custom logic would still need to be written.

That is the cleanest combined explanation.

## Why These Names Work

These names are strong because they are:

- specific enough to mean something
- broad enough to grow with the system
- connected directly to ANIP’s execution focus
- distinct from generic architecture or UX language

They also separate:

- the method
- the validation action
- the evaluation output

That separation will matter more as the system grows.

## Final Recommendation

Use these names consistently:

- `Scenario-Driven Execution Design`
- `Execution Scenario Validation`
- `Glue Gap Analysis`

Do not keep renaming them.
Consistency is part of how this becomes a real category rather than a one-off
idea.
