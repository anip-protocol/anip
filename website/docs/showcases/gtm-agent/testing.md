---
title: Testing
description: GTM Agent release question banks, hard-mode governance tests, multi-turn benchmark coverage, and release gates.
---

# Testing

The GTM showcase uses three test layers:

- generated-service and compose smoke tests,
- BI/dbt verification,
- agent-facing question banks.

The question bank is not generic ANIP conformance. It is the GTM release gate for user-facing behavior.

For concrete user-facing examples, see [Questions And Extensions](/docs/showcases/gtm-agent/questions-and-extensions).

The showcase also has a hard-mode governance bank. It exercises prompt injection, mixed safe/unsafe intent, actor-boundary pressure, provider-selected targets, approval bypass attempts, negated actions, and multi-turn ambiguity.

## GTM release validation

<a id="gtm-release-validation"></a>
<a id="490-question-bank"></a>

The current GTM release validation surface is the 540-case GTM benchmark suite plus 24 hard-mode governance cases.

| Bank | Count | Purpose |
| --- | --- | --- |
| Main phase banks used by the benchmark | 345 | Non-follow-up GTM scenarios across pipeline, enrichment, prioritization, outreach, approval, denial, restriction, and composition. |
| Variation banks used by the benchmark | 140 | Wording variation, unsupported effects, raw export denial, approval boundaries, derived target handling, and enum grounding. |
| Converted follow-up cases | 5 | Existing clarification-follow-up entries from the main banks represented as explicit two-turn benchmark cases. |
| Generated two-turn cases | 50 | Clarification and resolution flows across pipeline, enrichment, outreach, prioritization, routing, forecast, bottleneck, and reassignment. |
| GTM benchmark suite | 540 | Runtime behavior, routing, continuation state, loop count, token usage, and model-tier measurement. |
| Hard-mode governance bank | 24 | Prompt injection, mixed safe/unsafe intent, actor-boundary pressure, approval bypass attempts, provider-selected targets, negated actions, and multi-turn override handling. |
| Release validation surface | 564 | The 540-case GTM benchmark suite plus the 24-case hard-mode governance bank. |

Source locations:

```text
docs/examples/gtm-showcase/question-banks/
docs/examples/gtm-showcase/variation-question-banks-v3/
```

Hard-mode governance source evidence:

```text
docs/examples/gtm-showcase/hard-mode-governance-scenarios.md
benchmarks/gtm-agent-comparison/cases/gtm-hard-mode.json
```

The `gtm-pipeline-q2-review@0.4.5` release validation uses this 564-case surface. Older documentation may refer only to the pre-hard-mode broad behavior bank; use this page as the current source of truth.

For cross-approach benchmark comparison, use the dedicated benchmark repository:

- [anip-protocol/anip-benchmarks](https://github.com/anip-protocol/anip-benchmarks)
- [GTM Agent cost and governance report](https://github.com/anip-protocol/anip-benchmarks/tree/main/reports/2026-06-gtm-agent-cost-comparison)

The current report compares runtime-native ANIP mixed `gpt-5.4-nano -> gpt-5.4-mini` against an engineered MCP-style skills/recipes baseline. The MCP-style baseline includes consumer-side guardrails and is not a raw or intentionally weak tool-calling straw man.

For the reusable runtime pattern, see [Mixed Model Execution](/docs/concepts/mixed-model-execution). For benchmark interpretation, scope, and limitations, see [Benchmarks](/docs/testing/benchmarks).

Run artifacts live under:

```text
docs/examples/gtm-showcase/question-bank-runs/
```

## Phase intent

The phase banks are organized around behavior classes rather than implementation files:

| Phase area | Validates |
| --- | --- |
| Pipeline reads | Bounded summaries, stage breakdown, scope, masking. |
| Enrichment | Account context, lookalike evidence, missing target clarification. |
| Prioritization | Bounded ranking, rationale, raw model feature denial. |
| Outreach | Draft-only content, no external dispatch, target clarity. |
| Approval flows | Preview and approval-required behavior without silent mutation. |
| Actor boundaries | Restricted scope and masked financial values. |
| Composition | Multi-step service behavior with visible stops. |

## Hard-mode governance gate

The hard-mode gate is deliberately smaller than the 540-case benchmark suite. It targets the places where client-side prompt governance usually breaks:

| Pressure | Expected ANIP behavior |
| --- | --- |
| Prompt injection | Service-owned denial, approval, and raw-export boundaries still apply. |
| Actor impersonation | Natural-language role claims do not change actor authority. |
| Mixed safe/unsafe intent | Safe work does not silently absorb raw export, send-now, mutation, or hidden-internals requests. |
| Provider-selected targets | A composed capability may select a target only when the contract owns that selection boundary. |
| Approval bypass | Preview and preparation capabilities stop at approval instead of mutating downstream systems. |
| Multi-turn override | Earlier assistant text or follow-up instructions cannot override the contract. |

This bank is useful for benchmarks because it separates model intelligence from enforceable execution governance.

## Run a bank

Use the generated-stack scripts:

```bash
python3 examples/showcase/gtm/scripts/generated_stack/run_question_bank.py \
  --base-url http://127.0.0.1:4330 \
  --bank docs/examples/gtm-showcase/question-banks/gtm_phase1_question_bank.json
```

Use phase-sized banks while debugging. Use the generated 540-case benchmark suite plus the 24-case hard-mode bank before publishing package or showcase changes.

## Model

The GTM validation bank is designed to run with:

```text
ANIP_AGENT_MODEL=gpt-5.4-mini
```

This matters because the showcase should not require a very large model to compensate for missing service semantics. ANIP moves capability meaning and execution boundaries into the service-owned contract.

## Failure triage

When a question fails, triage in this order:

1. Confirm the stack was generated from `gtm-pipeline-q2-review@0.4.5`.
2. Confirm the expected language service exposes 23 capabilities.
3. Confirm the agent runtime is pointed at the selected language stack.
4. Confirm the dbt models and Metabase views return sane values.
5. Confirm the custom bundle report only changed implementation seams.
6. Decide whether the failure is stale test expectation, bundle bug, contract bug, generator/runtime bug, or model planning drift.

Do not fix GTM behavior by adding GTM-specific hacks to generic ANIP runtime code.
