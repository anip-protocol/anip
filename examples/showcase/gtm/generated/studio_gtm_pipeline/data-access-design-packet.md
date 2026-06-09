# Data Access Design Packet: GTM Pipeline Service

Generated: 2026-04-12T21:22:29.380345+00:00

## Backend
- Type: cube_rest
- Target: Cube semantic query surface
- Implementation language: python

## Domain
- Name: revenue_operations
- Metrics: Open Pipeline Value, Risk Score, Opportunity Count
- Dimensions: Quarter, Deal Stage, Account, Owner Scope
- Filters: Quarter, Owner Scope, Ranking Basis, Limit
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