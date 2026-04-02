# ANIP Tooling Schema Evolution: Likely V2 Direction

## Purpose

The current schemas are good enough for the first tooling slice.

They are not the final shape.

This note describes:

- what is good enough in v1
- what will likely need to change in v2
- what should not be changed yet

The goal is to evolve the schemas under real usage pressure rather than
pre-optimizing them too early.

## Current Assessment

The current schemas are strong enough for:

- the truth layer
- the first validator
- worked example packs
- early tool evolution

They are especially good at:

- keeping artifacts explicit
- making the validator testable
- preserving a stable contract between evaluation inputs and outputs

The main limitation is that they are still mostly shaped for:

- engineers
- early internal iteration
- rules-based validation

They are not yet shaped for:

- business-friendly authoring
- richer multi-service modeling
- large-scale agent-generated artifacts
- long-term comparison/review workflows

## What Is Good Enough In V1

### Requirements

The current requirements schema is good enough for:

- design inputs
- runtime needs
- audit/lineage posture
- single-service and multi-service distinction

It is still useful as the internal source of truth.

### Proposal

The current proposal schema is good enough for:

- recommended shape
- required components
- rationale
- first-order glue reduction claims

### Scenario

The current scenario schema is good enough for:

- defining concrete execution cases
- allowing domain flexibility
- iterating quickly

### Evaluation

The current evaluation schema is already quite strong because it centers on:

- result state
- handled by ANIP
- remaining glue
- what would improve the result

That is the correct center of gravity.

## Likely V2 Changes

## 1. Add `cross_service` As A First-Class Category

This is the clearest likely change.

Right now categories are:

- `safety`
- `orchestration`
- `observability`

That is already useful, but it is incomplete.

The current work strongly suggests that:

- cross-service behavior
- cross-service handoff
- cross-service coherence

deserve first-class treatment.

That means likely v2 additions:

### Scenario category

Add:

- `cross_service`

### Evaluation glue category

Add:

- `cross_service`

This will better match the actual direction of the ANIP story.

## 2. Strengthen Multi-Service Modeling In `proposal`

The current proposal schema is intentionally light.

That is fine for v1.

But it will likely become too weak once the UI and agent workflows need to
reason more deeply about system structure.

Likely v2 additions:

- explicit per-service boundaries
- service roles with stronger typing
- inter-service handoff assumptions
- shared governance expectations
- lineage expectations across service boundaries
- control surfaces per service

Not necessarily all at once.

But the proposal layer will probably need more structure than:

- `recommended_shape`
- `required_components`
- `service_shapes`

## 3. Introduce A Shared Vocabulary For Recurring Scenario Fields

The current `scenario.context` is intentionally loose.

That is the right choice for v1.

It lets examples evolve quickly.

But over time the system will probably benefit from a small shared vocabulary
for common scenario concepts such as:

- `risk`
- `side_effect`
- `budget_limit`
- `selected_cost`
- `permissions_state`
- `service_boundary`
- `approval_expectation`

The important constraint is:

- do not overconstrain domain-specific context

So the likely v2 direction is:

- keep flexible context
- but define optional standard fields that tools and agents can rely on

## 4. Add Review And Comparison Artifacts

The current system has:

- requirements
- proposal
- scenario
- evaluation

That is enough to bootstrap the validator.

But it is probably not enough for the broader product.

Likely v2 artifact additions:

### `comparison`

To represent:

- ANIP vs legacy
- proposal A vs proposal B
- version-to-version changes

### `review`

To represent:

- human review comments
- agent review comments
- consistency checks
- critique of an evaluation or proposal

This will matter once the system becomes collaborative and automatable.

## 5. Add Identity And Provenance Fields

As the tool becomes more interactive and more agent-driven, the artifacts will
likely need more explicit metadata such as:

- artifact id
- revision id
- created_by
- created_at
- derived_from
- source_mode

This matters for:

- traceability
- comparison
- agent-generated drafts
- review workflows

These are probably not necessary in the raw v1 schemas yet, but they are very
likely in v2.

## 6. Separate Internal Truth Shape From UI Shape

This is one of the biggest future shifts.

The current schemas are good as:

- artifact contracts

They are not necessarily the right direct shape for:

- form input
- wizard state
- business-friendly editing

That suggests a likely v2 architecture:

- canonical artifact schema stays fairly explicit
- UI input models become a separate layer
- UI compiles down to canonical artifacts

This is important because:

- the artifact shape should remain stable and automatable
- the UI shape should remain user-friendly

They should not be forced to be the same thing forever.

## What Should Not Change Yet

Some things should remain as they are for now.

### Do not over-structure `scenario.context`

It is still too early.

The examples and agent workflows need more time to show what recurring fields
deserve formalization.

### Do not turn `proposal` into a giant architecture schema yet

The current proposal structure is simple and useful.

Adding too much complexity too early would make the tool harder to evolve.

### Do not optimize for business-user editing directly in the canonical schemas

That should happen in the UI layer, not by polluting the truth-layer contracts.

## Recommended V2 Sequence

The likely safest sequence is:

1. add `cross_service` category support
2. introduce `comparison` and `review` artifact concepts
3. add optional common scenario vocabulary
4. strengthen multi-service proposal structure
5. add provenance/version metadata
6. separate canonical artifact models from UI-specific input models

## Practical Guidance

For now, keep using the current schemas.

Do not rewrite them preemptively.

Instead:

1. let the UI flow use them
2. let agents start generating and reviewing artifacts
3. watch for repeated friction
4. evolve the schemas only where the friction is consistent

That is the right way to keep the tool both:

- stable enough to build on
- flexible enough to evolve

## Bottom Line

The current schemas are in good enough shape for v1.

They are not the final product schema model.

The most likely first v2 changes are:

- `cross_service` support
- `comparison` and `review` artifacts
- stronger multi-service proposal structure
- provenance and revision metadata

That is a good place to be.
