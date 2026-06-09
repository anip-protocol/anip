# Application Integration Design Packet: GTM Prioritization Service

Generated: 2026-04-13T05:42:52.986762+00:00

## Backend
- Type: rest_api
- System: Lead Prioritization API
- Base URL: https://prioritization.internal.example.com
- Auth: bearer_token
- Implementation language: python

## Objects
- Lead: Lead or contact candidate scored for GTM follow-up.
- Scorecard: Explainable prioritization outcome for a bounded lead or account cohort.
- Routing Preview: Approval-gated routing recommendation before any mutation.

## Capabilities
- Score Leads (summarize, read, read_only) -> score_leads
- Prioritize Accounts (summarize, read, read_only) -> prioritize_accounts
- Route Leads (trigger_workflow, write, approval_required_write) -> route_leads

## Governance
- Permission rules: 2
- Clarification rules: 2
- Restriction rules: 2
- Denial rules: 2
- Approval rules: 1

## Scenarios
- Score bounded cohort: available
- Clarify missing cohort: clarification_required
- Deny raw model export: denied
- Approval-gated routing: approval_required