# v0.8 Security Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement event classification, retention enforcement, and failure redaction for ANIP v0.8, turning v0.7's declared governance posture into enforceable behavior.

**Architecture:** Add EventClass, RetentionTier, and DisclosureLevel enums to core models (both runtimes). Classify every audit entry at invocation time using side-effect type and outcome. Enforce retention via a background sweep that hard-deletes expired entries. Guard proof generation against gaps — `_rebuild_merkle_to()` returns a clear error if deleted rows create an incomplete replay range. Use asyncio tasks for the Python enforcer (not threads) to stay compatible with async storage backends. Redact failure responses at the response boundary based on a service-wide disclosure level. Thread `event_class` as a queryable filter through storage, service `query_audit()`, and route handlers. Update the spec, discovery schema, canonical ANIP schema, and discovery document to reflect the new capabilities.

**Tech Stack:** Python (Pydantic, pytest, asyncio), TypeScript (Zod, vitest, better-sqlite3), JSON Schema

**Design doc:** `docs/plans/2026-03-16-v08-security-hardening-design.md`

---

### Task 1: Add Hardening Enums and Models to Core Packages

Add `EventClass`, `RetentionTier`, and `DisclosureLevel` enums to both Python and TypeScript core model packages. Add `retention_enforced` to `AuditPosture`. Update `FailureDisclosure` to use `DisclosureLevel` values (add `"reduced"`). Export new types.

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/models.py`
- Modify: `packages/python/anip-core/src/anip_core/__init__.py`
- Modify: `packages/typescript/core/src/models.ts`
- Test: `packages/python/anip-core/tests/test_models.py`
- Test: `packages/typescript/core/tests/models.test.ts`

**Step 1: Write the failing tests -- Python**

Add these tests to `packages/python/anip-core/tests/test_models.py`:

```python
# --- v0.8 Hardening Models ---


def test_event_class_enum_values():
    from anip_core import EventClass

    assert EventClass.HIGH_RISK_SUCCESS == "high_risk_success"
    assert EventClass.HIGH_RISK_DENIAL == "high_risk_denial"
    assert EventClass.LOW_RISK_SUCCESS == "low_risk_success"
    assert EventClass.REPEATED_LOW_VALUE_DENIAL == "repeated_low_value_denial"
    assert EventClass.MALFORMED_OR_SPAM == "malformed_or_spam"


def test_retention_tier_enum_values():
    from anip_core import RetentionTier

    assert RetentionTier.LONG == "long"
    assert RetentionTier.MEDIUM == "medium"
    assert RetentionTier.SHORT == "short"
    assert RetentionTier.AGGREGATE_ONLY == "aggregate_only"


def test_disclosure_level_enum_values():
    from anip_core import DisclosureLevel

    assert DisclosureLevel.FULL == "full"
    assert DisclosureLevel.REDUCED == "reduced"
    assert DisclosureLevel.REDACTED == "redacted"


def test_audit_posture_retention_enforced():
    from anip_core import AuditPosture

    posture = AuditPosture()
    assert posture.retention_enforced is False

    posture2 = AuditPosture(retention_enforced=True)
    assert posture2.retention_enforced is True


def test_failure_disclosure_accepts_reduced():
    from anip_core import FailureDisclosure

    fd = FailureDisclosure(detail_level="reduced")
    assert fd.detail_level == "reduced"
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest packages/python/anip-core/tests/test_models.py -x -q`
Expected: FAIL -- `ImportError: cannot import name 'EventClass'`

**Step 3: Write the failing tests -- TypeScript**

Add these tests to `packages/typescript/core/tests/models.test.ts`:

```typescript
// --- v0.8 Hardening Models ---

describe("v0.8 hardening enums", () => {
  it("EventClass parses all values", () => {
    for (const val of [
      "high_risk_success",
      "high_risk_denial",
      "low_risk_success",
      "repeated_low_value_denial",
      "malformed_or_spam",
    ]) {
      expect(EventClass.parse(val)).toBe(val);
    }
  });

  it("EventClass rejects invalid values", () => {
    expect(() => EventClass.parse("unknown")).toThrow();
  });

  it("RetentionTier parses all values", () => {
    for (const val of ["long", "medium", "short", "aggregate_only"]) {
      expect(RetentionTier.parse(val)).toBe(val);
    }
  });

  it("DisclosureLevel parses all values", () => {
    for (const val of ["full", "reduced", "redacted"]) {
      expect(DisclosureLevel.parse(val)).toBe(val);
    }
  });

  it("AuditPosture includes retention_enforced", () => {
    const posture = AuditPosture.parse({});
    expect(posture.retention_enforced).toBe(false);

    const posture2 = AuditPosture.parse({ retention_enforced: true });
    expect(posture2.retention_enforced).toBe(true);
  });

  it("FailureDisclosure accepts reduced", () => {
    const fd = FailureDisclosure.parse({ detail_level: "reduced" });
    expect(fd.detail_level).toBe("reduced");
  });
});
```

Add the new imports at the top of the test file alongside existing imports:

```typescript
import { EventClass, RetentionTier, DisclosureLevel } from "@anip/core";
```

**Step 4: Run tests to verify they fail**

Run: `cd packages/typescript && npx tsc -b core && npx vitest run core/tests/models.test.ts`
Expected: FAIL -- compile error, `EventClass` not exported

**Step 5: Implement -- Python models**

In `packages/python/anip-core/src/anip_core/models.py`, add these after the `TrustPosture` class (after line 236, before the `# --- Discovery Posture (v0.7) ---` comment):

```python
# --- v0.8 Security Hardening ---


class EventClass(str, Enum):
    HIGH_RISK_SUCCESS = "high_risk_success"
    HIGH_RISK_DENIAL = "high_risk_denial"
    LOW_RISK_SUCCESS = "low_risk_success"
    REPEATED_LOW_VALUE_DENIAL = "repeated_low_value_denial"
    MALFORMED_OR_SPAM = "malformed_or_spam"


class RetentionTier(str, Enum):
    LONG = "long"
    MEDIUM = "medium"
    SHORT = "short"
    AGGREGATE_ONLY = "aggregate_only"


class DisclosureLevel(str, Enum):
    FULL = "full"
    REDUCED = "reduced"
    REDACTED = "redacted"
```

In `AuditPosture` (currently at line 242), add a new field:

```python
class AuditPosture(BaseModel):
    enabled: bool = True
    signed: bool = True
    queryable: bool = True
    retention: str | None = None
    retention_enforced: bool = False
```

In `FailureDisclosure` (currently at line 267), update `detail_level` to accept `"reduced"`:

```python
class FailureDisclosure(BaseModel):
    detail_level: Literal["full", "reduced", "redacted", "policy"] = "redacted"
```

**Step 6: Implement -- Python exports**

In `packages/python/anip-core/src/anip_core/__init__.py`, add to the imports from `.models`:

```python
    DisclosureLevel,
    EventClass,
    RetentionTier,
```

(Keep alphabetical order with existing exports.)

**Step 7: Implement -- TypeScript models**

In `packages/typescript/core/src/models.ts`, add after the `TrustPosture` schema (after line 223, before the `// Discovery Posture (v0.7)` comment):

```typescript
// ---------------------------------------------------------------------------
// Security Hardening (v0.8)
// ---------------------------------------------------------------------------

export const EventClass = z.enum([
  "high_risk_success",
  "high_risk_denial",
  "low_risk_success",
  "repeated_low_value_denial",
  "malformed_or_spam",
]);
export type EventClass = z.infer<typeof EventClass>;

export const RetentionTier = z.enum([
  "long",
  "medium",
  "short",
  "aggregate_only",
]);
export type RetentionTier = z.infer<typeof RetentionTier>;

export const DisclosureLevel = z.enum([
  "full",
  "reduced",
  "redacted",
]);
export type DisclosureLevel = z.infer<typeof DisclosureLevel>;
```

In `AuditPosture` (currently at line 229), add `retention_enforced`:

```typescript
export const AuditPosture = z.object({
  enabled: z.boolean().default(true),
  signed: z.boolean().default(true),
  queryable: z.boolean().default(true),
  retention: z.string().nullable().default(null),
  retention_enforced: z.boolean().default(false),
});
```

In `FailureDisclosure` (currently at line 258), update `detail_level` to include `"reduced"`:

```typescript
export const FailureDisclosure = z.object({
  detail_level: z.enum(["full", "reduced", "redacted", "policy"]).default("redacted"),
});
```

TypeScript exports are automatic via `export * from "./models.js"` in `index.ts`.

**Step 8: Run all tests**

Run: `.venv/bin/python -m pytest packages/python -x -q`
Expected: All pass

Run: `cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose`
Expected: All pass

**Step 9: Commit**

```
git add packages/python/anip-core/src/anip_core/models.py \
       packages/python/anip-core/src/anip_core/__init__.py \
       packages/python/anip-core/tests/test_models.py \
       packages/typescript/core/src/models.ts \
       packages/typescript/core/tests/models.test.ts
git commit -m "feat(core): add EventClass, RetentionTier, DisclosureLevel enums (v0.8)"
```

---

### Task 2: Bump Protocol Version to 0.8

Update protocol version and manifest version constants in both runtimes. Update default discovery posture version in manifest metadata.

**Files:**
- Modify: `packages/python/anip-core/src/anip_core/constants.py`
- Modify: `packages/typescript/core/src/constants.ts`
- Modify: `packages/python/anip-core/src/anip_core/models.py` (ManifestMetadata, ANIPManifest defaults)
- Modify: `packages/typescript/core/src/models.ts` (ManifestMetadata, ANIPManifest defaults)
- Modify: `examples/anip-ts/package.json` (version field)

**Step 1: Update Python constants**

In `packages/python/anip-core/src/anip_core/constants.py`, change:

```python
PROTOCOL_VERSION = "anip/0.8"
MANIFEST_VERSION = "0.8.0"
```

**Step 2: Update TypeScript constants**

In `packages/typescript/core/src/constants.ts`, change:

```typescript
export const PROTOCOL_VERSION = "anip/0.8";
export const MANIFEST_VERSION = "0.8.0";
```

**Step 3: Update Python model defaults**

In `packages/python/anip-core/src/anip_core/models.py`:

- `ManifestMetadata.version` default: `"0.7.0"` -> `"0.8.0"`
- `ANIPManifest.protocol` default: `"anip/0.7"` -> `"anip/0.8"`

**Step 4: Update TypeScript model defaults**

In `packages/typescript/core/src/models.ts`:

- `ManifestMetadata`: `version: z.string().default("0.8.0")`
- `ANIPManifest`: `protocol: z.string().default("anip/0.8")`

**Step 5: Update example package**

In `examples/anip-ts/package.json`, bump the `version` field to `"0.8.0"`.

**Step 6: Run all tests**

Run: `.venv/bin/python -m pytest packages/python -x -q`
Run: `cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose`

Expected: All pass. Some tests that check exact protocol version strings may need updating -- fix any that assert `"anip/0.7"` or `"0.7.0"`.

**Step 7: Commit**

```
git add packages/python/anip-core/src/anip_core/constants.py \
       packages/typescript/core/src/constants.ts \
       packages/python/anip-core/src/anip_core/models.py \
       packages/typescript/core/src/models.ts \
       examples/anip-ts/package.json
git commit -m "chore: bump protocol version to anip/0.8"
```

---

### Task 3: Event Classification Function

Implement `classify_event()` / `classifyEvent()` as a pure function in both service packages. This function takes side-effect type, success, and failure type and returns an `EventClass`.

**Files:**
- Create: `packages/python/anip-service/src/anip_service/classification.py`
- Create: `packages/python/anip-service/tests/test_classification.py`
- Create: `packages/typescript/service/src/classification.ts`
- Create: `packages/typescript/service/tests/classification.test.ts`

**Step 1: Write the failing tests -- Python**

Create `packages/python/anip-service/tests/test_classification.py`:

```python
"""Tests for event classification (v0.8)."""

import pytest

from anip_service.classification import classify_event


class TestClassifyEvent:
    """Classification table from design doc."""

    # --- Success cases ---

    def test_write_success(self):
        assert classify_event("write", True, None) == "high_risk_success"

    def test_irreversible_success(self):
        assert classify_event("irreversible", True, None) == "high_risk_success"

    def test_transactional_success(self):
        assert classify_event("transactional", True, None) == "high_risk_success"

    def test_read_success(self):
        assert classify_event("read", True, None) == "low_risk_success"

    # --- Auth/scope/purpose denial ---

    def test_write_auth_denial(self):
        assert classify_event("write", False, "invalid_token") == "high_risk_denial"

    def test_write_scope_denial(self):
        assert classify_event("write", False, "scope_insufficient") == "high_risk_denial"

    def test_write_purpose_denial(self):
        assert classify_event("write", False, "purpose_mismatch") == "high_risk_denial"

    def test_read_auth_denial(self):
        assert classify_event("read", False, "invalid_token") == "high_risk_denial"

    def test_read_scope_denial(self):
        assert classify_event("read", False, "scope_insufficient") == "high_risk_denial"

    def test_read_insufficient_authority(self):
        assert classify_event("read", False, "insufficient_authority") == "high_risk_denial"

    # --- Malformed/unknown ---

    def test_unknown_capability(self):
        assert classify_event(None, False, "unknown_capability") == "malformed_or_spam"

    def test_streaming_not_supported(self):
        assert classify_event("read", False, "streaming_not_supported") == "malformed_or_spam"

    def test_write_internal_error(self):
        assert classify_event("write", False, "internal_error") == "malformed_or_spam"

    # --- Pre-resolution failures (no side_effect_type) ---

    def test_no_side_effect_invalid_token(self):
        assert classify_event(None, False, "invalid_token") == "malformed_or_spam"

    def test_no_side_effect_unknown(self):
        assert classify_event(None, False, "unknown_capability") == "malformed_or_spam"

    # --- Handler-thrown ANIPError ---

    def test_handler_thrown_anip_error(self):
        """Handler ANIPErrors (e.g. not_found) on a write capability = high_risk_denial."""
        assert classify_event("write", False, "not_found") == "high_risk_denial"

    def test_handler_thrown_anip_error_read(self):
        """Handler ANIPErrors on a read capability = high_risk_denial."""
        assert classify_event("read", False, "not_found") == "high_risk_denial"
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest packages/python/anip-service/tests/test_classification.py -x -q`
Expected: FAIL -- `ModuleNotFoundError: No module named 'anip_service.classification'`

**Step 3: Write the failing tests -- TypeScript**

Create `packages/typescript/service/tests/classification.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { classifyEvent } from "../src/classification.js";

describe("classifyEvent", () => {
  // --- Success cases ---
  it("write + success = high_risk_success", () => {
    expect(classifyEvent("write", true, null)).toBe("high_risk_success");
  });

  it("irreversible + success = high_risk_success", () => {
    expect(classifyEvent("irreversible", true, null)).toBe("high_risk_success");
  });

  it("transactional + success = high_risk_success", () => {
    expect(classifyEvent("transactional", true, null)).toBe("high_risk_success");
  });

  it("read + success = low_risk_success", () => {
    expect(classifyEvent("read", true, null)).toBe("low_risk_success");
  });

  // --- Auth/scope/purpose denial ---
  it("write + scope_insufficient = high_risk_denial", () => {
    expect(classifyEvent("write", false, "scope_insufficient")).toBe("high_risk_denial");
  });

  it("read + invalid_token = high_risk_denial", () => {
    expect(classifyEvent("read", false, "invalid_token")).toBe("high_risk_denial");
  });

  it("read + scope_insufficient = high_risk_denial", () => {
    expect(classifyEvent("read", false, "scope_insufficient")).toBe("high_risk_denial");
  });

  // --- Malformed/unknown ---
  it("null + unknown_capability = malformed_or_spam", () => {
    expect(classifyEvent(null, false, "unknown_capability")).toBe("malformed_or_spam");
  });

  it("read + streaming_not_supported = malformed_or_spam", () => {
    expect(classifyEvent("read", false, "streaming_not_supported")).toBe("malformed_or_spam");
  });

  it("write + internal_error = malformed_or_spam", () => {
    expect(classifyEvent("write", false, "internal_error")).toBe("malformed_or_spam");
  });

  // --- Pre-resolution failures ---
  it("null + invalid_token = malformed_or_spam", () => {
    expect(classifyEvent(null, false, "invalid_token")).toBe("malformed_or_spam");
  });

  // --- Handler-thrown errors (not malformed, not internal) ---
  it("write + not_found = high_risk_denial", () => {
    expect(classifyEvent("write", false, "not_found")).toBe("high_risk_denial");
  });

  it("read + not_found = high_risk_denial", () => {
    expect(classifyEvent("read", false, "not_found")).toBe("high_risk_denial");
  });
});
```

**Step 4: Run tests to verify they fail**

Run: `cd packages/typescript && npx tsc -b service && npx vitest run service/tests/classification.test.ts`
Expected: FAIL -- cannot find module

**Step 5: Implement -- Python**

Create `packages/python/anip-service/src/anip_service/classification.py`:

```python
"""Event classification for v0.8 security hardening.

Classifies audit events by risk level based on the capability's side-effect
type and the invocation outcome. Used to drive retention tier selection.
"""

# Failure types that indicate malformed/spam requests, not authority-level events
_MALFORMED_FAILURE_TYPES = frozenset({
    "unknown_capability",
    "streaming_not_supported",
    "internal_error",
})

# Side-effect types that indicate high-risk operations
_HIGH_RISK_SIDE_EFFECTS = frozenset({
    "write",
    "irreversible",
    "transactional",
})


def classify_event(
    side_effect_type: str | None,
    success: bool,
    failure_type: str | None,
) -> str:
    """Classify an invocation event for retention and audit purposes.

    Args:
        side_effect_type: The capability's side-effect type (read/write/irreversible/transactional),
            or None if the failure occurred before capability resolution.
        success: Whether the invocation succeeded.
        failure_type: The failure type string if success is False, else None.

    Returns:
        An EventClass value string.
    """
    # Pre-resolution failures (no capability context)
    if side_effect_type is None:
        return "malformed_or_spam"

    # Successful invocations
    if success:
        if side_effect_type in _HIGH_RISK_SIDE_EFFECTS:
            return "high_risk_success"
        return "low_risk_success"

    # Failed invocations
    if failure_type in _MALFORMED_FAILURE_TYPES:
        return "malformed_or_spam"

    # All other failures are authority-significant denials
    return "high_risk_denial"
```

**Step 6: Implement -- TypeScript**

Create `packages/typescript/service/src/classification.ts`:

```typescript
/**
 * Event classification for v0.8 security hardening.
 *
 * Classifies audit events by risk level based on the capability's side-effect
 * type and the invocation outcome. Used to drive retention tier selection.
 */

const MALFORMED_FAILURE_TYPES = new Set([
  "unknown_capability",
  "streaming_not_supported",
  "internal_error",
]);

const HIGH_RISK_SIDE_EFFECTS = new Set([
  "write",
  "irreversible",
  "transactional",
]);

/**
 * Classify an invocation event for retention and audit purposes.
 *
 * @param sideEffectType - The capability's side-effect type, or null if failure occurred
 *   before capability resolution.
 * @param success - Whether the invocation succeeded.
 * @param failureType - The failure type string if success is false, else null.
 * @returns An EventClass value string.
 */
export function classifyEvent(
  sideEffectType: string | null,
  success: boolean,
  failureType: string | null,
): string {
  // Pre-resolution failures (no capability context)
  if (sideEffectType === null) {
    return "malformed_or_spam";
  }

  // Successful invocations
  if (success) {
    if (HIGH_RISK_SIDE_EFFECTS.has(sideEffectType)) {
      return "high_risk_success";
    }
    return "low_risk_success";
  }

  // Failed invocations
  if (failureType !== null && MALFORMED_FAILURE_TYPES.has(failureType)) {
    return "malformed_or_spam";
  }

  // All other failures are authority-significant denials
  return "high_risk_denial";
}
```

**Step 7: Run all tests**

Run: `.venv/bin/python -m pytest packages/python -x -q`
Run: `cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose`
Expected: All pass

**Step 8: Commit**

```
git add packages/python/anip-service/src/anip_service/classification.py \
       packages/python/anip-service/tests/test_classification.py \
       packages/typescript/service/src/classification.ts \
       packages/typescript/service/tests/classification.test.ts
git commit -m "feat(service): add event classification function (v0.8)"
```

---

### Task 4: Retention Policy Config and expires_at Computation

Implement the two-layer retention policy model: EventClass -> RetentionTier mapping, and RetentionTier -> Duration mapping. Add a function that computes `expires_at` from the current time and the tier's duration. This is used at audit log time.

**Files:**
- Create: `packages/python/anip-service/src/anip_service/retention.py`
- Create: `packages/python/anip-service/tests/test_retention.py`
- Create: `packages/typescript/service/src/retention.ts`
- Create: `packages/typescript/service/tests/retention.test.ts`

**Step 1: Write the failing tests -- Python**

Create `packages/python/anip-service/tests/test_retention.py`:

```python
"""Tests for retention policy (v0.8)."""

from datetime import datetime, timezone

from anip_service.retention import RetentionPolicy, DEFAULT_CLASS_TO_TIER, DEFAULT_TIER_TO_DURATION


class TestRetentionPolicy:

    def test_default_class_to_tier_mapping(self):
        assert DEFAULT_CLASS_TO_TIER["high_risk_success"] == "long"
        assert DEFAULT_CLASS_TO_TIER["high_risk_denial"] == "medium"
        assert DEFAULT_CLASS_TO_TIER["low_risk_success"] == "short"
        assert DEFAULT_CLASS_TO_TIER["repeated_low_value_denial"] == "short"
        assert DEFAULT_CLASS_TO_TIER["malformed_or_spam"] == "short"

    def test_default_tier_to_duration(self):
        assert DEFAULT_TIER_TO_DURATION["long"] == "P365D"
        assert DEFAULT_TIER_TO_DURATION["medium"] == "P90D"
        assert DEFAULT_TIER_TO_DURATION["short"] == "P7D"
        assert DEFAULT_TIER_TO_DURATION["aggregate_only"] == "P7D"

    def test_resolve_tier(self):
        policy = RetentionPolicy()
        assert policy.resolve_tier("high_risk_success") == "long"
        assert policy.resolve_tier("malformed_or_spam") == "short"

    def test_resolve_tier_custom_mapping(self):
        policy = RetentionPolicy(
            class_to_tier={"high_risk_denial": "long"},
        )
        assert policy.resolve_tier("high_risk_denial") == "long"
        # Other classes still use defaults
        assert policy.resolve_tier("malformed_or_spam") == "short"

    def test_compute_expires_at(self):
        policy = RetentionPolicy()
        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        expires = policy.compute_expires_at("short", now)
        assert expires is not None
        # P7D = 7 days later
        expected = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        assert expires == expected.isoformat()

    def test_compute_expires_at_long(self):
        policy = RetentionPolicy()
        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        expires = policy.compute_expires_at("long", now)
        assert expires is not None
        expected = datetime(2027, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        assert expires == expected.isoformat()

    def test_compute_expires_at_null_duration(self):
        policy = RetentionPolicy(
            tier_to_duration={"long": None},
        )
        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        expires = policy.compute_expires_at("long", now)
        assert expires is None

    def test_aggregate_only_treated_as_short_in_v08(self):
        policy = RetentionPolicy()
        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        short_expires = policy.compute_expires_at("short", now)
        agg_expires = policy.compute_expires_at("aggregate_only", now)
        assert short_expires == agg_expires

    def test_full_pipeline(self):
        """classify -> resolve tier -> compute expires_at."""
        policy = RetentionPolicy()
        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        tier = policy.resolve_tier("malformed_or_spam")
        expires = policy.compute_expires_at(tier, now)
        assert tier == "short"
        assert expires is not None
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest packages/python/anip-service/tests/test_retention.py -x -q`
Expected: FAIL -- `ModuleNotFoundError`

**Step 3: Write the failing tests -- TypeScript**

Create `packages/typescript/service/tests/retention.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import {
  RetentionPolicy,
  DEFAULT_CLASS_TO_TIER,
  DEFAULT_TIER_TO_DURATION,
} from "../src/retention.js";

describe("RetentionPolicy", () => {
  it("default class-to-tier mapping", () => {
    expect(DEFAULT_CLASS_TO_TIER.high_risk_success).toBe("long");
    expect(DEFAULT_CLASS_TO_TIER.high_risk_denial).toBe("medium");
    expect(DEFAULT_CLASS_TO_TIER.low_risk_success).toBe("short");
    expect(DEFAULT_CLASS_TO_TIER.repeated_low_value_denial).toBe("short");
    expect(DEFAULT_CLASS_TO_TIER.malformed_or_spam).toBe("short");
  });

  it("default tier-to-duration mapping", () => {
    expect(DEFAULT_TIER_TO_DURATION.long).toBe("P365D");
    expect(DEFAULT_TIER_TO_DURATION.medium).toBe("P90D");
    expect(DEFAULT_TIER_TO_DURATION.short).toBe("P7D");
    expect(DEFAULT_TIER_TO_DURATION.aggregate_only).toBe("P7D");
  });

  it("resolveTier uses defaults", () => {
    const policy = new RetentionPolicy();
    expect(policy.resolveTier("high_risk_success")).toBe("long");
    expect(policy.resolveTier("malformed_or_spam")).toBe("short");
  });

  it("resolveTier accepts custom class-to-tier override", () => {
    const policy = new RetentionPolicy({
      classToTier: { high_risk_denial: "long" },
    });
    expect(policy.resolveTier("high_risk_denial")).toBe("long");
    expect(policy.resolveTier("malformed_or_spam")).toBe("short");
  });

  it("computeExpiresAt for short tier", () => {
    const policy = new RetentionPolicy();
    const now = new Date("2026-03-16T12:00:00Z");
    const expires = policy.computeExpiresAt("short", now);
    expect(expires).toBe("2026-03-23T12:00:00.000Z");
  });

  it("computeExpiresAt for long tier", () => {
    const policy = new RetentionPolicy();
    const now = new Date("2026-03-16T12:00:00Z");
    const expires = policy.computeExpiresAt("long", now);
    expect(expires).toBe("2027-03-16T12:00:00.000Z");
  });

  it("computeExpiresAt returns null for null duration", () => {
    const policy = new RetentionPolicy({
      tierToDuration: { long: null },
    });
    const now = new Date("2026-03-16T12:00:00Z");
    expect(policy.computeExpiresAt("long", now)).toBeNull();
  });

  it("aggregate_only treated as short in v0.8", () => {
    const policy = new RetentionPolicy();
    const now = new Date("2026-03-16T12:00:00Z");
    expect(policy.computeExpiresAt("aggregate_only", now))
      .toBe(policy.computeExpiresAt("short", now));
  });
});
```

**Step 4: Run tests to verify they fail**

Run: `cd packages/typescript && npx tsc -b service && npx vitest run service/tests/retention.test.ts`
Expected: FAIL

**Step 5: Implement -- Python**

Create `packages/python/anip-service/src/anip_service/retention.py`:

```python
"""Retention policy for v0.8 security hardening.

Two-layer policy model:
  1. EventClass -> RetentionTier  (which tier does this event belong to?)
  2. RetentionTier -> Duration    (how long is that tier kept?)

Both layers are configurable per deployment.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

DEFAULT_CLASS_TO_TIER: dict[str, str] = {
    "high_risk_success": "long",
    "high_risk_denial": "medium",
    "low_risk_success": "short",
    "repeated_low_value_denial": "short",
    "malformed_or_spam": "short",
}

DEFAULT_TIER_TO_DURATION: dict[str, str | None] = {
    "long": "P365D",
    "medium": "P90D",
    "short": "P7D",
    # aggregate_only is a v0.8 compatibility placeholder -- not true aggregation.
    # Treated identically to "short" in v0.8.
    "aggregate_only": "P7D",
}

# Simple ISO 8601 duration parser (days only -- sufficient for retention)
_DURATION_RE = re.compile(r"^P(\d+)D$")


def _parse_iso_duration_days(duration: str) -> int:
    """Parse an ISO 8601 duration like 'P7D' into days."""
    m = _DURATION_RE.match(duration)
    if not m:
        raise ValueError(f"Unsupported ISO 8601 duration: {duration!r}. Only PnD format supported.")
    return int(m.group(1))


class RetentionPolicy:
    """Two-layer retention policy: EventClass -> Tier -> Duration."""

    def __init__(
        self,
        *,
        class_to_tier: dict[str, str] | None = None,
        tier_to_duration: dict[str, str | None] | None = None,
    ) -> None:
        self._class_to_tier = {**DEFAULT_CLASS_TO_TIER, **(class_to_tier or {})}
        self._tier_to_duration = {**DEFAULT_TIER_TO_DURATION, **(tier_to_duration or {})}

    def resolve_tier(self, event_class: str) -> str:
        """Map an EventClass to a RetentionTier."""
        return self._class_to_tier.get(event_class, "short")

    def compute_expires_at(self, tier: str, now: datetime | None = None) -> str | None:
        """Compute the expiry timestamp for a given tier.

        Returns ISO 8601 timestamp string, or None if the tier has indefinite retention.
        """
        now = now or datetime.now(timezone.utc)
        duration = self._tier_to_duration.get(tier)
        if duration is None:
            return None
        days = _parse_iso_duration_days(duration)
        expires = now + timedelta(days=days)
        return expires.isoformat()
```

**Step 6: Implement -- TypeScript**

Create `packages/typescript/service/src/retention.ts`:

```typescript
/**
 * Retention policy for v0.8 security hardening.
 *
 * Two-layer policy model:
 *   1. EventClass -> RetentionTier  (which tier does this event belong to?)
 *   2. RetentionTier -> Duration    (how long is that tier kept?)
 *
 * Both layers are configurable per deployment.
 */

export const DEFAULT_CLASS_TO_TIER: Record<string, string> = {
  high_risk_success: "long",
  high_risk_denial: "medium",
  low_risk_success: "short",
  repeated_low_value_denial: "short",
  malformed_or_spam: "short",
};

export const DEFAULT_TIER_TO_DURATION: Record<string, string | null> = {
  long: "P365D",
  medium: "P90D",
  short: "P7D",
  // aggregate_only is a v0.8 compatibility placeholder -- not true aggregation.
  // Treated identically to "short" in v0.8.
  aggregate_only: "P7D",
};

const DURATION_RE = /^P(\d+)D$/;

function parseIsoDurationDays(duration: string): number {
  const m = duration.match(DURATION_RE);
  if (!m) {
    throw new Error(
      `Unsupported ISO 8601 duration: '${duration}'. Only PnD format supported.`,
    );
  }
  return parseInt(m[1], 10);
}

export class RetentionPolicy {
  private _classToTier: Record<string, string>;
  private _tierToDuration: Record<string, string | null>;

  constructor(opts?: {
    classToTier?: Record<string, string>;
    tierToDuration?: Record<string, string | null>;
  }) {
    this._classToTier = { ...DEFAULT_CLASS_TO_TIER, ...(opts?.classToTier ?? {}) };
    this._tierToDuration = { ...DEFAULT_TIER_TO_DURATION, ...(opts?.tierToDuration ?? {}) };
  }

  resolveTier(eventClass: string): string {
    return this._classToTier[eventClass] ?? "short";
  }

  computeExpiresAt(tier: string, now?: Date): string | null {
    const ts = now ?? new Date();
    const duration = this._tierToDuration[tier];
    if (duration === undefined || duration === null) {
      return null;
    }
    const days = parseIsoDurationDays(duration);
    const expires = new Date(ts.getTime() + days * 24 * 60 * 60 * 1000);
    return expires.toISOString();
  }
}
```

**Step 7: Run all tests**

Run: `.venv/bin/python -m pytest packages/python -x -q`
Run: `cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose`
Expected: All pass

**Step 8: Commit**

```
git add packages/python/anip-service/src/anip_service/retention.py \
       packages/python/anip-service/tests/test_retention.py \
       packages/typescript/service/src/retention.ts \
       packages/typescript/service/tests/retention.test.ts
git commit -m "feat(service): add two-layer retention policy model (v0.8)"
```

---

### Task 5: Add event_class, retention_tier, expires_at to Storage and Audit

Update both storage backends to accept, store, index, and query the three new audit fields. Update audit log entry construction to pass them through. Update InMemoryStorage and SQLiteStorage in both runtimes.

**Files:**
- Modify: `packages/python/anip-server/src/anip_server/storage.py`
- Modify: `packages/python/anip-server/src/anip_server/audit.py`
- Modify: `packages/typescript/server/src/sqlite-worker.ts`
- Modify: `packages/typescript/server/src/storage.ts`
- Modify: `packages/typescript/server/src/audit.ts`
- Test: `packages/python/anip-server/tests/test_storage.py`
- Test: `packages/python/anip-server/tests/test_audit.py`
- Test: `packages/typescript/server/tests/storage.test.ts`
- Test: `packages/typescript/server/tests/audit.test.ts`

**Step 1: Write the failing tests -- Python storage**

Add to `packages/python/anip-server/tests/test_storage.py`:

```python
@pytest.mark.asyncio
async def test_store_and_query_audit_entry_with_event_class(sqlite_storage):
    """v0.8: audit entries include event_class, retention_tier, expires_at."""
    entry = {
        "sequence_number": 1,
        "timestamp": "2026-03-16T12:00:00Z",
        "capability": "test.cap",
        "token_id": "t1",
        "issuer": "svc",
        "subject": "agent",
        "root_principal": "human",
        "parameters": None,
        "success": True,
        "result_summary": None,
        "failure_type": None,
        "cost_actual": None,
        "delegation_chain": None,
        "invocation_id": "inv-000000000001",
        "client_reference_id": None,
        "stream_summary": None,
        "previous_hash": "sha256:0000",
        "signature": None,
        "event_class": "high_risk_success",
        "retention_tier": "long",
        "expires_at": "2027-03-16T12:00:00Z",
    }
    await sqlite_storage.store_audit_entry(entry)
    rows = await sqlite_storage.query_audit_entries(capability="test.cap")
    assert len(rows) == 1
    assert rows[0]["event_class"] == "high_risk_success"
    assert rows[0]["retention_tier"] == "long"
    assert rows[0]["expires_at"] == "2027-03-16T12:00:00Z"


@pytest.mark.asyncio
async def test_query_audit_entries_by_event_class(sqlite_storage):
    """v0.8: query filtering by event_class."""
    base = {
        "timestamp": "2026-03-16T12:00:00Z",
        "capability": "test.cap",
        "token_id": "t1",
        "issuer": "svc",
        "subject": "agent",
        "root_principal": "human",
        "parameters": None,
        "success": True,
        "result_summary": None,
        "failure_type": None,
        "cost_actual": None,
        "delegation_chain": None,
        "invocation_id": None,
        "client_reference_id": None,
        "stream_summary": None,
        "previous_hash": "sha256:0000",
        "signature": None,
        "retention_tier": "short",
        "expires_at": "2026-03-23T12:00:00Z",
    }
    await sqlite_storage.store_audit_entry({**base, "sequence_number": 1, "event_class": "high_risk_success"})
    await sqlite_storage.store_audit_entry({**base, "sequence_number": 2, "event_class": "malformed_or_spam"})
    await sqlite_storage.store_audit_entry({**base, "sequence_number": 3, "event_class": "high_risk_success"})

    rows = await sqlite_storage.query_audit_entries(event_class="high_risk_success")
    assert len(rows) == 2
    assert all(r["event_class"] == "high_risk_success" for r in rows)


@pytest.mark.asyncio
async def test_delete_expired_audit_entries(sqlite_storage):
    """v0.8: retention enforcer can delete expired entries."""
    base = {
        "timestamp": "2026-03-16T12:00:00Z",
        "capability": "test.cap",
        "token_id": "t1",
        "issuer": "svc",
        "subject": "agent",
        "root_principal": "human",
        "parameters": None,
        "success": True,
        "result_summary": None,
        "failure_type": None,
        "cost_actual": None,
        "delegation_chain": None,
        "invocation_id": None,
        "client_reference_id": None,
        "stream_summary": None,
        "previous_hash": "sha256:0000",
        "signature": None,
        "event_class": "malformed_or_spam",
        "retention_tier": "short",
    }
    await sqlite_storage.store_audit_entry({**base, "sequence_number": 1, "expires_at": "2026-03-10T00:00:00Z"})
    await sqlite_storage.store_audit_entry({**base, "sequence_number": 2, "expires_at": "2026-03-20T00:00:00Z"})
    await sqlite_storage.store_audit_entry({**base, "sequence_number": 3, "expires_at": None})

    deleted = await sqlite_storage.delete_expired_audit_entries("2026-03-16T12:00:00Z")
    assert deleted == 1

    remaining = await sqlite_storage.query_audit_entries()
    assert len(remaining) == 2
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest packages/python/anip-server/tests/test_storage.py -x -q -k "event_class or expired"`
Expected: FAIL -- column or parameter not recognized

**Step 3: Implement -- Python storage.py**

In `packages/python/anip-server/src/anip_server/storage.py`:

1. **StorageBackend protocol** -- add `event_class` to `query_audit_entries` signature and add `delete_expired_audit_entries` method.

2. **InMemoryStorage** -- update `query_audit_entries` to handle `event_class` filter. Add `delete_expired_audit_entries`.

3. **SQLiteStorage CREATE TABLE** -- add three columns after `signature TEXT`:
   `event_class TEXT`, `retention_tier TEXT`, `expires_at TEXT`

4. **Add indexes** after the existing index block:
   `CREATE INDEX IF NOT EXISTS idx_audit_event_class ON audit_log(event_class);`
   `CREATE INDEX IF NOT EXISTS idx_audit_expires_at ON audit_log(expires_at);`

5. **Migration block** -- add ALTER TABLE statements for each new column (same pattern as invocation_id migration).

6. **_sync_store_audit_entry** -- add the three new columns to the INSERT statement and values tuple.

7. **_sync_query_audit_entries** -- add `event_class` filter parameter and condition.

8. **Add `_sync_delete_expired_audit_entries`** method and async wrapper:
   `DELETE FROM audit_log WHERE expires_at IS NOT NULL AND expires_at < ?`

**Step 4: Implement -- Python audit.py**

Update `log_entry()` to pass through `event_class`, `retention_tier`, `expires_at` in the entry dict construction.

**Step 5: Implement -- TypeScript sqlite-worker.ts**

Same changes as Python:
1. Add columns to schema
2. Add indexes
3. Add migration ALTER TABLEs
4. Update storeAuditEntry INSERT
5. Update queryAuditEntries with eventClass filter
6. Add deleteExpiredAuditEntries function
7. Add message handler case

**Step 6: Implement -- TypeScript storage.ts**

Update `StorageBackend` interface with `deleteExpiredAuditEntries` and `eventClass` in query opts. Update `InMemoryStorage` and `SQLiteStorage` implementations.

**Step 7: Implement -- TypeScript audit.ts**

Update `logEntry()` to pass through the three new fields.

**Step 8: Write TypeScript tests**

Add storage tests for the three new fields, event_class filtering, and expired entry deletion to `packages/typescript/server/tests/storage.test.ts`.

**Step 9: Run all tests**

Run: `.venv/bin/python -m pytest packages/python -x -q`
Run: `cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose`
Expected: All pass

**Step 10: Commit**

```
git add packages/python/anip-server/src/anip_server/storage.py \
       packages/python/anip-server/src/anip_server/audit.py \
       packages/python/anip-server/tests/test_storage.py \
       packages/typescript/server/src/sqlite-worker.ts \
       packages/typescript/server/src/storage.ts \
       packages/typescript/server/src/audit.ts \
       packages/typescript/server/tests/storage.test.ts
git commit -m "feat(server): add event_class, retention_tier, expires_at to audit storage (v0.8)"
```

---

### Task 6: Wire Classification, Retention, and event_class Query Filter into Service

Update both service runtimes to classify events at invocation time, compute retention tier and expires_at, and pass them to the audit log. Accept retention policy config at service construction. Thread `event_class` as a queryable filter through `query_audit()` and route handlers.

**Files:**
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/typescript/service/src/service.ts`
- Modify: `packages/python/anip-server/src/anip_server/routes.py` (or equivalent binding)
- Modify: `packages/typescript/express/src/index.ts` (and fastify/hono equivalents)
- Test: `packages/python/anip-service/tests/test_service_init.py`
- Test: `packages/typescript/service/tests/service.test.ts`

**Step 1: Write failing tests -- Python**

Add to `packages/python/anip-service/tests/test_service_init.py` (adapt to use existing test fixtures for token/service construction):

```python
@pytest.mark.asyncio
async def test_invoke_stores_event_class_in_audit(service_with_storage):
    """v0.8: successful invocation stores event_class in audit entry."""
    service, storage = service_with_storage
    # Invoke a read capability (adapt capability name to match test fixtures)
    result = await service.invoke("flight.search", token, {"origin": "SFO", "destination": "LAX"})
    assert result["success"] is True

    entries = await storage.query_audit_entries(capability="flight.search")
    assert len(entries) >= 1
    entry = entries[0]
    assert entry["event_class"] == "low_risk_success"
    assert entry["retention_tier"] == "short"
    assert entry["expires_at"] is not None
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest packages/python/anip-service/tests/test_service_init.py -x -q -k "event_class"`
Expected: FAIL -- `event_class` not in audit entries

**Step 3: Implement -- Python service.py**

1. Add imports: `from anip_service.classification import classify_event` and `from anip_service.retention import RetentionPolicy`

2. Add `retention_policy: RetentionPolicy | None = None` parameter to `__init__`. Store as `self._retention_policy = retention_policy or RetentionPolicy()`.

3. Update `_log_audit` to accept `event_class`, `retention_tier`, `expires_at` keyword args and pass them to the audit entry dict.

4. At each audit call site in `invoke()`, compute classification:
   - Get `side_effect_type` from `decl.side_effect.type.value`
   - Call `classify_event(side_effect_type, success, failure_type)`
   - Call `self._retention_policy.resolve_tier(ec)`
   - Call `self._retention_policy.compute_expires_at(tier)`
   - Pass all three to `_log_audit`

**Step 4: Implement -- TypeScript service.ts**

Same pattern:
1. Import `classifyEvent` and `RetentionPolicy`
2. Add `retentionPolicy` to `ANIPServiceOpts`
3. Initialize `const retentionPolicy = opts.retentionPolicy ?? new RetentionPolicy()`
4. Update `logAudit` to accept and pass the three new fields
5. Compute classification at each audit call site

**Step 5: Write TypeScript tests**

Add test to `packages/typescript/service/tests/service.test.ts` verifying audit entries contain `event_class`, `retention_tier`, `expires_at`.

**Step 6: Thread event_class filter through service query_audit()**

In Python `service.py` `query_audit()` (currently line 649), add `event_class` to the filter passthrough:

```python
entries = await self._audit.query(
    root_principal=root_principal,
    capability=filters.get("capability"),
    since=filters.get("since"),
    invocation_id=filters.get("invocation_id"),
    client_reference_id=filters.get("client_reference_id"),
    event_class=filters.get("event_class"),  # v0.8
    limit=min(filters.get("limit", 50), 1000),
)
```

In TypeScript `service.ts` `queryAudit()` (currently line 910), add same:

```typescript
const entries = await audit.query({
  rootPrincipal,
  capability: f.capability as string | undefined,
  since: f.since as string | undefined,
  invocationId: f.invocation_id as string | undefined,
  clientReferenceId: f.client_reference_id as string | undefined,
  eventClass: f.event_class as string | undefined,  // v0.8
  limit: Math.min((f.limit as number) ?? 50, 1000),
});
```

**Step 7: Thread event_class through route handlers**

In the Python route handler that serves `/audit`, parse `event_class` from query parameters and pass it into the filters dict.

In each TypeScript binding (express, fastify, hono), parse `event_class` from `req.query` and pass it through. Follow the existing pattern for how `capability`, `since`, etc. are parsed and forwarded.

**Step 8: Run all tests**

Run: `.venv/bin/python -m pytest packages/python -x -q`
Run: `cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose`
Expected: All pass

**Step 9: Commit**

```
git add packages/python/anip-service/src/anip_service/service.py \
       packages/python/anip-service/tests/test_service_init.py \
       packages/typescript/service/src/service.ts \
       packages/typescript/service/tests/service.test.ts
git commit -m "feat(service): wire event classification, retention, and event_class query filter into invoke (v0.8)"
```

---

### Task 7: Retention Enforcer (Background Cleanup) + Proof Safety Guard

Implement a `RetentionEnforcer` class in both runtimes that periodically deletes expired audit entries. Wire it into the service lifecycle. **Python must use `asyncio.create_task` with a sleep loop — NOT a background thread** (the storage backend is async; calling it from a foreign event loop breaks loop-affine backends like asyncpg). Add a safety guard to `_rebuild_merkle_to()` that detects gaps from deleted rows and returns an error instead of a silently wrong Merkle tree.

**Files:**
- Create: `packages/python/anip-server/src/anip_server/retention_enforcer.py`
- Create: `packages/python/anip-server/tests/test_retention_enforcer.py`
- Create: `packages/typescript/server/src/retention-enforcer.ts`
- Create: `packages/typescript/server/tests/retention-enforcer.test.ts`
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/typescript/service/src/service.ts`

**Step 1: Write failing tests -- Python**

Create `packages/python/anip-server/tests/test_retention_enforcer.py`:

```python
"""Tests for retention enforcer (v0.8)."""

import asyncio

import pytest

from anip_server.retention_enforcer import RetentionEnforcer
from anip_server.storage import InMemoryStorage


@pytest.fixture
def storage():
    return InMemoryStorage()


@pytest.mark.asyncio
async def test_enforcer_deletes_expired_entries(storage):
    """Enforcer deletes entries where expires_at < now."""
    await storage.store_audit_entry({
        "sequence_number": 1,
        "timestamp": "2026-03-10T00:00:00Z",
        "capability": "test",
        "success": True,
        "previous_hash": "sha256:0000",
        "event_class": "malformed_or_spam",
        "retention_tier": "short",
        "expires_at": "2026-03-10T00:00:00Z",
    })
    await storage.store_audit_entry({
        "sequence_number": 2,
        "timestamp": "2026-03-16T00:00:00Z",
        "capability": "test",
        "success": True,
        "previous_hash": "sha256:0001",
        "event_class": "high_risk_success",
        "retention_tier": "long",
        "expires_at": "2027-03-16T00:00:00Z",
    })
    await storage.store_audit_entry({
        "sequence_number": 3,
        "timestamp": "2026-03-16T00:00:00Z",
        "capability": "test",
        "success": True,
        "previous_hash": "sha256:0002",
        "event_class": "high_risk_success",
        "retention_tier": "long",
        "expires_at": None,
    })

    enforcer = RetentionEnforcer(storage, interval_seconds=1)
    deleted = await enforcer.sweep()
    assert deleted == 1

    remaining = await storage.query_audit_entries()
    assert len(remaining) == 2


@pytest.mark.asyncio
async def test_enforcer_start_stop(storage):
    """Enforcer can be started and stopped."""
    enforcer = RetentionEnforcer(storage, interval_seconds=60)
    enforcer.start()
    enforcer.stop()
```

**Step 2: Implement -- Python**

Create `packages/python/anip-server/src/anip_server/retention_enforcer.py`:

**IMPORTANT:** Do NOT use `threading.Thread` + `asyncio.new_event_loop()`. The storage backend is async and may be loop-affine (asyncpg, SQLAlchemy async). Use `asyncio.create_task` with a sleep loop so the enforcer runs in the service's own event loop.

```python
"""Retention enforcer -- background cleanup of expired audit entries (v0.8).

Periodically deletes audit entries whose expires_at timestamp has passed.
Uses asyncio tasks (not threads) to stay compatible with async storage backends.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .storage import StorageBackend


class RetentionEnforcer:
    """Background sweep that deletes expired audit entries."""

    def __init__(
        self,
        storage: StorageBackend,
        *,
        interval_seconds: int = 60,
    ) -> None:
        self._storage = storage
        self._interval = interval_seconds
        self._task: asyncio.Task[None] | None = None

    async def sweep(self) -> int:
        """Run one cleanup sweep. Returns number of deleted entries."""
        now = datetime.now(timezone.utc).isoformat()
        return await self._storage.delete_expired_audit_entries(now)

    def start(self) -> None:
        """Start background cleanup as an asyncio task."""
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        """Cancel the background cleanup task."""
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self.sweep()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass  # Sweep failures are non-fatal
```

**Step 3: Write failing tests and implement -- TypeScript**

Create `packages/typescript/server/src/retention-enforcer.ts`:

```typescript
/**
 * Retention enforcer -- background cleanup of expired audit entries (v0.8).
 *
 * Periodically deletes audit entries whose expires_at timestamp has passed.
 * Modeled after CheckpointScheduler.
 */

import type { StorageBackend } from "./storage.js";

export class RetentionEnforcer {
  private _storage: StorageBackend;
  private _interval: number;
  private _timer: ReturnType<typeof setInterval> | null = null;

  constructor(storage: StorageBackend, intervalSeconds: number = 60) {
    this._storage = storage;
    this._interval = intervalSeconds;
  }

  async sweep(): Promise<number> {
    const now = new Date().toISOString();
    return this._storage.deleteExpiredAuditEntries(now);
  }

  start(): void {
    if (this._timer) return;
    this._timer = setInterval(() => {
      this.sweep().catch(() => {});
    }, this._interval * 1000);
  }

  stop(): void {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  }
}
```

Create `packages/typescript/server/tests/retention-enforcer.test.ts` with matching tests.

**Step 4: Wire into service lifecycle**

In both runtimes, instantiate `RetentionEnforcer` in the service constructor and call `start()`/`stop()` in the service lifecycle methods.

**Step 5: Add proof safety guard to `_rebuild_merkle_to()`**

Retention deletes rows from `audit_log`. The existing `_rebuild_merkle_to()` replays from `getAuditEntriesRange(1, N)` — if rows are missing, the Merkle tree will be wrong and proof verification will fail silently.

**Fix:** Before building the tree, verify the replay is complete. If rows are missing, raise/throw a clear error.

In Python `service.py` `_rebuild_merkle_to()`:

```python
async def _rebuild_merkle_to(self, sequence_number: int) -> MerkleTree:
    """Rebuild a Merkle tree from audit entries 1..sequence_number."""
    entries = await self._storage.get_audit_entries_range(1, sequence_number)
    if len(entries) < sequence_number:
        raise ValueError(
            f"Cannot rebuild proof: audit entries have been deleted by retention enforcement. "
            f"Expected {sequence_number} entries, found {len(entries)}. "
            f"Past checkpoints remain independently verifiable."
        )
    tree = MerkleTree()
    for row in entries:
        filtered = {
            k: v for k, v in sorted(row.items())
            if k not in ("signature", "id")
        }
        tree.add_leaf(json.dumps(filtered, separators=(",", ":"), sort_keys=True).encode())
    return tree
```

In TypeScript `service.ts` `rebuildMerkleTo()`:

```typescript
async function rebuildMerkleTo(sequenceNumber: number): Promise<MerkleTree> {
  const entries = await storage.getAuditEntriesRange(1, sequenceNumber);
  if (entries.length < sequenceNumber) {
    throw new Error(
      `Cannot rebuild proof: audit entries have been deleted by retention enforcement. ` +
      `Expected ${sequenceNumber} entries, found ${entries.length}. ` +
      `Past checkpoints remain independently verifiable.`
    );
  }
  const tree = new MerkleTree();
  for (const row of entries) {
    const filtered: Record<string, unknown> = {};
    for (const key of Object.keys(row).sort()) {
      if (key !== "signature" && key !== "id") {
        filtered[key] = row[key];
      }
    }
    tree.addLeaf(Buffer.from(JSON.stringify(filtered)));
  }
  return tree;
}
```

Add tests for this guard in both runtimes: insert entries, delete some via the storage method, then verify that calling the proof endpoint returns the expected error.

**Step 6: Run all tests**

Run: `.venv/bin/python -m pytest packages/python -x -q`
Run: `cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose`
Expected: All pass

**Step 7: Commit**

```
git add packages/python/anip-server/src/anip_server/retention_enforcer.py \
       packages/python/anip-server/tests/test_retention_enforcer.py \
       packages/typescript/server/src/retention-enforcer.ts \
       packages/typescript/server/tests/retention-enforcer.test.ts \
       packages/python/anip-service/src/anip_service/service.py \
       packages/typescript/service/src/service.ts
git commit -m "feat(server): add RetentionEnforcer background cleanup + proof safety guard (v0.8)"
```

---

### Task 8: Failure Detail Redaction

Implement `redact_failure()` / `redactFailure()` as a pure function in both service packages. Wire it into the response path of `invoke()`.

**Files:**
- Create: `packages/python/anip-service/src/anip_service/redaction.py`
- Create: `packages/python/anip-service/tests/test_redaction.py`
- Create: `packages/typescript/service/src/redaction.ts`
- Create: `packages/typescript/service/tests/redaction.test.ts`
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/typescript/service/src/service.ts`

**Step 1: Write failing tests -- Python**

Create `packages/python/anip-service/tests/test_redaction.py`:

```python
"""Tests for failure detail redaction (v0.8)."""

from anip_service.redaction import redact_failure


class TestRedactFailure:

    SAMPLE_FAILURE = {
        "type": "scope_insufficient",
        "detail": "Token scope ['read'] does not include required scope 'admin:write' for capability 'dangerous.action'",
        "retry": True,
        "resolution": {
            "action": "request_scope",
            "requires": "admin:write",
            "grantable_by": "org-admin@example.com",
            "estimated_availability": "PT1H",
        },
    }

    def test_full_returns_unchanged(self):
        result = redact_failure(self.SAMPLE_FAILURE, "full")
        assert result == self.SAMPLE_FAILURE

    def test_reduced_strips_grantable_by(self):
        result = redact_failure(self.SAMPLE_FAILURE, "reduced")
        assert result["type"] == "scope_insufficient"
        assert result["retry"] is True
        assert result["resolution"]["grantable_by"] is None
        assert result["resolution"]["action"] == "request_scope"
        assert result["resolution"]["requires"] == "admin:write"
        assert result["resolution"]["estimated_availability"] == "PT1H"

    def test_reduced_truncates_detail(self):
        long_detail = "x" * 300
        failure = {**self.SAMPLE_FAILURE, "detail": long_detail}
        result = redact_failure(failure, "reduced")
        assert len(result["detail"]) <= 200

    def test_reduced_preserves_short_detail(self):
        result = redact_failure(self.SAMPLE_FAILURE, "reduced")
        assert result["detail"] == self.SAMPLE_FAILURE["detail"]

    def test_redacted_uses_generic_detail(self):
        result = redact_failure(self.SAMPLE_FAILURE, "redacted")
        assert result["type"] == "scope_insufficient"
        assert result["detail"] != self.SAMPLE_FAILURE["detail"]
        assert "admin:write" not in result["detail"]

    def test_redacted_strips_resolution_fields(self):
        result = redact_failure(self.SAMPLE_FAILURE, "redacted")
        assert result["resolution"]["requires"] is None
        assert result["resolution"]["grantable_by"] is None
        assert result["resolution"]["estimated_availability"] is None
        assert result["resolution"]["action"] == "request_scope"

    def test_redacted_preserves_retry(self):
        result = redact_failure(self.SAMPLE_FAILURE, "redacted")
        assert result["retry"] is True

    def test_type_is_never_redacted(self):
        for level in ("full", "reduced", "redacted"):
            result = redact_failure(self.SAMPLE_FAILURE, level)
            assert result["type"] == "scope_insufficient"

    def test_policy_treated_as_redacted(self):
        result = redact_failure(self.SAMPLE_FAILURE, "policy")
        redacted = redact_failure(self.SAMPLE_FAILURE, "redacted")
        assert result == redacted

    def test_failure_without_resolution(self):
        failure = {"type": "internal_error", "detail": "Something broke", "retry": False}
        result = redact_failure(failure, "redacted")
        assert result["type"] == "internal_error"
```

**Step 2: Implement -- Python**

Create `packages/python/anip-service/src/anip_service/redaction.py`:

```python
"""Failure detail redaction for v0.8 security hardening.

Shapes failure responses based on disclosure level before they reach the caller.
Storage always records the full unredacted failure.
"""

from __future__ import annotations

from typing import Any

_GENERIC_MESSAGES: dict[str, str] = {
    "scope_insufficient": "Insufficient scope for this capability",
    "invalid_token": "Authentication failed",
    "token_expired": "Token has expired",
    "purpose_mismatch": "Token purpose does not match this capability",
    "insufficient_authority": "Insufficient authority for this action",
    "unknown_capability": "Capability not found",
    "not_found": "Resource not found",
    "unavailable": "Service temporarily unavailable",
    "concurrent_lock": "Operation conflict",
    "internal_error": "Internal error",
    "streaming_not_supported": "Streaming not supported for this capability",
    "scope_escalation": "Scope escalation not permitted",
}

_DEFAULT_GENERIC = "Request failed"


def redact_failure(
    failure: dict[str, Any],
    disclosure_level: str,
) -> dict[str, Any]:
    """Apply disclosure-level redaction to a failure response.

    Args:
        failure: The failure dict (type, detail, retry, resolution).
        disclosure_level: One of "full", "reduced", "redacted", "policy".
            "policy" is treated as "redacted" in v0.8.

    Returns:
        A new failure dict with appropriate redaction applied.
    """
    if disclosure_level == "policy":
        disclosure_level = "redacted"

    if disclosure_level == "full":
        return failure

    result = {**failure}
    resolution = {**(failure.get("resolution") or {})}

    if disclosure_level == "reduced":
        resolution["grantable_by"] = None
        detail = result.get("detail", "")
        if len(detail) > 200:
            result["detail"] = detail[:200]

    elif disclosure_level == "redacted":
        failure_type = result.get("type", "")
        result["detail"] = _GENERIC_MESSAGES.get(failure_type, _DEFAULT_GENERIC)
        resolution["requires"] = None
        resolution["grantable_by"] = None
        resolution["estimated_availability"] = None

    if resolution:
        result["resolution"] = resolution

    return result
```

**Step 3: Write failing tests and implement -- TypeScript**

Create `packages/typescript/service/src/redaction.ts` and `packages/typescript/service/tests/redaction.test.ts` with matching implementation and tests.

**Step 4: Wire into service invoke() response path**

In both runtimes:
1. Add `disclosure_level` / `disclosureLevel` parameter to service constructor
2. Import and call `redact_failure` / `redactFailure` on every failure response before returning
3. Apply at: unknown capability, streaming not supported, validation failure, ANIPError, internal error

**Step 5: Run all tests**

Run: `.venv/bin/python -m pytest packages/python -x -q`
Run: `cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose`
Expected: All pass

**Step 6: Commit**

```
git add packages/python/anip-service/src/anip_service/redaction.py \
       packages/python/anip-service/tests/test_redaction.py \
       packages/typescript/service/src/redaction.ts \
       packages/typescript/service/tests/redaction.test.ts \
       packages/python/anip-service/src/anip_service/service.py \
       packages/typescript/service/src/service.ts
git commit -m "feat(service): add failure detail redaction at response boundary (v0.8)"
```

---

### Task 9: Update Discovery Posture, Discovery Schema, and Canonical ANIP Schema

Update the discovery document to include `retention_enforced` in the posture.audit block. Update both JSON Schema files: `discovery.schema.json` (add `retention_enforced`, add `"reduced"` to `failure_disclosure.detail_level`) and `anip.schema.json` (add `EventClass`, `RetentionTier`, `DisclosureLevel` enum definitions; add `event_class`, `retention_tier`, `expires_at` to audit entry definitions; bump `$id` to v0.8). Update the service's `get_discovery()` to reflect the new field.

**Files:**
- Modify: `schema/discovery.schema.json`
- Modify: `schema/anip.schema.json`
- Modify: `packages/python/anip-service/src/anip_service/service.py`
- Modify: `packages/typescript/service/src/service.ts`
- Test: `packages/python/anip-service/tests/test_service_init.py`
- Test: `packages/typescript/service/tests/service.test.ts`

**Step 1: Write failing test -- Python**

Add to `packages/python/anip-service/tests/test_service_init.py`:

```python
def test_discovery_posture_includes_retention_enforced(service):
    """v0.8: discovery posture.audit includes retention_enforced: true."""
    doc = service.get_discovery()
    posture = doc["anip_discovery"]["posture"]
    assert posture["audit"]["retention_enforced"] is True
```

**Step 2: Update discovery schema**

In `schema/discovery.schema.json`:

1. In the `posture.audit` properties, add:

```json
"retention_enforced": {
  "type": "boolean",
  "description": "Whether the service actively deletes expired audit entries (v0.8)"
}
```

2. In the `failure_disclosure.detail_level` enum (currently `["full", "redacted", "policy"]`), add `"reduced"`:

```json
"detail_level": {
  "type": "string",
  "enum": ["full", "reduced", "redacted", "policy"],
  "description": "How much error detail is surfaced to callers"
}
```

**Step 3: Update canonical ANIP schema**

In `schema/anip.schema.json`:

1. Bump `$id` from `v0.7` to `v0.8`.

2. Add enum definitions for the new protocol-visible types:

```json
"EventClass": {
  "type": "string",
  "enum": ["high_risk_success", "high_risk_denial", "low_risk_success", "repeated_low_value_denial", "malformed_or_spam"],
  "description": "Classification of an audit event by risk level (v0.8)"
},
"RetentionTier": {
  "type": "string",
  "enum": ["long", "medium", "short", "aggregate_only"],
  "description": "Retention tier governing how long an audit entry is kept (v0.8)"
},
"DisclosureLevel": {
  "type": "string",
  "enum": ["full", "reduced", "redacted", "policy"],
  "description": "How much failure detail is surfaced to callers (v0.8)"
}
```

3. Add `event_class`, `retention_tier`, `expires_at` fields to the audit entry definition (if one exists — otherwise add them alongside the existing audit-related definitions).

**Step 5: Update Python get_discovery()**

In `packages/python/anip-service/src/anip_service/service.py`, update the posture construction in `get_discovery()` to include `AuditPosture(retention_enforced=True)`.

**Step 6: Update TypeScript getDiscovery()**

In `packages/typescript/service/src/service.ts`, update the posture.audit block to include `retention_enforced: true`.

**Step 7: Write TypeScript test and run all tests**

Run: `.venv/bin/python -m pytest packages/python -x -q`
Run: `cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose`
Expected: All pass

**Step 8: Commit**

```
git add schema/discovery.schema.json \
       schema/anip.schema.json \
       packages/python/anip-service/src/anip_service/service.py \
       packages/typescript/service/src/service.ts \
       packages/python/anip-service/tests/test_service_init.py \
       packages/typescript/service/tests/service.test.ts
git commit -m "feat(discovery,schema): add retention_enforced, reduced disclosure, and v0.8 enum definitions"
```

---

### Task 10: SPEC.md Updates

Add the v0.8 security hardening section to the specification. Update audit section, roadmap, and protocol version references.

**Files:**
- Modify: `SPEC.md`

**Step 1: Update protocol version**

Change `anip/0.7` to `anip/0.8` in the title/header.

**Step 2: Add new section after 6.7**

Add `### 6.8 Security Hardening (v0.8)` with subsections:
- Event Classification (classification table, normative language)
- Retention Enforcement (two-layer policy, normative language, checkpoint interaction)
- Failure Redaction (redaction table, normative language)
- Audit Entry Fields (v0.8) (new fields table)
- Discovery Posture (v0.8 additions) (retention_enforced)

See design doc for exact normative language.

**Step 3: Update posture.audit table in 6.7**

Add `retention_enforced` field.

**Step 4: Update roadmap**

Add security hardening row.

**Step 5: Run all tests and commit**

```
git add SPEC.md
git commit -m "docs(spec): add section 6.8 Security Hardening for v0.8"
```

---

### Task 11: Documentation Updates

Update all documentation files that reference the protocol version. Bump package versions.

**Files:**
- Modify: `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `docs/trust-model.md`
- Modify: `schema/README.md`, `schema/anip.schema.json`, `schema/discovery.schema.json`
- Modify: `skills/anip-consumer.md`, `skills/anip-implementer.md`, `skills/anip-validator.md`
- Modify: All `pyproject.toml` and `package.json` files (version bumps)

**Step 1: Update version references**

Search for `0.7` in all docs and update to `0.8` where appropriate.

**Step 2: Bump package versions**

All Python pyproject.toml and TypeScript package.json files: bump from `0.7.x` to `0.8.0`.

**Step 3: Run all tests and commit**

```
git add README.md SECURITY.md CONTRIBUTING.md docs/trust-model.md \
       schema/ skills/ packages/python/*/pyproject.toml \
       packages/typescript/*/package.json packages/typescript/package-lock.json
git commit -m "docs: update all references to v0.8"
```

---

## Test Commands Reference

**Python (all):** `.venv/bin/python -m pytest packages/python -x -q`

**TypeScript (all):** `cd packages/typescript && npx tsc -b core crypto server service express fastify hono && npx vitest run --reporter=verbose`

**Python (specific file):** `.venv/bin/python -m pytest packages/python/anip-service/tests/test_classification.py -x -q`

**TypeScript (specific file):** `cd packages/typescript && npx vitest run service/tests/classification.test.ts`

## v0.8 Audit Semantics Invariants

Throughout implementation, maintain these invariants:

1. Full-fidelity audit still exists -- all events stored with complete detail
2. Retention limits lifetime -- expired entries hard-deleted by background sweep
3. Aggregation is not happening yet -- each event is a distinct record
4. Checkpoints still cover all entries -- no selective checkpointing
5. Response redaction is separate from storage -- callers may see less than stored
6. `aggregate_only` tier is a placeholder -- treated as `short` in v0.8
7. `repeated_low_value_denial` exists in enum but is not assigned by classifier
8. Proof generation fails cleanly if retention has deleted entries from the replay range -- past checkpoints remain independently verifiable, but the service will not generate new proofs over gaps
9. Python retention enforcement runs in the service's event loop (asyncio task), not a background thread
