# GTM Desktop Data Portability

The Docker showcase uses Postgres plus dbt plus Metabase. The desktop showcase
must not require Docker, so the embedded profile uses a local read-only data
artifact.

## First Supported Path

- Prebuild the dbt marts from the Maven CRM source data.
- Store the resulting marts in SQLite or DuckDB.
- Point the embedded Python service runtime at the local artifact.
- Keep all service semantics and ANIP contracts unchanged.

## Boundary

Postgres remains the Docker verification path. The desktop app is not allowed
to require a local Postgres server, dbt runtime, or Metabase instance.

## Required Tables

The desktop artifact must include the data needed by:

- `bi_gtm__account_enrichment`
- `bi_gtm__forecast_stage_summary`
- `bi_gtm__pipeline_stage_summary`
- `bi_gtm__product_pipeline`
- `bi_gtm__risk_accounts`
- `bi_gtm__sales_team_performance`
- `bi_gtm__stage_bottlenecks`
- `dim_gtm__accounts`
- `dim_gtm__products`
- `dim_gtm__sales_agents`
- `fct_gtm__opportunities`
- `mart_gtm__account_enrichment`
- `mart_gtm__pipeline_health`

The dbt marts must be prebuilt during release packaging, not at user runtime.
