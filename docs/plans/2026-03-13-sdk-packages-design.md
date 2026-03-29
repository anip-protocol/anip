# ANIP SDK Packages Design

## Goal

Extract reusable ANIP SDK packages from the reference implementations so that correct ANIP v0.3 behavior becomes the default for adopters, rather than something each implementer must build from scratch.

## Architecture

Three packages per language with a clean dependency chain:

```
anip-core  -->  anip-crypto  -->  anip-server
```

Each layer is independently installable. Adopters stop at the layer they need:

- **Types only?** Install core.
- **Verifying signatures?** Install crypto (pulls in core).
- **Building an ANIP service?** Install server (pulls in crypto and core).

## Package Definitions

### 1. anip-core

**Python:** `anip-core` on PyPI (`anip_core`)
**TypeScript:** `@anip-dev/core` on npm

**Contents:**

- Protocol models: `ANIPManifest`, `CapabilityDeclaration`, `DelegationToken`, `InvokeRequest`, `InvokeResponse`, `PermissionResponse`, `TrustPosture`, `AnchoringPolicy`, `CheckpointBody`
- Side-effect types: `SideEffect`, `SideEffectType`
- Cost models: `Cost`, `CostActual`, `CostCertainty`
- Failure semantics: `ANIPFailure`, `Resolution`, structured failure types
- Delegation types: `DelegationConstraints`, `ConcurrentBranches`, `Purpose`
- Service identity: `ServiceIdentity`, `ManifestMetadata`, `ProfileVersions`
- Protocol constants: version strings (`anip/0.3`), profile version identifiers

**Boundary rules:**

- No crypto operations
- No signing or verification
- No storage or database
- No network I/O
- Stays mostly declarative; avoid helper/convenience creep

**Dependencies:**

- Python: `pydantic`
- TypeScript: `zod`

### 2. anip-crypto

**Python:** `anip-crypto` on PyPI (`anip_crypto`)
**TypeScript:** `@anip-dev/crypto` on npm

**Contents:**

- `KeyManager`: EC P-256 keypair generation, dual keypair management (delegation + audit), key persistence, KID derivation via SHA-256 thumbprint
- JWT helpers: `sign_jwt(claims, key)`, `verify_jwt(token, key)` with ES256
- Detached JWS: `sign_jws_detached(payload, key, kid)`, `verify_jws_detached(jws, payload, key)` for both delegation and audit purposes
- Purpose-specific methods on KeyManager enforce key separation at the API level
- JWKS: `build_jwks(key_manager)` constructs the public key set response
- Verification helpers: explicit `(artifact, signature, key)` tuples, not magic "verify object" calls
- Canonicalization: public, reusable canonical JSON helpers for verifiable artifacts

**Boundary rules:**

- No delegation chain logic
- No checkpoint/Merkle logic
- No storage or database
- No HTTP/transport
- Stays focused on cryptographic primitives and ANIP-aware verification, not workflow logic

**Dependencies:**

- Python: `anip-core`, `cryptography`, `PyJWT`
- TypeScript: `@anip-dev/core`, `jose`

### 3. anip-server

**Python:** `anip-server` on PyPI (`anip_server`)
**TypeScript:** `@anip-dev/server` on npm

**Contents:**

- **Delegation engine:** `issue_root_token(authenticated_principal, subject, scope, ...)` for root tokens (issuer derived from service_id, root_principal from authenticated context), `delegate(parent_token, subject, scope, ...)` for child tokens (issuer and root_principal derived from parent chain), `validate_delegation()`, scope narrowing validation, constraint narrowing, concurrent branch enforcement, budget authority checking, chain walking (DAG traversal to root principal). No raw issuer_id/root_principal parameters in the public API — trust context is always derived, never caller-supplied.
- **Permission discovery:** `discover_permissions(token, capabilities)` classifying capabilities as available/restricted/denied
- **Manifest builder:** `build_manifest(capabilities, trust, identity)` with SHA-256 capability hash, metadata, expiry. Parameter-driven, not env-var-driven.
- **Audit log:** `log_entry()`, `query_entries()`, hash chain computation. Uses storage abstraction.
- **Merkle tree:** RFC 6962 implementation. `build_tree()`, `get_root()`, `inclusion_proof()`, `consistency_proof()`, `verify_inclusion_proof()`. SHA-256 with `0x00` leaf prefix, `0x01` node prefix.
- **Checkpoints:** `create_checkpoint(sign_fn)` returning `(body, signature)` tuple. `CheckpointPolicy` (entry count threshold). `CheckpointScheduler` (interval-based, deliberately small).
- **Sinks:** Abstract `CheckpointSink` interface with `publish(signed_checkpoint)`. `LocalFileSink` built-in. Queue with retry for async delivery.
- **Storage:** Abstract `StorageBackend` interface for token store, audit log, checkpoint persistence. `SQLiteStorage` as default. Adopters can implement for Postgres, DynamoDB, etc.

**Boundary rules:**

- No HTTP framework code (no FastAPI, no Hono)
- No capability business logic
- No env-var parsing (that is the application's job)
- Library of server primitives, not an application framework

**Dependencies:**

- Python: `anip-core`, `anip-crypto`
- TypeScript: `@anip-dev/core`, `@anip-dev/crypto`
- SQLite drivers are optional/default (not required with custom storage backend)

## Repository Layout

```
packages/
  python/
    anip-core/
      pyproject.toml
      src/anip_core/
        __init__.py          # facade re-exports
        models.py
        failures.py
        constants.py
      tests/
    anip-crypto/
      pyproject.toml
      src/anip_crypto/
        __init__.py          # facade re-exports
        keys.py
        jwt.py
        jws.py
        jwks.py
        verify.py
      tests/
    anip-server/
      pyproject.toml
      src/anip_server/
        __init__.py          # facade re-exports
        delegation.py
        permissions.py
        manifest.py
        audit.py
        merkle.py
        checkpoint.py
        sinks.py
        storage.py
      tests/
  typescript/
    package.json             # workspace root
    tsconfig.base.json
    core/
      package.json           # @anip-dev/core
      src/
        index.ts
        models.ts
        failures.ts
        constants.ts
      tests/
    crypto/
      package.json           # @anip-dev/crypto
      src/
        index.ts
        keys.ts
        jwt.ts
        jws.ts
        jwks.ts
        verify.ts
      tests/
    server/
      package.json           # @anip-dev/server
      src/
        index.ts
        delegation.ts
        permissions.ts
        manifest.ts
        audit.ts
        merkle.ts
        checkpoint.ts
        sinks.ts
        storage.ts
      tests/
```

## Testing Strategy

- **Package tests:** Fresh, public-API-focused tests per package. Clean, adopter-friendly, serve as usage documentation.
- **Example tests:** Existing tests in `examples/` remain as integration/regression coverage, proving end-to-end behavior after refactoring to consume packages.

## Post-Extraction: Example Refactoring

The existing `examples/anip/` Python package is renamed from `anip_server` to `anip_flight_demo`. Both `examples/` and `adapters/` are refactored to import from the new SDK packages, validating that the extraction works correctly.

## Language Priorities

First wave: Python and TypeScript (both already have reference implementations).

Go, Java, C#, Rust follow in later phases per the SDK strategy document.

## Versioning

- Packages use language-native versioning (semver).
- Each package declares which ANIP protocol version it supports (`anip/0.3`).
- Protocol support is explicit in docs and runtime metadata.

## Key Design Principles

1. **Library, not framework.** Explicit parameters. No env-var magic. No opinion on HTTP framework.
2. **Storage is abstract.** SQLite is a default, not a requirement. The public API never leaks SQLite assumptions.
3. **Verification is explicit.** APIs take `(artifact, signature, key)` tuples, reflecting actual signed artifact shapes.
4. **Canonicalization is reusable.** Public helpers, not buried inside signing methods.
5. **Key separation is enforced.** Purpose-specific methods prevent delegation/audit key misuse at the API level.
6. **CheckpointScheduler stays small.** Implementation helper, not a job framework.
7. **Core stays declarative.** Models and constants only. No behavioral creep.
8. **Trust context is derived, never caller-supplied.** Root token issuance requires an `authenticated_principal` (the application layer's job to authenticate). Child token issuance derives `issuer` and `root_principal` from the parent chain. The SDK never exposes raw `issuer_id` or `root_principal` parameters that would let callers forge trust context.
