---
sidebar_position: 2
title: Why ANIP
description: Why agent-facing interfaces need a protocol designed for agents, not just APIs for human developers.
---

# Why ANIP

Every major interface paradigm emerged when the dominant consumer changed:

| Interface | Consumer | Era |
|-----------|----------|-----|
| CLI | Humans at terminals | 1970s-80s |
| GUI | Humans with screens and mice | 1980s-2000s |
| API | Programs written by humans | 2000s-2020s |
| **ANIP** | **AI agents** | **Now** |

Each shift wasn't a new format — it was a new set of assumptions about who is on the other end. That shift is happening again. The primary consumer of digital services is becoming an AI agent.

## What's wrong with today's stack

When agents use REST APIs directly, they operate blind:

**Authentication**: The agent doesn't know auth is required until it gets a `401`. It doesn't know what kind of auth (API key? OAuth? OIDC?) until it parses error messages or reads docs — which it may not have access to.

**Permissions**: The agent doesn't know what it's allowed to do until it tries and gets a `403`. It can't ask "what can I do?" without attempting each action and cataloging failures.

**Cost**: The agent doesn't know what an action will cost until after it's been charged. There's no standard way for a service to say "this will cost approximately $420."

**Side effects**: The agent can't distinguish a read from an irreversible write. HTTP methods (GET/POST/PUT/DELETE) are conventions, not enforced contracts. A POST might be read-only; a DELETE might be reversible.

**Recovery**: When something fails, the agent gets an HTTP status code and maybe a message. There's no structured guidance — who can fix the problem, what's needed, how long it will take.

## Where MCP fits — and where it stops

MCP (Model Context Protocol) is a significant improvement for tool discovery and transport standardization. It solves the problem of "how does an agent find and call tools?" with a clean, well-designed protocol.

But MCP does not address the execution context layer:

- No side-effect declaration — an agent can't distinguish read from write tools
- No permission discovery — agents learn access by failing
- No cost signaling — no way to declare or return cost information
- No delegation model — no scoped authority beyond basic auth
- No structured failure recovery — error codes without resolution guidance
- No audit — no protocol-level logging of what happened

ANIP is not a competitor to MCP. ANIP services can mount an MCP adapter alongside native ANIP, exposing the same capabilities through both protocols. MCP handles tool interoperability; ANIP handles execution governance.

## The missing middle

There's a gap between "just trust the service" and heavyweight trust infrastructure (blockchains, zero-knowledge proofs).

ANIP explores the practical middle ground:

- **Signed manifests**: Service claims are cryptographically signed, so agents can verify authenticity
- **Delegation chains**: Authority flows through verifiable JWT chains, not opaque tokens
- **Audit checkpoints**: Merkle trees provide tamper-evident execution history
- **Trust posture**: Services declare their trust level (declarative → signed → anchored), so agents can adjust their reliance

The goal is not absolute trust. The goal is making agent execution progressively more verifiable without making adoption unrealistic.

## Where ANIP is strongest

ANIP adds the most value where execution has real consequences:

- **Financial operations**: Budget-bound delegation, cost signaling, irreversibility declarations
- **Infrastructure changes**: Side-effect typing, rollback posture, transactional semantics
- **Approval workflows**: Permission discovery, delegation chains, audit trails
- **Multi-agent orchestration**: Scoped authority, lineage tracking, verifiable execution history

In these environments, the important question is not "can the model call the tool?" It is:

- What is it allowed to do?
- What will happen if it acts?
- How much will it cost?
- Who can fix a block?
- How do we verify what happened later?

That is the space ANIP is designed to occupy.
