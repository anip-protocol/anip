---
sidebar_position: 2
title: Why ANIP
description: Why agent-facing execution needs a protocol designed for agents, not just APIs for human developers.
---

# Why ANIP

ANIP is the governance, trust, and lineage layer for agent actions.

Every interface paradigm changed when the primary consumer changed:

- CLI for humans at terminals
- GUI for humans with screens and mice
- API for programs written by humans
- ANIP for **AI agents**

The shift is not about complexity. It is about who is on the other side.

## The problem with today's default stack

When agents use REST APIs directly, they often discover important constraints too late:

- auth by getting a 401
- missing permission by getting a 403
- cost after being charged
- irreversibility after the action has already happened
- audit posture only if someone thought to add a separate endpoint

MCP improves discovery and tool transport, but it still does not make authority, cost, rollback posture, and recovery first-class protocol primitives.

## Governance, trust, and lineage

ANIP is designed for systems where agent actions need to stay governable,
trustworthy, and traceable.

- governable: the interface can express authority, boundaries, approvals, and what happens when authority is insufficient
- trustworthy: manifests, delegation, checkpoints, and later attestation can move systems beyond pure trust-on-declaration
- traceable: actions remain connected to their origin, authority, and downstream effects through lineage and audit

That is why ANIP is strongest in environments where execution has real
consequences, not just convenient tool invocation.

## The missing middle

There is a missing middle between "just trust the service" and overly heavy
trust infrastructure.

ANIP explores that middle path through:

- signed delegation
- signed manifests
- anchored checkpoints
- later, stronger attestation and federated trust

The goal is not to turn ANIP into a blockchain project. The goal is to make
agent execution more verifiable without making adoption unrealistic.

## More than tool interoperability

MCP is a tool-interoperability layer. ANIP can also act as an agent
control-plane protocol.

That matters in systems with:

- planners
- policy services
- approval layers
- execution workers
- audit infrastructure

In those environments, the key question is not only whether a model can call a
tool. It is how authority, policy, side effects, cost, lineage, and audit move
through the system.

## What ANIP changes

ANIP makes the agent-facing contract explicit.

At minimum, ANIP defines:

- capability declaration
- delegation and scoped authority
- permission discovery
- structured failures
- side-effect typing

And in the broader ecosystem, ANIP also adds:

- audit logging
- signed manifests and JWKS
- checkpoints and trust posture
- transport-neutral bindings
- inspection tooling

## What this unlocks

ANIP is strongest where execution has consequences:

- travel booking
- finance ops
- approvals
- DevOps and infrastructure changes
- policy-governed orchestration

In those environments, the important question is not "can the model call the tool?" It is:

- what is the model allowed to do
- what will happen if it acts
- how much will it cost
- who can fix a block
- how do we verify what happened later

That is the space ANIP is designed to occupy.
