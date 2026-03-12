# ANIP v0.2: Cryptographic Trust Foundations — Design

## Version Boundary

- **v0.1:** Trust-on-declaration. Services declare capabilities, costs, and side effects; agents take declarations at face value. Suitable for trusted internal environments.
- **v0.2:** Signed delegation and verifiable declarations. Tokens are cryptographically signed, manifests carry integrity proofs, audit logs are tamper-detectable. The protocol shifts from "believe the server" to "verify what you can, trust what you must."

v0.2 does not claim to solve federation, third-party attestation, or enforcement proofs. Those remain explicitly open for future versions.

---

## Phase 1: Signed Delegation Tokens

### Problem

v0.1 tokens are opaque strings registered by the caller. The server trusts whatever the caller claims about identity, scope, and budget. There is no way to verify that a token was legitimately issued or that its claims haven't been tampered with.

### Design

**Format:** JWT (RFC 7519), signed with ES256 (ECDSA over P-256).

**Issuance model:** The server issues tokens, not the client. `POST /anip/tokens` becomes a delegation issuance endpoint:

1. Caller authenticates (API key, OAuth, mTLS — mechanism is out of scope for the protocol).
2. Server derives `root_principal` from the authentication context.
3. Server constructs the JWT with the requested scope and budget, constrained by the caller's authority.
4. Server signs the JWT and returns it.

The caller never proposes a pre-built token. The server is the authority on what gets signed.

**Child issuance:** An agent can request a child token by presenting its parent JWT. The server verifies the caller is the parent token's `sub`, then issues a child with equal or narrower scope (scope narrowing rule preserved).

**Key discovery:** JWKS endpoint at `/.well-known/jwks.json`. Clients verify token signatures locally against the published key set.

**JWT claims:**

| Claim | Description |
|-------|-------------|
| `iss` | Service identifier (issuer) |
| `sub` | Token subject (e.g., `agent:demo-agent`) |
| `aud` | Intended audience (service URL or identifier) |
| `iat` | Issued-at timestamp |
| `nbf` | Not-before timestamp |
| `exp` | Expiration timestamp |
| `scope` | Array of scoped permissions (e.g., `["travel.book:max_$300"]`) |
| `capability` | Bound capability name |
| `root_principal` | Identity of the human or system that originated the delegation chain |
| `parent_token_id` | ID of parent token (for child tokens) |
| `purpose` | Free-text purpose binding for audit context |
| `budget` | Budget constraint object (`{ "max": 300, "currency": "USD" }`) |

**Trust modes:**

- **Default (signed):** All tokens are JWT-signed. Verification is mandatory.
- **`--trust-on-declaration`:** Dev-only escape hatch. Accepts unsigned tokens for local development and testing. Services MUST log a warning when running in this mode. Production deployments MUST NOT use this mode.

### What This Proves

A client can verify that a token was issued by the claimed service, that its claims haven't been modified, and that it hasn't expired. The delegation chain becomes cryptographically traceable: each child token references its parent, and each signature can be verified against the service's published keys.

### What This Doesn't Prove

That the service will honor the token's constraints at execution time. A service could sign a token with `max_$300` and then charge $500. Behavioral enforcement remains trust-based in v0.2. Conformance testing (Phase 3) provides statistical confidence but not cryptographic proof.

---

## Phase 2: Signed Manifests and Service Identity

### Problem

v0.1 manifests are unsigned JSON. A MITM could modify capability declarations, cost ranges, or side-effect types in transit. There is no way to verify that the manifest you received is the one the service intended to publish.

### Design

**Signing mechanism:** Detached JWS (JSON Web Signature). The manifest remains plain JSON. The signature is delivered in the `X-ANIP-Signature` HTTP response header. This preserves backward compatibility — clients that don't check signatures see normal JSON; clients that do can verify integrity without parsing a JWS envelope.

**Manifest metadata:** New `manifest_metadata` section:

```json
{
  "manifest_metadata": {
    "version": "0.2.0",
    "sha256": "abc123...",
    "issued_at": "2026-03-11T00:00:00Z",
    "expires_at": "2026-04-11T00:00:00Z"
  }
}
```

The `sha256` is the hash of the canonical manifest body (excluding `manifest_metadata` itself). `expires_at` gives clients a staleness signal — if the manifest has expired, re-fetch before trusting its declarations.

**Service identity:** New `service_identity` section:

```json
{
  "service_identity": {
    "id": "flights.example.com",
    "jwks_uri": "https://flights.example.com/.well-known/jwks.json",
    "issuer_mode": "first-party"
  }
}
```

`issuer_mode` is `first-party` for v0.2. This field exists to make the federation boundary explicit — when third-party attestation arrives in a future version, the mode changes but the structure doesn't.

**Discovery endpoint update:** `/.well-known/anip` adds `jwks_uri` to its response, so clients can discover the verification key set before fetching the manifest.

### Integrity Claim

Manifest signing proves the manifest was produced by the holder of the signing key and has not been modified in transit. It does not prove the service will behave according to its declarations. The manifest is a statement of intent with integrity protection, not a behavioral guarantee.

### Timestamping

`issued_at` and `expires_at` in manifest metadata provide freshness signals. Clients SHOULD re-fetch expired manifests. Clock skew tolerance is implementation-defined but SHOULD be no more than 5 minutes.

---

## Phase 3: Conformance Testing and Signed Audit Logs

### Problem

Phases 1 and 2 prove identity and integrity but not behavior. A service could sign a perfect manifest and then violate every declaration. v0.2 needs a way to build confidence (not proof) that services behave as declared.

### 3A: Conformance Test Suite

A standardized test suite that any ANIP service can run against itself (or be tested by a third party).

**Test categories:**

| Category | What It Tests | Nuance |
|----------|--------------|--------|
| Side-effect accuracy | `read` capabilities don't mutate state; `irreversible` capabilities can't be undone | Binary pass/fail |
| Cost accuracy | Actual costs fall within declared ranges | Model-aware: fixed costs must match exactly; estimated/dynamic costs must fall within declared `range_min`/`range_max`; percentage tolerance for `typical` |
| Prerequisite enforcement | Capabilities with `requires` fail cleanly when prerequisites aren't met | Tests both the failure and the failure structure |
| Scope enforcement | Out-of-scope invocations are rejected with structured failures | Tests delegation chain validation |
| Budget enforcement | Over-budget invocations are rejected with `budget_exceeded` failure type | Tests against declared budget constraints |
| Failure semantics | Failures include `type`, `detail`, `resolution` with actionable guidance | Tests structure, not just rejection |

**`/verify` endpoint:** A convenience endpoint that checks token signatures and returns validation results. This is a helper — the real trust path is clients verifying signatures locally against JWKS. `/verify` SHOULD NOT be treated as the authority on token validity.

**Conformance levels:**

- **ANIP-compliant:** Passes core conformance (side effects, scope, budget, failures).
- **ANIP-complete:** Passes core + contextual conformance (costs, prerequisites, observability).

### 3B: Signed Audit Logs

**Hash chain:** Each audit entry includes `previous_hash` — the SHA-256 hash of the preceding entry. This creates an append-only chain where inserting, deleting, or reordering entries breaks the chain. The first entry in the chain uses a well-known sentinel value for `previous_hash`.

**Entry signing:** Each audit entry is signed with ES256. The signing key SHOULD be a dedicated audit key, separate from the delegation-signing key. Rationale: if the delegation key is compromised, the attacker cannot also forge audit entries. Key rotation for delegation tokens should not require re-signing the audit history.

**Global sequence:** Each entry carries a monotonically increasing `sequence_number` scoped to the service. Gaps in the sequence are detectable.

**Checkpoint hashes:** The service periodically publishes a `log_root_hash` — the hash of the full log state at a given sequence number. Checkpointing improves omission and rollback detection when checkpoints are externally anchored (published to a location the service cannot rewrite retroactively). Without external anchoring, checkpoints detect accidental corruption but not deliberate omission by the service operator.

**Audit entry structure:**

```json
{
  "sequence_number": 42,
  "timestamp": "2026-03-11T14:30:00Z",
  "capability": "book_flight",
  "token_id": "demo-abc123",
  "subject": "agent:demo-agent",
  "root_principal": "human:samir@example.com",
  "delegation_chain": ["human:samir@example.com", "agent:demo-agent"],
  "success": true,
  "cost_actual": { "financial": { "amount": 380, "currency": "USD" } },
  "previous_hash": "sha256:def456...",
  "signature": "eyJ..."
}
```

### What Signed Audit Logs Provide

**Append-only integrity:** Tampering with existing entries breaks the hash chain. Detectable by any client that has seen a previous checkpoint or entry hash.

**Key separation:** Compromising the delegation key does not compromise audit integrity.

**Omission detection (with external anchoring):** If checkpoints are published externally, a service cannot silently drop entries without the omission being detectable at the next checkpoint comparison.

### What Signed Audit Logs Don't Provide

**Non-repudiation in the legal sense.** The service controls the signing key and the log. A determined service operator could maintain a parallel log or selectively omit entries before they're checkpointed. Signed audit logs raise the bar for tampering significantly but do not make it impossible.

**Completeness guarantees.** Without external anchoring of checkpoints, the service could restart the log. The hash chain proves consistency of what's present, not completeness of what should be present.

---

## Migration from v0.1

- v0.2 services MUST support `--trust-on-declaration` mode for backward compatibility during migration.
- v0.2 clients SHOULD verify signatures when available and fall back to unsigned mode when connecting to v0.1 services.
- The `protocol` field in discovery responses changes from `"0.1"` to `"0.2"`. Clients use this to determine which trust model to apply.
- Existing v0.1 token registration requests are accepted in `--trust-on-declaration` mode only.

---

## What's Explicitly Deferred

- **Federation and third-party attestation:** `issuer_mode: "third-party"` is reserved but undefined.
- **Behavioral proofs:** Conformance tests provide statistical confidence, not cryptographic proof of correct behavior.
- **Cross-service delegation:** Tokens are scoped to a single service (`aud` claim). Multi-service delegation chains require protocol extensions.
- **Revocation:** Token expiration is the primary mechanism. Explicit revocation lists (CRL/OCSP-style) are deferred.
- **External checkpoint anchoring:** The protocol defines checkpoint hashes but does not mandate where they're published. Anchoring mechanisms (transparency logs, blockchain, trusted third parties) are implementation choices, not protocol requirements.
