# GitLab Governed Fronting Showcase Source Specification

This source document models a realistic fronting use case: GitLab REST/GraphQL APIs exist downstream, but agents should only see governed delivery capabilities.

## Purpose

Demonstrate that ANIP can govern project, merge request, pipeline, and release-note behavior without exposing broad GitLab tools directly to agents.

The ANIP contract owns the capability semantics. Native GitLab APIs are the backend for this showcase. GitLab MCP may be useful as a comparison point for raw tool exposure, but this package does not use MCP as the ANIP execution interface.

## Service Boundary

- Service ID: `gitlab-governance-service`
- Service name: GitLab Governance Service
- Primary backend: native GitLab REST/GraphQL API adapter
- Deployment posture: centralized ANIP fronting service with project allowlists, approval records, and audit.

## Backend Evidence

Native GitLab API supply:

- Project issue and merge request search.
- Issue preview mapped to issue creation fields.
- Merge request comment preview mapped to note APIs.
- Pipeline trigger request mapped to pipeline trigger or job-run APIs.
- Release-note draft generation from issues, merge requests, milestones, or comparison data.

MCP comparison:

- GitLab MCP may expose project search, issue, merge request, pipeline, and release operations.
- This showcase intentionally does not bind ANIP capabilities to GitLab MCP tools. The agent-facing surface remains ANIP capabilities backed by bounded GitLab API operations.

## Governed Capability Surface

| Capability | User intent | Required inputs | Optional governed inputs | Outcome posture |
| --- | --- | --- | --- | --- |
| `gitlab.project.search_context` | Search bounded issues and merge requests in an allowed project. | `project_id`, `query` | `state`, `labels`, `limit`, `backend_options` | Read-only. Returns bounded summaries, not raw export. |
| `gitlab.issue.prepare` | Prepare an issue with labels and assignees. | `project_id`, `title`, `description` | `labels`, `assignees`, `milestone`, `backend_options` | Preview-only. Requires approval before creation. |
| `gitlab.mr.comment.prepare` | Prepare a merge request comment. | `project_id`, `merge_request_iid`, `comment_purpose`, `context` | `backend_options` | Preview-only. Requires approval before posting. |
| `gitlab.pipeline.trigger.request` | Request a pipeline trigger. | `project_id`, `ref`, `pipeline_purpose` | `variables`, `backend_options` | Approval-gated. Protected refs require explicit grant. |
| `gitlab.release_notes.prepare` | Draft release notes from bounded project context. | `project_id`, `range` | `audience`, `include_mrs`, `backend_options` | Draft-only. Does not create or publish a release. |

`backend_options` is limited to bounded provider controls such as selected fields, pagination, or safe include flags. It must not allow arbitrary mutation payloads, secret variable access, protected ref bypass, or unbounded project export.

## Policy Semantics

- Project scope is explicit and allowlisted.
- Missing project, merge request, ref, or release range context returns `clarification_required`.
- Issue creation, merge request comments, and pipeline triggers are preview or approval-gated flows.
- Secret exfiltration, raw repository export, protected-ref bypass, and direct pipeline bypass are denied.
- Native REST/GraphQL is the execution binding for this package. MCP can be used as a comparison surface, but is not required for ANIP.

## Why ANIP Helps

GitLab tool access can mutate delivery systems quickly. ANIP keeps the public surface business-oriented and governed, while raw API or MCP operations remain implementation details.
