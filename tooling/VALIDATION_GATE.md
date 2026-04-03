# Post-Slice Validation Gate

## Purpose

This gate exists to answer one question before the next ANIP slice is
implemented:

> Did the last slice remove meaningful glue without making ANIP too heavy?

This is the concrete checkpoint between:

- `slice implemented`
- and
- `next slice approved for implementation`

It turns the review doctrine into a repeatable process.

## When To Run It

Run this gate:

- after a slice lands in the protocol and runtimes
- after examples and tooling are updated to match
- before the next slice moves from proposal into implementation

Current intended use:

- after `anip/0.15`
- before Phase 3 Slice 1 implementation

Next intended use:

- after `anip/0.16`
- before Phase 3 Slice 2 implementation

## What This Gate Evaluates

Every slice must pass two reviews:

1. `Glue Reduction Review`
2. `Complexity And Intuitiveness Review`

A slice is not successful if it passes only the first.

## Inputs

The gate uses:

- the current ANIP spec and runtime behavior
- the worked scenario packs
- the validator output
- a short human review of clarity and complexity

Recommended baseline scenarios:

1. `travel-single`
2. `travel-multiservice`
3. `devops-single`

Recommended extension after `anip/0.15`:

- add at least one authority-heavy scenario pack
- add at least one blocked-action / escalation-heavy scenario pack

Recommended extension after `anip/0.16`:

- add recovery-heavy and sequencing-heavy scenario packs
- explicitly measure:
  - refresh-path discoverability
  - wait-path clarity
  - revalidation-path clarity
  - verification / follow-up discoverability

Recommended extension after `anip/0.18`:

- add explicit multi-service handoff scenarios
- explicitly measure:
  - cross-service quote / offer handoff clarity
  - cross-service refresh-source discoverability
  - cross-service verification-path clarity
  - fan-out reconstruction quality
  - delayed follow-up lineage clarity

Recommended comparison input:

- one manual legacy comparison for the same travel scenario

## Recommended Scenario Set

### 1. Travel Single-Service

Use:

- [requirements.yaml](/Users/samirski/Development/codex/ANIP/tooling/examples/travel-single/requirements.yaml)
- [proposal.yaml](/Users/samirski/Development/codex/ANIP/tooling/examples/travel-single/proposal.yaml)
- [scenario.yaml](/Users/samirski/Development/codex/ANIP/tooling/examples/travel-single/scenario.yaml)

Why:

- tests pre-execution control
- tests budget and binding enforcement
- should show whether safety glue actually shrank

### 2. Travel Multi-Service

Use:

- [requirements.yaml](/Users/samirski/Development/codex/ANIP/tooling/examples/travel-multiservice/requirements.yaml)
- [proposal.yaml](/Users/samirski/Development/codex/ANIP/tooling/examples/travel-multiservice/proposal.yaml)
- [scenario.yaml](/Users/samirski/Development/codex/ANIP/tooling/examples/travel-multiservice/scenario.yaml)

Why:

- tests whether the slice still helps in the real pain zone
- checks cross-service reduction of safety and handoff glue
- exposes whether complexity increased without enough distributed value

### 3. DevOps Single-Service

Use:

- [requirements.yaml](/Users/samirski/Development/codex/ANIP/tooling/examples/devops-single/requirements.yaml)
- [proposal.yaml](/Users/samirski/Development/codex/ANIP/tooling/examples/devops-single/proposal.yaml)
- [scenario.yaml](/Users/samirski/Development/codex/ANIP/tooling/examples/devops-single/scenario.yaml)

Why:

- verifies that the simplification did not weaken already-healthy refusal flows
- ensures the slice did not trade simplicity for regressions

## Gate Steps

### Step 1. Run The Validator On The Baseline Scenarios

Run:

```bash
python3 tooling/bin/anip_design_validate.py \
  --requirements tooling/examples/travel-single/requirements.yaml \
  --proposal tooling/examples/travel-single/proposal.yaml \
  --scenario tooling/examples/travel-single/scenario.yaml
```

```bash
python3 tooling/bin/anip_design_validate.py \
  --requirements tooling/examples/travel-multiservice/requirements.yaml \
  --proposal tooling/examples/travel-multiservice/proposal.yaml \
  --scenario tooling/examples/travel-multiservice/scenario.yaml
```

```bash
python3 tooling/bin/anip_design_validate.py \
  --requirements tooling/examples/devops-single/requirements.yaml \
  --proposal tooling/examples/devops-single/proposal.yaml \
  --scenario tooling/examples/devops-single/scenario.yaml
```

Capture:

- result state
- handled-by-ANIP surfaces
- remaining glue
- what improved

### Step 2. Compare Against The Pre-Slice Baseline

For each scenario, ask:

- did the result state improve?
- did the Glue Gap Analysis shrink?
- did the remaining glue get narrower and more honest?

This is not only about `PARTIAL -> HANDLED`.

It is also about whether:

- the remaining glue is smaller
- the interface is more enforceable
- the system requires fewer wrappers

### Step 3. Perform The Complexity And Intuitiveness Review

Check:

- can the new slice still be explained simply from the spec?
- does the model now have one canonical place for each concept?
- are the main invoke-time controls obvious?
- can a strong engineer implement the behavior without Studio or the validator?
- did the slice remove overlap, or create new overlap?

For the `0.14` gate specifically, ask:

- is binding clearly canonical under `requires_binding`?
- is `control_requirements` now clearly limited to non-binding controls?
- does the simplification reduce conceptual duplication in the spec and UI?

For the `0.15` gate specifically, ask:

- are `restricted` and `denied` still easy to explain from the spec?
- is `reason_type` bounded and useful rather than taxonomy sprawl?
- does `resolution_hint` reduce blocked-action glue without making the model much heavier?
- is `resolution.action` still tight enough that Phase 3 can build on it safely?

### Step 4. Add One Manual Legacy Comparison

Before Slice 2, add one manual comparison for the travel scenario:

- ANIP version of the flow
- legacy REST / GraphQL / MCP shape of the same flow

Ask:

- what glue still remains in ANIP?
- what extra glue appears in the legacy interface?
- did the ANIP slice improve the gap in a tangible way?

This comparison does not need a full automated mode yet.

It just needs an honest comparison note.

### Step 5. Write The Gate Result

Use the template in:

- [VALIDATION_REPORT_TEMPLATE.md](/Users/samirski/Development/codex/ANIP/tooling/VALIDATION_REPORT_TEMPLATE.md)

## Pass Criteria

The slice passes this gate if all of the following are true:

- the key scenarios show meaningful glue reduction
- no core scenario regresses
- the model feels simpler or at least no heavier than before
- no major concept overlap remains in the active slice surface
- the remaining glue is clearer and narrower
- the spec is still understandable without tooling

## Failure Conditions

The slice fails this gate if any of the following happen:

- the Glue Gap Analysis does not improve in meaningful scenarios
- the slice adds concepts without removing corresponding glue
- the spec becomes harder to understand than the benefit justifies
- the tooling or Studio becomes necessary to explain the protocol
- the slice leaves core overlap unresolved and then asks the next slice to build on top of it

## Output

The gate should produce:

1. a short written report
2. updated evaluation outputs for the baseline scenarios
3. a go / no-go decision for the next slice

## Decision Rule

The default decision rule is:

- `go`
  - if the slice reduces glue and preserves clarity
- `pause`
  - if the slice improves behavior but still needs cleanup before expansion
- `no-go`
  - if the slice adds too much complexity for the value it delivers

For the current stage, the expected question is:

> Is `0.15` clean enough that Phase 3 Slice 1 can move from outline into
> proposal and implementation planning?

That should be answered by this gate, not by momentum.
