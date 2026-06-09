# GTM Native Language Parity Plan

## Problem

The GTM showcase was originally implemented in Python. Recent TypeScript and Go validation used generated ANIP hosts that proxied execution to the reviewed Python ANIP services. That is useful for generated-host smoke testing, but it is not language implementation parity.

Language parity for the GTM showcase must prove that teams can build ANIP services in any supported language. A proxy that calls another ANIP service only proves fronting/bridging behavior.

## Correct Standard

Each supported language must expose the ANIP service boundary natively and own GTM business execution in that same language.

Allowed:

- Generated ANIP substrate from the same service definition.
- Custom code bundles that fill declared backend adapter, policy, app, and helper seams.
- Shared language-neutral fixture data where that data represents the GTM domain dataset.
- Direct calls to non-ANIP downstream systems such as Postgres, Cube, REST helper APIs, or MCP helper APIs when the target language owns the adapter code.

Not valid as parity evidence:

- Generated TypeScript/Go/Java/C# ANIP service proxying to Python ANIP services.
- Reusing Python ANIP services as the execution implementation for another target language.
- Claiming a proxy/bridge result as native language implementation parity.

## Target Shape

Python remains the reviewed reference implementation. For each additional language, create a native custom bundle:

- `examples/showcase/gtm/custom-code-bundles/gtm_pipeline_typescript`
- `examples/showcase/gtm/custom-code-bundles/gtm_pipeline_go`
- `examples/showcase/gtm/custom-code-bundles/gtm_pipeline_java`
- `examples/showcase/gtm/custom-code-bundles/gtm_pipeline_csharp`

Existing proxy bundles may remain only as fronting examples and must be documented as such:

- `gtm_pipeline_typescript_proxy`
- `gtm_pipeline_go_proxy`

## Implementation Slices

Implement each native bundle by domain slice:

1. Actor and approval policy.
2. Pipeline data summaries and masked financial visibility.
3. Enrichment summaries, lookalikes, and account risk enrichment.
4. Prioritization scoring, account prioritization, and route preview approvals.
5. Outreach drafts, follow-up variants, objection variants, and safe-stop approval behavior.
6. Composed/compound capability handling that preserves downstream approval and denial semantics.

## Verification Sequence

For each language:

1. Generate from the same GTM service definition using the language-native custom bundle.
2. Run compile/smoke tests.
3. Run deterministic service-level parity probes for representative capabilities.
4. Run the 350 bank by phase, `1..7`, using `gpt-5.4-mini`.
5. Run the 140 variation bank by phase, `1..7`, using `gpt-5.4-mini`.
6. Run full 350 and full 140 only after individual phases pass.

## Presentation Rule

Registry/docs must clearly distinguish:

- Native language parity: the language owns GTM behavior.
- Fronting/proxy example: the language fronts an existing implementation or backend.

Both are valuable, but they prove different things.
