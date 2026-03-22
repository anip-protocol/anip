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
            assertNull(result.get("parameters"), ec);
            assertEquals(true, result.get("storage_redacted"), ec);
        }
    }
    @Test void highValuePreservesParameters() {
        for (String ec : new String[]{"high_risk_success", "high_risk_denial"}) {
            var entry = new HashMap<>(Map.of("event_class", ec, "parameters", Map.of("origin", "SEA")));
            var result = StorageRedaction.redactEntry(entry);
            assertNotNull(result.get("parameters"), ec);
            assertEquals(false, result.get("storage_redacted"), ec);
        }
    }
    @Test void doesNotMutateOriginal() {
        var entry = new HashMap<>(Map.of("event_class", "low_risk_success", "parameters", Map.of("origin", "SEA")));
        StorageRedaction.redactEntry(entry);
        assertNotNull(entry.get("parameters"));
    }
}
