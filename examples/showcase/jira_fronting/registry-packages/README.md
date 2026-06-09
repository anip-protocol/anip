# jira_governed_fronting_showcase

ANIP package `jira-fronting-showcase@0.2.0` for local showcase and registry smoke usage.

## Contents

- Services: 1
- Capabilities: 11
- ANIP spec: `anip/0.24`

## Capability Surface

- `jira.backlog.search_context`
- `jira.issue.get_context`
- `jira.incident_bug.prepare`
- `jira.story.prepare`
- `jira.subtask.prepare`
- `jira.customer_escalation.comment.prepare`
- `jira.workflow_transition.request`
- `jira.sprint_move.request`
- `jira.assignee_change.request`
- `jira.issue_link.request`
- `jira.release_notes.prepare`

## Generate

From a downloaded package bundle:

```bash
go run ./cmd/anip-generate --package-bundle <downloaded-package>.anip-package.json --target python --dependency-source local --output ./generated/jira-fronting-showcase --force
```

From a trusted registry package:

```bash
go run ./cmd/anip-generate --registry-url <registry-url> --package-id jira-fronting-showcase --package-version 0.2.0 --target python --dependency-source registry --output ./generated/jira-fronting-showcase --force
```

## Verify

```bash
go run ./cmd/anip-verify --definition anip-service-definition.json
go run ./cmd/anip-verify --package-bundle <downloaded-package>.anip-package.json
```

## Run Locally

Generated services default to port `9140` unless overridden by the generated runtime configuration.
