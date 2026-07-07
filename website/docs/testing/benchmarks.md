---
title: Benchmarks
description: How to read ANIP benchmark results, what they validate, and what not to overclaim.
---

# Benchmarks

ANIP benchmarks are evidence, not marketing shortcuts. They should be read as reproducible measurements of specific packages, agents, model settings, and question banks.

The current benchmark focus is the GTM Agent showcase because it has a realistic multi-service contract, governed outcomes, approval boundaries, denial behavior, multi-turn flows, and generated services across five languages.

## Current Benchmark Surface

The public benchmark surface is:

| Surface | Count | Purpose |
| --- | ---: | --- |
| GTM benchmark suite | 540 | Broad runtime behavior, routing, continuation state, loop count, token usage, and model-tier measurement. |
| Hard-mode governance bank | 24 | Prompt injection, mixed safe/unsafe intent, actor-boundary pressure, approval bypass attempts, provider-selected targets, negated actions, and multi-turn override handling. |
| Release validation surface | 564 | Combined GTM benchmark suite plus hard-mode governance bank. |

The benchmark harness and raw result artifacts live in the dedicated repository:

- [anip-protocol/anip-benchmarks](https://github.com/anip-protocol/anip-benchmarks)
- [GTM Agent cost and governance report](https://github.com/anip-protocol/anip-benchmarks/tree/main/reports/2026-06-gtm-agent-cost-comparison)

## Headline Result

Current public result:

| Lane | Normal suite | Hard-mode suite | Normal-suite tokens | Normal-suite loops |
| --- | ---: | ---: | ---: | ---: |
| ANIP runtime-native mixed `nano -> mini` | 540/540 | 24/24 | 1,461,506 | 1,188 |
| MCP-style skills/recipes on `mini` | 538/540 | 19/24 | 1,669,780 | 1,785 |
| MCP-style skills/recipes on `nano` | 515/540 | 18/24 | 1,780,090 | 1,785 |

The ANIP mixed lane starts with `gpt-5.4-nano` and falls back to `gpt-5.4-mini` only when deterministic contract validation says the primary plan is not safe or grounded enough to invoke.

## What The Result Means

The result supports four claims:

1. A smaller model can consume a governed ANIP service when the contract carries enough execution structure.
2. Runtime-native fallback can preserve correctness while avoiding the stronger model on the common path.
3. Service-owned governance improves hard-mode behavior because authority, denial, approval, and side-effect boundaries do not live only in the prompt.
4. Loop count and token usage are measurable release properties, not just qualitative impressions.

This is the practical model-cost argument for ANIP:

```text
stronger model for contract authoring
smaller model for governed consumption
fallback only when validation requires it
service enforcement either way
```

## What The Result Does Not Mean

Do not overread the benchmark.

It does not mean:

- every ANIP package can run on a nano model;
- nano is a replacement for stronger reasoning models;
- every MCP implementation will behave like this baseline;
- hard-mode governance can be solved only by ANIP;
- model choice alone creates security.

It means this specific GTM package, runtime, and benchmark suite demonstrate a useful pattern: when execution semantics are moved into service-owned contracts, the agent can use smaller models for more of the work and reserve stronger models for escalation.

## The MCP-Style Baseline

The MCP-style baseline is intentionally not a weak straw man. It uses an engineered client-side approach with skills/recipes-style prompting and consumer-side guardrails.

That framing matters. The comparison is not:

```text
ANIP vs intentionally bad tool calling
```

It is closer to:

```text
service-owned governance vs engineered consumer-side governance
```

Consumer-side guardrails can work for many cases, but they remain harder to make portable and enforceable. They depend on prompts, local app glue, model behavior, and evaluation coverage. ANIP moves more of the execution contract to the service boundary.

## Release Validation Versus Benchmarking

Release validation and benchmarking answer different questions.

| Activity | Question |
| --- | --- |
| Protocol conformance | Does the service speak ANIP correctly? |
| Generator conformance | Does code generation preserve the contract across targets? |
| Package verification | Is this the intended signed package? |
| GTM release validation | Does the GTM agent satisfy its declared behavior banks? |
| Benchmark comparison | How do different runtime approaches compare on pass rate, loops, token usage, and model tier? |

A benchmark result should never replace conformance, package verification, or service-side contract testing.

## How Mixed Mode Is Counted

For mixed model runs, the benchmark should record:

- primary model,
- fallback model,
- number of primary attempts,
- number of fallback attempts,
- fallback rate,
- fallback reasons,
- input, cached-input, and output token usage where available,
- total loops,
- total wall-clock time,
- pass/fail count by bank.

Cost estimates should be derived from recorded token usage and published model pricing at the time of analysis. Pricing changes, so benchmark reports should include the pricing date and avoid hardcoding timeless claims.

## Reproducing Results

Use the benchmark repository for cross-approach runs:

```bash
git clone https://github.com/anip-protocol/anip-benchmarks.git
cd anip-benchmarks
```

Use the main ANIP repository for package, generated-service, and showcase source material:

```bash
git clone https://github.com/anip-protocol/anip.git
cd anip
```

The GTM package currently used for public showcase validation is:

```text
gtm-pipeline-q2-review@0.4.5
```

The benchmark docs and scripts in `anip-benchmarks` are the source of truth for exact commands, environment variables, and raw run artifacts.

## How To Interpret Failures

Do not patch benchmark failures by adding phrase-specific logic.

Triage failures in this order:

1. Is the package or generated service stale?
2. Is the question expectation wrong?
3. Is the contract missing a generic semantic primitive?
4. Is the generated implementation violating the contract?
5. Is the planner failing to ground capability selection or inputs?
6. Is the model too weak for the ambiguity level?
7. Is the test trying to prove behavior that belongs in the service contract?

The right fix should usually improve the contract, runtime validation, generated service behavior, or benchmark expectation. It should not teach the agent one more magic phrase.

## Related Pages

- [Mixed Model Execution](/docs/concepts/mixed-model-execution)
- [GTM Agent Showcase](/docs/showcases/gtm-agent/overview)
- [GTM Agent Testing](/docs/showcases/gtm-agent/testing)
- [Conformance, Contract, and Scenario Testing](/docs/testing/conformance-contract-testing)
