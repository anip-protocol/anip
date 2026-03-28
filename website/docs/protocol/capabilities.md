---
title: Capability Declaration
description: Capability declaration is the center of the ANIP contract.
---

# Capability Declaration

ANIP is capability-first, not endpoint-first.

A capability declaration tells an agent:

- the capability name
- what it does
- required inputs
- expected output shape
- side-effect type
- rollback posture
- cost hints
- required scope
- observability posture

## Why this matters

With REST, the agent often learns meaning from external docs or trial-and-error.

With ANIP, the service itself publishes the contract.

## Side-effect types

ANIP makes side effects explicit:

- `read`
- `write`
- `transactional`
- `irreversible`

This is one of the biggest differences from ordinary API descriptions. It lets an agent reason about risk before invoke.

## Capability graph

Capabilities can also declare prerequisites and composition hints, helping agents navigate a service without hand-authored instructions.
