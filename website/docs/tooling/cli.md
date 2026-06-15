---
title: ANIP CLI
description: Complete command reference for generating, validating, verifying, packaging, and scaffolding ANIP services.
---

# ANIP CLI

The ANIP CLI is the local entry point for generation, validation, package work, and fronting scaffolds.

Primary binary:

```bash
anip
```

Compatibility wrappers:

```bash
anip-generate
anip-verify
```

The wrappers remain for existing scripts, but new documentation should use `anip`.

## Command map

```text
anip generate
anip fronting scaffold
anip package build-local
anip package publish-bundle
anip package attach-implementation
anip validate
anip verify
anip version
```

| Command | Use when |
|---------|----------|
| `anip generate` | Generate service code or resolved definitions from a definition, package bundle, or Registry package. |
| `anip fronting scaffold` | Convert reviewed fronting starter intent into a normal ANIP service scaffold. |
| `anip package build-local` | Build deterministic local packages for examples and smoke tests. |
| `anip package publish-bundle` | Publish an existing portable package bundle to a Registry, or emit the exact publish request JSON. |
| `anip package attach-implementation` | Create/publish a new package revision with immutable implementation-material metadata. |
| `anip validate` | Validate a service definition/package and optional trust constraints. |
| `anip verify` | Alias-compatible verification command for packages and Registry records. |
| `anip version` | Print CLI version/build metadata. |

Additional release/operator binaries:

| Binary | Use when |
|--------|----------|
| `anip-registry-keygen` | Generate Ed25519 Registry signing keys and environment values. |
| `anip-registry` | Run the Registry service. |
| `anip-registry-smoke` | Smoke-test a Registry deployment by publishing, verifying, and generating from a package. |

## Install

Each release publishes prebuilt archives for:

- macOS arm64 and amd64.
- Linux arm64 and amd64.
- Windows arm64 and amd64.

macOS users can install through Homebrew:

```bash
brew tap anip-protocol/anip
brew install anip
```

Verify:

```bash
anip version
anip generate --help
anip validate --help
```

## `anip generate`

Generate service code, transport runners, Docker artifacts, locks, or resolved service definitions.

### Input modes

| Mode | Required flags |
|------|----------------|
| Local definition | `--definition`, `--target`, `--output` |
| Local package bundle | `--package-bundle`, `--target`, `--output` |
| Registry package | `--registry-url`, `--package` or `--package-id` + `--package-version`, `--target`, `--output` |
| Resolved definition output | `--definition`, `--output` |

### Targets

```text
python
typescript
go
java
csharp
```

### Framework variants

| Target | Frameworks |
|--------|------------|
| TypeScript | `hono` default, `express`, `fastify` |
| Java | `spring-boot` default, `quarkus` |

Other targets use their default runtime/framework shape.

### Common flags

| Flag | Purpose |
|------|---------|
| `--target` | Target language. |
| `--framework` | Target framework variant where supported. |
| `--transport` | `http`, `stdio`, or `http,stdio`. Default: `http`. |
| `--dependency-source` | `registry` or `local`. |
| `--output` | Destination directory or resolved definition path. |
| `--force` | Overwrite existing output. |
| `--port` | HTTP port for generated hosts. Default: `4100`. |
| `--dockerfile` | Include target-specific Dockerfile. |
| `--docker-compose` | Include local single-service compose file. |
| `--package-name` | Override generated package name. |
| `--write-lock` | Write an ANIP package lock for the resolved artifact. |
| `--lock-file` | Enforce an existing package lock during generation. |

### Generate from a service definition

```bash
anip generate \
  --definition ./anip-service-definition.json \
  --target python \
  --transport http,stdio \
  --dependency-source local \
  --output ./generated/my-service \
  --force
```

Use this when you are developing locally from a checked-out contract.

### Generate from a local package bundle

```bash
anip generate \
  --package-bundle ./my-service-0.2.0.anip-package.json \
  --target go \
  --dependency-source registry \
  --write-lock ./anip-package-lock.json \
  --output ./generated/my-service \
  --force
```

Use this when the artifact is already packaged and signed.

### Generate from Registry

```bash
anip generate \
  --registry-url http://127.0.0.1:8200/registry-api/v1 \
  --package jira-fronting-showcase@0.2.3 \
  --target python \
  --dependency-source registry \
  --output ./generated/jira-fronting \
  --force
```

Equivalent long form:

```bash
anip generate \
  --registry-url http://127.0.0.1:8200/registry-api/v1 \
  --package-id jira-fronting-showcase \
  --package-version 0.2.3 \
  --target python \
  --output ./generated/jira-fronting \
  --force
```

### Generate with framework variants

TypeScript Fastify:

```bash
anip generate \
  --definition ./anip-service-definition.json \
  --target typescript \
  --framework fastify \
  --transport http,stdio \
  --output ./generated/my-fastify-service \
  --force
```

Java Quarkus:

```bash
anip generate \
  --definition ./anip-service-definition.json \
  --target java \
  --framework quarkus \
  --transport http \
  --output ./generated/my-quarkus-service \
  --force
```

### Generate with custom code bundle

```bash
anip generate \
  --package-bundle ./gtm-pipeline-q2-review-0.4.4.anip-package.json \
  --target python \
  --custom-code-bundle ./custom-code-bundles/python \
  --verify-custom-code-bundle-digest sha256:<digest> \
  --output ./generated/gtm-python \
  --force
```

Rules:

- Local bundles are explicitly provided by the user.
- Remote bundle refs are metadata-only by default.
- `--fetch-custom-code-bundle` is reserved; remote fetching is not enabled yet.
- Custom bundles must not rewrite generated public manifest semantics.

### Generate with lock enforcement

First write a lock:

```bash
anip generate \
  --package-bundle ./my-service-0.2.0.anip-package.json \
  --target python \
  --write-lock ./anip-package-lock.json \
  --output ./generated/my-service \
  --force
```

Later enforce it:

```bash
anip generate \
  --registry-url https://registry.example.com/registry-api/v1 \
  --package my-service@0.2.0 \
  --lock-file ./anip-package-lock.json \
  --target python \
  --output ./generated/my-service \
  --force
```

If the Registry package digest differs from the lock, generation should fail.

## `anip fronting scaffold`

Convert reviewed fronting starter intent into a normal ANIP service scaffold.

Usage:

```text
anip fronting scaffold --starter <starter.json> --target <language> --output <dir> [flags]
```

Flags:

| Flag | Purpose |
|------|---------|
| `--starter` | Path to an `anip-fronting-starter/v0` JSON file. |
| `--target` | `python`, `typescript`, `go`, `java`, or `csharp`. Default: `python`. |
| `--transport` | `http`, `stdio`, or `http,stdio`. Default: `http`. |
| `--dependency-source` | `local` or `registry`. Default: `local`. |
| `--port` | Generated service port. Default: `9100`. |
| `--output` | Output directory. |
| `--force` | Overwrite output directory. |

Example:

```bash
anip fronting scaffold \
  --starter ./docs/examples/jira-fronting-showcase/anip-fronting-starter.json \
  --target python \
  --transport http,stdio \
  --output ./generated/jira-fronting \
  --force
```

Generated fronting outputs include:

- `anip-service-definition.json`
- `integration-fronting/adapter-bindings.json`
- `integration-fronting/backend-profile.example.json`
- `integration-fronting/backend-selection.example.json`
- `integration-fronting/backend-templates/*`
- `integration-fronting/conformance.json`

The starter is not the behavior truth. It is reviewed implementation intent. The generated ANIP service definition is the contract.

## `anip package build-local`

Build a deterministic local package bundle signed by the development Registry key.

Usage:

```text
anip package build-local --definition <anip-service-definition.json> --package-id <id> --package-version <version> --output-dir <dir> [flags]
```

Flags:

| Flag | Purpose |
|------|---------|
| `--definition` | Path to `anip-service-definition.json`. |
| `--package-id` | Package ID. |
| `--package-version` | Package version. |
| `--output-dir` | Output directory for manifest, lock, bundle, and README artifacts. |
| `--name` | Package display name. Defaults to service definition system name. |
| `--project-ref` | Project lineage reference. Defaults to `studio-source:<package-id>`. |
| `--product-revision-ref` | Product revision reference. |
| `--developer-revision-ref` | Developer revision reference. |
| `--generated-at` | Deterministic generated/published timestamp. |
| `--source-doc-url` | Optional HTTPS source documentation URL. |
| `--showcase-url` | Optional HTTPS showcase files URL. |
| `--port` | Example generated service port used in README commands. Default: `9100`. |
| `--write-definition` | Also write `<package-id>-<version>-service-definition.json`. |

Example:

```bash
anip package build-local \
  --definition ./anip-service-definition.json \
  --package-id my-service \
  --package-version 0.1.0 \
  --output-dir ./registry-packages \
  --write-definition
```

Use this for:

- Examples.
- Local smoke tests.
- Reproducible showcase artifacts.

Do not treat local package signatures as public Registry trust. Production publication should use a real Registry.

## `anip package publish-bundle`

Publish an existing portable package bundle to a Registry, or produce the exact publish request JSON for review/offline signing.

Usage:

```text
anip package publish-bundle --package-bundle <bundle> [flags]
```

Flags:

| Flag | Purpose |
|------|---------|
| `--package-bundle` | Existing package bundle or Registry package record JSON. |
| `--output` | Write the publish request JSON to this path instead of stdout. Cannot be combined with `--registry-url`. |
| `--registry-url` | Registry base URL. When present, publish the bundle instead of only writing the request. |
| `--publish-token` | Registry publish bearer token. Defaults to `ANIP_REGISTRY_PUBLISH_TOKEN`. |

Review the publish request without contacting a Registry:

```bash
anip package publish-bundle \
  --package-bundle ./my-service-0.1.0.anip-package.json \
  --output ./publish-request.json
```

Publish to a Registry:

```bash
ANIP_REGISTRY_PUBLISH_TOKEN=... \
anip package publish-bundle \
  --package-bundle ./my-service-0.1.0.anip-package.json \
  --registry-url https://registry.example.com
```

The command accepts either a Registry UI origin such as `https://registry.example.com` or an API base ending in `/registry-api/v1`.

## `anip package attach-implementation`

Create or publish a new package revision that includes immutable implementation-material metadata.

Usage:

```text
anip package attach-implementation --package-bundle <bundle> --package-version <new-version> --custom-code-bundle-ref <immutable-ref> [flags]
```

Flags:

| Flag | Purpose |
|------|---------|
| `--package-bundle` | Existing package bundle or Registry package record JSON. |
| `--package-version` | New package version to publish. |
| `--custom-code-bundle-ref` | Immutable custom bundle ref, for example `git+https://repo.git@commit#sha256:<digest>`. |
| `--implementation-material-ref` | Alias for `--custom-code-bundle-ref`. |
| `--custom-code-bundle` | Reviewed local bundle directory used only to compute digest; not uploaded. |
| `--bundle-tree-sha256` | Expected normalized local bundle tree digest. |
| `--implementation-material-title` | Human-readable implementation material title. |
| `--output` | Write publish request JSON to this path. |
| `--registry-url` | Registry base URL. When present, publish the new revision instead of only writing the request. |
| `--publish-token` | Registry publish bearer token. Defaults to `ANIP_REGISTRY_PUBLISH_TOKEN`. |

Example:

```bash
anip package attach-implementation \
  --package-bundle ./my-service-0.1.0.anip-package.json \
  --package-version 0.1.1 \
  --custom-code-bundle-ref git+https://github.com/example/bundles.git@<commit>#sha256:<archive-digest> \
  --custom-code-bundle ./bundles/python \
  --implementation-material-title "Python implementation bundle" \
  --output ./publish-request.json
```

This command does not upload or fetch custom code unless publishing metadata to Registry. It records implementation material so Registry can sign it as part of the new package revision.

## Registry operator helpers

These are separate binaries rather than `anip` subcommands.

### `anip-registry-keygen`

Generate a Registry signing keypair:

```bash
anip-registry-keygen --key-id anip-protocol-registry-root-2026-q2
```

Shell output:

```bash
ANIP_REGISTRY_KEY_ID=anip-protocol-registry-root-2026-q2
ANIP_REGISTRY_ED25519_PRIVATE_KEY=<base64-seed>
ANIP_REGISTRY_EXTRA_PUBLIC_KEYS=anip-protocol-registry-root-2026-q2=<base64-public-key>
```

Use `--json` when you need machine-readable output.

### `anip-registry-smoke`

Smoke-test a Registry deployment:

```bash
ANIP_REGISTRY_PUBLISH_TOKEN=... \
anip-registry-smoke \
  --registry-url https://registry.example.com \
  --definition ./anip-service-definition.json \
  --package-id registry-smoke-test \
  --package-version 0.1.0 \
  --target typescript
```

The smoke publishes a package, verifies it through Registry APIs, serves the UI route, and generates code from the published package.

## `anip validate` and `anip verify`

Validate definitions, package bundles, or Registry packages.

Usage:

```text
anip validate --definition <file> [flags]
anip validate --package-bundle <bundle> [flags]
anip validate --registry-url <url> --package <id@version> [flags]
```

`anip verify` accepts the same flags for compatibility.

Flags:

| Flag | Purpose |
|------|---------|
| `--definition` | Path to local `anip-service-definition.json`. |
| `--package-bundle` | Path to portable `.anip-package.json`. |
| `--registry-url` / `--registry-base` | Registry base URL. |
| `--package` | Registry package reference as `package_id@package_version`. |
| `--package-id` | Registry package ID. |
| `--package-version` | Registry package version. |
| `--lock-file` | Enforce an ANIP package lock file. |
| `--expected-contract-signature` | Expected compiled contract signature. |
| `--require-registry-mode` | Required Registry signing mode, such as `production`. |
| `--trusted-registry-key-id` | Trusted Registry receipt signing key ID. |

Examples:

```bash
anip validate --definition ./anip-service-definition.json
```

```bash
anip verify --package-bundle ./my-service-0.1.0.anip-package.json
```

```bash
anip verify \
  --registry-url http://127.0.0.1:8200/registry-api/v1 \
  --package my-service@0.1.0 \
  --lock-file ./anip-package-lock.json
```

## Recommended process flows

### Local development

```text
definition -> validate -> generate -> run tests -> build-local package
```

Commands:

```bash
anip validate --definition ./anip-service-definition.json
anip generate --definition ./anip-service-definition.json --target python --output ./generated/service --force
anip package build-local --definition ./anip-service-definition.json --package-id my-service --package-version 0.1.0 --output-dir ./registry-packages
```

### Agent-authored prototype

```text
prompt + examples -> draft definition -> validate -> generate -> review risks
```

This is useful for learning or prototyping before Studio review. It is not a production release path because it skips reviewed Product Design, Developer Design, Registry signing, package locks, and release evidence.

Commands:

```bash
anip validate --definition ./anip-service-definition.json
anip generate --definition ./anip-service-definition.json --target python --transport http,stdio --output ./generated/prototype --force
```

See [Agent-Authored Contract Quickstart](/docs/getting-started/agent-authored-contract) and `skills/anip-contract-drafter.md`.

### Registry publication

```text
bundle -> publish request review -> publish-bundle -> verify from Registry -> generate with lock
```

Commands:

```bash
anip package publish-bundle --package-bundle ./my-service-0.1.0.anip-package.json --output ./publish-request.json
ANIP_REGISTRY_PUBLISH_TOKEN=... anip package publish-bundle --package-bundle ./my-service-0.1.0.anip-package.json --registry-url https://registry.example.com
anip verify --registry-url https://registry.example.com --package my-service@0.1.0 --require-registry-mode production
```

### Consumer/CI generation

```text
Registry package -> verify -> lock -> generate -> conformance/scenario tests
```

Commands:

```bash
anip verify --registry-url https://registry.example.com/registry-api/v1 --package my-service@0.2.0
anip generate --registry-url https://registry.example.com/registry-api/v1 --package my-service@0.2.0 --target go --write-lock ./anip-package-lock.json --output ./generated/service --force
```

### Fronting project

```text
starter/template -> Studio project -> package -> generated fronting service -> live smoke
```

CLI-only starter path:

```bash
anip fronting scaffold --starter ./starter.json --target python --output ./generated/fronting --force
anip validate --definition ./generated/fronting/anip-service-definition.json
```

### Implementation material revision

```text
package 0.2.0 -> generated service -> custom bundle -> package 0.2.1 with bundle ref
```

Command:

```bash
anip package attach-implementation \
  --package-bundle ./my-service-0.2.0.anip-package.json \
  --package-version 0.2.1 \
  --custom-code-bundle-ref git+https://github.com/example/bundles.git@<commit>#sha256:<digest> \
  --custom-code-bundle ./bundles/python \
  --output ./publish-request.json
```

## Safety rules

- Generate from signed packages for consumer builds.
- Use locks in CI.
- Do not fetch remote code automatically.
- Do not commit local env files or secrets.
- Treat fronting starters as evidence, not signed behavior truth.
- Treat custom bundles as implementation material, not contract mutation.
- Re-publish a new package revision when signed metadata changes.
