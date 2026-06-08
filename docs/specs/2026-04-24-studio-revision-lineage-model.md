# Studio Revision Lineage Model

## Purpose

Studio is moving from a greenfield-oriented authoring flow toward a real change-management model for existing systems.

The core requirement is simple:

- evidence-bearing artifacts cannot be modeled as mutable singleton records
- derived artifacts must point to explicit parent revisions
- drafts and revisions must be separate concepts

This document defines the target lineage model so incremental implementation phases move in one consistent direction.

## Problem

The older Studio model implicitly treated project state as "the current saved thing":

- current Product Design
- current Developer Definition
- current generation
- current verification

That breaks down as soon as a project changes over time.

Real projects need to answer:

- What was approved before?
- What changed?
- What is the new proposed behavior?
- Which technical contract implements that change?
- Which generated outputs and verification evidence correspond to that contract?
- What revision is actually deployed?

Without revision lineage, Studio becomes ambiguous:

- a save may overwrite the thing evidence was supposed to reference
- "latest" and "current" get confused with "approved" and "deployed"
- staleness becomes hard to reason about
- change management for existing projects becomes unsafe

## Core Model

Studio should model a project as a chain of revisions and derivations, not as one mutable blob.

### Artifact classes

1. Drafts
   - Editable working state.
   - Local to a lane or authoring surface.
   - Not evidence-bearing.
   - Can diverge from the latest saved revision.

2. Revisions
   - Immutable saved snapshots.
   - Evidence-bearing.
   - Addressable by revision id, revision number, and signature/hash.
   - May be superseded by newer revisions but are never overwritten.

3. Derived evidence
   - Generation runs.
   - Runtime proof.
   - Evaluation evidence.
   - PM review.
   - Later: release/deployment records.
   - Always anchored to explicit parent revisions.

## Target lineage chain

The intended lineage chain is:

1. `Product Revision`
   - PM/business design snapshot.
   - Requirements, scenarios, actor model, permission posture, service shape or fronting intent.

2. `Developer Baseline`
   - Explicit handoff pinned to one Product Revision.
   - Freezes the Product source revision developers are implementing against.

3. `Developer Revision`
   - Immutable compiled contract snapshot derived from one Developer Baseline.
   - Represents the technical implementation contract.

4. `Generation Run`
   - Derived from one Developer Revision.
   - Produces runtime targets, generated projects, manifests, and extension scaffolds.

5. `Verification Evidence`
   - Derived from one Generation Run and one Developer Revision.
   - Includes local proof, evaluation evidence, and observed-service evidence.

6. `PM Review`
   - Review decision against a specific evidence set.
   - Must identify the Product Revision, Developer Revision, Generation Run, Evaluation, and observed evidence it refers to.

7. `Release / Deployment` (future)
   - Records which revision chain is actually running.
   - Separates "latest proposed" from "currently deployed".

## Non-negotiable invariants

These rules should remain true across all implementation phases.

### 1. Drafts are editable, revisions are immutable

- A draft may be changed any number of times.
- A revision is never edited in place.
- Saving changed draft content creates a new revision.

### 2. Every evidence-bearing artifact has explicit lineage

No artifact should rely on "whatever is latest right now."

Examples:

- a Developer Revision must point to the Product Revision or Developer Baseline it came from
- a Generation Run must point to the Developer Revision it was generated from
- a PM Review must point to the exact signatures and artifact ids it reviewed

### 3. "Latest" is a convenience view, not a source of truth

Studio may show:

- latest Product Revision
- latest Developer Revision
- latest Generation Run

But the actual source of truth is the explicit revision id/signature attached to the artifact being viewed.

### 4. Staleness is lineage drift

Staleness should always be expressed relative to lineage.

Good:

- Developer Revision 7 is based on Product Revision 12, but Product Revision 13 now exists.
- Evaluation E9 was run against Developer Revision 7, while the latest saved revision is Developer Revision 8.

Bad:

- "Current state is stale."
- "Saved design is out of date."

The user should always be able to see what artifact drifted from what parent.

### 5. Evidence can be valid for an older revision even when a newer draft exists

Unsaved or newer work does not invalidate older saved revisions.

Instead:

- evidence remains valid for the revision it references
- evidence becomes stale only relative to a newer saved revision
- Studio must communicate that distinction clearly

## Draft vs revision semantics

### Product lane

- Product authoring surfaces edit a working Product draft.
- Save creates a new immutable Product Revision.
- Developer work should not silently follow mutable Product state.

### Developer lane

- Developer authoring surfaces edit a working Developer draft.
- Save creates a new immutable Developer Revision.
- Generation and verification launch from a saved Developer Revision, never from draft state.

### Verification lane

- Verification does not create "truth"; it records evidence against a specific revision chain.
- Verification selection should make the target revision explicit.

## Existing-project change model

This lineage model is specifically designed to support non-greenfield work.

For an existing project, the operating flow becomes:

1. Capture or import the currently deployed behavior as a known baseline.
2. Save that as a Product Revision and Developer Revision chain.
3. Propose changes by editing new drafts derived from those revisions.
4. Save new revisions.
5. Generate and verify against the new revision chain.
6. Approve and later deploy the new revision.

This allows Studio to represent:

- current deployed state
- proposed change
- approved but not yet deployed revision
- superseded revision history

## Immediate terminology rules

Studio copy should consistently use:

- `working draft`
- `saved revision`
- `latest saved revision`
- `aligned generation run`
- `aligned evaluation evidence`
- `PM review target`

Studio copy should avoid:

- `current saved truth`
- `saved construct`
- `latest current artifact`

Those phrases imply mutability and confuse lineage.

## Required identifiers

The long-term model should surface explicit ids on artifacts such as:

- `product_revision_artifact_id`
- `product_revision_number`
- `developer_baseline_artifact_id`
- `developer_revision_artifact_id`
- `developer_revision_number`
- `generation_run_artifact_id`
- `evaluation_id`
- `pm_review_artifact_id`
- later: `release_artifact_id`, `deployment_artifact_id`

Signatures remain important, but ids are also needed for usable navigation and diffing.

## Phase plan

### Phase 1

Developer Definition revisions.

Status:

- implemented

Scope:

- immutable `developer_definition_revision` artifacts
- latest mutable convenience artifact retained only as a pointer/current summary
- generation runs record exact Developer Revision lineage
- UI distinguishes working draft vs latest saved revision

### Phase 2

Product Design revisions and baseline lineage.

Status:

- first slice implemented

Scope:

- immutable Product Revision artifacts
- baseline lock points to explicit Product Revision
- Developer Overview and PM surfaces show Product Revision lineage
- drift is reported as Product Revision vs Developer Baseline mismatch

Implemented first slice:

- locking Developer Baseline creates or reuses an immutable `product_design_revision`
- the baseline records `product_revision_artifact_id`, `product_revision_number`, and `product_design_hash`
- Developer Definition and Generation Run lineage carry the pinned Product Revision metadata
- Product Design edits after baseline lock make the baseline stale until re-locked, which creates the next Product Revision
- project breadcrumbs show compact active lineage badges such as `Product r3` and `Dev r7`, with full artifact ids available in hover text
- Revision History gives a read-only inspection and JSON export surface for Product and Developer revisions
- Revision History supports read-only structured compare for Product revision snapshots and Developer revision contract fields
- Revision History can create a new editable draft from a selected Product or Developer revision without changing active baseline, generation target, verification target, or publication state
- Verification and PM Review evidence cards classify evidence as current, superseded, unversioned, mismatched, or missing relative to saved Developer Revision lineage
- Evaluation evidence envelopes and PM Review records persist explicit Product/Developer revision metadata at save time; older records fall back to generation-run inference
- Registry and Studio-local publication payloads carry structured Product/Developer revision lineage in package metadata, manifest metadata, recommended lock metadata, and receipt verification payloads
- Verification shows latest published lineage and classifies it as current, superseded, mismatched, or unpublished relative to the current saved Product/Developer revision chain
- generator and verifier CLI JSON outputs surface lineage, Product revision, Developer revision, receipt authority, receipt signature, and receipt status so package provenance is visible outside Studio
- Studio local-publication verification persists receipt status and revision lineage back onto the publication artifact, and Developer Definition plus Verification surfaces show receipt authority/status alongside Product/Developer revision provenance
- Studio Verification can import CLI JSON output as an external provenance artifact and reconcile package identity, receipt state, and Product/Developer revision lineage against the latest publication
- Studio Verification can run the verifier directly against a Studio-local publication bundle, persist the verifier JSON as external CLI provenance, and show the result in the same evidence history
- Backend coverage includes a real verifier smoke test for the Studio-local publication bundle path, not only the mocked endpoint behavior
- Studio Verification can run the verifier against a remote Registry package using the backend Registry URL, persist verifier JSON as external provenance, and reconcile it against the recorded remote publication artifact
- Backend coverage includes a real remote Registry smoke path: a signed Registry package fixture is generated by Go registry code, served through a temporary Registry API, and verified through Studio by the actual verifier
- Registry signing now has explicit `dev` and `production` modes; production startup requires a configured Ed25519 key, and `/healthz` plus `/keys` expose signing mode and active key identity
- verifier and Studio Registry verification can enforce trust policy with required Registry signing mode and trusted receipt key id; policy mismatches are stored as failed provenance instead of opaque execution errors
- Remote Registry publish now requires an authenticated publish token; Studio stores that token server-side and proxies publication writes so browser code never handles the secret
- Registry publication, package, and receipt records now carry publisher identity, and verifier receipt validation includes that identity when present
- PM approval is treated as release-lineage evidence: approved PM Review records are reconciled against the current Product Revision, Developer Revision, and contract signature
- Developer Definition, Verification, and Revision History now distinguish draft/current, published, PM-approved, and released states; release records reference the approved revision chain and remote Registry package/version

### Phase 3

Revision history views and diffs.

Scope:

- revision timeline UI
- per-revision status matrix
- diff views for Product and Developer revisions
- evidence grouped under each revision

### Phase 4

Approval and release lineage.

Scope:

- PM approval targets explicit revision chain
- release/deployment records reference approved revision chain
- Studio distinguishes latest proposed from deployed production state

## Implementation guidance

### Keep incremental compatibility layers

Older singleton artifacts may remain temporarily as compatibility pointers or "latest saved" summaries, but:

- they must not be treated as canonical immutable evidence
- they must not hide the underlying revision artifacts

### Prefer additive rollout

Do not block the whole system on a full redesign.

Instead:

- add immutable revisions first
- preserve compatibility pointers
- move gating and messaging to revisions
- add navigation and diffing after lineage is stable

### Avoid premature release orchestration

Release/deployment tracking matters, but it should not be the first thing added.

The first priority is correct revision lineage across Product and Developer.

## Decision

Studio should adopt revision lineage as the foundational operating model.

This means:

- mutable singleton state is only draft/convenience state
- saved revisions are the canonical evidence-bearing artifacts
- every downstream artifact must reference its parent revision explicitly

This is the correct direction for both greenfield and existing-project change management.
