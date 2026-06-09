# GTM Stage Bottleneck Business Spec

## Purpose

This document defines the bounded business behavior for stage-bottleneck review
inside the GTM pipeline service.

It defines behavior classes and representative requests, not an exhaustive
inventory of every possible user utterance.

## Problem

GTM and RevOps teams often need to know where open pipeline is getting stuck,
not only which accounts are risky overall.

That requires a bounded answer to questions like:

- where deals are accumulating
- which stages are aging the most
- whether bottlenecks concentrate in a region, manager group, or product line
- which of those views should be visible or restricted by actor

Without a bounded bottleneck capability, the agent drifts toward unconstrained
BI-style exploration or raw table access.

## Business Goal

The Phase 6 bottleneck capability should let a GTM user:

- request a bounded stage bottleneck summary for a quarter
- optionally scope that summary to an actor-visible region
- slice the summary by one declared dimension
- receive explainable evidence about stage accumulation, aging, and risk
- stay inside a governed read-only surface

## What The Service Must Be Able To Do

- summarize stage bottlenecks for a quarter
- support one bounded slice dimension at a time
- return top bottleneck rows with explainable evidence
- clarify missing quarter rather than guessing
- restrict actor scope when a user asks for a region they should not see
- mask financial values for actors who should not receive full numbers

## What It Must Not Do

- it must not expose raw opportunity exports
- it must not permit arbitrary grouping or filtering outside the declared slice
  surface
- it must not become a generic CRM query language
- it must not bypass actor-aware restriction or masking
- it must not mutate downstream systems

## Behavior Classes

PM/business should define bounded scope, behavior families, representative
scenario families, and edge cases, not every possible wording.

1. Clear in-scope bottleneck read
- return bounded bottleneck rows for a quarter and allowed slice

2. Ambiguity requiring clarification
- ask for the quarter when missing

3. Actor-aware restriction
- return `restricted` when an actor asks for a regional scope beyond their
  allowed boundary

4. Actor-aware masking
- return success with masked financial values when the actor can see the
  bottleneck shape but not the full numbers

5. Out-of-scope request
- deny raw export or unsupported slicing instead of improvising

## Representative Scenario Requests

- `Where are the biggest stage bottlenecks in our 2017-Q2 pipeline?`
- `Show the biggest stage bottlenecks by product for 2017-Q2 in the East region.`
- `Where are we bottlenecked?`
- `Show the biggest stage bottlenecks in the West region for 2017-Q2.`
- `Export every raw opportunity row behind the bottleneck view for 2017-Q2.`

These are representative, not exhaustive.

## Business Safety Posture

- bottleneck behavior must stay bounded and explainable
- missing quarter must trigger clarification instead of guessing
- unsupported slicing must not be improvised silently
- actor-aware restriction and masking are part of the governed contract
- raw bottleneck exports are not part of this capability

## Validation Intent

Studio should make it possible to verify that:

- this bottleneck spec is visible as a source artifact
- the developer design derives a bounded bottleneck capability from it
- the generated pipeline service exposes the capability with declared input
  metadata
- the running service executes aggregate bottleneck reads through the semantic
  layer without changing the ANIP contract
- actor-aware restriction and masking are visible in live runtime behavior

This spec is representative, not exhaustive.

## Non-Goals

- the PM is not expected to define every possible wording
- this capability is not a generic BI query builder
- this capability does not replace later team-performance or product-pipeline
  summaries
- this capability does not allow raw CRM export
