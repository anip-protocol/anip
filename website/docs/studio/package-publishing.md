---
title: Package Publishing
description: How Studio turns reviewed projects into signed Registry packages.
---

# Package Publishing

Package publishing is a release action.

Studio can help build and publish the package, but the package must represent a reviewed Developer Definition and approved release lineage.

## Package Authority

A published ANIP package is the consumable behavior contract.

It includes:

- Package ID and version.
- Service definition.
- Manifest.
- Recommended lock.
- Product and developer lineage.
- Contract signature.
- Registry receipt.
- Package README.
- Agent readiness metadata.
- Optional immutable implementation-material refs.

Consumers should generate from the package or a verified lock, not from copied page text.

## Local Package vs Registry Package

Studio may show local package state before remote publication.

| State | Meaning |
| --- | --- |
| Local package | Studio has built package material locally. Useful for review and local generation. |
| Registry package | Package has been published to Registry and is externally consumable. |
| Registry receipt | Registry signed and recorded package publication metadata. |
| Recommended lock | Digest-pinned consumer lock for repeatable generation. |

A local package is not the same as a published public package.

## Release Lineage

Studio should show release lineage clearly:

```text
Product Design revision -> Developer Definition revision -> Package version
```

PM/release approval should apply to that exact lineage.

If the Developer Definition changes, require a new approval for the new lineage.

## Publishing Preconditions

Before publishing:

- Product Design baseline is locked.
- Developer Design coverage is complete.
- Blocking diagnostics are resolved.
- Developer Definition is strict `anip/0.24`.
- Release lineage is approved.
- Package README is accurate.
- Package metadata contains no secrets.
- Source/project links are portable.
- Readiness findings are understandable to consumers.
- Registry trust settings are configured.

## What Package Metadata Should Not Contain

Do not publish:

- API tokens.
- Private source documents.
- Machine-local Studio URLs.
- Local file paths.
- Mutable implementation URLs without digest pins.
- Test-only evidence that exposes private data.
- Backend credentials.

If metadata changes after publication, publish a new package revision. Do not mutate a signed package in place.

## Implementation Material

Often, custom implementation material cannot be known at the initial Studio publication point.

Normal flow:

1. Publish behavior package.
2. Generate service.
3. Implement/test custom logic.
4. Attach immutable implementation-material ref and digest in a new package revision.

Do not add bundle refs after the fact without a new package revision. Package metadata is signed.

## Registry Configuration

Studio needs Registry settings when publishing:

| Setting | Purpose |
| --- | --- |
| `STUDIO_REGISTRY_URL` | Registry API base URL. |
| `STUDIO_REGISTRY_REQUIRED_MODE` | Expected Registry mode, such as `production`. |
| `STUDIO_REGISTRY_TRUSTED_KEY_ID` | Expected Registry signing key ID. |
| `STUDIO_REGISTRY_PUBLISH_TOKEN` | Server-side token used for publication. |

In hosted public Studio, publication should normally be disabled unless the deployment is intentionally write-capable and access-controlled.

## Publishing Checklist

Before clicking publish, verify:

- Package ID and version are correct.
- Product/developer lineage is correct.
- PM/release approval is present for that lineage.
- Contract signature is visible.
- Manifest and definition digests are present.
- README is not copied from another package.
- Agent readiness findings do not use internal Studio-only language.
- Public links are safe.
- No source document leaks are present.

After publication, consumers should verify and lock the package before generation. See [Package Trust Loop](/docs/getting-started/package-trust-loop).
