# github_governed_fronting_showcase

ANIP package `github-fronting-showcase@0.2.0` for local showcase and registry smoke usage.

## Contents

- Services: 1
- Capabilities: 5
- ANIP spec: `anip/0.24`

## Capability Surface

- `github.repo.search_context`
- `github.issue.prepare`
- `github.pr.comment.prepare`
- `github.workflow.dispatch.request`
- `github.release_notes.prepare`

## Generate

From a downloaded package bundle:

```bash
go run ./cmd/anip-generate --package-bundle <downloaded-package>.anip-package.json --target python --dependency-source local --output ./generated/github-fronting-showcase --force
```

From a trusted registry package:

```bash
go run ./cmd/anip-generate --registry-url <registry-url> --package-id github-fronting-showcase --package-version 0.2.0 --target python --dependency-source registry --output ./generated/github-fronting-showcase --force
```

## Verify

```bash
go run ./cmd/anip-verify --definition anip-service-definition.json
go run ./cmd/anip-verify --package-bundle <downloaded-package>.anip-package.json
```

## Run Locally

Generated services default to port `9150` unless overridden by the generated runtime configuration.
