# Superset Fronting Python Custom Bundle

This bundle fills the generated ANIP backend seam for the Superset governed
fronting showcase. The generated substrate owns ANIP validation, token issuance,
approvals, audit, and transports. This bundle maps governed analytics inputs to
bounded Superset REST API calls or preview payloads.

Required environment for live use:

```bash
SUPERSET_BASE_URL=http://127.0.0.1:8088
SUPERSET_USERNAME=admin
SUPERSET_PASSWORD=admin
SUPERSET_WORKSPACE_SCOPE=local
```

Optional controls:

```bash
SUPERSET_ACCESS_TOKEN=...
ANIP_SUPERSET_ALLOWED_WORKSPACES=local
ANIP_SUPERSET_ALLOWED_DATASETS=1,2,examples.birth_names
ANIP_SUPERSET_ALLOW_MUTATION=true
```

Write-like analytics actions default to preview-only. Mutations are disabled
unless `ANIP_SUPERSET_ALLOW_MUTATION=true` and the invocation carries a valid
ANIP approval grant.
