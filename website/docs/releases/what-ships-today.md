---
title: What Ships Today
description: Current distribution status across all ANIP ecosystems.
---

# What Ships Today

ANIP is not a spec waiting for implementations. Here's what's available now.

## Published to package registries

| Ecosystem | Registry | Packages | Install |
|-----------|----------|----------|---------|
| TypeScript | npm | 14 packages (`@anip-dev/core` through `@anip-dev/stdio`) | `npm install @anip-dev/service @anip-dev/hono` |
| Python | PyPI | 11 packages (`anip-core` through `anip-grpc`) | `pip install anip-service anip-fastapi` |
| Java | Maven Central | 16 modules under `dev.anip` | See [Install](/docs/getting-started/install) |
| Go | Module tags | 1 module with 12 packages | `go get github.com/anip-protocol/anip/packages/go` |

## Available in-repo

| Artifact | Status |
|----------|--------|
| C# runtime + adapters (12 projects) | Source available, NuGet publishing not yet configured |
| Conformance suite | `pip install -e ./conformance` |
| Contract testing harness | `pip install -e ./contract-tests` |
| Studio standalone Docker | `docker build -t anip-studio studio/` |
| Showcase apps (travel, finance, DevOps) | Runnable from repo, not packaged as standalone artifacts |

## Not yet published

- C# NuGet packages
- Studio Docker image to GHCR
- Conformance suite to PyPI
- Contract testing harness to PyPI

For detailed package lists per ecosystem, see the [distribution page](https://github.com/anip-protocol/anip/blob/main/docs/distribution.md) in the repo.
