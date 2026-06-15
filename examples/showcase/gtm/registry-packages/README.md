# GTM Pipeline Q2 Review

ANIP package `gtm-pipeline-q2-review@0.4.4` for local showcase and registry smoke usage.

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
go run ./cmd/anip-generate --registry-url <registry-url> --package-id gtm-pipeline-q2-review --package-version 0.4.4 --target python --dependency-source registry --output ./generated/gtm-pipeline-q2-review --force
```

## Verify

```bash
go run ./cmd/anip-verify --definition anip-service-definition.json
go run ./cmd/anip-verify --package-bundle <downloaded-package>.anip-package.json
```

## Run Locally

Generated services default to port `9100` unless overridden by the generated runtime configuration.
