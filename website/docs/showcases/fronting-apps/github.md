---
title: GitHub Fronting
description: Governed GitHub fronting showcase for repository context, issues, PR comments, workflow dispatch, and release notes.
---

# GitHub Fronting

GitHub demonstrates governed repository and delivery behavior on top of native GitHub APIs.

The package is:

```text
github-fronting-showcase@0.2.0
```

## What It Proves

GitHub has powerful write paths: issue creation, PR comments, workflow dispatch, and release publication flows. ANIP narrows those into repo-scoped capabilities with preview, approval, denial, and audit.

The contract is intentionally not a renamed GitHub API catalog:

- Repository access is allowlisted.
- Issue creation is prepared before mutation.
- PR comments are draft/approval flows, not direct writes.
- Workflow dispatch requires declared purpose and approval posture.
- Release notes are bounded drafts unless a separate publishing path is implemented.
- Secrets, raw repository exports, unbounded org search, and workflow bypasses are denied.

## Capability Surface

| Capability | Intent |
| --- | --- |
| `github.repo.search_context` | Search bounded repository context. |
| `github.issue.prepare` | Prepare a governed issue preview. |
| `github.pr.comment.prepare` | Prepare a pull-request comment preview. |
| `github.workflow.dispatch.request` | Request a workflow dispatch through approval posture. |
| `github.release_notes.prepare` | Prepare bounded release notes. |

## Backend Boundary

Native GitHub REST/GraphQL APIs are backend bindings. The ANIP contract owns what an agent is allowed to ask for, when approval is required, what must be denied, and what evidence is audited.

This is the distinction the showcase should make clear: GitHub's backend allows many operations; the ANIP product contract allows only the governed operations.

## Artifacts

| Artifact | Path |
| --- | --- |
| Source spec | `docs/examples/github-fronting-showcase/source-spec.md` |
| Package | `examples/showcase/github_fronting/registry-packages/github-fronting-showcase-0.2.0.anip-package.json` |
| Service definition | `examples/showcase/github_fronting/registry-packages/github-fronting-showcase-0.2.0-service-definition.json` |
| Custom bundles | `examples/showcase/github_fronting/custom-code-bundles/` |
| Generated services | `examples/showcase/github_fronting/generated/` |

## Live Validation

Credential file:

```text
/tmp/anip-github.env
```

Typical test scope:

- dedicated repository such as `anip-protocol/anip-fronting-test`;
- bounded read/search smoke;
- issue preparation smoke;
- approved issue creation smoke only when `ANIP_GITHUB_ALLOW_MUTATION=true` and an approval grant is supplied.

