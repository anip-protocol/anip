# Fronting Contract and Backend Profile Split

## Decision

ANIP fronting projects should separate governed behavior from backend implementation.

The ANIP Service Definition describes the stable governed capability surface:

- what the capability means
- required and optional semantic inputs
- actor and permission posture
- approval, denial, restriction, clarification, and audit rules
- supported and unsupported outcomes
- result and lineage expectations

Backend details are implementation profile material:

- REST/OpenAPI endpoints
- GraphQL operations
- MCP tools and resources
- SQL, warehouse, dbt, Cube, or other semantic-query bindings
- connection references
- selected raw operation references
- deployment-specific backend selection
- local code templates and custom backend seams

The same ANIP capability contract should normally survive a backend change from REST to MCP, dbt to Cube, or Snowflake to Databricks. A contract change is required only when governed behavior changes.

## Why This Matters

The original adapter-package direction created the wrong adoption pressure. It implied ANIP needed reusable outbound packages for each downstream technology family:

- REST
- GraphQL
- MCP
- SQL
- dbt
- Cube
- Snowflake
- Databricks
- SaaS-specific APIs

That is not the ANIP value. ANIP governs behavior. It should not require users to adopt or maintain ANIP-flavored downstream clients when language-native SDKs and organization-specific client libraries already exist.

The practical model is:

- Generate the ANIP runtime and policy substrate.
- Generate a local backend adapter seam.
- Generate backend implementation profile files and starter templates.
- Let teams customize the backend seam with normal language/framework code.

This lowers the adoption bar and avoids pretending that a thin generic outbound adapter can solve provider-specific semantics, identity, credentials, rate limits, query posture, and operational policy.

## Adapter Package Boundary

Keep inbound/interface adapters:

- `anip-rest`
- `anip-graphql`
- `anip-mcp`

These expose ANIP services outward through standard interfaces while preserving ANIP invocation, auth, error, and metadata semantics.

Outbound/backend adapter packages were removed before release. This includes protocol-shaped helpers, data/semantic-query helpers, and provider-specific helpers.

Examples and generated projects should prefer generated backend templates and custom local implementation code.

## Studio Contract Model

Studio should not expose backend implementation details as if they were the contract.

Product and Developer Design should focus on:

- governed capabilities
- user-visible business intent
- semantic inputs and result expectations
- authority, approval, denial, clarification, restriction, audit, and lineage
- outbound data handling requirements

Studio may capture backend operation evidence and mapping metadata, but that metadata should be framed as an implementation profile:

- useful for code generation
- useful for verifier evidence
- useful for deployment review
- replaceable without changing the contract when behavior stays the same

## Fronting Express Mode

Fronting should be a simplified Studio workflow, not a full generic Studio journey with every page exposed.

Recommended flow:

1. Import or point to backend evidence, such as OpenAPI, GraphQL schema, MCP tool metadata, API docs, or workflow docs.
2. Select candidate backend operations as supply.
3. Curate a small governed ANIP capability surface.
4. Review only the material governance questions: actor scope, approvals, denials, clarification, redaction, outbound boundary, and audit.
5. Generate the ANIP contract and package.
6. Generate local backend templates and implementation profile artifacts.
7. Verify the package.

The raw backend surface should never become the agent-facing surface by default. Raw operations are evidence. ANIP capabilities are the governed contract.

## Generator Behavior

For fronting packages, the generator should emit:

- `anip-service-definition.json`
- language runtime substrate
- local backend adapter seam
- `integration-fronting/adapter-bindings.json`
- `integration-fronting/backend-profile.example.json`
- `integration-fronting/backend-selection.example.json`
- `integration-fronting/backend-templates/*`
- `integration-fronting/conformance.json`

The backend profile and templates are implementation material. They should explain where to customize downstream execution without changing generated ANIP substrate.

Generated backend templates should be starter guidance, not a new shared dependency layer. Teams can replace the generated backend seam with their own SDK, internal client, gateway, MCP client, warehouse client, or semantic-query code.

## Contract Change Rule

Changing downstream implementation does not require a new ANIP contract when all of these remain stable:

- capability id and meaning
- semantic input contract
- output/result semantics
- side-effect posture
- permission and actor behavior
- approval behavior
- denial/restriction behavior
- clarification behavior
- audit and lineage behavior

A new contract or package version is required when any of those governed semantics change.

## Migration Plan

1. Remove unreleased outbound adapter packages.
2. Stop using outbound adapter parity as a release-quality goal.
3. Generate backend profile and backend template artifacts for fronting packages.
4. Update Studio fronting UX to present backend mappings as implementation profile material.
5. Move fronting project creation toward Express Mode.
6. Keep inbound ANIP interface adapters maintained as core integration surfaces.
