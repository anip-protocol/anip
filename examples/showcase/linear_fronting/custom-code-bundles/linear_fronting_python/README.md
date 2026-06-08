# Linear Fronting Python Custom Bundle

This bundle fills the generated ANIP backend seam for the Linear governed
fronting showcase. The generated substrate owns tokens, approvals, validation,
audit, and transport. This bundle only maps governed ANIP capability inputs to
bounded Linear GraphQL calls.

Required environment for live use:

```bash
LINEAR_API_KEY=...
LINEAR_TEAM_KEY=...
```

Optional controls:

```bash
ANIP_LINEAR_ALLOWED_TEAMS=ENG,OPS
ANIP_LINEAR_ALLOW_MUTATION=true
```

Mutations are disabled unless `ANIP_LINEAR_ALLOW_MUTATION=true` and the
invocation carries a valid ANIP approval grant.
