# GitLab Fronting Python Custom Bundle

This bundle fills the generated backend seam for `gitlab-fronting-showcase`.

It keeps GitLab-specific behavior outside generic ANIP packages:

- bounded project search across issues and merge requests;
- metadata-backed issue preview, merge-request comment preview, pipeline trigger preview, and release-note draft;
- optional approved issue creation after ANIP approval-grant validation;
- project allowlist and denylist controls through environment variables.

Required for live smoke:

```bash
GITLAB_TOKEN=...
GITLAB_PROJECT_ID=...
```

Optional policy controls:

```bash
GITLAB_API_BASE=https://gitlab.com/api/v4
ANIP_GITLAB_ALLOWED_PROJECTS=12345,group/project
ANIP_GITLAB_BLOCKED_PROJECTS=group/secret-project
ANIP_GITLAB_ALLOW_MUTATION=true
```

Mutation remains disabled unless both `ANIP_GITLAB_ALLOW_MUTATION=true` and a
valid ANIP approval grant are present on the invocation context.
