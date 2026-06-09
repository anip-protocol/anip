# Phase 8 BI Verification Surface

This document records the BI verification layer for the GTM showcase.

The goal is not to reproduce ANIP inside BI.

The goal is:

- ask the agent a governed question
- inspect the bounded ANIP result
- verify the same slice against the modeled data without writing SQL joins

## Tool

The first verification surface is `Metabase`.

It runs in the showcase stack at:

- `http://127.0.0.1:3035`

## Database Connection

Inside Metabase, connect to the showcase Postgres instance with:

- database type: `PostgreSQL`
- host: `gtm-postgres`
- port: `5432`
- database: `anip_gtm`
- user: `anip`
- password: `anip`
- schema: `analytics_gtm`

## Scripted Metabase Setup

The showcase includes a repeatable setup script for the curated saved questions
and dashboard:

```bash
python3 examples/showcase/gtm/scripts/setup_metabase_verification.py
```

Default local admin credentials created by that script:

- email: `admin@anip.local`
- password: `Anip-Demo-Admin-2026!`

## Curated BI Tables

The BI layer uses curated dbt-backed tables that mirror the governed ANIP
surface:

- `bi_gtm__pipeline_stage_summary`
- `bi_gtm__forecast_stage_summary`
- `bi_gtm__stage_bottlenecks`
- `bi_gtm__risk_accounts`
- `bi_gtm__sales_team_performance`
- `bi_gtm__product_pipeline`
- `bi_gtm__account_enrichment`

These tables intentionally align to the same business dimensions the agent and
services already use:

- quarter
- regional office / owner scope
- deal stage
- manager
- product
- account
- forecast mode semantics
- open pipeline, won revenue, risk, and age metrics

## Verification Mapping

Recommended first dashboards or saved questions:

1. `Pipeline Summary`
- source: `bi_gtm__pipeline_stage_summary`
- filters:
  - `engage_quarter`
  - `regional_office`
- group by:
  - `deal_stage`
- measures:
  - `open_pipeline_value`
  - `won_revenue`
  - `open_opportunity_count`
  - `average_open_risk_score`

2. `Forecast Summary`
- source: `bi_gtm__forecast_stage_summary`
- filters:
  - `engage_quarter`
  - `regional_office`
- group by:
  - `deal_stage`
- measures:
  - `open_pipeline_value`
  - `likely_revenue`
  - `best_case_revenue`
  - `risk_adjusted_revenue`

3. `Stage Bottlenecks`
- source: `bi_gtm__stage_bottlenecks`
- filters:
  - `engage_quarter`
  - `regional_office`
  - `manager_name`
  - `product_name`
- group by:
  - `deal_stage`
  - chosen slice dimension
- measures:
  - `open_opportunity_count`
  - `open_pipeline_value`
  - `average_open_days`
  - `average_open_risk_score`

4. `At-Risk Accounts`
- source: `bi_gtm__risk_accounts`
- filters:
  - `engage_quarter`
  - `regional_office`
- sort by:
  - `average_risk_score desc`
  - `open_pipeline_value desc`
- measures:
  - `open_opportunity_count`
  - `open_pipeline_value`
  - `average_risk_score`
  - `max_days_open`

5. `Sales Team Performance`
- source: `bi_gtm__sales_team_performance`
- filters:
  - `engage_quarter`
  - `regional_office`
- group by:
  - `manager_name`
- measures:
  - `open_pipeline_value`
  - `won_revenue`
  - `open_opportunity_count`
  - `average_open_risk_score`

6. `Product Pipeline`
- source: `bi_gtm__product_pipeline`
- filters:
  - `engage_quarter`
  - `regional_office`
  - `product_name`
- measures:
  - `open_pipeline_value`
  - `won_revenue`
  - `open_opportunity_count`
  - `average_open_risk_score`

7. `Account Enrichment`
- source: `bi_gtm__account_enrichment`
- filters:
  - `account_name`
  - `sector`
  - `office_location`
  - `icp_fit`
  - `intent_signal`

## Why This Matters

This makes the showcase easier to trust.

People can now:

- ask the GTM agent a question
- see the governed answer
- open a BI screen over the same marts
- validate the same quarter, region, stage, risk, product, or account slice

That answers the predictable criticism cleanly:

- this is not an agent improvising raw SQL
- and it is not a black-box answer with no evidence path

It is governed execution over a modeled warehouse, with a simple verification
surface on top.
