---
title: Business Intent
description: Product and business intent behind the GTM Agent showcase.
---

# Business Intent

The GTM Agent showcase models a revenue-operations assistant for quarterly pipeline review and follow-up preparation. The product goal is to let GTM users ask natural questions while keeping data scope, approval boundaries, and downstream action semantics explicit.

This is deliberately different from giving an agent a set of raw CRM, BI, or messaging tools. The agent receives governed ANIP capabilities that already encode what the provider allows.

## Primary users

The project models business actors such as:

- sales leaders who can inspect bounded pipeline, forecast, risk, and team evidence;
- account managers who operate within regional or account scope;
- revenue operations users who review prioritization and routing previews;
- approvers who can review prepared operational outcomes before execution.

The exact actor and permission model is part of the Studio project and compiled package. The docs describe the intent; the package is the enforcement source of truth.

## Product promise

The user should be able to ask questions such as:

- `Show pipeline health for 2017-Q2 in the East region.`
- `Rank the top at-risk accounts for 2017-Q2 in the East region.`
- `Prepare follow-up tasks for the top at-risk accounts in 2017-Q2 for the East region.`
- `Draft outreach for the top expansion candidate in Q2.`
- `Route the inbound leads from last week to sales.`
- `Export the raw CRM records for 2017-Q2.`

The important part is that these requests do not all have the same outcome:

| Request posture | Expected ANIP behavior |
| --- | --- |
| Bounded read | Return governed summary evidence. |
| Missing target or time scope | Ask for clarification. |
| Out-of-scope actor request | Return restricted or denied. |
| Write-adjacent preparation | Return preview and stop for approval. |
| Raw export request | Deny rather than leaking row-level data. |
| Send or mutate request | Deny or require approval, depending on declared capability semantics. |

## Business boundaries

The showcase encodes these business boundaries:

- Bounded GTM summaries are allowed.
- Raw row-level CRM export is not a supported product outcome.
- Financial values may be full, masked, or restricted based on actor visibility.
- Outreach generation is draft-only unless the contract explicitly grants a send path.
- Routing and reassignment are preview/approval flows, not silent backend mutations.
- Composed requests must preserve step-level outcomes, so a clarification, restriction, denial, or approval stop is visible.

## Why this matters

Without ANIP, the same behavior is often implemented as prompts, skills, recipes, or workflow code on the consumer side. That is brittle because the consumer can drift from the provider's intended rules.

In this showcase, the provider-owned contract defines what the service means by pipeline review, risk ranking, routing preparation, and outreach drafting. The agent plans against that contract, but the service still owns the boundary.

