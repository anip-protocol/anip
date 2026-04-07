# Dogfood Round 1 Findings: Permissions and Budget Delegation

Date: 2026-04-06
Branch: `feat/dogfood-round1-permissions-budget`

## Goal
Exercise real permission-driven ANIP consumption inside Studio dogfood mode, including all three permission outcomes:
- `available`
- `restricted`
- `denied`

## What Was Added
- Dogfood-only pressure mode in Studio via `STUDIO_DOGFOOD_PROFILE=round1`
- Permission-preflight behavior in the Studio stress agent
- Budget-aware delegated issuance for `evaluate_service_design`
- Non-delegable path for `generate_engineering_contract`
- Permission discovery support for real `denied` outcomes on `non_delegable`

## Live Dogfooding Result
A live ANIP-only stress run against Studio completed successfully with all three permission outcomes exercised.

Observed behavior:
- `create_project`: parent token was `restricted`, delegated child token became `available`
- `evaluate_service_design`: parent token was `restricted` with `request_budget_bound_delegation`, delegated child token became `available` with budget constraints
- `generate_engineering_contract`: parent token was `denied` with `reason_type = non_delegable`, agent switched to a fresh root capability token and completed successfully

## Important Bug Found
Dogfooding exposed a real mismatch in delegated issuance handling:
- the HTTP `/anip/tokens` route authenticated JWT bearers as `root_principal`
- delegated issuance needed the current token `subject`

That bug was fixed before the final successful run.

## Conclusion
Round 1 now proves that Studio can pressure ANIP permission discovery and delegation in one realistic app, not a segmented harness.

For the exercised flow:
- `available` works
- `restricted` works with delegated recovery
- `denied` works with explicit root-token escalation
- budget-aware delegation works

## Next Pressure Areas
Recommended next rounds:
1. audit as a first-class consumer surface
2. posture-aware discovery and manifest consumption
3. streaming and state/session semantics
