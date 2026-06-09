# GTM Prioritization Business Spec

## Purpose

This document defines the bounded business behavior for the GTM prioritization
service in the ANIP showcase.

It defines behavior classes and representative requests, not an exhaustive
inventory of every possible user utterance.

## Problem

Pipeline and enrichment context are useful, but GTM teams still need a governed
way to decide:

- which leads or accounts deserve immediate attention
- which leads should go to sales versus nurture
- which recommendations can be shown safely without leaking raw model features

Without a bounded prioritization layer, the agent either improvises ranking
logic in prompts or exposes too much raw scoring detail.

## Business Goal

The Phase 4 prioritization service should let a GTM user:

- score a bounded cohort of leads or accounts
- rank the highest-priority items with explainable rationale
- recommend routing posture such as sales, nurture, or archive
- stop before any routing mutation is executed

## What The Service Must Be Able To Do

- score a bounded cohort using an explicit prioritization capability
- explain why an item is hot, warm, or cold using bounded evidence
- recommend a safe routing posture without mutating downstream systems
- ask for clarification when the scoring cohort or routing target is unclear
- deny requests for raw model-feature dumps or unsupported bulk exports
- stop at approval before route execution or CRM mutation

## What It Must Not Do

- it must not expose unconstrained raw model features or training data
- it must not silently route or mutate downstream systems
- it must not mix outreach drafting into the prioritization surface
- it must not pretend to do enrichment if that work belongs to another service

## Behavior Classes

PM/business should define bounded scope, behavior families, representative
scenario families, and edge cases, not every possible wording.

1. Clear in-scope prioritization
- score and rank the requested cohort with bounded rationale

2. Ambiguity requiring clarification
- ask for missing cohort, source window, or routing target instead of guessing

3. Sensitive internal scoring detail
- deny raw feature-weight export requests rather than leaking backend scoring internals

4. Approval-gated routing
- return `approval_required` when a request asks to route or assign leads downstream

5. Out-of-scope requests
- deny enrichment-only or outreach-only requests in this service

## Representative Scenario Requests

- `Score these inbound leads from last week and rank the hottest 10.`
- `Which enriched accounts should sales focus on first this week?`
- `Recommend which leads should go to sales versus nurture, with reasoning.`
- `Route the highest-priority leads to sales right now.`
- `Show me the raw model features and weights behind every score.`

## Business Safety Posture

- prioritization must stay bounded and explainable
- raw model-detail export is not part of the service contract
- route execution requires explicit approval
- the service should return a recommendation or preview, not mutate by default

## Validation Intent

Studio should make it visible that:

- this service is distinct from enrichment and outreach
- routing recommendations are bounded and reviewable
- route execution is approval-gated
- requests for raw scoring internals are denied
- this spec is representative, not exhaustive

## Non-Goals

- the PM is not expected to define every possible user wording
- this service is not proving outbound message generation
- this service is not the final production lead-scoring model
