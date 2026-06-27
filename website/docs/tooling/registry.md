---
title: ANIP Registry
description: Publish, inspect, lock, and verify signed ANIP packages and starter templates.
---

# ANIP Registry

ANIP Registry is the trust and distribution service for ANIP packages and starter templates.

It is not just a file host. Registry signs what it accepts, exposes package metadata for inspection, produces lock information, and lets consumers verify that what they generate from is the same thing that was published.

## What Registry stores

Registry has two first-class artifact types:

| Artifact | Purpose |
| --- | --- |
| Package | Signed service contract bundle used by generators and verifiers. |
| Template | Safe starter project material used to create new Studio projects. |

Packages and templates are separate in the UI and API because they answer different questions:

- Package: "What behavior contract am I consuming?"
- Template: "What project starting point should I use?"

## Package contents

A package includes:

- Package ID and version.
- Signed manifest metadata.
- Service definition.
- Recommended lock.
- Product and developer lineage.
- Contract signature.
- Package README.
- Source/project links when safe and portable.
- Agent consumability metadata.
- Agent consumption readiness summary.
- Optional implementation-material refs with immutable digest pins.

The service definition and manifest are signed as part of the package record. If metadata changes, publish a new package revision.

For the full package and implementation-material lifecycle, see [Lifecycle and Revisions](/docs/concepts/lifecycle-and-revisions).

## Package version lifecycle

Package versions are immutable, but Registry can mark a specific version with an operational lifecycle state:

| State | Meaning | Consumer behavior |
| --- | --- | --- |
| `active` | The version is current and recommended. | Browse, download, lock, verify, and generate normally. |
| `superseded` | A newer version is preferred, but this version remains valid for compatibility. | Registry and CLI show a warning and replacement link when available. |
| `deprecated` | The version should not be used for new generation. | Registry and CLI show a stronger warning and replacement link when available. |
| `yanked` | The version should not be consumed by default because it is known-bad or misleading. | Downloads, locks, and generation fail unless the user explicitly opts into historical reproduction. |
| `takedown` | The version is not available for consumption. | Package contents, downloads, locks, and generation are blocked. |

Lifecycle state does not mutate the signed package contents. It is Registry-owned operational metadata around an immutable artifact, similar to unlisting or yanking in package ecosystems.

Use `superseded` for normal replacement, `deprecated` when consumers should actively move away, `yanked` when default generation must stop but audit/history still matters, and `takedown` for policy/security removal.

## What does not belong in a public package

Do not publish:

- Local-only Studio URLs as source links.
- Secret values.
- Private source documents.
- Machine-local paths.
- Generated runtime evidence that exposes internal data.
- Mutable custom bundle URLs without digest pins.

Implementation code can be referenced, but remote refs must be immutable and digest-pinned.

## Run Registry locally

```bash
cd registry
docker compose up --build
```

Open:

```text
http://127.0.0.1:8200/registry/packages
```

Reset local state:

```bash
docker compose down -v --remove-orphans
```

Run the local smoke:

```bash
registry/scripts/smoke-compose.sh
```

The smoke starts Registry with Postgres, publishes a test package, checks UI routes, verifies the package, and runs generator resolution.

The Registry backend redirects `/` to `/registry`, and `/registry` to `/registry/packages`.

## Install or deploy Registry

Registry can be run from source for local evaluation or deployed from the release Docker image.

Source install path:

```bash
git clone https://github.com/anip-protocol/anip.git
cd anip/registry
docker compose up --build
```

Container image path:

```bash
docker pull anipprotocol/registry:VERSION
```

Registry is stateless apart from Postgres. Packages, templates, receipts, digests, lineage, and download counters live in the database.

Minimum production-like configuration:

```text
ANIP_REGISTRY_DATABASE_URL=postgresql://...
ANIP_REGISTRY_ADDR=:8200
ANIP_REGISTRY_MODE=production
ANIP_REGISTRY_KEY_ID=...
ANIP_REGISTRY_ED25519_PRIVATE_KEY=...
ANIP_REGISTRY_PUBLISH_TOKEN=...
ANIP_REGISTRY_PUBLISHER_ID=...
ANIP_REGISTRY_PUBLISHER_TYPE=organization
ANIP_REGISTRY_RUN_MIGRATIONS=1
ANIP_REGISTRY_SEED_DEMO=0
```

Expose the browser UI at `/registry` and the API at `/registry-api/v1`. Use `/registry-api/v1/readyz` for load balancer readiness.

For one Registry replica, startup migrations are acceptable. For replicated deployments, run a migration job first:

```bash
ANIP_REGISTRY_MIGRATE_ONLY=1 anip-registry
```

Then start application replicas with:

```text
ANIP_REGISTRY_RUN_MIGRATIONS=0
```

Use a dedicated Registry database, keep signing keys and publish tokens in a secret manager, and keep public package browsing separate from authenticated publication.

The current hosted Registry is first-party publishing only. Public multi-publisher accounts, namespace ownership, scoped tokens, and moderation are planned as a separate Registry capability.

## API surface

Registry exposes public read APIs and authenticated publish APIs under `/registry-api/v1`.

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/registry-api/v1/healthz` | GET | Liveness and signing posture. |
| `/registry-api/v1/readyz` | GET | Readiness, store connectivity, and migration status. |
| `/registry-api/v1/metrics` | GET | Prometheus text metrics. |
| `/registry-api/v1/keys` | GET | Public Registry signing keys and active key metadata. |
| `/registry-api/v1/publications` | GET | List published package records. |
| `/registry-api/v1/publications` | POST | Publish a package bundle. Requires bearer token. |
| `/registry-api/v1/packages/{packageId}/{version}` | GET | Inspect one package version. Does not increment downloads. |
| `/registry-api/v1/packages/{packageId}/{version}/download` | GET | Download package artifact and increment package download count. |
| `/registry-api/v1/packages/{packageId}/{version}/lock` | GET | Download the recommended lock for one package version. |
| `/registry-api/v1/packages/{packageId}/{version}/receipt` | GET | Fetch signed Registry receipt. |
| `/registry-api/v1/admin/packages/{packageId}/{version}/lifecycle` | PATCH | Update package-version lifecycle state. Requires admin authorization. |
| `/registry-api/v1/templates` | GET | List starter templates. |
| `/registry-api/v1/templates` | POST | Publish a starter template. Requires bearer token. |
| `/registry-api/v1/templates/{templateId}/{version}` | GET | Inspect one template version. |
| `/registry-api/v1/templates/{templateId}/{version}/download` | GET | Download template artifact and increment template download count. |

The UI uses the same API. Generator and verifier clients should use the API, not scrape the UI.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `ANIP_REGISTRY_DATABASE_URL` | Postgres connection string. |
| `ANIP_REGISTRY_ADDR` | Listen address. Defaults to `:8200`. |
| `ANIP_REGISTRY_MODE` | `dev` or `production`. Production requires an explicit Ed25519 signing key. |
| `ANIP_REGISTRY_PUBLISH_TOKEN` | Bearer token required for publication. |
| `ANIP_REGISTRY_PUBLISHER_ID` | Publisher identity recorded in receipts. |
| `ANIP_REGISTRY_PUBLISHER_TYPE` | Publisher type metadata. |
| `ANIP_REGISTRY_KEY_ID` | Signing key ID in production-like mode. |
| `ANIP_REGISTRY_ED25519_PRIVATE_KEY` | Base64 Ed25519 seed or private key. |
| `ANIP_REGISTRY_EXTRA_PUBLIC_KEYS` | Comma-separated `key_id=<base64-public-key>` entries for key rotation verification. |
| `ANIP_REGISTRY_RUN_MIGRATIONS` | Run embedded Postgres migrations on startup. Defaults to `1`. |
| `ANIP_REGISTRY_MIGRATE_ONLY` | Run migrations and exit. Use for deployment migration jobs. |
| `ANIP_REGISTRY_SEED_DEMO` | Seed demo data for local browsing. |
| `ANIP_REGISTRY_UI_DIR` | Built Registry UI directory. Auto-discovered locally when omitted. |

Production signing keys can be generated with:

```bash
anip-registry-keygen --key-id anip-protocol-registry-root-2026-q2
```

The command prints `ANIP_REGISTRY_KEY_ID`, `ANIP_REGISTRY_ED25519_PRIVATE_KEY`, and an `ANIP_REGISTRY_EXTRA_PUBLIC_KEYS` entry for verifier key rotation lists.

## Trust model

Registry signs package records with an Ed25519 key. Consumers verify:

- Registry receipt signature.
- Manifest digest.
- Service-definition digest.
- Lock digest.
- Contract signature.
- Package lineage.

The browser UI is inspection-oriented. Programmatic trust should use `anip verify` or runtime verifier code.

Use production mode for public deployments:

```bash
ANIP_REGISTRY_MODE=production
ANIP_REGISTRY_KEY_ID=anip-protocol-registry-root-2026-q2
ANIP_REGISTRY_ED25519_PRIVATE_KEY=<base64-seed>
```

If `ANIP_REGISTRY_MODE=production` is set without a private key, Registry refuses to start. If mode is omitted, Registry defaults to `dev` for local compatibility and logs a warning when using the deterministic development key.

Read APIs are public. Publish APIs require `Authorization: Bearer <ANIP_REGISTRY_PUBLISH_TOKEN>`.

## Publishing packages

Use the CLI to publish existing portable package bundles:

```bash
ANIP_REGISTRY_PUBLISH_TOKEN=... \
anip package publish-bundle \
  --package-bundle ./my-service-0.1.0.anip-package.json \
  --registry-url https://registry.example.com
```

For review or offline signing workflows, emit the exact publish request without contacting Registry:

```bash
anip package publish-bundle \
  --package-bundle ./my-service-0.1.0.anip-package.json \
  --output ./publish-request.json
```

Registry computes and persists server-side digests for the manifest, service definition, recommended lock, and receipt. Package versions are immutable. If anything signed changes, publish a new package version.

Download counts are operational metadata. Inspecting a package detail page does not increment downloads; downloading the package artifact does.

## Lock files

A lock captures the package identity a consumer expects:

- Package ID.
- Package version.
- Manifest digest.
- Service-definition digest.
- Registry key identity.

Use a lock when generating in CI or rebuilding a service:

```bash
anip generate \
  --registry-url https://registry.example.com/registry-api/v1 \
  --package my-service@0.1.0 \
  --lock-file ./anip-package-lock.json \
  --target python \
  --output ./generated/my-service \
  --force
```

If Registry returns a package with a different digest, generation should fail.

If Registry marks a package version as `deprecated` or `superseded`, generation still proceeds but includes lifecycle metadata and a warning in the JSON result. If Registry marks a package version as `yanked`, generation fails unless `--allow-yanked-package` is set explicitly for pinned historical reproduction. `takedown` packages are always blocked.

## Template publishing

Templates are intended to lower Studio project creation cost. They can include:

- Project type.
- ANIP spec version.
- Industry/domain labels.
- Safe Markdown source documents.
- Reviewed starter metadata.
- Suggested capability shape.

Template import should reject templates targeting a newer ANIP spec than the Studio build supports. Template export should be selective: users choose what source documents and metadata are included, rather than blindly exporting a whole project.

For first release, template documents should be Markdown-only to reduce import risk and simplify review.

Registry enforces template safety limits before publication:

- Template publish requests are capped at 2 MiB.
- Template payloads are capped at 1 MiB.
- Template manifests are capped at 128 KiB.
- Templates may include at most 20 documents, 20 connections, 200 discovery records, and 100 capability mappings.
- Source documents must be safe Markdown `.md` files.
- Secret fields must be environment-style references, not secret values.
- Executable-looking fields such as install scripts are rejected.
- `template.anipSpecVersion` must match the supported Registry spec version, currently `anip/0.24`.

Template listing is separate from package listing and sorted by download count, then publication time, then template identity.

## Package vs template flow

Use a template when:

- Starting a new project.
- Sharing a repeatable project structure.
- Giving teams a guided starting point.

Use a package when:

- Publishing a reviewed behavior contract.
- Generating code.
- Verifying a service.
- Referencing immutable implementation material.

Templates help authors start. Packages help consumers trust.

Template publication and package publication should remain separate flows. A template can help create a project; it does not replace the reviewed package that consumers generate from.

## Storage and high availability

Registry is stateless except for Postgres. Packages, templates, immutable artifact JSON, receipts, digests, lineage, and download counts are stored in the Registry database, not local volumes.

That means:

- Multiple Registry instances can run behind a load balancer after migrations are applied.
- Container restarts do not lose packages or templates.
- Backups and replication should be configured at the Postgres layer.
- The application image does not need shared filesystem storage for package/template artifacts.

For highly available deployments, run migrations as a separate job:

```bash
ANIP_REGISTRY_MIGRATE_ONLY=1 anip-registry
```

Then run application replicas with:

```bash
ANIP_REGISTRY_RUN_MIGRATIONS=0
```

Startup migrations are enabled by default for local and single-replica deployments. The Postgres migration runner uses advisory locking, but an explicit migration job is easier to reason about for production rollouts.

## Observability

Registry emits structured JSON logs to stdout and Prometheus metrics at:

```text
/registry-api/v1/metrics
```

Metrics include HTTP request counts/durations, publish attempts by artifact kind and status, download counters, readiness, and migration status.

Use:

- `/registry-api/v1/healthz` for liveness.
- `/registry-api/v1/readyz` for load balancer readiness.
- `/registry-api/v1/metrics` for monitoring and alerts.

Alert on readiness failures, publish failures, repeated unauthorized publish attempts, and pending migrations.
