# GitLab Governed Fronting Showcase

This example demonstrates ANIP in front of native GitLab REST/GraphQL APIs. Agents see governed delivery capabilities, not raw project operations. GitLab MCP is useful as a comparison surface, but this package binds to native GitLab APIs.

## Source

- Source spec: `docs/examples/gitlab-fronting-showcase/source-spec.md`
- CLI starter: `docs/examples/gitlab-fronting-showcase/anip-fronting-starter.json`
- Package bundle: `registry-packages/gitlab-fronting-showcase-0.2.0.anip-package.json`

## Generate From Starter

```bash
cd packages/go
go run ./cmd/anip fronting scaffold \
  --starter ../../docs/examples/gitlab-fronting-showcase/anip-fronting-starter.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/gitlab_fronting/custom-code-bundles/gitlab_fronting_python \
  --transport http,stdio \
  --output ../../examples/showcase/gitlab_fronting/generated/studio_gitlab_fronting \
  --force
```

## Generate From Package

```bash
cd packages/go
go run ./cmd/anip-generate \
  --package-bundle ../../examples/showcase/gitlab_fronting/registry-packages/gitlab-fronting-showcase-0.2.0.anip-package.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/gitlab_fronting/custom-code-bundles/gitlab_fronting_python \
  --transport http,stdio \
  --output ../../examples/showcase/gitlab_fronting/generated/studio_gitlab_fronting \
  --force
```

Use the matching custom-code bundle for each generated language:

| Target | Custom code bundle |
| --- | --- |
| `python` | `../../examples/showcase/gitlab_fronting/custom-code-bundles/gitlab_fronting_python` |
| `typescript` | `../../examples/showcase/gitlab_fronting/custom-code-bundles/gitlab_fronting_typescript` |
| `go` | `../../examples/showcase/gitlab_fronting/custom-code-bundles/gitlab_fronting_go` |
| `java` | `../../examples/showcase/gitlab_fronting/custom-code-bundles/gitlab_fronting_java` |
| `csharp` | `../../examples/showcase/gitlab_fronting/custom-code-bundles/gitlab_fronting_csharp` |

The generated service is runnable without a custom bundle, but then the backend
seam intentionally returns generated stub/preparation responses. The showcase
release path uses the custom bundle for live GitLab execution in every supported
target language.

## Live GitLab Tests

```bash
export GITLAB_TOKEN="glpat-or-project-token"
export GITLAB_PROJECT_ID="group/project-or-numeric-id"
cd examples/showcase/gitlab_fronting/generated/studio_gitlab_fronting
PYTHON=.venv/bin/python ../../scripts/live_smoke.sh
```

Run the issue-creation smoke only against a disposable project:

```bash
export ANIP_GITLAB_ALLOW_MUTATION=true
PYTHON=.venv/bin/python ../../scripts/approved_issue_smoke.sh
```

The shell wrappers set the generated project on `PYTHONPATH` before Python
starts. This avoids import-bootstrap differences between direct script
execution and generated editable installs.

The approved issue smoke confirms `gitlab.issue.prepare` stops at preview first,
then creates a pending ANIP approval request, issues a one-time grant, and
resubmits the same parameters with `approval_grant`.

The TypeScript, Go, Java, and C# bundles also include live tests that run when
`GITLAB_TOKEN` and `GITLAB_PROJECT_ID` are present. They validate read/preview
behavior and approved issue creation through the generated handler.

## Design Point

The package uses native GitLab REST/GraphQL APIs as its execution binding. MCP can be compared separately as a raw tool surface, but the ANIP contract owns project scope, approval posture, bounded `backend_options`, denial rules, and audit.
