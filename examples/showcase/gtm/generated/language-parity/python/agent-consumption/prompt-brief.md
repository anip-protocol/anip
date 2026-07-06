# ANIP Agent Consumption Brief

This directory is generated from signed ANIP package metadata. It is framework-agnostic and can be loaded by LangGraph, Mastra, CrewAI, or custom agents.

- Package: `gtm-pipeline-q2-review@0.4.5`
- Contract signature: `57736b4fe62d4d9a3b5a4b57d0c1daeb217d470904b64cd8568d8532ae1d8bd4`
- Consumability schema: `anip-agent-consumability/v0`
- Capability hints: `23`
- Required app glue items: `0`

## How To Use

- Load `agent-consumability.json` as the semantic hint source.
- Load `agent-app-profile.json` when an agent runtime supports structured app-layer guidance.
- Load `capability-index.json` to map capability IDs to services, scopes, inputs, and hints.
- Use `app-glue-required.json` to keep app-specific behavior explicit instead of hiding it in generic runtime code.
- Load `runtime-customization.json` plus `custom/runtime-overrides.json` for reviewed app-specific normalization and capability-selection behavior.
- Use reviewed `intent_rules` as app-consumption guidance; do not treat unreviewed AI drafts as authority.
- Treat this brief as convenience text; JSON files are the authoritative artifacts.

