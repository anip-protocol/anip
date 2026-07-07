---
sidebar_position: 2
title: Why ANIP
description: Why autonomous systems need a control layer between reasoning and execution.
---

# Why ANIP

Software interfaces were never designed for autonomous systems.

| Interface | Built for | Era |
|-----------|----------|-----|
| CLI | Humans at terminals | 1970s-80s |
| GUI | Humans with screens and mice | 1980s-2000s |
| API | Programs written by humans | 2000s-2020s |
| **ANIP** | **Systems that act autonomously** | **Now** |

Each shift wasn't a new format — it was a new set of assumptions about who is on the other end. GUIs assumed someone could see a screen. APIs assumed a developer read the docs and wrote deterministic code.

Agents assume neither. They reason at runtime, under delegated authority, with incomplete information, around actions that have real consequences.

## The UI replacement trap

The current agent stack is often trying to use MCP as a replacement for product UIs.

That is understandable, but it exposes a hidden architectural problem.

In many products, the API was never the full product interface. The API exposed primitive operations:

- create record
- update status
- post message
- run query
- transition workflow
- fetch page

The **UI** stitched those primitives into a safe human workflow:

- which fields are required
- which defaults are applied
- which transitions are allowed
- which actions need confirmation
- which data is visible to this user
- which steps must happen before mutation
- what warning or recovery path appears when the action is unsafe

When an agent bypasses the UI and receives only raw tools, those workflow semantics do not automatically move with it.

Teams compensate by writing consumer-side skills, recipes, prompt instructions, and framework glue:

```text
If the user asks for X, call tool A, then B.
Never call C unless D is true.
Ask for approval before posting to this channel.
Only use this project unless the user says otherwise.
If the API returns 403, ask the manager.
```

Shared skill or recipe repositories make that easier to distribute, but they do not fix the authority problem. The behavior still lives on the consumer side, where it is advisory. It can be incomplete, stale, contradicted by another instruction, bypassed by prompt injection, or simply misapplied by the model.

This is the wrong place for production execution policy.

The service should own the workflow semantics.

ANIP is designed for that: a service-owned interface for agents, analogous to what a GUI is for humans, but built for systems that act. Instead of teaching every agent how to safely operate a product, the service exposes governed capabilities with bounded inputs, declared side effects, permission posture, approval requirements, denial behavior, audit obligations, and recovery guidance.

Browser and computer-use systems show the same pressure from another direction. Projects such as [OpenClaw](https://docs.openclaw.ai/browser) give agents browser automation because the human UI carries workflow semantics that raw APIs often do not. That can be useful as a bridge, especially when no better integration exists. But it is also a sign that the real agent interface is missing. Human UIs are optimized for visual perception, clicks, layout, and human judgment. They are not stable, typed, governed, verifiable contracts for delegated autonomous execution.

ANIP is the agent-native version of that missing interface.

## The real problem

The workflow moved to the wrong side of the boundary.

Today, many agent systems operate in a model that looks like this:

```
user intent → model reasoning → skill / recipe → raw tool call → execution
```

That model asks the consumer to reconstruct behavior the service used to own.

At the point of execution, the service often sees only a low-level operation:

- create this record
- update this field
- send this message
- run this query
- transition this workflow

But the missing question is the one that matters:

**Is this governed action allowed, safe, approved, auditable, and recoverable for this actor and purpose?**

Without a service-owned contract, the answer is spread across prompts, skills, app glue, local policy, and model judgment.

That creates predictable failure modes:

- **Cost is unknown** — the agent doesn't know what the action will consume until after it's charged
- **Authority is implicit** — the agent discovers access limits by getting a 401 or 403, or by following consumer-side rules
- **Side effects are advisory** — tool descriptions or hints may say what should happen, but the workflow policy is not necessarily enforced as a contract
- **Approval is bolted on** — the agent may be instructed to ask, but the service may not expose approval as a first-class continuation
- **Failure is opaque** — when something goes wrong, the agent gets an error code or tool error with no portable recovery path
- **Policy is overrideable** — prompt injection, stale skills, conflicting recipes, or hallucinated steps can redirect behavior

The system assumes the agent and its local instructions reconstructed the service workflow correctly.

That assumption is wrong.

This is not just an agent reliability problem. It is a **service-boundary problem**.

## Workflow frameworks are also compensation

Many agent frameworks have identified the same problem and offer workflow graphs, recipes, orchestration steps, tool routers, policy hooks, and guardrails.

Those are useful engineering tools. They can make one application safer.

But they are still compensation when the workflow logic lives outside the service:

- The rules are consumer-owned, not service-owned.
- The same service may be wrapped differently by every agent app.
- The behavior is not portable across clients, teams, or runtimes.
- The service cannot reliably audit the intended governed action, only the backend operation it receives.
- The contract between "what the agent thinks it is doing" and "what the service is allowed to do" remains implicit.

Framework workflows can coordinate execution. They should not be the authority boundary for execution.

ANIP does not remove the need for orchestration. It changes what orchestration operates on. Instead of composing raw tools and local recipes, the agent composes service-owned governed capabilities.

## It also changes the cost profile

When workflow semantics live in prompts, skills, recipes, and framework glue, the model has to reason through more policy on every request:

- Which tool maps to this intent?
- Which workflow order is safe?
- Which hidden rule applies?
- Which missing field should be clarified?
- Which action needs approval?
- Which failure is recoverable?
- Which data scope is allowed?

That increases prompt size, planning complexity, evaluation burden, and often the model tier required for reliable behavior.

With ANIP, the service carries more of that structure directly in the contract:

- capabilities are bounded
- inputs declare resolution behavior
- permissions are discoverable
- approval is a structured outcome
- failures include recovery guidance
- audit and verification are protocol surfaces

The model still reasons, but it reasons over a smaller, governed action space. That can reduce the amount of prompt choreography needed and make it practical to use smaller, cheaper models for bounded execution.

This is not theoretical. The GTM Agent showcase uses generated ANIP services across five languages and runs the agent layer with `gpt-5.4-mini` against a large question bank because the contract and services carry much of the execution structure that would otherwise have to live in the prompt.

The newer mixed-mode runtime path goes further: it can start with `gpt-5.4-nano` and fall back to `gpt-5.4-mini` when deterministic ANIP contract validation says the smaller model's plan is not grounded enough. See [Mixed Model Execution](/docs/concepts/mixed-model-execution) and [Benchmarks](/docs/testing/benchmarks).

## The gap

APIs and tool protocols describe *how* to call systems. They do not, by themselves, define the governed execution contract:

- What an action **means**
- What it **costs**
- Whether it is **reversible**
- Who is **allowed** to perform it
- How to **recover** if it fails

For humans, this context lives in documentation, product UI, intuition, and experience.

Agents have none of these.

MCP (Model Context Protocol) significantly improves tool discovery and transport standardization. It solves "how does an agent find and call tools?" with a clean protocol, and it includes useful tool metadata such as advisory annotations. But MCP does not make product workflow semantics a portable governed execution contract: permission discovery, purpose-bound delegation, approval grants, cost signaling, structured recovery, protocol-level audit, and package verification remain outside the core tool-call contract.

The gap is between knowing *what tools exist* and knowing *what governed action is allowed to happen when you use them*.

## What ANIP changes

ANIP defines a contract before execution happens.

Instead of:

```
call → fail → retry blindly
```

Agents can:

```
understand → evaluate → decide → act (or not)
```

Each action is described with:

| Before execution | What ANIP provides |
|-----------------|-------------------|
| **Capability** | What governed action is available? Service-owned capability declarations, not consumer-side recipes |
| **Inputs** | What information is required? Required fields, defaults, omission behavior, clarification rules, and resolver references |
| **Cost** | What will this consume? Declared range before, actual cost after |
| **Authority** | Who is allowed to do this? Scoped delegation chains, not flat tokens |
| **Side effects** | What changes in the world? Read / write / transactional / irreversible |
| **Approval** | Does this require a human or delegated approval? Structured `approval_required` outcomes and approval grants |
| **Reversibility** | Can this be undone? Rollback window and compensation paths |
| **Resolution** | What to do if blocked? Who can grant authority, what's needed, how long |
| **Audit** | What evidence is recorded? Invocation lineage, actor context, purpose, grants, outcomes, and checkpoints |
| **Verification** | Can the client trust what it discovered? Signed manifests, lock files, package digests, and verifier checks |

This allows agents to:

- Reason before acting
- Avoid unsafe execution
- Recover from failure with structured guidance
- Escalate to a human when authority is insufficient
- Use the service's declared capabilities instead of inventing or importing hidden workflows
- Produce audit evidence that matches the governed action, not just the backend API call

The important shift is that the service publishes the agent-facing product contract. A client may still use skills, prompts, workflows, or MCP adapters for ergonomics, but those layers consume the contract. They do not become the authority boundary.

## More than tool interoperability

The real difference between MCP and ANIP is not transport or discovery. It is role.

**MCP is a tool-interoperability layer.** It helps a model discover and call tools.

**ANIP is a control layer between reasoning and execution.** It governs how execution boundaries move through an agent system — across planners, policy services, approval layers, execution workers, and audit infrastructure.

In simple systems, the model calls a tool and recovers from errors. In serious systems, there are delegation chains, narrowed authority, approval steps, policy mediation, and checkpointed evidence. ANIP isn't just a tool surface in those environments — it becomes part of the system that governs how agent actions are authorized, constrained, executed, and recorded.

For a more concrete comparison across MCP, skills, native APIs, and ANIP fronting, see [ANIP vs MCP](/docs/concepts/anip-vs-mcp).

## Where it matters most

ANIP adds the most value where execution has real consequences:

- **Financial operations** — budget-bound delegation, cost signaling, irreversibility
- **Infrastructure changes** — side-effect typing, rollback posture, transactional semantics
- **Approval workflows** — permission discovery, delegation chains, audit trails
- **CI/CD and security** — purpose-bound authority, confused deputy prevention
- **Multi-agent orchestration** — scoped authority, lineage tracking, verifiable execution

As agents move from answering questions to taking actions, the interface between reasoning and execution becomes critical. Without it, systems remain unsafe, failures remain opaque, and autonomy remains unreliable.

## Adoption is incremental

ANIP does not require the full trust stack on day one:

1. **Start with capabilities** — declare what the service does, side effects, costs, structured failures. This alone is more useful than raw API access.
2. **Add delegation** — scoped JWT tokens, permission discovery. Purpose-bound agent access.
3. **Add trust** — signed manifests, JWKS, audit logging. Verifiable service claims.
4. **Add anchoring** — Merkle checkpoints, external anchoring. Tamper-evident evidence for compliance.

A lightweight ANIP service is still a valid ANIP service. Stronger trust is layered on top as deployment requirements grow.

## ANIP is that interface

The world is not going to stop deploying agents. The question is whether we give them interfaces that can express and enforce execution boundaries — or keep handing them tokens and hoping for the best.

ANIP is the control layer between reasoning and execution.
