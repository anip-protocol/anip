# Superset Governed Fronting Showcase

This showcase demonstrates an ANIP fronting service for Apache Superset. The agent-facing surface is a small set of governed analytics capabilities; native Superset REST APIs are the execution binding. Superset MCP is useful as a comparison surface, but this package does not bind ANIP capabilities to MCP tools.

## Source

- Source spec: `docs/examples/superset-fronting-showcase/source-spec.md`
- CLI starter: `docs/examples/superset-fronting-showcase/anip-fronting-starter.json`
- Package bundle: `registry-packages/superset-fronting-showcase-0.2.0.anip-package.json`

## Generate

```bash
cd packages/go
go run ./cmd/anip fronting scaffold \
  --starter ../../docs/examples/superset-fronting-showcase/anip-fronting-starter.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/superset_fronting/custom-code-bundles/superset_fronting_python \
  --transport http,stdio \
  --output ../../examples/showcase/superset_fronting/generated/studio_superset_fronting \
  --force
```

From the package bundle:

```bash
cd packages/go
go run ./cmd/anip-generate \
  --package-bundle ../../examples/showcase/superset_fronting/registry-packages/superset-fronting-showcase-0.2.0.anip-package.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/superset_fronting/custom-code-bundles/superset_fronting_python \
  --transport http,stdio \
  --port 9180 \
  --output ../../examples/showcase/superset_fronting/generated/studio_superset_fronting \
  --force
```

## Verify

```bash
cd packages/go
go run ./cmd/anip-verify \
  --definition ../../examples/showcase/superset_fronting/registry-packages/superset-fronting-showcase-0.2.0-service-definition.json
```

## Live Superset Tests

Start a local Superset 6.1 stack with sample data:

```bash
examples/showcase/superset_fronting/compose/setup.sh
source /tmp/anip-superset.env
```

The compose stack uses Superset's built-in metadata database for local setup and
loads Superset sample datasets for live API smoke testing.

Generate the service from the package with the language-specific custom bundle,
then run that language's live smoke tests. Available bundles:

- `custom-code-bundles/superset_fronting_python`
- `custom-code-bundles/superset_fronting_typescript`
- `custom-code-bundles/superset_fronting_go`
- `custom-code-bundles/superset_fronting_java`
- `custom-code-bundles/superset_fronting_csharp`

```bash
PYTHONPATH="<repo python packages>:<generated src>" \
  python examples/showcase/superset_fronting/scripts/live_smoke.py
```

When using the bundled compose stack, `/tmp/anip-superset.env` sets
`SUPERSET_BASE_URL` to `http://127.0.0.1:18088`.

The script sets the generated service's `ANIP_API_KEYS_JSON` itself, with one
API key per actor the 0.2.0 policy bindings select. The generated policy refuses
a principal no binding selects, so the old `dev-admin-key`, which carries no
actor claim, no longer works. The smoke checks that:

- `superset.analytics.discover_context` succeeds for `analytics_consumer`,
  `superset.chart.preview.create` for `analytics_creator` and
  `superset.dashboard.draft.prepare` for `analytics_owner`;
- the approval-gated `superset.chart.publish.request` (as `analytics_creator`)
  and `superset.dataset.draft.prepare` (as `dataset_draft_requester`) return
  `approval_required` with an `approval_request_id`; a token without
  `approver:<capability>` scope cannot grant it; an approver issues a one-time
  grant through `POST /anip/approval_grants`; and the requester's second
  invocation, carrying the top-level `approval_grant`, returns a preview with
  `mutation_performed: false`;
- a principal without an actor claim, an actor no binding names, and an actor
  bound only to other capabilities are denied, as are the deny bindings
  (`analytics_consumer` on `superset.analytics.answer_question`,
  `analytics_owner` on `superset.analytics.discover_context`,
  `analytics_creator` on `superset.dataset.draft.prepare`); the clarify binding
  for `analytics_consumer` on `superset.chart.publish.request` returns
  `clarification_required`.

It prints a JSON summary with `"capabilities_tested": 5` and seven refusals.
Every actor the bindings name on `superset.analytics.answer_question` also has a
deny binding there, so no actor can invoke it.

## Design Rule

Do not expose raw Superset MCP tools such as SQL execution or chart generation directly to agents. ANIP capabilities should enforce dataset scope, metric/dimension constraints, preview-only defaults, approval gates, denial rules, and audit.
