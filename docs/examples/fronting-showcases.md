# Governed Fronting Showcases

These examples demonstrate ANIP in front of existing systems. Native APIs, GraphQL APIs, and MCP tools are treated as backend implementation supply. The agent-facing surface is a smaller governed capability contract with explicit clarification, approval, restriction, denial, and audit semantics.

## Available Starters

| Showcase | Starter | Primary backend posture | Purpose |
| --- | --- | --- | --- |
| Jira | `docs/examples/jira-fronting-showcase/anip-fronting-starter.json` | Jira REST native API | Govern backlog/issue context, bug/story/subtask preparation, comments, transitions, sprint moves, assignment, issue links, and release notes. |
| GitHub | `docs/examples/github-fronting-showcase/anip-fronting-starter.json` | GitHub REST/GraphQL native API | Govern repository search, issue preparation, PR comments, workflow dispatch, and release notes. |
| Slack | `docs/examples/slack-fronting-showcase/anip-fronting-starter.json` | Slack Web API native API | Govern channel reads, thread summaries, message drafts, incident updates, and announcements. |
| Notion | `docs/examples/notion-fronting-showcase/anip-fronting-starter.json` | Notion native API | Govern workspace search, page updates, database queries, and comments. |
| Linear | `docs/examples/linear-fronting-showcase/anip-fronting-starter.json` | Linear GraphQL native API | Govern issue search, issue preparation, comments, transitions, and cycle moves. |
| Slite | `docs/examples/slite-fronting-showcase/anip-fronting-starter.json` | Slite API first, Slite MCP optional | Govern knowledge search, note drafts, review-state changes, and comment preparation. |
| GitLab | `docs/examples/gitlab-fronting-showcase/anip-fronting-starter.json` | GitLab REST/GraphQL native API | Govern project search, issue/MR preparation, pipeline requests, and release notes. |
| Superset | `docs/examples/superset-fronting-showcase/anip-fronting-starter.json` | Superset REST/native API | Govern analytics discovery, governed questions, chart previews, publish requests, and dashboard/dataset drafts. |

## Generate A Fronting Service

```bash
cd packages/go
go run ./cmd/anip fronting scaffold \
  --starter ../../docs/examples/jira-fronting-showcase/anip-fronting-starter.json \
  --target python \
  --dependency-source local \
  --transport http,stdio \
  --output /tmp/anip-jira-fronting \
  --force
```

The generated project contains:

- `anip-service-definition.json` as the generated ANIP behavior contract.
- `integration-fronting/adapter-bindings.json` mapping governed capabilities to backend operation refs.
- `integration-fronting/backend-profile.example.json` for implementation-time backend posture.
- `integration-fronting/backend-selection.example.json` for deployment-time backend selection.
- `integration-fronting/backend-templates/*` with local implementation seams for REST, GraphQL, MCP, and related adapters.
- HTTP and stdio runners when `--transport http,stdio` is used.

## Generate From A Published Package

After the Studio project has produced and published `jira-fronting-showcase@0.2.0`, generate from the trusted Registry package:

```bash
cd packages/go
go run ./cmd/anip-generate \
  --registry-url http://127.0.0.1:8200/registry-api/v1 \
  --package-id jira-fronting-showcase \
  --package-version 0.2.0 \
  --target python \
  --dependency-source registry \
  --transport http,stdio \
  --output /tmp/anip-jira-fronting-python \
  --force
```

The Jira showcase also includes an optional reviewed Python implementation bundle:

```bash
cd packages/go
go run ./cmd/anip-generate \
  --registry-url http://127.0.0.1:8200/registry-api/v1 \
  --package-id jira-fronting-showcase \
  --package-version 0.2.0 \
  --target python \
  --dependency-source registry \
  --transport http,stdio \
  --custom-code-bundle ../../examples/showcase/jira_fronting/custom-code-bundles/jira_fronting_python \
  --output /tmp/anip-jira-fronting-python \
  --force
```

Set `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN` to enable live Jira REST calls. The bundle performs bounded read and metadata calls. It returns governed previews for write-adjacent capabilities and does not mutate Jira.

The live smoke script exercises one bounded read and one write-adjacent preview:

```bash
set -a
source /tmp/anip-jira.env
set +a
PYTHONPATH="../../packages/python/anip-core/src:../../packages/python/anip-service/src:../../packages/python/anip-fastapi/src:/tmp/anip-jira-fronting-python/src" \
  python3 ../../examples/showcase/jira_fronting/scripts/live_smoke.py
```

## Design Rule

Do not expose raw backend tools such as `execute_sql`, `create_issue`, `chat.postMessage`, or `workflow_dispatch` directly as the product interface. Use ANIP to expose the organization-approved way of using those tools.
