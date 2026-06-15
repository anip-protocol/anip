# ANIP Distribution

This page tracks the release artifact story for the current public-release branch. It covers what the release workflow is configured to build and what users should expect from the first public release.

## Artifact Summary

| Artifact | Distribution path | Status |
| --- | --- | --- |
| ANIP spec | Repository + website | Current spec target: `anip/0.24` |
| CLI | GitHub release archives + Homebrew tap | CI artifact build + release workflow configured |
| TypeScript runtime | npm | Published/release workflow configured |
| Python runtime | PyPI | Published/release workflow configured |
| Java runtime | Maven Central | Published/release workflow configured |
| Go runtime | Go module tags | Published via repository tags |
| C# runtime | NuGet | Release workflow configured |
| Registry | Docker image + local compose | Release workflow configured |
| Studio API | Docker image + local compose | Release workflow configured |
| Studio web | Docker image + local compose | Release workflow configured |
| GTM showcase | In-repo generated stacks + compose + Docker images | Release baseline committed; image pipeline configured |
| Fronting showcases | In-repo packages + custom bundles | Release baseline committed |
| Conformance suite | In-repo | Packaging TBD |
| Contract testing harness | In-repo | Packaging TBD |

## CLI

The release workflow builds prebuilt archives for:

- `darwin/arm64`
- `darwin/amd64`
- `linux/arm64`
- `linux/amd64`
- `windows/arm64`
- `windows/amd64`

Each release includes checksums and a rendered Homebrew formula.

The CLI artifact workflow also builds the same cross-platform archive set on relevant pull requests, pushes to `main`, and manual dispatches. That catches packaging regressions before a release dispatch.

Homebrew installation uses the `anip-protocol/homebrew-anip` tap, installed as:

```bash
brew tap anip-protocol/anip
brew install anip
```

Validate:

```bash
anip version
anip generate --help
anip validate --help
anip verify --help
```

The primary binary is `anip`. Compatibility wrappers `anip-generate` and `anip-verify` are included.

## Runtime Packages

### TypeScript

Published to npm:

```bash
npm install @anip-dev/service @anip-dev/hono
```

Primary package families:

- Core/runtime: `@anip-dev/core`, `@anip-dev/crypto`, `@anip-dev/server`, `@anip-dev/service`
- Frameworks: `@anip-dev/hono`, `@anip-dev/express`, `@anip-dev/fastify`
- Interfaces/transports: `@anip-dev/rest`, `@anip-dev/graphql`, `@anip-dev/mcp`, `@anip-dev/mcp-hono`, `@anip-dev/mcp-express`, `@anip-dev/mcp-fastify`, `@anip-dev/stdio`

### Python

Published to PyPI:

```bash
pip install anip-service anip-fastapi
```

Primary package families:

- Core/runtime: `anip-core`, `anip-crypto`, `anip-server`, `anip-service`
- Frameworks: `anip-fastapi`
- Interfaces/transports: `anip-rest`, `anip-graphql`, `anip-mcp`, `anip-stdio`, `anip-grpc`

### Java

Published to Maven Central under group `dev.anip`:

```xml
<dependency>
  <groupId>dev.anip</groupId>
  <artifactId>anip-service</artifactId>
  <version>VERSION</version>
</dependency>
```

Primary modules:

- Core/runtime: `anip-core`, `anip-crypto`, `anip-server`, `anip-service`
- Frameworks: `anip-spring-boot`, `anip-quarkus`
- Interfaces/transports: `anip-rest`, `anip-rest-spring`, `anip-rest-quarkus`, `anip-graphql`, `anip-graphql-spring`, `anip-graphql-quarkus`, `anip-mcp`, `anip-mcp-spring`, `anip-mcp-quarkus`, `anip-stdio`

### Go

Consumed as a Go module:

```bash
go get github.com/anip-protocol/anip/packages/go@vVERSION
```

### C#

The release workflow is configured to publish NuGet packages:

```bash
dotnet add package Anip.Service --version VERSION
dotnet add package Anip.AspNetCore --version VERSION
```

Primary packages:

- Core/runtime: `Anip.Core`, `Anip.Crypto`, `Anip.Server`, `Anip.Service`
- Frameworks: `Anip.AspNetCore`
- Interfaces/transports: `Anip.Rest`, `Anip.Rest.AspNetCore`, `Anip.GraphQL`, `Anip.GraphQL.AspNetCore`, `Anip.Mcp`, `Anip.Mcp.AspNetCore`, `Anip.Stdio`

## Registry

Registry is distributed as a Docker image and local compose stack.

Local:

```bash
cd registry
docker compose up --build
```

Open:

```text
http://127.0.0.1:8200/registry/packages
```

Published image:

```bash
docker pull anipprotocol/registry:VERSION
```

Important environment variables:

- `ANIP_REGISTRY_DATABASE_URL`
- `ANIP_REGISTRY_MODE`
- `ANIP_REGISTRY_PUBLISH_TOKEN`
- `ANIP_REGISTRY_KEY_ID`
- `ANIP_REGISTRY_ED25519_PRIVATE_KEY`
- `ANIP_REGISTRY_SEED_DEMO`

Smoke:

```bash
registry/scripts/smoke-compose.sh
```

## Studio

Studio is distributed as separate API and web images. `anipprotocol/studio`
is also published as a compatibility alias for the standalone web image.

```bash
docker pull anipprotocol/studio-api:VERSION
docker pull anipprotocol/studio-web:VERSION
docker pull anipprotocol/studio:VERSION
```

The current public Studio image hotfix is `0.24.6`:

```bash
docker pull anipprotocol/studio-api:0.24.6
docker pull anipprotocol/studio-web:0.24.6
docker pull anipprotocol/studio:0.24.6
```

`0.24.6` is a Studio Docker image refresh for public showcase preload fixes.
It does not imply a new protocol/runtime package release.

Studio images can be released independently through:

```text
.github/workflows/publish-studio-docker.yml
```

The broader release-lane split is tracked in:

```text
https://github.com/anip-protocol/anip/issues/208
```

Local compose:

```bash
cd studio
docker compose up --build
```

Read-only seeded hosted-demo mode:

```bash
STUDIO_READ_ONLY=1 STUDIO_SEED_SHOWCASES=1 docker compose up --build
```

Smoke:

```bash
studio/scripts/smoke-compose.sh
```

## Showcase Artifacts

### GTM

The GTM showcase release baseline lives in:

```text
examples/showcase/gtm/
```

Important artifacts:

- `examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.4.anip-package.json`
- `examples/showcase/gtm/generated/language-parity/`
- `examples/showcase/gtm/docker-compose.language-parity-{python,typescript,go,java,csharp}.yml`
- `examples/showcase/gtm/custom-code-bundles/`
- `.github/workflows/publish-gtm-showcase-images.yml`

Docker image names:

- `anipprotocol/showcase-gtm-agent-ui`
- `anipprotocol/showcase-gtm-python`
- `anipprotocol/showcase-gtm-typescript`
- `anipprotocol/showcase-gtm-go`
- `anipprotocol/showcase-gtm-java`
- `anipprotocol/showcase-gtm-csharp`

The GTM image workflow accepts a GTM image tag, usually the GTM package version such as `0.4.4`, and can optionally move `latest`.

GTM images are intentionally not published by the main ANIP release workflow because their image tag follows the GTM package version, not the ANIP runtime release version.

Smoke:

```bash
examples/showcase/gtm/scripts/smoke-language-compose.sh python
examples/showcase/gtm/scripts/smoke-language-compose.sh typescript
examples/showcase/gtm/scripts/smoke-language-compose.sh go
examples/showcase/gtm/scripts/smoke-language-compose.sh java
examples/showcase/gtm/scripts/smoke-language-compose.sh csharp
```

### Fronting

Fronting showcase packages live under:

```text
examples/showcase/*_fronting/registry-packages/
```

Current first-release set:

- `jira-fronting-showcase@0.2.3`
- `github-fronting-showcase@0.2.0`
- `slack-fronting-showcase@0.2.0`
- `gitlab-fronting-showcase@0.2.0`
- `linear-fronting-showcase@0.2.0`
- `notion-fronting-showcase@0.2.0`
- `superset-fronting-showcase@0.2.0`

These packages use native APIs as their execution binding. MCP is documented as a comparison surface, not as the signed behavior contract.

## Testing Tools

### Conformance

```bash
pip install -e ./conformance
pytest conformance/ --base-url=http://localhost:9100 --bootstrap-bearer=demo-human-key
```

### Contract Testing

```bash
pip install -e ./contract-tests
anip-contract-tests --base-url=http://localhost:9100 --test-pack=contract-tests/packs/travel.json
```

## Release Validation Still Required

Before public release:

- Run release workflow dry run or prerelease.
- Validate Homebrew formula install on macOS arm64.
- Run Registry compose smoke.
- Run Studio read-only compose smoke.
- Run generator conformance across supported targets/framework variants.
- Run GTM language compose smokes.
- Build the website docs.
