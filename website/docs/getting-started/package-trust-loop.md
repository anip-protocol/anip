---
title: Package Trust Loop
description: Build, publish, verify, lock, and generate from an ANIP package.
---

# Package Trust Loop

The package trust loop is the path from a reviewed service definition to generated code that consumers can verify.

For revision semantics before and after packaging, see [Lifecycle and Revisions](/docs/concepts/lifecycle-and-revisions).

```text
Service Definition
  -> Registry package
  -> Registry receipt
  -> Lock file
  -> Generated service
  -> Runtime verification
```

## 1. Build a local package

For examples and local smoke testing:

```bash
cd packages/go
go run ./cmd/anip package build-local \
  --definition ../../examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3-service-definition.json \
  --package-id jira-fronting-showcase \
  --package-version 0.2.3 \
  --output-dir /tmp/anip-packages \
  --write-definition
```

Production publication should use a real Registry, not the deterministic local development key.

Before publication, check package metadata:

- README should explain the service and safe usage.
- Source links should be portable HTTP(S) links.
- Project links should not be machine-local Studio URLs.
- Custom implementation material should be immutable and digest-pinned.
- No secret values, local env files, or private workstation paths should appear in package metadata.

## 2. Verify a package

```bash
go run ./cmd/anip verify \
  --package-bundle ../../examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3.anip-package.json
```

Verification checks:

- Service-definition digest.
- Manifest digest.
- Lock digest.
- Registry receipt signature.
- Contract signature.
- Agent consumability metadata.
- Agent readiness metadata.

## 3. Write a lock while generating

```bash
go run ./cmd/anip generate \
  --package-bundle ../../examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3.anip-package.json \
  --target python \
  --dependency-source local \
  --write-lock /tmp/jira-fronting.lock.json \
  --output /tmp/jira-fronting \
  --force
```

Use the lock later:

```bash
go run ./cmd/anip generate \
  --registry-url http://127.0.0.1:8200/registry-api/v1 \
  --package jira-fronting-showcase@0.2.3 \
  --lock-file /tmp/jira-fronting.lock.json \
  --target python \
  --output /tmp/jira-fronting-regenerated \
  --force
```

If the Registry package digest changed, generation fails.

## 4. Attach implementation material

When a custom bundle should be advertised to consumers, create a new package revision:

```bash
go run ./cmd/anip package attach-implementation \
  --package-bundle ../../examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.3.anip-package.json \
  --package-version 0.4.1 \
  --custom-code-bundle-ref git+https://github.com/anip-protocol/gtm-bundles.git@<commit>#sha256:<digest> \
  --custom-code-bundle ../../examples/showcase/gtm/custom-code-bundles/python \
  --implementation-material-title "GTM Python implementation bundle" \
  --output /tmp/gtm-implementation-publish-request.json
```

Implementation metadata is signed package metadata. It cannot be safely bolted on after publication without changing package identity.

The normal sequence is:

1. Publish the behavior-only package.
2. Generate and implement the service.
3. Test the implementation.
4. Build a custom bundle archive or immutable external ref.
5. Publish a new package revision that includes the bundle ref and digest.

This keeps the original behavior contract stable and makes implementation material explicit.

## 5. Trust rules

- Consumers should generate from package identity, not from loose files.
- CI should use locks.
- Remote custom bundle refs must be immutable and digest-pinned.
- Automatic remote code fetching is disabled by default.
- Public package metadata should not include secrets, local paths, or machine-local Studio links.
- A package lock should be committed by consumers when reproducible generation matters.
- Registry download counts and package popularity are convenience signals, not trust signals.

The trust loop is what lets ANIP packages be shared without asking consumers to trust hidden local state.
