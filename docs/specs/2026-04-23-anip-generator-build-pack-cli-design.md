# ANIP Standalone Generator, Build Packs, and Runnable Host Generation

## Status

Canonical implementation design.

First TypeScript slice is now implemented in the monorepo as `@anip-dev/generator-typescript`:

- standalone generator package and CLI
- runnable TypeScript host generation
- generated policy seam
- generated backend adapter seam
- generated smoke tests

Current limitation:

- the generated host is runnable generically, but provider-specific backend execution still remains an explicit extension seam
- multi-language build packs are still pending after the TypeScript slice

## Problem

Studio currently performs too much generation work directly:

- it compiles the current Developer Definition into exported generation artifacts
- it emits runtime target manifests and adapter scaffolds
- it packages blueprint-style outputs

That is useful for authoring, but it is not the target operating model.

The target operating model is:

- Studio authors and exports the ANIP Service Definition
- a standalone generator CLI consumes that definition
- a language build pack produces a runnable service project
- extension packs provide the explicit handwritten seams
- verifier packs validate the generated or completed implementation

This is required for:

- local generation outside Studio
- CLI and CI usage
- reproducible enterprise builds
- multi-language support
- reducing trust pressure by generating source locally instead of distributing opaque service binaries

## Core Terms

### ANIP Service Definition

The canonical machine-readable behavior contract.

It is the only behavior authority.

It defines:

- service identities
- capabilities
- semantic inputs and outputs
- approval, denial, clarification, and restriction posture
- audit and lineage expectations
- generation hints
- verification expectations

### Generator

A standalone package and CLI that consumes the ANIP Service Definition and produces runnable project outputs by invoking a selected build pack.

The generator:

- is not Studio-only
- must be runnable directly from CLI
- must be callable by Studio
- must be callable by CI/CD

### Build Pack

A language/runtime-specific package that knows how to turn the Service Definition into a runnable project in one target stack.

A build pack owns:

- project layout
- generic runtime host wiring
- generated capability declarations
- generated invoke routing
- generated manifest/discovery wiring
- generated config loading shell
- generated extension hook interfaces
- generated test harness shell

A build pack does not own behavior semantics. Those stay in the Service Definition.

### Extension Pack

A package or generated seam that contains the handwritten completion points for implementation-specific logic.

Examples:

- backend adapter execution
- secrets resolution
- provider-specific request/response transforms
- custom runtime policy decisions that cannot remain declarative

Extension packs must not redefine capability semantics outside the Service Definition.

## Required Separation

The required split is:

- Studio:
  - authoring
  - review
  - validation
  - export
  - generator invocation
- Generator CLI:
  - parse Service Definition
  - select build pack
  - emit runnable project
- Build Pack:
  - provide generic runnable host infrastructure for a language
- Extension Pack:
  - provide explicit handwritten realization seams

Studio may preview generator output.
Studio must not remain the only place generation can happen.

## Why GTM Worked

GTM already had a generic runtime host available in the language runtime packages.

For TypeScript specifically:

- `@anip-dev/service` provides the core service runtime
- `@anip-dev/hono`, `@anip-dev/express`, `@anip-dev/fastify` provide generic HTTP mounting
- generated artifacts plus handwritten completion logic were layered on top of those generic packages

So GTM was not proof that Studio itself is the final generator.
It was proof that:

- the runtime infrastructure already exists
- the missing extraction is the standalone generator/build-pack layer

## First Complete Slice

The first complete slice is TypeScript only.

It must provide:

1. Standalone generator package:
   - `@anip-dev/generator-typescript`
2. CLI entrypoint:
   - `anip-generate-typescript`
3. Input:
   - `anip-service-definition.json`
4. Output:
   - runnable TypeScript service project
5. Generated host:
   - HTTP server bootstrap
   - discovery endpoint
   - manifest endpoint
   - JWKS endpoint
   - token endpoint
   - permissions endpoint
   - invoke routing
6. Generated seams:
   - backend adapter interface
   - policy runtime interface
   - environment/config loader
7. Generated tests:
   - discovery/manifest smoke tests
   - capability invoke smoke tests

This first slice does not need to solve every language or every runtime mode.
It must prove the extracted architecture end to end.

## Generator CLI Contract

The generator CLI must support:

```bash
anip-generate-typescript \
  --definition ./anip-service-definition.json \
  --output ./generated/issue-tracker-service
```

Minimum flags:

- `--definition`
- `--output`

Recommended future flags:

- `--package-manager`
- `--http-runtime hono|express|fastify`
- `--with-rest`
- `--with-mcp`
- `--with-graphql`
- `--force`

The generator must not depend on Studio APIs to operate.

## Runnable Project Requirements

The generated TypeScript project must be runnable without Studio.

Minimum generated files:

- `package.json`
- `tsconfig.json`
- `src/generated/service-definition.ts`
- `src/generated/capabilities.ts`
- `src/generated/runtime-target.ts`
- `src/runtime/backend-adapter.ts`
- `src/runtime/policy.ts`
- `src/app.ts`
- `src/main.ts`
- `README.md`

The generated host must instantiate:

- `createANIPService(...)`
- a selected HTTP binding such as `mountAnip(...)`

## Generated Behavior Rules

The generated host must be generic.

That means:

- no Jira-specific logic
- no GTM-specific logic
- no domain word lists
- no project-specific heuristics

The generated host may implement generic runtime behavior from the contract, including:

- required-input clarification failures
- prepare-only write-adjacent behavior
- approval-gated stop behavior
- generic audit envelope shaping
- backend binding selection

Provider-specific execution remains behind the generated extension seam.

## Supported Languages

The long-term build-pack model supports at least:

- TypeScript
- Python
- Java
- Go
- C#

The generic requirement is:

- each language gets a build pack that targets an existing generic ANIP runtime package where possible
- each language gets the same contract input
- each language preserves the same extension seam categories

The generator model is:

- one Service Definition
- one generator command surface
- many build packs

## Relationship to Blueprints and Registry

This design is the local-generation execution layer for the Service Blueprint model.

The flow becomes:

1. Studio exports ANIP Service Definition.
2. Studio or user packages a Service Blueprint.
3. Consumer resolves build pack and verifier pack.
4. Generator CLI emits local source.
5. Consumer builds locally.
6. Verifier pack validates local implementation.

This keeps trust anchored in:

- Service Definition
- build pack identity
- verifier pack identity
- local build and conformance outputs

## Non-Goals for First Slice

Not required in the first slice:

- full multi-language generation
- registry publishing
- automatic extension implementation
- packaging every deployment target
- solving every runtime flavor

The first slice only needs to prove:

- standalone CLI generation
- runnable generated project
- generic host generation
- explicit extension seams

## Implementation Order

1. Add standalone TypeScript generator package.
2. Extract current TS generation logic from Studio into shared generator helpers where needed.
3. Generate runnable Hono-based host by default.
4. Emit generated capability declarations from the Service Definition.
5. Emit backend adapter and policy extension seams.
6. Emit a minimal test harness.
7. Update Studio to invoke the standalone generator instead of owning generation logic directly.

## Hard Rules

- The ANIP Service Definition remains the only behavior authority.
- Build packs generate runnable infrastructure, not hidden semantics.
- Extension packs may realize the contract; they may not replace the contract.
- Studio is an authoring surface, not the permanent home of generation logic.
- Generated runtime host code must stay generic across domains and integrations.
