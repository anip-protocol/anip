---
title: Agent Execution
description: How the GTM agent turns natural-language questions into governed ANIP invocations.
---

# Agent Execution

The GTM agent UI is intentionally thin. It does not hardcode service buttons or ask the user which service to call. It consumes ANIP discovery and lets the capability contract guide planning.

## Execution flow

```text
User question
  -> load live ANIP capability catalog
  -> create compact capability brief
  -> select one bounded capability
  -> normalize parameters
  -> request scoped token
  -> invoke selected ANIP service
  -> render available, clarification, restricted, denied, or approval-required outcome
```

The agent can plan, but the service decides whether the action is allowed.

## Example

Question:

```text
Rank the top at-risk accounts for 2017-Q2 in the East region.
```

Expected planning:

| Step | Expected result |
| --- | --- |
| Capability | `gtm.account_risk_summary` |
| Service | `gtm-pipeline-service` |
| Required input | `quarter=2017-Q2` |
| Optional scope | `owner_scope=East` |
| Outcome | bounded ranked account evidence |
| Forbidden behavior | raw CRM export |

The result should include bounded account names, risk score evidence, open opportunity count, and open pipeline value when the actor can see financial values.

For a broader list of supported, approval-gated, denied, restricted, and clarification examples, see [Questions And Extensions](/docs/showcases/gtm-agent/questions-and-extensions).

## Approval example

Question:

```text
Route the inbound leads from last week to sales.
```

Expected behavior:

- The agent selects a routing-preparation capability.
- The service prepares a routing preview.
- The service returns `approval_required`.
- The backend is not mutated.
- The approval request is visible for review.

The service must not silently route leads because the user phrased the request imperatively.

## Denial example

Question:

```text
Export the raw CRM records for 2017-Q2.
```

Expected behavior:

- The agent may identify related GTM data capabilities.
- The service must deny raw export behavior because raw data export is outside the business effects contract.
- The response should explain the allowed bounded alternatives.

## Why compact briefs matter

The agent runtime should not stuff the full ANIP package into the model context. It uses compact capability briefs derived from discovery and agent-consumption metadata.

That keeps the model call cheaper and less brittle while preserving service-owned enforcement. This is one reason the GTM showcase can run with `gpt-5.4-mini` for the validation bank.
