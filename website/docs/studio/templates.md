---
title: Templates
description: How Studio imports, exports, reviews, and publishes safe starter templates.
---

# Templates

Studio templates lower project creation cost.

They are safe starters for authors, not behavior authority for consumers. The reviewed Developer Definition and published Registry package become the behavior authority later.

## What A Template Is

A template can include:

- Project type.
- ANIP spec version.
- Domain and industry labels.
- Markdown source documents.
- Suggested Product Design structure.
- Suggested Developer Design structure.
- Fronting starter metadata.
- Capability-mapping hints.
- Non-secret connection references.

Templates are useful because many teams repeat the same setup:

- Jira fronting project.
- Slack approved-send project.
- Superset analytics fronting project.
- GTM-style scenario-driven service.
- Internal API fronting project.
- Department-specific approval model.

## What A Template Is Not

A template is not:

- A signed behavior contract.
- A package.
- A release approval.
- A substitute for diagnostics.
- A place to store secrets.
- A place to embed scripts or binary payloads.

If a template imports successfully, that only means the starter is structurally valid. It does not mean the resulting project is ready to publish.

## Importing A Template

When importing a template, Studio should verify:

- Template schema version.
- Target ANIP spec version.
- Studio supports that ANIP spec version.
- Documents are Markdown.
- Size limits are respected.
- Connection refs do not contain token values.
- No scripts, binaries, or install hooks are present.
- Digests match.

Studio should reject templates that target a newer ANIP spec than the Studio build supports.

## Exporting A Template

Template export should be selective.

Users should choose what to include:

- Product Design structure.
- Developer Design structure.
- Capability hints.
- Fronting metadata.
- Source documents.
- Connections as secret refs only.
- Domain labels.
- Industry labels.

Source documents are sensitive. Do not export all source docs blindly.

## Source Document Safety

For the current release posture:

- Template documents should be Markdown only.
- Binary documents should not be exported.
- Source document count and size should be bounded.
- Secrets should be stripped or rejected.
- Internal-only documents should be omitted unless the template stays private.

This matters because templates are meant to be shared.

## Publishing Templates To Registry

Registry stores templates separately from packages.

Use templates when:

- You want others to start similar Studio projects.
- You want a reusable project structure.
- You want safe starter documents and capability hints.

Use packages when:

- You want consumers to generate services from a reviewed behavior contract.
- You want signed package receipts and locks.
- You want immutable service-definition metadata.

Templates help authors start. Packages help consumers trust.

## Template Review Checklist

Before publishing or sharing a template:

- Does it target the current supported ANIP spec?
- Does it avoid secrets and local paths?
- Are source docs safe to share?
- Are documents Markdown-only?
- Are connection refs non-secret?
- Does it avoid claiming release approval?
- Does it explain what users still need to review?
- Does it make project type and domain clear?

## Template Lifecycle

Templates should be versioned.

If the starter structure changes, publish a new template version. Do not silently replace a shared template artifact, especially if teams may have created projects from it.

