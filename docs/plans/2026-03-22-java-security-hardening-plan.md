# Java v0.8-v0.9 Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the v0.8-v0.9 security-hardening features (event classification, retention policy, failure redaction, disclosure control, audit aggregation, storage-side redaction) in the Java ANIP runtime, achieving full parity with Python, TypeScript, and Go.

**Architecture:** Six new classes in `packages/java/anip-service/src/main/java/dev/anip/service/` — each a focused utility with no external dependencies beyond `anip-core`. Extend `AuditEntry` with aggregation fields. Integration through `appendAuditEntry()` and `invoke()` in `ANIPService.java`, plus config fields in `ServiceConfig.java`. The Go implementation (just completed in PR #71) serves as the direct reference — same logic, Java idioms.

**Tech Stack:** Java 17, no new dependencies.

---

## File Structure

| File | Responsibility | Status |
|------|---------------|--------|
| `anip-service/.../service/EventClassification.java` | Event classification pure function | Create |
| `anip-service/.../service/RetentionPolicy.java` | Two-layer retention policy | Create |
| `anip-service/.../service/FailureRedaction.java` | Response-boundary failure redaction | Create |
| `anip-service/.../service/DisclosureControl.java` | Policy-mode caller-class resolution | Create |
| `anip-service/.../service/AuditAggregator.java` | Time-window bucketed audit aggregation | Create |
| `anip-service/.../service/StorageRedaction.java` | Write-path parameter stripping | Create |
| `anip-core/.../core/AuditEntry.java` | Add aggregation fields | Modify |
| `anip-service/.../service/ServiceConfig.java` | Add retention/disclosure/aggregation config | Modify |
| `anip-service/.../service/ANIPService.java` | Wire everything into invoke flow + lifecycle | Modify |
| `anip-service/src/test/java/.../EventClassificationTest.java` | Tests | Create |
| `anip-service/src/test/java/.../RetentionPolicyTest.java` | Tests | Create |
| `anip-service/src/test/java/.../FailureRedactionTest.java` | Tests | Create |
| `anip-service/src/test/java/.../DisclosureControlTest.java` | Tests | Create |
| `anip-service/src/test/java/.../AuditAggregatorTest.java` | Tests | Create |
| `anip-service/src/test/java/.../StorageRedactionTest.java` | Tests | Create |

Base paths:
- Source: `packages/java/anip-service/src/main/java/dev/anip/service/`
- Tests: `packages/java/anip-service/src/test/java/dev/anip/servicetest/`
- Core model: `packages/java/anip-core/src/main/java/dev/anip/core/`

---

## Task 1: Event Classification

**Files:**
- Create: `packages/java/anip-service/src/main/java/dev/anip/service/EventClassification.java`
- Create: `packages/java/anip-service/src/test/java/dev/anip/servicetest/EventClassificationTest.java`

- [ ] **Step 1: Write test**

```java
package dev.anip.servicetest;

import dev.anip.service.EventClassification;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class EventClassificationTest {

    @Test void highRiskSuccess() {
        for (String se : new String[]{"write", "irreversible", "transactional"}) {
            assertEquals("high_risk_success", EventClassification.classify(se, true, ""));
        }
    }

    @Test void lowRiskSuccess() {
        assertEquals("low_risk_success", EventClassification.classify("read", true, ""));
    }

    @Test void malformedNoSideEffect() {
        assertEquals("malformed_or_spam", EventClassification.classify("", false, "unknown_capability"));
        assertEquals("malformed_or_spam", EventClassification.classify(null, false, "unknown_capability"));
    }

    @Test void malformedFailureTypes() {
        for (String ft : new String[]{"unknown_capability", "streaming_not_supported", "internal_error"}) {
            assertEquals("malformed_or_spam", EventClassification.classify("read", false, ft));
        }
    }

    @Test void highRiskDenial() {
        for (String ft : new String[]{"scope_insufficient", "invalid_token", "token_expired", "purpose_mismatch"}) {
            assertEquals("high_risk_denial", EventClassification.classify("write", false, ft));
        }
    }
}
```

- [ ] **Step 2: Write implementation**

```java
package dev.anip.service;

import java.util.Set;

/**
 * Event classification per SPEC §6.8.
 * Pure function — maps (sideEffectType, success, failureType) to one of 5 event classes.
 */
public final class EventClassification {

    private static final Set<String> HIGH_RISK_SIDE_EFFECTS = Set.of("write", "irreversible", "transactional");
    private static final Set<String> MALFORMED_FAILURE_TYPES = Set.of("unknown_capability", "streaming_not_supported", "internal_error");

    private EventClassification() {}

    public static String classify(String sideEffectType, boolean success, String failureType) {
        if (sideEffectType == null || sideEffectType.isEmpty()) {
            return "malformed_or_spam";
        }
        if (success) {
            return HIGH_RISK_SIDE_EFFECTS.contains(sideEffectType) ? "high_risk_success" : "low_risk_success";
        }
        if (failureType != null && MALFORMED_FAILURE_TYPES.contains(failureType)) {
            return "malformed_or_spam";
        }
        return "high_risk_denial";
    }
}
```

- [ ] **Step 3: Run tests and commit**

```bash
cd packages/java && mvn test -pl anip-service -am -q
git add packages/java/anip-service/src/main/java/dev/anip/service/EventClassification.java \
       packages/java/anip-service/src/test/java/dev/anip/servicetest/EventClassificationTest.java
git commit -m "feat(java): add event classification (§6.8)"
```

---

## Task 2: Retention Policy

**Files:**
- Create: `packages/java/anip-service/src/main/java/dev/anip/service/RetentionPolicy.java`
- Create: `packages/java/anip-service/src/test/java/dev/anip/servicetest/RetentionPolicyTest.java`

- [ ] **Step 1: Write test**

```java
package dev.anip.servicetest;

import dev.anip.service.RetentionPolicy;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import static org.junit.jupiter.api.Assertions.*;

class RetentionPolicyTest {

    @Test void defaultTiers() {
        var rp = new RetentionPolicy(null, null);
        assertEquals("long", rp.resolveTier("high_risk_success"));
        assertEquals("medium", rp.resolveTier("high_risk_denial"));
        assertEquals("short", rp.resolveTier("low_risk_success"));
        assertEquals("aggregate_only", rp.resolveTier("repeated_low_value_denial"));
        assertEquals("short", rp.resolveTier("malformed_or_spam"));
        assertEquals("short", rp.resolveTier("unknown_class")); // fallback
    }

    @Test void computeExpiresAt() {
        var rp = new RetentionPolicy(null, null);
        Instant now = Instant.parse("2026-01-01T00:00:00Z");
        String exp = rp.computeExpiresAt("long", now);
        assertNotNull(exp);
        Instant parsed = Instant.parse(exp);
        long days = ChronoUnit.DAYS.between(now, parsed);
        assertEquals(365, days);
    }

    @Test void defaultRetention() {
        var rp = new RetentionPolicy(null, null);
        assertEquals("P90D", rp.getDefaultRetention());
    }

    @Test void customOverrides() {
        var rp = new RetentionPolicy(
            java.util.Map.of("low_risk_success", "long"),
            java.util.Map.of("short", "P14D")
        );
        assertEquals("long", rp.resolveTier("low_risk_success"));
        Instant now = Instant.parse("2026-01-01T00:00:00Z");
        String exp = rp.computeExpiresAt("short", now);
        Instant parsed = Instant.parse(exp);
        assertEquals(14, ChronoUnit.DAYS.between(now, parsed));
    }
}
```

- [ ] **Step 2: Write implementation**

```java
package dev.anip.service;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Two-layer retention model per SPEC §6.8.
 * Layer 1: EventClass → RetentionTier
 * Layer 2: RetentionTier → ISO 8601 duration (PnD)
 */
public class RetentionPolicy {

    private static final Map<String, String> DEFAULT_CLASS_TO_TIER = Map.of(
        "high_risk_success", "long",
        "high_risk_denial", "medium",
        "low_risk_success", "short",
        "repeated_low_value_denial", "aggregate_only",
        "malformed_or_spam", "short"
    );

    private static final Map<String, String> DEFAULT_TIER_TO_DURATION = Map.of(
        "long", "P365D",
        "medium", "P90D",
        "short", "P7D",
        "aggregate_only", "P1D"
    );

    private static final Pattern DURATION_RE = Pattern.compile("^P(\\d+)D$");

    private final Map<String, String> classToTier;
    private final Map<String, String> tierToDuration;

    public RetentionPolicy(Map<String, String> classOverrides, Map<String, String> tierOverrides) {
        this.classToTier = new HashMap<>(DEFAULT_CLASS_TO_TIER);
        if (classOverrides != null) this.classToTier.putAll(classOverrides);
        this.tierToDuration = new HashMap<>(DEFAULT_TIER_TO_DURATION);
        if (tierOverrides != null) this.tierToDuration.putAll(tierOverrides);
    }

    public String resolveTier(String eventClass) {
        return classToTier.getOrDefault(eventClass, "short");
    }

    public String computeExpiresAt(String tier, Instant now) {
        String duration = tierToDuration.get(tier);
        if (duration == null) return null;
        Matcher m = DURATION_RE.matcher(duration);
        if (!m.matches()) return null;
        int days = Integer.parseInt(m.group(1));
        return now.plus(days, ChronoUnit.DAYS).toString();
    }

    public String getDefaultRetention() {
        return tierToDuration.get("medium");
    }
}
```

- [ ] **Step 3: Run tests and commit**

```bash
cd packages/java && mvn test -pl anip-service -am -q
git add packages/java/anip-service/src/main/java/dev/anip/service/RetentionPolicy.java \
       packages/java/anip-service/src/test/java/dev/anip/servicetest/RetentionPolicyTest.java
git commit -m "feat(java): add two-layer retention policy (§6.8)"
```

---

## Task 3: Storage-Side Redaction

**Files:**
- Create: `packages/java/anip-service/src/main/java/dev/anip/service/StorageRedaction.java`
- Create: `packages/java/anip-service/src/test/java/dev/anip/servicetest/StorageRedactionTest.java`

- [ ] **Step 1: Write test**

```java
package dev.anip.servicetest;

import dev.anip.service.StorageRedaction;
import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class StorageRedactionTest {

    @Test void lowValueStripsParameters() {
        for (String ec : new String[]{"low_risk_success", "malformed_or_spam", "repeated_low_value_denial"}) {
            var entry = new HashMap<>(Map.of("event_class", ec, "parameters", Map.of("origin", "SEA")));
            var result = StorageRedaction.redactEntry(entry);
            assertNull(result.get("parameters"), ec + ": parameters should be null");
            assertEquals(true, result.get("storage_redacted"), ec + ": storage_redacted should be true");
        }
    }

    @Test void highValuePreservesParameters() {
        for (String ec : new String[]{"high_risk_success", "high_risk_denial"}) {
            var entry = new HashMap<>(Map.of("event_class", ec, "parameters", Map.of("origin", "SEA")));
            var result = StorageRedaction.redactEntry(entry);
            assertNotNull(result.get("parameters"), ec + ": parameters should be preserved");
            assertEquals(false, result.get("storage_redacted"), ec + ": storage_redacted should be false");
        }
    }

    @Test void doesNotMutateOriginal() {
        var entry = new HashMap<>(Map.of("event_class", "low_risk_success", "parameters", Map.of("origin", "SEA")));
        StorageRedaction.redactEntry(entry);
        assertNotNull(entry.get("parameters"), "original should not be mutated");
    }
}
```

- [ ] **Step 2: Write implementation**

```java
package dev.anip.service;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

/**
 * Storage-side parameter stripping per SPEC §6.10.
 * Strips parameters from low-value audit entries before persistence.
 */
public final class StorageRedaction {

    private static final Set<String> LOW_VALUE_CLASSES = Set.of(
        "low_risk_success", "malformed_or_spam", "repeated_low_value_denial"
    );

    private StorageRedaction() {}

    /**
     * Returns a shallow copy with parameters stripped if the event class is low-value.
     * Does not mutate the input.
     */
    public static Map<String, Object> redactEntry(Map<String, Object> entry) {
        var result = new HashMap<>(entry);
        String ec = (String) result.get("event_class");
        if (ec != null && LOW_VALUE_CLASSES.contains(ec)) {
            result.put("parameters", null);
            result.put("storage_redacted", true);
        } else {
            result.put("storage_redacted", false);
        }
        return result;
    }
}
```

- [ ] **Step 3: Run tests and commit**

```bash
cd packages/java && mvn test -pl anip-service -am -q
git add packages/java/anip-service/src/main/java/dev/anip/service/StorageRedaction.java \
       packages/java/anip-service/src/test/java/dev/anip/servicetest/StorageRedactionTest.java
git commit -m "feat(java): add storage-side parameter redaction (§6.10)"
```

---

## Task 4: Response-Boundary Failure Redaction

**Files:**
- Create: `packages/java/anip-service/src/main/java/dev/anip/service/FailureRedaction.java`
- Create: `packages/java/anip-service/src/test/java/dev/anip/servicetest/FailureRedactionTest.java`

- [ ] **Step 1: Write test**

```java
package dev.anip.servicetest;

import dev.anip.service.FailureRedaction;
import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class FailureRedactionTest {

    private Map<String, Object> sampleFailure() {
        var res = new HashMap<String, Object>();
        res.put("action", "request_scope");
        res.put("requires", List.of("travel.book"));
        res.put("grantable_by", "human:samir@example.com");
        var failure = new HashMap<String, Object>();
        failure.put("type", "scope_insufficient");
        failure.put("detail", "Need travel.book scope");
        failure.put("retry", false);
        failure.put("resolution", res);
        return failure;
    }

    @Test void fullPreservesEverything() {
        var result = FailureRedaction.redact(sampleFailure(), "full");
        assertEquals("Need travel.book scope", result.get("detail"));
        @SuppressWarnings("unchecked")
        var res = (Map<String, Object>) result.get("resolution");
        assertEquals("human:samir@example.com", res.get("grantable_by"));
    }

    @Test void reducedNullsGrantableBy() {
        var result = FailureRedaction.redact(sampleFailure(), "reduced");
        assertEquals("Need travel.book scope", result.get("detail")); // under 200 chars
        @SuppressWarnings("unchecked")
        var res = (Map<String, Object>) result.get("resolution");
        assertNull(res.get("grantable_by"));
        assertEquals("request_scope", res.get("action"));
    }

    @Test void redactedUsesGenericMessage() {
        var result = FailureRedaction.redact(sampleFailure(), "redacted");
        assertEquals("Insufficient scope for this capability", result.get("detail"));
        assertEquals("scope_insufficient", result.get("type")); // never redacted
        assertEquals(false, result.get("retry")); // never redacted
        @SuppressWarnings("unchecked")
        var res = (Map<String, Object>) result.get("resolution");
        assertEquals("request_scope", res.get("action")); // never redacted
        assertNull(res.get("requires"));
        assertNull(res.get("grantable_by"));
    }

    @Test void reducedTruncatesLongDetail() {
        var failure = new HashMap<String, Object>();
        failure.put("type", "internal_error");
        failure.put("detail", "x".repeat(300));
        failure.put("retry", false);
        var result = FailureRedaction.redact(failure, "reduced");
        String detail = (String) result.get("detail");
        assertTrue(detail.length() <= 200);
    }

    @Test void typeAndRetryNeverRedacted() {
        var failure = new HashMap<String, Object>();
        failure.put("type", "token_expired");
        failure.put("detail", "Token XYZ expired");
        failure.put("retry", true);
        for (String level : new String[]{"full", "reduced", "redacted"}) {
            var result = FailureRedaction.redact(failure, level);
            assertEquals("token_expired", result.get("type"), level);
            assertEquals(true, result.get("retry"), level);
        }
    }
}
```

- [ ] **Step 2: Write implementation**

```java
package dev.anip.service;

import java.util.HashMap;
import java.util.Map;

/**
 * Response-boundary failure redaction per SPEC §6.8.
 * Three disclosure levels: full, reduced, redacted.
 * Never redacts: type, retry, resolution.action
 */
public final class FailureRedaction {

    private static final Map<String, String> GENERIC_MESSAGES = Map.ofEntries(
        Map.entry("scope_insufficient", "Insufficient scope for this capability"),
        Map.entry("invalid_token", "Authentication failed"),
        Map.entry("token_expired", "Token has expired"),
        Map.entry("purpose_mismatch", "Token purpose does not match this capability"),
        Map.entry("insufficient_authority", "Insufficient authority for this action"),
        Map.entry("unknown_capability", "Capability not found"),
        Map.entry("not_found", "Resource not found"),
        Map.entry("unavailable", "Service temporarily unavailable"),
        Map.entry("concurrent_lock", "Operation conflict"),
        Map.entry("internal_error", "Internal error"),
        Map.entry("streaming_not_supported", "Streaming not supported for this capability"),
        Map.entry("scope_escalation", "Scope escalation not permitted")
    );

    private FailureRedaction() {}

    @SuppressWarnings("unchecked")
    public static Map<String, Object> redact(Map<String, Object> failure, String level) {
        if ("full".equals(level)) {
            return new HashMap<>(failure);
        }

        var result = new HashMap<>(failure);

        if ("reduced".equals(level)) {
            String detail = (String) result.get("detail");
            if (detail != null && detail.length() > 200) {
                result.put("detail", detail.substring(0, 200));
            }
            if (result.get("resolution") instanceof Map) {
                var res = new HashMap<>((Map<String, Object>) result.get("resolution"));
                res.put("grantable_by", null);
                result.put("resolution", res);
            }
            return result;
        }

        // "redacted" mode
        String failType = (String) result.get("type");
        result.put("detail", GENERIC_MESSAGES.getOrDefault(failType, "Request failed"));

        if (result.get("resolution") instanceof Map) {
            var res = (Map<String, Object>) result.get("resolution");
            var redactedRes = new HashMap<String, Object>();
            redactedRes.put("action", res.get("action"));
            redactedRes.put("requires", null);
            redactedRes.put("grantable_by", null);
            redactedRes.put("estimated_availability", null);
            result.put("resolution", redactedRes);
        }

        return result;
    }
}
```

- [ ] **Step 3: Run tests and commit**

```bash
cd packages/java && mvn test -pl anip-service -am -q
git add packages/java/anip-service/src/main/java/dev/anip/service/FailureRedaction.java \
       packages/java/anip-service/src/test/java/dev/anip/servicetest/FailureRedactionTest.java
git commit -m "feat(java): add response-boundary failure redaction (§6.8)"
```

---

## Task 5: Disclosure Control

**Files:**
- Create: `packages/java/anip-service/src/main/java/dev/anip/service/DisclosureControl.java`
- Create: `packages/java/anip-service/src/test/java/dev/anip/servicetest/DisclosureControlTest.java`

- [ ] **Step 1: Write test**

```java
package dev.anip.servicetest;

import dev.anip.service.DisclosureControl;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class DisclosureControlTest {

    @Test void fixedModes() {
        for (String level : new String[]{"full", "reduced", "redacted"}) {
            assertEquals(level, DisclosureControl.resolve(level, null, null));
        }
    }

    @Test void policyNoPolicy() {
        assertEquals("redacted", DisclosureControl.resolve("policy", null, null));
    }

    @Test void policyWithCallerClass() {
        var claims = Map.<String, Object>of("anip:caller_class", "internal");
        var policy = Map.of("internal", "full", "default", "redacted");
        assertEquals("full", DisclosureControl.resolve("policy", claims, policy));
    }

    @Test void policyFallsBackToDefault() {
        var claims = Map.<String, Object>of("anip:caller_class", "unknown_class");
        var policy = Map.of("internal", "full", "default", "reduced");
        assertEquals("reduced", DisclosureControl.resolve("policy", claims, policy));
    }

    @Test void policyFromStringListScope() {
        // Java tokens carry scope as List<String>
        var claims = Map.<String, Object>of("scope", List.of("travel.search", "audit:full"));
        var policy = Map.of("audit_full", "full", "default", "redacted");
        assertEquals("full", DisclosureControl.resolve("policy", claims, policy));
    }

    @Test void policyFromCallerClassOverridesScope() {
        var claims = Map.<String, Object>of(
            "anip:caller_class", "partner",
            "scope", List.of("audit:full")
        );
        var policy = Map.of("partner", "reduced", "audit_full", "full", "default", "redacted");
        assertEquals("reduced", DisclosureControl.resolve("policy", claims, policy));
    }
}
```

- [ ] **Step 2: Write implementation**

```java
package dev.anip.service;

import java.util.List;
import java.util.Map;

/**
 * Caller-class-aware disclosure level resolution per SPEC §6.9.
 * Fixed modes pass through. "policy" mode resolves caller class from token claims.
 */
public final class DisclosureControl {

    private DisclosureControl() {}

    public static String resolve(String level, Map<String, Object> tokenClaims, Map<String, String> policy) {
        if (!"policy".equals(level)) {
            return level;
        }

        String callerClass = resolveCallerClass(tokenClaims);

        if (policy == null) {
            return "redacted";
        }

        String mapped = policy.get(callerClass);
        if (mapped != null) return mapped;

        String def = policy.get("default");
        if (def != null) return def;

        return "redacted";
    }

    @SuppressWarnings("unchecked")
    private static String resolveCallerClass(Map<String, Object> claims) {
        if (claims == null) return "default";

        // 1. Explicit caller_class claim.
        Object cc = claims.get("anip:caller_class");
        if (cc instanceof String s && !s.isEmpty()) {
            return s;
        }

        // 2. Scope-derived: audit:full → audit_full.
        // Handle both List<String> (Java tokens) and List<?> (generic).
        Object scopeObj = claims.get("scope");
        if (scopeObj instanceof List<?> scopes) {
            for (Object s : scopes) {
                if ("audit:full".equals(s)) {
                    return "audit_full";
                }
            }
        }

        return "default";
    }
}
```

- [ ] **Step 3: Run tests and commit**

```bash
cd packages/java && mvn test -pl anip-service -am -q
git add packages/java/anip-service/src/main/java/dev/anip/service/DisclosureControl.java \
       packages/java/anip-service/src/test/java/dev/anip/servicetest/DisclosureControlTest.java
git commit -m "feat(java): add caller-class disclosure control (§6.9)"
```

---

## Task 6: Audit Aggregation

**Files:**
- Create: `packages/java/anip-service/src/main/java/dev/anip/service/AuditAggregator.java`
- Create: `packages/java/anip-service/src/test/java/dev/anip/servicetest/AuditAggregatorTest.java`

- [ ] **Step 1: Write test**

```java
package dev.anip.servicetest;

import dev.anip.service.AuditAggregator;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class AuditAggregatorTest {

    @Test void singleEventPassesThrough() {
        var agg = new AuditAggregator(60);
        Instant now = Instant.parse("2026-01-01T00:00:30Z");
        agg.submit(new HashMap<>(Map.of(
            "actor_key", "agent:test", "capability", "search",
            "failure_type", "scope_insufficient", "timestamp", now.toString()
        )));
        List<Object> results = agg.flush(now.plusSeconds(31));
        assertEquals(1, results.size());
        assertTrue(results.get(0) instanceof Map);
    }

    @Test @SuppressWarnings("unchecked") void multipleEventsAggregate() {
        var agg = new AuditAggregator(60);
        Instant base = Instant.parse("2026-01-01T00:00:00Z");
        for (int i = 0; i < 5; i++) {
            agg.submit(new HashMap<>(Map.of(
                "actor_key", "agent:spam", "capability", "search",
                "failure_type", "scope_insufficient",
                "timestamp", base.plusSeconds(i).toString(),
                "detail", "first detail"
            )));
        }
        List<Object> results = agg.flush(base.plusSeconds(61));
        assertEquals(1, results.size());
        var entry = (Map<String, Object>) results.get(0);
        assertEquals("aggregated", entry.get("entry_type"));
        assertEquals("repeated_low_value_denial", entry.get("event_class"));
        assertEquals(5, entry.get("count"));
    }

    @Test void differentKeysNotMerged() {
        var agg = new AuditAggregator(60);
        Instant base = Instant.parse("2026-01-01T00:00:00Z");
        agg.submit(new HashMap<>(Map.of("actor_key", "agent:a", "capability", "search",
            "failure_type", "scope_insufficient", "timestamp", base.toString())));
        agg.submit(new HashMap<>(Map.of("actor_key", "agent:b", "capability", "search",
            "failure_type", "scope_insufficient", "timestamp", base.toString())));
        List<Object> results = agg.flush(base.plusSeconds(61));
        assertEquals(2, results.size());
    }

    @Test void doesNotFlushOpenWindows() {
        var agg = new AuditAggregator(60);
        Instant now = Instant.parse("2026-01-01T00:00:30Z");
        agg.submit(new HashMap<>(Map.of("actor_key", "agent:test", "capability", "search",
            "failure_type", "scope_insufficient", "timestamp", now.toString())));
        List<Object> results = agg.flush(now.plusSeconds(10));
        assertEquals(0, results.size());
    }
}
```

- [ ] **Step 2: Write implementation**

```java
package dev.anip.service;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Time-window bucketed audit aggregation per SPEC §6.9.
 * Groups low-value denial events and emits aggregated entries at window close.
 */
public class AuditAggregator {

    private final long windowSeconds;
    private final Map<WindowKey, Bucket> windows = new ConcurrentHashMap<>();

    public AuditAggregator(int windowSeconds) {
        this.windowSeconds = windowSeconds;
    }

    public synchronized void submit(Map<String, Object> event) {
        String actorKey = strOr(event, "actor_key", "anonymous");
        String capability = strOr(event, "capability", "_pre_auth");
        String failureType = strOr(event, "failure_type", "unknown");

        Instant ts = parseTimestamp(event);
        long epoch = ts.getEpochSecond() - (ts.getEpochSecond() % windowSeconds);

        var wk = new WindowKey(actorKey, capability, failureType, epoch);
        var bucket = windows.computeIfAbsent(wk, k -> {
            String detail = (String) event.get("detail");
            if (detail != null && detail.length() > 200) detail = detail.substring(0, 200);
            return new Bucket(ts, detail);
        });
        bucket.events.add(event);
        if (ts.isAfter(bucket.lastSeen)) bucket.lastSeen = ts;
    }

    public synchronized List<Object> flush(Instant now) {
        List<Object> results = new ArrayList<>();
        long nowEpoch = now.getEpochSecond();

        var it = windows.entrySet().iterator();
        while (it.hasNext()) {
            var e = it.next();
            var wk = e.getKey();
            var bucket = e.getValue();
            long windowEnd = wk.epoch + windowSeconds;
            if (windowEnd > nowEpoch) continue;

            String windowStart = Instant.ofEpochSecond(wk.epoch).toString();
            String windowEndStr = Instant.ofEpochSecond(windowEnd).toString();

            if (bucket.events.size() == 1) {
                results.add(bucket.events.get(0));
            } else {
                Map<String, Object> aggregated = new LinkedHashMap<>();
                aggregated.put("entry_type", "aggregated");
                aggregated.put("event_class", "repeated_low_value_denial");
                aggregated.put("retention_tier", "aggregate_only");
                aggregated.put("grouping_key", Map.of(
                    "actor_key", wk.actorKey,
                    "capability", wk.capability,
                    "failure_type", wk.failureType
                ));
                aggregated.put("aggregation_window", Map.of("start", windowStart, "end", windowEndStr));
                aggregated.put("aggregation_count", bucket.events.size());
                aggregated.put("count", bucket.events.size());
                aggregated.put("first_seen", bucket.firstSeen.toString());
                aggregated.put("last_seen", bucket.lastSeen.toString());
                aggregated.put("representative_detail", bucket.representativeDetail);
                aggregated.put("capability", wk.capability);
                aggregated.put("failure_type", wk.failureType);
                aggregated.put("success", false);
                results.add(aggregated);
            }
            it.remove();
        }
        return results;
    }

    private static String strOr(Map<String, Object> m, String key, String def) {
        Object v = m.get(key);
        return v instanceof String s && !s.isEmpty() ? s : def;
    }

    private static Instant parseTimestamp(Map<String, Object> event) {
        Object ts = event.get("timestamp");
        if (ts instanceof String s) {
            try { return Instant.parse(s); } catch (Exception ignored) {}
        }
        return Instant.now();
    }

    private record WindowKey(String actorKey, String capability, String failureType, long epoch) {}

    private static class Bucket {
        final List<Map<String, Object>> events = new ArrayList<>();
        final Instant firstSeen;
        Instant lastSeen;
        final String representativeDetail;
        Bucket(Instant firstSeen, String detail) {
            this.firstSeen = firstSeen;
            this.lastSeen = firstSeen;
            this.representativeDetail = detail;
        }
    }
}
```

- [ ] **Step 3: Run tests and commit**

```bash
cd packages/java && mvn test -pl anip-service -am -q
git add packages/java/anip-service/src/main/java/dev/anip/service/AuditAggregator.java \
       packages/java/anip-service/src/test/java/dev/anip/servicetest/AuditAggregatorTest.java
git commit -m "feat(java): add time-window audit aggregation (§6.9)"
```

---

## Task 7: Extend AuditEntry Model + ServiceConfig

**Files:**
- Modify: `packages/java/anip-core/src/main/java/dev/anip/core/AuditEntry.java`
- Modify: `packages/java/anip-service/src/main/java/dev/anip/service/ServiceConfig.java`

- [ ] **Step 1: Add aggregation fields to AuditEntry**

Add after `entryType` field, before `streamSummary`:
```java
    private Map<String, String> groupingKey;
    private Map<String, String> aggregationWindow;
    private int aggregationCount;
    private String firstSeen;
    private String lastSeen;
    private String representativeDetail;
```

Add corresponding getters/setters following the existing pattern (Jackson snake_case via `@JsonProperty`).

- [ ] **Step 2: Add config fields to ServiceConfig**

Add after `retentionIntervalSeconds`:
```java
    private RetentionPolicy retentionPolicy;
    private String disclosureLevel = "full";
    private Map<String, String> disclosurePolicy;
    private int aggregationWindowSeconds;
```

Add fluent setters:
```java
    public ServiceConfig setRetentionPolicy(RetentionPolicy retentionPolicy) {
        this.retentionPolicy = retentionPolicy;
        return this;
    }
    public RetentionPolicy getRetentionPolicy() { return retentionPolicy; }

    public ServiceConfig setDisclosureLevel(String disclosureLevel) {
        this.disclosureLevel = disclosureLevel;
        return this;
    }
    public String getDisclosureLevel() { return disclosureLevel; }

    public ServiceConfig setDisclosurePolicy(Map<String, String> disclosurePolicy) {
        this.disclosurePolicy = disclosurePolicy;
        return this;
    }
    public Map<String, String> getDisclosurePolicy() { return disclosurePolicy; }

    public ServiceConfig setAggregationWindowSeconds(int aggregationWindowSeconds) {
        this.aggregationWindowSeconds = aggregationWindowSeconds;
        return this;
    }
    public int getAggregationWindowSeconds() { return aggregationWindowSeconds; }
```

Import `dev.anip.service.RetentionPolicy` will need to be added. Note: ServiceConfig is in the service module so this is fine.

- [ ] **Step 3: Run tests and commit**

```bash
cd packages/java && mvn test -pl anip-service -am -q
git add packages/java/anip-core/src/main/java/dev/anip/core/AuditEntry.java \
       packages/java/anip-service/src/main/java/dev/anip/service/ServiceConfig.java
git commit -m "feat(java): extend AuditEntry model and ServiceConfig for security hardening"
```

---

## Task 8: Wire Everything into ANIPService

**Files:**
- Modify: `packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java`

This is the integration task. Changes needed:

- [ ] **Step 1: Add instance fields**

After the existing fields in ANIPService, add:
```java
    private RetentionPolicy retentionPolicy;
    private String disclosureLevel;
    private Map<String, String> disclosurePolicy;
    private AuditAggregator aggregator;
```

- [ ] **Step 2: Wire in constructor/start**

In the constructor or `start()` method, initialize from config:
```java
    this.retentionPolicy = config.getRetentionPolicy() != null
        ? config.getRetentionPolicy() : new RetentionPolicy(null, null);
    this.disclosureLevel = config.getDisclosureLevel() != null
        ? config.getDisclosureLevel() : "full";
    this.disclosurePolicy = config.getDisclosurePolicy();
    if (config.getAggregationWindowSeconds() > 0) {
        this.aggregator = new AuditAggregator(config.getAggregationWindowSeconds());
    }
```

Start aggregator flush thread in `start()` alongside retention/checkpoint workers.

- [ ] **Step 3: Update appendAuditEntry**

Add `sideEffectType` parameter. Compute classification, retention, storage redaction:
```java
    String eventClass = EventClassification.classify(sideEffectType, success, failureType);
    String tier = retentionPolicy.resolveTier(eventClass);
    String expiresAt = retentionPolicy.computeExpiresAt(tier, Instant.now());
    entry.setEventClass(eventClass);
    entry.setRetentionTier(tier);
    entry.setExpiresAt(expiresAt);

    // Storage redaction
    if (StorageRedaction.isLowValue(eventClass)) {
        entry.setParameters(null);
        entry.setStorageRedacted(true);
    }

    // Route through aggregator if applicable
    if (aggregator != null && "malformed_or_spam".equals(eventClass)) {
        aggregator.submit(entryToMap(entry));
        return;
    }
```

- [ ] **Step 4: Update all appendAuditEntry call sites**

Add `capDef.getDeclaration().getSideEffect().getType()` parameter to all calls. For unknown capability (no capDef), pass `null`.

- [ ] **Step 5: Add failure redaction to invoke responses**

For each failure response in `invoke()`, compute effective disclosure level and redact:
```java
    Map<String, Object> tokenClaims = tokenClaimsMap(token);
    String effectiveLevel = DisclosureControl.resolve(disclosureLevel, tokenClaims, disclosurePolicy);
    failure = FailureRedaction.redact(failure, effectiveLevel);
```

Add `tokenClaimsMap` helper:
```java
    private Map<String, Object> tokenClaimsMap(DelegationToken token) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("scope", token.getScope());
        if (token.getCallerClass() != null && !token.getCallerClass().isEmpty()) {
            claims.put("anip:caller_class", token.getCallerClass());
        }
        return claims;
    }
```

- [ ] **Step 6: Update discovery posture**

In `getDiscovery()`, replace hardcoded retention/disclosure with:
```java
    Map<String, Object> failureDisc = new LinkedHashMap<>();
    failureDisc.put("detail_level", disclosureLevel);
    if ("policy".equals(disclosureLevel) && disclosurePolicy != null) {
        failureDisc.put("caller_classes", new ArrayList<>(disclosurePolicy.keySet()));
    }
```
Use `retentionPolicy.getDefaultRetention()` for audit retention.

- [ ] **Step 7: Add aggregator flush thread + helpers**

```java
    private void runAggregatorFlush() {
        while (!Thread.currentThread().isInterrupted()) {
            try { Thread.sleep(10_000); } catch (InterruptedException e) { break; }
            flushAggregator();
        }
        flushAggregator(); // final flush on shutdown
    }

    private void flushAggregator() {
        List<Object> results = aggregator.flush(Instant.now());
        for (Object item : results) {
            @SuppressWarnings("unchecked")
            Map<String, Object> entryData = item instanceof Map
                ? StorageRedaction.redactEntry((Map<String, Object>) item)
                : StorageRedaction.redactEntry((Map<String, Object>) item);
            persistAuditMap(entryData);
        }
    }
```

- [ ] **Step 8: Run all tests**

```bash
cd packages/java && mvn verify -q
```

- [ ] **Step 9: Commit**

```bash
git add packages/java/anip-service/src/main/java/dev/anip/service/ANIPService.java
git commit -m "feat(java): integrate classification, redaction, aggregation into invoke flow"
```

---

## Task 9: Run Conformance Suite

- [ ] **Step 1: Build and start**

```bash
cd packages/java && mvn package -pl anip-example-flights -am -DskipTests -q
java -jar anip-example-flights/target/anip-example-flights-0.11.0.jar &
sleep 8
```

- [ ] **Step 2: Run conformance**

```bash
pytest conformance/ \
  --base-url=http://localhost:8080 \
  --bootstrap-bearer=demo-human-key \
  --sample-inputs=conformance/samples/flight-service.json \
  -v
```

Expected: 43 passed, 1 skipped

- [ ] **Step 3: Clean up and commit any fixups**

---

## Task 10: Create PR

```bash
git checkout -b feat/java-security-hardening
git push -u origin feat/java-security-hardening
gh pr create --title "feat(java): add v0.8-v0.9 security hardening"
```
