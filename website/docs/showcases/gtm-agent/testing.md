---
title: Testing
description: GTM Agent 490-question validation, hard-mode governance tests, multi-turn benchmark coverage, and release gates.
---

# Testing

The GTM showcase uses three test layers:

- generated-service and compose smoke tests,
- BI/dbt verification,
- agent-facing question banks.

The question bank is not generic ANIP conformance. It is the GTM release gate for user-facing behavior.

For concrete user-facing examples, see [Questions And Extensions](/docs/showcases/gtm-agent/questions-and-extensions).

The showcase also has a hard-mode governance bank. It exercises prompt injection, mixed safe/unsafe intent, actor-boundary pressure, provider-selected targets, approval bypass attempts, negated actions, and multi-turn ambiguity.

## 490-question bank

The release bank is:

| Bank | Count | Purpose |
| --- | --- | --- |
| Phase banks | 350 | Main GTM scenarios across pipeline, enrichment, prioritization, outreach, approval, denial, restriction, and composition. |
| Variation banks | 140 | Wording variation, unsupported effects, raw export denial, approval boundaries, derived target handling, and enum grounding. |
| Combined | 490 | Full release behavior gate. |

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

The `gtm-pipeline-q2-review@0.4.4` release gate includes the 490-question broad behavior bank plus the 24-case hard-mode governance bank.

## Benchmark multi-turn extension

The benchmark suite also expands the broad release bank into a multi-turn representation used for ANIP-vs-MCP-style comparison work:

| Benchmark component | Count | Purpose |
| --- | ---: | --- |
| Converted release follow-up cases | 5 | Existing clarification-follow-up entries from the 350 main bank, represented as two-turn benchmark cases. |
| Generated two-turn cases | 50 | Clarification and resolution flows across pipeline, enrichment, outreach, prioritization, routing, forecast, bottleneck, and reassignment. |
| Combined benchmark suite | 540 | 345 non-follow-up main cases, 140 variation cases, 5 converted follow-up cases, and 50 generated two-turn cases. |

The 540-case benchmark is not a replacement for the official release gate. It is used to measure runtime behavior, loop counts, token usage, and model-tier behavior under repeated multi-turn pressure.

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

The hard-mode gate is deliberately smaller than the 490-question bank. It targets the places where client-side prompt governance usually breaks:

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

Use phase-sized banks while debugging. Use the full 350 and 140 sets as the broad release gate, then run the 24-case hard-mode bank before publishing package or showcase changes. Use the 540-case benchmark suite when comparing runtime strategies or model tiers.

## Model

The GTM validation bank is designed to run with:

```text
ANIP_AGENT_MODEL=gpt-5.4-mini
```

This matters because the showcase should not require a very large model to compensate for missing service semantics. ANIP moves capability meaning and execution boundaries into the service-owned contract.

## Failure triage

When a question fails, triage in this order:

1. Confirm the stack was generated from `gtm-pipeline-q2-review@0.4.4`.
2. Confirm the expected language service exposes 23 capabilities.
3. Confirm the agent runtime is pointed at the selected language stack.
4. Confirm the dbt models and Metabase views return sane values.
5. Confirm the custom bundle report only changed implementation seams.
6. Decide whether the failure is stale test expectation, bundle bug, contract bug, generator/runtime bug, or model planning drift.

Do not fix GTM behavior by adding GTM-specific hacks to generic ANIP runtime code.
