---
title: Authentication
description: How ANIP handles authentication — API keys, OIDC, and the delegation model.
---

# Authentication

ANIP separates authentication (who are you?) from authorization (what can you do?). This separation is fundamental — it's what enables purpose-bound delegation instead of the "token valid or invalid" model that makes agents vulnerable to confused deputy attacks.

## Authentication flow

Every ANIP request carries a bearer token in the `Authorization` header. The service's `authenticate` function resolves this token to a principal identity:

```
Authorization: Bearer <token>
       │
       ▼
 authenticate(bearer)
       │
       ▼
 Principal identity: "human:demo@example.com"
```

## Three authentication paths

### 1. API keys (simplest)

Map bearer strings directly to principal identities:

```python
service = ANIPService(
    service_id="my-service",
    capabilities=[...],
    authenticate=lambda bearer: {
        "demo-human-key": "human:demo@example.com",
        "agent-key": "agent:triage-bot",
    }.get(bearer),
)
```

The authenticate function returns `None` for unknown tokens, which results in a 401 response.

### 2. OIDC / OAuth2

Validate external JWTs and map claims to ANIP principals:

```bash
OIDC_ISSUER_URL=https://keycloak.example.com/realms/anip
OIDC_AUDIENCE=my-service
```

When configured, the service validates OIDC tokens against the issuer's JWKS and maps claims:
- `email` claim → `human:{email}` principal
- `sub` claim → `oidc:{sub}` principal

API keys continue to work alongside OIDC tokens.

### 3. Delegation tokens (agent path)

The most important path for agents. A human authenticates with an API key or OIDC token, then requests a scoped delegation token for the agent:

```bash
# Human issues a delegation token
curl -X POST https://service.example/anip/tokens \
  -H "Authorization: Bearer demo-human-key" \
  -H "Content-Type: application/json" \
  -d '{
    "scope": ["travel.search"],
    "capability": "search_flights",
    "purpose_parameters": { "task_id": "trip-planning" }
  }'
```

```json
{
  "issued": true,
  "token": "eyJhbGciOiJFZERTQSJ9...",
  "scope": ["travel.search"],
  "expires_at": "2026-03-28T12:00:00Z"
}
```

The agent uses this delegation token for all subsequent calls. The token carries:

- **Who** delegated authority (the human principal)
- **What scope** was granted (only `travel.search`)
- **What capability** it's for
- **Purpose constraints** (the task context)
- **Expiration**

## Why this matters: the confused deputy problem

Traditional APIs give agents a single token with broad access. If the agent is compromised — by prompt injection, supply chain attack, or any other vector — the attacker gets everything the token allows.

ANIP's delegation model limits blast radius:

| Traditional API | ANIP |
|----------------|------|
| Agent has a token | Agent has a **scoped** delegation token |
| Token grants access to everything | Token grants access to **specific capabilities** |
| No purpose constraint | Token carries **purpose parameters** |
| Compromise = full access | Compromise = limited to granted scope |
| Audit shows "token X was used" | Audit shows "human Y delegated scope Z to agent for purpose W" |

### The Clinejection example

A triage bot with a traditional API key has whatever permissions the key grants — potentially including CI operations, package publishing, and shell access.

A triage bot with an ANIP delegation token has:
```json
{
  "scope": ["issues.read", "issues.label", "issues.comment"],
  "capability": "triage_issue",
  "purpose_parameters": { "task": "issue-triage" }
}
```

When a prompt injection tries to make the bot run `npm install`, the interface checks the scope. `ci.install` is not in `["issues.read", "issues.label", "issues.comment"]`. Operation rejected.

## Principal classes

ANIP distinguishes between principal types, which affects what delegation is possible:

| Principal class | Example | Typical role |
|----------------|---------|--------------|
| `human:` | `human:admin@company.com` | Direct authentication, can delegate |
| `agent:` | `agent:triage-bot` | Receives delegated authority |
| `oidc:` | `oidc:sub-12345` | Federated identity |

Some capabilities may require specific principal classes — for example, an admin operation might require a `human:` principal and deny all `agent:` principals regardless of scope.

## Token validation

ANIP delegation tokens are standard JWTs signed by the service's key pair. On every request, the service:

1. Extracts the bearer token from the `Authorization` header
2. Validates the JWT signature against the service's JWKS
3. Checks expiration
4. Extracts the scope and capability from the token claims
5. Validates that the requested operation falls within the granted scope

If validation fails at any step, the service returns a structured failure with the specific reason.

## Next steps

- **[Delegation & Permissions](/docs/protocol/delegation-permissions)** — How scoped delegation and permission discovery work together
- **[Failures](/docs/protocol/failures-cost-audit)** — What happens when auth fails (structured response, not just 401)
