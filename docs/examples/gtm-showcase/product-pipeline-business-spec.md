# GTM Product Pipeline Business Spec

## Purpose

This document defines the bounded business behavior for product pipeline review
inside the GTM pipeline service.

It defines behavior classes and representative requests, not an exhaustive
inventory of every possible user utterance.

## Problem

GTM and product-facing leaders often need a bounded answer to:

- which products are carrying the most open pipeline
- which products are generating won revenue
- where loss volume and risk are concentrating by product line
- which product-level views should differ by actor and scope

Without a bounded capability, the agent drifts toward generic reporting or raw
data export.

## Business Goal

The Phase 6 product pipeline capability should let a GTM user:

- request a bounded product summary for a quarter
- optionally scope that summary to an allowed region
- optionally focus the view on one declared product
- receive explainable product rows with pipeline, win, loss, and risk context

## What The Service Must Be Able To Do

- summarize product pipeline for a quarter
- optionally narrow to one declared product
- return explainable product rows with open, won, and lost posture
- clarify missing quarter rather than guessing
- restrict actor scope when a user asks for a region they should not see
- mask financial values for actors who should not receive full numbers

## What It Must Not Do

- it must not expose raw row-level opportunity exports
- it must not become a generic free-form product analytics surface
- it must not bypass actor-aware restriction or masking
- it must not mutate downstream systems

## Behavior Classes

PM/business should define bounded scope, behavior families, representative
scenario families, and edge cases, not every possible wording.

1. Clear in-scope product summary read
- return bounded product rows for a quarter and optional scope

2. Ambiguity requiring clarification
- ask for the quarter when missing

3. Actor-aware restriction
- return `restricted` when an actor asks for a regional scope beyond their
  allowed boundary

4. Actor-aware masking
- return success with masked financial values when the actor can see product
  shape but not full revenue values

5. Out-of-scope request
- deny raw export requests instead of improvising

## Representative Scenario Requests

- `Show product pipeline performance for 2017-Q2.`
- `Show product pipeline performance for 2017-Q2 in the East region.`
- `How are the products performing?`
- `Show product pipeline for GTX Pro in 2017-Q2.`
- `Export every raw opportunity row behind the product pipeline view.`

These are representative, not exhaustive.

## Business Safety Posture

- product pipeline behavior must stay bounded and explainable
- missing quarter must trigger clarification instead of guessing
- actor-aware restriction and masking are part of the governed contract
- raw exports are not part of this capability

## Validation Intent

Studio should make it possible to verify that:

- this product-pipeline spec is visible as a source artifact
- the developer design derives a bounded product capability from it
- the generated pipeline service exposes the capability with declared input
  metadata
- the running service executes aggregate product reads through the semantic
  layer without changing the ANIP contract
- actor-aware restriction and masking are visible in live runtime behavior

This spec is representative, not exhaustive.

## Non-Goals

- the PM is not expected to define every possible wording
- this capability is not a generic BI query builder
- this capability does not allow raw CRM export
