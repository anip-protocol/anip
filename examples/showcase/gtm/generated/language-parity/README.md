# GTM Generated Language Parity Baseline

This directory contains the committed GTM generated-service baseline for the five supported ANIP language targets:

- `python`
- `typescript`
- `go`
- `java`
- `csharp`

Each directory was generated from the same GTM service definition and then filled with the matching language-native custom bundle. This is the apples-to-apples parity target for release validation.

Important boundaries:

- These services are native ANIP implementations in their target language, not proxies to the original Python showcase.
- Public manifests must stay identical to the signed contract. Custom bundles must not mutate generated declarations such as capability kind, composition, inputs, minimum scope, grant policy, side-effect posture, or resolution metadata.
- GTM-specific execution shortcuts belong behind backend adapters or runtime implementation seams. If the governed capability surface needs to change, regenerate and sign a new package revision instead of patching generated metadata.
- Generated signing keys, dependency directories, build outputs, and test caches are intentionally excluded.
- Older generated folders under `examples/showcase/gtm/generated/` remain historical/reference material unless explicitly documented otherwise.
- The hand-written Python showcase remains useful as a reference implementation, but it is not the language-parity comparison target.

Expected contract shape:

- 4 services
- 23 formalized GTM capabilities
- identical capability-id set across all five language outputs

Before publishing release artifacts, regenerate these outputs from the Studio-produced GTM contract and rerun the language parity gates.

## Local Docker Compose Stacks

Each language has a runnable compose stack at `examples/showcase/gtm/docker-compose.language-parity-<language>.yml`.

Run one stack from the GTM showcase directory:

```bash
cd examples/showcase/gtm
docker compose -f docker-compose.language-parity-python.yml up --build
```

Available stacks:

- Python: `docker-compose.language-parity-python.yml`
- TypeScript: `docker-compose.language-parity-typescript.yml`
- Go: `docker-compose.language-parity-go.yml`
- Java: `docker-compose.language-parity-java.yml`
- C#: `docker-compose.language-parity-csharp.yml`

Each stack starts:

- Postgres loaded through the GTM dbt project.
- Four native ANIP services for the selected language.
- Metabase for local BI inspection.
- The GTM agent LLM UI configured against the four language-native services.

The compose files intentionally use different host ports so multiple stacks can be compared without editing service code.
