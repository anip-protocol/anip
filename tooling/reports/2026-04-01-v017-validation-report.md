# Slice Validation Report

## Slice

- Slice / version: `anip/0.17`
- Date: `2026-04-01`
- Reviewer: `Codex`
- Decision: `go`

## Scope

- What changed:
  - added `refresh_via` and `verify_via` as same-manifest advisory composition hints
  - kept the slice narrowly focused on local capability relationships
  - aligned spec, schema, runtimes, Studio, examples, docs, and conformance on the new fields
- What this slice was supposed to remove:
  - bespoke refresh-path discovery glue
  - bespoke verification/follow-up discoverability glue
  - local orchestration guesswork around “what capability should I call next?”
- What this slice explicitly should not become:
  - workflow graph system
  - cross-service relationship language
  - planner language
  - compensation framework

## Glue Reduction Review

### Scenario Results

| Scenario | Previous | Current | Change | Notes |
| --- | --- | --- | --- | --- |
| travel-single | `PARTIAL` | `PARTIAL` | no result-state change | still dominated by budget / approval / replanning concerns rather than local composition discoverability |
| travel-multiservice | `PARTIAL` | `PARTIAL` | no result-state change | still dominated by multi-service handoff and reconstruction glue, which `0.17` intentionally does not solve |
| devops-single | `HANDLED` | `HANDLED` | no result-state change | already healthy; advisory hints improve local discoverability, not top-line result state |

### What Improved

- ANIP now exposes a lightweight local relationship layer around capabilities.
- Refresh paths are more discoverable from the manifest instead of requiring wrapper knowledge.
- Verification / follow-up hints are now protocol-visible for same-service cases.
- The slice stayed narrow and did not reopen Phase 2 or Phase 3 Slice 1 surfaces.
- Studio and docs now present local composition hints directly.

### What Glue Was Removed

- some manual mapping from stale-artifact failures to “which capability refreshes this?”
- some local service-specific knowledge about which read capability should verify an irreversible side effect
- some prompt / wrapper glue that previously had to infer obvious same-service follow-up paths from naming or docs

### What Glue Still Remains

- the main remaining glue is now clearly multi-service:
  - cross-service task continuity
  - cross-service parent/child linkage
  - cross-service audit reconstruction
  - cross-service handoff interpretation
- the current baseline still under-measures local advisory composition gains because the top-line scenarios are dominated by earlier-phase and distributed concerns
- some of the new recovery/composition pressure packs are likely overrated as `HANDLED` by the current evaluator, which means the tooling still needs to get better at judging advisory value, not just field presence

### Legacy Comparison Note

- legacy surface reviewed:
  - generic REST / GraphQL / MCP style single-service and multi-service action flows
- scenario:
  - stale artifact refresh and post-action verification / follow-up discovery
- main glue delta:
  - ANIP now exposes more of the local follow-up semantics directly in the interface
  - legacy interfaces still force:
    - name guessing
    - doc reading
    - prompt hints
    - wrapper-maintained “what to call next” knowledge

## Complexity And Intuitiveness Review

### What Got Simpler

- local refresh and verification relationships now have a bounded, manifest-visible form
- the slice is easy to explain from the spec
- same-manifest-only scope keeps the model concrete and understandable
- no duplicate inverse relation or graph language was added

### What Still Feels Heavy

- advisory composition is now another planning-oriented surface, so the tooling and docs have to stay clear that these hints are optional and local
- the current validator is still better at judging hard enforcement than advisory guidance

### Overlap Or Concept Drift

- no major overlap similar to pre-`0.14` Slice 1 remains
- no obvious workflow-engine drift appears in `0.17`
- no cross-service overreach was introduced; the same-manifest boundary holds
- the main future risk is trying to stretch these local hints into distributed semantics instead of letting Phase 4 solve that explicitly

### Tooling Dependence Check

- Can the slice still be understood from the spec alone?
  - yes
- Can a strong engineer still implement it without Studio or validator support?
  - yes
- Did the slice preserve ANIP's identity as an interface and control protocol?
  - yes

## Recommendation For The Next Slice

### What The Next Slice Should Target

- cross-service task continuity
- cross-service `parent_invocation_id` semantics
- cross-service audit linkage expectations
- bounded reconstructability across service boundaries

### What The Next Slice Must Not Touch

- turning advisory composition into a workflow language
- re-opening budget / binding / authority taxonomy
- stretching same-manifest hints into implicit cross-service references
- introducing a global registry, orchestrator, or central audit system

### Cleanup Required Before Implementation

- no protocol cleanup blocker remains from `0.17`
- before or alongside Phase 4 Slice 1 work, add multi-service continuity scenarios to the tooling baseline
- improve the evaluator so advisory and distributed value are judged more honestly, not just by surface presence

## Final Assessment

- Glue reduction result:
  - `0.17` improves local refresh / verification discoverability, but the current baseline scenarios do not show top-line result-state movement because the main unresolved pain is now distributed rather than local
- Complexity result:
  - positive; `0.17` adds useful planning hints without materially increasing conceptual weight
- Final justification:
  - this is a healthy, narrow protocol evolution
  - it did not turn ANIP into a monster
  - it closes a local composition gap cleanly
  - Phase 4 Slice 1 can move forward, and now is the right moment to do it because the main remaining glue is increasingly cross-service rather than single-service
