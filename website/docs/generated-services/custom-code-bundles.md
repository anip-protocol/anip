---
title: Custom Code Bundles
description: How implementation material fills generated service seams without changing the signed ANIP behavior contract.
---

# Custom Code Bundles

Generated ANIP services provide substrate: manifest shape, validation, dispatch, policy hooks, approval-grant validation, audit linkage, and transport runners. Custom code bundles fill implementation seams.

They are the right place for system-specific execution logic.

The core rule:

```text
Signed package = public behavior contract.
Custom bundle = reviewed implementation material behind that contract.
```

If a bundle changes what the service claims to do, the contract is wrong. Fix the Studio project/package instead of hiding the change in custom code.

## What bundles are for

Use bundles for:

- Backend adapters.
- Domain-specific handlers.
- Catalog resolvers.
- Policy hooks.
- Data clients.
- Service-specific tests.
- Runtime glue that is intentionally outside the protocol.

Do not use bundles to:

- Rewrite generated substrate files.
- Change capability declarations after generation.
- Change scopes, side effects, approval policy, composition metadata, or input requirements.
- Bypass contract validation.
- Fetch unpinned remote code automatically.

The public manifest must remain identical to the signed contract.

## Contract Parity Vs Adapter Parity

There are two different parity claims:

| Claim | Meaning |
| --- | --- |
| Contract parity | The same signed package and service definition generate the same public ANIP capability surface across languages. |
| Generated parity | The generated service compiles and passes generated tests for a language using the intended runtime package version. |
| Adapter parity | Reviewed custom bundles exist for each language and preserve the signed manifest while implementing backend seams. |
| Live parity | Those adapters have been exercised against real backend credentials with equivalent read, preview, denial, approval, and audit expectations. |
| Approved-mutation parity | Each language proves that mutation stops without approval and proceeds only with a valid approval grant and explicit test mutation flag. |

This is especially important for fronting showcases. A Jira, Slack, GitHub, Linear, Notion, GitLab, or Superset package can be correct as an ANIP contract even before every language has a live backend adapter. But a package should not claim five-language live backend parity until each language has a reviewed adapter and matching live smoke evidence.

Approval-gated adapters also depend on runtime package compatibility. If a handler needs access to approval-grant context, actor metadata, or continuation state, the generated service and the published runtime package must expose that context in the handler `InvocationContext`. Release gates should therefore test generation against the published package versions that users will actually install, not only against local source trees.

## What the generator enforces

The generator applies bundles as an overlay onto declared extension seams. It does not let a bundle rewrite arbitrary generated files.

Current enforcement includes:

- Bundle path must be a local directory.
- Symlinks are rejected.
- Unsafe paths, absolute paths, path traversal, and oversized path segments are rejected.
- Ignored directories such as `.git`, `node_modules`, `dist`, `build`, `.venv`, `__pycache__`, and test caches are skipped.
- Protected substrate files cannot be replaced.
- Capability IDs found in bundle source files must exist in the service definition.
- Generation can fail if the reviewed bundle digest does not match `--verify-custom-code-bundle-digest`.
- A `custom-code-bundle-report.json` file records every applied file, digest, seam classification, byte size, overlay mode, and normalized bundle tree digest.

Protected substrate includes files such as:

- `anip-service-definition.json`
- generated runtime/capability metadata
- agent-consumption metadata
- generated Docker files
- generated public manifest substrate

Allowed overlays are intentionally narrow: backend adapters, policy files, project metadata, custom entrypoints, tests, and dependency metadata such as `pyproject.toml`, `package.json`, `go.mod`, `pom.xml`, or `.csproj` files.

## Local bundle generation

```bash
anip generate \
  --package-bundle ./gtm-pipeline-q2-review-0.4.3.anip-package.json \
  --target python \
  --transport http,stdio \
  --custom-code-bundle ./examples/showcase/gtm/custom-code-bundles/python \
  --verify-custom-code-bundle-digest sha256:<tree-digest> \
  --output ./generated/gtm-python \
  --force
```

The digest is computed over the normalized local bundle tree. That gives CI a stable way to verify the bundle used for generation.

After generation, inspect:

```text
./generated/gtm-python/custom-code-bundle-report.json
```

That report is useful for CI and review because it shows exactly which implementation files were applied.

## Remote bundle references

Remote refs must be immutable and digest-pinned:

```text
git+https://github.com/anip-protocol/gtm-bundles.git@<commit>#sha256:<archive-digest>
```

Supported ref families:

| Ref family | Shape |
| --- | --- |
| Git | `git+https://...@<commit>#sha256:<digest>` |
| Registry artifact | `registry://<package>/<artifact>@<immutable-version>#sha256:<digest>` |
| Object store | `object+https://...#sha256:<digest>` or `object+s3://bucket/key#sha256:<digest>` |

Rejected shapes include floating branches, `latest`, missing digests, query strings, embedded credentials, and path traversal.

First-release behavior:

- The CLI validates the ref shape.
- Package metadata can record the immutable ref and digest.
- Generation does not automatically fetch remote code.
- Users explicitly provide local bundles for actual generation.
- `--fetch-custom-code-bundle` is reserved for future explicit fetching; today it validates the ref and fails because remote fetching is not enabled.

This avoids surprise code execution and keeps the user in control.

## Publishing implementation material

If a package should advertise a bundle, publish a new package revision:

```bash
anip package attach-implementation \
  --package-bundle ./gtm-pipeline-q2-review-0.4.3.anip-package.json \
  --package-version 0.4.1 \
  --custom-code-bundle-ref git+https://github.com/anip-protocol/gtm-bundles.git@<commit>#sha256:<archive-digest> \
  --custom-code-bundle ./examples/showcase/gtm/custom-code-bundles/python \
  --implementation-material-title "GTM Python implementation bundle" \
  --output ./publish-request.json
```

Because package metadata is signed, bundle refs cannot be safely added after the fact. They must be part of a package revision.

With `--registry-url`, `attach-implementation` publishes the new revision using `ANIP_REGISTRY_PUBLISH_TOKEN` or an explicit publish token. Without `--registry-url`, it writes the Registry publish request JSON for review or CI handoff.

See [Lifecycle and Revisions](/docs/concepts/lifecycle-and-revisions) for when to create a behavior-only package versus a later implementation-material revision.

## Bundle trust modes

| Mode | Behavior |
| --- | --- |
| Local reviewed bundle | Developer provides a local path and optional expected digest. |
| Metadata-only remote ref | Package records immutable ref and digest; user fetches/reviews out of band. |
| Future opt-in fetch | A future explicit fetcher may download only digest-pinned immutable refs. |

There is intentionally no "fetch whatever URL the package says" mode.

## Review workflow

A practical bundle workflow is:

1. Generate the service from a signed package.
2. Add custom implementation files only at declared seams.
3. Run local tests and live smokes.
4. Review `custom-code-bundle-report.json`.
5. Pin the normalized bundle digest in CI with `--verify-custom-code-bundle-digest`.
6. Publish a new package revision if the package should advertise the immutable implementation-material ref.

Do not publish a new package revision for local experiments. Publish a revision when consumers need a stable, discoverable implementation-material reference.

## Language parity

For multi-language showcases, bundles should preserve manifest parity across languages.

Example GTM bundle layout:

```text
custom-code-bundles/
  bundle-catalog.json
  python/
  typescript/
  go/
  java/
  csharp/
```

Each language can implement the same domain logic differently, but generated discovery and package manifest shape must remain equivalent.

For the GTM showcase, this means Python, TypeScript, Go, Java, and C# may have different framework code, but they must expose the same signed 23-capability public contract.

## Safety checklist

Before publishing or using a bundle:

- Does it avoid modifying generated substrate behavior?
- Does it preserve the signed public manifest?
- Is the ref immutable?
- Is the digest pinned?
- Are secrets excluded?
- Are generated keys excluded?
- Are tests included?
- Does generation fail if the expected digest mismatches?
- Does the bundle report show only expected seams?
- Does the generated service still verify against the package?
- Do live smokes prove the backend implementation respects approval, denial, clarification, and audit behavior?

Bundles are powerful because they let teams customize implementation honestly. They are safe only when they stay behind the contract boundary.
