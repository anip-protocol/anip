---
title: Project Types
description: When to use empty, template-based, fronting, and showcase Studio projects.
---

# Project Types

Studio supports different project starting points because not every ANIP service begins the same way.

The project type should reduce setup work without changing the core rule: the reviewed Developer Definition and Registry package become the behavior authority.

## Empty Project

Use an empty project when:

- You are designing a new ANIP service from scratch.
- You do not have a suitable starter template.
- You want full control over source documents and design structure.
- The domain is new or sensitive enough that a generic template would create false confidence.

An empty project usually requires more Product Design work:

1. Load source documents.
2. Define actors and scenarios.
3. Draft Product Design.
4. Lock baseline.
5. Build Developer Design.
6. Generate Developer Definition.
7. Publish package.

## Template-Based Project

Use a template when:

- You want a safe starting structure.
- You are working in a common domain.
- You want sample source documents, suggested sections, or capability shape.
- You want to reduce blank-page work without treating the template as authority.

Templates can include:

- Project type.
- ANIP spec version.
- Domain and industry labels.
- Markdown source documents.
- Suggested Product Design structure.
- Suggested Developer Design structure.
- Fronting starter metadata.

Templates are starters, not approvals. A project created from a template still needs review, diagnostics, release lineage, package publication, and validation.

## Fronting Project

Use a fronting project when:

- A backend system already exists.
- The agent should not see raw API/MCP/tool access.
- You want a smaller governed capability surface in front of a broader system.

Examples:

- Jira issue/workflow fronting.
- Slack channel read and approved-send fronting.
- GitHub/GitLab project operations.
- Linear issue workflow.
- Notion page/database actions.
- Superset analytics and chart workflows.
- Internal REST or GraphQL APIs.
- Existing MCP servers.

The fronting project should capture backend evidence, but the ANIP capability should remain the product contract.

## Showcase Project

Use showcase projects to learn and inspect:

- GTM Agent.
- Jira fronting.
- GitHub fronting.
- GitLab fronting.
- Slack fronting.
- Linear fronting.
- Notion fronting.
- Superset fronting.

In read-only hosted mode, showcase projects should be inspectable but not mutable. They are examples of good project structure, package publication, and generated-service handoff.

## Which One Should I Start With?

| Goal | Start with |
| --- | --- |
| Learn Studio quickly | Showcase project |
| Create a new domain service | Empty project or template |
| Put ANIP in front of a SaaS/API/backend | Fronting project or fronting template |
| Reuse an organizational pattern | Template-based project |
| Publish public package | Any project type, after review and release approval |

## What Should Not Change By Project Type

Every project type should still produce:

- Reviewed Product Design.
- Developer Design coverage.
- Strict `anip/0.24` Developer Definition.
- Package-ready metadata.
- Release lineage.
- Validation evidence.

Project type changes the starting path, not the trust model.

