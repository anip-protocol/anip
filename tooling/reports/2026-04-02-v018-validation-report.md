# Slice Validation Report

## Slice

- Slice / version: `anip/0.18`
- Date: `2026-04-02`
- Reviewer: `Codex`
- Decision: `go`

## Scope

- What changed:
  - added normative cross-service propagation guidance for `task_id`
  - added normative cross-service linkage guidance for `parent_invocation_id`
  - added `upstream_service` as an unvalidated reconstruction hint on invoke request/response/audit
  - aligned spec, schema, proto, runtimes, conformance, Studio, and docs on the new continuity surface
- What this slice was supposed to remove:
  - custom cross-service correlation glue
  - hidden task-propagation rules between services
  - bespoke parent/child linkage conventions
  - some operator-side trace stitching and reconstruction guesswork
- What this slice explicitly should not become:
  - workflow engine
  - global orchestrator
  - distributed tracing platform
  - cross-service relationship language

## Glue Reduction Review

### Scenario Results

| Scenario | Previous | Current | Change | Notes |
| --- | --- | --- | --- | --- |
| travel-single | `PARTIAL` | `PARTIAL` | no result-state change | still dominated by budget / approval / replanning concerns rather than cross-service continuity |
| travel-multiservice | `PARTIAL` | `PARTIAL` | no top-line result-state change | continuity and reconstruction are better, but the scenario still retains cross-service handoff interpretation glue |
| devops-single | `HANDLED` | `HANDLED` | no result-state change | local invocation model remains healthy; v0.18 does not materially change single-service posture |

### What Improved

- Cross-service continuity now has a bounded protocol surface instead of relying only on local convention.
- `task_id` and `parent_invocation_id` now have clearer multi-service meaning.
- `upstream_service` reduces some operator-side search work during reconstruction.
- The slice stayed structural and did not drift into workflow or service-graph semantics.
- Conformance now checks that foreign `task_id` and foreign `parent_invocation_id` are accepted rather than treated as service-local references.

### What Glue Was Removed

- some custom rules for whether downstream services may preserve an upstream task identity
- some ad hoc assumptions around whether a foreign `parent_invocation_id` is acceptable
- some operator-side guesswork about which service likely issued a parent invocation
- some wrapper logic that previously treated task and parent IDs as locally scoped instead of cross-service lineage fields

### What Glue Still Remains

- the main unresolved distributed glue is now more clearly about:
  - cross-service handoff semantics
  - cross-service output-to-input meaning
  - cross-service refresh / verification routing
  - bounded cross-service follow-up relationships
- the current core baseline still under-measures Phase 4 value because it tracks top-line scenario states better than it tracks reconstruction quality or handoff clarity
- `travel-multiservice` benefits from continuity, but it still remains `PARTIAL` because Slice 1 intentionally did not solve multi-service relationship semantics

### Legacy Comparison Note

- legacy surface reviewed:
  - generic REST / GraphQL / MCP style multi-service flows
- scenario:
  - one agent-driven task spanning multiple services with downstream follow-up and operator reconstruction
- main glue delta:
  - ANIP now preserves more lineage meaning directly at the interface boundary
  - legacy interfaces still force:
    - custom correlation IDs
    - hand-built propagation conventions
    - manual parent/child linkage rules
    - more operator-side trace stitching

## Complexity And Intuitiveness Review

### What Got Simpler

- multi-service continuity is easier to explain from the spec than before
- `upstream_service` is small, bounded, and clearly documented as a hint rather than a control surface
- the slice keeps Phase 4 grounded in continuity and reconstruction instead of jumping into richer distributed semantics too early

### What Still Feels Heavy

- Phase 4 introduces the first explicitly distributed semantic surface, so future slices need to stay disciplined
- `upstream_service` is helpful, but still only a hint; the tooling and docs need to keep that limitation visible

### Overlap Or Concept Drift

- no major overlap similar to pre-`0.14` Slice 1 appears here
- no obvious workflow-engine drift appears in `0.18`
- no global registry or tracing-system drift appears in the implemented surface
- the main future risk is trying to overload continuity fields to solve handoff semantics they were not designed to solve

### Tooling Dependence Check

- Can the slice still be understood from the spec alone?
  - yes
- Can a strong engineer still implement it without Studio or validator support?
  - yes
- Did the slice preserve ANIP's identity as an interface and control protocol?
  - yes

## Recommendation For The Next Slice

### What The Next Slice Should Target

- bounded cross-service handoff semantics
- clearer multi-service refresh / verification routing
- minimal distributed relationship clarity between adjacent services

### What The Next Slice Must Not Touch

- turning continuity fields into a workflow graph
- introducing a global task registry or central audit service
- re-opening local budget / binding / authority surfaces
- stretching same-manifest advisory composition hints into implicit distributed references without explicit rules

### Cleanup Required Before Implementation

- no protocol cleanup blocker remains from `0.18`
- before or alongside Phase 4 Slice 2 work, add more explicit multi-service handoff scenarios to the tooling baseline
- improve the evaluator so it can judge distributed coherence and reconstruction quality more directly, not just top-line `HANDLED / PARTIAL` states

## Final Assessment

- Glue reduction result:
  - `0.18` materially improves cross-service continuity and reconstructability, but the current baseline still does not fully capture the distributed value because the remaining pain has shifted to handoff semantics rather than identity propagation
- Complexity result:
  - positive; `0.18` adds a small, understandable distributed hint and clearer lineage rules without materially increasing conceptual weight
- Final justification:
  - this is a healthy, bounded Phase 4 start
  - it did not turn ANIP into a monster
  - it solves the right foundational distributed problem before richer multi-service semantics
  - Phase 4 Slice 2 can move forward, but it should stay narrowly focused on handoff / adjacent-service relationship clarity rather than broad distributed orchestration
