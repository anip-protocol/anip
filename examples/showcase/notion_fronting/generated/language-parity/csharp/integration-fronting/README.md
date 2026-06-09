# Governed API / MCP Fronting

This directory is generated from reviewed fronting mappings. Treat it as implementation profile material plus conformance evidence, not as the agent-facing behavior surface.

Raw MCP tools, API endpoints, database operations, and hybrid backend calls are not the agent-facing surface.
Agents invoke governed ANIP capabilities; generated runtime code builds a backend invocation plan only after semantic inputs, policy, approval posture, and clarification rules are evaluated.

## Files

- `adapter-bindings.json`: reviewed capability-to-backend bindings for implementation work.
- `backend-profile.example.json`: replaceable implementation profile showing which local backend template family can realize each binding.
- `backend-selection.example.json`: deployment-time selection template when a capability has multiple backend realizations.
- `backend-templates/`: generated local backend implementation guidance. Copy or replace these templates inside the generated backend adapter seam; do not depend on shared outbound adapter packages for governed behavior.
- `conformance.json`: static checks proving saved mappings are represented by generated capability metadata.

## Implementation rule

Provider-specific code belongs in the generated backend adapter seam, generated backend template files, or a reviewed custom code bundle. Do not expose raw backend operations directly to agents.
Generated runtimes pass only declared semantic inputs and declared backend input-contract fields into the adapter. If callers need extensibility, model it as an explicit governed input such as `filters`, `fields`, or `adapter_options` with documented bounds and audit handling.

Changing from REST to MCP, dbt to Cube, or Snowflake to Databricks should normally be a backend profile/code change, not a contract change, unless the governed capability behavior, inputs, approval posture, denial rules, clarification rules, or audit semantics change.
