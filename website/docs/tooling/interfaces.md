---
title: Interfaces and Adapters
description: ANIP can generate and mount multiple service surfaces from one runtime.
---

# Interfaces and Adapters

One of ANIP's strongest practical arguments is that it does not force you to choose between an agent-native interface and the rest of your API ecosystem.

ANIP can sit at the center and expose additional surfaces:

- REST / OpenAPI
- GraphQL
- MCP

## Why this matters

That means one service implementation can produce:

- native ANIP for agent reasoning
- familiar interfaces for conventional clients
- MCP tools for tool-consuming model ecosystems

This reduces the normal "build it twice" problem.

## Important boundary

The translated surfaces are useful, but the native ANIP surface remains the strongest place for:

- delegation
- cost signaling
- side-effect posture
- structured execution governance
