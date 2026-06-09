# Jira Governed Fronting Showcase

This example shows the intended ANIP pattern for fronting broad Jira REST access:
Jira API operations are downstream implementation details; agents invoke governed ANIP capabilities.

## Build artifacts

```bash
cd packages/go
go run ./cmd/anip-generate \
  --package-bundle ../../examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3.anip-package.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/jira_fronting/custom-code-bundles/jira_fronting_python \
  --transport http,stdio \
  --port 9140 \
  --output ../../examples/showcase/jira_fronting/generated/studio_jira_fronting \
  --force
```

Generate directly from the reviewed fronting starter:

```bash
cd packages/go
go run ./cmd/anip fronting scaffold \
  --starter ../../docs/examples/jira-fronting-showcase/anip-fronting-starter.json \
  --target python \
  --dependency-source local \
  --transport http,stdio \
  --output ../../examples/showcase/jira_fronting/generated/studio_jira_fronting \
  --force
```

Verify the local service definition:

```bash
cd packages/go
go run ./cmd/anip-verify \
  --package-bundle ../../examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3.anip-package.json
```

## What to inspect

- `registry-packages/jira-fronting-showcase-0.2.3.anip-package.json`: signed behavior contract with `integration_fronting` mappings.
- `generated/studio_jira_fronting/integration-fronting/adapter-bindings.json`: capability-to-backend binding pack.
- `generated/studio_jira_fronting/integration-fronting/backend-selection.example.json`: deployment-time backend selection template.
- `generated/studio_jira_fronting/integration-fronting/conformance.json`: static check that raw backend operations are governed.

## Live Jira tests

The generated Python adapter includes live Jira REST behavior for:

- `jira.backlog.search_context`: executes a bounded project-scoped search.
- `jira.issue.get_context`: retrieves bounded issue context.
- `jira.incident_bug.prepare`, `jira.story.prepare`, and `jira.subtask.prepare`: return issue creation previews without creating issues.
- `jira.customer_escalation.comment.prepare`, `jira.workflow_transition.request`, `jira.sprint_move.request`, `jira.assignee_change.request`, and `jira.issue_link.request`: return approval-gated previews without mutating Jira.
- `jira.release_notes.prepare`: prepares bounded release-note draft context without publishing.
- Optional Jira issue creation: disabled by default; requires `ANIP_JIRA_ALLOW_MUTATION=true` plus a real ANIP approval continuation grant supplied as the top-level `approval_grant` invoke field.

It uses these environment variables:

```bash
export JIRA_BASE_URL="https://anip-dev.atlassian.net"
export JIRA_EMAIL="your-atlassian-email@example.com"
export JIRA_API_TOKEN="your-token"
PYTHONPATH=examples/showcase/jira_fronting/generated/studio_jira_fronting/src \
  ./.venv/bin/pytest examples/showcase/jira_fronting/generated/studio_jira_fronting/tests/test_live_jira_backlog_search.py
```

If the variables are not set, the live test is skipped and the offline smoke test still uses the generated stub behavior.

Run the mutation smoke test only against a disposable Jira project:

```bash
export ANIP_JIRA_ALLOW_MUTATION=true
PYTHONPATH=examples/showcase/jira_fronting/generated/studio_jira_fronting/src \
  ./.venv/bin/pytest examples/showcase/jira_fronting/generated/studio_jira_fronting/tests/test_live_jira_backlog_search.py \
  -k bug_create
```

The mutation test first invokes `jira.incident_bug.prepare` with `request_execution_approval=true`,
receives an ANIP `approval_required` failure with an approval request ID, issues a
one-time grant through `/anip/approval_grants`, then resubmits the same parameters
with the top-level `approval_grant`. The Jira adapter only creates the issue after
the ANIP runtime validates and reserves that grant.

## Design point

The backend is Jira REST for this showcase. The ANIP contract owns project scope, approval posture, bounded `backend_options`, denial rules, and audit.
