# GitHub Fronting Python Custom Bundle

This bundle fills the generated backend seam for `github-fronting-showcase`.

It intentionally keeps GitHub behavior outside generic ANIP runtime packages:

- live bounded repository search through GitHub REST search;
- metadata-backed issue preview, PR comment preview, workflow dispatch preview, and release-note draft preparation;
- optional approved issue creation after ANIP approval-grant validation;
- repository allowlist and denylist controls through environment variables.

Required for live smoke:

```bash
GITHUB_TOKEN=...
GITHUB_OWNER=...
GITHUB_REPO=...
```

Optional policy controls:

```bash
ANIP_GITHUB_ALLOWED_REPOS=owner/repo,other/repo
ANIP_GITHUB_BLOCKED_REPOS=owner/private-repo
ANIP_GITHUB_ALLOW_MUTATION=true
```

Mutation remains disabled unless both `ANIP_GITHUB_ALLOW_MUTATION=true` and a
valid ANIP approval grant are present on the invocation context.
