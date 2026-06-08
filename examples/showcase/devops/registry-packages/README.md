# DevOps Infrastructure Showcase Registry Package

Generated from `docs/examples/devops-showcase/source-spec.md`.

Generate Python code:

```bash
cd packages/go
go run ./cmd/anip-generate \
  --package-bundle ../../examples/showcase/devops/registry-packages/devops-infrastructure-showcase-0.1.0.anip-package.json \
  --target python \
  --dependency-source local \
  --package-name anip_devops_showcase \
  --port 9130 \
  --output ../../examples/showcase/devops/generated/studio_devops \
  --force
```
