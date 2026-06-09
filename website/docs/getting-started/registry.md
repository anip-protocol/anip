---
title: Start With Registry
description: Browse packages and templates, verify what you consume, and generate services from trusted ANIP artifacts.
---

# Start With Registry

Registry is the fastest way to consume ANIP work that already exists.

Use it when you want to:

- Browse existing ANIP packages.
- Generate service code from a reviewed contract.
- Verify and lock the package you are consuming.
- Browse starter templates before creating a Studio project.
- Compare showcase packages such as GTM, Jira, GitHub, Slack, GitLab, Linear, Notion, and Superset.

Registry has two separate artifact types:

| Artifact | Use it for |
|----------|------------|
| Package | Consume a reviewed behavior contract and generate code. |
| Template | Start a new Studio project from safe starter material. |

Packages are for consumers. Templates are for authors.

## 1. Open Registry

Hosted Registry:

```text
https://registry.anip.dev/registry/packages
```

Local Registry:

```bash
cd registry
docker compose up --build
```

Open:

```text
http://127.0.0.1:8200/registry/packages
```

The package browser shows package identity, version, publication metadata, downloads, capability summaries, readiness guidance, package manifests, service definitions, recommended locks, and generator commands.

## 2. Choose A Package

Open a package when you want to answer:

- What governed capabilities does this service expose?
- Which ANIP spec version does it target?
- Is the package signed by a trusted Registry key?
- What source/project lineage produced it?
- Are there readiness findings the consuming agent should understand?
- Is there implementation material such as a custom bundle ref?
- What command generates code from this exact package?

Do not generate from loose JSON copied out of a page unless you are intentionally doing local development. Prefer a Registry package reference and a lock.

## 3. Verify Before Generating

Use `anip verify` against the Registry package:

```bash
anip verify \
  --registry-url https://registry.anip.dev/registry-api/v1 \
  --package jira-fronting-showcase@0.2.0 \
  --require-registry-mode production \
  --trusted-registry-key-id anip-protocol-registry-root-2026-q2
```

Verification checks package identity, manifest digest, service-definition digest, receipt signature, contract signature, and trust metadata.

For local development, use the local Registry URL:

```bash
anip verify \
  --registry-url http://127.0.0.1:8200/registry-api/v1 \
  --package jira-fronting-showcase@0.2.0
```

## 4. Generate With A Lock

Generate code and write a lock:

```bash
anip generate \
  --registry-url https://registry.anip.dev/registry-api/v1 \
  --package jira-fronting-showcase@0.2.0 \
  --target python \
  --transport http,stdio \
  --dependency-source registry \
  --write-lock ./anip-package-lock.json \
  --output ./generated/jira-fronting \
  --force
```

Regenerate later with lock enforcement:

```bash
anip generate \
  --registry-url https://registry.anip.dev/registry-api/v1 \
  --package jira-fronting-showcase@0.2.0 \
  --lock-file ./anip-package-lock.json \
  --target python \
  --output ./generated/jira-fronting \
  --force
```

If the package digest no longer matches the lock, generation should fail. That is intentional.

## 5. Use Templates To Start Projects

Templates live separately from packages:

```text
https://registry.anip.dev/registry/templates
```

Use a template when you want a safe starting point for a new Studio project. A template may include:

- Project type.
- ANIP spec version.
- Industry/domain labels.
- Markdown source documents.
- Suggested capability shape.
- Fronting starter intent.

Templates are not behavior authority. They help authors start. The reviewed Developer Definition and published package become the behavior authority later.

## 6. What Not To Trust

Do not treat these as trust signals:

- Download count.
- Popularity ordering.
- A nice README.
- A package name that looks official.
- A template that imports successfully.

Trust should come from:

- Registry key identity.
- Package receipt signature.
- Manifest and definition digests.
- Contract signature.
- Lock-file enforcement.
- Scenario validation and conformance evidence.

## Next Steps

- For the full trust loop, see [Package Trust Loop](/docs/getting-started/package-trust-loop).
- To run Registry and Studio locally, see [Run the Local Platform](/docs/getting-started/local-platform).
- For Registry internals and deployment details, see [ANIP Registry](/docs/tooling/registry).
- For project templates in Studio, see [Studio Templates](/docs/studio/templates).
