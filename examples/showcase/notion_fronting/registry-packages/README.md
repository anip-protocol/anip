# Notion Fronting Showcase

ANIP package `notion-fronting-showcase@0.2.0` for local showcase and registry smoke usage.

## Contents

- Services: 1
- Capabilities: 5
- ANIP spec: `anip/0.24`

## Capability Surface

- `notion.workspace.search_context`
- `notion.database.query_context`
- `notion.page.create.prepare`
- `notion.page.update.prepare`
- `notion.comment.prepare`

## Generate

From a downloaded package bundle:

```bash
go run ./cmd/anip-generate --package-bundle <downloaded-package>.anip-package.json --target python --dependency-source local --output ./generated/notion-fronting-showcase --force
```

From a trusted registry package:

```bash
go run ./cmd/anip-generate --registry-url <registry-url> --package-id notion-fronting-showcase --package-version 0.2.0 --target python --dependency-source registry --output ./generated/notion-fronting-showcase --force
```

## Verify

```bash
go run ./cmd/anip-verify --definition anip-service-definition.json
go run ./cmd/anip-verify --package-bundle <downloaded-package>.anip-package.json
```

## Run Locally

Generated services default to port `9162` unless overridden by the generated runtime configuration.
