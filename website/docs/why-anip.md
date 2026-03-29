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

## The problem

Agents do not fail safely.

Today, agents operate in a model that looks like this:

```
input → reasoning → tool call → execution
```

At the point of execution:

- **Cost is unknown** — the agent doesn't know what the action will consume until after it's charged
- **Permissions are implicit** — the agent discovers access limits by getting a 401 or 403
- **Side effects are hidden** — nothing in the interface distinguishes a read from an irreversible write
- **Failure is opaque** — when something goes wrong, the agent gets an error code with no guidance on how to recover

The system assumes the agent made the right decision. That assumption is wrong.

This is not a UX problem. This is a **control problem**.

## The gap

APIs describe *how* to call systems. They do not describe:

- What an action **means**
- What it **costs**
- Whether it is **reversible**
- Who is **allowed** to perform it
- How to **recover** if it fails

For humans, this context lives in documentation, intuition, and experience.

Agents have none of these.

MCP (Model Context Protocol) significantly improves tool discovery and transport standardization. It solves "how does an agent find and call tools?" with a clean protocol. But MCP does not address the execution context layer — no side-effect declaration, no permission discovery, no cost signaling, no delegation model, no structured failure recovery, no protocol-level audit.

The gap is between knowing *what tools exist* and knowing *what will happen when you use them*.

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
| **Cost** | What will this consume? Declared range before, actual cost after |
| **Authority** | Who is allowed to do this? Scoped delegation chains, not flat tokens |
| **Side effects** | What changes in the world? Read / write / transactional / irreversible |
| **Reversibility** | Can this be undone? Rollback window and compensation paths |
| **Resolution** | What to do if blocked? Who can grant authority, what's needed, how long |

This allows agents to:

- Reason before acting
- Avoid unsafe execution
- Recover from failure with structured guidance
- Escalate to a human when authority is insufficient

## More than tool interoperability

The real difference between MCP and ANIP is not transport or discovery. It is role.

**MCP is a tool-interoperability layer.** It helps a model discover and call tools.

**ANIP is a control layer between reasoning and execution.** It governs how execution boundaries move through an agent system — across planners, policy services, approval layers, execution workers, and audit infrastructure.

In simple systems, the model calls a tool and recovers from errors. In serious systems, there are delegation chains, narrowed authority, approval steps, policy mediation, and checkpointed evidence. ANIP isn't just a tool surface in those environments — it becomes part of the system that governs how agent actions are authorized, constrained, executed, and recorded.

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
