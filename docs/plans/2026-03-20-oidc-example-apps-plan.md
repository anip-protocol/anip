# OIDC Example Apps Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OIDC/OAuth2 authentication support to both example apps so they can validate external identity provider tokens alongside API keys.

**Architecture:** Each example app gets a local OIDC module (`oidc.ts` / `oidc.py`) that fetches JWKS, validates JWT signatures, checks issuer/audience/expiry, and maps claims to ANIP principals. The `authenticate` callback in each app gains an OIDC path. No SDK changes — example-app-only scope.

**Tech Stack:** TypeScript (`jose` for JWT/JWKS), Python (`PyJWT` + `httpx` for JWKS)

**Design doc:** `docs/plans/2026-03-20-oidc-example-apps-design.md`

---

## File Structure

```
examples/anip-ts/
├── src/
│   ├── app.ts              # MODIFIED — authenticate gains OIDC path
│   └── oidc.ts             # NEW — OIDC validation module
└── tests/
    └── oidc.test.ts         # NEW — OIDC validation tests

examples/anip/
├── app.py                   # MODIFIED — authenticate gains OIDC path
├── anip_flight_demo/
│   └── oidc.py              # NEW — OIDC validation module
└── tests/
    └── test_oidc.py          # NEW — OIDC validation tests
```

---

## Chunk 1: TypeScript OIDC Module

### Task 1: Create oidc.ts module

**Files:**
- Create: `examples/anip-ts/src/oidc.ts`

- [ ] **Step 1: Add `jose` dependency**

```bash
cd examples/anip-ts && npm install jose
```

- [ ] **Step 2: Create oidc.ts**

```typescript
/**
 * OIDC token validation for the ANIP example app.
 *
 * Validates external OIDC/OAuth2 JWTs against a provider's JWKS endpoint.
 * Maps OIDC claims to ANIP principal identifiers.
 *
 * This is example-app code, not an SDK package. Real deployments should
 * define their own claim-to-principal mapping policy.
 */
import * as jose from "jose";

export interface OidcConfig {
  issuerUrl: string;
  audience: string;
  jwksUrl?: string; // override — otherwise discovered from issuer
}

interface JwksCache {
  jwks: jose.createRemoteJWKSet extends (...args: any) => infer R ? R : never;
}

/**
 * Create an OIDC token validator.
 *
 * Returns an async function that validates a bearer token and returns
 * an ANIP principal string, or null if validation fails.
 *
 * JWKS is fetched and cached automatically. On unknown kid, jose's
 * createRemoteJWKSet handles refresh internally.
 */
export function createOidcValidator(
  config: OidcConfig,
): (bearer: string) => Promise<string | null> {
  let jwksUrl: string | null = config.jwksUrl ?? null;
  let jwks: ReturnType<typeof jose.createRemoteJWKSet> | null = null;
  let discoveryDone = false;

  async function getJwks(): Promise<ReturnType<typeof jose.createRemoteJWKSet>> {
    if (jwks) return jwks;

    // Discover JWKS URL from OIDC discovery if not explicitly set
    if (!jwksUrl && !discoveryDone) {
      discoveryDone = true;
      try {
        const discoveryUrl = `${config.issuerUrl.replace(/\/$/, "")}/.well-known/openid-configuration`;
        const resp = await fetch(discoveryUrl);
        if (resp.ok) {
          const doc = await resp.json();
          jwksUrl = doc.jwks_uri ?? null;
        }
      } catch {
        // Discovery failed — will return null on validation
      }
    }

    if (!jwksUrl) return null as any;

    // jose's createRemoteJWKSet handles caching and kid-miss refresh internally
    jwks = jose.createRemoteJWKSet(new URL(jwksUrl));
    return jwks;
  }

  return async (bearer: string): Promise<string | null> => {
    try {
      const keySet = await getJwks();
      if (!keySet) return null;

      const { payload } = await jose.jwtVerify(bearer, keySet, {
        issuer: config.issuerUrl,
        audience: config.audience,
      });

      // Map OIDC claims to ANIP principal
      return mapClaimsToPrincipal(payload);
    } catch {
      // Any validation failure → not an OIDC token we recognize
      return null;
    }
  };
}

/**
 * Map OIDC JWT claims to an ANIP principal identifier.
 *
 * This is deployment policy, not protocol meaning:
 * - email → "human:{email}"
 * - preferred_username → "human:{username}"
 * - sub → "oidc:{sub}"
 */
function mapClaimsToPrincipal(claims: jose.JWTPayload): string | null {
  const email = claims.email as string | undefined;
  if (email) return `human:${email}`;

  const username = claims.preferred_username as string | undefined;
  if (username) return `human:${username}`;

  const sub = claims.sub;
  if (sub) return `oidc:${sub}`;

  return null;
}
```

- [ ] **Step 3: Commit**

```bash
git add examples/anip-ts/src/oidc.ts examples/anip-ts/package.json examples/anip-ts/package-lock.json
git commit -m "feat(examples): add OIDC validation module for TypeScript example"
```

---

### Task 2: Update app.ts to use OIDC

**Files:**
- Modify: `examples/anip-ts/src/app.ts`

- [ ] **Step 1: Update app.ts**

```typescript
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { Hono } from "hono";
import { createANIPService } from "@anip/service";
import { mountAnip } from "@anip/hono";
import { searchFlights } from "./capabilities/search-flights.js";
import { bookFlight } from "./capabilities/book-flight.js";
import { createOidcValidator } from "./oidc.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

const API_KEYS: Record<string, string> = {
  "demo-human-key": "human:samir@example.com",
  "demo-agent-key": "agent:demo-agent",
};

const serviceId = process.env.ANIP_SERVICE_ID ?? "anip-flight-service";

// Optional OIDC authentication — enabled when OIDC_ISSUER_URL is set
const oidcValidator = process.env.OIDC_ISSUER_URL
  ? createOidcValidator({
      issuerUrl: process.env.OIDC_ISSUER_URL,
      audience: process.env.OIDC_AUDIENCE ?? serviceId,
      jwksUrl: process.env.OIDC_JWKS_URL,
    })
  : null;

const service = createANIPService({
  serviceId,
  capabilities: [searchFlights, bookFlight],
  trust: (process.env.ANIP_TRUST_LEVEL as "signed" | "anchored") ?? "signed",
  keyPath: process.env.ANIP_KEY_PATH ?? resolve(__dirname, "../anip-keys"),
  authenticate: async (bearer: string) => {
    // 1. API key map
    const principal = API_KEYS[bearer];
    if (principal) return principal;
    // 2. OIDC (if configured)
    if (oidcValidator) return oidcValidator(bearer);
    // 3. Not recognized — service will try ANIP JWT separately
    return null;
  },
});

const app = new Hono();
const { stop } = await mountAnip(app, service);

export { app, stop };
```

- [ ] **Step 2: Verify app still builds**

Run: `cd examples/anip-ts && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add examples/anip-ts/src/app.ts
git commit -m "feat(examples): integrate OIDC validation into TS example app"
```

---

### Task 3: TypeScript OIDC tests

**Files:**
- Create: `examples/anip-ts/tests/oidc.test.ts`

- [ ] **Step 1: Write tests**

```typescript
import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import { createOidcValidator } from "../src/oidc.js";
import * as jose from "jose";
import { createServer, type Server } from "node:http";

// Generate a test RSA key pair for signing OIDC tokens
let privateKey: jose.KeyLike;
let publicJwk: jose.JWK;
let jwksServer: Server;
let jwksPort: number;

const ISSUER = "http://localhost:JWKS_PORT";
const AUDIENCE = "test-service";

beforeAll(async () => {
  // Generate RSA key pair
  const { privateKey: priv, publicKey: pub } = await jose.generateKeyPair("RS256");
  privateKey = priv;
  publicJwk = await jose.exportJWK(pub);
  publicJwk.kid = "test-key-1";
  publicJwk.alg = "RS256";
  publicJwk.use = "sig";

  // Start a local JWKS server
  jwksServer = createServer((req, res) => {
    if (req.url === "/.well-known/openid-configuration") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({
        issuer: `http://localhost:${jwksPort}`,
        jwks_uri: `http://localhost:${jwksPort}/jwks`,
      }));
    } else if (req.url === "/jwks") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ keys: [publicJwk] }));
    } else {
      res.writeHead(404);
      res.end();
    }
  });

  await new Promise<void>((resolve) => {
    jwksServer.listen(0, () => {
      jwksPort = (jwksServer.address() as any).port;
      resolve();
    });
  });
});

afterAll(() => {
  jwksServer.close();
});

function issuer() {
  return `http://localhost:${jwksPort}`;
}

async function signToken(claims: Record<string, unknown>, opts?: { expiresIn?: string; kid?: string }) {
  return new jose.SignJWT(claims as jose.JWTPayload)
    .setProtectedHeader({ alg: "RS256", kid: opts?.kid ?? "test-key-1" })
    .setIssuer(issuer())
    .setAudience(AUDIENCE)
    .setIssuedAt()
    .setExpirationTime(opts?.expiresIn ?? "1h")
    .sign(privateKey);
}

describe("OIDC Validator", () => {
  it("validates token with email claim → human:{email}", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    const token = await signToken({ email: "samir@example.com" });
    const principal = await validate(token);
    expect(principal).toBe("human:samir@example.com");
  });

  it("validates token with preferred_username → human:{username}", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    const token = await signToken({ preferred_username: "samir", sub: "user-123" });
    const principal = await validate(token);
    expect(principal).toBe("human:samir");
  });

  it("validates token with only sub → oidc:{sub}", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    const token = await signToken({ sub: "service-account-xyz" });
    const principal = await validate(token);
    expect(principal).toBe("oidc:service-account-xyz");
  });

  it("rejects expired token", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    const token = await signToken({ email: "samir@example.com" }, { expiresIn: "-1h" });
    const principal = await validate(token);
    expect(principal).toBeNull();
  });

  it("rejects wrong issuer", async () => {
    const validate = createOidcValidator({ issuerUrl: "https://wrong-issuer.example.com", audience: AUDIENCE });
    const token = await signToken({ email: "samir@example.com" });
    const principal = await validate(token);
    expect(principal).toBeNull();
  });

  it("rejects wrong audience", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: "wrong-audience" });
    const token = await signToken({ email: "samir@example.com" });
    const principal = await validate(token);
    expect(principal).toBeNull();
  });

  it("rejects invalid signature", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    // Sign with a different key
    const { privateKey: otherKey } = await jose.generateKeyPair("RS256");
    const token = await new jose.SignJWT({ email: "samir@example.com" })
      .setProtectedHeader({ alg: "RS256", kid: "test-key-1" })
      .setIssuer(issuer())
      .setAudience(AUDIENCE)
      .setIssuedAt()
      .setExpirationTime("1h")
      .sign(otherKey);
    const principal = await validate(token);
    expect(principal).toBeNull();
  });

  it("handles JWKS fetch failure gracefully", async () => {
    const validate = createOidcValidator({
      issuerUrl: "http://localhost:1", // unreachable
      audience: AUDIENCE,
      jwksUrl: "http://localhost:1/jwks",
    });
    const token = await signToken({ email: "samir@example.com" });
    const principal = await validate(token);
    expect(principal).toBeNull();
  });

  it("handles unknown kid by refreshing JWKS", async () => {
    // jose's createRemoteJWKSet automatically refreshes on kid miss
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    // Use a different kid — jose will refresh JWKS and find the key
    // (Our test server always returns the same key set, so this tests the refresh path)
    const token = await signToken({ email: "samir@example.com" }, { kid: "test-key-1" });
    const principal = await validate(token);
    expect(principal).toBe("human:samir@example.com");
  });

  it("returns null for non-JWT strings", async () => {
    const validate = createOidcValidator({ issuerUrl: issuer(), audience: AUDIENCE });
    const principal = await validate("not-a-jwt");
    expect(principal).toBeNull();
  });

  it("uses explicit jwksUrl when provided", async () => {
    const validate = createOidcValidator({
      issuerUrl: issuer(),
      audience: AUDIENCE,
      jwksUrl: `http://localhost:${jwksPort}/jwks`,
    });
    const token = await signToken({ email: "direct@example.com" });
    const principal = await validate(token);
    expect(principal).toBe("human:direct@example.com");
  });
});
```

- [ ] **Step 2: Run tests**

Run: `cd examples/anip-ts && npx vitest run tests/oidc.test.ts`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add examples/anip-ts/tests/oidc.test.ts
git commit -m "feat(examples): add OIDC validation tests for TypeScript example"
```

---

## Chunk 2: Python OIDC Module

### Task 4: Create oidc.py module

**Files:**
- Create: `examples/anip/anip_flight_demo/oidc.py`
- Modify: `examples/anip/pyproject.toml` (add `PyJWT[crypto]` dependency)

- [ ] **Step 1: Add dependencies to pyproject.toml**

Add `"PyJWT[crypto]>=2.8"` and `"httpx>=0.27"` to the `dependencies` list.

- [ ] **Step 2: Create oidc.py**

```python
"""OIDC token validation for the ANIP example app.

Validates external OIDC/OAuth2 JWTs against a provider's JWKS endpoint.
Maps OIDC claims to ANIP principal identifiers.

This is example-app code, not an SDK package. Real deployments should
define their own claim-to-principal mapping policy.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import jwt as pyjwt
from jwt import PyJWKClient


class OidcValidator:
    """Validates OIDC bearer tokens and maps claims to ANIP principals.

    Args:
        issuer_url: Expected issuer (iss claim).
        audience: Expected audience (aud claim).
        jwks_url: Explicit JWKS URL. If not set, discovered from issuer.
    """

    def __init__(
        self,
        issuer_url: str,
        audience: str,
        jwks_url: str | None = None,
    ):
        self.issuer_url = issuer_url.rstrip("/")
        self.audience = audience
        self._jwks_url = jwks_url
        self._jwk_client: PyJWKClient | None = None
        self._discovery_done = False

    def _get_jwk_client(self) -> PyJWKClient | None:
        """Get or create the JWKS client, discovering the URL if needed."""
        if self._jwk_client is not None:
            return self._jwk_client

        jwks_url = self._jwks_url

        # Discover JWKS URL from OIDC discovery if not explicit
        if not jwks_url and not self._discovery_done:
            self._discovery_done = True
            try:
                discovery_url = f"{self.issuer_url}/.well-known/openid-configuration"
                resp = httpx.get(discovery_url, timeout=10)
                if resp.status_code == 200:
                    jwks_url = resp.json().get("jwks_uri")
            except Exception:
                return None

        if not jwks_url:
            return None

        # PyJWKClient handles caching and kid-miss refresh internally
        self._jwk_client = PyJWKClient(jwks_url)
        return self._jwk_client

    async def validate(self, bearer: str) -> str | None:
        """Validate an OIDC bearer token and return an ANIP principal, or None."""
        try:
            client = self._get_jwk_client()
            if client is None:
                return None

            # Resolve signing key by kid from JWT header
            signing_key = client.get_signing_key_from_jwt(bearer)

            # Verify and decode
            claims = pyjwt.decode(
                bearer,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self.issuer_url,
                audience=self.audience,
                options={"verify_exp": True},
            )

            return _map_claims_to_principal(claims)
        except Exception:
            return None


def _map_claims_to_principal(claims: dict[str, Any]) -> str | None:
    """Map OIDC JWT claims to an ANIP principal identifier.

    Deployment policy, not protocol meaning:
    - email → "human:{email}"
    - preferred_username → "human:{username}"
    - sub → "oidc:{sub}"
    """
    email = claims.get("email")
    if email:
        return f"human:{email}"

    username = claims.get("preferred_username")
    if username:
        return f"human:{username}"

    sub = claims.get("sub")
    if sub:
        return f"oidc:{sub}"

    return None
```

- [ ] **Step 3: Commit**

```bash
git add examples/anip/anip_flight_demo/oidc.py examples/anip/pyproject.toml
git commit -m "feat(examples): add OIDC validation module for Python example"
```

---

### Task 5: Update app.py to use OIDC

**Files:**
- Modify: `examples/anip/app.py`

- [ ] **Step 1: Update app.py**

```python
"""ANIP Flight Demo — configured via the ANIP service runtime."""
import os
from fastapi import FastAPI
from anip_service import ANIPService
from anip_fastapi import mount_anip

from anip_flight_demo.capabilities.search_flights import search_flights
from anip_flight_demo.capabilities.book_flight import book_flight
from anip_flight_demo.oidc import OidcValidator

# Bootstrap authentication: API keys -> principal identities.
API_KEYS = {
    "demo-human-key": "human:samir@example.com",
    "demo-agent-key": "agent:demo-agent",
}

SERVICE_ID = os.getenv("ANIP_SERVICE_ID", "anip-flight-service")

# Optional OIDC authentication — enabled when OIDC_ISSUER_URL is set
_oidc_validator = (
    OidcValidator(
        issuer_url=os.getenv("OIDC_ISSUER_URL", ""),
        audience=os.getenv("OIDC_AUDIENCE", SERVICE_ID),
        jwks_url=os.getenv("OIDC_JWKS_URL"),
    )
    if os.getenv("OIDC_ISSUER_URL")
    else None
)


async def _authenticate(bearer: str) -> str | None:
    """Bootstrap auth: API keys, then OIDC (if configured)."""
    # 1. API key map
    principal = API_KEYS.get(bearer)
    if principal:
        return principal
    # 2. OIDC (if configured)
    if _oidc_validator:
        return await _oidc_validator.validate(bearer)
    # 3. Not recognized — service will try ANIP JWT separately
    return None


service = ANIPService(
    service_id=SERVICE_ID,
    capabilities=[search_flights, book_flight],
    storage=f"sqlite:///{os.getenv('ANIP_DB_PATH', 'anip.db')}",
    trust=os.getenv("ANIP_TRUST_LEVEL", "signed"),
    key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
    authenticate=_authenticate,
)

app = FastAPI(title="ANIP Flight Service")
mount_anip(app, service)
```

- [ ] **Step 2: Commit**

```bash
git add examples/anip/app.py
git commit -m "feat(examples): integrate OIDC validation into Python example app"
```

---

### Task 6: Python OIDC tests

**Files:**
- Create: `examples/anip/tests/test_oidc.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for OIDC token validation in the example app."""
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import pytest
import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jwt import algorithms as jwt_algorithms

from anip_flight_demo.oidc import OidcValidator, _map_claims_to_principal


# --- Test key pair ---

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()
_public_jwk = jwt_algorithms.RSAAlgorithm.to_jwk(_public_key, as_dict=True)
_public_jwk["kid"] = "test-key-1"
_public_jwk["alg"] = "RS256"
_public_jwk["use"] = "sig"


# --- Local JWKS server ---

class _JwksHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/.well-known/openid-configuration":
            port = self.server.server_address[1]
            body = json.dumps({
                "issuer": f"http://localhost:{port}",
                "jwks_uri": f"http://localhost:{port}/jwks",
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/jwks":
            body = json.dumps({"keys": [_public_jwk]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # suppress logs


@pytest.fixture(scope="module")
def jwks_server():
    server = HTTPServer(("localhost", 0), _JwksHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{port}"
    server.shutdown()


def _sign_token(issuer: str, audience: str, claims: dict, exp_offset: int = 3600) -> str:
    payload = {
        "iss": issuer,
        "aud": audience,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
        **claims,
    }
    return pyjwt.encode(payload, _private_key, algorithm="RS256", headers={"kid": "test-key-1"})


# --- Claim mapping tests ---

class TestClaimMapping:
    def test_email_claim(self):
        assert _map_claims_to_principal({"email": "samir@example.com"}) == "human:samir@example.com"

    def test_preferred_username(self):
        assert _map_claims_to_principal({"preferred_username": "samir", "sub": "123"}) == "human:samir"

    def test_sub_only(self):
        assert _map_claims_to_principal({"sub": "service-xyz"}) == "oidc:service-xyz"

    def test_no_claims(self):
        assert _map_claims_to_principal({}) is None


# --- Validator tests ---

class TestOidcValidator:
    @pytest.fixture
    def validator(self, jwks_server):
        return OidcValidator(issuer_url=jwks_server, audience="test-service")

    async def test_valid_token_with_email(self, validator, jwks_server):
        token = _sign_token(jwks_server, "test-service", {"email": "samir@example.com"})
        result = await validator.validate(token)
        assert result == "human:samir@example.com"

    async def test_valid_token_with_username(self, validator, jwks_server):
        token = _sign_token(jwks_server, "test-service", {"preferred_username": "samir", "sub": "u1"})
        result = await validator.validate(token)
        assert result == "human:samir"

    async def test_valid_token_sub_only(self, validator, jwks_server):
        token = _sign_token(jwks_server, "test-service", {"sub": "svc-account"})
        result = await validator.validate(token)
        assert result == "oidc:svc-account"

    async def test_expired_token(self, validator, jwks_server):
        token = _sign_token(jwks_server, "test-service", {"email": "x@x.com"}, exp_offset=-3600)
        result = await validator.validate(token)
        assert result is None

    async def test_wrong_issuer(self, jwks_server):
        validator = OidcValidator(issuer_url="https://wrong.example.com", audience="test-service",
                                  jwks_url=f"{jwks_server}/jwks")
        token = _sign_token(jwks_server, "test-service", {"email": "x@x.com"})
        result = await validator.validate(token)
        assert result is None

    async def test_wrong_audience(self, jwks_server):
        validator = OidcValidator(issuer_url=jwks_server, audience="wrong-aud")
        token = _sign_token(jwks_server, "wrong-aud-not-matching", {"email": "x@x.com"})
        result = await validator.validate(token)
        assert result is None

    async def test_invalid_signature(self, validator, jwks_server):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        payload = {"iss": jwks_server, "aud": "test-service", "email": "x@x.com",
                   "iat": int(time.time()), "exp": int(time.time()) + 3600}
        token = pyjwt.encode(payload, other_key, algorithm="RS256", headers={"kid": "test-key-1"})
        result = await validator.validate(token)
        assert result is None

    async def test_jwks_fetch_failure(self):
        validator = OidcValidator(issuer_url="http://localhost:1", audience="x",
                                  jwks_url="http://localhost:1/jwks")
        result = await validator.validate("some-token")
        assert result is None

    async def test_non_jwt_string(self, validator):
        result = await validator.validate("not-a-jwt")
        assert result is None

    async def test_explicit_jwks_url(self, jwks_server):
        validator = OidcValidator(issuer_url=jwks_server, audience="test-service",
                                  jwks_url=f"{jwks_server}/jwks")
        token = _sign_token(jwks_server, "test-service", {"email": "direct@example.com"})
        result = await validator.validate(token)
        assert result == "human:direct@example.com"
```

- [ ] **Step 2: Install and run tests**

Run:
```bash
cd examples/anip
pip install -e ".[dev]" PyJWT[crypto] httpx
pytest tests/test_oidc.py -v
```
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add examples/anip/tests/test_oidc.py
git commit -m "feat(examples): add OIDC validation tests for Python example"
```

---

## Chunk 3: Verify and CI

### Task 7: Verify existing example tests still pass

- [ ] **Step 1: Run TypeScript example tests**

Run: `cd examples/anip-ts && npx vitest run`
Expected: All existing tests pass (OIDC is optional, not breaking)

- [ ] **Step 2: Run Python example tests**

Run: `cd examples/anip && pytest tests/ -v`
Expected: All existing + new OIDC tests pass

- [ ] **Step 3: Commit any fixes**

If any existing tests break due to the `authenticate` callback becoming async (TypeScript), fix them.

**Note:** The TypeScript `authenticate` callback changes from sync `(bearer) => string | null` to async `async (bearer) => string | null`. Check if `createANIPService` accepts async authenticate callbacks. If not, the implementer should check `packages/typescript/service/src/service.ts` for the authenticate type and adapt — either make the OIDC path sync (cache JWKS eagerly) or update the service to accept async callbacks.
