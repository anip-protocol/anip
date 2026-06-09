# Services

This directory contains the manually maintained GTM ANIP service benchmark.
Do not treat these files as disposable generated output.

Planned services:

- `gtm-pipeline-service`
- `gtm-enrichment-service`
- `gtm-prioritization-service`
- `gtm-outreach-service`

The first one to implement should be:

- `gtm-pipeline-service`

Implementation modes should stay mixed on purpose:

- pipeline and enrichment: warehouse/data-access services
- prioritization: REST backend fronted by ANIP
- outreach: MCP backend fronted by ANIP

Preservation rule:

- `examples/showcase/gtm/services/*` is benchmark source.
- `examples/showcase/gtm/generated/*` is generated or copied output.
- Run `python3 examples/showcase/gtm/scripts/verify_manual_benchmark.py` before and after generator work that touches the GTM showcase.
- If the verifier fails, either revert the accidental change or intentionally update `examples/showcase/gtm/manual-benchmark-manifest.json` as part of a reviewed benchmark change.
