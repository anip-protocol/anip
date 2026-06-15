# GTM Local Stack

Each language stack contains:

- Postgres
- dbt
- Metabase
- four generated ANIP services
- GTM agent UI/runtime

## Compose files

```text
docker-compose.language-parity-python.yml
docker-compose.language-parity-typescript.yml
docker-compose.language-parity-go.yml
docker-compose.language-parity-java.yml
docker-compose.language-parity-csharp.yml
```

## Image tags

```text
anipprotocol/showcase-gtm-python:0.4.4
anipprotocol/showcase-gtm-typescript:0.4.4
anipprotocol/showcase-gtm-go:0.4.4
anipprotocol/showcase-gtm-java:0.4.4
anipprotocol/showcase-gtm-csharp:0.4.4
anipprotocol/showcase-gtm-agent-ui:0.4.4
```

## Entry points

| Language | Entry | Agent | Metabase |
| --- | --- | --- | --- |
| Python | `http://127.0.0.1:4310/` | `http://127.0.0.1:4310/agent` | `http://127.0.0.1:3041/` |
| TypeScript | `http://127.0.0.1:4320/` | `http://127.0.0.1:4320/agent` | `http://127.0.0.1:3042/` |
| Go | `http://127.0.0.1:4330/` | `http://127.0.0.1:4330/agent` | `http://127.0.0.1:3043/` |
| Java | `http://127.0.0.1:4340/` | `http://127.0.0.1:4340/agent` | `http://127.0.0.1:3044/` |
| C# | `http://127.0.0.1:4350/` | `http://127.0.0.1:4350/agent` | `http://127.0.0.1:3045/` |

## Start Go stack

```bash
export OPENAI_API_KEY=...
export ANIP_AGENT_MODEL=gpt-5.4-mini

docker compose \
  -p anip-gtm-go-local \
  -f examples/showcase/gtm/docker-compose.language-parity-go.yml \
  up -d
```

## Rebuild dbt and Metabase setup

```bash
docker compose \
  -p anip-gtm-go-local \
  -f examples/showcase/gtm/docker-compose.language-parity-go.yml \
  up gtm-dbt

GTM_METABASE_URL=http://127.0.0.1:3043 \
  python3 examples/showcase/gtm/scripts/setup_metabase_verification.py
```

