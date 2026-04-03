# ANIP Scenario Validation: Process And Tooling

## Purpose

This document answers a practical question:

> If ANIP is going to become a scenario-driven design validation system, what process and tooling are required to make that real?

The goal is not to jump straight into a large product.

The goal is to define:

- the process teams would follow
- the artifacts that process needs
- the tools that should exist
- the order in which those tools should be built

## The Core Outcome

The system should eventually be able to answer:

> Given these requirements and these scenarios, where would this design still require bespoke glue?

That is the real output.

Not:

- a pretty architecture diagram
- a generic “recommended stack”
- a protocol compliance report

But:

- what ANIP covers
- what it does not
- what glue the team will still write

## The Process

The right process has five stages.

### Stage 1: Capture requirements

The team describes what the system actually needs.

Examples:

- transports required
- trust posture
- scale expectations
- audit requirements
- lineage requirements
- approval expectations
- public vs internal deployment
- action risk level
- domain constraints

This stage should produce one structured artifact:

- `requirements.yaml`

### Stage 2: Propose a structure

The system maps requirements to:

- deployment shape
- required runtime capabilities
- optional capabilities
- anti-pattern warnings

This stage should produce:

- `proposal.yaml`
- optional diagram output

Important:
this stage is advisory, not authoritative.

### Stage 3: Select scenarios

The team chooses scenarios relevant to the system.

Scenarios should come from:

- a canonical ANIP scenario library
- domain-specific scenario packs
- team-authored custom scenarios

This stage should produce:

- one or more `scenario.yaml` files

### Stage 4: Evaluate

The evaluator checks whether the approach can satisfy the scenario without
extra glue.

This stage should answer:

- handled by ANIP
- partially handled
- still requires glue

And more importantly:

- where glue is still needed
- what kind of glue it is
- what ANIP/runtime capability is missing

This stage should produce:

- `evaluation.md`
- or `evaluation.json`

### Stage 5: Refine

The team updates:

- requirements
- structure
- capabilities
- scenarios

Then reruns evaluation until the major glue gaps are explicit and acceptable.

This is what makes the system practical rather than theoretical.

## The Minimum Artifact Set

To make this real, ANIP needs a small but disciplined artifact model.

### 1. Requirements schema

Purpose:

- describe the system being designed

Likely file:

- `requirements.schema.json`

Likely user form:

- `requirements.yaml`

### 2. Proposal schema

Purpose:

- describe the proposed ANIP structure

Likely file:

- `proposal.schema.json`

Likely output:

- `proposal.yaml`

### 3. Scenario schema

Purpose:

- describe a testable real-world situation

Likely file:

- `scenario.schema.json`

Likely input:

- `scenario.yaml`

### 4. Evaluation schema

Purpose:

- standardize the evaluator output

Likely file:

- `evaluation.schema.json`

Likely output:

- `evaluation.yaml`
- `evaluation.md`

### 5. Scenario libraries

Purpose:

- provide canonical cases teams can test against

Examples:

- `scenarios/travel/`
- `scenarios/devops/`
- `scenarios/saas/`

## The Tooling Stack

The system does not need one big tool on day one.

It needs a layered tooling stack.

### Tool 1: Requirements linter

Input:

- `requirements.yaml`

Output:

- validation errors
- missing fields
- contradictory requirements

Purpose:

- ensure the planner and evaluator receive structured, sane inputs

This is the simplest useful tool.

### Tool 2: Structure proposer

Input:

- `requirements.yaml`

Output:

- `proposal.yaml`

Purpose:

- map requirements to:
  - deployment shape
  - required components
  - optional components
  - anti-pattern warnings

This can be:

- rules-based first
- prompt-assisted second

### Tool 3: Scenario selector

Input:

- `requirements.yaml`
- optional domain hint

Output:

- recommended scenario set

Purpose:

- avoid making teams search manually for relevant scenarios

This can start very simply:

- just tags and filtering

### Tool 4: Scenario evaluator

Input:

- `requirements.yaml`
- `proposal.yaml`
- one or more `scenario.yaml`

Output:

- pass / partial / fail
- glue still required
- missing ANIP surfaces
- improvement suggestions

This is the most important tool in the stack.

This is the tool that makes the whole system worth caring about.

### Tool 5: Gap reporter

Input:

- evaluation outputs across scenarios

Output:

- grouped glue gaps
- grouped missing capabilities
- repeated failure patterns

Purpose:

- turn many scenario runs into a clear summary

This is what teams will actually use in planning.

### Tool 6: Diagram generator

Input:

- `proposal.yaml`

Output:

- Mermaid
- SVG
- markdown diagrams

Purpose:

- visualize the recommended structure

Useful, but secondary.

This should not be the first tool built.

## The Right Build Order

The order matters a lot.

The wrong approach would be:

- build a fancy planner UI first

The right approach is:

### Phase 1: Truth layer

Build:

- requirements schema
- scenario schema
- evaluation schema
- canonical scenarios
- evaluator rubric

Why:

- without this, everything else is guesswork

### Phase 2: Manual evaluator

Build:

- prompt template
- markdown evaluator output
- a small CLI wrapper if helpful

Why:

- proves the concept before overengineering

### Phase 3: Structure proposer

Build:

- rules-based proposal engine
- approach schema
- basic diagram generation

Why:

- now the planner has a stable evaluation target

### Phase 4: Integrated workflow

Build:

- one CLI command or lightweight web UI
- requirements in
- proposal out
- scenarios selected
- evaluations run
- gap report produced

Why:

- this is when the system becomes genuinely reusable

## The Evaluator Logic

The evaluator should not ask:

- is this elegant
- is this interesting
- is this compliant in the abstract

It should ask:

1. Can the system handle the scenario safely?
2. Can it do so without blind trial-and-error?
3. Can it explain failure or recovery correctly?
4. Can it preserve audit and lineage for the scenario?
5. What glue would still need to be written?

This should lead to explicit outputs like:

- `handled_by_anip`
- `partially_handled`
- `still_requires_glue`

And:

- `glue_you_will_still_write`

That should be a first-class output field, not an afterthought.

## The Glue Categories The System Must Report

The tooling should classify remaining glue into:

### Safety glue

- permission wrappers
- budget guards
- approval checks
- retries
- escalation logic

### Orchestration glue

- sequencing wrappers
- multi-step condition chains
- compensation logic
- policy-specific orchestration

### Observability glue

- correlation IDs
- trace stitching
- audit joins
- workflow reconstruction logic

If the system cannot say which glue category remains, it is not doing the most
important part of the job.

## Recommended Repo Structure

One possible future layout:

```text
design-validation/
  schemas/
    requirements.schema.json
    proposal.schema.json
    scenario.schema.json
    evaluation.schema.json

  scenarios/
    travel/
    devops/
    saas/

  prompts/
    propose-structure.md
    evaluate-scenario.md
    summarize-gaps.md

  examples/
    travel-basic/
    devops-controlled/

  cli/
    anip_design_validate.py
```

This keeps the system explicit and inspectable.

## The Human Process Around The Tools

The tools alone are not enough.

Teams should follow a consistent process:

1. write requirements
2. run proposer
3. choose scenario pack
4. run evaluator
5. review glue gaps
6. change design
7. rerun

That process is what turns the tooling into a real design method.

## The Strongest v1

The strongest realistic v1 is:

- `requirements.yaml`
- `proposal.yaml`
- `scenario.yaml`
- prompt-based evaluator
- markdown gap report

That is enough to validate the system direction.

Do **not** start with:

- big web product
- auto-generated code
- full-blown architecture generator

Those can come later if the scenario system proves real value.

## Good First Deliverables

If this roadmap becomes a real project, the first useful deliverables are:

1. requirements schema
2. scenario schema
3. evaluation rubric
4. 5 to 7 canonical scenarios
5. first evaluator prompt
6. first worked examples

That would already be enough to show something valuable.

## Worked Example Types To Build First

The first examples should be:

### Travel

- over-budget booking
- permission block
- task-level audit reconstruction

### DevOps

- high-risk action with insufficient authority
- escalation instead of blind retry
- parent/child invocation lineage

### Generic SaaS

- support agent acting on behalf of a user
- scoped authority mismatch
- post-action traceability

These examples will make the evaluator immediately understandable.

## What Success Looks Like

This system is working when a team can say:

- here are our requirements
- here is the proposed ANIP shape
- here are the scenarios we care about
- here is the glue we still need
- here is what ANIP already removes

At that point, ANIP is no longer just:

- a spec
- a set of SDKs
- a demo surface

It becomes:

- a way to reason about whether agent execution designs are actually good

## Final Summary

To make scenario-driven ANIP validation real, the project needs:

- a clear process
- structured artifacts
- a small layered tool stack
- a disciplined build order
- canonical scenarios
- glue-gap reporting as the core output

The planner matters.
The evaluator matters more.
The scenarios matter most.
