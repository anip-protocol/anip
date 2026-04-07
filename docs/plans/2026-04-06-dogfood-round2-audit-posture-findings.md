# Dogfood Round 2 Findings: Audit and Posture-Aware Consumption

Date: 2026-04-06
Branch: `feat/dogfood-round2-audit-posture`

## Goal
Exercise ANIP discovery posture and audit as real consumer surfaces inside the Studio dogfood loop.

## What Was Added
- Round 2 dogfood profile in Studio via `STUDIO_DOGFOOD_PROFILE=round2`
- Different discovery posture for the two Studio ANIP services:
  - `studio-assistant`: `trust_level = signed`, `failure_disclosure = redacted`
  - `studio-workbench`: `trust_level = anchored`, `proofs_available = true`, `failure_disclosure = full`
- Posture-aware stress-agent logic:
  - fetch discovery before starting the loop
  - derive per-service audit mode from discovery posture
  - verify audit entries after real invocations using `client_reference_id` and `invocation_id`

## Live Dogfooding Result
A live ANIP-only stress run against Studio completed successfully.

The agent now consumes discovery posture before executing the workflow:
- assistant posture was treated as lower-trust / basic-audit
- workbench posture was treated as higher-trust / strict-audit

The agent then queried `/anip/audit` throughout the workflow and successfully verified audit entries for:
- `interpret_project_intent`
- `create_project`
- `accept_first_design`
- `evaluate_service_design`
- `draft_fix_from_change`
- `generate_business_brief`
- `generate_engineering_contract`

## Important Finding
Dogfooding exposed a real lineage coupling edge:
- invoke-time `task_id` must match the token purpose task ID
- the current consumer path does not know that value after token issuance

For Round 2, audit verification was shifted to:
- `client_reference_id`
- `invocation_id`

That still pressured audit and discovery honestly, but it shows a remaining ANIP consumer ergonomics gap around task identity reuse after token issuance.

## Conclusion
Round 2 is a success.

For the exercised Studio path:
- discovery posture is now affecting agent behavior
- audit is now a real consumer surface, not just an inspect-only surface
- workbench can be treated as the higher-trust authoritative service
- assistant can be treated as a lower-trust advisory surface

## Follow-on Opportunity
The biggest concrete follow-on from this round is:
- make task identity reuse easier for consumers after token issuance

That is not required to validate Round 2, but dogfooding clearly surfaced it.
