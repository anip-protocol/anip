---
title: What Ships Today
description: Current ANIP release surface across protocol, runtimes, CLI, Studio, Registry, and showcases.
---

# What Ships Today

ANIP is not only a protocol document. The current public-release branch includes runtimes, generators, Registry, Studio, showcase packages, and compose-based verification paths.

## Protocol target

The current release target is `anip/0.24`.

Major recent features:

- **v0.23 capability composition**: capabilities can be `atomic` or `composed`; composed capabilities declare step graphs, input/output mapping, empty-result policy, failure policy, and audit policy.
- **v0.23 approval grants**: `approval_required` can persist an approval request; approvers issue signed one-time or session-bound grants; invocation continues only when the grant validates.
- **v0.24 input resolution**: inputs can declare how they are resolved: explicit, closed values, backend-resolved, actor-policy-derived, app-selected, or clarification-required.

These are the protocol primitives that made the GTM and fronting showcases realistic: dynamic references no longer need fake hardcoded catalogs, and approval paths can be represented as real ANIP continuations instead of string parameters.

## Runtime support

| Runtime | Status |
| --- | --- |
| Python | `anip/0.24` implemented |
| TypeScript | `anip/0.24` implemented |
| Go | `anip/0.24` implemented |
| Java | `anip/0.24` implemented |
| C# | `anip/0.24` implemented |

Framework variants:

- TypeScript: Hono, Express, Fastify.
- Java: Spring Boot, Quarkus.
- C#: ASP.NET Core.

## CLI

The CLI builds release archives for macOS, Linux, and Windows on arm64 and amd64. A dedicated CLI artifact CI workflow builds the same archive shape before release so packaging breaks are caught earlier.

Primary commands:

```bash
anip generate
anip fronting scaffold
anip package build-local
anip package attach-implementation
anip validate
anip verify
anip version
```

Homebrew formula publishing is configured through the `anip-protocol/homebrew-anip` tap:

```bash
brew tap anip-protocol/anip
brew install anip
```

## Registry

Registry ships as:

- Go backend.
- Web UI.
- Docker image.
- Local Postgres compose stack.
- Package publication and browsing.
- Template publication and browsing.
- Signed package receipts.
- Recommended lock generation.
- Strict `anip/0.24` validation for this release.

Run locally:

```bash
cd registry
docker compose up --build
```

Open:

```text
http://127.0.0.1:8200/registry/packages
```

## Studio

Studio ships as:

- Studio API Docker image.
- Studio web Docker image.
- Local Postgres compose stack.
- Read-only hosted-demo mode.
- Showcase seeding.
- Starter template import/export.
- Registry publication workflow.
- Autopilot Mode and Guided Mode.
- Fronting project flow.

Run locally:

```bash
cd studio
docker compose up --build
```

Run read-only seeded mode:

```bash
STUDIO_READ_ONLY=1 STUDIO_SEED_SHOWCASES=1 docker compose up --build
```

## Showcases

### GTM Agent

The GTM showcase is the release-quality deep example:

- Studio-produced contract.
- Registry package: `gtm-pipeline-q2-review@0.4.3`.
- Generated native services in Python, TypeScript, Go, Java, and C#.
- Full-stack compose per language.
- Docker images for each language stack and the shared agent UI.
- Agent UI and approval UI.
- 23 formalized capabilities.
- Custom bundle catalog with digest verification.

### Governed fronting

Current fronting packages:

| Package | Backend posture |
| --- | --- |
| `jira-fronting-showcase@0.2.3` | Native Jira REST API |
| `github-fronting-showcase@0.2.0` | Native GitHub REST/GraphQL APIs |
| `slack-fronting-showcase@0.2.0` | Native Slack Web API |
| `gitlab-fronting-showcase@0.2.0` | Native GitLab REST/GraphQL APIs |
| `linear-fronting-showcase@0.2.0` | Native Linear GraphQL API |
| `notion-fronting-showcase@0.2.0` | Native Notion API |
| `superset-fronting-showcase@0.2.0` | Native Superset REST API |

The fronting packages demonstrate the central ANIP claim:

```text
MCP and APIs expose access.
ANIP exposes the governed way to use that access.
```

## Still source-local or release-gated

Some assets are implemented but still require release-run validation:

- Homebrew tap update with real release version.
- Public Docker image push through the release workflow.
- Manual GTM showcase image publish to Docker Hub, if we want package-version tags such as `0.4.3` before the next platform release.
- Hosted Registry deployment.
- Hosted read-only Studio deployment.
- Docs site build and publishing.
- Conformance/contract-test packaging outside the repo.

## Public release gates

Before public launch:

- Full CI matrix passes.
- Generator conformance passes across languages and framework variants.
- Registry Docker smoke passes.
- Studio read-only Docker smoke passes.
- GTM language compose smokes pass.
- Fronting packages verify.
- Docs build.
- Release workflow dry run or prerelease succeeds.
