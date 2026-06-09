# ANIP Agent Consumption Brief

This directory is generated from signed ANIP package metadata. It is framework-agnostic and can be loaded by LangGraph, Mastra, CrewAI, or custom agents.

- Package: `gtm-pipeline-q2-review@0.3.7`
- Contract signature: `sha256:c8ef395f5f19361a2f86e7078b2f8cec199b346d69293f3b754380063636f4e8`
- Consumability schema: `anip-agent-consumability/v0`
- Capability hints: `23`
- Required app glue items: `11`

## How To Use

- Load `agent-consumability.json` as the semantic hint source.
- Load `agent-app-profile.json` when an agent runtime supports structured app-layer guidance.
- Load `capability-index.json` to map capability IDs to services, scopes, inputs, and hints.
- Use `app-glue-required.json` to keep app-specific behavior explicit instead of hiding it in generic runtime code.
- Load `runtime-customization.json` plus `custom/runtime-overrides.json` for reviewed app-specific normalization and capability-selection behavior.
- Use reviewed `intent_rules` as app-consumption guidance; do not treat unreviewed AI drafts as authority.
- Treat this brief as convenience text; JSON files are the authoritative artifacts.

## Required App Glue

- `gtm.account_enrichment_summary`: Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.
- `gtm.account_risk_summary`: Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.
- `gtm.at_risk_account_enrichment_summary`: Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.
- `gtm.bottleneck_account_outreach_draft`: Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.
- `gtm.draft_outreach_message`: Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.
- `gtm.objection_response_variants`: Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.
- `gtm.pipeline_forecast_summary`: Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.
- `gtm.prioritize_accounts`: Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.
- `gtm.prioritized_outreach_draft`: Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.
- `gtm.score_leads`: Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.
- `gtm.stage_bottleneck_summary`: Operator review classified this as consuming-app guidance. The contract remains valid; the app profile owns selection, framing, or clarification behavior without changing generic ANIP invocation.

