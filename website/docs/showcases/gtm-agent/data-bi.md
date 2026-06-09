---
title: Data and BI
description: GTM data, dbt models, Cube, and Metabase verification.
---

# Data and BI

The GTM showcase uses a local Postgres warehouse loaded with the Maven CRM dataset. dbt transforms the raw data into governed GTM marts and BI views. ANIP services and Metabase both read from those modeled views.

## Source data

Raw data lives under:

```text
examples/showcase/gtm/data/raw/maven/
```

The compose stack loads:

- `accounts.csv`
- `products.csv`
- `sales_pipeline.csv`
- `sales_teams.csv`

The initialization SQL lives under:

```text
examples/showcase/gtm/data/init/
```

## dbt models

dbt project path:

```text
examples/showcase/gtm/dbt/
```

Important mart and BI models:

| Model | Purpose |
| --- | --- |
| `fct_gtm__opportunities` | Normalized opportunity fact table. |
| `mart_gtm__pipeline_health` | Pipeline health by quarter, region, and stage. |
| `mart_gtm__account_enrichment` | Account enrichment evidence. |
| `bi_gtm__pipeline_stage_summary` | Metabase-friendly pipeline stage summary. |
| `bi_gtm__forecast_stage_summary` | Forecast modes and contributing stage values. |
| `bi_gtm__stage_bottlenecks` | Bottleneck-oriented open pipeline slices. |
| `bi_gtm__risk_accounts` | At-risk account ranking surface. |
| `bi_gtm__sales_team_performance` | Sales team performance summary. |
| `bi_gtm__product_pipeline` | Product pipeline summary. |
| `bi_gtm__account_enrichment` | BI view over enrichment context. |

## BI correctness rule

Open opportunities use `sales_price` when `close_value` is not populated. Therefore open pipeline calculations must use:

```sql
coalesce(close_value, sales_price)
```

Closed-won revenue can use `close_value`, but aggregates should still coalesce null sums to zero so Metabase does not display missing values where the correct value is zero.

## Metabase verification

Each language compose stack includes Metabase and a setup service that creates curated questions and dashboards.

Default credentials:

| Field | Value |
| --- | --- |
| Email | `admin@anip.local` |
| Password | `Anip-Demo-Admin-2026!` |

Metabase ports:

| Language stack | Metabase |
| --- | --- |
| Python | `http://127.0.0.1:3041/` |
| TypeScript | `http://127.0.0.1:3042/` |
| Go | `http://127.0.0.1:3043/` |
| Java | `http://127.0.0.1:3044/` |
| C# | `http://127.0.0.1:3045/` |

The Metabase setup script is:

```text
examples/showcase/gtm/scripts/setup_metabase_verification.py
```

Rerun it manually:

```bash
GTM_METABASE_URL=http://127.0.0.1:3043 \
  python3 examples/showcase/gtm/scripts/setup_metabase_verification.py
```

## What to verify in BI

Use Metabase to verify:

- Q2 pipeline by region and stage.
- Forecast totals by mode.
- Stage bottleneck rankings.
- At-risk account rankings.
- Sales team performance.
- Product pipeline.
- Account enrichment context.

If Metabase and the ANIP service disagree, check the dbt model first, then the service backend adapter.

