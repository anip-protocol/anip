---
title: Studio for Developers
description: How developers use Studio to convert product intent into ANIP definitions, package metadata, generated code, and validation evidence.
---

# Studio for Developers

Developers use Studio to turn reviewed product intent into an executable ANIP contract.

The developer role is to make the Product Design enforceable:

- Define capabilities.
- Specify inputs and resolution behavior.
- Model side effects and scopes.
- Declare approval and denial paths.
- Capture backend integration metadata.
- Produce the Developer Definition.
- Publish or hand off a package.
- Generate and validate service code.

## Developer Design

Developer Design is the technical contract draft. It should answer:

| Area | Developer responsibility |
| --- | --- |
| Capabilities | Business-level capability IDs and descriptions. |
| Inputs | Required/optional inputs, types, semantic types, defaults, allowed values. |
| Resolution | Missing, ambiguous, unresolved, actor-policy, backend-resolved, and app-selected behavior. |
| Side effects | Read, write-adjacent, transactional, irreversible, or other declared posture. |
| Scopes | Minimum scopes and purpose-bound authority. |
| Approvals | Approval request shape, grant checks, continuation behavior. |
| Failures | Clarification, denied, restricted, failure, and recovery behavior. |
| Composition | Service-owned multi-step operations when the agent should not orchestrate child steps. |
| Backend mappings | Implementation evidence and adapter seams, not the public behavior contract. |
| Agent guidance | Consumability metadata that helps agents plan without replacing service enforcement. |

## Developer Source Evidence

Product source documents explain what the service should mean. Developer source evidence explains how that meaning becomes a generation-grade contract.

Developer evidence can be entered manually, drafted section by section in Guided Mode, imported from structured source documents, or used by Autopilot. Regardless of path, the evidence must make these decisions explicit:

| Evidence | Why it matters |
| --- | --- |
| Capability input contracts | Prevents generated services from guessing required inputs, optional scope, defaults, allowed values, and entity references. |
| Input resolution | Tells agents and runtimes when to clarify, use actor policy, use defaults, resolve through a backend, or require explicit input. |
| Runtime governance | Defines operation type, side-effect posture, produced effects, forbidden effects, and approval boundaries. |
| Composition | Makes provider-owned multi-step behavior explicit instead of hiding it in prompts or app glue. |
| Backend bindings | Connects governed capabilities to real adapters without turning the public contract into a raw API wrapper. |
| Verification expectations | Defines what must be proven before the package is trusted. |

If this evidence is missing, Studio should show diagnostics or ask targeted questions. It should not let a release-grade Developer Definition depend on assistant guesses.

## Developer Definition

The Developer Definition is the canonical machine-readable contract emitted from Studio.

Generators and verifiers consume this artifact, not hidden UI state.

It should include:

- `anip/0.24` contract shape.
- Capability declarations.
- Input resolution metadata.
- Side-effect posture.
- Delegation and approval policy.
- Runtime metadata required by generated services.
- Agent-consumption hints when present.
- Integration fronting metadata when relevant.

It should not include:

- Secret values.
- Machine-local paths.
- Private source docs.
- Prompt-only behavior that the service will not enforce.
- Backend implementation shortcuts that change the public manifest.

## Coverage Mapping

Studio should make coverage explicit:

```text
Product Design item -> Developer Design section -> Developer Definition artifact
```

Coverage exists to answer:

- Did every product scenario become a capability, policy, risk, non-goal, or explicit omission?
- Did approval intent become approval behavior?
- Did denial intent become denial behavior?
- Did source docs influence the generated contract?
- Did the Developer Definition drift away from Product Design?

Do not publish by ignoring coverage errors. Coverage is how Studio prevents business intent from being lost.

## Mode Expectations For Developers

The three authoring modes are all valid, but they have different responsibilities:

| Mode | Developer expectation |
| --- | --- |
| Manual Mode | Fill or review the Developer Design surfaces directly and use diagnostics as the gate. |
| Guided Mode | Let the assistant draft one section, then accept, revise, or reject it before moving on. |
| Autopilot Mode | Provide enough developer evidence up front, then review the completed draft and diagnostics. |

Autopilot should be fastest when a project has complete evidence. Guided Mode should be preferred when evidence is partial and the assistant needs human decisions. Manual Mode should be preferred when the team needs exact deterministic control.

## Input Resolution

ANIP v0.24 added input-resolution metadata because real services cannot hardcode every account, project, channel, page, dataset, or repository into a manifest.

Developers should use `resolution` to describe what the service does:

| Mode | Use when |
| --- | --- |
| `closed_values` | The value must be one of the declared allowed values. |
| `backend_resolved` | The service resolves the value through a backend catalog or lookup. |
| `actor_policy` | The value is derived from actor, tenant, or policy context. |
| `actor_policy_or_explicit` | Actor policy can derive it, but explicit values are allowed when policy permits. |
| `app_selected` | The consuming app selects before invoking. |
| `explicit_only` | The caller must provide the value directly. |
| `clarify` | Missing or ambiguous values require clarification. |

This belongs in the contract because agents need to know whether to ask, infer, delegate to service resolution, or stop.

## Backend Integration Metadata

Backend integration metadata is not the same thing as the public ANIP contract.

For fronting projects, Studio may capture evidence such as:

- Jira REST operation.
- Linear GraphQL mutation.
- Slack Web API method.
- Notion API endpoint.
- Superset REST path.
- MCP tool evidence.

That metadata helps implementation, generation, and review. It should not turn the public ANIP capability into a raw backend operation.

Good:

```text
slack.channel_announcement.request
```

Weak:

```text
chat.postMessage
```

The ANIP capability should own preview, approval, channel policy, denial, audit, and continuation behavior.

## Package Handoff

After Developer Definition is ready, Studio can produce or publish package material:

- Package README.
- Manifest.
- Service definition.
- Recommended lock.
- Contract signature.
- Product/developer lineage.
- Agent readiness summary.
- Optional immutable implementation-material refs.

The package is what consumers generate from. Treat it like a release artifact.

## Developer Checklist

Before publishing or handing off:

- Capabilities are business-level.
- Inputs have resolution behavior.
- Optional scope-affecting inputs have defaults, clarification, or service-owned resolution.
- Approval paths have real approval grants, not string parameters.
- Denial/restriction behavior is explicit.
- Public manifest matches the signed contract.
- Generated services preserve manifest shape across supported languages.
- Custom bundles do not mutate the public declaration.
- Package metadata contains no secrets, private docs, or machine-local links.
- Scenario validation covers realistic happy, clarification, approval, denial, restriction, and follow-up paths.

For the validation side, see [Execution Scenario Validation](/docs/concepts/execution-scenario-validation).
