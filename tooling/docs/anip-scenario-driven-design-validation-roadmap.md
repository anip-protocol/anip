# ANIP Scenario-Driven Design Validation Roadmap

## Purpose

This document captures a possible next step for ANIP beyond protocol design,
package structure, and reference docs.

The core idea is simple:

> ANIP should not only describe how agent execution works. It should help teams determine whether their proposed design actually removes glue in real scenarios.

That means shifting from:

- protocol semantics only
- implementation guidance only
- architecture suggestion only

to something stronger:

- scenario-driven design validation

## Core Insight

The most important question is no longer:

> What architecture should I use?

It is:

> Given my requirements and my scenarios, will this system behave correctly without bespoke glue?

That is the adoption question teams actually care about.

They do not ultimately want:

- prettier diagrams
- more protocol fields
- generic component lists

They want to know:

- will this break in production
- what glue will I still have to write
- where will agent behavior still collapse into wrappers and workflows

That is why scenarios should become the truth layer.

## The Strategic Shift

The wrong center of gravity would be:

`requirements -> planner -> architecture -> done`

The stronger model is:

`requirements -> proposed structure -> scenarios -> gap detection`

Or even more simply:

`design -> scenarios -> reality check`

The planner still matters.
But it is secondary.

Its role is to help generate a plausible ANIP structure that can then be tested
against scenarios.

The scenarios are what prove whether the structure is actually good.

## What This System Should Become

The long-term system has four layers:

1. requirements model
2. structure proposal
3. scenario tests
4. glue-gap evaluation

Each layer has a different job.

### 1. Requirements model

Captures what the system needs to support.

Examples:

- transport requirements
- trust posture
- delegation and purpose needs
- audit needs
- lineage needs
- scale and HA constraints
- public vs internal surface
- approval expectations
- domain-specific action risk

### 2. Structure proposal

Maps those requirements to a proposed ANIP shape.

Examples:

- embedded single-process
- production single-service
- horizontally scaled
- control-plane / worker split
- multi-service estate

Plus:

- required runtime components
- optional capabilities
- likely anti-patterns

### 3. Scenario tests

Defines real situations the system must handle well.

Examples:

- over budget booking
- missing permission with grantable recovery
- irreversible side-effect decision
- child invocation with lineage continuity
- operator reconstructs action chain

### 4. Glue-gap evaluation

Determines whether the proposed design is sufficient.

This is the most valuable layer.

The output should answer:

- what works cleanly
- what fails
- what glue is still required
- which ANIP features are missing
- which parts still rely on bespoke logic

## Why Scenarios Matter More Than The Planner

The planner is useful because it helps teams move from requirements to a
proposed structure.

But the planner is not the killer feature.

The killer feature is the scenario layer, because it answers:

> Does this design actually remove glue, or are we still going to write wrappers?

That is what makes the system compelling.

Without scenarios, the output is:

- interesting
- helpful
- but still speculative

With scenarios, the output becomes:

- concrete
- falsifiable
- adoption-relevant

That is a major difference.

## The North Star

The system should be centered on this question:

> Given this scenario, does the design pass without bespoke glue?

That should be the core ANIP validation test.

Not:

- does the schema validate
- does the package compile
- does the transport adapter work

Those still matter.
But they are not the strategic differentiator.

The differentiator is:

> can the design handle realistic agent execution scenarios without forcing the team to rebuild safety, orchestration, or observability logic outside the interface?

## Three Glue Categories The Evaluator Should Target

The evaluator should explicitly look for gaps in three categories.

### 1. Safety glue

Examples:

- budget guards
- permission wrappers
- approval gates
- irreversible-action checks
- retry logic
- escalation logic

### 2. Orchestration glue

Examples:

- multi-step wrapper workflows
- custom sequencing logic
- policy-specific condition branches
- compensation branches

### 3. Observability glue

Examples:

- correlation IDs
- trace stitching
- custom lineage reconstruction
- bespoke dashboards
- audit joins across systems

The output should say not only whether the scenario passes, but what glue in
these categories would still be required.

## What A Good Output Looks Like

The strongest output is not:

> Recommended architecture: shape 2

The stronger output is:

> This design handles these scenarios cleanly, but still requires:
>
> - custom permission wrapper glue
> - custom retry logic
> - a bespoke correlation layer

That is what makes the system genuinely useful.

It turns ANIP from:

- a protocol
- a doc set
- an architecture idea

into:

- a design validation system

## Proposed v1 Scope

The first version should be small and disciplined.

Do not start with a full product.

Start with:

1. a minimal scenario format
2. a small set of canonical scenarios
3. an evaluator template
4. an optional structure proposal layer

That is enough to make the value obvious.

## Proposed v1 Architecture

### Input A: Requirements

Structured requirements about the system.

For example:

- transports: `http`
- trust: `signed`
- lineage: `task + parent invocation`
- scale: `single service`
- audit: `durable + searchable`
- approvals: `external to ANIP`

### Input B: Scenario

A structured description of a situation the agent/system must handle.

For example:

- action
- context
- expected behavior
- expected ANIP signals

### Intermediate: Proposed structure

The system proposes:

- deployment shape
- required components
- optional components
- likely weak spots

### Output: Evaluation

The system returns:

- pass / partial / fail
- missing ANIP surfaces
- glue still required
- suggested improvements

## Minimal Scenario Format

The v1 scenario format should stay deliberately simple.

Example:

```yaml
scenario:
  name: "book flight over budget"
  category: "safety"

  context:
    capability: "book_flight"
    side_effect: "irreversible"
    cost_estimate: 800
    caller_budget: 500
    permissions_state: "available"

  expected_behavior:
    - do_not_execute
    - explain_budget_conflict
    - preserve_task_identity
    - preserve_invocation_lineage_if_followup_exists

  expected_anip_support:
    - cost_visibility
    - structured_failure
    - task_id
    - audit_record
```

This is enough for a useful first pass.

## Recommended Starter Scenarios

The first scenario library should be small and high-signal.

### Safety

1. book flight over budget
2. attempt action with insufficient permission
3. evaluate irreversible action before execution

### Orchestration

4. choose retry vs escalate after blocked action
5. multi-step dependency where one step should not proceed blindly

### Observability

6. reconstruct a task through audit by `task_id`
7. follow a parent/child invocation chain

These seven scenarios would already be enough to show real value.

## Domain Choices For v1

The best first domains are the ones ANIP already has in concrete form.

Recommended:

- travel
- devops

Why:

- they already exist as showcase surfaces
- they cover clear safety and lineage needs
- they are understandable to new users

Finance can follow, but travel and devops are the strongest first pair.

## Role Of The Planner

The planner should be treated as a helper, not the star.

Its job is to answer:

> Given these requirements, what deployment shape and ANIP components are likely needed?

That output is useful because it gives the evaluator something concrete to test.

But the planner should always serve scenario validation.

The flow should be:

1. collect requirements
2. propose a structure
3. run scenarios against it
4. expose the remaining glue

That keeps the system honest.

## How This Fits The Current ANIP Direction

This roadmap fits the current ANIP direction very well because it builds on:

- workflow glue reduction
- safety / orchestration / observability framing
- implementation requirements and deployment shapes
- lineage and task identity evolution

It does **not** require ANIP to become:

- a workflow engine
- an architecture generator
- a full compliance platform

Instead, it makes ANIP better at answering:

> what kind of execution semantics does this system still lack?

That is exactly where ANIP is strongest.

## Concrete Implementation Thoughts

The likely implementation path is:

### Phase 1: Documents and prompts

- define the scenario schema
- define canonical scenarios
- define evaluation criteria
- define a planner prompt/template

This phase can be done mostly in docs and prompt form.

### Phase 2: Lightweight evaluator

- requirements in
- scenario in
- structured evaluation out

This could be:

- prompt-driven first
- maybe CLI-based later

### Phase 3: Structured tool

- form or YAML input
- proposed structure output
- scenario evaluation output
- glue-gap report

This is where it starts becoming an actual ANIP design assistant.

### Phase 4: Integration into demos/docs/site

- playground scenarios use the same structure
- website explains what passes and what still requires glue
- future Studio or web tooling can expose the evaluator

## Best First Artifact

The best next artifact is not a full tool.

It is:

> a scenario-driven validation spec for ANIP design evaluation

That gives the system a stable truth layer before any UI or CLI is built.

The likely first concrete files would be:

- scenario schema
- starter scenario pack
- evaluator criteria
- example requirement sets

## Strong Summary

ANIP should not stop at telling teams how to implement the protocol.

It should help them answer the deeper question:

> Will this design actually behave correctly without bespoke glue?

That is why the next strong evolution is:

- requirements
- deployment shape proposal
- scenario tests
- glue-gap evaluation

The planner helps.
The scenarios matter most.
The real value is in exposing where glue is still required.

That is how ANIP can move from:

- protocol
- implementation guidance
- demos

to:

- a system for validating whether agent execution designs are actually good.
