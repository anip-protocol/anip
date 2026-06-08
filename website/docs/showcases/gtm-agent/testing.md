---
title: Testing
description: GTM Agent 490-question validation and release gates.
---

# Testing

The GTM showcase uses three test layers:

- generated-service and compose smoke tests,
- BI/dbt verification,
- agent-facing question banks.

The question bank is not generic ANIP conformance. It is the GTM release gate for user-facing behavior.

For concrete user-facing examples, see [Questions And Extensions](/docs/showcases/gtm-agent/questions-and-extensions).

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

## Run a bank

Use the generated-stack scripts:

```bash
python3 examples/showcase/gtm/scripts/generated_stack/run_question_bank.py \
  --base-url http://127.0.0.1:4330 \
  --bank docs/examples/gtm-showcase/question-banks/gtm_phase1_question_bank.json
```

Use phase-sized banks while debugging. Use the full 350 and 140 sets as release gates.

## Model

The GTM validation bank is designed to run with:

```text
ANIP_AGENT_MODEL=gpt-5.4-mini
```

This matters because the showcase should not require a very large model to compensate for missing service semantics. ANIP moves capability meaning and execution boundaries into the service-owned contract.

## Failure triage

When a question fails, triage in this order:

1. Confirm the stack was generated from `gtm-pipeline-q2-review@0.4.3`.
2. Confirm the expected language service exposes 23 capabilities.
3. Confirm the agent runtime is pointed at the selected language stack.
4. Confirm the dbt models and Metabase views return sane values.
5. Confirm the custom bundle report only changed implementation seams.
6. Decide whether the failure is stale test expectation, bundle bug, contract bug, generator/runtime bug, or model planning drift.

Do not fix GTM behavior by adding GTM-specific hacks to generic ANIP runtime code.
