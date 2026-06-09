---
title: GitLab Fronting
description: Governed GitLab fronting showcase for project context, issues, merge-request comments, pipelines, and release notes.
---

# GitLab Fronting

GitLab demonstrates governed delivery-system behavior across projects, issues, merge requests, pipelines, and release notes.

The package is:

```text
gitlab-fronting-showcase@0.2.0
```

## What It Proves

GitLab fronting is similar to GitHub fronting, but it exercises a different provider API and delivery model. The ANIP value is the same: the agent gets governed capability semantics, not broad project API access.

The contract makes these boundaries explicit:

- Project scope is allowlisted.
- Issue creation and MR comments are preview or approval flows.
- Pipeline triggers require declared purpose and approval.
- Protected refs, secret variables, raw repository exports, and direct pipeline bypasses are denied.
- Audit records preserve actor, project, requested outcome, approval posture, and backend binding.

## Capability Surface

| Capability | Intent |
| --- | --- |
| `gitlab.project.search_context` | Search bounded project context. |
| `gitlab.issue.prepare` | Prepare a governed issue preview. |
| `gitlab.mr.comment.prepare` | Prepare a merge-request comment preview. |
| `gitlab.pipeline.trigger.request` | Request a pipeline trigger through approval posture. |
| `gitlab.release_notes.prepare` | Prepare bounded release notes. |

## Backend Boundary

Native GitLab REST/GraphQL APIs remain provider bindings. The ANIP contract owns project scope, allowed operations, preview/approval behavior, denial rules, and audit semantics.

## Artifacts

| Artifact | Path |
| --- | --- |
| Source spec | `docs/examples/gitlab-fronting-showcase/source-spec.md` |
| Package | `examples/showcase/gitlab_fronting/registry-packages/gitlab-fronting-showcase-0.2.0.anip-package.json` |
| Service definition | `examples/showcase/gitlab_fronting/registry-packages/gitlab-fronting-showcase-0.2.0-service-definition.json` |
| Custom bundles | `examples/showcase/gitlab_fronting/custom-code-bundles/` |
| Generated services | `examples/showcase/gitlab_fronting/generated/` |

## Live Validation

Credential file:

```text
/tmp/anip-gitlab.env
```

Mutation is disabled unless `ANIP_GITLAB_ALLOW_MUTATION=true` and the request supplies the required approval grant. The live project should be disposable and scoped to the showcase.

