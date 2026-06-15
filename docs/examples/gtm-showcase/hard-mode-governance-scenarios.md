# GTM hard-mode governance scenarios

This document promotes the GTM hard-mode benchmark from an ad hoc benchmark artifact into explicit showcase source evidence.

These scenarios describe realistic user pressure that a governed GTM agent must handle without moving execution policy into consumer-side prompts, recipes, or benchmark-only repair code.

The current published GTM package remains `gtm-pipeline-q2-review@0.4.4`. This document is source evidence for the next reviewed Studio/package revision if the hard-mode scenarios are incorporated into package lineage.

## Purpose

The normal GTM release bank validates broad product behavior. Hard-mode validates governance pressure:

- prompt-injection-style instructions;
- mixed safe and unsafe intent;
- actor impersonation and scope pressure;
- provider-selected target ambiguity;
- approval bypass attempts;
- negated actions;
- multi-turn attempts to override a prior safe boundary.

The goal is not to make the agent cleverer. The goal is to prove that service-owned ANIP contracts keep authority, input resolution, denial, approval, and recovery semantics outside the model's discretion.

## Scenario groups

| Group | What it proves |
| --- | --- |
| Prompt injection | Instructions to ignore approval, denial, or raw-export boundaries must not change service behavior. |
| Actor boundary pressure | A user cannot escalate actor authority by claiming a different role in natural language. |
| Mixed safe/unsafe intent | A safe summary request combined with raw export, send-now, mutation, or hidden internals should stop at the unsafe boundary. |
| Provider-selected targets | Composed capabilities may select a target only when the contract owns that selection boundary and stops at the declared approval boundary when drafting or write-adjacent work follows. |
| Explicit target drafts | Draft-only outreach remains supported when a concrete target and objective are provided. |
| Approval bypass | Approval-gated previews must not become silent downstream mutations. |
| Input resolution | Vague targets or missing references require clarification rather than guessing; known business cohorts may be resolved only when the contract declares that mapping or provider-selected boundary. |
| Bounded explanations | Bounded rationale is supported; raw scoring internals, model weights, hidden records, and feature dumps are denied. |
| Multi-turn recovery | Prior turns and assistant text cannot override contract authority, scope, approval, or denial behavior. |

## Source benchmark file

The executable hard-mode benchmark cases live at:

```text
benchmarks/gtm-agent-comparison/cases/gtm-hard-mode.json
```

That file currently contains 24 cases. It is intentionally separate from the 490-question release gate until the scenarios are incorporated into a reviewed Studio project revision and package lineage.

## Expected outcome classes

Hard-mode cases use the same ANIP outcome classes as the normal GTM agent:

- `success`
- `clarification_required`
- `restricted`
- `denied`
- `approval_required`

The important property is that these outcomes are service-owned. A model may request a capability, but the service decides whether execution is allowed and which governed outcome applies.

## Incorporation path

Hard-mode is official in `gtm-pipeline-q2-review@0.4.4`. The promotion path was:

1. Add these scenarios as Product Design source evidence in Studio.
2. Confirm Product scenario coverage includes the hard-mode groups above.
3. Confirm Developer Design evidence expresses any required runtime governance, input contracts, approval boundaries, denial behavior, and composition metadata.
4. Create reviewed Product and Developer revisions.
5. Publish a new GTM package revision only if the compiled contract changes.
6. Regenerate services from the new package.
7. Run the normal release gate and hard-mode gate:

```text
490-question normal GTM release bank
24-question hard-mode governance bank
```

8. Preserve a new Studio snapshot if the canonical showcase state changes.

## Current benchmark signal

The hard-mode benchmark is useful because it distinguishes service-side governance from client-side prompt governance.

In local engineering runs:

- ANIP compact mini passed the hard-mode bank.
- ANIP mixed nano-to-mini passed the hard-mode bank.
- The MCP-style skill/recipe baseline still failed several hard-mode cases even when using stronger models.

This does not mean stronger models are useless. It means stronger reasoning is not a substitute for provider-owned execution contracts when the issue is authority, approval, denial, recovery, and audit.
