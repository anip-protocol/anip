---
title: Superset Fronting
description: Governed Superset fronting showcase for analytics discovery, answers, chart previews, chart publishing requests, dashboard drafts, and dataset drafts.
---

# Superset Fronting

Superset demonstrates governed analytics behavior over a local BI system.

The package is:

```text
superset-fronting-showcase@0.2.0
```

## What It Proves

Superset is a strong ANIP example because analytics systems often expose powerful primitives: SQL, datasets, charts, dashboards, and publishing. ANIP should not make raw SQL the agent-facing product interface.

The contract exposes governed analytics capabilities:

- Discovery is bounded to allowed datasets, charts, dashboards, databases, metrics, and dimensions.
- Analytics answers use provider-owned semantic execution, chart data, dataset metadata, or saved-query behavior, not arbitrary agent-supplied SQL.
- Chart creation defaults to preview.
- Chart publishing, dashboard updates, and dataset drafts require approval posture.
- Raw export, unrestricted SQL, protected database access, and publication bypass are denied.

## Capability Surface

| Capability | Intent |
| --- | --- |
| `superset.analytics.discover_context` | Discover allowed analytics context. |
| `superset.analytics.answer_question` | Answer a bounded analytics question without exposing raw SQL as the agent interface. |
| `superset.chart.preview.create` | Prepare a chart preview. |
| `superset.chart.publish.request` | Request chart publication through approval posture. |
| `superset.dashboard.draft.prepare` | Prepare a dashboard draft. |
| `superset.dataset.draft.prepare` | Prepare a dataset draft. |

## Backend Boundary

The backend is native Superset REST/API behavior. Superset MCP can be useful as a comparison surface, but this showcase does not expose MCP tools as the ANIP product contract.

The important difference:

```text
Agent-facing: governed analytics capability
Backend-facing: Superset-native execution binding
```

## Artifacts

| Artifact | Path |
| --- | --- |
| Source spec | `docs/examples/superset-fronting-showcase/source-spec.md` |
| Package | `examples/showcase/superset_fronting/registry-packages/superset-fronting-showcase-0.2.0.anip-package.json` |
| Service definition | `examples/showcase/superset_fronting/registry-packages/superset-fronting-showcase-0.2.0-service-definition.json` |
| Custom bundles | `examples/showcase/superset_fronting/custom-code-bundles/` |
| Local compose | `examples/showcase/superset_fronting/compose/` |
| Generated services | `examples/showcase/superset_fronting/generated/` |

## Local Validation

Superset is designed to be runnable locally because it should not require a paid SaaS account to understand the showcase.

Start the local Superset 6.1 stack:

```bash
examples/showcase/superset_fronting/compose/setup.sh
```

Then run the live smoke:

```bash
python3 examples/showcase/superset_fronting/scripts/live_smoke.py
```

The smoke should validate bounded discovery and preview behavior without exposing raw SQL as an agent input.

