# ANIP Studio: Developer Definition, Code Generation, and SDLC Integration

## Purpose

Studio is now strong on Product Design, traceability, and review, but code generation is still too tightly coupled to Studio internals.

That coupling is the wrong long-term shape.

ANIP needs a clean path into existing software delivery workflows:

1. Product intent is authored and reviewed in Studio
2. Developer Design formalizes that intent into a machine-readable definition
3. Generator adapters consume that definition
4. Verifier modules consume that definition
5. CLI tooling validates, lints, generates, and verifies in CI
6. IDE plugins can author the same Developer Design artifact without requiring the full PM workflow

The result is that ANIP becomes compatible with normal SDLC practices instead of depending on Studio as the only execution surface.

Related design note:

- `2026-04-16-anip-design-revision-signatures.md`

## Problem

Today, Studio still risks being perceived as:

- the place where PM writes intent
- the place where developers shape implementation
- the place where generation logic lives
- the place where verification is initiated

That is too much responsibility in one product boundary.

It creates five problems:

1. **Generation is too Studio-centric**
   - code generation logic is not cleanly reusable outside Studio
   - CI and automation have no stable first-class contract to consume

2. **Developer tooling is constrained**
   - IDE workflows should not require the full PM guidance and signoff experience
   - developers need a formal artifact they can edit, lint, and generate from directly

3. **Verification lacks the right contract boundary**
   - Product Design contains freeform and abstract business intent
   - deterministic implementation verification cannot reliably operate against that layer directly

4. **Studio risks becoming a monolith**
   - UI, generation, verification, and automation concerns become too entangled

5. **Verification is not isolated enough**
   - implementation conformance should be checkable outside Studio
   - CI pipelines need a stable verifier boundary, not a UI-driven workflow

## Design Goal

The right architecture is:

- **Product Design defines intent**
- **Developer Design formalizes that intent**
- **Developer Definition becomes the canonical machine-readable contract**
- **Generator adapters consume that contract**
- **Verifier modules consume that contract**
- **Verification checks implementation against that contract**
- **PM signoff confirms the formalization still matches business intent**

Studio remains important, but it becomes:

- the authoring surface
- the review surface
- the export/import surface
- the traceability surface

It should not be the only place where generation logic exists.

## Core Model

### 1. Product Design

Product Design remains the business-facing layer.

It captures:

- requirements
- scenarios
- service design intent
- risk and authority posture
- approval expectations
- PM review and signoff

This layer is allowed to be partly interpretive and partly freeform.

It is not the primary deterministic verification target.

### 2. Developer Design

Developer Design is the formal refinement layer.

It records:

- concrete service boundaries
- concrete capability definitions
- inputs and outputs
- authority and approval semantics
- audit and lineage requirements
- backend mapping choices
- orchestration expectations
- extension points

Developer Design must be structured enough to drive:

- code generation
- linting
- deterministic verification

### 3. Developer Definition

Developer Design should produce a canonical exportable artifact.

Examples:

- `developer-definition.json`
- `anip-service-definition.json`

This artifact becomes the stable contract between:

- Studio
- CLI tooling
- generator adapters
- IDE plugins
- verification tooling

This is the key architectural shift.

## Module Boundaries

The contract should be consumed by separate modules with clear ownership.

Examples:

- `anip-definition-schema`
- `anip-generator-*`
- `anip-verifier-*`
- `anip-cli`

### Definition schema module

Owns:

- canonical schema
- schema versioning
- shared validation helpers

### Generator modules

Own:

- target-specific scaffold generation
- adapter-specific linting
- generator-specific capability support checks

### Verifier modules

Own:

- implementation conformance checks
- observed service validation
- regression-pack execution against declared expectations
- evidence production for CI and Studio

### CLI module

Owns:

- a stable command surface for validate, lint, generate, and verify
- machine-readable output for CI
- local developer entrypoints

The important boundary is:

- Studio authors and exports the contract
- modules consume the contract directly
- CI and IDE tooling do not depend on Studio runtime APIs for normal operation

## Canonical Artifact: Developer Definition

The Developer Definition should be versioned and schema-validated.

At minimum it should contain:

- schema version
- project identity
- source Product Design references
- coverage mapping back to Product Design
- service boundaries
- capability inventory
- capability inputs
- capability outputs
- side-effect posture
- authority and approval posture
- audit and lineage expectations
- cross-service orchestration expectations
- backend mapping requirements
- generator hints
- extension points
- verification hints

### Example categories

#### Identity and provenance

- project id
- project title
- generated at
- source requirements ids
- source scenario ids
- source service design ids
- PM review state

#### Service model

- service names
- responsibilities
- owned domain concepts
- cross-service handoffs

#### Capability model

- capability id
- capability title
- inputs
- outputs
- approval requirement
- restriction behavior
- audit requirement

#### Implementation model

- backend adapter shape
- domain mapping requirements
- response shaping requirements
- extension hooks

#### Verification model

- required observed services
- required capability declarations
- required runtime behaviors
- expected regression classes

## Coverage Mapping and Traceability

Product Design cannot be the direct verification target for all cases.

That does **not** mean Product Design becomes advisory only.

Instead, Product Design must flow into Developer Design through explicit coverage mapping.

Each relevant Product Design unit should have a developer-side coverage state such as:

- `not_addressed`
- `partially_addressed`
- `addressed`
- `deferred`
- `not_applicable`

Each mapped item should support:

- rationale
- linked developer artifact(s)
- linked implementation area(s)
- linked verification evidence where available

This gives the right chain:

1. Product Design defines intent
2. Developer Design formalizes the intent
3. Verification checks implementation against the formalized design
4. PM reviews the trace and signs off

## Generator Adapters

Code generation should be extracted into dedicated generator adapters.

Examples:

- Python FastAPI adapter
- TypeScript adapter
- Go adapter
- other language/runtime targets later

Each adapter should:

- accept the same Developer Definition contract
- validate required fields for its target
- lint unsupported or inconsistent choices
- generate scaffold/output
- report issues in a consistent format

The key rule is:

**Generators consume the canonical definition directly.**

They should not depend on Studio runtime internals as their primary interface.

## Verifier Modules

Implementation verification should be externalized just like code generation.

Verifier modules should consume the same Developer Definition contract and validate:

- generated implementation correctness
- manually implemented service correctness
- deployed service conformance
- regression behavior against declared expectations

Examples:

- `anip-verifier`
- `anip-verifier-regression`
- `anip-verifier-observed-surface`

Verifier modules should support both:

- local developer use
- CI pipeline execution

This is critical for enterprise adoption because verification must be automatable and source-controlled, not trapped inside a Studio session.

## CLI and CI Integration

Once the Developer Definition exists, CLI support becomes straightforward.

Examples:

```bash
anip design validate developer-definition.json
anip design lint developer-definition.json
anip design generate --adapter python-fastapi developer-definition.json
anip design generate --adapter typescript developer-definition.json
anip design verify --definition developer-definition.json --service http://localhost:8080
anip design verify --definition developer-definition.json --regression-pack gtm-phase7.json
```

This enables normal CI workflows:

- validate design artifacts on pull request
- lint generator inputs before generation
- generate scaffold in automation
- verify live or generated services against the formalized contract
- fail delivery when required contract assertions do not hold
- publish conformance evidence as part of the pipeline result

Studio should be able to export this exact artifact so teams can:

- commit it to source control
- validate it in CI
- generate from it outside Studio
- verify implementations from it outside Studio

## Source of Truth and Drift Rules

This architecture only works if the source-of-truth rules are explicit.

The rule should be:

- Studio is the primary authoring and review surface
- frozen exported artifacts committed in git are the delivery truth
- generation and CI verification run against repo-tracked artifacts
- if Studio and git diverge, Studio cannot claim the project is current until that divergence is reconciled

That gives each layer a clear role:

- Studio owns authoring, review, traceability, and export
- git owns delivery-state truth
- CLI and CI consume the repo-tracked artifacts

This avoids an ambiguous state where:

- Studio shows one version
- the repo contains another
- CI validates a third assumption

### Drift handling

When Studio and repo artifacts differ, the system should surface that explicitly.

Examples of valid states:

- `in_sync`
- `studio_ahead_of_repo`
- `repo_ahead_of_studio`
- `diverged`

Studio should not silently overwrite repo truth, and CI should not depend on whatever Studio currently holds in memory.

The hard rule is:

- delivery workflows trust frozen repo artifacts
- authoring workflows must reconcile against those artifacts before claiming readiness

## Conformance Levels

The contract flow should expose explicit conformance levels instead of collapsing everything into a single pass/fail concept.

Recommended levels:

1. `schema_valid`
   - the Developer Definition satisfies the canonical schema
2. `lint_valid`
   - the definition is internally coherent enough to proceed
3. `adapter_supported`
   - the chosen generator or verifier can support the requested features
4. `generated`
   - scaffold or generated output was produced successfully
5. `runtime_conformant`
   - the implementation surface matches the formalized contract
6. `regression_green`
   - declared regression packs pass against the implementation
7. `signoff_approved`
   - PM signoff exists for the frozen Product Design and Developer Definition pair

These levels should be usable in:

- Studio status views
- CLI output
- CI pipeline gates
- IDE diagnostics

This gives teams a clearer maturity ladder than a single “valid” label.

## Extension Namespacing

The Developer Definition will need extension points, but those must not become an unstructured junk drawer.

Extensions should be namespaced from the start.

Recommended patterns:

- `generator.<adapter-name>.*`
- `verifier.<module-name>.*`
- `runtime.<platform-name>.*`
- `x-<org>.*` for organization-local extensions

The rule is:

- if a field is required across multiple generators or verifiers, promote it into the core contract
- if it is target-specific, keep it in a namespaced extension block

This preserves a disciplined core while still allowing adapter-specific evolution.

Without namespacing, the Developer Definition will accumulate one-off fields that are difficult to validate, port, or reason about.

## Linting

The Developer Definition should support dedicated linting before generation.

Linting is distinct from schema validation.

Examples of lint rules:

- required capability ownership missing
- approval posture conflicts with declared side effects
- cross-service orchestration references missing services
- extension hooks declared without generator support
- verification expectations impossible to satisfy for the chosen adapter

This gives teams an earlier and stricter quality gate than generation alone.

## Verification Boundary

Implementation verification should target **Developer Design**, not raw Product Design prose.

That means:

- deterministic verification is used wherever the design is structured enough
- human review remains for interpretive business intent

Examples of deterministic verification:

- required service exists
- required capability exists
- required input exists
- declared approval behavior is present
- declared denial/restriction behavior is present
- required lineage fields are present
- observed metadata matches declared service surface
- regression cases pass/fail as expected

Examples that remain review-based:

- whether narrative business intent is well represented
- whether PM expectations were interpreted correctly
- whether explanation quality is sufficient for operators

This is the right split:

- **Developer Design is the deterministic verification target**
- **Product Design is the traceability and signoff source**

## CI/CD Integration

This model is designed to fit directly into existing enterprise delivery pipelines.

A typical pipeline shape becomes:

1. export or load the committed Developer Definition
2. validate schema and contract completeness
3. lint the definition for internal consistency
4. generate target scaffolding where required
5. build and test the implementation
6. verify the implementation against the same Developer Definition
7. publish conformance evidence
8. block promotion if required checks fail

That means the Developer Definition becomes a first-class SDLC artifact:

- reviewable in pull requests
- enforceable in CI
- consumable by local tooling
- usable for runtime verification after deployment

For ANIP showcases such as GTM, this is the next important step:

- wire the GTM pipeline to validate, lint, generate, and verify against the exported Developer Definition in CI/CD

That is the enterprise proof point:

- not just that Studio can shape a system
- but that the same contract can govern implementation correctness in delivery pipelines

## Studio Responsibilities

Under this model, Studio should be responsible for:

1. authoring Product Design
2. authoring Developer Design
3. maintaining coverage mapping between them
4. exporting the Developer Definition
5. importing the Developer Definition where appropriate
6. presenting verification results
7. presenting PM signoff and review state

Studio should **not** be the only runtime that generation depends on.
Studio should **not** be the only runtime that verification depends on.

## IDE Plugin Direction

This architecture is what makes IDE support realistic.

The plugin scope should be:

- Developer Design only
- no PM guidance workflow
- no PM signoff workflow
- no business authoring workflow

The plugin should:

- edit the same canonical Developer Definition
- validate and lint it locally
- invoke generator adapters
- optionally scaffold ANIP service code directly in the IDE

This is especially valuable for:

- VS Code
- Zed

The important dependency rule remains the same:

- IDE plugins consume the Developer Definition contract
- IDE plugins call generator adapters or CLI entrypoints
- IDE plugins do **not** depend on Studio server APIs as the primary generation path

## Why This Fits Existing SDLCs

This model fits existing engineering workflows because it introduces a stable contract boundary.

Teams can:

- review Product Design in Studio
- formalize implementation in Developer Design
- export a canonical Developer Definition
- commit that definition to source control
- lint and validate it in CI
- generate scaffolds from it in automation
- verify live services against it
- enforce conformance in deployment pipelines
- use IDE tooling without needing the full Studio experience

That means ANIP is no longer just:

- a protocol
- a Studio workflow
- a showcase flow

It becomes a delivery model that fits naturally into:

- code review
- CI pipelines
- local IDE workflows
- generated scaffolding
- implementation verification

## Recommended Rollout

The rollout should be incremental, but the first proving set should still be complete enough to demonstrate the whole delivery loop.

That means:

- not artificially minimizing the architecture
- but defining one bounded proving surface that exercises the full contract model end to end

For example, GTM can be the first complete proving surface even if the broader ANIP platform later expands to more adapters and domains.

### Phase 1: Define the contract

- define the canonical Developer Definition schema
- make coverage mapping first-class
- define export/import behavior in Studio

### Phase 2: Define the first complete proving surface

- choose one flagship pipeline, such as GTM
- define the full generation and verification flow for that pipeline
- lock the source-of-truth and drift rules for that first surface

### Phase 3: Extract generator and verifier paths

- convert the selected generation path to consume the exported Developer Definition
- convert the selected verification path to consume the same contract
- make conformance levels explicit in the outputs

### Phase 4: Add CLI entrypoints

- `validate`
- `lint`
- `generate`
- `verify`

### Phase 5: Wire Studio to the same contract

- Studio exports the same artifact the CLI consumes
- Studio no longer acts as the only place generation logic can run
- Studio no longer acts as the only place verification can be initiated

### Phase 6: Add IDE support

- VS Code first
- Zed next
- scope limited to Developer Design and generator execution

### Phase 7: Expand adapters and domains

- add more language/runtime targets
- keep all adapters bound to the same contract
- use the same conformance model and drift rules everywhere

## Non-Goals

This design does not mean:

- Product Design becomes unimportant
- PM prose must be fully machine-verifiable
- IDE plugins should reimplement Studio
- generators should call back into Studio APIs for normal use
- every Studio concept must be part of the exported artifact

The goal is a clean contract boundary, not duplication of the full Studio product.

## Decision

ANIP should adopt a **Developer Definition** artifact as the canonical machine-readable output of Developer Design.

Studio should author and export that artifact.

Generator adapters, verifier modules, CLI tooling, CI workflows, and IDE plugins should consume that artifact directly.

Verification should target the formalized Developer Design contract, while PM confidence should come from coverage mapping and signoff back to Product Design.
