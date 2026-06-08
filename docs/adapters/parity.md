# ANIP Adapter Package Boundary

This document replaces the earlier outbound adapter parity matrix.

## Current Direction

ANIP should not require a maintained outbound adapter package for every downstream technology.

The durable ANIP value is the governed behavior contract:

- capability semantics
- semantic inputs
- authority and actor policy
- approval requirements
- denial and restriction behavior
- clarification behavior
- audit and lineage
- generated/verifier-backed conformance

Downstream execution is implementation material. A generated ANIP service may call REST, GraphQL, MCP, dbt, Cube, Snowflake, Databricks, a provider SDK, an internal gateway, or handwritten code without changing ANIP semantics.

## Keep Maintained

Maintain inbound/interface packages that expose ANIP services through common protocols:

| Package family | Purpose |
| --- | --- |
| `anip-rest` | Expose ANIP invocation/discovery/error semantics through REST. |
| `anip-graphql` | Expose ANIP invocation/discovery/error semantics through GraphQL. |
| `anip-mcp` | Expose ANIP capabilities to MCP clients while preserving ANIP governance semantics. |

These are ANIP surface adapters. They help clients call ANIP services.

## Removed Before Release

The unreleased outbound/backend helper packages have been removed:

| Family | Removed helper shape | New default |
| --- | --- | --- |
| REST/OpenAPI | Outbound REST helper packages | Generated backend seam plus local native API template. |
| GraphQL | Outbound GraphQL helper packages | Generated backend seam plus local GraphQL template. |
| MCP | Outbound MCP helper packages | Generated backend seam plus local MCP template. |
| SQL/Warehouse | Outbound SQL and warehouse helper packages | Generated backend seam plus local SQL/warehouse template. |
| Semantic query | Outbound semantic-query helper packages | Generated backend seam plus local semantic-query template. |
| SaaS providers | Outbound provider-specific helper packages | Generated backend seam plus provider SDK or organization client code. |

They were removed before public release, so examples and generated projects should not ask users to install them.

## Generator Rule

Generated fronting services include local implementation material instead of requiring shared outbound adapter packages:

- `integration-fronting/adapter-bindings.json`
- `integration-fronting/backend-profile.example.json`
- `integration-fronting/backend-selection.example.json`
- `integration-fronting/backend-templates/*`
- language-specific backend adapter seam

The generated backend seam is where teams use normal language-native SDKs, HTTP clients, MCP clients, warehouse clients, or internal libraries.

## Contract Rule

Changing downstream implementation does not require a contract change when governed behavior stays the same.

Examples:

- REST to MCP for Jira can keep the same `jira.prepare_bug_ticket` contract.
- dbt to Cube for metrics can keep the same forecast-summary contract.
- Snowflake to Databricks can keep the same bounded-query capability contract.

Update the ANIP contract only when capability meaning, input semantics, output semantics, side-effect posture, authority, approval, denial, clarification, restriction, audit, or lineage behavior changes.
