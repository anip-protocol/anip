# ANIP Execution Scenario Validation Rubric

## Purpose

This rubric defines how ANIP Execution Scenario Validation should judge a
proposed design.

It is meant to keep evaluation:

- consistent
- honest
- comparable across scenarios
- focused on glue reduction

The evaluator should not ask whether the design is elegant in the abstract.
It should ask whether the design can handle a real execution scenario without
forcing the team to rebuild bespoke glue.

## Core Output States

Every scenario evaluation should end in one of three states.

### 1. `HANDLED`

Use this when the proposed design can satisfy the scenario with ANIP-visible
semantics and expected surrounding runtime components, without requiring a
meaningful new layer of bespoke glue for the core behavior.

In practice, this means:

- the required execution context is visible before, during, or after action
- the expected decision or block can be reached cleanly
- audit and lineage are sufficient for the scenario
- remaining work is ordinary application implementation, not compensating glue

Use `HANDLED` only when the core scenario behavior is truly covered.

### 2. `PARTIAL`

Use this when ANIP meaningfully improves the scenario but does not fully remove
the need for custom logic around the core behavior.

In practice, this means:

- ANIP improves understanding, recovery, or traceability
- but one or more critical control surfaces still live outside ANIP
- the system would still require bespoke glue for correct behavior

This should probably be the most common result early on.

`PARTIAL` is not a weak result.
It is often the most honest and useful one.

### 3. `REQUIRES_GLUE`

Use this when the proposed design still depends heavily on custom wrappers or
external logic for the core scenario outcome.

In practice, this means:

- the agent must rely on blind trial-and-error
- the interface does not expose enough decision context
- recovery or escalation is mostly bespoke
- observability depends on custom stitching
- the proposal leaves a major control requirement outside the design

Use this result when the scenario claim would otherwise be misleading.

## Primary Output

The primary output is not the architecture recommendation.

The primary output is:

> what glue the team will still have to write

That means every evaluation must include a dedicated section:

- `Glue you will still write`

This should be explicit, not vague.

Good examples:

- you will still write budget-enforcement logic here
- you will still write approval-routing logic here
- you will still write retry decision logic here
- you will still write correlation stitching here

Bad examples:

- some custom logic may be needed
- additional integration work is required

The system should be concrete enough to be uncomfortable.

## Evaluation Questions

Every scenario evaluation should answer these questions.

### 1. Can the system understand enough before acting?

Check whether the design exposes:

- permissions
- side effects
- rollback posture
- cost
- prerequisites
- risk-relevant constraints

If not, safety glue is likely required.

### 2. Can the system block or redirect the action correctly?

Check whether the design can:

- stop unsafe execution
- return structured failure
- suggest retry, replan, or escalation

If not, orchestration glue is likely required.

### 3. Can the system explain what happened afterward?

Check whether the design preserves:

- invocation identity
- task identity
- parent linkage
- durable audit
- queryability

If not, observability glue is likely required.

### 4. Is the missing behavior core or peripheral?

This is the most important judgment.

If the missing logic is central to the scenario outcome, the result should lean
toward `PARTIAL` or `REQUIRES_GLUE`.

If the missing work is incidental and does not undermine the core ANIP claim,
the result can remain `HANDLED`.

## Glue Categories

Every evaluation should classify remaining glue into one or more categories.

### Safety glue

Examples:

- permission wrappers
- budget checks
- approval gates
- side-effect guards
- retry logic
- escalation handling

### Orchestration glue

Examples:

- multi-step sequencing wrappers
- dependency ordering logic
- compensation branches
- policy-specific workflow branches

### Observability glue

Examples:

- correlation ID systems
- lineage stitching
- audit reconstruction logic
- custom dashboards just to understand the task chain

## Recommended Evaluation Output Format

Every evaluation should contain these sections in order:

1. `Result`
2. `Handled by ANIP`
3. `Glue you will still write`
4. `Glue category`
5. `Why`
6. `What would improve the result`

That keeps the output focused and comparable.

## Example Output Skeleton

```md
# Evaluation: scenario_name

Result: PARTIAL

Handled by ANIP:
- cost visibility
- side-effect posture
- structured failure
- audit recording

Glue you will still write:
- you will still write budget-enforcement logic here
- you will still write approval-routing logic here

Glue category:
- safety
- orchestration

Why:
- the design improves the decision surface but does not yet make the key
  control constraint enforceable through an ANIP-visible control surface

What would improve the result:
- move the constraint into delegation, permission evaluation, or another
  protocol-visible enforcement surface
```

## Result Heuristics

Use these heuristics when choosing between states.

### Choose `HANDLED` when

- the scenario’s core decision can be made from ANIP-visible context
- the system can respond correctly without a new wrapper layer
- audit and lineage are sufficient for the scenario

### Choose `PARTIAL` when

- ANIP clearly helps
- but one important control surface still lives outside the system
- or the design still requires some bespoke logic for the central scenario

### Choose `REQUIRES_GLUE` when

- the scenario would mostly still be handled by custom wrappers
- the system still depends on trial-and-error or ad hoc policy code
- the ANIP layer is too weak to make the scenario meaningfully cleaner

## Hard Rule

When in doubt, prefer:

- `PARTIAL`

over:

- `HANDLED`

The system becomes valuable by being trustworthy, not by inflating pass rates.

## What This Rubric Protects

This rubric protects ANIP from two failure modes:

### 1. Empty optimism

Everything looks “handled” because the evaluator is too generous.

That destroys credibility.

### 2. Empty pessimism

Everything looks “requires glue” because the evaluator ignores real ANIP value.

That destroys usefulness.

The rubric exists to keep the evaluator sharp and fair.

## Strong Summary

Execution Scenario Validation should not only say whether a design looks good.

It should say:

- what ANIP already covers
- what glue still remains
- whether the remaining gap is peripheral or central

That is how the system becomes a real design truth layer instead of just a new
style of documentation.
