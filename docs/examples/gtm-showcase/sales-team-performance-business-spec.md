# GTM Sales Team Performance Business Spec

## Purpose

This document defines the bounded business behavior for sales team performance
review inside the GTM pipeline service.

It defines behavior classes and representative requests, not an exhaustive
inventory of every possible user utterance.

## Problem

GTM leaders and RevOps users often need a bounded answer to:

- which teams or managers are carrying the most open pipeline
- where win performance is strongest or weakest
- where stalled load and risk concentration are building
- which of those views should differ by actor and scope

Without a bounded capability, the agent drifts toward generic BI exploration or
raw CRM exports.

## Business Goal

The Phase 6 sales team performance capability should let a GTM user:

- request a bounded team-performance summary for a quarter
- optionally scope that summary to an allowed region
- view performance by one declared slice
- receive explainable evidence about pipeline, wins, and stall pressure

## What The Service Must Be Able To Do

- summarize team or manager performance for a quarter
- support one bounded slice dimension at a time
- return explainable performance rows with pipeline and risk context
- clarify missing quarter rather than guessing
- restrict actor scope when a user asks for a region they should not see
- mask financial values for actors who should not receive full numbers

## What It Must Not Do

- it must not expose raw row-level opportunity exports
- it must not permit arbitrary grouping outside the declared slice surface
- it must not become a generic CRM query layer
- it must not bypass actor-aware restriction or masking
- it must not mutate downstream systems

## Behavior Classes

PM/business should define bounded scope, behavior families, representative
scenario families, and edge cases, not every possible wording.

1. Clear in-scope team performance read
- return bounded performance rows for a quarter and allowed slice

2. Ambiguity requiring clarification
- ask for the quarter when missing

3. Actor-aware restriction
- return `restricted` when an actor asks for a regional scope beyond their
  allowed boundary

4. Actor-aware masking
- return success with masked financial values when the actor can see team shape
  but not the full numbers

5. Out-of-scope request
- deny raw export or unsupported slicing instead of improvising

## Representative Scenario Requests

- `How are our sales teams performing in 2017-Q2?`
- `Show sales team performance for 2017-Q2 by regional office.`
- `How are the teams performing?`
- `Show West-region sales team performance for 2017-Q2.`
- `Export every raw opportunity row behind the sales team performance view.`

These are representative, not exhaustive.

## Business Safety Posture

- team performance behavior must stay bounded and explainable
- missing quarter must trigger clarification instead of guessing
- unsupported slicing must not be improvised silently
- actor-aware restriction and masking are part of the governed contract
- raw exports are not part of this capability

## Validation Intent

Studio should make it possible to verify that:

- this team-performance spec is visible as a source artifact
- the developer design derives a bounded team-performance capability from it
- the generated pipeline service exposes the capability with declared input
  metadata
- the running service executes aggregate team reads through the semantic layer
  without changing the ANIP contract
- actor-aware restriction and masking are visible in live runtime behavior

This spec is representative, not exhaustive.

## Non-Goals

- the PM is not expected to define every possible wording
- this capability is not a generic BI query builder
- this capability does not replace later reassignment-preview behavior
- this capability does not allow raw CRM export
