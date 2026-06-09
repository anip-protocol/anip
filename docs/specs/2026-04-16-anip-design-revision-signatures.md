# ANIP Studio: Frozen Design Revisions, Signatures, and Verification Identity

## Purpose

ANIP now has a stronger end-to-end design flow:

1. Product Design defines business intent
2. Developer Design formalizes that intent
3. generation and verification operate against the formalized design

The next step is to make that flow cryptographically stable enough for:

- CI/CD enforcement
- deterministic drift detection
- auditability
- reproducible enterprise delivery workflows

That requires more than a simple lock flag.

It requires content-derived identities for each frozen stage of the process.

## Problem

Today, Studio can lock Product Design for development and can model PM review/signoff, but the process is still too mutable from a validation perspective.

Without stable revision identities:

- a "locked" baseline is only a UI state
- downstream tools cannot prove which exact design revision they are using
- validation can proceed even if the design changed underneath
- PM signoff is harder to tie to a specific developer formalization
- CI cannot cheaply reject mismatched design state before deeper verification runs

That is not rigorous enough for the workflow ANIP is aiming to support.

## Design Goal

The process should have three frozen, content-addressable identities:

1. `product_design_revision_id`
2. `developer_definition_id`
3. `pm_signoff_id`

Each one should be derived from canonical frozen content, not from mutable database ids.

Any meaningful change to the underlying artifact must produce a new identity.

Validation should check those identities first before doing deeper conformance work.

## Core Model

### 1. Product Design Revision

Created when PM/Product Design is explicitly locked for development.

It represents the frozen baseline that Developer Design is allowed to implement.

It should include:

- the active requirements set
- the scenario pack
- the selected service design
- revision metadata
  - created at
  - created by
  - optional note

This is the authoritative business-to-development handoff identity.

### 2. Developer Definition

Created when Developer Design is frozen as the formal implementation contract.

It should include:

- the full Developer Definition payload
- a reference to the `product_design_revision_id` it was derived from
- developer completion metadata
  - frozen at
  - frozen by
  - optional note

This is the canonical contract used for:

- generation
- implementation verification
- CI/CD enforcement

### 3. PM Signoff

Created when PM signs off on the finalized Developer Design.

It should include:

- the `product_design_revision_id`
- the `developer_definition_id`
- signoff metadata
  - approved at
  - approved by
  - note / rationale
  - optional changes-requested state if approval is withheld

This is the approval record that confirms:

- the implementation contract still matches intended business outcome

## Identity Generation

### Use content hashes, not mutable row ids

The real identity should be derived from canonicalized content.

Examples:

- `product_design_revision_id = sha256(canonical_product_design_revision_json)`
- `developer_definition_id = sha256(canonical_developer_definition_json)`
- `pm_signoff_id = sha256(canonical_pm_signoff_json)`

Human-friendly revision labels may exist as wrappers:

- `v1`
- `v2`
- `rev-2026-04-16-01`

But those are not the real verification identity.

The verification identity is the content hash.

### Canonicalization requirement

If identities are content-derived, then hashing must operate on canonical serialized content.

That means:

- stable key ordering
- no transient fields
- no transport-only fields
- no mutable timestamps inside the hashed payload unless intentionally part of identity

The same frozen content must always hash to the same identity.

## Validation Rules

Validation should be staged.

### Stage 1: identity validation

Before deep verification, the system should confirm:

- the implementation claims a `developer_definition_id`
- that definition exists
- the definition points to the expected `product_design_revision_id`
- if PM signoff is required, a matching `pm_signoff_id` exists for the same pair

If any of those fail, validation should stop early with a clear mismatch result.

### Stage 2: design conformance validation

Only after identities match should the system run deeper checks such as:

- declared capabilities exist
- required governance behavior exists
- required metadata exists
- runtime behavior matches the formalized design
- regression packs pass against the expected contract

This gives a clean validation posture:

- first prove you are validating against the right frozen contract
- then prove the implementation conforms to it

## Repo Storage

These frozen artifacts should be exportable from Studio and stored in the git repo.

Preferred shape:

- `design/product-design-revision.json`
- `design/developer-definition.json`
- `design/pm-signoff.json`

Optionally:

- `design/manifest.json`

The repo-stored artifacts become the source-controlled inputs for:

- code generation
- verification
- CI/CD

This is important because the source of truth should not live only inside Studio.

Studio remains the authoring and review tool.
Git becomes the transport and enforcement surface for delivery workflows.

## ANIP Metadata Exposure

ANIP service metadata should expose references to the frozen design identities.

Suggested fields:

- `anip.design.product_revision_id`
- `anip.design.developer_definition_id`
- `anip.design.pm_signoff_id`
- `anip.design.definition_schema_version`
- `anip.design.generated_at`

This should not dump full PM or developer artifacts into runtime metadata.

It should expose stable references that validators and tooling can compare against repo-tracked design artifacts.

## CI/CD Usage

This design enables a clean enterprise workflow:

1. Studio freezes Product Design
2. Studio exports repo-storable frozen artifacts
3. artifacts are committed to source control
4. generator adapters produce scaffolds from `developer-definition.json`
5. verifier modules check implementation against `developer-definition.json`
6. CI rejects:
   - missing identities
   - mismatched identities
   - unsigned or unapproved definitions when signoff is required
   - implementation drift against the locked definition

The important point is:

- generation and verification are both pinned to the same frozen contract identity

## Relationship to Existing Studio Flow

This does not replace:

- Product Design locking
- Coverage Mapping
- PM review

It strengthens them.

The process becomes:

1. Product Design is frozen into a revision
2. Developer Design is formalized into a definition tied to that revision
3. PM signs off on that definition
4. implementation is generated and verified against that definition
5. runtime metadata reports which frozen identities the implementation claims

This makes the ANIP workflow much harder to drift or hand-wave.

## Rollout Recommendation

Implement in this order:

1. define canonical export shapes for:
   - Product Design revision
   - Developer Definition
   - PM signoff record
2. define canonical serialization rules
3. generate content-derived identities
4. expose those identities in Studio UI
5. export them into repo files
6. include them in ANIP metadata
7. make verifier modules check identity compatibility before deeper validation
8. wire that into the GTM CI/CD pipeline as the reference implementation

## Summary

ANIP should not only lock the process semantically.

It should lock it cryptographically and operationally:

- lock the Product Design revision
- lock the Developer Definition
- sign the PM approval over that definition
- publish those identities in metadata
- validate against those identities in CI/CD

That takes the ANIP workflow from a strong design system to a much stronger delivery and governance system.
