---
sidebar_position: 1
title: Introduction
description: What ANIP is, why it exists, and what it changes for agent execution.
---

# ANIP

ANIP stands for **Agent-Native Interface Protocol**.

It exists to answer a problem REST, OpenAPI, and MCP do not solve on their own: an agent can call a tool or endpoint, but still not know enough about the **execution boundary** before it acts.

ANIP makes that boundary explicit.

Before an agent invokes a capability, ANIP can tell it:

- what the capability does
- whether it is read, write, transactional, or irreversible
- what scope or delegated authority is required
- whether permission is available, restricted, or denied
- what the action is likely to cost
- what happens if the action fails
- whether the action will be logged and verifiable later

That changes the role of the interface. Instead of "make a call and see what happens," the agent can reason before acting.

## What ANIP is not

ANIP is not:

- a replacement for HTTP
- a replacement for gRPC
- a replacement for MCP
- a wrapper around GUI automation

ANIP is the **protocol layer** that makes agent execution legible and governable across transports.

## What ships today

ANIP already includes:

- multi-language runtimes across TypeScript, Python, Java, Go, and C#
- transport bindings for HTTP, stdio, and gRPC
- interface adapters for REST, GraphQL, and MCP
- ANIP Studio for inspection and invocation
- conformance and contract-testing tooling
- showcase applications across travel, finance, and DevOps

## Start here

- Read [Why ANIP](./why-anip.md) for the framing.
- Read [Feature Map](./feature-map.md) for the full surface.
- Go to [Install](./getting-started/install.md) if you want to run code.
- Go to [Quickstart](./getting-started/quickstart.md) if you want the smallest real service.
