---
sidebar_position: 2
title: Why ANIP
description: Why agent-facing execution needs a protocol designed for agents, not just APIs for human developers.
---

# Why ANIP

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
