package dev.anip.servicetest;

import dev.anip.service.AuditAggregator;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class AuditAggregatorTest {
    @Test void singleEventPassesThrough() {
        var agg = new AuditAggregator(60);
        Instant now = Instant.parse("2026-01-01T00:00:30Z");
        agg.submit(new HashMap<>(Map.of(
            "actor_key", "agent:test", "capability", "search",
            "failure_type", "scope_insufficient", "timestamp", now.toString())));
        var results = agg.flush(now.plusSeconds(31));
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
                "detail", "first detail")));
        }
        var results = agg.flush(base.plusSeconds(61));
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
        assertEquals(2, agg.flush(base.plusSeconds(61)).size());
    }

    @Test void doesNotFlushOpenWindows() {
        var agg = new AuditAggregator(60);
        Instant now = Instant.parse("2026-01-01T00:00:30Z");
        agg.submit(new HashMap<>(Map.of("actor_key", "agent:test", "capability", "search",
            "failure_type", "scope_insufficient", "timestamp", now.toString())));
        assertEquals(0, agg.flush(now.plusSeconds(10)).size());
    }
}
