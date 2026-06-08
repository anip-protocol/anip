---
title: Scenario-Driven Execution Design
description: How ANIP turns product intent into governed execution behavior that services can enforce and agents can rely on.
---

# Scenario-Driven Execution Design

Scenario-driven execution design is the discipline of defining what a service is allowed to do by describing the real execution scenarios it must handle. It is the bridge between business intent and a formal ANIP service contract.

The goal is not to write prompts. The goal is to make the important behavior explicit, reviewable, enforceable, and testable.

## Why scenarios matter

Agents do not only need a list of operations. They need to know what each operation means in context:

- What is the user trying to accomplish?
- What inputs are required before the service can act?
- What can be inferred, resolved, or selected by policy?
- What requires clarification?
- What requires approval?
- What is denied or restricted?
- What must be audited?
- What happens when the user follows up with missing context?

Traditional APIs usually answer only "what endpoint exists?" ANIP answers "what governed capability exists, under what authority, with what execution posture?"

## The design unit is a scenario

A scenario describes one meaningful interaction path. It should include:

| Element | Purpose |
| --- | --- |
| User intent | The business request in user language. |
| Capability selection | Which ANIP capability should own the request. |
| Required context | Inputs that must be present or resolved. |
| Resolution behavior | Whether missing or ambiguous inputs are clarified, backend-resolved, actor-policy-derived, app-selected, or rejected. |
| Authority posture | Required scopes, actor policy, approval requirements, and denial/restriction rules. |
| Side-effect posture | Read, write-adjacent, transactional, or irreversible. |
| Expected outcome | Available result, clarification, approval_required, restricted, denied, or structured failure. |
| Audit expectation | What evidence must be recorded. |

Scenarios are not scripts for the model. They are examples that force the contract to define the behavior.

## Example: raw API access vs governed scenario

Raw Jira access might expose:

```text
create_issue
update_issue
transition_issue
search
comment
```

A scenario-driven ANIP design exposes governed capabilities instead:

```text
jira.incident_bug.prepare
jira.workflow_transition.request
jira.customer_escalation.comment.prepare
jira.sprint_move.request
jira.release_notes.prepare
```

The difference is not naming. The ANIP capability owns the decision boundary:

- `jira.incident_bug.prepare` may require project, severity, customer impact, summary, and evidence.
- Direct mutation can be preview-only until an approval grant is supplied.
- Unsupported projects are denied before calling Jira.
- Missing severity triggers clarification instead of guessing.
- The audit trail records the preview, approval request, grant, and continuation.

## Scenario types

Good ANIP designs include scenarios across several classes:

| Scenario type | What it proves |
| --- | --- |
| Happy path | The normal request can complete. |
| Missing input | The service asks a specific clarification question instead of guessing. |
| Ambiguous input | The service refuses to resolve unsafe ambiguity silently. |
| Actor-policy path | The service derives allowed scope from the actor or tenant policy. |
| Approval path | The service stops before a gated side effect and issues an approval request. |
| Denial path | The service rejects unsupported or forbidden actions clearly. |
| Restriction path | The service returns reduced data or limited capability when policy allows partial execution. |
| Follow-up path | The service correctly handles the next user turn after clarification or approval. |
| Audit path | The service records enough evidence for review and verification. |

If a design only contains happy paths, it is not ready for autonomous or semi-autonomous agent use.

## Relationship to ANIP v0.24 input resolution

ANIP v0.24 added portable input-resolution metadata because scenario work exposed a real gap: not every input should be treated like a closed enum, and not every concrete reference can be hardcoded in a contract.

An input can declare a resolution posture such as:

- `closed_values` — value must be one of the declared allowed values.
- `backend_resolved` — service resolves the value using a catalog or backend lookup.
- `app_selected` — consuming application owns selection before invoking ANIP.
- `actor_policy` — value is derived from actor, tenant, or policy context.
- `actor_policy_or_explicit` — actor policy can derive it, but explicit values are allowed when policy permits.
- `explicit_only` — caller must provide it directly.
- `clarify` — missing or ambiguous value requires a clarification response.

That lets a contract say "this account reference is backend-resolved through `gtm.account_catalog`" without pretending every account name belongs in the manifest.

## What belongs in the contract

The contract should include:

- Capability IDs, descriptions, inputs, outputs, side effects, scopes, and costs.
- Resolution behavior for inputs.
- Approval requirements and approval-grant policy.
- Composed capability structure when the service owns a multi-step business operation.
- Denial, restriction, clarification, and failure semantics.
- Audit posture and lineage expectations.

The contract should not include:

- Prompt instructions that only one model will understand.
- Raw backend SDK details as the agent-facing behavior.
- Secret values.
- Environment-specific URLs unless they are non-secret deployment metadata.
- Hidden implementation shortcuts that change the public manifest.

## What belongs in implementation material

Implementation material can include:

- Backend adapters.
- Custom code bundles.
- Local SDK clients.
- Database queries.
- dbt, Cube, Snowflake, Databricks, REST, GraphQL, or MCP integration code.
- Catalog resolvers.
- Organization-specific policy hooks.

Implementation can change as long as it does not change the signed behavior contract. If behavior changes, publish a new package revision.

## Design checklist

Before generating a service, ask:

- Are the capabilities business-level, not raw tool names?
- Does each capability have a clear side-effect posture?
- Are required inputs explicit?
- Do optional inputs state what happens when omitted?
- Are dynamic references modeled with `resolution` instead of hardcoded fake catalogs?
- Are approval-gated operations preview-first?
- Are denial/restriction outcomes explicit?
- Are follow-up turns covered?
- Is the audit trail sufficient to explain what happened?
- Can another implementation in another language produce the same public manifest?

Scenario-driven execution design is what prevents ANIP from becoming another tool wrapper. It keeps the service honest about what agents are allowed to do.

## How Studio operationalizes this

Studio is where scenario-driven execution design becomes a reviewed project workflow.

The concept maps into Studio like this:

| Studio area | Scenario-driven role |
| --- | --- |
| Source Docs | Evidence and context: product requirements, API notes, policies, examples, support processes, existing workflows. |
| Product Design | Business-owned scenario baseline: goals, actors, scenario classes, approvals, denials, restrictions, risks, non-goals, audit expectations. |
| Product baseline lock | Review point that says the business behavior is stable enough for contract design. |
| Developer Design | Technical translation: capabilities, inputs, resolution, scopes, side effects, approvals, failures, composition, backend mappings. |
| Coverage map | Proof that Product Design items have a corresponding Developer Design or explicit omission. |
| Developer Definition | Canonical ANIP contract emitted from the reviewed design. |
| Registry package | Signed distribution artifact that consumers can verify and generate from. |
| Execution Scenario Validation | Runtime proof that the generated service behaves according to the scenarios. |

This distinction matters because Studio has two audiences.

PM/business users should focus on:

- What the agent-facing service is supposed to accomplish.
- Which actors and scopes matter.
- Which requests are allowed.
- Which requests require clarification.
- Which requests require approval.
- Which requests are denied or restricted.
- What evidence should be recorded.

Developers should focus on:

- Which capabilities implement those scenarios.
- Which inputs are required.
- Which input-resolution mode is correct.
- Which scopes and side effects apply.
- Which approval grants and continuation rules are needed.
- Which backend mappings are implementation evidence.
- Which generated service and package artifacts preserve the reviewed contract.

The handoff is the coverage map. If Product Design says "posting to Slack requires approval" but Developer Design exposes a direct send capability without approval, the project is not ready. If Product Design says "summarize pipeline by region" but Developer Design has only a raw SQL capability, the project is not ready.

## Studio example: product scenario to capability

Product Design scenario:

```text
When a sales leader asks for Q2 pipeline health by region,
the service should return a bounded summary. It must not expose raw row-level exports.
If quarter is missing, ask for it. If region is omitted, use actor policy.
```

Developer Design translation:

```text
capability: gtm.pipeline_summary
side_effect: read
inputs:
  quarter:
    required: true
    semantic_type: time_scope
    resolution.mode: clarify
  owner_scope:
    required: false
    semantic_type: scope_reference
    resolution.mode: actor_policy_or_explicit
business_effects:
  produces: content.summary
  does_not_produce: raw_data_export
```

That translation is the heart of Studio. The product scenario does not become a prompt recipe. It becomes contract metadata that generated services can enforce and agents can inspect.

## Studio example: fronting scenario to capability

Product Design scenario:

```text
When an incident lead asks to post a customer-impacting update to Slack,
the service should prepare a channel announcement preview.
Only approved channels are allowed. Posting requires approval.
```

Developer Design translation:

```text
capability: slack.channel_announcement.request
side_effect: write_adjacent
inputs:
  channel_ref:
    resolution.mode: backend_resolved
    catalog_ref: slack.allowed_channel_catalog
  message:
    required: true
approval:
  required: true
backend_evidence:
  slack_web_api: chat.postMessage
```

The backend evidence helps implementation, but the public ANIP capability is not `chat.postMessage`. The governed capability owns channel policy, preview, approval, denial, and audit behavior.

## Why this is different from skills and workflows

Skills, recipes, and workflow graphs often try to encode scenarios on the consumer side.

That can help one client, but it creates problems:

- Each consumer can encode the workflow differently.
- Policy can drift away from service reality.
- Prompt injection can target consumer-side instructions.
- The service cannot easily prove what behavior was intended.
- Another agent client may not have the same workflow file.

Studio puts scenario design on the provider side and turns it into packageable contract material. The agent can still use skills or workflows as affordances, but they should not be the trust boundary.

## When Studio output is good enough

A Studio project is ready to move toward publication when:

- Product Design has meaningful non-happy-path scenarios.
- Developer Design maps those scenarios into capabilities and policy.
- Diagnostics do not show missing intent or unsafe omission rules.
- Release lineage is approved.
- The Developer Definition is strict for the target ANIP spec.
- Registry package metadata is safe and portable.
- Scenario validation proves the running service behaves as designed.
