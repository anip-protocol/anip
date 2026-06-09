# Data Access Design Packet: GTM Account Enrichment Data Access

Generated: 2026-04-13T02:43:43.584029+00:00

## Backend
- Type: curated_sql
- Target: Curated SQL planner
- Implementation language: python

## Domain
- Name: revenue_operations
- Metrics: Sales Amount
- Dimensions: Customer
- Filters: Time Window
- Grains: aggregate
- Result Modes: exploratory, decision_grade

## Governed Outcomes
- available: enabled
- restricted: enabled
- denied: enabled
- clarification_required: enabled

## Clarification Rules
- ambiguous_ranking_metric: enabled
- ambiguous_time_semantics: enabled
- ambiguous_entity_grain: disabled
- ambiguous_account_hierarchy: disabled

## Scenario Pack
- Categories: allowed, restricted, denied, clarification_required
- Target Count: 12