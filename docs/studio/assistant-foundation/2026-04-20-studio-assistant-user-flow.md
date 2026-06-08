# Studio Assistant User Flow

Date: 2026-04-20

## Purpose

This document describes the implemented Studio assistant flow from the user's point of view and the deterministic boundary behind it.

The assistant is optional. Studio must remain usable without it.

## Entry Point

The assistant is exposed through one dedicated project page:

- `Project AI Assistant`
- PM lane: draft Product Design from source documents
- Developer lane: draft Developer Design from the locked PM baseline

The lane is explicit in the UI. It tells Studio which bounded assistant capability group to call, but it does not create two separate assistant systems.

## PM Lane

The PM lane expects a readable business source document.

The flow is:

1. User uploads or selects a source document in Source Docs.
2. User opens Project AI Assistant and chooses PM lane.
3. User clicks `AI Draft Product Design`.
4. Studio calls bounded PM assistant actions for the draft sections.
5. Studio renders one draft bundle with section cards.
6. User reviews proposed items.
7. If a section needs clarification, user answers only the selected blocking questions.
8. User clicks `Regenerate Section`.
9. Studio reruns only that section with the answered clarification context.
10. User saves accepted sections.

Saved content becomes normal deterministic Product Design artifacts. The assistant draft bundle remains a proposal artifact, not canonical truth.

## Developer Lane

The Developer lane expects a locked PM baseline.

The flow is:

1. PM Product Design is locked into a baseline.
2. User opens Project AI Assistant and chooses Developer lane.
3. User clicks `AI Draft Developer Design`.
4. Studio calls bounded Developer assistant actions using the locked PM baseline.
5. Studio renders one Developer Design draft bundle with section cards.
6. User reviews proposed service, capability, input, policy, backend, and verification sections.
7. If a section needs clarification, user answers only the selected implementation-grade questions.
8. User clicks `Regenerate Section`.
9. Studio reruns only that section with the answered clarification context.
10. User saves accepted sections as assistant review artifacts for deterministic Developer Definition work.

The developer assistant does not ask the developer to restate PM intent already captured in the baseline.

## Clarification Loop

Clarification questions are not final content.

For clarification sections:

- Studio shows the questions inline in the section card.
- User selects the questions that matter.
- User answers the selected questions.
- Studio persists those answers in the draft bundle.
- `Regenerate Section` is enabled only when every selected question has an answer.
- The assistant receives the original source context plus an explicit `Assistant clarification answers` block.
- Only the affected section is replaced.

After regeneration, Studio shows `Clarification context used for latest regeneration` so the user can see exactly which answers were used.

If regeneration fails, the section enters a failed state with a section-level error and the user can retry regeneration. The failure does not mutate canonical project artifacts.

## Persistence Model

Studio stores assistant draft bundles as PM artifacts:

- `assistant_product_design_draft_bundle`
- `assistant_developer_design_draft_bundle`

These artifacts contain:

- draft bundle metadata
- section proposals
- selected item IDs
- editable clarification answers
- clarification answers used for latest regeneration
- assistant runtime context

They are durable proposal state. They are not generation truth.

Canonical truth is written only when the user accepts and Studio applies validated deterministic operations.

## Read-Only Mode

When Studio starts in read-only mode:

- users can explore the assistant page
- users cannot draft, discard, edit clarification answers, regenerate sections, or save accepted sections
- read-only mode is controlled by startup configuration, not by the UI

This supports hosted demos such as `anip.dev` while preserving local editable workflows.

## Product Rule

The assistant should feel like:

> Upload a business spec, get a usable draft, answer only missing decisions, review the result, and save deterministic project truth.

It should not feel like:

> Ask a chatbot to explain which form fields to fill one by one.
