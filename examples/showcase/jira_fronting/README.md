# Jira Governed Fronting Showcase

This example shows the intended ANIP pattern for fronting broad Jira REST access:
Jira API operations are downstream implementation details; agents invoke governed ANIP capabilities.

## Build artifacts

```bash
cd packages/go
go run ./cmd/anip generate \
  --definition ../../examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3-service-definition.json \
  --package-name jira_governed_fronting_showcase \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/jira_fronting/custom-code-bundles/jira_fronting_python \
  --transport http,stdio \
  --port 9140 \
  --output ../../examples/showcase/jira_fronting/generated/studio_jira_fronting \
  --force
```

The command reads the package's signed service definition. Generating from the
`.anip-package.json` bundle itself is refused (`resolved package is missing
package_execution_signature`): the 0.2.3 package predates that field. The
checked-in `agent-consumption/` files were written by the generator's
`BuildAgentConsumptionKit` from the bundle's `agent_consumability` and
`agent_consumption_readiness` metadata, which a bare definition does not carry.

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
  --definition ../../examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3-service-definition.json
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
- `jira.customer_escalation.comment.prepare`: returns a comment preview without posting it.
- `jira.workflow_transition.request`, `jira.sprint_move.request`, `jira.assignee_change.request`, and `jira.issue_link.request`: approval-gated. They return `approval_required` until the runtime validates an approval grant, then a preview; they never mutate Jira.
- `jira.release_notes.prepare`: prepares bounded release-note draft context without publishing.

The Python bundle never mutates Jira: write-adjacent capabilities return governed
previews that a host application routes through its approval and execution layer.

It uses these environment variables:

```bash
export JIRA_BASE_URL="https://anip-dev.atlassian.net"
export JIRA_EMAIL="your-atlassian-email@example.com"
export JIRA_API_TOKEN="your-token"
export ANIP_JIRA_GENERATED_APP_MODULE=jira_governed_fronting_showcase.app
PYTHONPATH=examples/showcase/jira_fronting/generated/studio_jira_fronting/src \
  python examples/showcase/jira_fronting/scripts/live_smoke.py
```

The script sets the generated service's `ANIP_API_KEYS_JSON` itself, with one
API key per actor the 0.2.3 policy bindings select. The generated policy refuses
a principal no binding selects, so the old `dev-admin-key`, which carries no
actor claim, no longer works. The smoke checks that:

- reads and previews succeed for `jira_release_preparer`, and
  `jira.release_notes.prepare` for `jira_triage_operator`;
- each approval-gated capability returns `approval_required` with an
  `approval_request_id`; a token without `approver:<capability>` scope cannot
  grant it; `jira_change_approver` issues a one-time grant through
  `POST /anip/approval_grants`; and the requester's second invocation, carrying
  the top-level `approval_grant`, returns a preview with
  `mutation_performed: false`;
- a principal without an actor claim and an actor no binding names are denied,
  as are the deny bindings (`jira_triage_operator` on
  `jira.assignee_change.request`, `jira_release_preparer` on
  `jira.release_notes.prepare`); the clarify binding on `jira.issue.get_context`
  returns `clarification_required`.

It prints a JSON summary with `"capabilities_tested": 11` and five refusals.

Without credentials, the generated `tests/` (service smoke and bundle adapter
tests) run offline.

## Design point

The backend is Jira REST for this showcase. The ANIP contract owns project scope, approval posture, bounded `backend_options`, denial rules, and audit.
