# ANIP Tooling Next Steps Plan

## Why This Plan Exists

Phase 4 Slice 2 should mark a real transition point for ANIP.

Up to this point, the main effort went into building the protocol surface
aggressively enough that ANIP could cover the major execution-semantic layers:

- local control
- authority posture
- recovery posture
- same-service advisory composition
- cross-service continuity
- cross-service handoff clarity

After that point, the main question should no longer be:

> what else can the protocol add?

It should become:

> where do scenarios still expose glue, weak measurement, or awkward protocol
> semantics?

That means the next center of gravity is:

- scenario-driven execution design
- execution scenario validation
- Glue Gap Analysis

This plan defines the next work order for that shift.

## Core Rule

After Phase 4 Slice 2:

- protocol evolution should slow down
- tooling pressure should go up
- scenario evidence should become the main driver
- protocol changes should become narrower and harder to justify

That is the intended maturity shift.

## Immediate Priority

The first bottleneck is not the protocol.

It is the evaluator.

Right now the validator still scores some distributed and advisory-heavy
scenarios too generously. That weakens the value of:

- validation reports
- slice gates
- future legacy comparison
- agent-generated critique loops

So the first priority is to make the measurement layer stricter and more honest.

---

## Work Order

### 1. Harden The Evaluator

Goal:

- make evaluations more discriminating, especially for distributed and
  advisory-only cases

Do:

- tighten `HANDLED` so it requires stronger evidence that glue is truly removed
- make advisory-only hints less likely to auto-score as fully handled
- distinguish:
  - protocol-handled
  - protocol-assisted
  - still-wrapper-dependent
- add stronger scrutiny for:
  - cross-service handoff clarity
  - reconstruction quality
  - refresh-path discoverability
  - verification/follow-up discoverability
  - operator dependence on hidden topology knowledge

Expected outputs:

- revised evaluation rubric
- stricter evaluator prompt/instructions
- updated evaluator output language

### 2. Expand Glue Categories

Goal:

- make `Glue Gap Analysis` more precise and easier to compare over time

Do:

- standardize a stronger category set, including:
  - `safety`
  - `authority`
  - `recovery`
  - `cross_service`
  - `observability`
  - `orchestration`
- allow scenarios and evaluations to point to multiple pressure areas
- make the evaluator explain:
  - what category of glue remains
  - why ANIP did not remove it
  - whether the remaining gap is protocol, tooling, or implementation-side

Expected outputs:

- schema/rubric update
- better report quality
- more useful trend tracking across slices

### 3. Formalize Scenario Suites

Goal:

- turn scenario work into a stable public measurement system

Create stable suites:

- `core-baseline`
- `authority-suite`
- `recovery-suite`
- `multiservice-suite`
- `legacy-comparison-suite`

Each scenario should have:

- stable ID
- clear intent
- target pressure area
- expected result shape
- expected remaining glue categories

Expected outputs:

- versioned scenario-pack structure
- scenario README/index
- explicit baseline membership

### 4. Standardize The Report Format

Goal:

- make every evaluation easy to compare, publish, and review

Every run should produce:

- result state:
  - `HANDLED`
  - `PARTIAL`
  - `REQUIRES_GLUE`
- handled surfaces
- remaining glue
- glue category
- explanation of why
- what would improve the result
- optional complexity / intuitiveness note
- optional protocol/tooling follow-up

Expected outputs:

- final report template
- stable evaluation object contract
- cleaner reviewer workflow

### 5. Lock The Tooling Object Model

Goal:

- define the stable artifact and API layer for both humans and agents

Core objects:

- `Scenario`
- `RequirementsSet`
- `Proposal`
- `Evaluation`
- `Comparison`
- `Review`
- `StarterPack`

The rule:

- every important UI action should map cleanly to these objects and operations

Expected outputs:

- API object model note
- operation list for the future web tool
- automation-safe interfaces

### 6. Build The First Product Shell

Goal:

- make the tooling usable as a real web product, not just YAML + CLI

Build first:

- scenario browser
- guided requirements entry
- proposal viewer
- evaluation viewer
- comparison/report view

Deployment shape:

- web-first
- hostable on `anip.dev`
- self-hostable via Docker

Expected outputs:

- first UI shell
- basic API backend or local service layer
- documented run path

### 7. Add Agent Workflows

Goal:

- use agents as a discovery engine for both tooling gaps and ANIP gaps

Agents should be able to:

- generate scenarios
- draft requirements
- propose ANIP shapes
- critique proposals
- critique evaluations
- compare ANIP vs legacy outcomes
- suggest protocol/tooling improvements

Expected outputs:

- structured agent tasks
- agent review prompts
- review object or annotation flow

---

## Recommended Sequence

Use this exact order:

1. evaluator hardening
2. glue-category expansion
3. scenario-suite formalization
4. report/output standardization
5. tooling object model
6. web tool shell
7. agent workflows

This order matters because:

- if the evaluator is weak, everything downstream becomes less trustworthy
- if scenario suites are unstable, comparisons and reviews will drift
- if object contracts are loose, the UI and agent layers will become brittle

## What Not To Do Next

Do not immediately:

- add more protocol surface just because it is possible
- build a large UI before the evaluator is trustworthy
- make YAML the public UX
- let the scaffold/starter-pack generator outrun the validator
- let agents hide weak measurement under plausible prose

The next phase should optimize for:

- stronger truth
- stronger comparability
- stronger repeatability

Not:

- faster feature accumulation

## Success Criteria

This next tooling phase is successful if:

- the evaluator stops over-crediting advisory-only support
- multi-service and recovery scenarios produce more believable outputs
- scenario packs become stable enough to rerun across releases
- the report format becomes easy to compare and publish
- humans can use the system without authoring raw YAML
- agents can use the system without relying on hidden UI logic
- protocol changes become driven by repeated scenario evidence instead of open
  semantic expansion

## Immediate First Deliverable

The first concrete deliverable should be:

> a stricter evaluator revision for distributed and advisory scenarios

That is the highest-leverage next step because it improves:

- release gates
- scenario credibility
- Glue Gap Analysis quality
- later web UI usefulness
- later agent-review usefulness

If this piece stays weak, everything built on top of it will look more complete
than it really is.

## Short Version

The next phase should not start with more protocol work.

It should start with:

- better measurement
- better scenarios
- better reports
- then product surface
- then agent loops

That is how ANIP shifts from aggressive semantic expansion to evidence-driven
maturity.

---

## V3 Priority: Structured Proposal Surface Declarations

The V2 evaluator infers which advisory surfaces a proposal declares by
heuristically matching text in `required_components`, `key_runtime_requirements`,
and `rationale`. This is wording-sensitive — changing prose can change the score
without a real design change.

V3 should introduce structured surface declarations in the proposal schema so
evaluator judgments depend on machine-readable design surfaces, not text
inference. For example:

```yaml
proposal:
  declared_surfaces:
    refresh_via: true
    verify_via: true
    cross_service_handoff: true
    budget_enforcement: true
    recovery_class: true
```

This would let the evaluator check declared intent directly instead of scanning
prose. It is the single highest-leverage improvement for evaluator truthfulness
after V2.
