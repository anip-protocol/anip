# GTM Showcase Business Spec

## Purpose

This is the canonical PM-readable business specification for the GTM ANIP
showcase.

It is intentionally not written as a Studio-internal artifact first.

This document defines expected behavior classes and representative requests,
not an exhaustive language inventory.

The showcase has to prove that a business document like this can be translated
into bounded behavior specifications, developer design, generated service code,
implementation validation, and real agent execution.

## Problem

Revenue and GTM teams need agents that can answer pipeline-health questions,
identify at-risk deals, and prepare follow-up work without exposing raw data or
improvising unsafe write behavior.

The current default pattern in the market is usually:

- a general-purpose agent
- prompts
- broad tool access to CRM or data systems
- weak reviewability when the agent narrows, guesses, or overreaches

That pattern is not good enough for serious in-house GTM operations.

## Business Goal

Build a bounded GTM agent experience that lets a revenue operator or GTM user:

- understand current pipeline health for a quarter or region
- identify the accounts and opportunities most at risk
- understand why those accounts are risky through bounded evidence
- prepare follow-up work
- stop cleanly at approval before any downstream mutation

## What The Agent Must Be Able To Do

For Phase 1, the agent must be able to:

- summarize bounded pipeline health
- identify stalled opportunities
- rank risky accounts with explicit evidence
- prepare follow-up tasks for review

For Phase 1, it must not attempt to:

- enrich accounts from outside datasets
- score new inbound leads
- draft outreach content
- execute follow-up mutations without approval
- export raw row-level CRM data

## Behavior Classes

The PM is not expected to enumerate every possible user utterance.

The PM is expected to define:

- bounded capability scope
- behavior families
- representative scenario families
- critical boundaries and edge cases

The relevant behavior classes for this showcase are:

1. clear in-scope bounded read
- return available results with bounded evidence

2. ambiguity requiring clarification
- do not guess missing quarter, ranking basis, or scope

3. broad or unsafe data requests
- in Phase 1, deny raw row-level exports rather than improvising a narrower interpretation

That is a Phase 1 policy choice for this showcase, not a universal ANIP rule.

4. operational write preparation
- allow plan preparation
- stop at `approval_required` before downstream side effects

5. out-of-scope requests
- deny rather than improvise

## Representative Scenario Requests

- “Which deals in our Q2 pipeline are at risk this quarter, and why?”
- “Show me all opportunities stuck longer than 30 days.”
- “Rank the highest-risk accounts in our Q2 pipeline.”
- “Prepare follow-up tasks for the highest-risk accounts in my Q2 pipeline.”
- “Show me raw row-level records for our Q2 pipeline.”

These are representative scenario requests, not an exhaustive list.

## Business Safety Posture

- the system must not guess missing critical parameters
- the system must not expose raw exports when the bounded capability is meant to
  return governed summaries
- the system must not execute downstream operational changes without approval
- the system must make its restriction, denial, clarification, and approval
  behavior visible and reviewable

## Validation Intent

This business spec is representative, not exhaustive.

The showcase is successful only if the following can be demonstrated:

- this business spec is visible as a source artifact
- Studio translates this spec into bounded requirements and scenarios
- Studio developer design derives an implementation shape from those
  requirements
- the running service code is generated from that design path, then completed
  and run
- Studio validates the running service against observed ANIP metadata and
  runtime behavior
- more than one agent runtime can consume the same governed service correctly

## Non-Goals

- proving a single unconstrained GTM super-agent
- covering every GTM workflow in the first release
- proving outbound enrichment, lead scoring, and outreach in Phase 1
- relying on hidden manual interpretation steps that Studio cannot represent
- expecting the PM to define every possible wording a user might use
