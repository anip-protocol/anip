---
title: Page-by-Page Guide
description: What each Studio page is for, who should use it, and what decisions it should make visible.
---

# Page-by-Page Guide

Studio has many pages because it covers the full path from source material to published package. The project dashboard should be the default entry point; deeper pages exist for review, repair, and advanced work.

## Project Dashboard

Audience:

- PM/business.
- Developers.
- Reviewers.

Purpose:

- Show next recommended actions.
- Surface diagnostics.
- Show release/publish status.
- Link to Product Design, Developer Design, Developer Definition, diagrams, packages, and templates.

The dashboard should answer:

- What is blocking this project?
- What needs review?
- Is release lineage approved?
- Is the package local-only or published to Registry?
- Can a template be exported?
- Which workflow should I continue: Guided Mode, Autopilot Mode, manual review, or publication?

## Source Docs

Audience:

- PM/business.
- Developers.

Purpose:

- Load and inspect source material.
- Keep source material separate from generated contract output.
- Preserve the evidence behind Product Design and Developer Design.

Examples:

- Product requirements.
- API notes.
- Security policy.
- Workflow examples.
- Existing MCP/OpenAPI/GraphQL notes.
- Fronting intent.

Source docs can contain sensitive material. Template export must be selective; users should not export all source docs blindly.

Studio separates Product source docs from Developer source docs because they answer different questions. Product source docs should describe intent, scenarios, actors, policy, and outcomes. Developer source docs should describe input contracts, runtime governance, composition, backend bindings, and verification expectations.

If Autopilot has Product docs but no Developer evidence, it should not invent a generation-ready Developer Definition. The user should add Developer source docs, switch to Guided Mode for targeted questions, or complete the missing Developer Design surfaces manually.

## Product Design

Audience:

- PM/business owner.
- Product reviewer.
- Developer reviewer.

Purpose:

- Define business intent.
- Capture scenarios, actors, goals, risks, approvals, denials, restrictions, and non-goals.
- Establish the baseline developers must map to.

This is where scenario-driven execution design starts.

Good Product Design is written in business language. It should be understandable without reading service-definition JSON.

## Product Baseline / Review

Audience:

- PM/business owner.
- Release owner.

Purpose:

- Lock the Product Design baseline.
- Make later changes explicit revisions.
- Prevent the Developer Definition from silently drifting from business intent.

The baseline should be reviewed before package publication.

## Developer Design

Audience:

- Developers.
- Architects.
- Platform/security reviewers.

Purpose:

- Convert Product Design into ANIP capabilities and contract behavior.
- Define inputs, side effects, scopes, resolution, approvals, denials, restrictions, composition, and backend integration metadata.

Developer Design should not be a raw backend operation list. It should describe governed capabilities.

The most important Developer Design pages are the ones that make runtime behavior explicit:

- Capability Formalization.
- Roles & Access.
- Audit & Lineage.
- Scenario Coverage Intent.
- Scenario Execution Semantics.
- Generation Settings.
- Evidence & Verification Plan.

For generation-grade contracts, these pages must be populated from reviewed evidence. Assistant suggestions are useful, but accepted and saved artifacts are what matter.

## Developer Design Map / Coverage

Audience:

- Developers.
- PM/business reviewers.
- Release reviewers.

Purpose:

- Show how Product Design maps into Developer Design.
- Identify uncovered Product Design items.
- Make orphan technical sections visible.

Coverage is critical because it proves product intent did not disappear before generation.

## Diagrams

Audience:

- PM/business.
- Developers.
- Reviewers.

Purpose:

- Visualize project structure, capability flow, scenario flow, or fronting topology.
- Help reviewers understand design without reading every field.

Diagrams are explanatory artifacts. They do not replace the Developer Definition.

## Developer Definition

Audience:

- Developers.
- Generator users.
- Reviewers.

Purpose:

- Show the canonical ANIP service definition.
- Provide the machine-readable contract used by generators and verifiers.
- Expose contract signature and generated handoff material.

This is the authority exported by Studio before package publication.

## Registry Publication

Audience:

- Developers.
- Release owner.
- Registry/package owner.

Purpose:

- Show local package state.
- Show publication readiness.
- Show PM/release approval state.
- Publish the approved package to Registry.
- Display package digest, definition digest, receipt, signature, and lineage.

Publication is a release action. If implementation material is added later, publish a new package revision instead of mutating existing metadata.

## Templates

Audience:

- PM/business.
- Developers.
- Platform teams.

Purpose:

- Import starter templates.
- Export safe starter templates from completed projects.
- Decide which source documents and sections are safe to share.

Templates help authors start projects. They are not behavior authority.

## Fronting Setup

Audience:

- Developers.
- Integration owners.
- Security/platform reviewers.

Purpose:

- Capture backend integration posture.
- Record backend operation evidence.
- Keep raw backend API/MCP details out of the public behavior contract.
- Define governed capabilities in front of broader systems.

Fronting setup should support realistic implementation without making the agent-facing contract a raw tool catalog.

## Assistant Page

Audience:

- PM/business.
- Developers.

Purpose:

- Run Guided Mode or Autopilot Mode.
- Draft sections from source material.
- Repair incomplete designs.
- Ask for structured suggestions.

The assistant accelerates authoring. It does not replace review, diagnostics, release approval, or package verification.

Guided Mode is best when the team wants to review and accept one section at a time. Autopilot Mode is best when the source evidence is already complete enough for Studio to draft the project end to end. Manual Mode remains the deterministic fallback when users need to edit the canonical surfaces directly.

The expected outcome is the same in all modes: a locked Product baseline, saved Developer Definition, clean readiness diagnostics, package material, and validation evidence.
