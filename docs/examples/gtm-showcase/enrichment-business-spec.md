# GTM Enrichment Service Business Spec

## Purpose

This document defines the Phase 2 business intent for the GTM enrichment layer.

It extends the Phase 1 pipeline-review loop with bounded account enrichment,
without turning the showcase into one large GTM super-service.

This document defines behavior classes and representative requests, not an
exhaustive language inventory.

## Problem

A GTM user can identify risky accounts from the pipeline service, but that is
not enough to decide how to prioritize or frame follow-up.

The user often still needs:

- firmographic context
- a quick explanation of why an account matters
- a bounded way to find similar accounts

That information should be available through a governed service boundary rather
than by giving the agent unconstrained access to raw enrichment sources.

## Business Goal

The system should let a revenue operator or GTM user:

- request bounded enrichment summaries for a selected set of accounts
- understand the firmographic and fit context for those accounts
- ask for lookalike accounts similar to a named reference account
- receive explainable, bounded enrichment evidence

The service should stay non-mutating in this phase.

## What The Agent Must Be Able To Do

- summarize enrichment context for a bounded set of accounts
- explain why an account is considered a strong or weak fit
- identify lookalike accounts using bounded similarity logic
- stay within an explicit account or segment scope

## What It Must Not Do

- it must not expose raw unconstrained enrichment exports
- it must not invent enrichment from unsupported sources
- it must not silently mix outreach or lead-scoring behavior into the service
- it must not mutate downstream systems

## Behavior Classes

The PM is not expected to define every possible wording a user might use.

The PM should define:

- bounded capability scope
- behavior families
- representative scenario families
- critical boundaries and edge cases

For this service, the main behavior classes are:

1. clear in-scope bounded enrichment read
- return a bounded enrichment summary for selected accounts

2. ambiguity requiring clarification
- ask for the account set or reference account when missing

3. broad or unsafe data request
- deny raw bulk export requests in this phase

4. bounded similarity analysis
- return explainable lookalike accounts based on bounded matching logic

5. out-of-scope request
- deny lead scoring, outreach drafting, or operational mutation requests

## Representative Scenario Requests

- `Summarize firmographic context for Acme Corporation and Codehow.`
- `Show enrichment context for the top 5 at-risk accounts from the current pipeline review.`
- `Find lookalike accounts similar to Acme Corporation.`
- `Which enriched accounts look most similar to our best software customers?`
- `Export the full raw enrichment dataset for every account.`

These are representative, not exhaustive.

## Business Safety Posture

- the service must return bounded evidence, not unconstrained raw enrichment
- unsafe or out-of-scope requests should stop cleanly with denial
- missing account scope should trigger clarification instead of guessing
- the service must remain read-only in this phase

## Validation Intent

Studio should make it possible to verify that:

- this business spec is the source artifact
- the developer design stays bounded to enrichment and lookalike behavior
- the generated enrichment service matches the intended capability contract
- the running service exposes ANIP metadata that Studio can inspect and compare

This spec is representative, not exhaustive.

## Non-Goals

- the PM is not expected to define every possible user wording
- proving outreach or scoring behavior in this service
- proving downstream mutation
- merging all GTM layers into one service
