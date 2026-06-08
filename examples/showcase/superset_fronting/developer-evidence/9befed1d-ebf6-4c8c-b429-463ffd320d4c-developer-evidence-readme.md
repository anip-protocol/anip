# Completed Superset Developer Evidence

Completed developer evidence for the browser-authored Superset Fronting Showcase 0.2.0 Studio project.

Project ID: `9befed1d-ebf6-4c8c-b429-463ffd320d4c`
Product revision artifact: `9befed1d-ebf6-4c8c-b429-463ffd320d4c-product-design-revision-1`
Product revision number: `1`

Files:

- `9befed1d-ebf6-4c8c-b429-463ffd320d4c-capability-runtime-governance.completed.csv`
- `9befed1d-ebf6-4c8c-b429-463ffd320d4c-capability-input-contracts.completed.csv`
- `9befed1d-ebf6-4c8c-b429-463ffd320d4c-capability-composition.completed.csv`

Important governance choices:

- `superset.analytics.answer_question` is backed by provider-owned semantic execution and bounded chart-data style reads. Raw SQL is not an agent input and is not modeled as a backend operation.
- `superset.chart.preview.create` and `superset.dashboard.draft.prepare` are preview/draft capabilities and do not save or publish Superset assets.
- `superset.chart.publish.request` and `superset.dataset.draft.prepare` are approval-gated and stop at approval request / preview mutation posture.
- All six capabilities are atomic from the ANIP contract perspective. Superset native REST calls are provider-owned adapter internals, not child ANIP composition steps.
