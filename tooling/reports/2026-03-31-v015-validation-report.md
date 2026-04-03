# Slice Validation Report

## Slice

- Slice / version: `anip/0.15`
- Date: `2026-03-31`
- Reviewer: `Codex`
- Decision: `go`

## Scope

- What changed:
  - added explicit authority posture vocabulary through `reason_type`
  - added `resolution_hint` on restricted permission entries
  - tightened canonical `resolution.action` vocabulary around blocked authority
  - clarified `restricted` vs `denied` semantics and aligned runtimes, conformance, Studio, and docs
- What this slice was supposed to remove:
  - authority interpretation glue
  - permission probing glue
  - bespoke blocked-action mapping logic
  - custom translation from denial strings into next-step behavior
- What this slice explicitly should not become:
  - IAM system
  - approval platform
  - workflow engine
  - broad recovery/planning system

## Glue Reduction Review

### Scenario Results

| Scenario | Previous | Current | Change | Notes |
| --- | --- | --- | --- | --- |
| travel-single | `PARTIAL` | `PARTIAL` | no result-state change | still dominated by budget / approval glue rather than authority-classification glue |
| travel-multiservice | `PARTIAL` | `PARTIAL` | no result-state change | still dominated by booking-path budget glue and multi-service handoff policy logic |
| devops-single | `HANDLED` | `HANDLED` | no result-state change | blocked-action handling is cleaner and more explicit, but the top-line result was already healthy |

### What Improved

- Authority posture is now more machine-readable.
- Permission discovery gives a more useful next-step surface before invocation.
- `restricted` vs `denied` semantics are cleaner than before.
- `resolution_hint` and canonical authority actions reduce wrapper guesswork.
- The Studio and docs surface now teach a clearer authority model.

### What Glue Was Removed

- some custom mapping from permission denial to agent next step
- some permission-probing and string-parsing glue around blocked authority
- some bespoke logic to distinguish:
  - broader scope needed
  - stronger token shape needed
  - non-delegable action
- conceptual glue around whether authority blockers were terminal or grantable

### What Glue Still Remains

- travel scenarios still retain:
  - budget and approval glue
  - replanning / cheaper-alternative logic
  - multi-service handoff policy glue
  - some operator-side cross-service audit aggregation glue
- broader recovery posture is still not explicit enough:
  - when to wait
  - when to refresh
  - when to replan
  - when to verify or compensate

### Legacy Comparison Note

- legacy surface reviewed:
  - generic REST / GraphQL / MCP style travel and admin-control flows
- scenario:
  - blocked booking / high-risk operation under insufficient authority
- main glue delta:
  - ANIP now exposes more of the authority meaning directly
  - legacy surfaces still force:
    - permission probing
    - custom denial parsing
    - manual escalation mapping
    - inconsistent next-step handling

## Complexity And Intuitiveness Review

### What Got Simpler

- authority blockers now have a bounded, named vocabulary
- blocked authority meaning is easier to explain from the spec
- `restricted` and `denied` now have a cleaner practical split
- conformance now checks more of the authority semantics directly

### What Still Feels Heavy

- `resolution.action` is becoming strategically important and now spans both:
  - authority posture
  - broader recovery semantics
- that means Phase 3 must be careful not to explode the action vocabulary too quickly

### Overlap Or Concept Drift

- no major overlap similar to pre-`0.14` Slice 1 remains
- no obvious IAM or approval-system drift remains in the implemented `0.15` surface
- the main future risk is reopening too many recovery/action concepts at once in Phase 3

### Tooling Dependence Check

- Can the slice still be understood from the spec alone?
  - yes
- Can a strong engineer still implement it without Studio or validator support?
  - yes
- Did the slice preserve ANIP's identity as an interface and control protocol?
  - yes

## Recommendation For The Next Slice

### What The Next Slice Should Target

- recovery posture
- next-step semantics after failure or block
- tighter use of canonical `resolution.action`
- lightweight advisory recovery guidance

### What The Next Slice Must Not Touch

- re-opening authority posture vocabulary broadly
- re-opening Slice 1 binding or budget semantics
- introducing workflow graphs, planners, or compensation engines
- large synonym-heavy action sets

### Cleanup Required Before Implementation

- no protocol cleanup blocker remains from `0.15`
- before or alongside Phase 3 Slice 1 work, add authority-heavy scenario packs to the tooling baseline
- keep Phase 3 Slice 1 narrower than the full Phase 3 outline

## Final Assessment

- Glue reduction result:
  - `0.15` improves authority interpretation and blocked-action clarity, but the current baseline scenarios do not show top-line result-state movement because they are still dominated by Slice-1-era budget and multi-service concerns
- Complexity result:
  - positive; `0.15` adds surface area, but it is still bounded, understandable, and aligned with the spec
- Final justification:
  - this is a healthy, narrow protocol evolution
  - it did not turn ANIP into a monster
  - it materially improves the blocked-authority surface without making tooling mandatory
  - Phase 3 Slice 1 can move forward, but only as a narrow recovery-semantics slice built on the current canonical authority and action model
