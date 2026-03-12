# REST/GraphQL Adapter v0.2 Migration Design

## Goal

Migrate all four REST/GraphQL adapters (rest-py, rest-ts, graphql-py, graphql-ts) from v0.1 declaration mode (adapter-constructed tokens) to v0.2 signed mode (caller-provided credentials). The adapters become stateless protocol bridges that hold no authority.

## Core Principle

Adapters translate protocol surfaces. Callers supply authority. The ANIP service remains the sole issuer, verifier, and enforcer.

## Architecture

### Before (v0.1)

```
Caller --> Adapter (constructs tokens locally) --> ANIP Server
                ^
                |-- root token at startup
                |-- capability token per-request (chained from root)
                |-- adapter is authority holder
```

### After (v0.2)

```
Caller (provides credentials) --> Adapter (forwards credentials) --> ANIP Server
                                       ^
                                       |-- no tokens of its own
                                       |-- no standing authority
                                       |-- pure protocol bridge
```

## Credential Flow

Two modes, token taking precedence over API key:

### 1. Delegation Token (Preferred)

Caller sends `X-ANIP-Token: <signed-anip-token>`. Adapter forwards it directly to `POST /anip/invoke`. No issuance step.

This is the primary conceptual model. The caller owns delegation acquisition and the adapter just translates.

### 2. API Key (Convenience)

Caller sends `X-ANIP-API-Key: <key>`. Adapter requests a short-lived, per-request capability token from `POST /anip/tokens` using that key, scoped narrowly to the specific capability being invoked. Then invokes with the resulting token.

This is an on-ramp for callers who don't want to manage token lifecycle themselves.

### Precedence

1. If `X-ANIP-Token` is present, use the token directly
2. If only `X-ANIP-API-Key` is present, request a capability token
3. If neither is present, return 401

We deliberately avoid `Authorization: Bearer` for ANIP tokens because adapters often sit behind gateways or middleware that already use `Authorization` for their own JWTs. Using a dedicated `X-ANIP-Token` header avoids accidental credential forwarding.

### Token Issuance Rules (API Key Path)

- Scope uses `capability.minimum_scope` — the broadest scope the capability accepts
- Short-lived: per-request, no caching (keep the model simple and conservative)
- One token per invocation
- **Authority note:** This path issues maximally-scoped tokens for the capability. Callers who need fine-grained constraints (budget limits, task-specific purpose) must use the token path with a pre-issued delegation token instead.
- **Audit identity note:** Tokens issued via this path use adapter-specific subjects (e.g., `adapter:anip-rest-adapter`). The audit `subject` field will show the adapter identity, while `root_principal` correctly reflects the human authenticated by the API key. The convenience path does NOT preserve full caller identity in the subject — only `root_principal` traces back to the caller.

## Headers (Same for REST and GraphQL)

| Header | Purpose |
|--------|---------|
| `X-ANIP-Token: <token>` | Signed ANIP delegation token (preferred) |
| `X-ANIP-API-Key: <key>` | ANIP API key for adapter-mediated issuance (convenience, maximum scope) |

GraphQL auth stays entirely in HTTP headers, never in query/mutation arguments.

## Changes Per Adapter

Each adapter (rest-py, rest-ts, graphql-py, graphql-ts) gets identical structural changes:

### Remove

- Root token registration at startup
- Capability token construction (inline dict/object literals)
- `issuer` config field (adapter no longer has an identity)
- Token chain logic (parent references, chain walks)

### Add

- Credential extraction (read `Authorization` / `X-ANIP-API-Key` headers)
- Token-path invocation (forward token directly to `/anip/invoke`)
- API-key-path issuance (request token from `/anip/tokens`, then invoke)
- 401 response for missing credentials

### Update

- Config: remove token-related fields, keep `anip_service_url` and discovery settings
- Error handling: structured ANIP failure forwarding (see below)

### Keep

- Discovery/manifest fetch (already unauthenticated)
- Capability-to-endpoint/resolver translation logic
- Response formatting

## Error Handling

### Structured Failure Forwarding

ANIP failure types must be forwarded faithfully, not collapsed into generic HTTP errors:

| ANIP Failure | REST Response | GraphQL Response |
|-------------|---------------|-----------------|
| `budget_exceeded` | 403 with structured body | Error with `extensions.anip_failure_type` |
| `insufficient_authority` | 403 with structured body | Error with `extensions.anip_failure_type` |
| `purpose_mismatch` | 403 with structured body | Error with `extensions.anip_failure_type` |
| `{"issued": false}` | 403 with issuance denial detail | Error with `extensions.anip_failure_type` |

### Other Error Cases

| Condition | REST | GraphQL |
|-----------|------|---------|
| No credentials | 401 | Error explaining required headers |
| Expired/invalid token | Forward ANIP server's error | Forward as GraphQL error |
| ANIP server unreachable | 502 | Error with upstream failure detail |

### GraphQL Partial-Success

If an ANIP call fails, map it into a GraphQL error that preserves the underlying failure type and detail in the `extensions` field. Do not flatten to generic error messages.

## Config Changes

### Before

```yaml
anip_service_url: "http://localhost:8000"
issuer: "rest-adapter"
scope: ["flights.search", "flights.book"]
```

### After

```yaml
anip_service_url: "http://localhost:8000"
```

No `issuer`, no `scope`, no token config. The adapter discovers capabilities and translates. Scope is determined by the caller's credentials.

## What Does Not Change

- The ANIP server itself (no modifications needed)
- The MCP adapters (already migrated to v0.2)
- The ANIP protocol spec
- Discovery/manifest endpoints

## Future: Managed Mode (Not in Scope)

A future "managed mode" (Option B from design discussion) could add:
- Adapter-level caller authentication middleware
- Principal mapping (caller identity -> ANIP principal)
- Delegated issuance on behalf of authenticated callers

This is explicitly out of scope for v0.2. If added later, it would be an opt-in deployment mode, not the default.
