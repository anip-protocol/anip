# Developer Definition Revisioning

## Problem

Studio currently treats the saved Developer Definition as both:

- a mutable singleton artifact that can be overwritten in place
- the evidence anchor for generation, runtime proof, evaluation, and PM review

That model is confusing. Once generation or proof points at a specific compiled contract signature, the saved contract must behave like an immutable revision, not a mutable "current construct."

## Desired Model

Studio should distinguish three states clearly:

1. Working draft
   - Editable.
   - May diverge from the latest saved revision.
   - Cannot be treated as evidence-bearing delivery truth.

2. Latest saved revision
   - Immutable saved snapshot of the compiled contract.
   - Identified by revision number, artifact id, and contract signature.
   - Generation and verification launch from this revision, not from draft state.

3. Derived evidence
   - Generation runs, local proof, evaluation evidence, and PM review.
   - Must reference the exact saved revision they were created from.

## Immediate Slice

Implement the first coherent slice now:

- Save creates an immutable `developer_definition_revision` artifact.
- The existing `developer_definition` artifact remains as a convenience pointer to the latest saved revision.
- Generation runs record the saved revision artifact id and revision number.
- Studio copy changes from "current saved compiled contract" to "latest saved revision."
- UI shows:
  - working draft status
  - latest saved revision
  - whether the draft is ahead of the latest saved revision

## Rules

- Unsaved draft changes do not invalidate an older saved revision.
- They do make older generation/proof evidence stale with respect to the draft.
- Saving changed draft content creates a new revision.
- Saving unchanged content should not create a duplicate revision.
- Generation and proof should never claim to launch from mutable page state.

## Follow-On Work

- Add revision history browsing on Developer Definition and Verification pages.
- Allow explicit selection of older revisions for inspection/export.
- Allow PM review to target a chosen saved revision when needed.
