---
slug: execution-safety-agent-systems
title: "Execution Safety for Agent Systems"
authors: [anip]
tags: [security, architecture, trust]
---

Modern agent systems combine LLM-based reasoning, tool/API execution, and implicit system-level permissions. This creates a well-known class of vulnerability: the **confused deputy**.

The agent becomes a privileged intermediary that accepts untrusted input, makes decisions based on it, and executes actions with higher authority than it should have.

<!-- truncate -->

## The problem

Current tool and API interfaces provide:

- Input/output schemas
- Invocation mechanics

They do not provide:

- Execution constraints
- Authority boundaries
- Side-effect visibility
- Pre-execution validation

As a result, agents cannot reliably distinguish safe from unsafe actions. Execution decisions are made without sufficient context. Failures provide no structured recovery path.

## The failure model

Today's agent execution model looks like this:

```
untrusted input
    ↓
LLM reasoning
    ↓
tool invocation
    ↓
execution with system authority
```

No enforced boundary exists between reasoning, authorization, and execution.

### Consequences

- **Privilege escalation via prompt injection** — an injected instruction runs with the agent's full token authority
- **Unintended irreversible actions** — the agent cannot distinguish a read from a permanent state change
- **Inability to enforce least privilege** — tokens are valid-or-invalid, not purpose-scoped
- **No deterministic pre-execution validation** — the system trusts the agent's judgment, with no contract to check against

This is not hypothetical. It is inherent to the current model. The [Clinejection attack](/blog/clinejection-confused-deputy) demonstrated exactly this chain at production scale.

## The ANIP approach

ANIP introduces a pre-execution contract. Each action is described with:

- **Authority requirements** — who is allowed to perform this action, with what scope
- **Cost constraints** — what the action will consume, declared before execution
- **Side-effect classification** — read, write, transactional, or irreversible
- **Reversibility guarantees** — whether and how the action can be undone
- **Explicit failure and resolution paths** — what to do when blocked, who can grant authority

### The enforcement model

Execution becomes conditional:

```
reasoning
    ↓
contract evaluation
    ↓
authorization + constraint check
    ↓
execution (or denial with structured resolution)
```

The critical difference: the interface enforces the boundary, not the model. A prompt injection can still manipulate the agent's reasoning. But when the manipulated reasoning produces an action outside the delegation scope, the interface rejects it — deterministically, before execution, with a structured explanation of why.

## Security impact

ANIP enables:

- **Explicit separation between intent and authority** — the agent's reasoning produces intent; the delegation chain determines whether authority exists
- **Deterministic validation before execution** — scope, budget, and capability checks happen at the protocol level, not in application code
- **Structured handling of permission boundaries** — restricted and denied responses tell the agent what's missing and who can grant it
- **Reduction of confused deputy risk** — purpose-bound tokens limit blast radius even when the agent is compromised

## What ANIP is not

ANIP is not:

- An API replacement
- A tool registry
- An orchestration framework

It is a **control layer between reasoning and execution**.

## Why this matters now

As agents gain the ability to modify systems, move money, provision infrastructure, and operate CI/CD pipelines, execution safety becomes a requirement — not a feature.

The current model — hand an agent a token, hope it makes good decisions, log what happens after the fact — does not scale to autonomous systems with real blast radius.

The question is not whether agents will act. They already do. The question is whether the interfaces they act through can express and enforce the boundaries that make autonomous execution safe.

---

*ANIP is open source: [github.com/anip-protocol/anip](https://github.com/anip-protocol/anip). Read the [docs](https://anip.dev/docs/intro) or follow the [quickstart](https://anip.dev/docs/getting-started/quickstart).*
