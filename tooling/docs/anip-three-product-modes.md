# ANIP Product Modes: Design, ANIP Validation, and Legacy Validation

## Purpose

This note formalizes the likely product progression for the ANIP
scenario-validation system.

The key idea is:

> ANIP should not stop at being a protocol and a set of SDKs. It should become a way to design systems, validate ANIP systems, and expose the glue current systems still require.

This is where ANIP starts moving beyond:

- protocol semantics
- implementation guidance
- demos

and into:

- design method
- validation system
- comparison engine

That is a much bigger and more useful category.

## Why This Matters

Right now, teams keep inventing a huge number of workarounds to make agents
appear smarter:

- permission wrappers
- approval gates
- retry logic
- escalation flows
- budget guards
- side-effect safety checks
- correlation IDs
- trace stitching
- audit reconstruction glue

All of this exists because the interfaces agents act through are still too
weak.

That means the most compelling ANIP product is not just:

- a protocol browser
- a better manifest viewer
- a nicer invoke console

It is a system that can answer:

> What glue is this design still forcing me to write?

That is the real AHA moment.

## The Three Product Modes

These should be treated as the three core modes of the future system.

### 1. Design Mode

This mode answers:

> Given my requirements and scenarios, what should this system look like?

This is for:

- greenfield systems
- ANIP adoption planning
- architecture exploration
- platform design discussions

#### Inputs

- requirements
- initial scenarios

#### Outputs

- proposed ANIP structure
- recommended deployment shape
- required components
- optional capabilities
- likely weak spots
- expected glue reduction

#### Why it matters

This mode helps teams move from:

- abstract ANIP interest

to:

- a plausible system design

It is the planning layer.

But it is not the strongest mode on its own.

### 2. ANIP Validation Mode

This mode answers:

> Given the ANIP service or services I built, how good is the design actually?

This is the first truly practical mode because it deals with reality rather
than intention.

#### Inputs

- existing ANIP service or set of services
- scenarios

#### Outputs

- `HANDLED`, `PARTIAL`, or `REQUIRES_GLUE`
- handled-by-ANIP summary
- Glue Gap Analysis
- missing control surfaces
- what would improve the result

#### Why it matters

This mode is where ANIP becomes falsifiable.

The system can no longer hide behind:

- “good architecture”
- “clean semantics”
- “interesting design”

It has to show:

- whether the built system actually handles the scenario well
- and what glue still remains

That is a major shift.

### 3. Legacy Validation Mode

This mode answers:

> Given my current REST, GraphQL, MCP, or tool-calling stack, what glue is it still forcing me to write?

This is likely the strongest eye-opener.

#### Inputs

- legacy service or interface surface
  - REST
  - GraphQL
  - MCP
  - tool schemas
- scenarios

#### Outputs

- `HANDLED`, `PARTIAL`, or `REQUIRES_GLUE`
- Glue Gap Analysis
- missing control surfaces
- what the legacy design still pushes into wrappers, workflows, or tracing
- optionally, comparison against an equivalent ANIP shape

#### Why it matters

This mode is where the ANIP story becomes painfully concrete.

It does not just say:

- ANIP is better

It says:

- here is the glue your current interface is forcing you to write today

That is far more persuasive.

## The Comparison View

The third mode should not feel like propaganda.

It should remain honest.

That means the comparison surface should be:

- a `Comparison View`

not the name of the mode itself.

The modes are:

- `Design Mode`
- `ANIP Validation Mode`
- `Legacy Validation Mode`

And then the product can offer:

- `Comparison View`

to show:

- same scenario
- same goal
- ANIP output
- legacy output
- different glue surfaces

That is the right separation.

## Why Legacy Validation Is So Powerful

Legacy Validation Mode is likely the strongest AHA moment because it turns the
ANIP claim into something tangible.

Without it, ANIP can still sound like:

- another protocol
- better semantics
- nicer architecture

With it, the story becomes:

> Here is what your current system is costing you in wrappers, retries, escalation logic, and trace stitching.

That is a completely different level of persuasion.

It also makes the evaluation much more memorable.

Example:

### ANIP Validation Mode

Result:

- `PARTIAL`

Glue you will still write:

- budget-enforcement logic
- approval integration

### Legacy Validation Mode

Result:

- `REQUIRES_GLUE`

Glue you will still write:

- permission probing
- side-effect guard logic
- retry decisions
- escalation routing
- cross-service correlation IDs
- trace stitching
- audit reconstruction

That contrast is what makes the ANIP value obvious.

## Why These Modes Should Be Built In This Order

The right build order is:

### First: ANIP Validation Mode

Why:

- it is the most grounded
- the schemas and examples already point here
- it produces the first real truth layer

This should be built first.

### Second: Design Mode

Why:

- once validation exists, approach generation can be judged honestly
- otherwise design proposals are too easy to make vague or flattering

Design Mode should grow on top of the validation system.

### Third: Legacy Validation Mode

Why:

- it reuses the same rubric
- it reuses the same scenario model
- it adds the strongest comparison story

Legacy Validation Mode should come after the ANIP evaluator is stable.

That keeps the comparison credible.

## What Each Mode Evaluates

This is the critical part.

All three modes should evaluate against the same core question:

> Does this design handle the scenario without bespoke glue?

But each mode applies that question differently.

### Design Mode evaluates:

- whether the proposed structure is plausible
- whether the shape matches the requirements
- what glue is likely still required

### ANIP Validation Mode evaluates:

- whether the implemented ANIP surfaces are sufficient
- whether the scenario passes in reality
- what glue still remains in the current ANIP system

### Legacy Validation Mode evaluates:

- what control surfaces the legacy system lacks
- what glue the team is compensating with today
- how much of that glue ANIP could potentially reduce

## The Strongest Product Framing

The cleanest product framing is:

### Design Mode

Helps teams design ANIP systems.

### ANIP Validation Mode

Tells teams how good their ANIP system actually is.

### Legacy Validation Mode

Shows teams why they needed glue in the first place.

That is a very strong stack.

It also creates a natural journey:

1. understand your current pain
2. design something better
3. validate the result

That is a full product loop.

## Why This Takes ANIP To A New Level

This is what changes ANIP from:

- protocol
- docs
- demos

into:

- system design method
- validation method
- migration and comparison tool

That is a much bigger category.

It also means ANIP is no longer only saying:

- “here is a better interface”

It is saying:

- “here is a way to prove where your current design still depends on glue”

That is the stronger position.

## What This Means For Studio

These three modes also suggest the likely long-term Studio evolution.

Studio does not need to host all of this immediately.

But over time it could become the natural UI for:

- Design Mode
- ANIP Validation Mode
- Legacy Validation Mode
- Comparison View
- Glue Gap Analysis

That is much bigger than a single-service inspector.

It is also a much more durable product direction.

## Final Summary

The future ANIP product should likely center on three modes:

- `Design Mode`
- `ANIP Validation Mode`
- `Legacy Validation Mode`

with:

- `Comparison View`

as the main explanatory output surface.

This matters because it turns ANIP into more than a protocol.

It becomes:

- a way to design better systems
- a way to validate ANIP systems honestly
- a way to expose the glue current systems are still forcing teams to write

That is a major step forward.
