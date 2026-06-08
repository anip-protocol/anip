# Phase 8 Scale And Packaging Plan

This document records the next expansion slice after Phase 7.

Phase 7 proved governed scenario composition. Phase 8 needs to turn that into a
broader and more portable flagship pack without diluting the core story.

The goals are:

- prove the question pack is broad, not canned
- prove the generated service shape is not Python-specific
- give users a direct way to cross-check answers against modeled business data
- package the stack so it can be run and inspected without custom setup work

## Execution Order

The work should proceed in this order:

1. expand the regression matrix to `50` questions per phase
2. add a BI verification surface to the showcase stack
3. lock a language-neutral service generation target
4. generate the same services in `2` non-Python languages first
5. prove parity on the same regression pack
6. expand from `3` languages to `5` only after parity is stable
7. create language-specific compose overlays
8. package and ship

This ordering is intentional.

The highest-signal credibility gains come from:

- broader question coverage
- easier answer verification
- proof that the protocol contract survives a language change

Those should land before maintaining five separate stacks.

## Workstream 1: Fifty Questions Per Phase

The target is not random prompt volume. The target is a disciplined question
matrix.

Each phase should cover at least:

- happy path
- clarification
- denial
- restriction
- approval
- actor-aware variation
- wording variation
- top-N variation
- region variation
- quarter variation
- channel and objective variation where applicable
- safe-stop behavior where downstream completion is not allowed

For the compound phases, the matrix should also cover:

- multi-hop success
- multi-hop approval stop
- multi-hop actor-aware denial
- multi-hop clarification stop
- planner variants that still stay inside the same governed surface

The point is:

- breadth of governed behavior
- not a bag of one-off prompts

Status:

- the first full broad-bank execution is now complete
- executed coverage: `350 / 350`
- result:
  - Phase 1: `50 / 50`
  - Phase 2: `50 / 50`
  - Phase 3: `50 / 50`
  - Phase 4: `50 / 50`
  - Phase 5: `50 / 50`
  - Phase 6: `50 / 50`
  - Phase 7: `50 / 50`
- executed artifacts:
  - [question-bank-runs/README.md](./question-bank-runs/README.md)

### Small Shared Runtime Promotion

After the first broad-bank hardening pass, we promoted only the pieces that had
already proven to be deterministic and cross-domain:

- metadata-driven enum/default normalization
- generic raw-export/direct-send preflight denial helpers

Those now live in the shared Python runtime-utils package:

- [packages/python/anip-runtime-utils](../../../packages/python/anip-runtime-utils)

What stayed local on purpose:

- GTM cohort parsing
- GTM account/reference cleanup
- service-local aliases and backend semantics

The rule is:

- promote patterns, not fixes
- keep domain vocabulary local until it proves reusable

The broad bank was rerun after this extraction and stayed green at `350 / 350`.

## Workstream 2: BI Verification Surface

The showcase should include a BI/reporting surface so users can validate the
modeled data without writing SQL or reverse-engineering joins.

### Recommended Tool

Use `Metabase` first.

Reason:

- open source
- straightforward Docker Compose fit
- better business-user verification surface than raw SQL
- easy to expose a few curated dashboards instead of an analyst-only interface

Alternative options:

- `Superset`
  - stronger for exploration-heavy slicing
  - less polished as a simple buyer-facing validation surface
- `Lightdash`
  - attractive if dbt-native semantics need to be the central story
  - not the simplest first packaging choice

### BI Scope

The BI layer should mirror the governed data model already exposed through ANIP.

The first dashboards should map directly to the showcase capabilities:

- pipeline summary
- risk-adjusted forecast
- stage bottlenecks
- stalled opportunities
- at-risk account ranking
- sales-team performance
- product pipeline
- reassignment preview alignment
- lead scoring and routing preview alignment

The dashboard filters should use the same business concepts the services use:

- quarter
- region / owner scope
- stage
- product
- manager
- ranking basis where relevant
- top-N or bounded result counts where relevant

The goal is not to reproduce ANIP inside BI.

The goal is:

- ask the agent a governed question
- inspect the bounded answer
- verify the underlying modeled slice from the same warehouse data

Status:

- `Metabase` is now wired into the showcase Compose stack
- curated `analytics_gtm.bi_gtm__*` dbt views now exist for verification
- verification runbook:
  - [phase8-bi-verification.md](./phase8-bi-verification.md)

## Workstream 3: Adapter Parity Across Languages

The protocol story gets much stronger if the same services can be generated in
multiple languages and still pass the same regression pack.

### Requirements

We need parity for:

- adapters
- service generation
- runtime behavior against the same ANIP contract

The target is `5` supported languages, but not all at once.

### Recommended Sequence

1. keep `Python` as the baseline implementation
2. add `TypeScript`
3. add one compiled language, preferably `Go`
4. prove parity on the same regression suite
5. only then expand to the remaining two languages

This is the right order because:

- Python and TypeScript prove the common interpreted runtime cases
- Go proves the contract is not tied to one dynamic-language execution model
- adding all five immediately would create too much template and packaging
  surface before parity is known to be real

### Parity Standard

Language parity should mean:

- same Studio source design
- same generated service contract
- same capability IDs
- same inputs and defaults
- same governed outcomes
- same approval posture
- same audit semantics
- same regression result categories

If a language target passes only because of a custom forked template path, that
is not real parity.

## Workstream 4: Code Generation For Five Languages

Studio should generate the same service family across all target languages from
the same design source.

That means:

- one source design
- one protocol contract
- multiple generated implementations

The claim should not be:

- this one Python path happens to work

The claim should be:

- the protocol and generation model are carrying the behavior

The correct implementation standard is:

- generic generation logic in Studio
- language-specific templates where necessary
- no GTM-only Studio core logic
- no per-language behavioral drift hidden in handwritten patches

## Workstream 5: Same Services In Different Languages

For the flagship proof, we should generate the same showcase services in
multiple languages:

- pipeline
- enrichment
- prioritization
- outreach

This should be tested as:

- same question pack
- same actor pack
- same expected outcomes
- same approval checks
- same audit assertions

The point is to prove:

- the protocol is doing the work
- not language-specific runtime magic

## Workstream 6: Compose Packs Per Language

We should not maintain five unrelated Compose stacks by copy-paste.

The right shape is:

- one shared base stack
- thin language-specific overlays

Shared base:

- Postgres
- dbt
- Cube
- Studio
- BI tool
- shared seed and observer jobs

Language overlays:

- service images
- adapter/runtime language selection
- language-specific build steps

That keeps the system maintainable while still making it easy to demo a
language-specific stack.

## Packaging Standard

Packaging is the last step, not the proof itself.

The package should include:

- reproducible startup
- preloaded Studio artifacts
- saved proof docs
- regression reports
- BI dashboards
- operator runbook
- language overlay instructions

The package should let someone do four things quickly:

1. run the stack
2. ask governed questions
3. inspect approvals and audit
4. cross-check the answers against the modeled data

## Immediate Next Slice

The immediate next implementation sequence should be:

1. expand the question packs toward `50` per phase
2. add `Metabase` to the Docker Compose stack
3. wire curated dashboards to the same GTM marts and dimensions
4. define the first non-Python parity target
5. generate the same service family in that language
6. run the same regression suite against both stacks

Only after that should we broaden to all five languages and all packaging
variants.

## Success Criteria

Phase 8 is successful when we can show:

- the question packs are broad enough that people cannot dismiss them as canned
- answers can be cross-checked in a simple BI layer without SQL
- the same services can be generated in multiple languages
- the same regression suite passes across those language targets
- the stack can be packaged and run with minimal manual setup
