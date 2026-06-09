# GTM Pipeline Forecast Business Spec

## Purpose

This document defines the bounded business behavior for the forecast layer
inside the GTM pipeline service.

It defines behavior classes and representative requests, not an exhaustive
inventory of every possible user utterance.

## Problem

GTM leaders and RevOps users do not only want current pipeline shape. They also
want a bounded answer to:

- what is likely to close
- what the best-case forecast looks like
- which stages and deals are driving the forecast
- how forecast visibility should differ by actor

Without a bounded forecast capability, the agent either improvises forecast
logic in prompts or drifts toward unconstrained BI-style querying.

## Business Goal

The Phase 6 forecast capability should let a GTM user:

- request a bounded pipeline forecast for a quarter
- optionally scope that forecast to a region or actor-visible slice
- choose a declared forecast mode such as `risk_adjusted`, `likely`, or
  `best_case`
- see explainable stage rollups and top contributors
- receive the right visibility level for their actor role

## What The Service Must Be Able To Do

- summarize forecast totals for a bounded quarter and optional owner scope
- explain forecast shape by stage
- surface top contributing open opportunities or accounts
- clarify missing quarter rather than guessing
- restrict actor scope when a user asks for a region they should not see
- mask financial forecast values for actors who should not receive full numbers

## What It Must Not Do

- it must not expose raw row-level CRM exports
- it must not invent unsupported forecast modes
- it must not become a generic free-form query surface
- it must not bypass actor-aware restriction or masking rules
- it must not mutate downstream systems

## Behavior Classes

PM/business should define bounded scope, behavior families, representative
scenario families, and edge cases, not every possible wording.

1. Clear in-scope forecast read
- return bounded forecast totals, stage rollups, and top contributors

2. Ambiguity requiring clarification
- ask for the quarter when missing

3. Actor-aware restriction
- return `restricted` when an actor asks for a scope beyond their allowed
  region or ownership boundary

4. Actor-aware masking
- return success with masked financial values when the actor can see the shape
  of the forecast but not the full numbers

5. Out-of-scope request
- deny raw export or unsupported analysis requests rather than improvising

## Representative Scenario Requests

- `What is our risk-adjusted pipeline forecast for 2017-Q2?`
- `Show the best-case pipeline forecast for 2017-Q2 in the East region.`
- `What is our likely pipeline forecast?`
- `Show the best-case pipeline forecast for 2017-Q2 in the West region.`
- `Export every raw opportunity row behind the forecast for 2017-Q2.`

These are representative, not exhaustive.

## Business Safety Posture

- forecast behavior must stay bounded and explainable
- missing quarter must trigger clarification instead of guessing
- unsupported forecast modes should not be improvised silently
- actor-aware restriction and masking are part of the governed contract
- raw forecast exports are not part of this capability

## Validation Intent

Studio should make it possible to verify that:

- this forecast spec is visible as a source artifact
- the developer design derives a bounded forecast capability from it
- the generated pipeline service exposes the capability with declared input
  metadata
- the running service executes aggregate forecast reads through the semantic
  layer without changing the ANIP contract
- actor-aware restriction and masking are visible in live runtime behavior

This spec is representative, not exhaustive.

## Non-Goals

- the PM is not expected to define every possible wording
- this capability is not a generic BI query builder
- this capability does not replace the later bottleneck, team-performance, or
  reassignment-preview capabilities
- this capability does not allow raw CRM export
