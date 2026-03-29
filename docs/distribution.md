# ANIP Distribution

What ANIP artifacts are currently distributed, where they are published, and what still remains source-only.

## Current Status

| Ecosystem | Registry | Status |
|-----------|----------|--------|
| TypeScript | npm | Published |
| Python | PyPI | Published |
| Java | Maven Central | Published |
| Go | Module tags | Published |
| C# | — | In-repo, NuGet not yet configured |
| Studio | — | Docker build path, image publishing not yet configured |

## TypeScript

Published to npm. Install:

```bash
npm install @anip-dev/service @anip-dev/hono
```

Full package family: `@anip-dev/core`, `@anip-dev/crypto`, `@anip-dev/server`, `@anip-dev/service`, `@anip-dev/hono`, `@anip-dev/express`, `@anip-dev/fastify`, `@anip-dev/rest`, `@anip-dev/graphql`, `@anip-dev/mcp`, `@anip-dev/mcp-hono`, `@anip-dev/mcp-express`, `@anip-dev/mcp-fastify`, `@anip-dev/stdio`.

## Python

Published to PyPI. Install:

```bash
pip install anip-service anip-fastapi
```

Full package family: `anip-core`, `anip-crypto`, `anip-server`, `anip-service`, `anip-fastapi`, `anip-rest`, `anip-graphql`, `anip-mcp`, `anip-studio`, `anip-stdio`, `anip-grpc`.

## Java

Published to Maven Central under group `dev.anip`. Install:

```xml
<dependency>
  <groupId>dev.anip</groupId>
  <artifactId>anip-service</artifactId>
  <version>VERSION</version>
</dependency>
```

Full module family: `anip-core`, `anip-crypto`, `anip-server`, `anip-service`, `anip-spring-boot`, `anip-quarkus`, `anip-rest`, `anip-rest-spring`, `anip-rest-quarkus`, `anip-graphql`, `anip-graphql-spring`, `anip-graphql-quarkus`, `anip-mcp`, `anip-mcp-spring`, `anip-mcp-quarkus`, `anip-stdio`.

## Go

Consumed as a module via version tags:

```bash
go get github.com/anip-protocol/anip/packages/go@vVERSION
```

## C\#

In-repo packages: `Anip.Core`, `Anip.Crypto`, `Anip.Server`, `Anip.Service`, `Anip.AspNetCore`, `Anip.Rest`, `Anip.Rest.AspNetCore`, `Anip.GraphQL`, `Anip.GraphQL.AspNetCore`, `Anip.Mcp`, `Anip.Mcp.AspNetCore`, `Anip.Stdio`.

NuGet publishing is not yet configured. C# is part of the codebase and release planning, but not yet part of the public package-registry story.

## Studio

Two deployment modes:

- **Embedded**: `pip install anip-studio` then mount at `/studio` inside a Python ANIP service
- **Standalone**: build and run as a Docker container

```bash
docker build -t anip-studio studio/
docker run -p 3000:80 anip-studio
```

Docker image publishing (GHCR or similar) is not yet configured. CI smoke-builds the image to catch drift.

## Conformance Suite

Validates that an ANIP implementation speaks the protocol correctly. Currently in-repo (PyPI publishing planned):

```bash
pip install -e ./conformance
pytest conformance/ --base-url=http://localhost:9100 --bootstrap-bearer=demo-human-key
```

Required options: `--base-url` and `--bootstrap-bearer`. Optional: `--sample-inputs` (JSON file mapping capability names to test parameters).

## Contract Testing

Validates that declared side effects match observed behavior. Distinct from conformance:

- **Conformance**: does this implementation speak ANIP correctly?
- **Contract testing**: does this service behave as it declares?

Currently in-repo (not yet on PyPI):

```bash
pip install -e ./contract-tests
anip-contract-tests --base-url=http://localhost:9100 --test-pack=contract-tests/packs/travel.json
```

## Showcase and Demo Apps

Runnable reference applications in the repository covering travel booking, financial operations, and DevOps infrastructure. Not yet packaged as standalone installable artifacts.

## Release Workflow

Today's release workflow publishes:

- TypeScript packages to npm
- Python packages to PyPI
- Java modules to Maven Central

Not yet published:

- C# NuGet packages
- Docker images (Studio, showcases)
- Conformance suite to PyPI
- Contract-testing harness to PyPI
