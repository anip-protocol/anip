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
        assertEquals("short", rp.resolveTier("unknown_class"));
    }
    @Test void computeExpiresAt() {
        var rp = new RetentionPolicy(null, null);
        Instant now = Instant.parse("2026-01-01T00:00:00Z");
        String exp = rp.computeExpiresAt("long", now);
        assertNotNull(exp);
        assertEquals(365, ChronoUnit.DAYS.between(now, Instant.parse(exp)));
    }
    @Test void defaultRetention() {
        assertEquals("P90D", new RetentionPolicy(null, null).getDefaultRetention());
    }
    @Test void customOverrides() {
        var rp = new RetentionPolicy(
            java.util.Map.of("low_risk_success", "long"),
            java.util.Map.of("short", "P14D")
        );
        assertEquals("long", rp.resolveTier("low_risk_success"));
        Instant now = Instant.parse("2026-01-01T00:00:00Z");
        assertEquals(14, ChronoUnit.DAYS.between(now, Instant.parse(rp.computeExpiresAt("short", now))));
    }
}
