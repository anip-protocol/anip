# ANIP v0.2 Trust Model

> Cryptographic foundations for agent delegation, manifest integrity, and audit tamper-evidence.

This document describes the security architecture introduced in ANIP v0.2. For operational guidance (reporting vulnerabilities, deployment, trust modes), see [SECURITY.md](../SECURITY.md).

---

## 1. Threat Model

ANIP v0.2 defends against a specific set of threats in the agent delegation model:

### In Scope

| Threat | Mitigation |
|--------|-----------|
| **Token forgery** — an agent fabricates a delegation token | Server-issued JWTs with ES256 signatures; agents cannot mint tokens |
| **Token tampering** — an agent modifies claims (scope, budget, subject) | JWT signature verification rejects modified tokens |
| **Store tampering** — the token store is modified after issuance | Trust boundary compares every signed JWT claim against stored state |
| **Scope escalation** — a child token exceeds parent authority | Server enforces scope narrowing and budget caps at issuance |
| **Manifest tampering** — a manifest is modified in transit or at rest | Detached JWS signature over the manifest body |
| **Audit tampering** — log entries are modified or deleted | Hash chain with per-entry signatures; gaps break the chain |
| **Key confusion** — delegation key used to forge audit entries or vice versa | Separate signing keys with distinct `use` claims in JWKS |

### Out of Scope

| Threat | Why |
|--------|-----|
| **Prompt injection** | ANIP governs authorization, not intent; a compromised agent can still act within its granted authority |
| **Compromised runtime** | If the agent host is compromised, the attacker has the JWT and can use it within its validity window |
| **Compromised service** | If the service is compromised, signing keys are exposed; ANIP does not protect against service-side compromise |
| **Network eavesdropping** | ANIP signs but does not encrypt; TLS is required for confidentiality |
| **Denial of service** | ANIP does not rate-limit; token budgets cap spending but not request volume |
| **Cross-service delegation** | v0.2 uses a first-party issuer model; federated trust is a future goal |

---

## 2. Signed Delegation Tokens

### Issuance Flow

```
Human/Agent                         Service
    |                                  |
    |-- POST /anip/tokens ------------>|
    |   Authorization: Bearer <key>    |
    |   {subject, scope, capability}   |
    |                                  |
    |   1. Authenticate caller (API key -> identity)
    |   2. Validate scope narrowing (if child token)
    |   3. Generate token_id, store DelegationToken
    |   4. Build JWT claims from stored token
    |   5. Sign JWT with delegation key (ES256)
    |                                  |
    |<-- {issued, token_id, token} ----|
    |    (token is the signed JWT)     |
```

The service is the sole token issuer. Agents never construct tokens — they request them and receive signed JWTs. This eliminates an entire class of token forgery attacks.

### JWT Claims

Every issued JWT contains these claims:

| Claim | Source | Purpose |
|-------|--------|---------|
| `jti` | Server-generated | Unique token ID, links JWT to stored token |
| `iss` | Service identity | Issuer identifier |
| `sub` | Token request | The agent identity this token is for |
| `aud` | Service identity | Intended audience |
| `iat` / `exp` | Server clock | Issuance and expiry timestamps |
| `scope` | Token request (validated) | Authorized scope labels |
| `capability` | Token request | Which capability this token authorizes |
| `root_principal` | Derived from auth or parent chain | The human at the root of the delegation chain |
| `constraints` | Stored token | Delegation depth, concurrency rules |
| `parent_token_id` | Parent JWT (if child) | Links child to parent for chain verification |
| `budget` | Parsed from scope | Financial budget cap (if any) |

### Trust Boundary: `_resolve_jwt_token()`

When an agent presents a JWT to a protected endpoint, the server:

1. **Verifies the JWT signature** against the delegation signing key
2. **Looks up the stored token** by `jti`
3. **Compares every trust-critical claim** in the JWT against the stored token:
   - `sub` must match `stored.subject`
   - `scope` must match `stored.scope` (sorted comparison)
   - `capability` must match `stored.purpose.capability`
   - `root_principal` must match the stored delegation chain root (child tokens only)
   - `parent_token_id` must match `stored.parent`
   - `constraints` must match `stored.constraints` (full object comparison)
4. **Any mismatch** returns a `token_integrity_violation` failure

This dual verification (signature + store comparison) means that neither a forged JWT nor a tampered store alone can produce a valid token. An attacker would need to compromise both the signing key and the database simultaneously.

Missing claims are treated as integrity violations, not silent passes. If the JWT lacks `constraints` or `root_principal` (for child tokens), the verification fails explicitly.

### Delegation Chains

Child tokens are issued by presenting a parent JWT:

```
Human authenticates with API key
  └── Issues root token T1 (subject: agent:A, scope: travel.book:max_$500)
        └── Agent A requests child token T2 (subject: agent:B, scope: travel.book:max_$300)
              └── Agent B uses T2 to invoke book_flight
```

At each level:
- The caller must be the parent token's `sub` (only the delegatee can sub-delegate)
- Child scope must be a subset of parent scope
- Child budget must be ≤ parent budget
- `root_principal` is carried from the root through all children

### Algorithm and Key Details

- **Algorithm:** ES256 (ECDSA with P-256 / secp256r1 and SHA-256)
- **Key format:** JWK (JSON Web Key) with `kty: "EC"`, `crv: "P-256"`
- **Key identifier:** SHA-256 of the public key's compressed point encoding, truncated to 8 hex characters
- **Key persistence:** PEM-encoded private keys + JWK public key material, stored in a JSON file on disk

---

## 3. Signed Manifests

The manifest declares the service's capabilities, cost ranges, side-effect types, and other metadata. In v0.2, the manifest is signed to prevent tampering.

### Signing Mechanism

The server signs the manifest using a **detached JWS** (JSON Web Signature):

1. Serialize the manifest to JSON bytes (canonical — this exact byte sequence is the signing input)
2. Compute a SHA-256 hash of the manifest body for the `manifest_metadata.sha256` field
3. Build JWS header: `{"alg": "ES256", "kid": "<delegation-key-id>"}`
4. Sign: `base64url(header) + "." + base64url(manifest_bytes)` → ECDSA signature
5. Return the manifest body as the HTTP response, with the detached JWS in the `X-ANIP-Signature` header

The detached JWS format is `header..signature` (empty payload section), following RFC 7515 Appendix F. The consumer reconstructs the signing input from the response body.

### Manifest Metadata

Every v0.2 manifest includes:

```json
{
  "manifest_metadata": {
    "version": "0.2.0",
    "sha256": "a1b2c3...",
    "issued_at": "2026-03-12T...",
    "expires_at": "2026-03-13T..."
  },
  "service_identity": {
    "id": "anip-flight-service",
    "jwks_uri": "/.well-known/jwks.json",
    "issuer_mode": "first-party"
  }
}
```

### Verification

A consumer verifies the manifest by:

1. Fetching the JWKS from `service_identity.jwks_uri`
2. Finding the key matching the `kid` in the JWS header
3. Reconstructing the signing input from the JWS header and response body
4. Verifying the ECDSA signature

### What Manifest Signing Does Not Do

Manifest signing proves the manifest was produced by the holder of the signing key. It does not prove that the declarations are *accurate*. A service can sign a manifest that claims `side_effect: "read"` for a capability that actually mutates state. Manifest signing protects integrity, not truthfulness.

---

## 4. Signed Audit Logs

### Hash Chain

Audit log entries form a hash chain:

```
Entry 1                    Entry 2                    Entry 3
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ sequence: 1      │      │ sequence: 2      │      │ sequence: 3      │
│ prev: "sha256:0" │──────│ prev: hash(E1)   │──────│ prev: hash(E2)   │
│ data: {...}      │      │ data: {...}      │      │ data: {...}      │
│ signature: sig1  │      │ signature: sig2  │      │ signature: sig3  │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

- The first entry uses the sentinel value `"sha256:0"` as its previous hash
- Each subsequent entry's `previous_hash` is the SHA-256 hash of the prior entry's canonical JSON (excluding `signature` and `id`)
- Each entry is individually signed with the **audit signing key** (separate from the delegation key)

### What the Hash Chain Proves

- **Ordering:** entries have a definitive sequence
- **Completeness:** deleting or reordering entries breaks the chain
- **Integrity:** modifying an entry's content changes its hash, breaking the next entry's `previous_hash` link
- **Attribution:** each entry's signature proves it was written by the holder of the audit key

### What the Hash Chain Does Not Prove

- **Liveness:** the chain does not prove entries were written in real-time (the service could batch-sign)
- **Completeness of recording:** the service could omit invocations entirely (the chain proves ordering of *recorded* entries, not that all events were recorded)
- **External anchoring:** the chain is self-referential; there is no external timestamp authority or witness

### Key Separation

The JWKS endpoint publishes two keys:

| Key | `use` | Purpose |
|-----|-------|---------|
| Delegation key | `sig` | Signs JWTs and manifests |
| Audit key | `audit` | Signs audit log entries |

Separating keys limits blast radius: compromising the audit key does not allow forging delegation tokens, and vice versa.

---

## 5. Issuer and Audience Model

v0.2 uses a **first-party issuer model**:

- The service that enforces capabilities is the same entity that issues tokens
- `iss` and `aud` in JWTs are both the service's identity
- There is no external identity provider or token exchange

This is simpler than federated models (OAuth, OIDC) but limits cross-service delegation. An agent holding a token for Service A cannot use it at Service B.

### Caller Authentication

Token issuance requires caller authentication via `Authorization: Bearer <api-key>`. The API key maps to a caller identity (e.g., `"demo-human-key"` → `"human:samir@example.com"`).

The reference implementation uses a static API key map. Production deployments should replace this with a proper identity provider.

---

## 6. Discovery

The `/.well-known/anip` discovery endpoint advertises:

- Protocol version (`anip/0.2`)
- JWKS URI for public key retrieval
- Supported auth formats (`jwt-es256`)
- Endpoint paths (manifest, tokens, invoke, etc.)

This allows agents to bootstrap trust: discover the service, fetch its public keys, and verify all subsequent interactions.

---

## 7. Non-Goals and Remaining Gaps

These are explicitly not addressed in v0.2 and represent areas for future work:

| Gap | Description |
|-----|-------------|
| **Key revocation** | No CRL or OCSP. Rotation requires restarting the service, which invalidates all outstanding tokens. |
| **Token revocation** | Individual tokens cannot be revoked before expiry. The only mechanism is deleting them from the store, which causes `_resolve_jwt_token()` to reject them. |
| **Federated trust** | No cross-service token exchange. Each service is its own trust root. |
| **Formal verification** | The trust model has not been formally verified. The reference implementations have test coverage but no third-party security audit. |
| **Key custody** | Signing keys are stored as plaintext PEM on disk. Production deployments should use HSMs or key management services. |
| **Clock skew** | JWT expiry checks use the server's clock. There is no tolerance for clock skew between issuer and verifier (they are the same entity in v0.2). |
| **Encrypted tokens** | JWTs are signed but not encrypted. Any party that intercepts a JWT can read its claims. TLS mitigates this in transit; at-rest encryption is the deployer's responsibility. |
