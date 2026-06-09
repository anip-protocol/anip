# GTM Reassignment Preview Business Spec

## Purpose

This document defines the bounded business behavior for reassignment preview
planning inside the GTM pipeline service.

It defines behavior classes and representative requests, not an exhaustive
inventory of every possible user utterance.

## Problem

GTM leaders and RevOps operators sometimes need a bounded answer to:

- which open opportunities should be rebalanced away from overloaded coverage
- which managers have capacity to absorb those opportunities
- why a reassignment was suggested
- which of those requests should stop at approval instead of executing

Without a bounded capability, the agent drifts toward generic staffing advice
or direct ownership mutation.

## Business Goal

The Phase 6 reassignment-preview capability should let an authorized GTM user:

- request a bounded reassignment preview for a quarter
- optionally scope that preview to an allowed region
- choose one declared reassignment basis
- receive a preview that explains source load, target capacity, and expected
  operational impact

## What The Service Must Be Able To Do

- prepare a bounded reassignment preview for a quarter
- optionally narrow the preview to one allowed region
- support one declared selection basis at a time
- return explainable source and target manager recommendations
- clarify missing quarter rather than guessing
- restrict actor scope when a user asks for a region they should not see
- return `approval_required` instead of mutating assignments

## What It Must Not Do

- it must not execute reassignment directly
- it must not expose raw row-level exports as part of reassignment planning
- it must not become a generic workforce-planning tool
- it must not bypass actor-aware restriction
- it must not skip approval before downstream assignment mutation

## Behavior Classes

PM/business should define bounded scope, behavior families, representative
scenario families, and edge cases, not every possible wording.

1. Clear in-scope reassignment preview
- return `approval_required` with a bounded preview payload

2. Ambiguity requiring clarification
- ask for the quarter when missing

3. Actor-aware restriction
- return `restricted` when an actor asks for a regional scope beyond their
  allowed boundary

4. Approval-gated operational write preview
- stop at approval instead of mutating ownership

5. Out-of-scope request
- deny direct assignment execution or raw export instead of improvising

## Representative Scenario Requests

- `Prepare a reassignment plan for overloaded managers in 2017-Q2.`
- `Prepare a reassignment plan for the East region in 2017-Q2.`
- `Prepare a reassignment plan.`
- `Prepare a reassignment plan for the West region in 2017-Q2.`
- `Reassign these opportunities right now and update CRM ownership.`

These are representative, not exhaustive.

## Business Safety Posture

- reassignment behavior must stay bounded and explainable
- missing quarter must trigger clarification instead of guessing
- actor-aware restriction is part of the governed contract
- downstream assignment mutation is not part of this capability
- approval is required before any later execution step

## Validation Intent

Studio should make it possible to verify that:

- this reassignment-preview spec is visible as a source artifact
- the developer design derives a bounded reassignment-preview capability from it
- the generated pipeline service exposes the capability with declared input
  metadata
- the running service returns `approval_required` with a preview instead of
  mutating ownership
- actor-aware restriction and approval behavior are visible in live runtime
  behavior

This spec is representative, not exhaustive.

## Non-Goals

- the PM is not expected to define every possible wording
- this capability is not a generic staffing optimizer
- this capability does not execute reassignment
- this capability does not allow raw CRM export
