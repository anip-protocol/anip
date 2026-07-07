---
title: Capability Map
description: The 23 GTM ANIP capabilities mapped to services and governed outcomes.
---

# Capability Map

The GTM package exposes 23 ANIP capabilities across four services. This page is a readable map; the signed package remains the source of truth.

Package:

```text
gtm-pipeline-q2-review@0.4.5
```

## Pipeline service

| Capability | Kind | Posture | Produces | Forbidden |
| --- | --- | --- | --- | --- |
| `gtm.pipeline_summary` | atomic | read | summary | raw data export |
| `gtm.pipeline_forecast_summary` | atomic | read | summary | raw data export |
| `gtm.stage_bottleneck_summary` | atomic | read | summary | raw data export |
| `gtm.sales_team_performance_summary` | atomic | read | summary | raw data export |
| `gtm.product_pipeline_summary` | atomic | read | summary | raw data export |
| `gtm.stalled_opportunity_review` | atomic | read | summary | raw data export |
| `gtm.account_risk_summary` | atomic | read | summary | raw data export |
| `gtm.prepare_followup_tasks` | atomic | approval-gated | preview, approval request, summary | approval execution, raw data export |
| `gtm.prepare_reassignment_plan` | atomic | approval-gated | preview, approval request, summary | approval execution, raw data export |
| `gtm.at_risk_followup_preparation` | composed | approval-gated | preview, approval request, summary | approval execution, raw data export |
| `gtm.at_risk_reassignment_preparation` | composed | approval-gated | preview, approval request, summary | approval execution, raw data export |

## Enrichment service

| Capability | Kind | Posture | Produces | Forbidden |
| --- | --- | --- | --- | --- |
| `gtm.account_enrichment_summary` | atomic | read | summary | raw data export |
| `gtm.lookalike_accounts` | atomic | read | summary | raw data export |
| `gtm.at_risk_account_enrichment_summary` | atomic | read | summary | raw data export |

## Prioritization service

| Capability | Kind | Posture | Produces | Forbidden |
| --- | --- | --- | --- | --- |
| `gtm.score_leads` | atomic | read | summary, recommendation | raw model features, raw data export |
| `gtm.prioritize_accounts` | atomic | read | summary, recommendation | raw model features, raw data export |
| `gtm.route_leads` | atomic | approval-gated | preview, approval request, summary | approval execution, raw model features, raw data export |
| `gtm.prioritized_routing_preparation` | composed | approval-gated | preview, approval request, summary | approval execution, raw model features, raw data export |

## Outreach service

| Capability | Kind | Posture | Produces | Forbidden |
| --- | --- | --- | --- | --- |
| `gtm.draft_outreach_message` | atomic | read | draft | external dispatch, system mutation, raw data export |
| `gtm.suggest_followup_content` | atomic | read | draft | external dispatch, system mutation, raw data export |
| `gtm.objection_response_variants` | atomic | read | draft | external dispatch, system mutation, raw data export |
| `gtm.prioritized_outreach_draft` | atomic | read | draft | external dispatch, system mutation, approval execution, raw data export |
| `gtm.bottleneck_account_outreach_draft` | atomic | approval-gated | draft, preview, approval request | external dispatch, system mutation, approval execution, raw data export |

## How to interpret this map

Read capabilities are not automatically unrestricted. They still carry actor scope, input resolution, masking, restricted outcomes, and denied effects.

Approval-gated capabilities do not perform the downstream write. They prepare a bounded preview and return an approval-required outcome. Approval execution is explicitly not produced by the first-cut GTM package.

Composed capabilities preserve service ownership and step boundaries. They should not hide clarification, restriction, denial, or approval stops inside a single opaque result.
