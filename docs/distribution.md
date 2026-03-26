# ANIP Distribution

This page describes what ANIP artifacts are currently distributed, where they are published, and what still remains source-only.

## Current Status

ANIP currently ships artifacts across several ecosystems:

- **TypeScript**: published to npm
- **Python**: published to PyPI
- **Java**: published to Maven Central
- **Go**: consumed via module tags
- **C#**: source/runtime available in-repo, NuGet publishing not yet configured
- **Studio**: buildable as a standalone Docker image, but image publishing is not yet configured

## TypeScript

Published registry: npm

Package family:

- `@anip/core`
- `@anip/crypto`
- `@anip/server`
- `@anip/service`
- `@anip/hono`
- `@anip/express`
- `@anip/fastify`
- `@anip/rest`
- `@anip/graphql`
- `@anip/mcp`
- `@anip/mcp-hono`
- `@anip/mcp-express`
- `@anip/mcp-fastify`
- `@anip/stdio`

Example:

```bash
npm install @anip/service @anip/hono
```

## Python

Published registry: PyPI

Package family:

- `anip-core`
- `anip-crypto`
- `anip-server`
- `anip-service`
- `anip-fastapi`
- `anip-rest`
- `anip-graphql`
- `anip-mcp`
- `anip-studio`
- `anip-stdio`
- `anip-grpc`

Example:

```bash
pip install anip-service anip-fastapi
```

## Conformance Suite

The conformance suite validates that an ANIP implementation speaks the protocol correctly. It is currently an in-repo tool, not yet published to PyPI (planned for the first tagged release):

```bash
pip install -e ./conformance
anip-conformance --base-url=http://localhost:9100
```

## Contract Testing

The contract-testing harness validates that declared side effects and behavioral claims match observed behavior. It serves a different purpose from conformance:

- **Conformance** asks: does this implementation speak ANIP correctly?
- **Contract testing** asks: does this service behave as it declares?

The contract-testing harness is currently an in-repo tool, not yet published to PyPI:

```bash
pip install -e ./contract-tests
anip-contract-tests --base-url=http://localhost:9100 --test-pack=contract-tests/packs/travel.json
```

## Java

Published registry: Maven Central

Group: `dev.anip`

Published modules:

- `anip-core`
- `anip-crypto`
- `anip-server`
- `anip-service`
- `anip-spring-boot`
- `anip-quarkus`
- `anip-rest`
- `anip-rest-spring`
- `anip-rest-quarkus`
- `anip-graphql`
- `anip-graphql-spring`
- `anip-graphql-quarkus`
- `anip-mcp`
- `anip-mcp-spring`
- `anip-mcp-quarkus`
- `anip-stdio`

Example:

```xml
<dependency>
  <groupId>dev.anip</groupId>
  <artifactId>anip-service</artifactId>
  <version>VERSION</version>
</dependency>
```

## Go

Distribution model: module tags

Go is consumed as a module rather than through a separate package registry.

Example:

```bash
go get github.com/anip-protocol/anip/packages/go@vVERSION
```

## C\#

Current status:

- ANIP C# packages exist in-repo
- NuGet publishing is not configured yet

This means C# is part of the codebase and release planning, but not yet part of the public package-registry story.

## Studio

Studio currently has two modes:

- **Embedded**: mounted at `/studio` inside a Python ANIP service
- **Standalone**: built from `studio/` as a static app served by nginx

Local standalone usage:

```bash
docker build -t anip-studio studio/
docker run -p 3000:80 anip-studio
```

Current status:

- Docker build path exists
- CI smoke-builds the image
- Image publishing is not yet configured

## Showcase and Demo Apps

The showcase apps are currently best understood as:

- Runnable reference applications in the repository
- Examples of ANIP across domains (travel, finance, devops) and transports

They are **not yet** packaged as polished installable products unless and until Docker images or dedicated demo bundles are published.

## Release Workflow

Today's release workflow publishes:

- TypeScript packages to npm
- Python packages to PyPI
- Java modules to Maven Central

It does **not yet** publish:

- NuGet packages
- Docker images
- Conformance suite to PyPI
- Contract-testing harness to PyPI
- Packaged showcase/demo artifacts
