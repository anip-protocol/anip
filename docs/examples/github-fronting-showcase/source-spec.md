# GitHub Governed Fronting Showcase Source Specification

This source document models a realistic fronting use case: GitHub REST/GraphQL APIs exist downstream, but agents should only see governed repository capabilities.

## Purpose

Demonstrate that ANIP can govern repository and delivery operations without exposing broad code-hosting tools directly to agents.

The ANIP contract owns the capability semantics. Native GitHub APIs are the backend because they are durable service integration surfaces. GitHub MCP may be useful as a comparison point for raw tool exposure, but this package does not use MCP as the ANIP execution interface.

## Service Boundary

- Service ID: `github-governance-service`
- Service name: GitHub Governance Service
- Primary backend: native GitHub REST/GraphQL API adapter
- Deployment posture: centralized ANIP fronting service with enterprise identity, repo allowlists, approval records, and audit.

## Backend Evidence

Native GitHub API supply:

- Repository issue and pull request search through REST or GraphQL.
- Issue preview mapped to issue creation fields.
- Pull request comment preview mapped to review/comment APIs.
- Workflow dispatch request mapped to GitHub Actions workflow dispatch.
- Release-note draft generation from issue, pull request, milestone, or comparison data.

MCP comparison:

- GitHub MCP may expose repository search, issue, pull request, workflow, and release operations.
- This showcase intentionally does not bind ANIP capabilities to GitHub MCP tools. The agent-facing surface remains ANIP capabilities backed by bounded GitHub API operations.

## Governed Capability Surface

| Capability | User intent | Required inputs | Optional governed inputs | Outcome posture |
| --- | --- | --- | --- | --- |
| `github.repo.search_context` | Search bounded issue and pull request context in an allowed repository. | `owner`, `repo`, `query` | `state`, `labels`, `limit`, `backend_options` | Read-only. Returns bounded summaries, not raw repository export. |
| `github.issue.prepare` | Prepare an issue with labels and assignees. | `owner`, `repo`, `title`, `body` | `labels`, `assignees`, `milestone`, `backend_options` | Preview-only. Requires approval before creation. |
| `github.pr.comment.prepare` | Prepare a pull request comment from review or release context. | `owner`, `repo`, `pull_number`, `comment_purpose`, `context` | `visibility`, `backend_options` | Preview-only. Requires approval before posting. |
| `github.workflow.dispatch.request` | Request a GitHub Actions workflow run. | `owner`, `repo`, `workflow_id`, `ref` | `inputs`, `backend_options` | Approval-gated. Restricted workflows require explicit grant. |
| `github.release_notes.prepare` | Draft release notes from bounded repository context. | `owner`, `repo`, `range` | `audience`, `include_prs`, `backend_options` | Draft-only. Does not create or publish a release. |

`backend_options` is allowed only for bounded provider features such as selected fields, GraphQL pagination, or expand-like metadata. It must not allow arbitrary mutation payloads, secret access, workflow bypass, or unbounded repository export.

## Policy Semantics

- Repository scope is explicit and allowlisted.
- Missing repo, pull request, workflow, or range context returns `clarification_required`.
- Issue creation, PR comments, workflow dispatches, and release publication are not executed without approval.
- Secret exfiltration, raw file export, unbounded codebase dumps, and direct workflow bypass are denied.
- Native REST/GraphQL is the execution binding for this package. MCP can be used as a comparison surface, but is not required for ANIP.

## Why ANIP Helps

GitHub MCP gives agents access to powerful tools. ANIP turns that access into reviewed capabilities with explicit approvals, denial rules, clarification behavior, and audit records.
