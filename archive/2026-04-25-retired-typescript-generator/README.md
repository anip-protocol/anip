# Retired TypeScript Generator Archive

Archived on 2026-04-25.

This archive preserves the old Studio-coupled TypeScript generator path while removing it from active product/runtime flow.

## Archived Items

- `packages/typescript/generator`: legacy `@anip-dev/generator-typescript` package and CLI.
- `studio/server/generator_cli.py`: Studio backend adapter that shelled out to the legacy TypeScript generator.
- `studio/server/local_runtime_proof.py`: Studio backend runtime proof path that rebuilt and ran generated TypeScript bundles through npm.
- `scripts/complete-gtm-pipeline-studio-project.ts`: one-off automation that called the retired Studio generator endpoint.
- `examples/showcase/gtm/generated/studio_gtm_pipeline_typescript_registry`: generated output produced by the retired path.

## Active Direction

Studio owns project modeling, revisions, Registry publication, and generation handoff records.

Generators and verifiers are external Go tools. They should resolve immutable Registry packages or package bundles and produce target-language output outside Studio.

The old `/api/projects/{pid}/generator/typescript` and `/api/projects/{pid}/proofs/local-runtime` endpoints remain only as `410 Gone` compatibility guards so stale clients fail explicitly.
