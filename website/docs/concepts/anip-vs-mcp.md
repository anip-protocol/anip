---
title: ANIP vs MCP
description: How ANIP and MCP relate, where each belongs, and why governed execution should not live in prompts or skill files.
---

# ANIP vs MCP

ANIP and MCP solve different problems.

MCP standardizes how agents discover and call tools. ANIP defines the governed execution contract for what those tools or services are allowed to do.

The short version:

```text
MCP exposes what can be called.
ANIP defines what is allowed to happen.
```

They are complementary. MCP is useful interoperability infrastructure. ANIP is the behavior and governance layer that should sit between agent reasoning and consequential execution.

## Core distinction

| Question | MCP | ANIP |
|----------|-----|------|
| What does the agent discover? | Callable tools with schemas and annotations | Governed capabilities with inputs, outcomes, authority, side effects, recovery, and audit posture |
| How does an agent invoke work? | Tool invocation is a primary concern | Governed invocation semantics are a primary concern |
| What authority does the caller have? | OAuth/resource authorization can secure access to MCP servers; business authority is usually outside the tool schema | First-class delegation, permission discovery, approval grants, and actor-scoped execution |
| What side effects can happen? | Tool annotations can provide advisory hints such as read-only, destructive, idempotent, and open-world | Contract side-effect posture tied to permission, approval, audit, and verification |
| What requires approval? | Usually host/client UX, workflow, skill, or backend-specific policy | Part of the service-side contract and continuation flow |
| What must be denied or restricted? | Usually backend-specific or host/client policy | Declared and enforced by the ANIP service with structured outcomes |
| How should missing context be handled? | Elicitation can request structured user input; broader resolution semantics are application-specific | Structured clarification and input resolution attached to capability inputs |
| How is execution audited? | Usually outside the tool protocol surface | First-class audit, lineage, and checkpoint model |
| What can be packaged and verified? | Tool schemas, annotations, and server behavior vary by implementation | Signed packages, locks, receipts, verifier checks |

MCP gives the model a usable tool interface. ANIP gives the organization a governed execution boundary.

## What MCP already gives you

MCP is not just a list of function names. Modern MCP includes useful protocol surfaces:

- Tool discovery and invocation.
- Tool input and output schemas.
- Tool annotations such as read-only, destructive, idempotent, and open-world hints.
- OAuth-based authorization for HTTP transports.
- Elicitation for structured user input.
- Sampling and task-related protocol features.

Those are valuable. They make tool interoperability much better than every agent framework inventing its own connector format.

The distinction is that MCP describes a callable tool surface and supporting interaction primitives. It does not, by itself, define a portable, signed, service-owned contract for business authority, approval policy, denial policy, audit obligations, input-resolution posture, scenario validation, and implementation conformance.

That is the layer ANIP is designed to provide.

## Why MCP alone is not enough

Raw tool access is not the same as governed behavior.

An MCP server may expose operations such as:

- `create_issue`
- `update_issue`
- `transition_issue`
- `post_message`
- `execute_sql`
- `generate_chart`

Those operations may be callable, but the agent still needs to know:

- Is this actor allowed to do this in this project, channel, repository, dataset, workspace, or customer scope?
- Is the user asking for enough context, or should the service clarify before anything happens?
- Is a missing value safe to default, derived from actor policy, resolved by the backend, or selected by the app?
- Is this a read, a harmless draft, a write, a transactional change, or an irreversible action?
- Is the safe next step a preview, a prepared change, an approval request, or a committed operation?
- Does execution require stronger delegation, a human approval grant, a bound quote/reference, or an enforceable cost ceiling?
- Should the service deny the request, restrict the result, or require the direct human principal instead of a delegated agent?
- If execution fails, can the agent retry, wait, refresh stale state, revalidate a binding, ask for broader scope, or stop permanently?
- If this is part of a workflow, what is the approved next capability to refresh, verify, compensate, or continue the task?
- How should this invocation be tied to the larger task, parent invocation, and upstream service so the audit trail is coherent?
- What cost was declared before execution, what cost actually happened, and did it stay within the delegated budget?
- What evidence must be recorded so a reviewer can later understand who acted, under what authority, against which contract?
- How can a consumer verify the package, lock, manifest signature, implementation bundle, generated service, and scenario-test evidence?
- What happens when the backend technically allows something but the organization, policy, or product contract does not?

Those are not just "better descriptions." They are execution semantics. If they live in prompts, skills, tool descriptions, or scattered workflow glue, the system remains fragile. The model may follow the instructions, but the instructions are not the authority boundary.

ANIP moves that boundary to the service side by making those answers part of the capability contract: permissions, input resolution, side-effect posture, approvals, denials, recovery, lineage, cost, audit, package trust, implementation material, and scenario validation.

## Where skills fit

Skills can still be useful. They may provide task affordances, examples, UI guidance, or workflow convenience.

They should not be the primary place for:

- authority
- approval requirements
- denial rules
- data-scope restrictions
- side-effect policy
- audit obligations
- implementation truth

A practical framing:

```text
Use MCP as the pipe.
Use skills as optional task affordances.
Use ANIP as the governed execution contract.
```

## Jira example

A raw Jira tool surface might expose:

- search issues
- create issue
- update issue
- transition issue
- add comment

That is useful, but it is not a governed product interface.

An ANIP fronting service should expose capabilities such as:

```text
jira.incident_bug.prepare
jira.story.prepare
jira.workflow_transition.request
jira.triage_comment.prepare
jira.team_backlog.search
```

The ANIP service can then own:

- required fields
- allowed projects
- allowed issue types
- actor-specific team scope
- approval before status transition
- denial of direct transition to terminal states
- clarification when severity or impact is missing
- audit records for prepared and approved changes

The agent does not need a large skill file teaching it Jira etiquette. It selects from governed Jira capabilities.

## Slack example

Slack is a strong example because raw posting capability is operationally sensitive.

A raw tool might allow:

```text
chat.postMessage
conversations.history
conversations.list
```

A governed ANIP surface should instead expose:

```text
slack.channel_context.search
slack.incident_update.prepare
slack.channel_announcement.request
slack.approved_message.send
```

That allows the service to enforce:

- allowed channel lists
- preview-before-send behavior
- explicit approval grants for posting
- actor and workspace policy
- denied posting to restricted channels
- audit records with message, channel, actor, and grant identifiers

The important difference is not that the backend is Slack. The difference is that posting is a governed behavior, not a raw tool call.

## Superset example

Analytics systems make the distinction especially clear.

Raw Superset access may expose dataset discovery, chart generation, dashboard updates, and SQL execution. Exposing `execute_sql` directly to an agent is usually too broad for a governed capability boundary.

A better ANIP surface is:

```text
superset.analytics.discover_context
superset.analytics.answer_question
superset.chart.preview.create
superset.chart.publish.request
superset.dashboard.draft.prepare
superset.dataset.draft.prepare
```

The ANIP service should declare:

- raw SQL from agents is not accepted
- provider-owned semantic execution is used behind the boundary
- allowed datasets, metrics, dimensions, and grain are bounded
- chart creation defaults to preview
- publishing requires approval
- exports and high-grain results can be restricted

This is safer than wrapping a broad SQL execution tool and hoping the model stays within policy. The capability should describe the governed analytics behavior, not the backend tool.

## Architecture patterns

ANIP does not require MCP.

### Native API fronting

This is usually the best production default.

```text
Agent or application
  -> ANIP service
  -> native REST, GraphQL, SQL, SDK, semantic layer, or internal API
```

Benefits:

- fewer layers
- direct observability
- clearer auth and policy integration
- stronger control over payload shaping
- easier testing and deployment

### ANIP exposed as MCP

This is useful when clients already speak MCP.

```text
MCP client
  -> ANIP-as-MCP server
  -> ANIP capability runtime
  -> backend implementation
```

The client still sees MCP tools, but those tools are ANIP capabilities rather than raw backend operations.

### ANIP in front of an MCP backend

This can be useful for prototyping or when an MCP server already provides valuable orchestration.

```text
Agent or application
  -> ANIP service
  -> MCP backend server
  -> target system
```

This should not be the default enterprise architecture. It means ANIP is consuming an agent-oriented tool abstraction as its backend. That can work, but native APIs are often cleaner when available.

## Decision guide

Use MCP when:

- you need a standard way for existing MCP clients to discover and call tools
- your ecosystem already speaks MCP
- you want local tool interoperability
- you want a compatibility layer for model clients and IDE/desktop tooling
- the tool surface is low-risk enough that advisory hints and backend enforcement are sufficient

Use ANIP when:

- you want agents to discover governed capabilities, not raw backend tools
- execution has authority, approval, cost, audit, recovery, or side-effect concerns
- callers need to know what is available, restricted, denied, approval-required, or clarification-required before acting
- the organization needs service-owned policy and workflow semantics, not prompt-side advice
- capability behavior must be packaged, signed, generated, locked, and verified
- multiple agent clients need the same portable governed behavior

Use both when:

- MCP clients need access to a governed ANIP service
- ANIP should expose an MCP facade whose tools are governed capabilities
- existing MCP servers expose useful backend operations but need a safer public surface
- you want to compare raw tool access with governed capability access

Default production stance:

- Expose governed ANIP capabilities as the product contract.
- Expose MCP when MCP clients need to consume those capabilities.
- Use native APIs as the backend integration path when they are cleaner than MCP.

## What not to do

Do not generate one ANIP capability for every MCP tool by default. That recreates the raw tool surface with a different name.

Do not bury approvals, denials, or sensitive data rules only in prompts or skill files. Those are advisory, not authoritative.

Do not expose broad backend primitives such as raw SQL, arbitrary workflow dispatch, or unrestricted message posting as the product contract.

Do not let custom bundles rewrite public manifest semantics. Implementation material may fill extension points, but the signed contract remains the authority.

## Summary

MCP is valuable because agents and agent clients need a standard way to discover and call tools across systems.

ANIP is valuable because providers and organizations need a standard way to expose discoverable governed capabilities, not just raw tools, and to define what is allowed to happen when agents act.

The practical architecture is:

- MCP for client/tool interoperability.
- ANIP for the service-owned governed capability contract.
- Native APIs where they are the cleaner backend.
- Skills only as optional affordances, not the trust boundary.
