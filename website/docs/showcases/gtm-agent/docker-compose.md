---
title: Docker Compose
description: How the GTM Agent Docker Compose stacks are structured and run.
---

# Docker Compose

The GTM showcase has one language-parity compose file per generated language.

Clone the repository first if you have not already:

```bash
git clone https://github.com/anip-protocol/anip.git
cd anip
```

The compose stacks run local Postgres, dbt, Metabase, four generated ANIP
services, and the GTM Agent UI. Docker is enough for the stack itself, but the
agent UI needs an OpenAI-compatible key to answer natural-language questions:

```bash
export OPENAI_API_KEY="sk-..."
export ANIP_AGENT_MODEL="gpt-5.4-mini"
```

`ANIP_AGENT_API_KEY` can be used instead of `OPENAI_API_KEY`, and
`ANIP_AGENT_BASE_URL` or `OPENAI_BASE_URL` can point at another
OpenAI-compatible endpoint.

```text
examples/showcase/gtm/docker-compose.language-parity-python.yml
examples/showcase/gtm/docker-compose.language-parity-typescript.yml
examples/showcase/gtm/docker-compose.language-parity-go.yml
examples/showcase/gtm/docker-compose.language-parity-java.yml
examples/showcase/gtm/docker-compose.language-parity-csharp.yml
```

Source links:

- [GTM showcase folder](https://github.com/anip-protocol/anip/tree/main/examples/showcase/gtm)
- [Python compose file](https://github.com/anip-protocol/anip/blob/main/examples/showcase/gtm/docker-compose.language-parity-python.yml)
- [TypeScript compose file](https://github.com/anip-protocol/anip/blob/main/examples/showcase/gtm/docker-compose.language-parity-typescript.yml)
- [Go compose file](https://github.com/anip-protocol/anip/blob/main/examples/showcase/gtm/docker-compose.language-parity-go.yml)
- [Java compose file](https://github.com/anip-protocol/anip/blob/main/examples/showcase/gtm/docker-compose.language-parity-java.yml)
- [C# compose file](https://github.com/anip-protocol/anip/blob/main/examples/showcase/gtm/docker-compose.language-parity-csharp.yml)
- [Agent runtime](https://github.com/anip-protocol/anip/tree/main/examples/showcase/gtm/agents/llm_runtime)
- [Custom bundles](https://github.com/anip-protocol/anip/tree/main/examples/showcase/gtm/custom-code-bundles)

Each stack starts the same logical system:

- Postgres with Maven CRM data.
- dbt model build.
- Metabase with curated GTM verification questions.
- Four generated ANIP services in the selected language.
- GTM agent runtime and UI.

## Ports

| Language | Entry page | Agent UI | Metabase | Pipeline | Enrichment | Prioritization | Outreach |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Python | `4310` | `4310/agent` | `3041` | `4210` | `4211` | `4212` | `4213` |
| TypeScript | `4320` | `4320/agent` | `3042` | `4220` | `4221` | `4222` | `4223` |
| Go | `4330` | `4330/agent` | `3043` | `4230` | `4231` | `4232` | `4233` |
| Java | `4340` | `4340/agent` | `3044` | `4240` | `4241` | `4242` | `4243` |
| C# | `4350` | `4350/agent` | `3045` | `4250` | `4251` | `4252` | `4253` |

## Run one stack

Choose one language stack:

| Language | Command |
| --- | --- |
| Python | `docker compose -p anip-gtm-python -f examples/showcase/gtm/docker-compose.language-parity-python.yml up -d --build` |
| TypeScript | `docker compose -p anip-gtm-typescript -f examples/showcase/gtm/docker-compose.language-parity-typescript.yml up -d --build` |
| Go | `docker compose -p anip-gtm-go -f examples/showcase/gtm/docker-compose.language-parity-go.yml up -d --build` |
| Java | `docker compose -p anip-gtm-java -f examples/showcase/gtm/docker-compose.language-parity-java.yml up -d --build` |
| C# | `docker compose -p anip-gtm-csharp -f examples/showcase/gtm/docker-compose.language-parity-csharp.yml up -d --build` |

Example for Go:

```bash
export OPENAI_API_KEY="sk-..."
export ANIP_AGENT_MODEL=gpt-5.4-mini

docker compose \
  -p anip-gtm-go-local \
  -f examples/showcase/gtm/docker-compose.language-parity-go.yml \
  up -d --build
```

Open:

```text
http://127.0.0.1:4330/
```

The entry page links to:

- `/agent` for the GTM Agent chat UI.
- Metabase on `http://127.0.0.1:3043`.
- The local runbook and example questions.
- The public GTM architecture and testing docs.

Stop:

```bash
docker compose \
  -p anip-gtm-go-local \
  -f examples/showcase/gtm/docker-compose.language-parity-go.yml \
  down
```

## Documentation Links In The Local UI

The local entry page at `/` links back to the public GTM docs:

- [Architecture](/docs/showcases/gtm-agent/architecture)
- [Questions And Extensions](/docs/showcases/gtm-agent/questions-and-extensions)
- [Generate Services](/docs/showcases/gtm-agent/generated-services)
- [Testing](/docs/showcases/gtm-agent/testing)

Published Docker images default these links to `https://anip.dev`. Override the docs base when testing unpublished docs:

```bash
ANIP_AGENT_DOCS_BASE_URL=http://127.0.0.1:3000 \
docker compose \
  -p anip-gtm-go-local \
  -f examples/showcase/gtm/docker-compose.language-parity-go.yml \
  up -d --build
```

## Smoke scripts

Use the smoke script to check stack basics:

```bash
examples/showcase/gtm/scripts/smoke-language-compose.sh go
```

Use the auth smoke to check demo actor tokens and capability auth:

```bash
examples/showcase/gtm/scripts/smoke-language-compose-auth.sh go
```

## Structure

Each compose file follows the same shape:

```text
gtm-postgres
gtm-dbt
gtm-metabase
gtm-metabase-setup
gtm-pipeline-service
gtm-enrichment-service
gtm-prioritization-service
gtm-outreach-service
gtm-agent-llm-ui
```

The only intended differences are language image, generated-service build context, and port offsets.
