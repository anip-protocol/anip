# Jira Fronting Python Custom Bundle

This bundle fills the generated Python backend adapter seam for the Jira fronting showcase.

It is implementation material, not part of the signed ANIP behavior contract. Generate the service from the signed Registry package, then apply this bundle explicitly:

```bash
go run ./cmd/anip-generate \
  --registry-url http://127.0.0.1:8200/registry-api/v1 \
  --package-id jira-fronting-showcase \
  --package-version 0.2.0 \
  --target python \
  --transport http,stdio \
  --dependency-source registry \
  --custom-code-bundle examples/showcase/jira_fronting/custom-code-bundles/jira_fronting_python \
  --output /tmp/anip-jira-fronting-python \
  --force
```

Runtime credentials are read from environment variables:

- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`

The adapter performs live read and metadata calls when credentials are present. Mutating Jira calls are intentionally not executed by this bundle; write-adjacent capabilities return governed previews that a host application can route through its approval and execution layer.
