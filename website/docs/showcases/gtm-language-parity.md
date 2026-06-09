---
title: GTM Language Parity
description: Run the GTM showcase generated from one contract across Python, TypeScript, Go, Java, and C#.
---

# GTM Language Parity

The GTM showcase proves that one signed ANIP contract can generate native services in all supported languages.

This is not a proxy setup. Each language stack is native to that language.

## What This Proves

The parity proof has three layers:

1. **Contract parity** — every language is generated from the same signed package.
2. **Manifest parity** — every generated stack exposes the same public capability set and public manifest semantics.
3. **Behavior parity** — each language stack can answer the same GTM scenario bank through the same agent runtime.

The important constraint:

```text
Custom bundles may implement behavior.
Custom bundles must not mutate the signed public contract.
```

That means a language-specific bundle can fill backend adapters, approval stores, fixtures, and runtime integration seams. It must not change capability IDs, inputs, side-effect posture, composition metadata, input resolution, required scopes, or approval policy.

## Canonical Package

The promoted baseline lives in:

```text
examples/showcase/gtm/generated/language-parity/
```

It includes Python, TypeScript, Go, Java, and C# implementations generated from the same GTM contract.

The package is:

```text
gtm-pipeline-q2-review@0.4.3
```

Package path:

```text
examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.3.anip-package.json
```

Expected contract shape:

| Property | Expected value |
| --- | --- |
| Spec | `anip/0.24` |
| Package | `gtm-pipeline-q2-review@0.4.3` |
| Services | 4 |
| Capabilities | 23 |
| Languages | Python, TypeScript, Go, Java, C# |
| Transport | HTTP for compose stacks; stdio can be generated from the same package |

The generated language outputs are:

```text
examples/showcase/gtm/generated/language-parity/python/
examples/showcase/gtm/generated/language-parity/typescript/
examples/showcase/gtm/generated/language-parity/go/
examples/showcase/gtm/generated/language-parity/java/
examples/showcase/gtm/generated/language-parity/csharp/
```

The hand-written Python showcase remains useful as historical/reference material. It is not the parity target. Parity compares generated language outputs from the same contract.

## Capability Domains

The GTM contract covers a revenue-operations workflow, not a toy calculator.

Capability groups include:

- Pipeline summaries.
- Forecast summaries.
- Stage bottleneck analysis.
- Sales-team performance.
- Product pipeline.
- Account risk.
- Account enrichment.
- Outreach drafts.
- Follow-up and reassignment preparation.
- Prioritized routing and compound scenarios.

The exact capability IDs are defined by the signed service definition and exposed through each generated manifest. Docs should not become a second source of truth for the capability list.

## Native Language Output

Each target is generated as a native implementation:

| Language | Output posture |
| --- | --- |
| Python | Python service code with native runtime/custom bundle seams. |
| TypeScript | TypeScript service code with native runtime/custom bundle seams. |
| Go | Go service code with native runtime/custom bundle seams. |
| Java | Java service code with native runtime/custom bundle seams. |
| C# | C# service code with native runtime/custom bundle seams. |

The non-Python stacks are not HTTP proxies to Python. If a language cannot pass parity without delegating to another implementation, it is not release-quality parity.

## Generate From The Package

Generation uses the same package and changes only the target language and bundle:

```bash
anip generate \
  --package-bundle examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.3.anip-package.json \
  --target typescript \
  --transport http \
  --custom-code-bundle examples/showcase/gtm/custom-code-bundles/gtm_pipeline_typescript \
  --output /tmp/gtm-typescript \
  --force
```

For release baselines, the committed generated outputs live under `examples/showcase/gtm/generated/language-parity/`.

## Custom Bundle Boundary

The GTM bundles provide implementation material:

- fixture-backed GTM data access
- backend adapter logic
- approval grant handling
- actor policy helpers
- domain rendering logic
- framework-specific service wiring

They must not change the public ANIP contract.

Bad bundle behavior:

- changing a composed capability to atomic in the manifest
- removing required inputs from the public declaration
- changing `resolution.mode`
- weakening approval policy
- adding hidden capabilities
- changing side-effect posture

Valid bundle behavior:

- implementing the declared capability
- optimizing internal execution
- resolving provider data behind `resolver_ref`
- returning previews or approval-required responses according to the contract
- adapting the generated service to language/framework conventions

## Run a language stack

```bash
examples/showcase/gtm/scripts/smoke-language-compose.sh python
examples/showcase/gtm/scripts/smoke-language-compose.sh typescript
examples/showcase/gtm/scripts/smoke-language-compose.sh go
examples/showcase/gtm/scripts/smoke-language-compose.sh java
examples/showcase/gtm/scripts/smoke-language-compose.sh csharp
```

Each smoke starts:

- Four generated ANIP services.
- Agent runtime.
- Agent UI route.
- Required local dependencies.

It verifies:

- Discovery documents.
- 23-capability union.
- Manifest shape.
- Runtime JSON.
- UI reachability.

The direct compose files are also available:

```text
examples/showcase/gtm/docker-compose.language-parity-python.yml
examples/showcase/gtm/docker-compose.language-parity-typescript.yml
examples/showcase/gtm/docker-compose.language-parity-go.yml
examples/showcase/gtm/docker-compose.language-parity-java.yml
examples/showcase/gtm/docker-compose.language-parity-csharp.yml
```

Each stack starts:

- Postgres loaded with the GTM dataset.
- Four generated ANIP services for the selected language.
- Metabase for BI inspection.
- GTM agent runtime/UI configured against that language's services.

Ports differ by stack so multiple language stacks can be compared without editing service code.

## Why this matters

Language parity prevents a common failure mode: one language becomes the real implementation and other languages become wrappers or demos.

The release standard is stricter:

- Same contract.
- Same capability IDs.
- Same public manifest semantics.
- Native implementation per language.
- Custom bundles fill execution seams only.
- No language-specific manifest mutation.

## Generator Conformance vs Scenario Tests

Do not rely only on the GTM question bank for generator quality.

Use separate gates:

| Gate | Purpose |
| --- | --- |
| Generator conformance | Proves generated structure and contract semantics are consistent across targets. |
| Compose smoke | Proves each generated language stack starts and exposes the expected ANIP surface. |
| Question banks | Prove the GTM app behavior through realistic user prompts. |

The GTM bank is intentionally domain-specific. It is a strong showcase gate, but it is not a generic ANIP conformance suite.

## Question-bank validation

The GTM showcase also has LLM-dependent question banks. Those validate planner and runtime behavior against user-facing scenarios.

Use them as release gates, not as the only parity mechanism:

- Generator conformance should catch structural drift.
- Compose smoke should catch service topology drift.
- Scenario/question banks should catch behavior drift.

If a question-bank case fails, first decide whether the contract is missing a generic behavior primitive, the implementation violates the contract, or the test expectation is stale.

Do not patch generic runtime code with GTM-specific phrases.

## Question Banks

The release validation bank is:

| Bank | Coverage | Size |
| --- | --- | --- |
| Phase banks | Phase-by-phase GTM scenarios: happy paths, clarification, denial, restriction, approval, actor variation, and composition. | 350 |
| Variation banks | Wording variation, unsupported effects, derived targets, approval boundaries, enum grounding, and raw-export denial. | 140 |
| Combined release gate | Full GTM scenario behavior across generated stacks. | 490 |

The 350-bank source lives in:

```text
docs/examples/gtm-showcase/question-banks/
```

The 140-bank source lives in:

```text
docs/examples/gtm-showcase/variation-question-banks-v3/
```

Run phase-sized banks while debugging. Use the full 350/140/490 runs as release gates.

## Model Configuration

For GTM agent-service testing, use the lightweight test model configured for the bank:

```text
ANIP_AGENT_MODEL=gpt-5.4-mini
```

That model choice is for generated ANIP service testing. Studio assistant authoring is a different workflow and should use the configured Studio assistant model.

## Failure Triage

When parity breaks, triage in this order:

1. **Same contract?** Confirm every language was generated from `gtm-pipeline-q2-review@0.4.3`.
2. **Same capability count?** Confirm all five expose the 23-capability union.
3. **Same manifest semantics?** Confirm bundle code did not mutate declarations.
4. **Same topology?** Confirm the agent runtime points to four service endpoints, not duplicated aliases or stale ports.
5. **Same compact brief?** Confirm the runtime sends compact capability briefs, not full manifest JSON, and that every language exposes enough agent-consumption metadata.
6. **Same approval flow?** Confirm `approval_required` responses produce real approval request/grant continuation state.
7. **Same follow-up handling?** Confirm clarification follow-ups retain pending capability context rather than replanning from scratch.

If the issue is GTM-specific, fix the GTM bundle or contract. If the issue is generic, fix the generator, shared runtime utilities, or ANIP metadata model. Do not hide drift with language-specific manifest overrides.

## Release Standard

The GTM language parity showcase is release-ready only when:

- All five language outputs are regenerated from the same signed package.
- Manifest structural parity passes across all five.
- Compose smoke passes for all five.
- The 350-bank passes for all five.
- The 140 variation bank passes for all five.
- Custom bundles do not mutate public declarations.
- Any required app-specific behavior is explicit implementation material, not hidden generic runtime logic.

This is the showcase that proves ANIP is not one runtime with four afterthought ports. It is one contract producing native governed services across the supported language set.
