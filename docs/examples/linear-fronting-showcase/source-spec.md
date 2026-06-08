# Linear Governed Fronting Showcase Source Specification

This source document models a realistic fronting use case: Linear GraphQL API exists downstream, but agents should only see governed product-work capabilities.

## Purpose

Demonstrate that ANIP can govern issue-tracking behavior without exposing raw workspace tools directly to agents.

The ANIP contract owns the capability semantics. The Linear GraphQL API is the backend for this showcase. Linear MCP may be useful as a comparison point for raw tool exposure, but this package does not use MCP as the ANIP execution interface.

## Service Boundary

- Service ID: `linear-governance-service`
- Service name: Linear Governance Service
- Primary backend: native Linear GraphQL API adapter
- Deployment posture: centralized ANIP fronting service with team allowlists, actor-aware visibility, approval records, and audit.

## Backend Evidence

Native Linear API supply:

- Issue, project, team, label, cycle, and workflow search through GraphQL.
- Issue creation preview mapped to issue create mutation inputs.
- Comment preview mapped to comment create mutation inputs.
- Status transition request mapped to issue update workflow state.
- Cycle/project move request mapped to issue update mutation inputs.

MCP comparison:

- Linear MCP may expose issue search, issue creation, comments, and workflow updates.
- This showcase intentionally does not bind ANIP capabilities to Linear MCP tools. The agent-facing surface remains ANIP capabilities backed by bounded GraphQL operations.

## Governed Capability Surface

| Capability | User intent | Required inputs | Optional governed inputs | Outcome posture |
| --- | --- | --- | --- | --- |
| `linear.issue.search_context` | Search bounded Linear issues, projects, and cycles. | `team_key`, `query` | `project_id`, `cycle_id`, `limit`, `backend_options` | Read-only. Actor-visible summaries only. |
| `linear.issue.prepare` | Prepare an issue with team, labels, and priority. | `team_key`, `title`, `description` | `project_id`, `labels`, `priority`, `backend_options` | Preview-only. Requires approval before creation. |
| `linear.comment.prepare` | Prepare an issue comment. | `issue_id`, `comment_purpose`, `context` | `backend_options` | Preview-only. Requires approval before posting. |
| `linear.status_transition.request` | Request a status transition. | `issue_id`, `target_status`, `reason` | `backend_options` | Approval-gated. Restricted workflow states require explicit grant. |
| `linear.cycle_move.request` | Request moving an issue into a cycle. | `issue_id`, `target_cycle`, `reason` | `backend_options` | Approval-gated. Cross-team moves require explicit grant. |

`backend_options` is limited to bounded provider controls such as selected fields, pagination, or safe include flags. It must not allow arbitrary GraphQL execution, raw workspace export, or hidden team access.

## Policy Semantics

- Searches are bounded by team scope and result limits.
- Missing team, issue, target status, or target container context returns `clarification_required`.
- Issue creation, comments, transitions, and moves are preview or approval-gated flows.
- Private team exfiltration, workflow bypass, unapproved mutation, and raw exports are denied.
- Native GraphQL is the execution binding for this package. MCP can be used as a comparison surface, but is not required for ANIP.

## Why ANIP Helps

Linear GraphQL access provides powerful operations. ANIP exposes the organization-approved ways of using those operations, with explicit clarification, approval, restriction, denial, and audit semantics.
