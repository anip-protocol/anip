# GitHub fronting TypeScript custom bundle

Adds a native GitHub REST backend adapter and live smoke tests for the generated TypeScript service.

Required live-test environment:

```bash
GITHUB_TOKEN=...
GITHUB_OWNER=anip-protocol
GITHUB_REPO=anip-fronting-test
ANIP_GITHUB_ALLOWED_REPOS=anip-protocol/anip-fronting-test
ANIP_GITHUB_ALLOW_MUTATION=true
```

Mutation tests intentionally create one issue only after the generated ANIP handler receives an approval grant.
