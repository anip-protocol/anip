# GitHub Governed Fronting Showcase

This example shows the intended ANIP pattern for fronting broad GitHub REST/GraphQL API access:
raw GitHub operations are downstream implementation details; agents invoke governed ANIP capabilities. GitHub MCP is useful as a comparison surface, but this package binds to native GitHub APIs.

## Build artifacts

```bash
cd packages/go
go run ./cmd/anip-generate \
  --package-bundle ../../examples/showcase/github_fronting/registry-packages/github-fronting-showcase-0.2.0.anip-package.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/github_fronting/custom-code-bundles/github_fronting_python \
  --transport http,stdio \
  --port 9150 \
  --output ../../examples/showcase/github_fronting/generated/studio_github_fronting \
  --force
```

Generate directly from the reviewed fronting starter:

```bash
cd packages/go
go run ./cmd/anip fronting scaffold \
  --starter ../../docs/examples/github-fronting-showcase/anip-fronting-starter.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/github_fronting/custom-code-bundles/github_fronting_python \
  --transport http,stdio \
  --output ../../examples/showcase/github_fronting/generated/studio_github_fronting \
  --force
```

Verify the local service definition:

```bash
cd packages/go
go run ./cmd/anip-verify \
  --definition ../../examples/showcase/github_fronting/registry-packages/github-fronting-showcase-0.2.0-service-definition.json
```

## What to inspect

- `registry-packages/github-fronting-showcase-0.2.0-service-definition.json`: signed behavior contract with `integration_fronting` mappings.
- `generated/studio_github_fronting/integration-fronting/adapter-bindings.json`: capability-to-backend binding pack.
- `generated/studio_github_fronting/integration-fronting/backend-selection.example.json`: deployment-time backend selection template.
- `generated/studio_github_fronting/integration-fronting/conformance.json`: static check that raw backend operations are governed.

## Live GitHub tests

The generated Python adapter includes live GitHub REST behavior for:

- `github.repo.search_context`: executes a bounded repository-scoped issue/PR search.
- `github.issue.prepare`: fetches repository metadata and returns a create-issue payload preview without creating an issue.
- Optional GitHub issue creation: disabled by default; requires `ANIP_GITHUB_ALLOW_MUTATION=true` plus a real ANIP approval continuation grant supplied as the top-level `approval_grant` invoke field.

It uses these environment variables:

```bash
export GITHUB_TOKEN="github_pat_or_fine_grained_token"
export GITHUB_OWNER="your-org-or-user"
export GITHUB_REPO="your-repo"
PYTHONPATH="<repo python packages>:<generated src>" \
  python examples/showcase/github_fronting/scripts/live_smoke.py
```

Run the issue-creation smoke test only against a disposable repository:

```bash
export ANIP_GITHUB_ALLOW_MUTATION=true
PYTHONPATH="<repo python packages>:<generated src>" \
  python examples/showcase/github_fronting/scripts/approved_issue_smoke.py
```

The approved issue smoke first invokes `github.issue.prepare` and confirms that it
stops at a preview-only result. It then creates a pending ANIP approval request,
issues a one-time grant, and resubmits the same parameters with the top-level
`approval_grant`. The GitHub adapter only creates the issue after the ANIP runtime
validates and reserves that grant.

## Design point

The package uses native GitHub REST/GraphQL APIs as its execution binding. MCP can be compared separately as a raw tool surface, but the governed ANIP contract remains the agent-facing interface.
