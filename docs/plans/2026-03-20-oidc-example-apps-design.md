# OIDC Integration for Example Apps Design

**Goal:** Add OIDC/OAuth2 authentication support to both example apps so ANIP services can sit behind enterprise identity providers like Keycloak, using standard OIDC token validation.

**Architecture:** A small OIDC validation module in each example app (not in the SDK). The existing `authenticate` callback gains an OIDC path alongside the API key map. OIDC configuration is env-driven. No ANIP core or SDK changes.

**Tech Stack:** TypeScript (`jose` for JWT/JWKS), Python (`PyJWT` + `httpx` for JWKS fetching)

---

## Scope

**In scope:**
- OIDC JWT validation in the example apps' `authenticate` callback
- JWKS fetching with caching and key rotation support
- Issuer, audience, expiry validation
- Claim-to-principal mapping
- Keycloak documented as the reference walkthrough

**Not in scope:**
- SDK auth helper packages (`@anip-dev/auth-oidc` or similar)
- ANIP core or service changes
- Provider-specific integrations (Okta, Auth0, Cognito)
- Docker Compose for Keycloak

## Configuration

Env-driven, optional. When `OIDC_ISSUER_URL` is not set, apps behave exactly as today.

| Variable | Required | Description |
|----------|----------|-------------|
| `OIDC_ISSUER_URL` | Yes (to enable OIDC) | Issuer URL, e.g., `https://keycloak.example.com/realms/anip` |
| `OIDC_AUDIENCE` | No | Expected `aud` claim. Defaults to service ID. |
| `OIDC_JWKS_URL` | No | Override JWKS endpoint. Defaults to discovery via `{issuer}/.well-known/openid-configuration` → `jwks_uri`. |

**Discovery flow:** When only `OIDC_ISSUER_URL` is set, the module fetches `{issuer}/.well-known/openid-configuration` to resolve `jwks_uri`. `OIDC_JWKS_URL` is only an override for providers that don't support standard discovery.

## Auth Flow

The `authenticate` callback handles bootstrap auth only. ANIP delegation JWT resolution is the service's separate concern.

```
authenticate(bearer) callback:
  1. Try API key map → return principal or continue
  2. If OIDC configured, try OIDC JWT validation → return principal or continue
  3. Return null

Service (separately):
  4. If authenticate returned null, try ANIP delegation JWT resolution
```

The callback never inspects ANIP JWTs. It returns `null` for anything it doesn't recognize, and the service handles the rest.

## OIDC Validation Logic

A local module in each example app (`oidc.ts` / `oidc.py`).

### JWKS Management
- Fetch JWKS from the provider's `jwks_uri` (resolved via discovery or override)
- Cache keys in memory
- On `kid` cache miss, refresh JWKS once before failing (handles key rotation)
- No TTL-based refresh — only refresh on miss

### Token Validation
- Verify JWT signature against provider's public keys (RS256 — standard OIDC)
- Validate `iss` matches `OIDC_ISSUER_URL`
- Validate `aud` contains `OIDC_AUDIENCE`
- Validate `exp` is in the future
- Reject if any check fails (return `null`)

### Claim-to-Principal Mapping

Maps external OIDC claims to ANIP principal identifiers:

- If token has `email` claim → `"human:{email}"`
- Else if token has `preferred_username` → `"human:{preferred_username}"`
- Else use `sub` claim → `"oidc:{sub}"`

This mapping is **deployment policy, not protocol meaning**. The `human:` and `oidc:` prefixes are conventions for the example apps, not ANIP protocol requirements. Real deployments should define their own mapping.

## File Structure

### TypeScript

```
examples/anip-ts/src/
├── app.ts              # modified — authenticate gains OIDC path
└── oidc.ts             # NEW — validateOidcToken(), JWKS cache
```

### Python

```
examples/anip/
├── app.py              # modified — authenticate gains OIDC path
└── oidc.py             # NEW — validate_oidc_token(), JWKS cache
```

## Module API

### TypeScript (`oidc.ts`)

```typescript
interface OidcConfig {
  issuerUrl: string;
  audience: string;
  jwksUrl?: string;  // override, otherwise discovered
}

/**
 * Create an OIDC token validator.
 * Returns a function that validates a bearer token and returns a principal or null.
 */
function createOidcValidator(config: OidcConfig): (bearer: string) => Promise<string | null>
```

### Python (`oidc.py`)

```python
class OidcValidator:
    def __init__(self, issuer_url: str, audience: str, jwks_url: str | None = None): ...
    def validate(self, bearer: str) -> str | None: ...  # sync — matches ANIPService authenticate callback
```

### Usage in `app.ts` / `app.py`

```typescript
// TypeScript
const serviceId = process.env.ANIP_SERVICE_ID ?? "anip-flight-service";

const oidcValidator = process.env.OIDC_ISSUER_URL
  ? createOidcValidator({
      issuerUrl: process.env.OIDC_ISSUER_URL,
      audience: process.env.OIDC_AUDIENCE ?? serviceId,
    })
  : null;

const service = createANIPService({
  // ...
  authenticate: async (bearer) => {
    // 1. API key
    const principal = API_KEYS[bearer];
    if (principal) return principal;
    // 2. OIDC (if configured)
    if (oidcValidator) return oidcValidator(bearer);
    // 3. Not recognized
    return null;
  },
});
```

## Testing

Tests use mocked JWKS endpoints — no real Keycloak dependency.

### Test cases:

- Valid OIDC token with `email` claim → returns `"human:{email}"`
- Valid OIDC token with `preferred_username` → returns `"human:{username}"`
- Valid OIDC token with only `sub` → returns `"oidc:{sub}"`
- Expired token → returns `null`
- Wrong issuer → returns `null`
- Wrong audience → returns `null`
- Invalid signature → returns `null`
- Unknown `kid` triggers JWKS refresh → validates after refresh
- JWKS fetch failure → returns `null` (graceful degradation)
- OIDC not configured → callback uses API keys only

### TypeScript tests

Vitest with mocked HTTP (or a local JWKS server). Generate test JWTs with `jose`.

### Python tests

Pytest with mocked httpx responses. Generate test JWTs with `PyJWT`.

## Documentation

Each example app's README gains an "OIDC Integration" section:

1. How to configure env vars
2. Keycloak setup walkthrough (create realm, client, user)
3. How principal mapping works (deployment policy, not protocol)
4. How OIDC auth coexists with API keys and ANIP delegation tokens
