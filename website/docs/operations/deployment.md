---
title: Deployment
description: Deploy ANIP services, Registry, and Studio safely.
---

# Deployment

ANIP deployments have three different concerns:

- **Runtime services** that implement ANIP capabilities.
- **Registry** that distributes signed packages and templates.
- **Studio** that authors projects and publishes packages.

Treat them separately. Their security posture is different.

## Recommended first public deployment

For the first public ANIP deployment, do not start with a complex Kubernetes cluster unless you already operate one.

A pragmatic baseline is:

- Managed Postgres with backups and point-in-time recovery.
- One containerized Registry instance.
- Startup migrations enabled for the first single-replica deployment.
- Public browse/download routes.
- Publish token restricted to maintainers or CI.
- Structured logs from stdout.
- `/registry-api/v1/readyz` health checks and `/registry-api/v1/metrics` scraping.

Scale later:

- Move migrations to an explicit job.
- Set app instances to `ANIP_REGISTRY_RUN_MIGRATIONS=0`.
- Run two or more stateless Registry replicas.
- Add CDN/custom domain/WAF as needed.
- Add scoped publisher accounts and namespace ownership before third-party publishing.

This keeps cost and operational complexity low while preserving the important durability boundary: Postgres.

## Runtime services

Generated ANIP services can run as normal application services:

```text
agent/client -> ANIP service -> backend system
```

Recommended runtime baseline:

- Terminate TLS at the ingress or service.
- Validate bearer tokens and delegation tokens.
- Store audit/checkpoint data in durable storage.
- Expose health endpoints to the platform.
- Keep backend credentials in the platform secret manager.
- Configure structured logs without leaking secrets.
- Run conformance tests after deployment.
- Run scenario validation for critical behavior.

Runtime services are usually not public package infrastructure. They are application services that enforce a specific ANIP contract for agents or internal clients.

## Registry

Registry should be deployed as a stateful service with Postgres.

Minimum production-like environment:

```text
ANIP_REGISTRY_DATABASE_URL=postgres://...
ANIP_REGISTRY_MODE=production
ANIP_REGISTRY_PUBLISH_TOKEN=...
ANIP_REGISTRY_PUBLISHER_ID=...
ANIP_REGISTRY_PUBLISHER_TYPE=organization
ANIP_REGISTRY_KEY_ID=...
ANIP_REGISTRY_ED25519_PRIVATE_KEY=...
```

Recommended production variables:

| Variable | Purpose |
| --- | --- |
| `ANIP_REGISTRY_DATABASE_URL` | Managed Postgres connection string. |
| `ANIP_REGISTRY_MODE` | Use `production` for public registries. |
| `ANIP_REGISTRY_KEY_ID` | Stable signing key id, for example `anip-protocol-registry-root-2026-q2`. |
| `ANIP_REGISTRY_ED25519_PRIVATE_KEY` | Base64 Ed25519 private key seed, stored as a secret. |
| `ANIP_REGISTRY_EXTRA_PUBLIC_KEYS` | Optional key rotation/public verification list. |
| `ANIP_REGISTRY_PUBLISH_TOKEN` | Strong publish token, stored as a secret. |
| `ANIP_REGISTRY_PUBLISHER_ID` | Publisher identity for first-party packages. |
| `ANIP_REGISTRY_PUBLISHER_TYPE` | Publisher kind, such as `organization`. |
| `ANIP_REGISTRY_RUN_MIGRATIONS` | Run migrations at startup. |
| `ANIP_REGISTRY_MIGRATE_ONLY` | Run migrations and exit. |
| `ANIP_REGISTRY_SEED_DEMO` | Keep `0` for public production registries unless intentionally seeding demo data. |

Health and observability endpoints:

| Endpoint | Purpose |
|----------|---------|
| `/registry-api/v1/healthz` | Process liveness. Use for simple container liveness checks. |
| `/registry-api/v1/readyz` | Readiness. Verifies store connectivity and migration status. Use for load balancer readiness. |
| `/registry-api/v1/metrics` | Prometheus text metrics for HTTP traffic, publish/download counters, readiness, and migration status. |

Migration controls:

```text
ANIP_REGISTRY_RUN_MIGRATIONS=1
ANIP_REGISTRY_MIGRATE_ONLY=0
```

For single-node local deployment, the default is fine: the Registry runs pending migrations on startup. For replicated production deployments, prefer an explicit migration job:

```bash
ANIP_REGISTRY_MIGRATE_ONLY=1 anip-registry
```

Then start application pods with migrations disabled:

```text
ANIP_REGISTRY_RUN_MIGRATIONS=0
```

Registry migrations use a Postgres advisory lock so concurrent startup is safe, but a separate migration job is easier to reason about operationally.

Operational guidance:

- Store the Ed25519 private key in a secret manager.
- Rotate publish tokens.
- Keep publish tokens out of `app.yaml`, shell history, compose files, and logs.
- Back up Postgres and enable point-in-time recovery for public or shared registries.
- Use managed Postgres or a replicated Postgres operator when high availability matters.
- Put publication endpoints behind authentication.
- Keep package browse routes public if the Registry is public.
- Monitor package publication failures and verification failures.
- Scrape `/registry-api/v1/metrics` and alert on readiness failures, publish failures, and migration drift.
- Collect structured JSON logs from stdout.
- Use a separate staging Registry for pre-release testing.
- Treat signing key rotation as a release operation. Preserve old public keys for verification of historical packages.

Package and template storage:

- Packages and templates are stored in Postgres, including immutable bundle JSON and metadata.
- Downloads are served from the database-backed registry state.
- Do not rely on container-local storage for package durability.
- If external bundle artifacts are referenced by packages, those artifacts must live in immutable external storage with digest pinning.
- Download counts and publication metadata are also database state.

High-availability baseline:

- Run Postgres with backups and at least one replica before publishing public packages.
- Run one Registry replica during the first migration, or use `ANIP_REGISTRY_MIGRATE_ONLY=1` as a migration job.
- After migrations complete, run two or more stateless Registry replicas behind a load balancer.
- Use `/registry-api/v1/readyz` for traffic readiness and `/registry-api/v1/healthz` only for liveness.
- Keep signing keys and publish tokens in the platform secret manager, not in images or compose files.

Local compose:

```bash
cd registry
docker compose up --build
```

Container platform choices:

| Platform | Use when | Notes |
| --- | --- | --- |
| Docker Compose on a VM | Cheapest early deployment or private evaluation. | Use managed Postgres if possible; otherwise back up the VM database volume aggressively. |
| Managed app container platform | Good first public deployment. | Works well because Registry is stateless except for Postgres. |
| Kubernetes | Use when you already operate K8s or need more control. | Run migrations as a job, then deploy stateless replicas. |

For DigitalOcean App Platform or similar platforms, attach managed Postgres and pass the resolved database connection string to `ANIP_REGISTRY_DATABASE_URL`. Do not quote template placeholders in a way that the app receives the literal string rather than the resolved connection URL.

## Studio

Studio is a write-capable authoring system. Public hosted Studio should usually run read-only.

Read-only public demo:

```text
STUDIO_READ_ONLY=1
STUDIO_SEED_SHOWCASES=1
```

Public read-only Studio is for browsing seeded projects, contracts, packages, templates, and showcase evidence. It should not allow assistant calls, project mutation, publication, or server-side generation actions that write state.

Health and observability endpoints:

| Endpoint | Purpose |
|----------|---------|
| `/api/health` | Process liveness. |
| `/api/readyz` | Readiness. Verifies database connectivity and Studio migration status. |
| `/api/metrics` | Prometheus text metrics for HTTP traffic, readiness, and migration status. |

Migration controls:

```text
STUDIO_RUN_MIGRATIONS=1
STUDIO_MIGRATE_ONLY=0
```

For replicated Studio deployments, prefer the same explicit migration-job pattern:

```bash
STUDIO_MIGRATE_ONLY=1 studio-api
```

Then start application pods with:

```text
STUDIO_RUN_MIGRATIONS=0
```

Studio migrations also use a Postgres advisory lock, so concurrent startup is protected, but a separate migration job keeps production rollouts clearer.

Internal authoring deployment:

```text
DATABASE_URL=postgresql://...
STUDIO_REGISTRY_URL=https://registry.example.com/registry-api/v1
STUDIO_REGISTRY_PUBLISH_TOKEN=...
STUDIO_REGISTRY_REQUIRED_MODE=production
STUDIO_REGISTRY_TRUSTED_KEY_ID=...
```

Operational guidance:

- Use SSO or network controls for write-capable deployments.
- Keep assistant/API keys out of packages and exports.
- Use read-only mode for public showcase browsing.
- Seed showcase projects only when that is intentional.
- Back up the Studio database if teams use it for real authoring.
- Treat source documents as potentially sensitive.
- Scrape `/api/metrics` and alert on readiness failures.
- Collect structured JSON logs from stdout.
- For highly available deployments, run migrations before scaling Studio replicas, then use `/api/readyz` for load balancer readiness.
- Use `STUDIO_ASSISTANT_MODEL=gpt-5.4` for production-quality Studio authoring. Keep smaller simulator/agent-test models separate.
- Lock Registry trust settings in environment variables for hosted deployments: `STUDIO_REGISTRY_URL`, `STUDIO_REGISTRY_REQUIRED_MODE`, and `STUDIO_REGISTRY_TRUSTED_KEY_ID`.

## Local platform compose

For evaluation, run Registry and Studio locally:

```bash
cd registry
docker compose up --build
```

In another terminal:

```bash
cd studio
docker compose up --build
```

See [Run the Local Platform](/docs/getting-started/local-platform).

## Public routes

Recommended public route posture:

| Component | Public route | Posture |
| --- | --- | --- |
| Registry UI | `/registry` | Public browse if the Registry is public. |
| Registry API | `/registry-api/v1` | Public read endpoints; publish endpoints token-gated. |
| Studio UI | `/studio` or app root | Public only in read-only mode. |
| Studio API | `/api` | Public only for read-only-safe routes in hosted demo mode. |
| Runtime services | service-specific | Expose only to intended agents/apps, usually not as public unauthenticated services. |

Use `/registry-api/v1/readyz` and `/api/readyz` for load balancer readiness. Use liveness checks only to restart crashed processes, not to decide whether traffic should be routed.

## Backups and disaster recovery

For Registry, Postgres is the durable system of record. Back up:

- packages
- templates
- manifests
- service definitions
- recommended locks
- receipts
- publication metadata
- download counters

For Studio, Postgres stores workspaces, source documents, product/developer revisions, local package state, template exports, and showcase seeds.

Minimum public deployment posture:

- automated backups
- point-in-time recovery
- restore test before launch
- documented signing-key recovery/rotation process
- separate staging database

## Deployment gates

Before making a release public:

- Website docs build passes.
- CLI release archives are generated for supported platforms.
- Registry Docker image builds.
- Studio Docker image builds.
- Registry smoke passes.
- Studio read-only smoke passes.
- Representative package verifies from Registry.
- Generated service starts from package.
- Conformance suite passes.
- Scenario validation passes for showcase services.
- No local paths or secrets appear in published package metadata.
- Registry `/registry-api/v1/readyz` and `/registry-api/v1/metrics` are reachable.
- Studio read-only mode blocks mutation routes if hosted publicly.
- Registry package/template browse works through the public domain.

## Read-only versus write-capable deployments

| Deployment | Intended audience | Mutation allowed? |
|------------|-------------------|-------------------|
| Public Studio demo | External readers/evaluators | No |
| Internal Studio | Product/dev/security teams | Yes |
| Public Registry | Package consumers | Browse/download only, publish gated |
| Internal Registry | Authors and CI | Publish gated |
| Runtime service | Agents/apps | Only through ANIP contract |

Do not deploy write-capable Studio publicly unless you intentionally want users to create projects, call assistants, publish packages, or mutate shared state.
