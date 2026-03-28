---
title: Install
description: Install ANIP by ecosystem and understand what is already published today.
---

# Install

ANIP is already available across multiple ecosystems.

## TypeScript

Published to npm.

```bash
npm install @anip/service @anip/hono
```

Other published packages include:

- `@anip/core`
- `@anip/crypto`
- `@anip/server`
- `@anip/express`
- `@anip/fastify`
- `@anip/rest`
- `@anip/graphql`
- `@anip/mcp`
- `@anip/stdio`

## Python

Published to PyPI.

```bash
pip install anip-service anip-fastapi
```

Other published packages include:

- `anip-core`
- `anip-crypto`
- `anip-server`
- `anip-rest`
- `anip-graphql`
- `anip-mcp`
- `anip-studio`
- `anip-stdio`
- `anip-grpc`

## Java

Published to Maven Central under `dev.anip`.

```xml
<dependency>
  <groupId>dev.anip</groupId>
  <artifactId>anip-service</artifactId>
  <version>VERSION</version>
</dependency>
```

## Go

Consumed as a Go module.

```bash
go get github.com/anip-protocol/anip/packages/go@vVERSION
```

## C#

Current status:

- runtime exists in-repo
- NuGet publishing is not configured yet

## Studio

Studio can run:

- embedded at `/studio` inside a Python ANIP service
- standalone as a Dockerized static app built from `studio/`

```bash
docker build -t anip-studio studio/
docker run -p 3000:80 anip-studio
```

## Conformance and contract testing

Conformance is currently an in-repo tool:

```bash
pip install -e ./conformance
pytest conformance/ --base-url=http://localhost:9100 --bootstrap-bearer=demo-human-key
```

Contract testing is also currently in-repo:

```bash
pip install -e ./contract-tests
anip-contract-tests --base-url=http://localhost:9100 --test-pack=contract-tests/packs/travel.json
```

For the full artifact story, see [What Ships Today](../releases/what-ships-today.md).
