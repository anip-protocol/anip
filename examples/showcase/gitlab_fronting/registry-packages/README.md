# gitlab_governed_fronting_showcase

ANIP package `gitlab-fronting-showcase@0.2.0` for local showcase and registry smoke usage.

## Contents

- Services: 1
- Capabilities: 5
- ANIP spec: `anip/0.24`

## Capability Surface

- `gitlab.project.search_context`
- `gitlab.issue.prepare`
- `gitlab.mr.comment.prepare`
- `gitlab.pipeline.trigger.request`
- `gitlab.release_notes.prepare`

## Generate

From a downloaded package bundle:

```bash
go run ./cmd/anip-generate --package-bundle <downloaded-package>.anip-package.json --target python --dependency-source local --output ./generated/gitlab-fronting-showcase --force
```

From a trusted registry package:

```bash
go run ./cmd/anip-generate --registry-url <registry-url> --package-id gitlab-fronting-showcase --package-version 0.2.0 --target python --dependency-source registry --output ./generated/gitlab-fronting-showcase --force
```

## Verify

```bash
go run ./cmd/anip-verify --definition anip-service-definition.json
go run ./cmd/anip-verify --package-bundle <downloaded-package>.anip-package.json
```

## Run Locally

Generated services default to port `9155` unless overridden by the generated runtime configuration.
