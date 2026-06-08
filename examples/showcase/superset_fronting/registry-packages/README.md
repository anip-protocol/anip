# superset_governed_fronting_showcase

ANIP package `superset-fronting-showcase@0.2.0` for local showcase and registry smoke usage.

## Contents

- Services: 1
- Capabilities: 6
- ANIP spec: `anip/0.24`

## Capability Surface

- `superset.analytics.discover_context`
- `superset.analytics.answer_question`
- `superset.chart.preview.create`
- `superset.chart.publish.request`
- `superset.dashboard.draft.prepare`
- `superset.dataset.draft.prepare`

## Generate

From a downloaded package bundle:

```bash
go run ./cmd/anip-generate --package-bundle <downloaded-package>.anip-package.json --target python --dependency-source local --output ./generated/superset-fronting-showcase --force
```

From a trusted registry package:

```bash
go run ./cmd/anip-generate --registry-url <registry-url> --package-id superset-fronting-showcase --package-version 0.2.0 --target python --dependency-source registry --output ./generated/superset-fronting-showcase --force
```

## Verify

```bash
go run ./cmd/anip-verify --definition anip-service-definition.json
go run ./cmd/anip-verify --package-bundle <downloaded-package>.anip-package.json
```

## Run Locally

Generated services default to port `9180` unless overridden by the generated runtime configuration.
