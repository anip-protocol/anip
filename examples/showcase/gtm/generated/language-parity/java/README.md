# GTM Java Native Custom Bundle

This bundle fills the generated Java ANIP service seams with GTM-specific
implementation logic for the language-parity showcase.

It is intentionally custom implementation material:

- generated substrate remains generic Java ANIP host code
- GTM SQL, fixture catalogs, actor interpretation, and approval previews live here
- the Java service does not proxy to the Python or TypeScript reference stacks

Generate with:

```bash
go run ./cmd/anip-generate \
  --definition ../../output/gtm-language-parity/python/anip-service-definition.json \
  --target java \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/gtm/custom-code-bundles/gtm_pipeline_java_native \
  --output ../../output/gtm-language-parity/java-native \
  --force
```
