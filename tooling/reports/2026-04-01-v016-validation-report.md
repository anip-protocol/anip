# Slice Validation Report

## Slice

- Slice / version: `anip/0.16`
- Date: `2026-04-01`
- Reviewer: `Codex`
- Decision: `go`

## Scope

- What changed:
  - added required `resolution.recovery_class`
  - tightened the canonical `resolution.action` vocabulary and completed runtime canonicalization
  - made action-to-recovery posture mapping explicit and conformance-checked
  - updated Studio and docs to expose recovery posture more directly
- What this slice was supposed to remove:
  - bespoke failure-to-next-step mapping glue
  - synonym handling around recovery actions
  - custom retry / wait / refresh interpretation logic
  - wrapper logic that had to infer recovery posture from failure text
- What this slice explicitly should not become:
  - workflow engine
  - planner
  - composition graph system
  - compensation framework
  - broad second taxonomy that competes with `resolution.action`

## Glue Reduction Review

### Scenario Results

| Scenario | Previous | Current | Change | Notes |
| --- | --- | --- | --- | --- |
| travel-single | `PARTIAL` | `PARTIAL` | no result-state change | still dominated by budget, approval, and replanning concerns rather than recovery-posture interpretation |
| travel-multiservice | `PARTIAL` | `PARTIAL` | no result-state change | still dominated by booking-path control glue and multi-service handoff / operator glue |
| devops-single | `HANDLED` | `HANDLED` | no result-state change | refusal/recovery path is now cleaner to route, but the scenario was already healthy |

### What Improved

- Failure recovery posture is now more explicit and machine-readable.
- `resolution.action` is more disciplined and less synonym-prone than before.
- Agents can distinguish retry-now vs refresh vs redelegation vs revalidate vs terminal without bespoke mapping code.
- Studio now exposes recovery posture directly instead of leaving the user to infer it from action strings alone.
- Conformance now guards canonical action usage more directly.

### What Glue Was Removed

- some custom “what should happen next?” mapping logic after failure
- some ad hoc grouping of failure actions into:
  - retry now
  - wait
  - refresh
  - redelegate
  - terminal
- some wrapper-side translation from failure text into routing decisions
- some action-synonym glue that Phase 3 would otherwise have compounded

### What Glue Still Remains

- travel scenarios still retain:
  - budget and approval glue
  - cheaper-alternative / replanning glue
  - multi-service handoff policy glue
  - operator-side cross-service audit aggregation glue
- recovery-heavy scenario pressure is still underrepresented in the tooling baseline:
  - stale binding / refresh-first
  - temporary unavailability / wait-then-retry
  - revalidate-state before retry
  - terminal service-owner intervention

### Legacy Comparison Note

- legacy surface reviewed:
  - generic REST / GraphQL / MCP style failure and blocked-action flows
- scenario:
  - recoverable failure and blocked booking / admin-operation style next-step routing
- main glue delta:
  - ANIP now exposes more of the recovery posture directly
  - legacy interfaces still force:
    - custom retry classification
    - string parsing of failure bodies
    - hand-built wait / refresh / redelegation routing
    - inconsistent next-step behavior across services

## Complexity And Intuitiveness Review

### What Got Simpler

- `resolution.action` and recovery posture now fit together more cleanly.
- Recovery routing is easier to explain from the spec.
- The slice stayed narrowly centered on failure posture rather than reopening Phase 2 surfaces.
- Canonical action cleanup reduced drift instead of adding another layer on top of existing drift.

### What Still Feels Heavy

- `resolution.action` is now carrying a lot of strategic weight across:
  - authority
  - control
  - recovery
- that is acceptable for now, but it means Slice 2 must be careful not to add a large parallel composition taxonomy too quickly

### Overlap Or Concept Drift

- no major overlap similar to pre-`0.14` Slice 1 remains
- `recovery_class` stays advisory and does not appear to reopen `retry`
- no obvious workflow-engine drift appears in the implemented `0.16` surface
- the main future risk is adding too many follow-up / composition hint concepts in Phase 3 Slice 2

### Tooling Dependence Check

- Can the slice still be understood from the spec alone?
  - yes
- Can a strong engineer still implement it without Studio or validator support?
  - yes
- Did the slice preserve ANIP's identity as an interface and control protocol?
  - yes

## Recommendation For The Next Slice

### What The Next Slice Should Target

- narrow advisory composition hints
- refresh / verification / follow-up guidance that reduces orchestration glue
- lightweight next-step relationships between capabilities

### What The Next Slice Must Not Touch

- re-opening authority posture taxonomy
- re-opening Slice 1 budget / binding semantics
- changing `retry` semantics
- adding workflow graphs, planners, or large compensation machinery
- creating a second broad taxonomy that competes with canonical `resolution.action`

### Cleanup Required Before Implementation

- no protocol cleanup blocker remains from `0.16`
- before or alongside Phase 3 Slice 2 work, add recovery-heavy scenario packs to the tooling baseline
- do not judge Slice 2 only with the current three baseline scenarios; they still under-measure recovery-specific gains

## Final Assessment

- Glue reduction result:
  - `0.16` improves recovery interpretation and failure routing clarity, but the current baseline scenarios do not show top-line result-state movement because they are still dominated by earlier-phase concerns
- Complexity result:
  - positive; `0.16` adds meaningful semantic value without materially increasing conceptual weight
- Final justification:
  - this is a healthy, narrow protocol evolution
  - it did not turn ANIP into a monster
  - it improves the recovery surface in a way agents and implementers can use directly from the protocol
  - Phase 3 Slice 2 can move forward, but only if the validation baseline is expanded with recovery-heavy scenarios so the next gate measures the right thing
