---
title: Fronting Showcases
description: Realistic governed fronting examples for Jira, GitHub, GitLab, Slack, Linear, Notion, and Superset.
---

# Fronting Showcases

The fronting showcases prove one specific adoption path:

```text
existing system -> governed ANIP capability service -> agent/client
```

They are intentionally not raw MCP replicas and not one-to-one API wrappers. Each showcase starts from a real downstream API surface, then exposes a smaller business-level ANIP contract with clarification, preview, approval, restriction, denial, and audit behavior.

## What They Prove

The showcases demonstrate that ANIP can govern existing tools without requiring teams to create giant skill files that explain how agents should safely use them.

The pattern is the same across every showcase:

1. Source docs define the business-safe capability surface.
2. Studio produces a reviewed Product Design, Developer Design, and Developer Definition.
3. Registry publishes a signed package.
4. The CLI generates an ANIP service from that package.
5. Custom implementation material wires the generated service to the native backend API.
6. Smoke tests prove read, preview, approval, and mutation posture against real or local systems.

The public behavior contract is ANIP. The backend API is implementation material.

## Model Posture

Fronting showcases follow the same model split as the GTM showcase.

Studio authoring can use a stronger model such as `gpt-5.4` to draft and review the project contract. The consuming agent path is intentionally designed for smaller models such as `gpt-5.4-mini`, because the ANIP service carries the governed capability surface, backend boundary, approval behavior, denial posture, and audit semantics.

That is especially important for fronting. A raw Jira, Slack, GitHub, Linear, Notion, GitLab, or Superset API gives the agent many low-level operations. ANIP narrows that into business capabilities such as prepare, preview, request approval, deny, restrict, or audit. The smaller action space reduces the amount of policy the consuming model has to carry in prompt memory.

## Local Setup

Clone the repository before running local generation or smoke commands:

```bash
git clone https://github.com/anip-protocol/anip.git
cd anip
```

The fronting packages and bundles live in the repository:

- [Jira fronting](https://github.com/anip-protocol/anip/tree/main/examples/showcase/jira_fronting)
- [GitHub fronting](https://github.com/anip-protocol/anip/tree/main/examples/showcase/github_fronting)
- [GitLab fronting](https://github.com/anip-protocol/anip/tree/main/examples/showcase/gitlab_fronting)
- [Slack fronting](https://github.com/anip-protocol/anip/tree/main/examples/showcase/slack_fronting)
- [Linear fronting](https://github.com/anip-protocol/anip/tree/main/examples/showcase/linear_fronting)
- [Notion fronting](https://github.com/anip-protocol/anip/tree/main/examples/showcase/notion_fronting)
- [Superset fronting](https://github.com/anip-protocol/anip/tree/main/examples/showcase/superset_fronting)

Registry packages may record immutable implementation-material refs, including
Git refs, but the CLI does not fetch or apply remote custom bundles yet. Use the
local `--custom-code-bundle` path from the cloned repository. Remote
`--custom-code-bundle-ref` is currently validation/provenance metadata, not an
automatic code-download mechanism.

## Detailed Pages

Use these pages when reviewing or publishing individual fronting showcases:

- [Validation Levels](/docs/showcases/fronting-apps/validation-levels)
- [Jira Fronting](/docs/showcases/fronting-apps/jira)
- [GitHub Fronting](/docs/showcases/fronting-apps/github)
- [GitLab Fronting](/docs/showcases/fronting-apps/gitlab)
- [Slack Fronting](/docs/showcases/fronting-apps/slack)
- [Linear Fronting](/docs/showcases/fronting-apps/linear)
- [Notion Fronting](/docs/showcases/fronting-apps/notion)
- [Superset Fronting](/docs/showcases/fronting-apps/superset)

## Validation Levels

A fronting showcase is not one binary claim. There are several separate things to prove, and they should not be collapsed into one word like "works".

| Level | What it proves | What it does not prove |
| --- | --- | --- |
| Contract-ready | Studio produced a reviewed Product Design, Developer Design, Developer Definition, and service definition with governed capabilities, mappings, policies, and outcomes. | No generated service or backend adapter has been exercised yet. |
| Package-ready | The signed Registry package verifies and can be consumed as the behavior authority. | It does not prove a particular language implementation or backend credential set. |
| Generated-service ready | The CLI can generate a service in a target language and generated tests pass against the selected runtime package version. | It does not prove real backend behavior unless a custom adapter is present and tested. |
| Adapter-ready | A reviewed custom bundle implements backend seams for a language without changing the signed contract. | It may still be only unit-tested or mocked. |
| Live-read ready | The adapter has been exercised against real credentials for bounded reads, search, describe, or preview behavior. | It does not prove writes or approval continuation. |
| Approved-mutation ready | A real approval grant and an explicit mutation test flag prove that the service stops before approval and continues only after approval. | It should be scoped to a dedicated test workspace, repository, project, channel, or database. |
| Five-language parity | Python, TypeScript, Go, Java, and C# generate from the same package and pass the same contract-level expectations. | Live backend adapter parity is a separate claim unless each language has equivalent custom adapter smokes. |

This distinction matters for fronting projects because the signed ANIP package and the backend adapter are intentionally separate. A package can be contract-ready and generated-service ready before every language has live adapter parity. A public showcase should state the highest validation level it actually passed.

When a showcase claims five-language live adapter parity, it means all five generated services use compatible runtime package versions, include reviewed backend adapters, and pass the same live-read or approved-mutation checks. When it only claims five-language generation parity, it means the contract and generated substrate are portable, but backend execution may still be implemented in a subset of languages.

## Showcase Matrix

| Showcase | Native backend | Package | Main proof |
| --- | --- | --- | --- |
| [Jira](/docs/showcases/fronting-apps/jira) | Jira REST API | `jira-fronting-showcase@0.2.3` | Issue and workflow operations become preview/approval-governed workflows. |
| [GitHub](/docs/showcases/fronting-apps/github) | GitHub REST/GraphQL APIs | `github-fronting-showcase@0.2.0` | Repository and delivery operations become repo-scoped, approval-aware capabilities. |
| [GitLab](/docs/showcases/fronting-apps/gitlab) | GitLab REST/GraphQL APIs | `gitlab-fronting-showcase@0.2.0` | Project, MR, pipeline, and release-note operations are bounded by project policy. |
| [Slack](/docs/showcases/fronting-apps/slack) | Slack Web API | `slack-fronting-showcase@0.2.0` | Channel reads and sends are controlled through scope, preview, and approval grants. |
| [Linear](/docs/showcases/fronting-apps/linear) | Linear GraphQL API | `linear-fronting-showcase@0.2.0` | Product-work mutations become team-scoped, preview/approval flows. |
| [Notion](/docs/showcases/fronting-apps/notion) | Notion API | `notion-fronting-showcase@0.2.0` | Workspace search, page updates, database queries, and comments are bounded and approval-aware. |
| [Superset](/docs/showcases/fronting-apps/superset) | Superset REST/native API | `superset-fronting-showcase@0.2.0` | Analytics actions avoid raw SQL exposure and use governed semantic/chart/dataset workflows. |

MCP is useful as a comparison surface for some of these systems. It is not the behavior authority for these packages.

## Jira

Jira demonstrates governed work-management behavior.

Capability surface:

- `jira.backlog.search_context`
- `jira.issue.get_context`
- `jira.incident_bug.prepare`
- `jira.story.prepare`
- `jira.subtask.prepare`
- `jira.customer_escalation.comment.prepare`
- `jira.workflow_transition.request`
- `jira.sprint_move.request`
- `jira.assignee_change.request`
- `jira.issue_link.request`
- `jira.release_notes.prepare`

What it proves:

- Searches are project-scoped and bounded.
- Issue creation stops at preview unless an approval grant is present.
- Workflow transitions are approval-gated and can deny unsafe terminal-state bypass.
- Comments, sprint moves, assignment changes, and issue links are explicit governed requests.
- Backend options are named, bounded, and audited; they are not arbitrary JQL or mutation payloads.

Live smoke posture:

- Reads Jira metadata and bounded issue context.
- Exercises preview-only issue preparation.
- Exercises approved mutation when `ANIP_JIRA_ALLOW_MUTATION=true` and a real approval grant is provided.

## GitHub

GitHub demonstrates governed repository and delivery behavior.

Capability surface:

- `github.repo.search_context`
- `github.issue.prepare`
- `github.pr.comment.prepare`
- `github.workflow.dispatch.request`
- `github.release_notes.prepare`

What it proves:

- Repository scope is explicit and allowlisted.
- Issue creation and PR comments stop at preview or approval-required outcomes.
- Workflow dispatch is not a raw button exposed to the agent; it is an approval-gated request.
- Release notes are draft-only unless a separate publication path is explicitly implemented.
- Secret access, unbounded repo export, and workflow bypass are denied.

Live smoke posture:

- Uses a dedicated test repository.
- Performs bounded read/search behavior.
- Exercises issue preparation and approved issue creation when mutation is explicitly enabled.

## GitLab

GitLab demonstrates governed delivery-system behavior for projects, issues, merge requests, and pipelines.

Capability surface:

- `gitlab.project.search_context`
- `gitlab.issue.prepare`
- `gitlab.mr.comment.prepare`
- `gitlab.pipeline.trigger.request`
- `gitlab.release_notes.prepare`

What it proves:

- Project scope is explicit and bounded.
- Issue and MR comment mutations are preview/approval flows.
- Pipeline triggers require declared purpose and approval.
- Protected refs, secret variable access, raw repository export, and direct pipeline bypass are denied.

Live smoke posture:

- Uses a dedicated GitLab test project.
- Performs read/search behavior through the native GitLab API.
- Exercises approved issue creation when `ANIP_GITLAB_ALLOW_MUTATION=true`.

## Slack

Slack demonstrates governed communication behavior. This is the clearest example of why "agent can post to Slack" is not enough as a safety story.

Capability surface:

- `slack.channel.read_context`
- `slack.thread.summarize`
- `slack.message.prepare`
- `slack.incident_update.prepare`
- `slack.announcement.request`

What it proves:

- Channel reads are bounded by channel, actor visibility, and result limits.
- Message sends are not direct by default.
- Prepared messages require approval before posting.
- High-reach announcements can require stronger grants.
- Hidden recipients, private channel exfiltration, unapproved sends, and raw exports are denied.

Live smoke posture:

- Reads from a dedicated test channel.
- Prepares a message preview.
- Posts only when `ANIP_SLACK_ALLOW_SEND=true` and an approval grant is supplied.
- Demonstrates that without approval the service stops before mutation.

## Linear

Linear demonstrates governed product-work behavior on top of the native GraphQL API.

Capability surface:

- `linear.issue.search_context`
- `linear.issue.prepare`
- `linear.comment.prepare`
- `linear.status_transition.request`
- `linear.cycle_move.request`

What it proves:

- Team scope is explicit and bounded.
- Issue creation, comments, status transitions, and cycle moves are preview or approval-gated flows.
- Cross-team moves and restricted workflow states require explicit grants.
- Arbitrary GraphQL execution and raw workspace export are denied.

Live smoke posture:

- Uses a dedicated Linear workspace/team.
- Performs bounded issue/team lookup.
- Exercises approved issue creation when `ANIP_LINEAR_ALLOW_MUTATION=true`.

## Notion

Notion demonstrates governed workspace and knowledge-base behavior.

Capability surface:

- `notion.workspace.search_context`
- `notion.database.query_context`
- `notion.page.create.prepare`
- `notion.page.update.prepare`
- `notion.comment.prepare`

What it proves:

- Workspace, page, and database reads are bounded to shared/actor-visible scope.
- Page creation, page updates, and comments stop at preview or approval.
- Parent overrides, hidden page access, arbitrary block mutation, and workspace-wide export are denied.
- Backend options can expose safe provider controls without becoming a raw Notion payload escape hatch.

Live smoke posture:

- Uses a dedicated Notion test page and database shared with a test integration.
- Performs workspace search and database query.
- Exercises page/comment preparation and approved mutation where the test integration is configured for it.

## Superset

Superset demonstrates governed analytics behavior.

Capability surface:

- `superset.analytics.discover_context`
- `superset.analytics.answer_question`
- `superset.chart.preview.create`
- `superset.chart.publish.request`
- `superset.dashboard.draft.prepare`
- `superset.dataset.draft.prepare`

What it proves:

- Analytics behavior should not expose raw SQL as the agent-facing capability.
- Dataset, chart, dashboard, metric, dimension, and database scope are allowlisted and actor-visible.
- Chart creation defaults to preview.
- Chart publishing, dashboard updates, and dataset drafts require approval.
- Raw exports, unrestricted SQL, protected database access, and dashboard publication bypass are denied.

Local smoke posture:

- Runs a local Superset stack with a seeded database.
- Exercises native Superset REST/native behavior.
- Validates discovery, governed analytics answers, and chart/dataset preview behavior.

## Generate From A Package

Use the same CLI shape for every fronting showcase. Change the package ID, bundle path, and output directory:

```bash
anip generate \
  --package-bundle examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3.anip-package.json \
  --target python \
  --transport http,stdio \
  --custom-code-bundle examples/showcase/jira_fronting/custom-code-bundles/jira_fronting_python \
  --output ./generated/jira-fronting \
  --force
```

The generated service includes:

- HTTP runner.
- stdio runner when requested.
- `anip-service-definition.json`.
- capability handlers.
- policy and approval seams.
- backend integration templates.
- optional custom bundle report.

The generated code is not the source of truth. The signed package and service definition are.

## Generate All Fronting Showcases Locally

From the repository root, this loop regenerates the first-release fronting packages for all supported target languages with their reviewed custom bundles:

```bash
cd packages/go

for app in jira github gitlab slack linear notion superset; do
  package="${app}-fronting-showcase"
  for target in python typescript go java csharp; do
    go run ./cmd/anip generate \
      --package-bundle "../../examples/showcase/${app}_fronting/registry-packages/${package}-0.2.0.anip-package.json" \
      --target "$target" \
      --transport http,stdio \
      --dependency-source registry \
      --custom-code-bundle "../../examples/showcase/${app}_fronting/custom-code-bundles/${app}_fronting_${target}" \
      --output "../../examples/showcase/${app}_fronting/generated/language-parity/${target}" \
      --force
  done
done
```

This is the local-generation equivalent of the Registry consumption path. It proves the packages are portable across the five generated runtimes while keeping provider-specific backend behavior inside custom bundles.

For release work, add bundle digest verification from each app's bundle catalog if one is present:

```bash
--verify-custom-code-bundle-digest sha256:<bundle-digest>
```

## Test Credential Files

Live smokes use local env files under `/tmp`. These files must never be committed:

```text
/tmp/anip-jira.env
/tmp/anip-github.env
/tmp/anip-gitlab.env
/tmp/anip-slack.env
/tmp/anip-linear.env
/tmp/anip-notion.env
/tmp/anip-superset.env
```

Mutation flags are explicit. Examples:

```text
ANIP_JIRA_ALLOW_MUTATION=true
ANIP_SLACK_ALLOW_SEND=true
ANIP_GITHUB_ALLOW_MUTATION=true
ANIP_GITLAB_ALLOW_MUTATION=true
ANIP_LINEAR_ALLOW_MUTATION=true
ANIP_NOTION_ALLOW_MUTATION=true
```

These flags are not approval grants. They only allow the smoke harness to attempt mutation. The ANIP service still requires the proper approval posture for governed write behavior.

## Studio And Registry Flow

For release-quality showcases, the expected flow is:

```text
Studio project
  -> reviewed Developer Definition
  -> signed Registry package
  -> CLI generation
  -> custom implementation material
  -> live smoke
```

Do not treat starter JSON as the release artifact. Starter JSON is useful for creating or recreating project shape. The reviewed Developer Definition and Registry package are the behavior authority.

## What To Inspect

For each showcase, inspect:

- Source spec under `docs/examples/*-fronting-showcase/source-spec.md`.
- Studio project seeded in the local or read-only showcase database.
- Registry package under `examples/showcase/*_fronting/registry-packages/`.
- Generated service under `examples/showcase/*_fronting/generated/`.
- Custom bundle under `examples/showcase/*_fronting/custom-code-bundles/`.
- Live smoke under `examples/showcase/*_fronting/scripts/`.

The important question is always the same:

```text
Does the agent see a governed business capability,
or just a renamed backend operation?
```

The showcase is only successful when the answer is governed capability.
