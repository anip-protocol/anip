# GTM Pipeline Python Custom Code Bundle

This bundle overlays the Go-generated Python scaffold for `gtm-pipeline-q2-review`
with the preserved GTM benchmark implementation:

- concrete GTM capability handlers
- Cube/Postgres data access adapter
- actor identity and approval store helpers
- Docker-friendly Python project dependencies

Use it with:

```bash
go run ./cmd/anip-generate \
  --registry-url http://127.0.0.1:8200 \
  --package gtm-pipeline-q2-review@0.2.0 \
  --target python \
  --custom-code-bundle ../../examples/showcase/gtm/custom-code-bundles/gtm_pipeline_python \
  --dockerfile \
  --docker-compose \
  --output ../../examples/showcase/gtm/generated/go_registry_gtm_pipeline_custom \
  --force \
  --port 4100
```
