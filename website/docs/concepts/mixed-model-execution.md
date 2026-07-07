---
title: Mixed Model Execution
description: How ANIP enables smaller models to consume governed capabilities with deterministic fallback to stronger models.
---

# Mixed Model Execution

Mixed model execution is the pattern of using a smaller, cheaper model for the common path and escalating to a stronger model only when the request needs it.

ANIP makes this pattern more practical because the agent is not guessing from raw tools. It is consuming a governed service contract: capabilities, inputs, side effects, approvals, denials, recovery guidance, and audit semantics are part of the interface.

The important point is not "nano can do everything." It cannot. The point is narrower and stronger:

> ANIP can move a large class of bounded agent execution down the model-cost curve, while preserving service-owned enforcement.

## The Runtime Pattern

A mixed model ANIP runtime usually follows this flow:

```text
user request
  -> compact ANIP capability profile
  -> small model planner
  -> deterministic plan validation
  -> invoke if safe
  -> fallback to stronger model if validation fails
  -> service-side enforcement either way
```

The smaller model can handle common routing, extraction, clarification, and invocation planning when the contract makes the task obvious. The runtime does not blindly trust that output. It validates the proposed plan against contract-derived metadata before invoking the service.

If the proposed plan is incomplete, unsafe, unsupported, outside the candidate set, or mismatched to the requested effect, the runtime escalates to the fallback model.

## What Is Validated Before Invocation

The fallback validator is intentionally deterministic. It uses contract metadata and the user request; it does not use benchmark expected answers.

Typical fallback triggers include:

- The selected capability was not discovered.
- The selected capability is outside the compact candidate set shown to the planner.
- The planner output is malformed or has non-object parameters.
- A required input is missing and the request contains concrete evidence that should have been resolved.
- The selected capability cannot produce the requested primary effect.
- The request appears write-adjacent but the selected capability is not approval-gated or otherwise allowed to stop safely.

Unsupported-effect requests are different. If the contract declares that a capability does **not** produce raw exports, external dispatch, raw model features, or direct mutations, a denial can be the correct governed outcome. That should not automatically trigger fallback.

## What Still Belongs To The Service

Mixed model execution is not the trust boundary.

The model can propose a capability and parameters. The runtime can validate whether that proposal is plausible enough to invoke. The service still owns the actual authority boundary:

- permission checks,
- purpose-bound delegation,
- approval grants,
- side-effect enforcement,
- input validation,
- denial and restriction behavior,
- audit and lineage.

This distinction matters. A stronger fallback model may produce a better plan, but it still must not be allowed to bypass service policy.

## Why This Is Different From Prompt-Only Routing

In a prompt-only setup, the agent often has to carry large amounts of hidden policy:

- which tools map to which business intent,
- which actions are preview-only,
- which actions require approval,
- which actor can see which data,
- which failures are recoverable,
- which requests must be denied.

That increases prompt size, reasoning burden, evaluation burden, and the model tier needed for reliable operation.

With ANIP, much of that structure is published by the service. The runtime can show the model a compact capability profile, ask for a plan, then validate the plan before execution. The model still reasons, but it reasons over a smaller and more explicit action space.

## SDK Support

ANIP `0.24.13` exposes planner fallback validation helpers across the runtime-utils packages for all supported SDK families:

| Language | Helper |
| --- | --- |
| Python | `validate_invocation_plan_for_fallback(...)` |
| TypeScript | `validateInvocationPlanForFallback(...)` |
| Go | `ValidateInvocationPlanForFallback(...)` |
| Java | `validateInvocationPlanForFallback(...)` |
| C# | `AgentConsumption.ValidateInvocationPlanForFallback(...)` |

These helpers are for agent runtimes and planners. Generated ANIP services remain responsible for enforcing the contract at invocation time.

## Where To Use It

Mixed model execution is useful when:

- most requests are bounded and repeatable;
- the capability set is discoverable and compact enough to route over;
- the service contract declares inputs, effects, approvals, and denials clearly;
- the runtime can escalate when the small model output is not grounded;
- the organization wants lower cost without moving authority into the model.

It is not a substitute for a stronger model when the work is genuinely ambiguous, open-ended, architectural, adversarial, or high-judgment. In those cases, escalation is the correct behavior.

## GTM Agent Example

The GTM Agent showcase is the first public ANIP example using runtime-native mixed model execution. It validates a `gpt-5.4-nano -> gpt-5.4-mini` lane against the GTM benchmark suite and hard-mode governance bank.

See:

- [Benchmarks](/docs/testing/benchmarks)
- [GTM Agent Showcase](/docs/showcases/gtm-agent/overview)
- [GTM Agent Testing](/docs/showcases/gtm-agent/testing)
