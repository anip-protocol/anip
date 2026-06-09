# Phase 2 Live Proof

## Purpose

Record the minimum live Phase 2 bring-up steps and the first working
multi-service GTM results.

Phase 2 is not complete yet. This document captures the point where the second
bounded service became live and the LLM runtime began traversing two ANIP
services in one governed flow.

## Recorded Execution Sequence

1. generate the Studio enrichment scaffold under
   `examples/showcase/gtm/generated/studio_gtm_enrichment`
2. add a generated-service Dockerfile for the enrichment runtime
3. wire `gtm-enrichment-service` into the GTM Compose stack
4. add a Studio observer for the enrichment project and service
5. extend the LLM runtime to read live capability briefs from both services
6. add deterministic cross-service bridging for:
   - top at-risk accounts -> enrichment summary
7. run the live stack and confirm Studio saves observed enrichment metadata
8. run direct and cross-service Phase 2 questions against the live stack

## Runtime Wiring

The live Phase 2 stack now includes:

- `gtm-pipeline-service`
- `gtm-enrichment-service`
- `gtm-agent-llm-ui`
- `gtm-studio-observe-enrichment`

## Live Metadata Result

Studio now observes and saves live metadata for:

- project: `gtm-account-enrichment`
- service: `anip-gtm-enrichment-showcase`

Observed enrichment metadata checks passed for the live runtime:

- protocol: `anip/0.22`
- trust level: `signed`
- manifest signature present: `true`
- JWKS URI present: `true`
- capabilities present:
  - `gtm.account_enrichment_summary`
  - `gtm.lookalike_accounts`
- minimum scope:
  - `gtm.enrichment.read`

## Live Questions And Outcomes

### Direct enrichment question

Question:

`Summarize firmographic context for Acme Corporation and Codehow.`

Observed result:

- selected capability: `gtm.account_enrichment_summary`
- selected service: `enrichment`
- outcome: `success`
- loop counts:
  - planner loops: `1`
  - service invoke loops: `1`
  - total loops: `2`

Returned bounded enrichment fields included:

- sector
- office location
- parent company
- revenue band
- employee band
- ICP fit
- intent signal
- likely buying motion
- enrichment rationale

### Cross-service enrichment question

Question:

`Show enrichment context for the top 5 at-risk accounts in 2017-Q2.`

Observed result:

- planned capability: `gtm.account_risk_summary`
- final selected capability: `gtm.account_enrichment_summary`
- final selected service: `enrichment`
- prior service calls recorded: `1`
- outcome: `success`
- loop counts:
  - planner loops: `1`
  - service invoke loops: `2`
  - total loops: `3`

Cross-service trace:

1. pipeline service returns the top at-risk accounts for `2017-Q2`
2. runtime extracts and deduplicates the account names
3. enrichment service returns bounded enrichment context for those accounts

Final enrichment result was returned for:

- `Betasoloin`
- `Condax`
- `Dalttechnology`

## Architecture Notes

The current Phase 2 path still follows the same core ANIP design stance:

- thin prompting
- thin runtime
- bounded services
- service-side enforcement

The cross-service bridge is deterministic and explicit. It does not replace the
governed service contract. It only resolves the bounded handoff between two
ANIP services and records that prior call path in the runtime output.

## Next Required Step

Turn these live Phase 2 paths into saved regression coverage:

1. direct enrichment cases
2. cross-service enrichment cases
3. saved run artifacts with loop counts and pass/fail status
