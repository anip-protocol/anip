# ANIP v0.3 Proposal: Trust Levels

> Draft proposal for tiered trust assurance in ANIP.

## Motivation

v0.2 gives ANIP cryptographic attribution — signed tokens, signed manifests, signed audit entries. But all verification is local: the service controls both the keys and the storage. A service can sign everything correctly and still silently omit events, rewrite history, or misrepresent its posture to external parties.

v0.3 addresses this by defining **trust levels** that let services declare — and callers verify — how much assurance backs the cryptographic claims.

## Version Progression

| Version | One-liner | What it proves |
|---------|-----------|---------------|
| v0.2 | Signed | Who signed it |
| v0.3 | Anchored | History was externally anchored |
| v0.4 | Attested | Someone else checked |

---

## Trust Levels

### Signed (Bronze)

The baseline cryptographic layer — what v0.2 already provides.

**Provides:**
- Signed delegation tokens (server-issued JWT/ES256)
- Signed manifests (detached JWS)
- Signed audit entries with hash-chain integrity
- Local verification of signatures and chain integrity

**Proves:**
- Who issued authority
- What the service declared
- Whether locally stored audit history was modified after signing

**Does not prove:**
- That no events were omitted
- That the service cannot rewrite history (it controls both keys and storage)
- That external parties should trust the service by default

**Best fit:** Internal systems, trusted environments, early protocol adoption.

---

### Anchored (Silver)

Adds external checkpointing — the service publishes cryptographic commitments to infrastructure it does not solely control.

**Provides everything in Bronze, plus:**
- Merkle tree accumulation over audit entries
- Periodic signed checkpoint publication to an external sink
- Inclusion and consistency proofs

**Implementation:**
1. Each audit entry is included in a running Merkle tree (in addition to the existing hash chain)
2. Every N entries or T minutes, the service computes a **checkpoint**:
   - Log range covered (sequence numbers)
   - Current Merkle root
   - Timestamp
   - Service identity
   - Signature by the audit key
3. The checkpoint is published to an external system:
   - Customer-controlled log sink
   - Immutable object store (S3 with Object Lock, GCS with retention)
   - Witness service
   - Transparency-log endpoint
4. Publication is **asynchronous** — not in the request hot path
5. If the sink is unavailable, checkpoints queue for retry; anchoring lag is observable

**Why Merkle trees (not just hash chains):**
- The Merkle root commits to the full set of entries efficiently
- **Inclusion proofs** show a given entry is part of a checkpointed history without revealing other entries
- **Consistency proofs** show the log only grew (append-only) from one checkpoint to the next
- Hash chains prove ordering; Merkle trees prove membership and growth

**Proves better than Bronze:**
- Rewriting older history conflicts with already-published checkpoints
- External observers can verify local history matches an anchored root
- Omission becomes harder to hide — if there is a declared checkpoint cadence and an external observer monitoring it, gaps or delays in checkpoint publication are visible. Between checkpoints, omission is still possible.

**Best fit:** Enterprise deployments, higher-trust internal platforms, systems where auditability matters but full third-party attestation is not required.

---

### Attested (Gold)

Adds independent verification — external parties provide evidence that the service is following its declared trust posture.

**Provides everything in Silver, plus:**
- Independently queryable transparency or witness infrastructure
- Third-party attestation of conformance and anchoring practices
- Signed attestation artifacts linked from the manifest

**Implementation (early sketch):**
1. Checkpoints are published to one or more **independent witnesses** or transparency logs
2. Witnesses return receipts, inclusion proofs, or signed acknowledgements
3. Third-party **attestors** verify:
   - ANIP conformance suite passed
   - Checkpoint publication occurred and was continuous
   - Anchoring lag stayed within declared policy
   - Key management posture matched the claimed level
4. The service publishes attestation artifacts alongside its manifest or trust metadata

**Adds over Silver:**
- Stronger resistance to silent history rewriting — independent witnesses make undetected rollback harder, though not impossible
- External parties have evidence the service maintained its declared trust posture during the attestation window
- Auditors, customers, and partner services get independently verifiable trust signals — not absolute proof, but credible assurance

**Best fit:** Regulated environments, cross-organization delegation, public or ecosystem-facing ANIP services.

> **Note:** Gold is primarily a v0.4 concern. v0.3 should define the anchoring mechanisms that Gold builds on, and leave attestation governance for later.

---

## Mechanism vs Policy

The core protocol should define **mechanisms and policy hooks**, not hardcode operational thresholds.

### The spec defines (mechanism):

| Mechanism | What it standardizes |
|-----------|---------------------|
| Trust levels | `signed`, `anchored`, `attested` assurance classes |
| Checkpoint format | Signed object with Merkle root, range, timestamp, service ID |
| External anchoring | How checkpoints are published and verified |
| Trust posture declaration | How a service declares its level in discovery/manifest |
| Risk classification hooks | How profiles can require stricter anchoring for certain actions |

### The deployment defines (policy):

| Policy | Examples |
|--------|---------|
| Checkpoint cadence | Every 100 entries, every 5 minutes |
| Maximum anchoring lag | Checkpoints must be published within 10 minutes |
| High-risk action classification | `side_effect: irreversible` or `cost.financial.amount > 1000` |
| Immediate checkpointing triggers | Irreversible actions, financial ops above threshold |
| External sink choice | S3 bucket, customer log sink, transparency service |
| Trusted attestors | Which third parties are accepted for Gold |

### Why this separation matters:

A financial services deployment might require immediate checkpointing for any action over $500 and attestation from a specific auditor. An internal developer platform might checkpoint hourly and never need attestation. The protocol supports both without either being the default.

---

## Policy Hooks

ANIP should allow services or profiles to declare policies such as:

```yaml
# Example: trust posture declaration in manifest metadata
trust:
  level: silver
  anchoring:
    cadence: "5m"
    max_lag: "15m"
    sink: "witness:acme-audit-service"
  policies:
    - trigger: { side_effect: "irreversible" }
      action: immediate_checkpoint
    - trigger: { cost_financial_above: 1000 }
      action: immediate_checkpoint
```

These are **declarative** — the service states its policy, and callers (or attestors) can verify compliance. The protocol defines the vocabulary; deployments fill in the values.

---

## Checkpoint Object (Draft)

```json
{
  "version": "0.3",
  "service_id": "travel-service",
  "checkpoint_id": "ckpt-00042",
  "range": {
    "first_sequence": 1,
    "last_sequence": 500
  },
  "merkle_root": "sha256:a3f2...",
  "previous_checkpoint": "sha256:b7e1...",
  "timestamp": "2026-03-12T18:00:00Z",
  "entry_count": 500,
  "signature": "<ES256 signature over canonical form>"
}
```

---

## How This Fits the Roadmap

| Version | Trust model | What's new |
|---------|------------|------------|
| v0.1 | Declaration | Contracts declared, no cryptographic enforcement |
| v0.2 | Signed | JWT tokens, signed manifests, hash-chained audit — local verification |
| **v0.3** | **Anchored** | **Merkle trees, external checkpointing, trust level declarations, policy hooks** |
| v0.4 | Attested | Third-party attestation, witness receipts, conformance certification |

The principle: each version extends trust guarantees without requiring the previous version's deployment to change. A Bronze (v0.2) deployment remains valid. Silver (v0.3) is additive. Gold (v0.4) builds on Silver's anchoring infrastructure.

---

## Resolved Questions

1. **Checkpoint format:** Separate signed JSON with detached JWS — same pattern v0.2 uses for manifests. JWTs are bearer authorization tokens; checkpoints are archival artifacts. Different semantics, different format.

2. **Merkle tree algorithm:** SHA-256 with RFC 6962 (Certificate Transparency) structure. Battle-tested, existing library support in Python and TypeScript, defines inclusion/consistency proof formats. The reference implementations already use SHA-256 for the hash chain.

3. **Trust level in discovery:** Both surfaces, different granularity. `/.well-known/anip` exposes a compact `trust_level` summary (e.g. `"anchored"`) so callers can filter early. The manifest remains the source of truth for the full trust posture — anchoring policy, cadence, sink identifiers, policy hooks.

4. **Anchoring verification endpoint:** `GET /anip/checkpoints` — a convenience/inspection surface exposing checkpoint metadata and receipts if available. This is a helper for callers to monitor checkpoint cadence and inspect proofs, **not the authoritative trust anchor itself**. Callers should verify checkpoint artifacts independently, not blindly trust the endpoint. Optional for `signed`, available for `anchored`.

5. **Backward compatibility:** Not a constraint. There are no external dependents yet, so v0.3 may introduce clean protocol changes if they improve the trust model. v0.2 semantics are the conceptual baseline (a v0.2-style deployment is still `signed`), but not a hard wire-format compatibility promise. Clarity matters more than migration burden at this stage.

---

*This is a draft proposal. If you see something missing, wrong, or underspecified, [open an issue](https://github.com/anip-protocol/anip/issues).*
