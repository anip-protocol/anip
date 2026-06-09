---
title: Architecture
description: Runtime architecture of ANIP from agent consumers through governed services to downstream systems.
---

# Architecture

ANIP is an agent-facing service architecture.

It sits between consumers that want to act and downstream systems that can perform real work. The core architectural boundary is the ANIP service: agents discover governed capabilities, request authority, check availability, invoke work, and receive structured outcomes. The service owns the behavior contract and decides how to execute safely downstream.

## Runtime Shape

```mermaid
flowchart LR
  subgraph Consumers[Upstream consumers]
    Agent[Agent runtime]
    App[Application / workflow]
    MCPClient[MCP client]
    CI[CI / verifier]
  end

  subgraph ANIP[ANIP service boundary]
    Discovery[Capability discovery]
    Manifest[Signed manifest]
    Auth[Delegation + permission check]
    Invoke[Governed invoke]
    Policy[Policy, approval, input resolution]
    Audit[Audit + lineage + checkpoints]
  end

  subgraph Downstream[Downstream execution]
    API[REST / GraphQL / SDK]
    Data[SQL / warehouse / semantic layer]
    SaaS[SaaS platform]
    Internal[Internal service]
    MCP[MCP backend]
  end

  Agent --> Discovery
  App --> Discovery
  MCPClient --> Discovery
  CI --> Manifest
  Discovery --> Manifest
  Manifest --> Auth
  Auth --> Invoke
  Invoke --> Policy
  Policy --> API
  Policy --> Data
  Policy --> SaaS
  Policy --> Internal
  Policy --> MCP
  Invoke --> Audit
  Policy --> Audit
```

## Upstream Side

Upstream consumers are not expected to reverse-engineer product behavior from raw APIs.

They need to discover:

- Which governed capabilities exist.
- Which actor and scope can use them.
- Which inputs are required, defaulted, backend-resolved, app-selected, or clarification-required.
- Which capability is read-only, write, transactional, or irreversible.
- Which action is available, restricted, denied, approval-required, or clarification-required before execution.
- Which recovery path exists when execution cannot proceed.
- Which package, manifest, and contract produced the capability surface.

ANIP exposes that through service discovery, manifests, permission checks, structured invocation, structured failures, audit, lineage, and package trust.

## Service Boundary

The ANIP service is the authority boundary.

It owns:

- Capability declarations and side-effect posture.
- Input-resolution behavior.
- Delegation and permission checks.
- Approval grants and continuations.
- Denial, restriction, clarification, and recovery behavior.
- Cross-service lineage and task identity.
- Audit records and optional checkpoints.
- Manifest and package truth.
- Runtime implementation seams.

The service may be generated from a package, hand-written against ANIP runtimes, or generated with reviewed custom bundles. That implementation choice must not change the public contract exposed to agents.

## Downstream Side

Downstream systems are implementation details.

An ANIP service can call:

- Native REST APIs.
- GraphQL APIs.
- SaaS SDKs.
- SQL databases or warehouses.
- Semantic layers such as dbt, Cube, or Superset datasets.
- Internal service gateways.
- MCP servers when they are the practical backend adapter.

The downstream shape should not leak as the agent-facing product contract. For example, a Slack backend may expose `chat.postMessage`, but the ANIP capability should be closer to `slack.channel_announcement.request` or `slack.approved_message.send` so preview, approval, allowed channels, denial, and audit are first-class.

## Transport And Interface Surfaces

ANIP services can expose the same governed capability contract through multiple surfaces:

| Surface | Role |
|---------|------|
| Native ANIP over HTTP | Default network service interface. |
| Native ANIP over stdio | Local subprocess interface for agent clients and developer tools. |
| Native ANIP over gRPC | High-performance internal platform interface where supported. |
| Generated REST / GraphQL / MCP interfaces | Compatibility surfaces derived from the same capability declarations. |

Generated REST, GraphQL, and MCP interfaces are client-facing surfaces. They are not backend adapters. Backend integration belongs in service implementation seams or custom bundles.

## Invocation Flow

```mermaid
sequenceDiagram
  participant Agent
  participant ANIP as ANIP Service
  participant Policy as Policy / Approval / Resolution
  participant Backend as Downstream System
  participant Audit

  Agent->>ANIP: Discover capabilities + manifest
  Agent->>ANIP: Request or present delegation token
  Agent->>ANIP: Check permissions for intended capability
  Agent->>ANIP: Invoke capability with context
  ANIP->>Policy: Resolve inputs, scope, side effects, approvals
  alt available
    ANIP->>Backend: Execute bounded downstream operation
    Backend-->>ANIP: Result
    ANIP->>Audit: Record invocation + lineage + cost
    ANIP-->>Agent: available result
  else clarification required
    ANIP->>Audit: Record governed stop
    ANIP-->>Agent: clarification_required + missing context
  else approval required
    ANIP->>Audit: Record approval stop + preview
    ANIP-->>Agent: approval_required + continuation
  else restricted or denied
    ANIP->>Audit: Record restriction or denial
    ANIP-->>Agent: structured failure + recovery guidance
  end
```

## Trust Boundary

The public ANIP contract includes:

- Capability IDs, descriptions, and side-effect posture.
- Inputs, allowed values, input resolution, and clarification behavior.
- Required scopes and delegation posture.
- Approval, denial, restriction, and recovery behavior.
- Composition and cross-service handoff hints.
- Audit and lineage expectations.
- Manifest, package, lock, and receipt metadata.
- Optional immutable implementation-material references.

The public contract should not include:

- Secret values.
- Local filesystem paths.
- Machine-local Studio links.
- Raw backend tokens.
- Private source documents.
- Hidden prompt instructions.
- Generated implementation shortcuts that mutate manifest shape.

## What Changes And What Does Not

The downstream backend can change without changing the agent-facing capability contract.

```text
slack.channel_announcement.request
```

can be implemented with Slack Web API, an internal messaging gateway, or a future MCP backend. The behavior contract remains: prepare, preview, require approval, send only with a valid grant, and audit the result.

That is the core ANIP architecture:

- Consumers discover and invoke governed capabilities.
- ANIP services own the execution contract.
- Downstream systems perform bounded implementation work.
- Tooling packages, generates, verifies, and distributes the contract, but it is not required at runtime.
