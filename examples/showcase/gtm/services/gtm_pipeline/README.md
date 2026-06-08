# GTM Pipeline Service

This service is the Phase 1 bounded ANIP service for the GTM showcase.

It owns:

- `gtm.pipeline_summary`
- `gtm.stalled_opportunity_review`
- `gtm.account_risk_summary`
- `gtm.prepare_followup_tasks`

The service reads modeled GTM data from Postgres after the raw Maven CRM tables
have been cleaned and shaped by dbt.
