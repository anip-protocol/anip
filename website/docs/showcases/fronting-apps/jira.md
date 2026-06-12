---
title: Jira Fronting
description: Governed Jira fronting showcase for issue, workflow, sprint, assignment, link, and release-note operations.
---

# Jira Fronting

Jira demonstrates how broad issue-tracker APIs become a smaller governed ANIP capability surface.

The package is:

```text
jira-fronting-showcase@0.2.3
```

## What It Proves

Jira is a strong fronting example because the raw backend can search issues, create work, transition workflow state, move work between sprints, change assignees, comment, link issues, and produce release notes. Giving an agent raw API access would push too much safety logic into prompts or client-side recipes.

The ANIP contract makes those actions explicit:

- Reads are project-scoped and bounded.
- New work is prepared as a preview before mutation.
- Workflow, sprint, assignment, link, and escalation operations are approval-aware requests.
- Unsafe terminal-state bypasses and arbitrary backend payloads are denied.
- Audit records capture actor, project scope, normalized inputs, backend intent, and outcome.

## Capability Surface

| Capability | Intent |
| --- | --- |
| `jira.backlog.search_context` | Search bounded backlog context. |
| `jira.issue.get_context` | Retrieve bounded issue context. |
| `jira.incident_bug.prepare` | Prepare an incident/bug issue preview. |
| `jira.story.prepare` | Prepare a story issue preview. |
| `jira.subtask.prepare` | Prepare a subtask preview. |
| `jira.customer_escalation.comment.prepare` | Prepare a governed escalation comment. |
| `jira.workflow_transition.request` | Request a workflow transition with approval posture. |
| `jira.sprint_move.request` | Request a sprint move. |
| `jira.assignee_change.request` | Request an assignee change. |
| `jira.issue_link.request` | Request a governed issue link. |
| `jira.release_notes.prepare` | Prepare bounded release notes. |

## Backend Boundary

The agent sees Jira business capabilities, not raw Jira REST operations or arbitrary JQL execution.

Native Jira REST remains an implementation detail inside custom bundles. The contract owns project scope, allowed backend options, approval posture, denial behavior, and audit semantics.

## Artifacts

| Artifact | Path |
| --- | --- |
| Source spec | `docs/examples/jira-fronting-showcase/source-spec.md` |
| Package | `examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3.anip-package.json` |
| Service definition | `examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3-service-definition.json` |
| Custom bundles | `examples/showcase/jira_fronting/custom-code-bundles/` |
| Generated services | `examples/showcase/jira_fronting/generated/` |

## Live Validation

Credential file:

```text
/tmp/anip-jira.env
```

Mutation is disabled unless both conditions are true:

- `ANIP_JIRA_ALLOW_MUTATION=true`
- the invoke request includes the required ANIP approval grant.

The important behavior is not "agent can create Jira issue". The important behavior is that the service can prepare the issue, stop at the approval boundary, and only continue when the host supplies the governed approval continuation.
