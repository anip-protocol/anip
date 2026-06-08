# Linear Governed Fronting Showcase

This example demonstrates ANIP in front of Linear GraphQL. Agents see governed product-work capabilities, not raw workspace operations.

## Source

- Source spec: `docs/examples/linear-fronting-showcase/source-spec.md`
- CLI starter: `docs/examples/linear-fronting-showcase/anip-fronting-starter.json`
- Package bundle: `registry-packages/linear-fronting-showcase-0.2.0.anip-package.json`

## Generate From Starter

```bash
cd packages/go
go run ./cmd/anip fronting scaffold \
  --starter ../../docs/examples/linear-fronting-showcase/anip-fronting-starter.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/linear_fronting/custom-code-bundles/linear_fronting_python \
  --transport http,stdio \
  --output ../../examples/showcase/linear_fronting/generated/studio_linear_fronting \
  --force
```

## Generate From Package

```bash
cd packages/go
go run ./cmd/anip-generate \
  --package-bundle ../../examples/showcase/linear_fronting/registry-packages/linear-fronting-showcase-0.2.0.anip-package.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/linear_fronting/custom-code-bundles/linear_fronting_python \
  --transport http,stdio \
  --output ../../examples/showcase/linear_fronting/generated/studio_linear_fronting \
  --force
```

## Live Linear Tests

```bash
export LINEAR_API_KEY="lin_api_..."
export LINEAR_TEAM_KEY="<team-key-from-issue-prefix>"
export ANIP_LINEAR_ALLOWED_TEAMS="<same-team-key-or-csv-allowlist>"
PYTHONPATH="<repo python packages>:<generated src>" \
  python examples/showcase/linear_fronting/scripts/live_smoke.py
```

`LINEAR_TEAM_KEY` is the team key used in issue identifiers, not necessarily
the workspace or team display name. For example, issue `ANI-123` uses team key
`ANI`.

Run the issue-creation smoke only against a disposable workspace/team:

```bash
export ANIP_LINEAR_ALLOW_MUTATION=true
PYTHONPATH="<repo python packages>:<generated src>" \
  python examples/showcase/linear_fronting/scripts/approved_issue_smoke.py
```

The approved issue smoke confirms `linear.issue.prepare` stops at preview
first, then creates a pending ANIP approval request, issues a one-time grant,
and resubmits the same parameters with `approval_grant`.

## Design Point

The backend is Linear GraphQL for this showcase. The ANIP contract owns team scope, approval posture, bounded `backend_options`, denial rules, and audit.
