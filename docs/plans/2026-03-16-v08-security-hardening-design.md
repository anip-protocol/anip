# v0.8 Security Hardening Design

**Goal:** Turn v0.7's declared governance posture into enforceable behavior by defining the hardening vocabulary and implementing retention enforcement + failure redaction.

**Architecture:** Define three new protocol-visible enums (EventClass, RetentionTier, DisclosureLevel) in core models. Implement retention enforcement via background cleanup sweep. Implement response-boundary failure redaction driven by disclosure level. Defer aggregation, caller-class-aware redaction, storage-side redaction, and selective checkpointing to v0.9+.

**Motivation:** ANIP's audit richness can become an abuse surface. Repeated bogus invocations grow audit storage, force checkpoint churn, and create operational noise. v0.7 discloses governance posture; v0.8 starts enforcing it.

---

## New Core Models

### EventClass

Enum: `high_risk_success`, `high_risk_denial`, `low_risk_success`, `repeated_low_value_denial`, `malformed_or_spam`

Protocol-visible on audit entries. Queryable. Used to drive retention tier selection. Advisory in v0.8 — does not yet fully determine all downstream behavior.

`repeated_low_value_denial` exists in the enum but is not assigned by the v0.8 classifier. It is reserved for v0.9 aggregation.

### RetentionTier

Enum: `long`, `medium`, `short`, `aggregate_only`

Each tier maps to an ISO 8601 duration (or null for indefinite retention) via a two-layer policy model.

`aggregate_only` is a v0.8 compatibility placeholder. In v0.8 it is treated identically to `short`. True aggregation semantics — collapsing repeated events into summary records — are deferred to v0.9.

### DisclosureLevel

Enum: `full`, `reduced`, `redacted`

Applied at the response boundary to shape failure detail before it reaches the caller. These values already exist in the discovery schema for `failure_disclosure.detail_level`; this formalizes them as a reusable type.

---

## Event Classification

### Classification Function

A pure function `classifyEvent(sideEffectType, success, failureType) → EventClass` in the service package (both runtimes). Called by the service before logging — not in the audit layer.

### Classification Table

| Side-effect type | Success | Failure (auth/scope/purpose) | Failure (malformed/unknown) |
|---|---|---|---|
| `irreversible`, `transactional`, `write` | `high_risk_success` | `high_risk_denial` | `malformed_or_spam` |
| `read` | `low_risk_success` | `high_risk_denial` | `malformed_or_spam` |

All auth/scope/purpose denials are `high_risk_denial` regardless of side-effect type. A denied read is still an authority boundary event.

Failures that occur before capability resolution (invalid token, unknown capability) → `malformed_or_spam`.

### Two-Layer Retention Policy

```
classifyEvent(sideEffectType, success, failureType) → EventClass

RetentionClassPolicy:   EventClass    → RetentionTier
RetentionTierPolicy:    RetentionTier → Duration | null
```

Both layers are configurable per deployment.

**Layer 1 defaults — class → tier:**

| Event class | Default tier |
|---|---|
| `high_risk_success` | `long` |
| `high_risk_denial` | `medium` |
| `low_risk_success` | `short` |
| `repeated_low_value_denial` | `short` |
| `malformed_or_spam` | `short` |

**Layer 2 defaults — tier → duration:**

| Tier | Default duration |
|---|---|
| `long` | P365D |
| `medium` | P90D |
| `short` | P7D |
| `aggregate_only` | P7D (v0.8 placeholder, not true aggregation) |

A deployment wanting to keep denied reads longer overrides layer 1: `high_risk_denial → long`. A deployment wanting all `medium` entries kept 180 days overrides layer 2: `medium → P180D`.

---

## Retention Enforcement

### Background Cleanup Sweep

A `RetentionEnforcer` class (both runtimes) that periodically deletes expired audit entries.

- Constructed with a `StorageBackend` and an interval (default: 60 seconds)
- On each tick: `DELETE FROM audit_log WHERE expires_at IS NOT NULL AND expires_at < now()`
- Started/stopped by the service lifecycle (`service.start()` / `service.stop()`)
- **Python:** Uses `asyncio.create_task` with a sleep loop (NOT a background thread) to stay compatible with async/loop-affine storage backends
- **TypeScript:** Uses `setInterval` (already event-loop-native)

### Storage Changes

- Add `event_class TEXT`, `retention_tier TEXT`, `expires_at TEXT` columns to the `audit_log` table
- Index on `expires_at` for efficient cleanup queries
- Index on `event_class` for query filtering

### Audit Query Changes

- `query_audit_entries()` gains an optional `event_class` filter parameter
- `event_class` is threaded through all layers: storage, service `query_audit()`, and route handlers
- No change to existing filters (capability, since, invocation_id, client_reference_id, limit)

### Checkpoint Interaction

- Checkpoints continue to include all entries regardless of event class (no selective checkpointing in v0.8)
- Past checkpoint verification remains valid — checkpoint proofs reference sequence ranges and Merkle roots computed at checkpoint time
- However, live storage is no longer a full source of historical reconstruction once retention deletes rows. Deployments requiring full historical replay should configure `long` tier or null duration for relevant event classes.
- **Proof safety guard:** `_rebuild_merkle_to()` verifies that all expected rows exist before building the tree. If rows have been deleted by retention, proof generation returns a clear `audit_entries_expired` error instead of a silently wrong Merkle root.

### Audit Entry Fields at Log Time

1. Service calls `classifyEvent()` → gets `EventClass`
2. Service looks up `RetentionTier` via class policy (layer 1)
3. Service computes `expires_at` from tier duration via tier policy (layer 2), or null if duration is null
4. All three fields (`event_class`, `retention_tier`, `expires_at`) passed to `auditLog.logEntry()` alongside existing fields

---

## Failure Detail Redaction

### Redaction Function

A pure function `redactFailure(failure, disclosureLevel) → redacted failure` in the service package (both runtimes). Called at the response boundary — after the service builds the `InvokeResponse` but before it's returned to the caller.

### Redaction Behavior by Level

| Field | `full` | `reduced` | `redacted` |
|---|---|---|---|
| `failure.type` | as-is | as-is | as-is |
| `failure.detail` | as-is | truncated to 200 chars | generic message per failure type |
| `failure.retry` | as-is | as-is | as-is |
| `resolution.action` | as-is | as-is | as-is |
| `resolution.requires` | as-is | as-is | `null` |
| `resolution.grantable_by` | as-is | `null` | `null` |
| `resolution.estimated_availability` | as-is | as-is | `null` |

- `failure.type` is never redacted — callers always need the failure category for programmatic handling
- `reduced` strips `grantable_by` (reveals internal authority structure) while keeping actionable detail
- `redacted` replaces `detail` with a fixed string per failure type (e.g., `"scope_insufficient"` → `"Insufficient scope for this capability"`) and strips all resolution hints except `action`
- Generic messages are a static map in the service, not caller-controlled

### Disclosure Level Configuration

- The service owns a `DisclosureLevel` config value, set at construction
- Discovery posture reflects this value — discovery describes behavior, it is not the source of truth for it
- v0.8 applies a single service-wide disclosure level — no per-caller or per-capability variation yet
- `"policy"` is accepted but treated as `"redacted"` in v0.8 (placeholder for v0.9 caller-class-aware engine)

### Storage Separation

- Audit storage always records the full unredacted failure regardless of disclosure level
- Response redaction and storage policy are separate controls (Rule 4 from the hardening doc)

---

## Spec & Discovery Changes

### SPEC.md

- Bump protocol version to `anip/0.8`
- New section: "Security Hardening: Event Classification, Retention, and Disclosure"
  - `EventClass` enum definition and classification rules
  - `RetentionTier` enum and two-layer policy model
  - `DisclosureLevel` enum and redaction behavior table
  - Normative: services MUST assign `event_class` to audit entries
  - Normative: services MUST assign `retention_tier` to audit entries
  - Normative: services MUST compute `expires_at` when the selected tier has a finite duration
  - `expires_at` MAY be null when the retention policy specifies indefinite retention
  - Normative: services SHOULD enforce retention via periodic cleanup
  - Normative: services MUST apply disclosure-level redaction to failure responses
  - Note: `aggregate_only` tier is a v0.8 placeholder; true aggregation semantics deferred
- Update existing audit section to reference new fields
- Update roadmap

### Discovery Posture

The existing `posture.audit` block gains one new field:

```json
"audit": {
  "enabled": true,
  "signed": true,
  "queryable": true,
  "retention": "P90D",
  "retention_enforced": true
}
```

`retention_enforced: boolean` — whether the service actively deletes expired entries. This is the operational credibility signal: the difference between declaring retention and enforcing it.

### Schema Updates (`discovery.schema.json`)

- Add `retention_enforced` boolean to `posture.audit` properties

### Model Updates (`models.py` / `models.ts`)

- Add `EventClass`, `RetentionTier`, `DisclosureLevel` enums to core models
- Add `retention_enforced: bool` to `AuditPosture`

---

## v0.8 Audit Semantics Summary

These invariants must remain explicit throughout the implementation:

- Full-fidelity audit still exists in v0.8 — all events are stored with complete detail
- Retention limits lifetime — expired entries are deleted by background sweep
- Aggregation is not happening yet — each event is a distinct audit record
- Checkpoints still cover all entries — no selective checkpointing by event class
- Response redaction is separate from storage — callers may see less than what is stored

---

## Explicit Deferrals (v0.9+)

- **Audit aggregation** — collapsing repeated identical low-value failures into summary records. `repeated_low_value_denial` exists in `EventClass` but is not assigned by the v0.8 classifier. `aggregate_only` exists in `RetentionTier` but is treated as `short`.
- **Caller-class-aware redaction** — per-caller disclosure levels (anonymous vs. authenticated vs. privileged). v0.8 applies a single service-wide disclosure level.
- **Storage-side redaction** — filtering which fields are persisted in audit entries for low-value events. v0.8 always stores full-fidelity records.
- **Selective checkpointing** — filtering which events enter the Merkle tree by event class.
- **`"policy"` disclosure level enforcement** — accepted but treated as `"redacted"` in v0.8.

---

## Testing Scope

- Unit tests for `classifyEvent()` covering the full classification table
- Unit tests for `redactFailure()` covering all three disclosure levels
- Integration tests for retention enforcement (entries with expired `expires_at` are cleaned up by sweep)
- Integration tests for `event_class` query filtering
- Schema validation tests for new discovery fields (`retention_enforced`)
- Model validation tests for new enums
- Both runtimes (Python + TypeScript)
