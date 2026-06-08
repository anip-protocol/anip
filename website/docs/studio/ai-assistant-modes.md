---
title: AI Assistant Modes
description: How Guided Mode and Autopilot Mode work in Studio and what their trust boundaries are.
---

# AI Assistant Modes

Studio supports AI-assisted authoring, but the assistant is not the authority.

The authority is the reviewed Product Design, Developer Design, Developer Definition, diagnostics, release approval, Registry package, and validation evidence.

## Manual, Guided, And Autopilot

Studio has three authoring modes that write into the same project model.

| Mode | What changes | What stays the same |
| --- | --- | --- |
| Manual Mode | Users edit and review the Studio surfaces directly. | Diagnostics, locked baselines, saved Developer Definitions, packages, and validation evidence remain the gates. |
| Guided Mode | The assistant drafts one section at a time and the user accepts, rejects, or revises. | Accepted content must still satisfy the same coverage and readiness rules. |
| Autopilot Mode | Studio attempts to draft the project from the selected source context. | Autopilot output is still a draft; it cannot bypass evidence, diagnostics, or release approval. |

The target is convergence: given the same reviewed source evidence and decisions, all three modes should be able to reach the same canonical Developer Definition and package semantics.

## Guided Mode

Use Guided Mode when you want control over each section.

Guided Mode is best for:

- Sensitive projects.
- New domains.
- PM-led review.
- Projects with strict approval boundaries.
- Fronting projects where backend behavior must be reviewed carefully.

Guided Mode should:

- Work section by section.
- Show what source material influenced the draft.
- Let the user accept, reject, or revise.
- Keep the user responsible for product decisions.
- Avoid hiding missing assumptions.

Guided Mode trades speed for reviewability.

## Autopilot Mode

Use Autopilot Mode when you want Studio to complete a project draft quickly.

Autopilot Mode is best for:

- Early drafts.
- Low-risk internal prototypes.
- Template-based projects.
- Showcase project regeneration.
- Fast exploration before manual review.

Autopilot Mode should:

- Draft across the project.
- Stop for review.
- Surface assumptions and diagnostics.
- Ask targeted questions when required evidence is incomplete.
- Refuse to invent implementation-grade details that are not present in source evidence.
- Avoid publishing automatically.
- Never bypass release approval.

Autopilot Mode is faster, but it still produces a draft. A human should review before package publication.

## Source Context Requirements

Autopilot is not magic. It works only as well as the source context allows.

For Product Design, source context should describe the business:

- Goals.
- Actors.
- Real situations.
- Expected outcomes.
- Approval, denial, restriction, and clarification behavior.
- Audit expectations.
- Non-goals.

For Developer Design, source context must be more concrete:

- Capability input contracts.
- Input semantic types and resolution behavior.
- Runtime governance and side effects.
- Approval and denial policy.
- Composition, handoff, and service ownership.
- Backend or adapter binding evidence.
- Verification expectations.

If Developer evidence is missing, Autopilot should stop or produce questions. It should not silently fill contract fields with plausible guesses. Users can then switch to Manual Mode or Guided Mode, answer the missing questions, upload structured developer evidence, and continue.

## Recovery From Incomplete Evidence

When Studio detects incomplete evidence:

1. Resolve Product Design first and lock the Product baseline.
2. Add Developer Source Docs or answer the missing Developer Design questions.
3. Use Guided Mode for section-by-section repair if the project needs human decisions.
4. Use Manual Mode for exact deterministic edits where the team already knows the answer.
5. Rerun Autopilot only after the missing evidence is present.

This keeps the assistant useful without turning it into a hidden policy author.

## Model Configuration

Studio authoring is contract design work. Use a strong authoring model for production-quality projects:

```bash
STUDIO_ASSISTANT_PROVIDER=openai
STUDIO_ASSISTANT_MODEL=gpt-5.4
OPENAI_API_KEY=...
```

Generated-service simulators and test harnesses can use a smaller model independently:

```bash
STUDIO_SIMULATOR_PROVIDER=openai
STUDIO_SIMULATOR_MODEL=gpt-5.4-mini
OPENAI_API_KEY=...
```

Do not confuse those settings. The Studio assistant is designing contracts. The simulator is testing already-produced contracts.

## What The Assistant Can Help With

The assistant can help:

- Summarize source documents.
- Draft Product Design sections.
- Suggest scenarios.
- Suggest risks, non-goals, approvals, and denials.
- Draft Developer Design structure.
- Suggest capability IDs.
- Identify missing coverage.
- Explain diagnostics.
- Generate package README drafts.
- Help build templates from completed projects.

## What The Assistant Must Not Own

The assistant must not own:

- Release approval.
- Final Product Design baseline.
- Final Developer Definition authority.
- Registry publication trust.
- Secret handling.
- Backend permission enforcement.
- Runtime policy decisions.

The assistant can draft. The project artifacts must still verify.

## Good Assistant Output

Good assistant output:

- References source material.
- Makes assumptions explicit.
- Uses business language in Product Design.
- Uses precise contract language in Developer Design.
- Suggests governed capabilities, not raw backend tools.
- Identifies approval, denial, restriction, clarification, and audit paths.
- Produces content that diagnostics can validate.

Weak assistant output:

- Hides assumptions.
- Copies raw API operations as capabilities.
- Treats examples as policy.
- Leaves optional business-scope inputs undefined.
- Omits denial or restriction paths.
- Suggests publication without resolving diagnostics.

## Review Rule

Every assistant-produced project should still go through:

1. Product Design review.
2. Developer Design coverage review.
3. Diagnostics resolution.
4. Release lineage approval.
5. Package verification.
6. Scenario validation.

The assistant lowers authoring cost. It does not lower the review bar.
