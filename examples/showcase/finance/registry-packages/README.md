# Finance Operations Showcase Registry Package

Generated from `docs/examples/finance-showcase/source-spec.md`.

Generate Python code:

```bash
cd packages/go
go run ./cmd/anip-generate \
  --package-bundle ../../examples/showcase/finance/registry-packages/finance-operations-showcase-0.1.0.anip-package.json \
  --target python \
  --dependency-source local \
  --package-name anip_finance_showcase \
  --port 9120 \
  --output ../../examples/showcase/finance/generated/studio_finance \
  --force
```
