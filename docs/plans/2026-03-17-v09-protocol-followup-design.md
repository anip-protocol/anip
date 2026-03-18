# ANIP v0.9 Protocol Follow-up Design

**Goal:** Complete the security and audit story that v0.8 started by activating the placeholders it left behind.

**Scope:** Four items in sequential implementation order. Selective checkpointing is deferred to v0.10.

**Architecture:** Each item builds on the previous. Aggregation activates write-path grouping, storage-side redaction uses that grouping as a signal, caller-class redaction extends the response-boundary layer, and proof semantics closes the client-side gap.

---

## Key Distinctions

Two distinctions must remain crisp throughout this design:

1. **Storage-side redaction vs response-boundary redaction.** Storage-side redaction determines what is persisted. Response-boundary redaction determines what a caller sees. They are independent policies applied at different points in the write and read paths. Storage-side redaction is a v0.9 write-path addition. Response-boundary redaction is a v0.8 read-path feature extended in v0.9 with caller-class awareness.

2. **Checkpoint validity vs proof regenerability.** A checkpoint remains valid even when the audit entries it covers have been deleted by retention enforcement. Proof regeneration requires live audit entries. `proof_unavailable` signals that proof regeneration is no longer possible, not that the checkpoint or the audit trail is compromised.

---

## 1. Audit Aggregation

### Purpose

Collapse repeated identical low-value denials into summary records. This activates the `repeated_low_value_denial` event class and `aggregate_only` retention tier, both of which exist as v0.8 placeholders.

### Grouping Key

Denials are grouped by the tuple:

- **actor_key** — resolved from the token subject or authenticated principal when available, `"anonymous"` for missing/invalid tokens. This handles pre-auth failures where no valid subject exists.
- **capability** — which capability was attempted, or `"_pre_auth"` for failures before capability resolution.
- **failure_type** — the `ANIPFailure.type` value (e.g., `"scope_insufficient"`).

Request parameters are excluded from the grouping key in v0.9. Normalizing request bodies for grouping adds complexity for marginal value.

### Time Window

- Fixed-width bucketed windows, configurable with a default of **60 seconds**.
- At window close, if a bucket has **>1 event** for a grouping key, emit one aggregated entry.
- If a bucket has exactly 1 event, store it as a normal entry.
- Bucketed (not rolling) because: simpler to implement consistently across runtimes, deterministic window boundaries, easier to reason about in audit inspection.

### Delayed Emission

Aggregated entries materialize at window close, not at request time. This means the audit log has a latency gap of up to one window duration for aggregated events. Individual non-aggregated events still emit immediately. This is acceptable for low-value denials but is a change from v0.8's "every request produces an immediate audit row" model and must be documented explicitly.

### Aggregated Entry Shape

```
AggregatedAuditEntry:
  entry_type: "aggregated"
  event_class: "repeated_low_value_denial"
  retention_tier: "aggregate_only"
  grouping_key:
    actor_key: string
    capability: string
    failure_type: string
  window:
    start: ISO 8601 timestamp
    end: ISO 8601 timestamp
  count: integer
  first_seen: ISO 8601 timestamp
  last_seen: ISO 8601 timestamp
  representative_detail: string | null  # bounded to 200 chars max
```

`representative_detail` is the failure detail from the first event in the window, truncated to 200 characters. Nullable for cases where the detail adds no signal (e.g., repeated malformed requests).

### Classifier Changes

The classifier itself does not change. Individual events within a window are still classified as `malformed_or_spam` or other appropriate classes. The `repeated_low_value_denial` classification is applied at aggregation time when a bucket crosses the >1 threshold. The resulting summary record carries `repeated_low_value_denial` as its event class.

### Retention

`aggregate_only` gets its own duration, distinct from `short`:

- `aggregate_only`: **P1D** (1 day)
- `short`: P7D (unchanged)

P1D is appropriate for noise — long enough to detect patterns, short enough to not accumulate.

---

## 2. Storage-Side Redaction

### Purpose

Reduce what is persisted for low-value audit events. v0.8 stores full-fidelity records for all events. v0.9 strips request parameters from low-value entries at write time.

### Which Events Are Redacted

Storage-side redaction applies to entries with event class:

- `low_risk_success`
- `malformed_or_spam`
- `repeated_low_value_denial`

It does not apply to:

- `high_risk_success` — operators need full inspection capability.
- `high_risk_denial` — denied high-risk operations are security-relevant.

### What Gets Stripped

For affected event classes, the stored entry omits:

- `parameters` — the full request body.

The stored entry keeps:

- `timestamp`
- `actor_key` / principal context
- `capability`
- `event_class`
- `retention_tier`
- `failure_type`
- Bounded failure detail suitable for storage (not coupled to response disclosure policy)
- `invocation_id`
- `sequence_number`

### Write-Path Placement

Storage-side redaction runs after classification and before persistence:

```
request -> classify -> [aggregation window] -> storage-redact -> persist
```

Response-boundary redaction (v0.8) is a separate, independent layer on the read path:

```
persist -> [response-boundary redact based on disclosure level] -> respond
```

The two redaction layers are independent. Storage-side redaction determines what hits the database. Response-boundary redaction determines what the caller sees. Neither depends on the other.

### Checkpointing

The persisted redacted entry is the canonical hashed form for checkpointing. The Merkle tree hashes what was stored. There is no separate "pre-redaction" or "full-fidelity" hash.

### Marker Field

A new field on audit entries:

```
storage_redacted: boolean (default false)
```

This lets audit consumers distinguish intentional parameter omission from missing data.

### What This Doesn't Do

- No configurable field masks — fixed policy (parameters only).
- No retroactive redaction of existing entries.

---

## 3. Caller-Class-Aware Redaction

### Purpose

Replace the single service-wide disclosure level with a two-mode model: fixed level (v0.8 behavior) or per-caller resolution via service policy.

### Two Modes

The service's `disclosure_level` configuration determines the mode:

- **Fixed mode** (`"full"`, `"reduced"`, or `"redacted"`): That level applies uniformly to all callers. This is identical to v0.8 behavior.
- **Policy mode** (`"policy"`): The effective disclosure level is resolved per-caller from the service's disclosure policy.

### Caller Class Resolution

When in policy mode, the caller class is resolved from the token:

1. If the token contains an `anip:caller_class` claim, use it.
2. If the token's scope includes a disclosure-related scope (e.g., `audit:full`), derive from scope.
3. Default: `"default"`.

The `anip:caller_class` claim is caller/issuer-supplied input. It is not trusted on its own. It is only meaningful when the service's disclosure policy contains a matching entry. An unrecognized caller class falls through to the `"default"` entry.

### Service-Side Policy

The service declares a disclosure policy at construction:

```python
disclosure_policy = {
    "internal": "full",
    "partner": "reduced",
    "default": "redacted",
}
```

This maps caller class strings to maximum allowed disclosure levels.

### Resolution Logic

```
if disclosure_level != "policy":
    effective = disclosure_level  # fixed mode
else:
    caller_class = resolve_from_token(token)
    effective = disclosure_policy.get(caller_class)
              or disclosure_policy.get("default")
              or "redacted"
```

The service is always the authority. An unrecognized caller class can never escalate disclosure.

### Discovery Posture Update

`failure_disclosure` in the discovery posture gains an optional field:

```
failure_disclosure:
  detail_level: "policy"
  caller_classes: ["internal", "partner", "default"]  # optional, informational
```

`caller_classes` advertises known classes but does not reveal the class-to-level mapping. The mapping is a service-internal concern.

### What This Doesn't Do

- No per-request disclosure negotiation (caller cannot request a specific level in the request body).
- No disclosure cascading across delegation chains (disclosure is between immediate caller and service).

---

## 4. `proof_unavailable` Client Semantics

### Purpose

Close the semantic gap from v0.8's `proof_unavailable: "audit_entries_expired"` response. Define SHOULD-level guidance for services and clients.

### Service-Side Guidance

Services SHOULD include an `expires_hint` field on checkpoint detail responses:

```
checkpoint:
  checkpoint_id: "chk-..."
  ...existing fields...
  expires_hint: "2026-06-15T00:00:00Z"
```

`expires_hint` is:

- **Best-effort and informational** — actual expiration depends on retention enforcement timing.
- **Optional** — services that don't track per-entry expiration can omit it.
- **Derived from the earliest expected expiration** of any audit entry within the checkpoint's sequence range, based on current retention policy and tier durations.

### Client-Side Guidance

1. **Clients SHOULD retrieve and cache proofs before `expires_hint`** if they need them for offline verification or compliance.
2. **`proof_unavailable: "audit_entries_expired"` is permanent.** The live audit entries needed for proof regeneration are no longer available. Retries will not produce the proof unless the deployment has an out-of-band archival path.
3. **The checkpoint remains valid.** `proof_unavailable` means the proof cannot be regenerated from live storage, not that the checkpoint is invalid or the audit trail is compromised.
4. **No retry semantics.** Unlike transient errors, this response should not trigger retry loops. Clients should handle it as a terminal state for that proof request.

### Spec Placement

This guidance belongs in SPEC.md section 6.5 (checkpoint detail endpoint) as a normative note. The `expires_hint` field is added to the `CheckpointResponse` schema as optional.

### Discovery Posture

No discovery changes needed. `proof_unavailable` is a runtime response, and `retention_enforced: true` in the posture already signals that retention is active. `expires_hint` is a per-checkpoint field, not a posture-level declaration.

### What This Doesn't Do

- No mandatory `proof_expires_at` field (SHOULD, not MUST).
- No client-side proof caching protocol (out of scope — clients decide how to cache).
- No out-of-band archival path specification (deployment concern, not protocol).
- No new error codes.

---

## Deferred to v0.10

**Selective checkpointing** — filtering which events enter the Merkle tree by event class.

This is deferred because:

- It changes what enters the Merkle tree, affecting proof semantics more deeply.
- It is the most likely to reopen checkpoint/trust design questions.
- It is easier to get wrong in a way that confuses ANIP's trust story.
- v0.9's work (especially aggregation and storage-side redaction) may reduce the pressure for selective checkpointing.

---

## Implementation Order

1. Audit aggregation — activates write-path grouping, `repeated_low_value_denial`, `aggregate_only` with P1D retention
2. Storage-side redaction — uses event class as signal, strips parameters, adds `storage_redacted` marker
3. Caller-class-aware redaction — extends response-boundary layer with policy mode, caller class resolution
4. `proof_unavailable` client semantics — spec/schema additions, `expires_hint` field, SHOULD-level guidance

Each step builds on the previous. Both Python and TypeScript runtimes are updated in each step.
