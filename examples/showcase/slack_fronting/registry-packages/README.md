# slack_governed_fronting_showcase

ANIP package `slack-fronting-showcase@0.2.0` for local showcase and registry smoke usage.

## Contents

- Services: 1
- Capabilities: 5
- ANIP spec: `anip/0.24`

## Capability Surface

- `slack.channel.read_context`
- `slack.thread.summarize`
- `slack.message.prepare`
- `slack.incident_update.prepare`
- `slack.announcement.request`

## Generate

From a downloaded package bundle:

```bash
go run ./cmd/anip-generate --package-bundle <downloaded-package>.anip-package.json --target python --dependency-source local --output ./generated/slack-fronting-showcase --force
```

From a trusted registry package:

```bash
go run ./cmd/anip-generate --registry-url <registry-url> --package-id slack-fronting-showcase --package-version 0.2.0 --target python --dependency-source registry --output ./generated/slack-fronting-showcase --force
```

## Verify

```bash
go run ./cmd/anip-verify --definition anip-service-definition.json
go run ./cmd/anip-verify --package-bundle <downloaded-package>.anip-package.json
```

## Run Locally

Generated services default to port `9160` unless overridden by the generated runtime configuration.
