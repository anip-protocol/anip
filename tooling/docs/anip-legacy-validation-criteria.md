# ANIP Legacy Validation Mode: Evaluation Criteria

## Purpose

This document defines how **Legacy Validation Mode** should evaluate existing
non-ANIP interfaces against the ANIP scenario-validation method.

The goal is not to attack legacy systems unfairly.

The goal is to answer a sharper question:

> Given a real execution scenario, what glue does this REST, GraphQL, or MCP surface still force the team to write?

That is what makes Legacy Validation Mode valuable.

## Core Principle

Legacy Validation Mode should remain honest.

It should not assume:

- ANIP always wins everything
- legacy systems are useless
- any non-ANIP surface automatically fails

Instead, it should ask:

1. what can this interface express directly
2. what can the agent know before acting
3. what still has to be rebuilt in wrappers, workflows, or tracing

That is the whole point.

## Legacy Validation Output

Legacy Validation Mode should use the same result states as ANIP Validation:

- `HANDLED`
- `PARTIAL`
- `REQUIRES_GLUE`

And it should produce the same core sections:

1. `Handled by the current interface`
2. `Glue you will still write`
3. `Glue category`
4. `Why`
5. `What would improve the result`

The difference is:

- in Legacy Validation Mode, the “improvement” section will often point toward
  missing execution semantics rather than small local design tweaks

## Shared Legacy Evaluation Questions

Every legacy interface should be judged against the same shared questions.

### 1. Can the interface expose decision-critical context before execution?

Examples:

- permissions before invoke
- side-effect posture
- rollback posture
- cost expectations
- approval expectations
- prerequisites

If not, the evaluator should identify:

- safety glue

### 2. Can the interface guide correct blocked-action behavior?

Examples:

- structured failure
- retry guidance
- escalation guidance
- grantable authority hints

If not, the evaluator should identify:

- orchestration glue

### 3. Can the interface preserve post-action traceability?

Examples:

- stable invocation identity
- caller correlation
- task grouping
- parent/child action lineage
- audit queryability

If not, the evaluator should identify:

- observability glue

### 4. Is the scenario outcome still mostly controlled by wrappers?

This is the most important legacy question.

If the agent must rely on:

- trial-and-error calls
- hard-coded policy wrappers
- custom retries
- custom escalation rules
- custom tracing

then the evaluator should lean toward:

- `PARTIAL`
- or `REQUIRES_GLUE`

## REST Evaluation Criteria

REST is often the strongest legacy surface operationally.

It is usually:

- stable
- explicit in payloads
- well-understood by developers
- easy to document

But standard REST surfaces usually do **not** directly encode ANIP-style
execution semantics.

### What REST often handles reasonably well

- discoverable resource and action surfaces
- request/response structure
- status codes
- domain-specific payloads
- general integration ergonomics

REST can sometimes score `PARTIAL` on simpler scenarios because the surface is
clear and predictable.

### What REST usually does not handle directly

- permission discovery before action
- side-effect posture as a first-class contract
- rollback posture as a first-class contract
- cost visibility as a first-class execution surface
- structured recovery semantics beyond app-specific errors
- first-class task identity and parent invocation lineage
- protocol-level audit queryability

### REST glue likely to appear

#### Safety glue

- permission probing wrappers
- budget checks outside the interface
- action safety wrappers around risky endpoints
- retry logic based on app-specific error parsing

#### Orchestration glue

- preflight endpoint sequences
- approval branches encoded outside the contract
- action sequencing wrappers

#### Observability glue

- correlation IDs
- trace stitching
- custom audit joins
- task reconstruction logic

### When REST might score `PARTIAL`

Use `PARTIAL` when:

- the service is well designed
- error payloads are reasonably structured
- some domain-specific control information is present
- but core execution semantics still live mostly outside the interface

### When REST should score `REQUIRES_GLUE`

Use `REQUIRES_GLUE` when:

- the scenario depends on pre-execution authority understanding
- the scenario depends on side-effect or cost reasoning
- the scenario depends on structured escalation or lineage
- the current surface requires wrapper logic for the core behavior

## GraphQL Evaluation Criteria

GraphQL is often strong for:

- flexible data retrieval
- joining domain data efficiently
- front-end integration
- schema introspection

But GraphQL usually does not solve execution-governance problems by itself.

### What GraphQL often handles reasonably well

- rich query surfaces
- typed schemas
- flexible data selection
- efficient data composition

GraphQL may perform well for:

- information-gathering scenarios
- planning steps
- read-heavy agent tasks

### What GraphQL usually does not handle directly

- governed action semantics
- permission discovery before mutations
- side-effect posture around mutations
- rollback posture
- cost semantics for actions
- structured recovery guidance
- durable invocation lineage
- audit queryability for action chains

### GraphQL glue likely to appear

#### Safety glue

- mutation wrappers
- permission probes outside the schema
- cost/budget guards outside the mutation contract

#### Orchestration glue

- mutation sequencing logic
- approval or escalation branches
- domain-specific “safe mutation” wrappers

#### Observability glue

- mutation correlation logic
- tracing around mutation chains
- separate audit/event systems to reconstruct action history

### When GraphQL might score `PARTIAL`

Use `PARTIAL` when:

- the scenario is mostly data gathering
- the interface gives enough planning context
- the risky action is not the core of the scenario

### When GraphQL should score `REQUIRES_GLUE`

Use `REQUIRES_GLUE` when:

- the scenario depends on mutation safety
- the scenario depends on structured blocked-action behavior
- the scenario depends on post-action lineage and auditability

## MCP Evaluation Criteria

MCP is different from REST and GraphQL because it is already closer to the
agent/tool interaction layer.

That means it can often do better than plain legacy HTTP surfaces for:

- tool discovery
- tool invocation
- agent compatibility

But MCP is still not the same thing as ANIP.

The real distinction is:

- MCP is primarily a tool-interoperability layer
- ANIP is trying to provide governed execution semantics

### What MCP often handles reasonably well

- tool discovery
- tool callability
- model-facing integration
- simple action execution

For narrow callable-tool scenarios, MCP may genuinely score well.

### What MCP usually does not handle directly

- explicit authority and delegation semantics
- permission discovery before invoke
- side-effect and rollback posture as first-class execution semantics
- cost semantics
- structured escalation/recovery guidance
- task identity and parent invocation lineage
- durable audit queryability
- checkpoint/trust posture

### MCP glue likely to appear

#### Safety glue

- permission wrappers around tools
- side-effect risk heuristics in prompts or wrappers
- retry logic driven by tool failures
- approval routing outside the protocol

#### Orchestration glue

- wrappers deciding whether a tool should be called
- planner/policy coordination outside the tool contract
- escalation logic in orchestration code

#### Observability glue

- tool-call correlation IDs
- external tracing
- workflow reconstruction from logs
- custom action history layers

### When MCP might score `PARTIAL`

Use `PARTIAL` when:

- the scenario is mainly about tool invocation
- the action is simple
- the missing control surfaces do not dominate the scenario outcome

### When MCP should score `REQUIRES_GLUE`

Use `REQUIRES_GLUE` when:

- the scenario depends on governed execution
- the scenario depends on safe blocked-action behavior
- the scenario depends on lineage continuity
- the scenario depends on post-action auditability

## Legacy Mode By Scenario Type

The legacy result should also vary by scenario type.

### Safety scenarios

Examples:

- over budget
- insufficient authority
- irreversible action

Legacy surfaces will often score:

- `PARTIAL`
- or `REQUIRES_GLUE`

because this is where missing pre-execution semantics hurt most.

### Orchestration scenarios

Examples:

- multi-step dependency
- retry vs escalate
- cross-service handoff

Legacy surfaces will often score:

- `REQUIRES_GLUE`

because orchestration glue is exactly what fills the semantic gap.

### Observability scenarios

Examples:

- reconstruct the task chain
- follow parent-child action flow
- query the action history

Legacy surfaces will often score:

- `REQUIRES_GLUE`

because this is usually where correlation, tracing, and audit stitching become
fully bespoke.

## Example Legacy Output Pattern

The output should be explicit and concrete.

Example:

```md
# Evaluation: search_then_book_across_services_with_budget_constraint

Mode: Legacy Validation
Surface: REST + GraphQL
Result: REQUIRES_GLUE

Handled by the current interface:
- domain data retrieval
- basic action invocation

Glue you will still write:
- you will still write permission probing between services here
- you will still write budget-enforcement logic in the booking path here
- you will still write cross-service correlation logic here
- you will still write trace stitching and audit reconstruction here
- you will still write retry and escalation routing here

Glue category:
- safety
- orchestration
- observability

Why:
- the interfaces expose callable operations and domain data, but not enough
  execution semantics for governed cross-service action

What would improve the result:
- add explicit authority and permission discovery
- add action posture and recovery semantics
- add first-class task and invocation lineage
- add protocol-level audit queryability
```

That is what makes the legacy comparison hit.

## The Strongest Legacy Comparison Question

Legacy Validation Mode should always drive back to this question:

> What is the interface forcing the team to rebuild outside the interface?

That is the right center of gravity.

Not:

- is REST bad
- is GraphQL incomplete
- is MCP weaker in the abstract

But:

- what glue is the current interface forcing into wrappers, workflows, and tracing systems?

That is the honest and useful comparison.

## Recommended Implementation Order

When Legacy Validation Mode is eventually implemented, the order should be:

1. REST criteria
2. MCP criteria
3. GraphQL criteria

Why:

- REST is the most familiar comparison for most teams
- MCP is the most strategically important comparison
- GraphQL is valuable, but usually more complementary than central in the ANIP story

## Final Summary

Legacy Validation Mode should evaluate REST, GraphQL, and MCP against the same
scenario truth layer.

It should:

- stay honest
- expose remaining glue directly
- separate what the current interface does well from what it still forces teams
  to rebuild

That is how Legacy Validation Mode becomes the eye-opener instead of just
another comparison chart.
