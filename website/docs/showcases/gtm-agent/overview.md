---
title: GTM Agent Showcase
description: The flagship ANIP showcase for governed revenue-operations agents, generated services, BI verification, and 490-question validation.
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
- A realistic 490-question bank can validate behavior through user-facing questions.
- BI views in Metabase can independently inspect the modeled GTM data behind the ANIP services.

## Release baseline

| Item | Baseline |
| --- | --- |
| Package | `gtm-pipeline-q2-review@0.4.4` |
| ANIP spec | `anip/0.24` |
| Services | 4 |
| Capabilities | 23 |
| Generated languages | Python, TypeScript, Go, Java, C# |
| Agent model used for validation | `gpt-5.4-mini` |
| Question bank | 350 phase questions + 140 variation questions |
| Docker images | `anipprotocol/showcase-gtm-{python,typescript,go,java,csharp}:0.4.4` |

The package artifact lives at:

```text
examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.4.anip-package.json
```

The generated language outputs live at:

```text
examples/showcase/gtm/generated/language-parity/
```

## Why `gpt-5.4-mini` Is Enough Here

The GTM Agent showcase intentionally separates contract authoring from contract consumption.

Studio authoring was validated with `gpt-5.4` because it produces reviewed Product Design, Developer Design, and package material. The running GTM agent uses `gpt-5.4-mini` for question handling because it is consuming a signed ANIP package with 23 governed capabilities, explicit inputs, approval gates, denial/restriction behavior, and service-owned audit semantics.

That matters. Without ANIP, the agent would need a much larger prompt, skill file, or workflow graph to remember how to safely stitch together pipeline, enrichment, routing, and outreach behavior. With ANIP, the service contract carries that execution structure, so the agent model can focus on selecting the bounded capability, resolving inputs, and reporting the service-owned outcome.

The 490-question bank is designed to test that boundary. It is not testing whether a model can improvise GTM policy. It is testing whether a smaller model can consume governed services whose behavior is already explicit.

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
9. [Testing](/docs/showcases/gtm-agent/testing): how the 490-question validation is organized.

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
