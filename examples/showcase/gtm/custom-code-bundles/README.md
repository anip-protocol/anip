# GTM Custom Code Bundles

These bundles are implementation material for `gtm-pipeline-q2-review`.
They are intentionally separate from the signed ANIP behavior contract.

The signed package defines the governed capability surface. A bundle may fill
generated extension seams, such as backend adapters, policy hooks, app entry
points, and project metadata. It must not rewrite generated substrate files,
capability declarations, agent-consumption metadata, Docker files, or contract
validation output.

## Native Language Parity Bundles

Use these bundles for the generated GTM showcase services:

- `gtm_pipeline_python_native`
- `gtm_pipeline_typescript`
- `gtm_pipeline_go_native`
- `gtm_pipeline_java_native`
- `gtm_pipeline_csharp_native`

The older proxy/reference bundles remain for historical comparison. They are not
the language-parity release target.

## Local Generation

Each native bundle has a normalized tree digest listed in
`bundle-catalog.json`. Pass that digest when generating so accidental local
changes, ignored-cache leakage, or the wrong bundle fail fast:

```bash
cd packages/go
go run ./cmd/anip generate \
  --package-bundle ../../examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.3.anip-package.json \
  --target python \
  --dependency-source local \
  --custom-code-bundle ../../examples/showcase/gtm/custom-code-bundles/gtm_pipeline_python_native \
  --verify-custom-code-bundle-digest sha256:89eef6e855812e5cdf6c2848f8471eb01c8ea9e1fb8b112e30abd818c04431aa \
  --output /tmp/anip-gtm-python-native \
  --force
```

Or run the full local bundle smoke:

```bash
examples/showcase/gtm/scripts/verify-custom-bundles.sh
```

## Publishing Implementation Metadata

After a reviewed bundle is published to an immutable external location, create a
new package revision that records the implementation material ref and local tree
digest:

```bash
cd packages/go
go run ./cmd/anip package attach-implementation \
  --package-bundle ../../examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.3.anip-package.json \
  --package-version 0.4.1 \
  --custom-code-bundle-ref 'git+https://github.com/anip-protocol/gtm-bundles.git@<commit-sha>#sha256:<artifact-sha256>' \
  --custom-code-bundle ../../examples/showcase/gtm/custom-code-bundles/gtm_pipeline_python_native \
  --output /tmp/gtm-pipeline-q2-review-0.4.1-publish-request.json
```

The CLI does not upload or fetch custom code automatically. Remote fetching is
reserved for an explicit future opt-in flow; users must review and provide the
local bundle themselves.
