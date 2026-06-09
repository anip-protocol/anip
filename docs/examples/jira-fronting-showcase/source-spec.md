# Jira Governed Fronting Showcase Source Specification

This source document models a realistic fronting use case: Jira REST APIs exist downstream, but agents should only see curated governed Jira workflows.

## Purpose

Demonstrate that ANIP governs Jira behavior without forcing every agent team to encode Jira etiquette in prompts, skills, or MCP tool-selection instructions.

The stable ANIP contract describes organization-approved Jira workflows. Jira REST is the backend for this showcase. Atlassian MCP may be useful as a comparison point for raw tool exposure, but this package does not use MCP as the ANIP execution interface.

## Service Boundary

- Service ID: `jira-governance-service`
- Service name: Jira Governance Service
- Primary backend: native Jira REST API adapter
- Deployment posture: centralized ANIP fronting service with enterprise SSO, scoped downstream credentials, durable audit, and approval records.

## Backend Evidence

Native Jira API supply:

- Issue search through bounded JQL or API search.
- Issue detail retrieval, comments, changelog, transitions, links, sprints, and metadata discovery.
- Issue create preview mapped to Jira issue-create fields.
- Comment preview mapped to issue comment APIs.
- Workflow transition, sprint move, assignee change, issue link, and subtask request previews mapped to Jira metadata and mutation APIs.

MCP comparison:

- Atlassian MCP may expose search, issue creation, comments, transitions, and related Jira operations.
- This showcase intentionally does not bind ANIP capabilities to Atlassian MCP tools. The agent-facing surface remains ANIP capabilities backed by bounded Jira REST operations.

## Governed Capability Surface

| Capability | User intent | Required inputs | Optional governed inputs | Outcome posture |
| --- | --- | --- | --- | --- |
| `jira.backlog.search_context` | Find bounded work context in an allowed Jira project. | `project_key`, `query` | `issue_type`, `status`, `limit`, `backend_options` | Read-only. Returns bounded issue summaries, not raw export. |
| `jira.issue.get_context` | Inspect one issue with bounded comments/history. | `issue_key` | `include_comments`, `include_changelog`, `backend_options` | Read-only. Actor-visible fields only. |
| `jira.incident_bug.prepare` | Prepare a bug from incident or defect context. | `project_key`, `summary`, `description`, `severity` | `labels`, `components`, `backend_options` | Preview-only. Requires approval before creation. |
| `jira.story.prepare` | Prepare a story with acceptance criteria. | `project_key`, `summary`, `acceptance_criteria` | `priority`, `labels`, `backend_options` | Preview-only. Requires approval before creation. |
| `jira.subtask.prepare` | Prepare a subtask under an existing parent issue. | `parent_issue_key`, `summary`, `description` | `assignee`, `backend_options` | Preview-only. Requires approval before creation. |
| `jira.customer_escalation.comment.prepare` | Prepare a customer-safe escalation or incident comment. | `issue_key`, `comment_purpose`, `context` | `visibility`, `backend_options` | Preview-only. Requires approval before posting. |
| `jira.workflow_transition.request` | Request a status transition for an existing issue. | `issue_key`, `target_status`, `reason` | `comment`, `backend_options` | Approval-gated. Denies workflow bypass and restricted terminal transitions without explicit grant. |
| `jira.sprint_move.request` | Request moving issue(s) into a sprint or backlog. | `issue_keys`, `target_sprint`, `reason` | `backend_options` | Approval-gated. Requires actor-visible board/sprint scope. |
| `jira.assignee_change.request` | Request reassignment with a business reason. | `issue_key`, `assignee_ref`, `reason` | `backend_options` | Approval-gated. Requires assignee resolution and audit. |
| `jira.issue_link.request` | Request linking two issues with a declared relationship. | `source_issue_key`, `target_issue_key`, `link_type`, `reason` | `backend_options` | Approval-gated. Denies hidden cross-project linking. |
| `jira.release_notes.prepare` | Prepare release notes from bounded Jira issues. | `project_key`, `release_ref`, `issue_query` | `audience`, `limit`, `backend_options` | Draft-only. Does not publish or mutate Jira. |

`backend_options` is a named governed escape hatch for bounded provider-specific controls such as selected fields, expand clauses, pagination, or safe include flags. It must be size-limited, audited, and never allow arbitrary JQL, raw payload injection, hidden project access, or bypass of declared scope.

## Policy Semantics

- Searches are project-scoped, result-limited, and actor-visible.
- Issue, project, sprint, assignee, release, and link references are backend-resolved; missing or ambiguous references return `clarification_required`.
- Issue creation, comment posting, transitions, sprint moves, assignee changes, and issue links stop at preview or `approval_required`.
- Raw JQL export, unrestricted issue dumps, workflow bypass, private project exfiltration, and unapproved mutation are denied.
- Jira REST is the execution binding for this package. MCP can be used as a comparison surface, but is not required for ANIP.

## Why ANIP Helps

Without ANIP, teams usually write skill files explaining when to search, when to create, when to transition, how to ask for missing project context, and when to request approval. This service moves those rules into a service-side governed contract that can be reviewed, packaged, verified, audited, and reused across clients.
