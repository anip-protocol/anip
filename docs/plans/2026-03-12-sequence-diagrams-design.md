# Sequence Diagrams Design

## Goal

Add 5 Mermaid sequence diagrams to ANIP documentation. Each diagram does one job. Prefer clarity over completeness.

## Format

Mermaid `sequenceDiagram` blocks in fenced code blocks. GitHub renders natively. Keep diagrams narrow — avoid packing every field and note. Scannable in under 20 seconds for README diagrams.

## Diagrams

### 1. Native ANIP Invoke Flow

**Actors:** Agent, ANIP Service

**Steps:** Discovery, manifest fetch, token issuance (authenticated), permission check, invoke, response with cost_actual.

**Placement:** README (lean, no signature detail), SPEC.md (same diagram)

**Design constraint:** No branches, no crypto detail. Happy path only. Scannable in 20 seconds.

### 2. Budget Escalation Flow

**Actors:** Agent, ANIP Service, Human Delegator

**Steps:** Agent invokes, gets `budget_exceeded` with `resolution.grantable_by`, escalates to human, human issues new token with higher budget, agent retries, succeeds.

**Placement:** README, SPEC.md

**Design constraint:** This is the "killer feature" diagram. Keep it focused on the escalation loop — don't repeat the full invoke setup.

### 3. v0.2 Signed Trust Flow

**Actors:** Caller, ANIP Service

**Steps:** Fetch discovery/JWKS, fetch signed manifest, issue token (authenticated), invoke with token, server verifies signature + claims.

**Placement:** SPEC.md, docs/trust-model-v0.2.md

**Design constraint:** Separate manifest verification from invoke path visually. Keep it narrow — one column per actor, no nested sub-flows.

### 4. MCP Adapter Flow

**Actors:** MCP Host/Client, MCP Adapter, ANIP Service

**Steps:** MCP tool call arrives, adapter extracts credentials, requests capability token from ANIP service, invokes with signed token, maps response back to MCP tool result.

**Placement:** adapters/mcp-py/README.md, adapters/mcp-ts/README.md

**Design constraint:** Structure should make it obvious that MCP preserves more ANIP semantics than REST/GraphQL adapters. Show credential flow cleanly.

### 5. REST/GraphQL Adapter Flow

**Actors:** HTTP Client, Adapter, ANIP Service

**Steps:** Two explicitly labeled lanes:
- **Preferred: Signed token path** — X-ANIP-Token forwarded directly to ANIP service
- **Convenience: API key path** — X-ANIP-API-Key → adapter requests token → invoke. Note indicating where delegation fidelity is reduced (audit subject is adapter identity, not caller).

**Placement:** adapters/rest-py/README.md, adapters/rest-ts/README.md, adapters/graphql-py/README.md, adapters/graphql-ts/README.md

**Design constraint:** Label the two paths clearly. Keep the API-key path note concise — one line about reduced delegation fidelity.

## Placement Summary

| Diagram | README | SPEC.md | trust-model-v0.2.md | MCP READMEs | REST/GraphQL READMEs |
|---------|--------|---------|---------------------|-------------|----------------------|
| 1. Native invoke | yes | yes | | | |
| 2. Budget escalation | yes | yes | | | |
| 3. Signed trust | | yes | yes | | |
| 4. MCP adapter | | | | yes | |
| 5. REST/GraphQL adapter | | | | | yes |

## Principles

- 5 diagrams, no more
- Each does one job
- Prefer clarity over completeness
- README diagrams are lean — no crypto detail, no branches
- Keep Mermaid narrow — if a diagram gets too wide, it stops helping
- Don't duplicate information that prose already covers well
