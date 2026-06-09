---
title: Execution Scenario Validation
description: How to prove that an ANIP service behaves according to its declared scenarios and signed contract.
---

# Execution Scenario Validation

Execution scenario validation checks that a running ANIP service behaves like its contract says it will behave. It is separate from protocol conformance.

- **Conformance** asks: does this service speak ANIP correctly?
- **Scenario validation** asks: does this service make the right governed execution decision for this business situation?

Both are required.

## Why conformance is not enough

A service can be protocol-conformant and still be behaviorally wrong.

For example, it might:

- Return `available` when it should require approval.
- Ask for clarification when actor policy should derive the value.
- Leak a previous assistant clarification into the next capability selection.
- Accept an unsupported target because the backend binding has an overly broad pass-through.
- Expose a raw backend operation as an ANIP capability without governance.
- Produce different public manifests across language targets generated from the same contract.

Conformance catches wire-format and protocol errors. Scenario validation catches semantic drift.

## Validation inputs

An execution scenario validation pack should include:

| Field | Meaning |
| --- | --- |
| Scenario ID | Stable identifier for the case. |
| User request | Natural-language request or direct invoke payload. |
| Expected capability | Capability that should own the request. |
| Token/actor context | Scopes, actor identity, tenant, session, or approval state. |
| Prior turn context | Previous clarification or approval request, if any. |
| Expected outcome | `success`, `clarification_required`, `approval_required`, `restricted`, `denied`, or a specific failure type. |
| Expected audit posture | Required audit class or linkage. |
| Notes | Why this behavior matters. |

For direct service validation, the pack can invoke capabilities directly. For agent-facing validation, it can include model/planner requests and expected capability/outcome.

## Scenario classes to test

At minimum, validate these:

| Class | Example |
| --- | --- |
| Capability selection | "Create a Sev-2 bug from this incident" selects `jira.incident_bug.prepare`. |
| Missing context | "Summarize pipeline for the quarter" asks which quarter. |
| Dynamic reference resolution | "Summarize Acme" routes to backend resolution instead of rejecting because Acme is not hardcoded. |
| Approval stop | "Post this incident update to Slack" returns `approval_required` before sending. |
| Approval continuation | Same request with a valid one-time grant performs the side effect exactly once. |
| Denial | "Run arbitrary SQL" is denied by the Superset fronting service. |
| Restriction | User can see regional aggregates but not owner-level records. |
| Follow-up after clarification | User answer fills the missing field for the same capability, not a different one. |
| Manifest parity | Generated services in every supported language expose the same public capability surface. |

## What to assert

Prefer stable assertions:

- Capability ID.
- Outcome status.
- Required clarification field.
- Approval request presence.
- Approval grant policy.
- Whether mutation occurred.
- Audit linkage identifiers.
- Contract signature or manifest digest.
- Capability count and capability ID set.

Avoid brittle assertions:

- Exact wording of model-generated summaries.
- Exact timestamp strings.
- JSON field ordering.
- Provider-specific incidental metadata unless it is part of the contract.

## Approval validation

Approval scenarios should validate both halves:

1. Initial invoke returns `approval_required` with a preview and approval request.
2. A valid approval grant allows the exact continuation.

The grant should be bound to:

- Capability.
- Parameters digest.
- Actor/session when session-bound.
- Expiry.
- Use count.
- Approval request ID.

The service should reject:

- Reused one-time grants.
- Expired grants.
- Grants for different parameters.
- Grants for different capabilities.
- Session-bound grants used outside the bound session.

## Fronting validation

For fronting services, scenario validation must prove that ANIP is not just renaming backend tools.

Validate that:

- Agents see governed capabilities, not raw backend tools.
- Native APIs, GraphQL APIs, or MCP tools are implementation material, not the public behavior contract.
- Write-adjacent operations stop at preview or approval.
- `backend_options` is bounded and audited.
- Raw SQL, hidden project switching, unbounded exports, or arbitrary tool pass-through are denied.
- Package metadata does not imply a backend path that the implementation does not actually use.

## Language and framework parity

Generated services must preserve public manifest shape across:

- Python
- TypeScript
- Go
- Java
- C#

Framework variants should preserve behavior too:

- TypeScript Hono, Express, Fastify.
- Java Spring Boot, Quarkus.

The implementation may differ internally, but the signed public manifest must not drift. Custom bundles can fill execution seams; they must not rewrite declaration shape, inputs, side effects, scopes, approval policy, or composition metadata.

## Release gate guidance

Use three layers:

1. **Fast per-scenario debugging** — small phase-sized runs.
2. **Full scenario banks** — release gate for a showcase or contract.
3. **Cross-language parity** — same contract, all generated targets, same expected outcomes.

If a scenario fails, do not immediately patch the phrase or one model output. First ask whether the contract is missing a generic behavior primitive, whether the implementation is violating the contract, or whether the scenario expectation is wrong.

That discipline is how ANIP avoids hiding domain-specific behavior inside generic runtime code.
