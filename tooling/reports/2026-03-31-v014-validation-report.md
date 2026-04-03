# Slice Validation Report

## Slice

- Slice / version: `anip/0.14`
- Date: `2026-03-31`
- Reviewer: `Codex`
- Decision: `go`

## Scope

- What changed:
  - removed overlapping binding-oriented `control_requirements` forms
  - kept `requires_binding` as the canonical home for binding and freshness
  - narrowed `control_requirements` to non-binding controls
  - simplified spec, runtimes, Studio, and docs around the same model
- What this slice was supposed to remove:
  - conceptual overlap
  - duplicate declaration paths
  - avoidable learning cost
  - future Slice 2 implementation pressure on top of a muddy Slice 1 model
- What this slice explicitly should not become:
  - new behavior expansion
  - policy engine
  - workflow engine
  - approval system

## Glue Reduction Review

### Scenario Results

| Scenario | Previous | Current | Change | Notes |
| --- | --- | --- | --- | --- |
| travel-single | `PARTIAL` | `PARTIAL` | no result-state change | still blocked mainly by budget / approval glue |
| travel-multiservice | `PARTIAL` | `PARTIAL` | no result-state change | still blocked mainly by booking-path budget glue |
| devops-single | `HANDLED` | `HANDLED` | no result-state change | refusal path remains healthy |

### What Improved

- The active pre-execution model is simpler.
- Binding semantics now have one canonical home.
- The next slice no longer needs to build on top of duplicated binding concepts.
- The public explanation surface is cleaner across spec, Studio, and docs.

### What Glue Was Removed

- protocol-shape glue around deciding whether binding/freshness belonged in:
  - `requires_binding`
  - or
  - invoke-time `control_requirements`
- implementation ambiguity across runtimes and Studio
- conceptual glue for readers trying to learn Slice 1

### What Glue Still Remains

- travel scenarios still retain:
  - budget-enforcement glue
  - approval / escalation glue
  - some multi-service handoff and aggregation glue
- authority posture is still too coarse for many blocked-action cases
- blocked authority failures still need wrapper interpretation in richer systems

### Legacy Comparison Note

- legacy surface reviewed:
  - generic REST / GraphQL / MCP style travel flow
- scenario:
  - over-budget search-then-book travel flow
- main glue delta:
  - ANIP still leaves budget and approval glue
  - legacy surfaces additionally force:
    - permission probing
    - side-effect guard wrappers
    - custom budget wrappers
    - bespoke correlation and trace stitching
    - more custom blocked-action interpretation

## Complexity And Intuitiveness Review

### What Got Simpler

- `requires_binding` is now the clear home for binding and freshness.
- `control_requirements` is narrower and easier to explain.
- The protocol no longer teaches two overlapping ways to express the same precondition.
- Slice 1 now feels more like one coherent control model instead of two intersecting ones.

### What Still Feels Heavy

- budget behavior still spans several sections and wants a compact decision-flow explanation
- the broader ANIP story is getting larger, so future slices must stay tightly bounded

### Overlap Or Concept Drift

- the major Slice 1 overlap is resolved
- no new category drift is obvious in `0.14`
- the remaining risk is not current duplication, but adding too much authority vocabulary in Slice 2

### Tooling Dependence Check

- Can the slice still be understood from the spec alone?
  - yes
- Can a strong engineer still implement it without Studio or validator support?
  - yes
- Did the slice preserve ANIP's identity as an interface and control protocol?
  - yes

## Recommendation For The Next Slice

### What The Next Slice Should Target

- authority posture
- blocked-action clarity
- stronger delegation meaning
- deterministic escalation posture

### What The Next Slice Must Not Touch

- binding semantics
- freshness semantics
- budget location and enforcement model
- any move toward workflow or approval-system creep

### Cleanup Required Before Implementation

- no major cleanup blocker remains from Slice 1
- keep Slice 2 tightly scoped and use this same gate again before further expansion

## Final Assessment

- Glue reduction result:
  - `0.14` did not materially change scenario result states, but it preserved Slice 1 gains while reducing conceptual and implementation overlap
- Complexity result:
  - positive; the active model is simpler and safer to extend
- Final justification:
  - this is a healthy simplification release, not a monster-making expansion
  - the protocol remains understandable without tooling
  - Slice 2 can move forward, but only if it stays focused on authority and blocked-action clarity rather than reopening Slice 1 surfaces
