---
title: Linear Fronting
description: Governed Linear fronting showcase for issue search, issue creation, comments, status transitions, and cycle moves.
---

# Linear Fronting

Linear demonstrates governed product-work behavior on top of Linear's native GraphQL API.

The package is:

```text
linear-fronting-showcase@0.2.0
```

## What It Proves

Linear is useful for demonstrating team-scoped governance because the backend API can see and mutate product work across issues, comments, workflow states, and cycles.

The ANIP contract makes the safe product-work boundary explicit:

- Team scope is allowlisted.
- Issue search is bounded.
- Issue creation and comments are prepared or approval-gated.
- Status transitions and cycle moves require declared intent and approval posture.
- Cross-team moves, restricted states, arbitrary GraphQL, and raw workspace export are denied.

## Capability Surface

| Capability | Intent |
| --- | --- |
| `linear.issue.search_context` | Search bounded issue context. |
| `linear.issue.prepare` | Prepare an issue preview. |
| `linear.comment.prepare` | Prepare a comment preview. |
| `linear.status_transition.request` | Request a governed status transition. |
| `linear.cycle_move.request` | Request a governed cycle move. |

## Backend Boundary

Linear's native API is GraphQL. That does not mean the agent gets GraphQL. The ANIP contract exposes team-scoped product-work capabilities with controlled outcomes.

## Artifacts

| Artifact | Path |
| --- | --- |
| Source spec | `docs/examples/linear-fronting-showcase/source-spec.md` |
| Package | `examples/showcase/linear_fronting/registry-packages/linear-fronting-showcase-0.2.0.anip-package.json` |
| Service definition | `examples/showcase/linear_fronting/registry-packages/linear-fronting-showcase-0.2.0-service-definition.json` |
| Custom bundles | `examples/showcase/linear_fronting/custom-code-bundles/` |
| Generated services | `examples/showcase/linear_fronting/generated/` |

## Live Validation

Credential file:

```text
/tmp/anip-linear.env
```

The live smoke should use a dedicated team or test workspace. Mutation requires `ANIP_LINEAR_ALLOW_MUTATION=true` plus a valid ANIP approval grant.

