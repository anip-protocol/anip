---
title: Generated Services
description: How the GTM package and custom bundles generate five native service implementations.
---

# Generated Services

The GTM services are generated from one package:

```text
examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.4.anip-package.json
```

The package defines the signed ANIP behavior contract. The custom-code bundles fill implementation seams for each language.

## Generated outputs

```text
examples/showcase/gtm/generated/language-parity/python/
examples/showcase/gtm/generated/language-parity/typescript/
examples/showcase/gtm/generated/language-parity/go/
examples/showcase/gtm/generated/language-parity/java/
examples/showcase/gtm/generated/language-parity/csharp/
```

Each output exposes the same public ANIP capability semantics. They differ only in language runtime and implementation seam code.

## Custom bundles

Release-target bundles:

| Language | Bundle |
| --- | --- |
| Python | `examples/showcase/gtm/custom-code-bundles/gtm_pipeline_python_native` |
| TypeScript | `examples/showcase/gtm/custom-code-bundles/gtm_pipeline_typescript` |
| Go | `examples/showcase/gtm/custom-code-bundles/gtm_pipeline_go_native` |
| Java | `examples/showcase/gtm/custom-code-bundles/gtm_pipeline_java_native` |
| C# | `examples/showcase/gtm/custom-code-bundles/gtm_pipeline_csharp_native` |

Bundles may implement:

- backend adapter queries,
- actor parsing helpers,
- approval storage,
- language-specific service wiring,
- GTM rendering logic.

Bundles must not implement:

- hidden capabilities,
- weaker approval policy,
- different side-effect posture,
- different input contract semantics,
- different composition semantics,
- contract mutations hidden in generated code.

## Generate Locally

Run generation from `packages/go`. These commands generate from the same `gtm-pipeline-q2-review@0.4.4` package and attach the reviewed language-specific custom bundle.

### Python

```bash
cd packages/go
go run ./cmd/anip generate \
  --package-bundle ../../examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.4.anip-package.json \
  --target python \
  --transport http \
  --dependency-source registry \
  --custom-code-bundle ../../examples/showcase/gtm/custom-code-bundles/gtm_pipeline_python_native \
  --output ../../examples/showcase/gtm/generated/language-parity/python \
  --force
```

### TypeScript

```bash
cd packages/go
go run ./cmd/anip generate \
  --package-bundle ../../examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.4.anip-package.json \
  --target typescript \
  --transport http \
  --dependency-source registry \
  --custom-code-bundle ../../examples/showcase/gtm/custom-code-bundles/gtm_pipeline_typescript \
  --output ../../examples/showcase/gtm/generated/language-parity/typescript \
  --force
```

### Go

```bash
cd packages/go
go run ./cmd/anip generate \
  --package-bundle ../../examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.4.anip-package.json \
  --target go \
  --transport http \
  --dependency-source registry \
  --custom-code-bundle ../../examples/showcase/gtm/custom-code-bundles/gtm_pipeline_go_native \
  --output ../../examples/showcase/gtm/generated/language-parity/go \
  --force
```

### Java

```bash
cd packages/go
go run ./cmd/anip generate \
  --package-bundle ../../examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.4.anip-package.json \
  --target java \
  --transport http \
  --dependency-source registry \
  --custom-code-bundle ../../examples/showcase/gtm/custom-code-bundles/gtm_pipeline_java_native \
  --output ../../examples/showcase/gtm/generated/language-parity/java \
  --force
```

### C#

```bash
cd packages/go
go run ./cmd/anip generate \
  --package-bundle ../../examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.4.anip-package.json \
  --target csharp \
  --transport http \
  --dependency-source registry \
  --custom-code-bundle ../../examples/showcase/gtm/custom-code-bundles/gtm_pipeline_csharp_native \
  --output ../../examples/showcase/gtm/generated/language-parity/csharp \
  --force
```

## Bundle Digest Verification

Release generation should verify the selected bundle digest. Read the digest from:

```text
examples/showcase/gtm/custom-code-bundles/bundle-catalog.json
```

Then pass it as `--verify-custom-code-bundle-digest`. Example for Go:

```bash
cd packages/go
go run ./cmd/anip generate \
  --package-bundle ../../examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.4.anip-package.json \
  --target go \
  --transport http \
  --dependency-source registry \
  --custom-code-bundle ../../examples/showcase/gtm/custom-code-bundles/gtm_pipeline_go_native \
  --verify-custom-code-bundle-digest sha256:<gtm_pipeline_go_native_digest> \
  --output ../../examples/showcase/gtm/generated/language-parity/go \
  --force
```

## Legacy Single-Command Shape

The shorter form is useful for quick experiments:

```bash
cd packages/go
go run ./cmd/anip generate \
  --package-bundle ../../examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.4.anip-package.json \
  --target go \
  --transport http \
  --dependency-source registry \
  --custom-code-bundle ../../examples/showcase/gtm/custom-code-bundles/gtm_pipeline_go_native \
  --output ../../examples/showcase/gtm/generated/language-parity/go \
  --force
```

For release work, include bundle digest verification.

## Docker images

The generated services are packaged as:

```text
anipprotocol/showcase-gtm-python:0.4.4
anipprotocol/showcase-gtm-typescript:0.4.4
anipprotocol/showcase-gtm-go:0.4.4
anipprotocol/showcase-gtm-java:0.4.4
anipprotocol/showcase-gtm-csharp:0.4.4
```

The shared agent UI image is:

```text
anipprotocol/showcase-gtm-agent-ui:0.4.4
```
