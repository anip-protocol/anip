# dbt

This directory contains the Phase 1 dbt project for the GTM showcase.

The project is responsible for:

- cleaning the raw Maven CRM tables loaded into `raw_gtm`
- fixing small source inconsistencies explicitly in SQL
- producing modeled analytics tables in `analytics_gtm`
- shaping the first bounded capability surface for:
  - `gtm.pipeline_summary`
  - `gtm.stalled_opportunity_review`
  - `gtm.account_risk_summary`
  - `gtm.prepare_followup_tasks`

The first target is a clean modeled layer over the Maven CRM dataset for:

- accounts
- opportunities
- products
- sales teams

This should produce semantic-ready models for Cube and the ANIP services.
