---
title: Checkpoints and Trust
description: Signed manifests, JWKS, Merkle checkpoints, and trust posture in ANIP.
---

# Checkpoints and Trust

ANIP includes a trust model, not just a tool schema. Services can prove their claims are authentic, and agents can verify that execution history hasn't been tampered with.

## Trust posture

Every ANIP service declares its trust posture in the discovery document, so agents and operators know how much to rely on the service's claims:

| Level | What it means |
|-------|--------------|
| `declarative` | Service declares capabilities but doesn't sign anything |
| `signed` | Manifest is cryptographically signed, JWKS published |
| `anchored` | Audit checkpoints anchored to external trust (e.g., transparency logs) |

```json
{
  "trust": {
    "level": "signed",
    "anchoring": {
      "cadence": "hourly"
    }
  }
}
```

An agent connecting to a `signed` service knows the manifest hasn't been modified since the service signed it. An `anchored` service provides even stronger guarantees through external verification.

## Signed manifests

The manifest at `GET /anip/manifest` includes a cryptographic signature in the `X-ANIP-Signature` header. This signature is verifiable against the service's JWKS (JSON Web Key Set) at `GET /.well-known/jwks.json`.

```bash
# Fetch the manifest — note the signature header
curl -I https://service.example/anip/manifest
```

```
HTTP/1.1 200 OK
Content-Type: application/json
X-ANIP-Signature: eyJhbGciOiJFZERTQSJ9...
```

The manifest also includes a SHA-256 hash of its content in `manifest_metadata.sha256`, allowing offline verification.

## JWKS

The service publishes its public signing keys at the standard JWKS endpoint:

```bash
curl https://service.example/.well-known/jwks.json
```

```json
{
  "keys": [
    {
      "kty": "OKP",
      "crv": "Ed25519",
      "x": "dGhpcyBpcyBhIHB1YmxpYyBrZXk...",
      "kid": "primary-signing-key",
      "use": "sig"
    }
  ]
}
```

JWKS serves as the verification surface for:
- Manifest signatures
- Delegation token signatures
- Audit checkpoint signatures

## Merkle checkpoints

ANIP can produce Merkle tree checkpoints over audit history. These checkpoints create a tamper-evident chain — if any audit entry is modified or deleted after the fact, the checkpoint hashes won't match.

```bash
curl https://service.example/anip/checkpoints?limit=3
```

```json
{
  "checkpoints": [
    {
      "checkpoint_id": "cp_a1b2c3",
      "sequence": 42,
      "merkle_root": "sha256:7d3f8a...",
      "entry_count": 150,
      "created_at": "2026-03-27T11:00:00Z",
      "signature": "eyJhbGciOi..."
    }
  ]
}
```

### What checkpoints prove

- **Completeness**: The checkpoint covers a known count of audit entries
- **Integrity**: The Merkle root changes if any entry is modified
- **Non-repudiation**: The checkpoint is signed by the service's key

### Consistency proofs

Individual audit entries can be verified against a checkpoint's Merkle tree using inclusion proofs, confirming that a specific invocation was recorded without needing to download the entire audit log.

## Why trust matters for agents

In traditional APIs, "trust" is an all-or-nothing proposition — you either trust the service or you don't. ANIP provides a spectrum:

- **Declarative services** are useful for development and testing
- **Signed services** are appropriate for internal production deployments
- **Anchored services** provide audit evidence suitable for compliance and external review

Agents can adapt their behavior based on trust posture — for example, requiring `signed` or higher for financial operations, while accepting `declarative` for read-only data queries.

## Next steps

- **[Capabilities](/docs/protocol/capabilities)** — What services declare about their capabilities
- **[Transport: HTTP](/docs/transports/http)** — How these endpoints work over HTTP
