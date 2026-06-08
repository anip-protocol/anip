# GTM Outreach Business Spec

## Purpose

This document defines the bounded business behavior for the GTM outreach
service in the ANIP showcase.

It defines behavior classes and representative requests, not an exhaustive
inventory of every possible user utterance.

## Problem

Once pipeline, enrichment, and prioritization exist, GTM users still need a
governed way to prepare outreach content:

- drafts should use bounded context
- the system should not quietly send anything
- conversation examples should improve content quality without turning the agent
  into an unconstrained outbound system

## Business Goal

The Phase 5 outreach service should let a GTM user:

- draft bounded outreach messages for a selected lead or account
- request follow-up content variants and objection-response variants
- tailor drafts using explicit account or lead context
- stop before any outbound send action

## What The Service Must Be Able To Do

- draft a bounded outreach message for a selected target
- suggest follow-up content or objection-response variants
- ask for clarification when target, persona, or message goal is unclear
- deny send requests, bulk scraping requests, or raw conversation export requests
- keep the output draft-only in the first cut

## What It Must Not Do

- it must not send emails, LinkedIn messages, or sequences
- it must not expose raw training conversations or long transcript dumps
- it must not pretend to enrich or score when those belong to other services
- it must not mutate CRM engagement state

## Behavior Classes

PM/business should define bounded scope, behavior families, representative
scenario families, and edge cases, not every possible wording.

1. Clear in-scope draft generation
- draft bounded outreach content for an explicit target and purpose

2. Ambiguity requiring clarification
- ask for missing persona, target, channel, or objective instead of guessing

3. Draft-only behavior
- return drafts and variants, not send actions

4. Sensitive source-content requests
- deny raw transcript export or training-corpus dump requests

5. Out-of-scope requests
- deny direct scoring, enrichment-only, or CRM mutation requests in this service

## Representative Scenario Requests

- `Draft a first-touch email for Condax based on its current GTM context.`
- `Generate three follow-up variants for a manufacturing account that is high priority.`
- `Suggest objection-response variants for a prospect comparing us to a competitor.`
- `Send this outreach sequence now.`
- `Show me the raw sales-conversation transcripts you used to draft this message.`

## Business Safety Posture

- the first outreach layer is draft-only
- send actions are out of scope
- transcript or training-corpus export is out of scope
- the service should stay bounded to the selected target and requested content type

## Validation Intent

Studio should make it visible that:

- the outreach service is separate from scoring and enrichment
- draft generation is bounded to explicit context
- send behavior is denied or approval-gated outside the first cut
- this spec is representative, not exhaustive

## Non-Goals

- the PM is not expected to define every possible user wording
- this service is not proving autonomous outbound execution
- this service is not a general conversation model wrapper
