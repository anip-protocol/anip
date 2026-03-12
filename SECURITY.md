# Security Policy

ANIP v0.2 introduces cryptographically signed delegation tokens, signed manifests, and tamper-evident audit foundations, but it does not by itself solve prompt injection, host sandboxing, or internet-scale trust federation.

## Supported Versions

| Version | Status |
|---------|--------|
| v0.2    | Current — signed tokens, signed manifests, hash-chain audit |
| v0.1    | Legacy — declaration-only trust, no cryptographic verification |

v0.1 is available via `ANIP_TRUST_MODE=declaration` for development and migration. It should not be used in production.

## Reporting Vulnerabilities

If you discover a security vulnerability in ANIP, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email **security@anip.dev** with a description of the vulnerability, reproduction steps, and affected versions
3. You will receive an acknowledgment within 48 hours
4. We will work with you on a fix before public disclosure

## Trust Model Summary

ANIP v0.2 uses a **first-party issuer model**: the service generates and signs all delegation tokens. Agents request tokens; the service issues JWTs. This avoids the complexity of federated trust while providing cryptographic verification of authority chains.

**What is cryptographically verified:**
- Token authenticity (JWT/ES256 signatures)
- Token integrity (signed claims compared against stored state)
- Manifest integrity (detached JWS signature)
- Audit chain integrity (hash chain with sequential signatures)
- Scope narrowing (child tokens cannot exceed parent authority)

**What is declared but not cryptographically enforced:**
- Cost ranges (declared in manifest, checked at invocation, but not signed per-invocation)
- Side-effect types (declared, not verified — a service claiming "read" could mutate state)
- Capability descriptions (human-readable, not machine-verified)

For the full threat model and architectural details, see [docs/trust-model-v0.2.md](docs/trust-model-v0.2.md).

## Trust Modes

| Mode | Flag | Use Case |
|------|------|----------|
| **Signed** (default) | `ANIP_TRUST_MODE=signed` | Production — all tokens are server-issued JWTs with ES256 signatures |
| **Declaration** | `ANIP_TRUST_MODE=declaration` | Development/migration — clients build token dicts locally, no signatures |

Declaration mode accepts unsigned token dicts for backward compatibility with v0.1 clients. It provides no cryptographic guarantees and exists only to support incremental migration.

## Deployment Guidance

- **Always use signed mode in production.** Declaration mode is for development only.
- **Rotate signing keys** by deleting the persisted key file and restarting the server. Existing JWTs will be invalidated.
- **Protect API keys.** The reference server uses static Bearer tokens for caller authentication. Production deployments should use a proper identity provider.
- **Run behind TLS.** ANIP does not encrypt payloads — it signs them. Transport encryption (HTTPS) is required to protect tokens in transit.
- **Scope tokens narrowly.** Issue tokens with the minimum scope and budget needed for each task.

## What v0.2 Improves Over v0.1

- Tokens are **server-issued JWTs** instead of client-constructed dicts — the server is the authority, not the caller
- Manifests carry **detached JWS signatures** — consumers can verify the manifest hasn't been tampered with
- Audit logs form a **hash chain** with per-entry signatures — tampering breaks the chain
- A **trust boundary** in `_resolve_jwt_token()` compares every signed JWT claim against stored state, detecting store tampering
- **Separate signing keys** for delegation and audit (blast radius containment)
- **JWKS endpoint** at `/.well-known/jwks.json` for public key discovery

## What v0.2 Does Not Solve

- **Prompt injection** — ANIP controls what an agent is *authorized* to do, not what it is *tricked into wanting* to do
- **Host sandboxing** — ANIP assumes the agent runtime is not compromised
- **Federated trust** — v0.2 uses a first-party issuer model; cross-service delegation chains are not yet supported
- **Key revocation** — no CRL or OCSP equivalent; key rotation requires server restart
- **Rate limiting / abuse** — ANIP enforces budget caps per token but does not rate-limit token requests
- **Encrypted payloads** — tokens and manifests are signed, not encrypted; TLS is required for confidentiality
- **Formal verification** — the trust model has not been formally verified or audited by a third party
