# Security Policy

The current ANIP protocol version is v0.24. Its security foundations are v0.2's signed tokens, manifests, and audit chain and v0.3's anchored trust, extended by invocation lineage (v0.4), async storage (v0.5), streaming invocations with transport fault isolation (v0.6), discovery posture (v0.7), security hardening with event classification, retention policies, and failure redaction (v0.8), and the later additions listed below. It does not by itself solve prompt injection, host sandboxing, or internet-scale trust federation.

## Supported Versions

| Version | Status |
|---------|--------|
| v0.24 (packages 0.24.18 and later) | Current — receives security fixes |
| Packages 0.24.17 and earlier | Affected by [GHSA-h9rv-5v5h-pmr6](https://github.com/anip-protocol/anip/security/advisories/GHSA-h9rv-5v5h-pmr6) — upgrade |
| v0.23 and earlier | Not supported — upgrade to the current release |

ANIP is pre-1.0. Security fixes are made on the latest release only. See the [version history](https://anip.dev/docs/releases/version-history) for what each version added.

The declaration-only trust model from v0.1 is available via `ANIP_TRUST_MODE=declaration` for development and migration. It should not be used in production.

## Reporting Vulnerabilities

If you discover a security vulnerability in ANIP, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email **security@anip.dev** with a description of the vulnerability, reproduction steps, and affected versions
3. You will receive an acknowledgment within 48 hours
4. We will work with you on a fix before public disclosure

## Trust Model Summary

ANIP uses a **first-party issuer model**, introduced in v0.2: the service generates and signs all delegation tokens. Agents request tokens; the service issues JWTs. This avoids the complexity of federated trust while providing cryptographic verification of authority chains.

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

For the full threat model and architectural details, see [docs/trust-model.md](docs/trust-model.md).

## Trust Modes

| Mode | Flag | Use Case |
|------|------|----------|
| **Signed** (default) | `ANIP_TRUST_LEVEL=signed` | Bronze — all tokens are server-issued JWTs with ES256 signatures |
| **Anchored** | `ANIP_TRUST_LEVEL=anchored` | Silver — signed + Merkle tree checkpoints over audit log |
| **Attested** | `ANIP_TRUST_LEVEL=attested` | Gold — anchored + third-party co-signing (future) |
| **Declaration** | `ANIP_TRUST_MODE=declaration` | Development/migration — clients build token dicts locally, no signatures |

Declaration mode accepts unsigned token dicts for backward compatibility with v0.1 clients. It provides no cryptographic guarantees and exists only to support incremental migration.

## Deployment Guidance

- **Always use signed mode in production.** Declaration mode is for development only.
- **Rotate signing keys** by deleting the persisted key file and restarting the server. Existing JWTs will be invalidated.
- **Protect API keys.** The reference server uses static Bearer tokens for caller authentication. Production deployments should use a proper identity provider.
- **Run behind TLS.** ANIP does not encrypt payloads — it signs them. Transport encryption (HTTPS) is required to protect tokens in transit.
- **Scope tokens narrowly.** Issue tokens with the minimum scope and budget needed for each task.

## What v0.2 Introduced

- Tokens are **server-issued JWTs** instead of client-constructed dicts — the server is the authority, not the caller
- Manifests carry **detached JWS signatures** — consumers can verify the manifest hasn't been tampered with
- Audit logs form a **hash chain** with per-entry signatures — tampering breaks the chain
- A **trust boundary** in `_resolve_jwt_token()` compares every signed JWT claim against stored state, detecting store tampering
- **Separate signing keys** for delegation and audit (blast radius containment)
- **JWKS endpoint** at `/.well-known/jwks.json` for public key discovery

## What v0.3 Adds

- **Trust levels** — `signed` (Bronze), `anchored` (Silver), `attested` (Gold) declared in discovery
- **Merkle tree checkpoints** — RFC 6962-compatible trees over audit log entries, with inclusion and consistency proofs
- **Checkpoint scheduling** — automatic checkpoints by entry count and/or time interval
- **Async sink publication** — checkpoints published to external sinks via background queue
- **Checkpoint endpoints** — `GET /anip/checkpoints` and `GET /anip/checkpoints/{id}` with proof support

## What v0.4–v0.6 Adds

- **Invocation lineage (v0.4)** — server-generated `invocation_id` and caller-supplied `client_reference_id` on every invoke response and audit entry for end-to-end traceability
- **Async storage (v0.5)** — fully async storage layer, non-blocking audit writes
- **Streaming invocations (v0.6)** — `ResponseMode` enum, SSE transport for progress events, `StreamSummary` with delivery accounting
- **Sink isolation (v0.6)** — transport write failures are caught and swallowed; handler execution is never aborted by a client disconnect
- **Error redaction (v0.6)** — streamed internal errors emit generic messages, never raw exception details

## What v0.7 Adds

- **Discovery posture** — services declare a governance stance (`open`, `gated`, `restricted`, `closed`) in the discovery document, letting agents understand the engagement model before requesting tokens
- **Posture metadata** — human-readable `description`, machine-readable `access` rules, and optional `contact` for access requests

## What v0.8 Adds

- **Event classification** — audit events tagged by sensitivity (`public`, `internal`, `confidential`, `restricted`) for data governance
- **Retention policies** — configurable TTLs per retention tier (`ephemeral`, `short`, `standard`, `extended`, `permanent`) with automatic `expires_at` on audit entries
- **Failure detail redaction** — internal error details stripped from client-facing failure responses based on event class
- **Proof safety guards** — retention enforcer prevents serving expired or retention-violating audit proofs

## What v0.9–v0.24 Add

Only the security-relevant additions are listed here. The [version history](https://anip.dev/docs/releases/version-history) covers every version.

- **Audit disclosure controls (v0.9)** — storage-side redaction, caller-class disclosure resolved per caller, audit aggregation, and proof expiration guidance
- **Multi-replica integrity (v0.10)** — storage-atomic audit append, lease-based exclusive invocation locks, and leader-elected background jobs
- **Token purpose binding (v0.12)** — tokens are bound to a purpose; `task_id` and `parent_invocation_id` make invocation trees auditable
- **Enforceable budgets and bindings (v0.13–v0.14)** — budget constraints in delegation tokens are enforced before execution and cannot be widened by a child token; capabilities can require a binding and declare control requirements
- **Non-delegable actions (v0.15)** — a `non_delegable_action` failure tells the caller that no delegation path exists for the action
- **Bootstrap authentication contract (v0.20)** — an explicit hook contract for authenticating the caller before token issuance, plus capability-targeted root issuance
- **Parent token semantics (v0.22)** — `parent_token` is a token ID, not a JWT, consistently across runtimes
- **Signed approval grants (v0.23)** — an approval is a signed, parameter-bound, finite-use grant (`one_time` or `session_bound`), signed like the manifest (ES256 JWS by default)

## Delegation Enforcement Fix (packages 0.24.18)

Packages up to 0.24.17 did not enforce several delegation rules the specification requires. Which rules were missing differed per runtime. Details are in advisory [GHSA-h9rv-5v5h-pmr6](https://github.com/anip-protocol/anip/security/advisories/GHSA-h9rv-5v5h-pmr6) and in the [0.24.18 release notes](https://anip.dev/docs/releases/delegation-enforcement-0-24-18).

- **Go, Java, C#** — a token could invoke capabilities other than the one it was issued for; a delegated token could widen its parent's scope; any authenticated principal could delegate from another principal's token by its ID; delegation depth was not checked.
- **Python, TypeScript** — a delegation token was accepted as the credential for root token issuance. In TypeScript, and in Python's stdio and gRPC transports, the caller was additionally treated as the root principal of the token's chain.
- **All runtimes** — a budget carried by a scope could be shed when delegating.

All five runtimes now enforce the same rules, and the conformance suite tests them (`conformance/test_delegation.py`). If you run an ANIP service with more than one principal or more than one capability, upgrade.

## What ANIP Does Not Yet Solve

- **Prompt injection** — ANIP controls what an agent is *authorized* to do, not what it is *tricked into wanting* to do
- **Host sandboxing** — ANIP assumes the agent runtime is not compromised
- **Federated trust** — ANIP uses a first-party issuer model; cross-service delegation chains and token exchange are not yet supported. The cross-service fields added in v0.18–v0.19 (`upstream_service`, `cross_service` hints) are unvalidated and do not establish trust between services
- **Key revocation** — no CRL or OCSP equivalent; key rotation requires server restart
- **Rate limiting / abuse** — ANIP enforces budget caps per token but does not rate-limit token requests
- **Encrypted payloads** — tokens and manifests are signed, not encrypted; TLS is required for confidentiality
- **Formal verification** — the trust model has not been formally verified or audited by a third party
