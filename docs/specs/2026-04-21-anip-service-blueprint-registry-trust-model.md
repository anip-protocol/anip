# ANIP Service Blueprints, Local Generation, and Registry Trust Model

## Purpose

ANIP should let teams distribute governed service behavior without asking consumers to trust opaque prebuilt services or binaries.

The portable unit should be a signed, inspectable service contract plus the toolchain metadata needed to generate, inspect, build, and verify the implementation locally.

This document is the canonical registry and blueprint trust-model spec. Older exploratory registry notes should be treated as background unless their terminology is explicitly carried forward here.

Core message:

**Design the blueprint. Generate locally. Inspect the source. Build it yourself. Verify conformance.**

This is a stronger enterprise trust model than distributing generated applications or prebuilt binaries directly.

## Naming

Use distinct names for the human-facing concept and the technical artifact.

### ANIP Service Blueprint

The user-facing distributable package.

A blueprint is the reviewable design package that contains:

- canonical service definition
- metadata
- signatures
- build pack requirements
- verifier pack requirements
- optional extension pack references
- optional regression pack references
- compatibility declarations

### ANIP Service Definition

The canonical machine-readable contract inside a blueprint.

Suggested filename:

- `anip-service-definition.json`

This is the externalized name for what Studio currently models as the Developer Definition. Studio can keep "Developer Definition" as the authoring lane label, but exported artifacts should use "ANIP Service Definition" when presented outside Studio.

### ANIP Build Pack

A language/runtime-specific generator package.

Examples:

- `anip-build-pack-python`
- `anip-build-pack-typescript`
- `anip-build-pack-java`
- `anip-build-pack`
- `anip-build-pack-csharp`

Build packs generate source locally. They should not distribute opaque generated service binaries.

### ANIP Verifier Pack

A package that validates generated or completed implementations against the Service Definition.

Verifier packs should produce durable conformance evidence tied to the same contract identity used for generation.

### ANIP Extension Pack

An optional package for implementation hooks that cannot reasonably stay fully declarative.

Extension packs must be signed, namespaced, versioned, and constrained so they do not become a hidden business policy layer.

### Lockfiles

ANIP should distinguish two lockfile roles.

- **Publisher recommended lock:** shipped with a blueprint to declare the author-tested schema, build pack, verifier pack, runtime, extension, and regression pack set.
- **Consumer project lock:** produced or updated by the consuming team when they resolve, generate, build, and verify locally.

The consumer project lock is the authoritative record for a local delivery pipeline. The publisher recommended lock is guidance and a reproducibility starting point, not a mandatory enterprise runtime dependency.

## Trust Model

The trust posture should shift from:

- trust this prebuilt service
- trust this generated binary
- trust hidden prompt or skill behavior

to:

- inspect the Service Definition
- verify the blueprint signature
- resolve exact build and verifier packs
- generate source locally
- inspect generated source
- build in local CI
- verify runtime conformance
- retain signed evidence

This does not remove trust entirely. It narrows trust to smaller, reusable, reviewable components:

- schema
- generator/build pack
- runtime library
- verifier pack
- signed extension packs
- registry provenance

That is a materially better enterprise adoption story.

Hard rule:

**The ANIP Service Definition is the only behavior authority. Manifest files, lockfiles, build packs, verifier packs, extension packs, registry receipts, and generated source are subordinate to the Service Definition.**

## Artifact Package

A blueprint package should have a stable layout.

```text
anip-blueprint/
  manifest.json
  anip-service-definition.json
  anip.recommended.lock
  signatures/
    blueprint.sig
    service-definition.sig
    registry-receipt.json
  regression/
    regression-pack.json
  extensions/
    extension-manifest.json
  docs/
    README.md
```

### `manifest.json`

The package manifest should include:

- blueprint id
- name
- description
- publisher
- version
- license
- schema version
- supported build packs
- supported verifier packs
- required extension packs
- optional extension packs
- regression pack references
- compatibility matrix
- source provenance
- registry provenance

### `anip-service-definition.json`

The canonical behavior contract.

It should include:

- service identities
- capabilities
- input contracts
- output contracts
- side-effect posture
- actor and authority model
- approval posture
- denial, restriction, and clarification rules
- audit and lineage requirements
- backend binding declarations
- generator hints
- verification hints
- extension hook declarations

### `anip.recommended.lock`

The publisher recommended lock should include:

- Service Definition digest
- manifest digest
- schema version and digest
- build pack names, versions, digests, and signatures
- runtime package names, versions, digests, and signatures
- verifier pack names, versions, digests, and signatures
- extension pack names, versions, digests, and signatures
- regression pack digests
- author-tested generated-at timestamp
- author-tested generator command metadata

### Consumer `anip.lock`

The consumer lock is created during local resolution and generation.

It should include:

- selected blueprint identity
- selected Service Definition digest
- selected manifest digest
- exact build pack identities used locally
- exact runtime package identities used locally
- exact verifier pack identities used locally
- exact extension pack identities used locally
- generated source digest manifest
- local generation command metadata
- local conformance report reference

The consumer lock may intentionally differ from the publisher recommended lock when an enterprise pins approved internal build packs, runtime libraries, or verifier packs.

## Signatures and Evidence

Studio already displays contract evidence such as a SHA-256 signature for the saved compiled contract identity.

That should become the foundation for registry-grade verification, but a hash alone is not enough.

Use three distinct concepts:

### Digest

A deterministic hash over canonical content.

Example:

- `sha256(canonical_anip_service_definition_json)`

The digest proves content identity.

### Signature

A signer attestation over a digest and selected metadata.

The signature proves who signed that content identity.

### Registry Receipt

A registry-issued receipt proving that a specific artifact digest, signature, publisher, and version were accepted by the registry at a specific time.

The receipt should include:

- registry id
- package id
- package version
- artifact digests
- signer identity
- publisher identity
- accepted timestamp
- registry signature
- optional transparency log reference

## Registry Verification

ANIP Registry should verify artifacts before publishing and when resolving dependencies.

Registry checks should include:

- schema validation
- canonical digest recomputation
- signature validation
- publisher authorization
- version immutability
- extension namespace ownership
- compatibility matrix validation
- optional regression pack validation
- malware/static policy checks for build, verifier, and extension packs

Published artifact versions are immutable.

Hard rules:

- a published blueprint version must not be overwritten
- a published manifest digest must not change
- a published Service Definition digest must not change
- a published registry receipt must remain tied to the original digests
- changed content requires a new version
- yanking or deprecating a version may change registry metadata, but not the published artifact bytes or signed digest identities

Registry consumers should be able to run:

```bash
anip registry verify anip-blueprint/
anip blueprint inspect anip-blueprint/
anip generate --blueprint anip-blueprint/ --language go
anip verify --definition anip-blueprint/anip-service-definition.json --target ./generated
```

## Studio Integration

Studio should connect this model directly to the existing Developer Definition and Contract Evidence flow.

### Export

Studio should support:

- Export ANIP Service Definition
- Package ANIP Service Blueprint
- Generate `anip.recommended.lock`
- Generate local conformance plan
- Include regression pack
- Include extension manifest

### Sign

Studio should support signing:

- Product Design revision identity
- ANIP Service Definition identity
- blueprint manifest identity
- PM signoff identity
- verification evidence identity

Signing can start with local development keys and later support enterprise signing providers.

### Publish

Studio should support publishing to:

- local filesystem
- private registry
- public ANIP Registry

Publishing should never require uploading generated service source or built binaries.

Published blueprint versions must be immutable. If Studio packages a changed Service Definition, manifest, regression pack, or extension manifest, it must require a new blueprint version before publishing.

### Import

Studio should support importing a blueprint from:

- local package
- registry reference
- git reference

Import should show:

- publisher
- signatures
- registry receipt
- schema compatibility
- build pack compatibility
- extension requirements
- verifier requirements
- regression coverage

### Contract Evidence UI

The current Contract Evidence panel should evolve from saved compiled contract identity into a fuller evidence chain:

- Product Design revision digest/signature
- ANIP Service Definition digest/signature
- Blueprint manifest digest/signature
- Generator/build pack identity
- Verifier pack identity
- Registry receipt
- Generation run identity
- Evaluation run identity
- Observed service metadata identity
- PM signoff identity

The verification page should make mismatches obvious before deeper tests run.

## Local Generation Flow

Expected consumer flow:

1. Pull or receive blueprint package.
2. Inspect manifest and Service Definition.
3. Verify signatures and registry receipt.
4. Resolve build pack and verifier pack from `anip.recommended.lock` or enterprise-approved policy.
5. Generate source locally in the chosen language.
6. Review generated source and extension hooks.
7. Implement or bind required extension hooks.
8. Build locally.
9. Run verifier pack and regression pack.
10. Save consumer `anip.lock` and conformance report.

No opaque service binary needs to be trusted.

## Resolution and Distribution Policy

Default posture:

- ANIP Registry owns build pack metadata, trust identity, signatures, compatibility declarations, and registry receipts.
- Language-native registries may host runtime/helper packages when that is the normal dependency channel for the target ecosystem.
- The consumer `anip.lock` records both the ANIP Registry identity and any language-native package identities that were resolved locally.

Examples:

- Python runtime helper packages may be installed from PyPI, but their ANIP trust identity should still be recorded in the build pack metadata and consumer lock.
- Java runtime helper packages may be installed from Maven repositories, but the ANIP Registry should still declare supported versions and compatibility.
- Go modules may resolve through normal module tooling, but the generated source and consumer lock should still bind back to the selected ANIP build pack identity.

This avoids turning ANIP Registry into a replacement for every language package ecosystem while still keeping ANIP-specific trust, compatibility, and verification metadata centralized.

## Conformance Report

Local verification should emit a signed or signable report.

Suggested filename:

- `anip-conformance-report.json`

Suggested statuses:

- `schema_valid`
- `signature_valid`
- `dependencies_resolved`
- `generated`
- `extension_hooks_bound`
- `runtime_surface_valid`
- `observed_metadata_valid`
- `regression_green`
- `contract_evidence_aligned`
- `pm_signoff_aligned`

The report should include:

- Service Definition digest
- blueprint manifest digest
- lockfile digest
- generator/build pack identities
- verifier pack identities
- generated source digest summary
- runtime metadata digest
- regression result digest

## Extension Pack Guardrails

Bundled custom logic is useful, but it must not become a backdoor for hidden business truth.

Rules:

- extension packs may implement declared hooks
- extension packs may provide backend adapters
- extension packs may provide runtime helper logic
- extension packs may not introduce undeclared capability semantics
- extension packs may not redefine capability semantics outside the Service Definition
- extension packs may not silently bypass approval, denial, restriction, or audit requirements
- extension packs must declare every hook they bind
- extension packs must not bind hooks that are absent from the Service Definition or extension manifest
- extension packs must be signed and namespaced
- verifier packs must fail when required hook bindings are missing
- verifier packs must fail when extension metadata does not match the declared hook set
- verifier packs must fail when observed runtime behavior bypasses declared approval, denial, restriction, audit, or lineage semantics

Policy stays declarative whenever possible.

Behavior-critical semantics stay in the Service Definition.

## Relationship to Integration Fronting

This trust model works for both:

- ANIP services generated in front of native APIs
- ANIP services generated in front of MCP servers

The same Service Blueprint can declare backend implementation profiles such as:

- native REST adapter
- MCP adapter
- database adapter
- hybrid adapter

The generated governed capability surface stays stable while the backend adapter implementation can vary by build pack or extension pack.

This directly supports the Jira showcase:

- same Jira Service Blueprint
- native REST implementation profile
- Atlassian MCP implementation profile
- same regression pack
- same governed capability contract
- locally generated and verified source

## Implementation Slices

### Slice 1: Naming and Export Shape

- Rename external export wording from Developer Definition to ANIP Service Definition.
- Keep Studio lane wording as Developer Definition where useful.
- Add blueprint package manifest generation.
- Add `anip.recommended.lock` generation from current generator/runtime/verifier versions.

### Slice 2: Evidence Chain

- Expand Contract Evidence to show manifest, definition, generator, verifier, and registry identities.
- Add evidence mismatch warnings before generation and verification.
- Store evidence chain on generation and evaluation runs.

### Slice 3: Local Package Export

- Export a complete local blueprint package.
- Include Service Definition, manifest, lockfile, regression pack, and extension manifest.
- Add CLI command examples to exported README.

### Slice 4: Registry Compatibility

- Add registry metadata fields to manifest.
- Add registry receipt placeholder support.
- Add import verification for local registry receipts.

### Slice 5: Registry Publish and Pull

- Publish blueprint package to private/public registry.
- Pull blueprint package from registry into Studio.
- Verify signatures and receipts before allowing generation.

## Implementation Priority

Do not build the public registry first.

Recommended sequence:

1. Local blueprint export from Studio.
2. Local generation with build packs and consumer `anip.lock`.
3. Local conformance report tied to the Service Definition digest.
4. Private registry publish/pull with signatures and receipts.
5. Public registry and ecosystem discovery.

## Open Questions

- What signing format should ANIP use first: minisign, Sigstore, JWS, or another envelope?
- Should registry receipts use a transparency log from day one?
- Should generated source digest summaries include every generated file or a canonical manifest only?
- Which runtime/helper package ecosystems should be mirrored or pinned by official ANIP build packs first?
- Should Studio support organization signing keys before public registry publishing?
- How should private enterprise registries federate with the public ANIP Registry?
