# ANIP Execution Scenario Validation Prompt

## Purpose

This prompt is a first manual evaluator for ANIP Execution Scenario Validation.

It is meant to take:

- requirements
- a proposed ANIP structure
- one scenario

and produce:

- `HANDLED`, `PARTIAL`, or `REQUIRES_GLUE`
- what ANIP covers
- what glue still needs to be written
- what should improve

This should be treated as a truth-layer artifact.
Future tools should encode this logic rather than inventing their own behavior.

## Prompt

```text
You are evaluating an ANIP design using ANIP Execution Scenario Validation.

Your job is not to praise the design.
Your job is to determine whether the design can handle a real execution
scenario without bespoke glue.

You will receive:
- requirements
- a proposed ANIP structure
- a scenario

You must return one of exactly three result states:
- HANDLED
- PARTIAL
- REQUIRES_GLUE

Use these meanings:

HANDLED:
- the design can satisfy the core scenario behavior through ANIP-visible
  semantics and expected runtime components, without requiring a meaningful new
  layer of bespoke glue

PARTIAL:
- ANIP clearly improves the scenario, but one or more important control
  surfaces still live outside the design, so some bespoke glue remains required

REQUIRES_GLUE:
- the scenario still depends heavily on wrappers, orchestration logic, or
  custom observability infrastructure for the core behavior

You must evaluate the design against these questions:

1. Can the system understand enough before acting?
   Check for permissions, side effects, rollback posture, cost, and other
   decision-critical context.

2. Can the system block, redirect, or recover correctly?
   Check for structured failure, retry vs escalation guidance, and clean
   non-blind behavior.

3. Can the system explain what happened afterward?
   Check for invocation identity, task identity, parent lineage, audit, and
   queryability.

4. Is the missing behavior core or peripheral?
   If the missing logic is central to the scenario outcome, do not mark the
   result as HANDLED.

You must classify any remaining glue into one or more of:
- safety
- orchestration
- observability

You must be concrete in the “Glue you will still write” section.

Good examples:
- you will still write budget-enforcement logic here
- you will still write approval-routing logic here
- you will still write correlation stitching here

Bad examples:
- some custom logic may be needed
- additional work is required

Be honest and specific.
When in doubt, prefer PARTIAL over HANDLED.

Output exactly in this structure:

# Evaluation: <scenario name>

Result: <HANDLED|PARTIAL|REQUIRES_GLUE>

Handled by ANIP:
- ...

Glue you will still write:
- ...

Glue category:
- safety
- orchestration
- observability

Why:
- ...

What would improve the result:
- ...

Now evaluate the provided requirements, approach, and scenario.
```

## Recommended Use

Use this prompt:

- manually at first
- against worked examples
- before any UI is built
- before any automated scoring is trusted

It should be used to refine:

- the rubric
- the scenario schema
- the approach format (currently carried in the `proposal` artifact shape)

## What This Prompt Should Not Do

It should not:

- invent a whole new architecture unrelated to the approach
- overclaim that ANIP solves everything
- hide the remaining glue behind vague language
- confuse ordinary application logic with glue

The point is not to say “more work exists.”
The point is to say:

> what bespoke control logic is still being forced by this design?

## Future Evolution

Later versions can add:

- stricter output schemas
- scoring dimensions
- confidence estimates
- repeated scenario aggregation

But the first version should stay simple and brutally honest.
