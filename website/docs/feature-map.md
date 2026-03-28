---
sidebar_position: 3
title: Feature Map
description: A high-level map of the protocol, transports, adapters, tooling, and ecosystem pieces that ANIP currently includes.
---

# Feature Map

This page is the fast inventory of what ANIP includes today.

## Protocol primitives

Core protocol features:

- capability declaration
- side-effect typing
- delegation DAG and scoped JWT authority
- permission discovery
- structured failure semantics

Contextual protocol features:

- cost signaling
- capability graph
- state and session semantics
- observability contract

## Trust and verification

ANIP includes:

- signed manifests
- JWKS exposure
- audit logs
- Merkle checkpoints
- trust posture in discovery

## Transports

ANIP currently has real bindings for:

- HTTP
- stdio
- gRPC

See [Transports](./transports/overview.md).

## Runtime and interface ecosystem

ANIP ships:

- TypeScript runtime and adapters
- Python runtime and adapters
- Java runtime and adapters
- Go runtime
- C# runtime

And interface surfaces for:

- REST / OpenAPI
- GraphQL
- MCP

## Tooling

Current tooling includes:

- ANIP Studio
- conformance suite
- contract-testing harness
- showcase applications

## Releases

The current protocol line is **v0.11**.

Highlights across recent versions:

- `v0.6` streaming invocations
- `v0.7` discovery posture
- `v0.8` security hardening
- `v0.9` audit aggregation
- `v0.10` horizontal scaling
- `v0.11` runtime observability

See [Version History](./releases/version-history.md).
