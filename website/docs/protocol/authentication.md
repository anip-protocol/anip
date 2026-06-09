---
title: Authentication
description: How ANIP authenticates callers, issues delegation tokens, and validates approval-capable authority.
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Authentication

ANIP separates authentication from authorization.

Authentication answers: **who is calling?**

Authorization answers: **what governed capability may this caller exercise, for what purpose, under what constraints?**

That separation is central to ANIP. A service can authenticate a human, agent, workflow, or integration through whatever identity system it already uses, then issue a narrow ANIP delegation token that carries the bounded authority the agent is allowed to use.

## The Authentication Model

ANIP has four related auth surfaces:

| Surface | Purpose | Typical credential |
|---------|---------|--------------------|
| Discovery | Let callers find the ANIP service and its contract | Usually none |
| Bootstrap authentication | Convert an existing identity credential into a principal | API key, OIDC/OAuth2 JWT, service secret |
| Delegation token validation | Verify scoped ANIP authority for protected calls | ANIP ES256 JWT from `/anip/tokens` |
| Approval grant validation | Verify a human or policy system approved a pending side effect | Approver bearer token plus signed approval grant |

Do not collapse these into one idea. A bootstrap credential proves identity. A delegation token proves bounded authority. An approval grant proves that a specific approval request was approved under the service's policy.

## Endpoint Auth Posture

ANIP discovery is intentionally reachable before token issuance. Agents need to know what a service is, what it exposes, and how to ask for authority before they can invoke anything.

| Endpoint | Auth posture |
|----------|--------------|
| `GET /.well-known/anip` | No delegation token required |
| `GET /anip/manifest` | No delegation token recommended; gated only when declarations are sensitive |
| `GET /.well-known/jwks.json` | No delegation token required |
| `GET /anip/checkpoints` | No delegation token required when anchored trust is enabled |
| `GET /anip/checkpoints/{id}` | No delegation token required when anchored trust is enabled |
| `POST /anip/tokens` | Bearer bootstrap credential for root issuance, or bearer ANIP JWT for delegated issuance |
| `POST /anip/permissions` | Bearer ANIP JWT |
| `POST /anip/invoke/{capability}` | Bearer ANIP JWT |
| `POST /anip/approval_grants` | Bearer approver credential/token |
| `POST /anip/audit` | Bearer ANIP JWT or service-defined audit credential |

HTTP transports use `Authorization: Bearer <credential>`. Other transports carry the same semantics in their request envelope. For example, ANIP stdio exposes token issuance as `anip.tokens.issue`, and generated MCP surfaces may carry approval continuation metadata through reserved parameters, but the authority model stays the same.

## Authentication Flow

```text
Caller credential
    |
    v
Bootstrap auth hook or ANIP JWT verifier
    |
    v
Resolved principal + caller class
    |
    v
Authorization checks: scope, capability, purpose, budget, approval, policy
```

The service first resolves identity or token authority. It then applies the capability contract and runtime policy. A valid token alone is not enough to run an action if scope, purpose, budget, approval, or side-effect policy does not allow it.

## Bootstrap Authentication

Bootstrap authentication is how a caller obtains a root ANIP delegation token. It is deliberately pluggable because organizations already have identity systems.

The portable runtime contract is:

- The runtime must support a synchronous `authenticate(bearer)` hook.
- The hook returns a principal string such as `human:demo@example.com`, `agent:triage-bot`, or `oidc:sub-12345`.
- The hook returns `null`, `None`, or `nil` for unknown credentials.
- Runtimes may also support async auth hooks when the language/runtime model supports them, but they must await them correctly.

### API Keys

API keys are the simplest bootstrap path. They are useful for local demos, internal services, and controlled automation.

<Tabs groupId="language" queryString>
<TabItem value="python" label="Python" default>

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

</TabItem>
<TabItem value="typescript" label="TypeScript">

```typescript
const service = createANIPService({
  serviceId: "my-service",
  capabilities: [...],
  authenticate: (bearer) => ({
    "demo-human-key": "human:demo@example.com",
    "agent-key": "agent:triage-bot",
  })[bearer] ?? null,
});
```

</TabItem>
<TabItem value="go" label="Go">

```go
svc, _ := service.New(service.Config{
    ServiceID: "my-service",
    Capabilities: capabilities,
    Authenticate: func(bearer string) *string {
        keys := map[string]string{
            "demo-human-key": "human:demo@example.com",
            "agent-key":      "agent:triage-bot",
        }
        if p, ok := keys[bearer]; ok { return &p }
        return nil
    },
})
```

</TabItem>
<TabItem value="java" label="Java">

```java
new ANIPService(new ServiceConfig()
    .setAuthenticate(bearer -> {
        var keys = Map.of(
            "demo-human-key", "human:demo@example.com",
            "agent-key", "agent:triage-bot"
        );
        return Optional.ofNullable(keys.get(bearer));
    }));
```

</TabItem>
<TabItem value="csharp" label="C#">

```csharp
var service = new AnipService(new ServiceConfig {
    Authenticate = bearer => {
        var keys = new Dictionary<string, string> {
            ["demo-human-key"] = "human:demo@example.com",
            ["agent-key"] = "agent:triage-bot",
        };
        return keys.TryGetValue(bearer, out var p) ? p : null;
    }
});
```

</TabItem>
</Tabs>

Missing or invalid bootstrap credentials fail at the transport boundary, normally with a 401 response containing an ANIP failure body.

### OIDC / OAuth2

Production services usually validate an external identity token and map claims into ANIP principal names.

```bash
OIDC_ISSUER_URL=https://keycloak.example.com/realms/anip
OIDC_AUDIENCE=my-service
```

Common mappings:

| OIDC claim | ANIP principal |
|------------|----------------|
| `email` | `human:{email}` |
| `sub` | `oidc:{sub}` |
| service-account subject | `agent:{name}` or `service:{name}` |

OIDC authenticates the caller. ANIP still issues its own delegation token so the service can bind capability, scope, purpose, budget, caller class, and expiration to the agent's work.

## Delegation Tokens

Delegation tokens are the normal agent path.

A caller authenticates with a bootstrap credential, then requests a scoped ANIP token:

```bash
curl -X POST https://service.example/anip/tokens \
  -H "Authorization: Bearer demo-human-key" \
  -H "Content-Type: application/json" \
  -d '{
    "scope": ["travel.search"],
    "capability": "search_flights",
    "purpose_parameters": { "task_id": "trip-planning" },
    "caller_class": "automated_agent",
    "budget": { "currency": "USD", "max_amount": 500 }
  }'
```

```json
{
  "token_id": "tok_root_001",
  "token": "eyJhbGciOiJFUzI1NiIs...",
  "expires": "2026-06-15T14:00:00Z",
  "task_id": "trip-planning",
  "budget": {
    "currency": "USD",
    "max_amount": 500
  }
}
```

The returned `token` is a service-issued ES256 JWT. The returned `token_id` is the stable handle used when issuing child tokens.

Delegation token authority includes:

| Token field | Why it matters |
|-------------|----------------|
| `scope` | What permission strings the token carries |
| `capability` | Which capability the token is pre-bound to, when present |
| `purpose_parameters` | Task context such as `task_id` |
| `constraints.budget` | Maximum authorized cost or spend envelope |
| `caller_class` | Disclosure and policy classification such as `automated_agent`, `internal`, or `partner` |
| `expires` | Time bound for authority |
| `parent_token_id` | Delegation lineage for child tokens |

### Root vs Delegated Issuance

The same `/anip/tokens` endpoint supports root and delegated issuance.

| Path | Auth credential | `parent_token` | Subject |
|------|-----------------|----------------|---------|
| Root issuance | Bootstrap credential | Omitted | Defaults to authenticated principal unless supplied |
| Delegated issuance | Existing ANIP JWT | Token ID string of the parent | Explicit delegated subject |

`parent_token` is a token ID string, not a JWT. The service looks up the parent token in storage, then verifies that the child token narrows rather than widens parent authority.

```json
{
  "scope": ["travel.book"],
  "subject": "agent:booking-worker",
  "parent_token": "tok_root_001",
  "capability": "book_flight",
  "ttl_hours": 1,
  "budget": {
    "currency": "USD",
    "max_amount": 200
  }
}
```

Runtimes expose convenience helpers for both paths:

| Helper | Use |
|--------|-----|
| `issueCapabilityToken()` | Root token pre-bound to a capability |
| `issueDelegatedCapabilityToken()` | Child token pre-bound to a capability and parent token ID |

Both helpers require explicit scope. Capability names and scope strings are not the same thing, so runtimes must not infer scope from capability name.

## Token Validation

ANIP delegation tokens are standard JWTs signed by the service's ES256 key pair. Public keys are exposed through `/.well-known/jwks.json`.

For protected calls, the service validates:

1. The bearer token is present.
2. The JWT signature verifies against the service JWKS.
3. The token exists in service storage and has not been revoked or tampered with.
4. The token is not expired.
5. The token scope covers the requested capability's `minimum_scope`.
6. The token capability binding matches the requested capability when a binding is present.
7. Purpose, task, budget, delegation-depth, and concurrency constraints are satisfied.
8. Any required approval grant is valid before execution continues.

Failures are intentionally structured. Missing or invalid transport credentials may return HTTP 401. Valid authentication with insufficient authority should return an ANIP failure object such as `scope_insufficient`, `invalid_token`, `token_expired`, `approval_required`, or `approval_grant_invalid`, with recovery guidance.

## Approval Grants

Some capabilities are callable only after an explicit approval step. In that flow, the service first returns `approval_required` and records an approval request. A human approver, admin UI, queue worker, or policy workflow then issues an approval grant.

The canonical HTTP surface is:

```bash
curl -X POST https://service.example/anip/approval_grants \
  -H "Authorization: Bearer approver-token" \
  -H "Content-Type: application/json" \
  -d '{
    "approval_request_id": "apr_8a7c",
    "grant_type": "one_time",
    "expires_in_seconds": 900,
    "max_uses": 1
  }'
```

Security-relevant behavior:

- The approver is authenticated before request-specific authority is checked.
- The service loads the approval request before validating approver scope.
- Approver authority is checked against the loaded request's capability.
- The grant copies capability, scope, requester, and digests from the stored approval request, not from caller-controlled request fields.
- Request approval and grant insertion must be atomic so two approvers cannot issue competing grants for the same request.
- Continuation invocation validates the signed grant before performing the side effect.

Approval grants are not a replacement for delegation tokens. They are an additional control for specific side effects.

## Principal Classes

ANIP principal names are intentionally simple strings, but runtimes and services commonly distinguish principal classes.

| Principal class | Example | Typical role |
|-----------------|---------|--------------|
| `human:` | `human:admin@company.com` | Direct user, approver, delegator |
| `agent:` | `agent:triage-bot` | Automated caller using delegated authority |
| `service:` | `service:billing-worker` | Service-to-service automation |
| `oidc:` | `oidc:sub-12345` | Federated identity that has not been mapped to a human or service label |

Capabilities may require specific principal classes. For example, a destructive admin operation can require a `human:` approver even if an `agent:` token has related read scopes.

`caller_class` is separate from the principal prefix. It is an issuer-supplied classification used for disclosure policy and agent-facing response shaping. A service may reveal different metadata to `internal`, `partner`, `automated_agent`, and `default` caller classes.

## Why This Matters

Traditional APIs often give agents broad credentials and rely on the agent application to behave. That creates a confused deputy risk: if the agent is manipulated, the attacker gets whatever the credential can do.

ANIP reduces that blast radius:

| Traditional API posture | ANIP posture |
|-------------------------|--------------|
| Agent has a broad token | Agent has a scoped delegation token |
| Token grants endpoint access | Token grants bounded capability authority |
| Purpose lives in app code or prompt text | Purpose is carried in the token and audit trail |
| Approval is a workflow convention | Approval is a signed grant tied to a stored request |
| Audit shows a credential was used | Audit shows who delegated what, to whom, for what task |
| Recovery is usually HTTP status-specific | Recovery is part of the ANIP failure contract |

Example delegated authority:

```json
{
  "scope": ["issues.read", "issues.label", "issues.comment"],
  "capability": "triage_issue",
  "purpose_parameters": { "task_id": "issue-triage" },
  "caller_class": "automated_agent"
}
```

If a prompt injection asks the agent to publish a package or run a CI deploy, the service checks the requested capability against the token. The issue-triage token does not carry that authority.

## Next Steps

- [Delegation & Permissions](/docs/protocol/delegation-permissions) — How scoped authority, permission discovery, and policy evaluation fit together.
- [Capabilities](/docs/protocol/capabilities) — How capability declarations define inputs, side effects, approval posture, and resolution behavior.
- [Failures, Cost & Audit](/docs/protocol/failures-cost-audit) — How services return recoverable failures and record execution.
- [Protocol Reference](/docs/protocol/reference) — The canonical endpoint and wire-format reference.
