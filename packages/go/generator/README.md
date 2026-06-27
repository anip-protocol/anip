# generator

generator foundation for ANIP.

Current scope:

- resolve an `anip-service-definition.json` from a local file
- resolve an `anip-service-definition.json` from a portable `.anip-package.json` bundle
- resolve an `anip-service-definition.json` from Registry package identity
- normalize service/capability/runtime metadata from the Service Definition
- emit runnable `typescript`, `go`, `python`, `java`, and `csharp` ANIP host projects from the same generator core

The first migration target was `typescript` so the generator could reach parity with the existing TypeScript generator before adding native targets. Native `go`, `python`, `java`, and `csharp` targets now sit on the same shared generation model.

It establishes the generator-side contract boundary so future generation can consume:

- local exported Service Definitions
- Studio-local package bundles
- Registry package identities

without depending on Studio-local artifacts.

## CLI

Generate a TypeScript project from a local definition:

```bash
cd packages/go
go run ./cmd/anip generate \
  --definition ./path/to/anip-service-definition.json \
  --target typescript \
  --output ./generated-service \
  --force
```

Create a governed fronting scaffold directly from a reviewed starter file:

```bash
cd packages/go
go run ./cmd/anip fronting scaffold \
  --starter ./path/to/anip-fronting-starter.json \
  --target python \
  --dependency-source local \
  --transport http,stdio \
  --output ./generated-fronting-service \
  --force
```

The starter schema is intentionally small: system/service identity plus selected
backend operations mapped to governed capability IDs and bounded inputs. The
generated output is a normal ANIP service project with `anip-service-definition.json`
and `integration-fronting/` implementation profile artifacts. Raw API/MCP
operations remain backend implementation material; agents see only the governed
capabilities.

Generate a TypeScript project from Registry:

```bash
cd packages/go
go run ./cmd/anip generate \
  --registry-url http://127.0.0.1:8200 \
  --package issue-tracker-native-and-mcp-fronting@0.1.0 \
  --target typescript \
  --output ./generated-service \
  --force
```

Registry generation is trust-gated. The generator fetches the package, receipt, and Registry public keys, then verifies the manifest, Service Definition, recommended lock, and Ed25519 receipt before writing output.

Registry package lifecycle is also enforced. `superseded` and `deprecated` packages can still resolve, but the resolved result includes lifecycle metadata and a warning. `yanked` packages fail by default and require the explicit `--allow-yanked-package` CLI flag or equivalent resolver option for pinned historical reproduction. `takedown` packages are always blocked.

Every generated project also includes a framework-agnostic agent consumption kit:

```text
agent-consumption/
  agent-consumability.json
  agent-readiness.json
  agent-app-profile.json
  capability-index.json
  app-glue-required.json
  runtime-customization.json
  custom/
    runtime-overrides.json
    README.md
  prompt-brief.md
```

The JSON files are the authoritative artifacts. Agent frameworks such as LangGraph, Mastra, CrewAI, or custom runtimes can load them to guide capability routing, required context handling, business-effect boundaries, and explicit app-glue handoff without depending on language-specific generated code. Package-specific language normalization and capability-selection tuning belongs in `agent-consumption/custom/runtime-overrides.json`, not in shared runtime libraries.

Generate from a portable Studio-local package bundle without running Studio or Registry:

```bash
cd packages/go
go run ./cmd/anip generate \
  --package-bundle ./work-item-fronting-0.2.0.anip-package.json \
  --target typescript \
  --output ./generated-service \
  --force
```

Generate a Go project from a local definition:

```bash
cd packages/go
go run ./cmd/anip generate \
  --definition ./path/to/anip-service-definition.json \
  --target go \
  --output ./generated-go-service \
  --force
```

Generate a Python project from a local definition:

```bash
cd packages/go
go run ./cmd/anip generate \
  --definition ./path/to/anip-service-definition.json \
  --target python \
  --output ./generated-python-service \
  --force
```

Apply local handwritten implementation material through explicit extension seams:

```bash
cd packages/go
go run ./cmd/anip generate \
  --definition ./path/to/anip-service-definition.json \
  --target python \
  --output ./generated-python-service \
  --custom-code-bundle ./path/to/custom-bundle \
  --force
```

Custom code bundles are implementation material, not part of the signed ANIP behavior contract. The generator accepts local filesystem bundles only through `--custom-code-bundle` and writes `custom-code-bundle-report.json` with every applied file, SHA-256 digest, seam classification, byte size, overlay mode, and normalized bundle tree digest. Use `--verify-custom-code-bundle-digest sha256:<digest>` to block generation when the local reviewed bundle does not match the expected normalized tree digest.

Allowed overlays are limited to declared extension seams such as backend adapters, policy files, project metadata, and test files. Bundles must not replace generated substrate files such as `anip-service-definition.json`, generated runtime/capability metadata, generated runnable entrypoints, agent-consumption metadata, Docker files, or symlinks. Custom bundles may add alternate entrypoint files, but they must not overwrite the generated entrypoint that wires the signed contract into the runtime.

Remote bundle references are metadata-only by default. Package-declared refs and `--custom-code-bundle-ref` are validated and reported, but the generator does not download or apply remote code automatically. If a ref is present and no local bundle is supplied, the output includes a warning that implementation material is available but not applied. `--fetch-custom-code-bundle` is the explicit opt-in switch for future remote fetching; today it validates the ref and then fails because remote fetching is not enabled yet.

Allowed ref shapes:

- Git refs must use `git+https://...@<commit>#sha256:<bundle digest>`.
- Registry refs must use `registry://<package>/<artifact>@<immutable version>#sha256:<bundle digest>`.
- Object refs must use `object+https://...#sha256:<bundle digest>` or `object+s3://bucket/key#sha256:<bundle digest>`.
- Floating refs such as branches, `latest`, credentials, query strings, path traversal, and unpinned digests are rejected.

The ref digest pins the remote artifact bytes. A separate `bundle_tree_sha256` metadata field may pin the normalized local bundle tree digest for local-bundle verification. Even when remote fetching is implemented later, the bundle will remain implementation material: it may fill extension points, but it must not rewrite generated substrate files or bypass contract validation.

After local implementation and testing, publish a new signed package revision that records the immutable implementation material:

```bash
cd packages/go
go run ./cmd/anip package attach-implementation \
  --package-bundle ./path/to/package.anip-package.json \
  --package-version 0.1.1 \
  --custom-code-bundle-ref 'git+https://github.com/acme/anip-service.git@0123456789abcdef0123456789abcdef01234567#sha256:abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd' \
  --custom-code-bundle ./path/to/reviewed-custom-bundle \
  --registry-url http://127.0.0.1:8200/registry-api/v1
```

With `--registry-url`, the command publishes using `ANIP_REGISTRY_PUBLISH_TOKEN` or `--publish-token`. Without `--registry-url`, the same command writes the exact Registry publish request JSON to stdout or to `--output`. The CLI does not upload or fetch custom code automatically; it only records the immutable ref and optional normalized local tree digest so the Registry can include them in the signed manifest for the new package revision.

Generate a Java project from a local definition:

```bash
cd packages/go
go run ./cmd/anip generate \
  --definition ./path/to/anip-service-definition.json \
  --target java \
  --dependency-source local \
  --output ./generated-java-service \
  --force
```

Generate a C# project from a local definition:

```bash
cd packages/go
go run ./cmd/anip generate \
  --definition ./path/to/anip-service-definition.json \
  --target csharp \
  --dependency-source local \
  --output ./generated-csharp-service \
  --force
```

Resolve and write the raw Service Definition without generating a project:

```bash
cd packages/go
go run ./cmd/anip generate \
  --definition ./path/to/anip-service-definition.json \
  --output ./resolved-definition.json
```

`anip-generate` remains available as a compatibility binary, but `anip generate` is the primary command shape for package managers such as Homebrew. `anip validate` is the primary validator entrypoint; `anip verify` and `anip-verify` remain compatibility aliases.

Next steps:

- make registry-mode Java and .NET dependency distribution practical outside the monorepo
- add stronger parity validation against the legacy TypeScript generator outputs
