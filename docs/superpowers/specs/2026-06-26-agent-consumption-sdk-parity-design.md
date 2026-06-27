# Agent Consumption SDK Parity Design

## Purpose

Python `anip-runtime-utils` currently contains the strongest reusable agent-consumption logic for compact capability routing, contract-derived capability scoring, required input detection, unsupported-effect detection, and safe fallback selection. That creates an architectural imbalance: generated services are language-parity capable, but consuming-agent helper logic is Python-first.

This work makes agent-consumption helpers available across TypeScript, Go, Java, and C# without hiding GTM-specific behavior in shared SDKs.

## Goals

- Provide language-native helper packages/modules for agent-consumption behavior in TypeScript, Go, Java, and C#.
- Keep Python `anip-runtime-utils` as the temporary behavioral reference.
- Move long-term parity definition into shared golden fixtures that every language runs.
- Keep all helper behavior contract-derived from capability metadata, input semantics, business effects, and runtime customization.
- Preserve the principle that domain-specific interpretation belongs in package metadata or app customization, not shared SDK code.

## Non-Goals

- Do not port GTM-specific routing behavior.
- Do not add hardcoded benchmark-question phrases.
- Do not change generated GTM services to make parity tests pass.
- Do not require LLM calls for SDK helper tests.
- Do not implement full benchmark runners in every language.
- Do not make Python the permanent source of truth.

## Public Surfaces

### TypeScript

Create a new workspace package:

- Package name: `@anip-dev/runtime-utils`
- Location: `packages/typescript/runtime-utils`
- Entry point: `src/index.ts`

### Go

Create a new package:

- Package path: `packages/go/runtimeutils`
- Import path: `github.com/anip-protocol/anip/packages/go/runtimeutils`

### Java

Create a new Maven module:

- Artifact: `dev.anip:anip-runtime-utils`
- Location: `packages/java/anip-runtime-utils`
- Package: `dev.anip.runtimeutils`

### C#

Create a new project:

- Package: `Anip.RuntimeUtils`
- Location: `packages/csharp/src/Anip.RuntimeUtils`
- Namespace: `Anip.RuntimeUtils`

## Shared Fixture Contract

Add shared fixtures under:

`packages/agent-consumption-fixtures/`

The first fixture file should be:

`packages/agent-consumption-fixtures/capability-selection.json`

Each case includes:

- `id`
- `conversation`
- `selected_capability`
- `expected_capability`
- `expected_missing_inputs`
- `expected_unsupported_effects`
- `metadata`

The metadata is intentionally small and language-neutral. It must include only the structures required by the helpers:

- `capability_id`
- `description`
- `business_effects.produces`
- `business_effects.does_not_produce`
- `input_specs`
- `app_profile.capability_framing`
- `app_profile.input_meanings`
- `app_profile.app_boundaries.unsupported_effects`
- `runtime_customization.capability_selection`
- `runtime_customization.normalization`

## Required Helper Behavior

Each non-Python SDK should expose equivalent behavior for:

- Text tokenization and semantic text key normalization.
- Compact capability scoring using capability id, description, framing, input names, input meanings, and app boundaries.
- Required input detection from declared `input_specs`.
- Grounded capability fallback when the selected capability has missing required context and a same-effect peer is better grounded.
- Stronger same-effect contract match when another same-effect capability is materially better and should clarify instead of executing a nearby contract.
- Unsupported-effect detection from declared unsupported effects and canonical effect terms.
- Compact capability brief rendering for agent prompts.

## Contract-Derived Behavior Only

Shared helpers may use generic lexical normalization such as tokenization, plural reduction, simple suffix variants, and stopwords.

Shared helpers must not contain:

- GTM terms such as account cohorts, Q2 candidates, routing queues, outreach, pipeline, enrichment, or account names.
- Benchmark fixture phrases.
- Product-specific actor names or role names.
- Tool-specific backend names.

If domain language matters, it must enter through fixture metadata or package runtime customization.

## Testing Strategy

Testing must be deterministic and offline.

Each language must run the same golden fixture suite and verify:

- Capability score ordering.
- Missing required inputs.
- Unsupported effect detection.
- Grounded fallback selection.
- Stronger same-effect contract match.
- Compact brief contains required contract fields and excludes unrelated metadata.

Python keeps its existing tests and should gain a fixture-parity test that reads the same shared fixtures. Once all languages pass the same fixture suite, fixture behavior becomes the parity contract.

## Release Strategy

This is a public SDK surface addition across ecosystems, so it should be treated as a feature release. The preferred version is `0.25.0`, unless the release strategy requires keeping it under the `0.24.x` line for compatibility timing.

The release should include:

- TypeScript package publish.
- Go module package availability.
- Java Maven artifact.
- C# NuGet package.
- Python package unchanged or patched only for fixture parity if needed.

## Risks

- Copying Python implementation too literally can create non-idiomatic SDKs. The fixtures should define behavior; each language can implement idiomatically.
- Over-porting can freeze experimental Python helpers too early. The first version should include only stable, validated algorithms.
- If fixtures are too GTM-shaped, parity will be fake. Fixtures must use neutral domains such as documents, tickets, records, or generic CRM-like examples without relying on showcase names.

## Acceptance Criteria

- TypeScript, Go, Java, and C# expose runtime-utils helper APIs.
- Python, TypeScript, Go, Java, and C# pass the same shared fixture suite.
- No shared helper implementation contains GTM-specific terms.
- Existing service/runtime tests continue to pass.
- Documentation explains that runtime-utils are consumer-side helper utilities, not the service-side trust boundary.
