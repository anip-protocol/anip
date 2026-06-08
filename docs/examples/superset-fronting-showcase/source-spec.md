# Superset Governed Fronting Showcase Source Specification

This source document models a realistic analytics fronting use case: Superset native APIs exist downstream, but agents should only see governed analytics capabilities.

## Purpose

Demonstrate that ANIP can govern analytics behavior in front of Apache Superset without exposing raw SQL, chart, dashboard, or dataset tools directly to agents.

The ANIP contract owns the analytics capability semantics. Superset native REST APIs are the durable backend for this showcase. Superset MCP may be useful as a comparison point for raw tool exposure, but this package does not use MCP as the ANIP execution interface.

## Service Boundary

- Service ID: `superset-governance-service`
- Service name: Superset Governance Service
- Primary backend: native Superset REST API adapter
- Deployment posture: centralized ANIP fronting service with enterprise SSO, Superset actor mapping, dataset allowlists, metric/dimension governance, SQL restrictions, approval records, and audit.

## Backend Evidence

Native Superset API supply:

- Dataset discovery and dataset metadata through `/api/v1/dataset/`.
- Chart discovery and chart metadata through `/api/v1/chart/`.
- Dashboard discovery and dashboard metadata through `/api/v1/dashboard/`.
- Chart-data, dataset, chart, and dashboard APIs where enabled by deployment policy.
- Chart/dashboard create or update APIs where enabled by deployment policy.

MCP comparison:

- Superset MCP exposes tool-level operations for datasets, charts, dashboards, SQL, and databases.
- This showcase intentionally does not bind ANIP capabilities to Superset MCP tools. The point is to expose a governed capability surface backed by bounded native APIs, not to rename raw MCP tools.
- ANIP adds business-level governance: metric allowlists, result-grain restrictions, preview-only defaults, explicit approvals, and denial of raw SQL or raw exports.

## Governed Capability Surface

| Capability | User intent | Required inputs | Optional governed inputs | Outcome posture |
| --- | --- | --- | --- | --- |
| `superset.analytics.discover_context` | Discover allowed datasets, charts, dashboards, metrics, and dimensions. | `workspace_scope`, `query` | `asset_type`, `limit`, `backend_options` | Read-only. Returns actor-visible analytics catalog summaries. |
| `superset.analytics.answer_question` | Answer a governed analytics question against allowed datasets and metrics. | `question`, `dataset_ref` | `metric`, `dimension`, `time_window`, `filters`, `limit`, `backend_options` | Read-only or preview. Uses bounded chart-data or provider-owned semantic execution; raw SQL is not an agent input or backend mapping. |
| `superset.chart.preview.create` | Create a chart preview from governed metric/dimension intent. | `dataset_ref`, `metric`, `visualization_type` | `dimension`, `time_window`, `filters`, `title`, `backend_options` | Preview-only. Does not save a chart by default. |
| `superset.chart.publish.request` | Request saving or updating a chart. | `chart_preview_ref`, `dashboard_scope`, `reason` | `title`, `backend_options` | Approval-gated. Requires analytics owner or BI admin approval. |
| `superset.dashboard.draft.prepare` | Prepare a dashboard draft or update proposal. | `dashboard_scope`, `objective`, `chart_refs` | `layout_hint`, `audience`, `backend_options` | Preview-only. Requires approval before publish. |
| `superset.dataset.draft.prepare` | Prepare a virtual dataset or semantic dataset draft. | `database_ref`, `dataset_purpose`, `query_intent` | `source_tables`, `metrics`, `backend_options` | Approval-gated draft. Raw SQL is not accepted from agents. |

`backend_options` is limited to bounded provider controls such as selected fields, pagination, chart rendering format, or preview output format. It must not allow arbitrary SQL execution, unbounded result export, database switching, dataset allowlist bypass, or hidden dashboard publication.

## Policy Semantics

- Dataset, chart, dashboard, and database scope must be actor-visible and allowlisted.
- Missing dataset, metric, chart preview, dashboard scope, or publish reason returns `clarification_required`.
- Chart creation defaults to preview-only. Saving charts, publishing dashboards, and creating virtual datasets require approval.
- Raw SQL is not accepted from agents. The service may use provider-owned semantic execution only within declared dataset, metric, grain, row-limit, and audit constraints.
- Owner-level, row-level, customer-level, or sensitive dimensions may be restricted even if Superset RBAC allows the underlying query.
- Raw exports, unrestricted SQL, protected database access, dashboard publication bypass, and unapproved saved-query creation are denied.
- Native REST APIs are the execution binding for this package. MCP can be used as a comparison surface, but is not required for ANIP.

## Why ANIP Helps

Superset MCP gives agents useful analytics tools, but it still exposes tool-level operations. ANIP exposes organization-approved analytics capabilities with explicit input semantics, metric constraints, preview behavior, approvals, denial rules, and audit.

## Source Notes

- Superset MCP admin documentation describes built-in MCP access for datasets, charts, dashboards, SQL, and databases, with RBAC enforcement and action-log audit: https://superset.apache.org/admin-docs/configuration/mcp-server/
- Superset user documentation describes AI/MCP tools such as dataset listing, dataset metadata, chart preview/generation, and SQL execution: https://superset.apache.org/user-docs/using-superset/using-ai-with-superset/
