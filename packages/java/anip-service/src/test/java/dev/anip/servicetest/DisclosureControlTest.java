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
