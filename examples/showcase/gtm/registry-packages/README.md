# GTM Pipeline Q2 Review

ANIP package `gtm-pipeline-q2-review@0.4.6` for local showcase and registry smoke usage.

`0.4.6` is the current package. It is `0.4.5` with its policy rules moved off the
composed capabilities: the runtime runs a composition's steps itself and never
evaluates a binding that names a composed capability, so current validators and
generators refuse such a definition. Rules 0 to 4, 8 and 12 drop
`gtm.at_risk_followup_preparation` and `gtm.at_risk_reassignment_preparation`
(they already name the child preparation capabilities). Rule 5 moves to the two
children, where rule 8 still denies them to `sales_leader`. Rule 9 moves to
`gtm.prepare_followup_tasks`, so `rev_ops_manager` now reaches the approval stop
of `gtm.at_risk_followup_preparation` that 0.4.5 declared but never enforced, and
the same approval stop when invoking the child directly.

It is built from its service definition with `anip package build-local` and the
deterministic development Registry key, and carries `package_execution_signature`,
manifest/lock/service-definition digests, the Registry receipt and Product/Developer
revision lineage:

```bash
cd packages/go
go run ./cmd/anip package build-local \
  --definition ../../examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.6-service-definition.json \
  --package-id gtm-pipeline-q2-review \
  --package-version 0.4.6 \
  --name "GTM Pipeline Q2 Review" \
  --output-dir <scratch-dir> \
  --write-definition \
  --generated-at 2026-11-14T00:00:00Z \
  --project-ref studio:e19bba7f-ce1d-4ca8-bfb2-60fad064f007 \
  --product-revision-ref "e19bba7f-ce1d-4ca8-bfb2-60fad064f007-product-design-revision-1@r1" \
  --developer-revision-ref e19bba7f-ce1d-4ca8-bfb2-60fad064f007-developer-definition-revision-2 \
  --source-package ../../examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.5.anip-package.json
```

`--source-package` carries the agent metadata Studio reviewed for 0.4.5
(consumability, readiness with its finding reviews, the simulation report and
the publication gate) into 0.4.6. None of it depends on the policy bindings, and
build-local cannot derive the simulation or the reviews from the definition.

Copy the four `gtm-pipeline-q2-review-0.4.6*` files from the scratch directory;
the command also writes a generic `README.md` there.

Older package files in this folder are signed history and are kept unchanged.
Packages 0.3.6 to 0.4.5 bind policy rules to composed capabilities, so
`anip validate`/`anip-verify`, `anip generate` and Registry publication refuse
them; use 0.4.6.

## Contents

- Services: 4
- Capabilities: 23
- ANIP spec: `anip/0.24`

## Capability Surface

- `gtm.pipeline_summary`
- `gtm.pipeline_forecast_summary`
- `gtm.stage_bottleneck_summary`
- `gtm.sales_team_performance_summary`
- `gtm.product_pipeline_summary`
- `gtm.stalled_opportunity_review`
- `gtm.account_risk_summary`
- `gtm.prepare_followup_tasks`
- `gtm.prepare_reassignment_plan`
- `gtm.account_enrichment_summary`
- `gtm.lookalike_accounts`
- `gtm.at_risk_account_enrichment_summary`
- `gtm.score_leads`
- `gtm.prioritize_accounts`
- `gtm.route_leads`
- `gtm.draft_outreach_message`
- `gtm.suggest_followup_content`
- `gtm.objection_response_variants`
- `gtm.bottleneck_account_outreach_draft`
- `gtm.prioritized_outreach_draft`
- `gtm.at_risk_followup_preparation`
- `gtm.at_risk_reassignment_preparation`
- `gtm.prioritized_routing_preparation`

## Generate

From a downloaded package bundle:

```bash
go run ./cmd/anip-generate --package-bundle <downloaded-package>.anip-package.json --target python --dependency-source local --output ./generated/gtm-pipeline-q2-review --force
```

From a trusted registry package:

```bash
go run ./cmd/anip-generate --registry-url <registry-url> --package-id gtm-pipeline-q2-review --package-version 0.4.6 --target python --dependency-source registry --output ./generated/gtm-pipeline-q2-review --force
```

## Verify

```bash
go run ./cmd/anip-verify --definition anip-service-definition.json
go run ./cmd/anip-verify --package-bundle <downloaded-package>.anip-package.json
```

## Run Locally

Generated services default to port `9100` unless overridden by the generated runtime configuration.
