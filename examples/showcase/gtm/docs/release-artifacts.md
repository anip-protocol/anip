# GTM Release Artifacts

Canonical package:

```text
examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.5.anip-package.json
```

Related package files:

```text
examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.5-service-definition.json
examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.5-manifest.json
examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.5-lock.json
examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.5-publish-request.json
```

Generated language outputs:

```text
examples/showcase/gtm/generated/language-parity/python/
examples/showcase/gtm/generated/language-parity/typescript/
examples/showcase/gtm/generated/language-parity/go/
examples/showcase/gtm/generated/language-parity/java/
examples/showcase/gtm/generated/language-parity/csharp/
```

Release-target custom bundles:

```text
examples/showcase/gtm/custom-code-bundles/gtm_pipeline_python_native/
examples/showcase/gtm/custom-code-bundles/gtm_pipeline_typescript/
examples/showcase/gtm/custom-code-bundles/gtm_pipeline_go_native/
examples/showcase/gtm/custom-code-bundles/gtm_pipeline_java_native/
examples/showcase/gtm/custom-code-bundles/gtm_pipeline_csharp_native/
```

Bundle catalog:

```text
examples/showcase/gtm/custom-code-bundles/bundle-catalog.json
```

Before publishing or rebuilding Docker images:

- verify the package version is `0.4.5`;
- verify all generated outputs come from the same package;
- verify bundle reports are present;
- run compose smoke;
- run question-bank release gates.

