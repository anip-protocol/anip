---
title: GTM Agent Showcase
description: The flagship ANIP showcase for governed revenue-operations agents, generated services, BI verification, broad question-bank validation, and hard-mode governance tests.
---

# GTM Agent Showcase

The GTM Agent showcase is the deepest ANIP example. It demonstrates how a business-facing agent can operate across revenue-operations data, enrichment, prioritization, routing previews, and outreach drafts without relying on hidden prompts, consumer-side recipes, or raw backend tool access.

The point of the showcase is not only that an agent can answer GTM questions. The point is that the behavior is specified, generated, enforced, tested, and explainable.

## What it proves

The showcase proves:

- Product and business intent can be captured in Studio as reviewed capability semantics.
- Developer-owned evidence can complete runtime governance, input contracts, composition, and backend boundaries.
- The resulting ANIP package can generate native services in Python, TypeScript, Go, Java, and C#.
- The same contract can drive an agent UI that discovers capabilities and selects services automatically.
- Approval, clarification, denial, masking, and restricted outcomes are service-owned behavior, not prompt conventions.
- A 540-case GTM benchmark suite can validate broad behavior, multi-turn continuation, loop count, token usage, and model-tier behavior.
- A 24-case hard-mode governance bank extends release validation to prompt-injection resistance, actor boundaries, approval stops, provider-selected targets, and multi-turn override handling.
- BI views in Metabase can independently inspect the modeled GTM data behind the ANIP services.

## Release baseline

| Item | Baseline |
| --- | --- |
| Package | `gtm-pipeline-q2-review@0.4.5` |
| ANIP spec | `anip/0.24` |
| Services | 4 |
| Capabilities | 23 |
| Generated languages | Python, TypeScript, Go, Java, C# |
| Agent model used for validation | `gpt-5.4-mini` |
| GTM benchmark suite | 540 cases |
| Hard-mode governance bank | 24 cases |
| Release validation surface | 564 cases |
| Docker images | `anipprotocol/showcase-gtm-{python,typescript,go,java,csharp}:0.4.5` |

The package artifact lives at:

```text
examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.5.anip-package.json
```

The generated language outputs live at:

```text
examples/showcase/gtm/generated/language-parity/
```

## Why `gpt-5.4-mini` Is Enough Here

The GTM Agent showcase intentionally separates contract authoring from contract consumption.

Studio authoring was validated with `gpt-5.4` because it produces reviewed Product Design, Developer Design, and package material. The running GTM agent uses `gpt-5.4-mini` for question handling because it is consuming a signed ANIP package with 23 governed capabilities, explicit inputs, approval gates, denial/restriction behavior, and service-owned audit semantics.

That matters. Without ANIP, the agent would need a much larger prompt, skill file, or workflow graph to remember how to safely stitch together pipeline, enrichment, routing, and outreach behavior. With ANIP, the service contract carries that execution structure, so the agent model can focus on selecting the bounded capability, resolving inputs, and reporting the service-owned outcome.

The 540-case GTM benchmark suite and 24-case hard-mode governance bank are designed to test that boundary. They are not testing whether a model can improvise GTM policy. They test whether a smaller model can consume governed services whose behavior, authority, denial, approval, and recovery semantics are already explicit.

## Benchmark evidence

The reproducible benchmark harness and raw result artifacts live in the dedicated benchmark repository:

- [anip-protocol/anip-benchmarks](https://github.com/anip-protocol/anip-benchmarks)
- [GTM Agent cost and governance report](https://github.com/anip-protocol/anip-benchmarks/tree/main/reports/2026-06-gtm-agent-cost-comparison)

Current headline result:

| Lane | Normal suite | Hard-mode suite | Normal-suite tokens | Normal-suite loops |
| --- | ---: | ---: | ---: | ---: |
| ANIP runtime-native mixed `nano -> mini` | 540/540 | 24/24 | 1,461,506 | 1,188 |
| MCP-style skills/recipes on `mini` | 538/540 | 19/24 | 1,669,780 | 1,785 |
| MCP-style skills/recipes on `nano` | 515/540 | 18/24 | 1,780,090 | 1,785 |

The ANIP mixed lane uses deterministic contract validation to decide when to fall back from `gpt-5.4-nano` to `gpt-5.4-mini`. The fallback decision is part of runtime validation, not benchmark-oracle knowledge.

## How to read this section

Use these pages in order if you are new to the showcase:

1. [Business Intent](/docs/showcases/gtm-agent/business-intent): what the product is supposed to do and what must be governed.
2. [Architecture](/docs/showcases/gtm-agent/architecture): how the agent, services, warehouse, dbt, Cube, and Metabase fit together.
3. [Data and BI](/docs/showcases/gtm-agent/data-bi): how the Maven CRM data becomes governed GTM evidence.
4. [Capability Map](/docs/showcases/gtm-agent/capability-map): how 23 ANIP capabilities map to services and outcomes.
5. [Agent Execution](/docs/showcases/gtm-agent/agent-execution): how questions become bounded ANIP invocations.
6. [Questions And Extensions](/docs/showcases/gtm-agent/questions-and-extensions): what the current agent supports, stops, denies, and how to extend it.
7. [Generate Services](/docs/showcases/gtm-agent/generated-services): how the package and custom bundles produce five native implementations.
8. [Docker Compose](/docs/showcases/gtm-agent/docker-compose): how to run the local stacks.
9. [Testing](/docs/showcases/gtm-agent/testing): how the broad behavior gate, hard-mode governance gate, and benchmark multi-turn extension are organized.

## What not to infer

Do not infer behavior from the agent prompt alone. The prompt is only the consumer-facing planning layer. The important behavior lives in:

- the Studio project contract,
- the signed package,
- the generated service manifests,
- the custom-code bundle implementation seams,
- service-side runtime checks,
- approval and audit surfaces,
- question-bank expected outcomes.

If a behavior matters for safety or correctness, it should be visible in one of those artifacts.
